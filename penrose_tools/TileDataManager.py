# penrose_tools/TileDataManager.py
"""
Manages tile lifecycle for the overlay rendering system.
- Generates OverlayTile objects using pentagrid math
- Builds neighbor graph via edge hashing
- Detects star/starburst patterns using spatial vertex index (O(1) per lookup)
- Runs generation on a background thread to avoid render stalls
- Implements comfort zone / generation zone viewport management
"""
import cmath
import logging
import math
import threading
import time
import numpy as np
from penrose_tools.OverlayTile import OverlayTile


class TileDataManager:
    """
    CPU-side tile data manager for the overlay system.
    Generates tiles, computes neighbors and patterns, and provides
    packed GPU buffer data. All heavy work runs on a background thread.
    """

    def __init__(self):
        self.logger = logging.getLogger('TileDataManager')

        # Fifth roots of unity (same as Operations)
        self.zeta = [cmath.exp(2j * cmath.pi * i / 5) for i in range(5)]

        # Current tile set keyed by (r, s, kr, ks)
        self.tiles = {}          # dict[tuple, OverlayTile]
        self.tile_list = []      # ordered list for GPU buffer packing
        self._tile_index_map = {}  # id(tile) → index for O(1) lookup

        # Viewport zones (in world/ribbon space)
        self.gen_bounds = None   # (min_x, min_y, max_x, max_y) - generation zone
        self.comfort_bounds = None  # comfort zone - regen triggers when camera exits this

        # Background thread state
        self._lock = threading.Lock()
        self._worker_thread = None
        self._pending_result = None  # (tiles_dict, tile_list) from background thread
        self._pending_request = None  # queued request when worker is busy
        self._generation_in_progress = False
        self._shutdown = False

        # GPU buffer data (packed numpy arrays, ready for upload)
        self.gpu_vertices = None     # float32, shape (N, 4, 2) - quad corners
        self.gpu_tile_data = None    # float32, shape (N, 8) - per-tile attributes
        self.gpu_data_dirty = False  # True when new data is ready for upload
        self.tile_count = 0

        # Pattern detection stats
        self.star_count = 0
        self.starburst_count = 0

        # Current gamma (needed for ribbon->camera space conversion)
        self._current_gamma = [0.0, 0.0, 0.0, 0.0, 0.0]

        # Tile geometry cache: reuse tiles across regenerations when gamma is unchanged.
        # Keyed by (r, s, kr, ks) -> OverlayTile with valid vertices.
        self._tile_cache = {}         # dict[tuple, OverlayTile]
        self._cache_gamma = None      # gamma tuple the cache was built with

        # Two-pass staged results for incremental loading
        self._staged_geometry = None   # (tiles_dict, tile_list, gpu_verts, gpu_data,
                                       #  gen_bounds, comfort_bounds, gamma, gen_id)
        self._staged_patterns = None   # (pattern_type_col, blend_factor_col, stars, bursts, gen_id)

        # Carry-over blend map: preserve blend_factor from previous generation
        # so Pass 1 geometry doesn't flash to flat 0.5 while Pass 2 computes
        self._prev_blend_map = {}      # dict[(r,s,kr,ks) -> float]

        # Generation ID for interruption handling
        self._generation_id = 0
        self._active_generation_id = 0

    def shutdown(self):
        """Signal background thread to stop."""
        self._shutdown = True
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)

    # -------------------------------------------------------------------------
    # Viewport zone management
    # -------------------------------------------------------------------------

    def needs_regeneration(self, camera_x, camera_y, zoom, aspect):
        """Check if camera has moved outside the comfort zone."""
        if self.comfort_bounds is None:
            return True

        half_h = 3.0 / zoom
        half_w = half_h * aspect
        view_min_x = camera_x - half_w
        view_max_x = camera_x + half_w
        view_min_y = camera_y - half_h
        view_max_y = camera_y + half_h

        cmin_x, cmin_y, cmax_x, cmax_y = self.comfort_bounds
        return (view_min_x < cmin_x or view_max_x > cmax_x or
                view_min_y < cmin_y or view_max_y > cmax_y)

    def _compute_zones(self, camera_x, camera_y, zoom, aspect,
                        velocity_x=0.0, velocity_y=0.0):
        """Compute generation zone and comfort zone.

        Both zones scale with velocity to provide more runway at high speed.
        The generation zone is biased in the movement direction so tiles are
        ready before the user pans into view.
        """
        half_h = 3.0 / zoom
        half_w = half_h * aspect

        # Velocity-based bias: shift the zones ahead of movement direction.
        speed = (velocity_x ** 2 + velocity_y ** 2) ** 0.5
        # Adaptive factor: 0.0 at rest, 1.0 at speed >= 0.2
        speed_factor = min(1.0, speed * 5.0)

        if speed > 0.0001:
            # Bias up to 60% of viewport in the movement direction
            bias_scale = min(0.6, speed * 4.0)
            bias_x = (velocity_x / speed) * half_w * bias_scale
            bias_y = (velocity_y / speed) * half_h * bias_scale
        else:
            bias_x = 0.0
            bias_y = 0.0

        cx = camera_x + bias_x
        cy = camera_y + bias_y

        # Generation zone: 80-120% larger than viewport (scales with speed)
        gen_margin_w = half_w * (0.8 + 0.4 * speed_factor)
        gen_margin_h = half_h * (0.8 + 0.4 * speed_factor)
        gen_bounds = (
            cx - half_w - gen_margin_w,
            cy - half_h - gen_margin_h,
            cx + half_w + gen_margin_w,
            cy + half_h + gen_margin_h,
        )

        # Comfort zone: 40-70% larger than viewport (scales with speed)
        comfort_margin_w = half_w * (0.4 + 0.3 * speed_factor)
        comfort_margin_h = half_h * (0.4 + 0.3 * speed_factor)
        comfort_bounds = (
            cx - half_w - comfort_margin_w,
            cy - half_h - comfort_margin_h,
            cx + half_w + comfort_margin_w,
            cy + half_h + comfort_margin_h,
        )

        return gen_bounds, comfort_bounds

    # -------------------------------------------------------------------------
    # Public API: request generation (non-blocking)
    # -------------------------------------------------------------------------

    def request_generation(self, camera_x, camera_y, zoom, aspect, gamma,
                           velocity_x=0.0, velocity_y=0.0):
        """
        Request tile generation for the given viewport.
        Runs on a background thread. Non-blocking.
        If a worker is already running, the request is queued as pending.
        The running worker completes normally; when done, _finish_worker
        launches the pending request with a fresh generation ID.
        """
        gen_bounds, comfort_bounds = self._compute_zones(
            camera_x, camera_y, zoom, aspect, velocity_x, velocity_y)

        if self._generation_in_progress:
            # Queue as pending — will be launched when current worker finishes.
            # Don't increment _active_generation_id here: let the current
            # worker finish so it can deliver its results. The pending request
            # will get a fresh ID when _finish_worker launches it.
            self._pending_request = (gen_bounds, comfort_bounds, gamma)
            return

        self._generation_id += 1
        self._active_generation_id = self._generation_id
        self._launch_worker(gen_bounds, comfort_bounds, gamma, self._generation_id)

    def _launch_worker(self, gen_bounds, comfort_bounds, gamma, generation_id):
        """Start a background generation thread."""
        self._generation_in_progress = True
        self._worker_thread = threading.Thread(
            target=self._generate_worker,
            args=(gen_bounds, comfort_bounds, gamma, generation_id),
            daemon=True
        )
        self._worker_thread.start()

    def poll_geometry(self):
        """Check if Pass 1 (geometry + GPU arrays) results are ready.
        If so, swap in tile data and return staged GPU arrays.
        Returns (gpu_vertices, gpu_tile_data, tile_count, generation_id) or None.
        """
        if self._staged_geometry is None:
            return None

        with self._lock:
            staged = self._staged_geometry
            self._staged_geometry = None

        (tiles_dict, tile_list, gpu_vertices, gpu_tile_data,
         gen_bounds, comfort_bounds, gamma, generation_id) = staged

        self.tiles = tiles_dict
        self.tile_list = tile_list
        self.gen_bounds = gen_bounds
        self.comfort_bounds = comfort_bounds
        self.tile_count = len(tile_list)
        self._current_gamma = gamma
        self.gpu_vertices = gpu_vertices
        self.gpu_tile_data = gpu_tile_data

        # Build O(1) tile->index lookup
        self._tile_index_map = {id(tile): i for i, tile in enumerate(tile_list)}

        self.logger.info(f"Geometry ready: {self.tile_count} tiles (gen_id={generation_id})")
        return (gpu_vertices, gpu_tile_data, self.tile_count, generation_id)

    def poll_patterns(self):
        """Check if Pass 2 (pattern detection) results are ready.
        Returns (pattern_type_col, blend_factor_col, stars, bursts,
                 symmetry_tile_ids, generation_id) or None.
        """
        if self._staged_patterns is None:
            return None

        with self._lock:
            staged = self._staged_patterns
            self._staged_patterns = None

        # Save blend map for carry-over to next generation's Pass 1
        (pattern_type_col, blend_factor_col, stars, bursts,
         symmetry_tile_ids, gen_id) = staged
        if self.tile_list and len(self.tile_list) == len(blend_factor_col):
            blend_map = {}
            for i, tile in enumerate(self.tile_list):
                key = (tile.r, tile.s, tile.kr, tile.ks)
                blend_map[key] = (float(blend_factor_col[i]), float(pattern_type_col[i]))
            self._prev_blend_map = blend_map

        return staged

    # -------------------------------------------------------------------------
    # Background worker
    # -------------------------------------------------------------------------

    def _finish_worker(self):
        """Called at the end of a worker run. Launches pending request if any."""
        self._generation_in_progress = False
        pending = self._pending_request
        self._pending_request = None
        if pending is not None and not self._shutdown:
            gen_bounds, comfort_bounds, gamma = pending
            self._generation_id += 1
            self._active_generation_id = self._generation_id
            self._launch_worker(gen_bounds, comfort_bounds, gamma, self._generation_id)

    def _generate_worker(self, gen_bounds, comfort_bounds, gamma, generation_id):
        """Background thread: two-pass generation.
        Pass 1: tiles + GPU buffer packing (geometry only, default patterns).
        Pass 2: neighbors + patterns -> pattern patch columns.
        """
        try:
            t0 = time.perf_counter()

            # Check if gamma changed — invalidate tile cache
            gamma_tuple = tuple(round(g, 6) for g in gamma)
            if self._cache_gamma != gamma_tuple:
                self._tile_cache = {}
                self._cache_gamma = gamma_tuple

            tiles_dict = self._generate_tiles(gen_bounds, gamma, generation_id)
            tile_list = list(tiles_dict.values())
            t1 = time.perf_counter()

            # Pack GPU arrays with default pattern values (runs on background thread)
            gpu_vertices, gpu_tile_data = self._pack_gpu_buffers_staged(tile_list, gamma)
            t2 = time.perf_counter()

            # Check for interruption before posting Pass 1
            if self._shutdown or generation_id != self._active_generation_id:
                self._finish_worker()
                return

            with self._lock:
                self._staged_geometry = (
                    tiles_dict, tile_list, gpu_vertices, gpu_tile_data,
                    gen_bounds, comfort_bounds, gamma, generation_id
                )

            self.logger.debug(
                f"Pass 1: {len(tile_list)} tiles in {(t1-t0)*1000:.1f}ms, "
                f"pack {(t2-t1)*1000:.1f}ms"
            )

            # --- Pass 2: Neighbors + pattern detection ---
            if generation_id != self._active_generation_id:
                self._finish_worker()
                return

            self._calculate_neighbors(tile_list)
            t3 = time.perf_counter()

            if generation_id != self._active_generation_id:
                self._finish_worker()
                return

            stars, bursts, symmetry_tile_ids = self._detect_patterns(tile_list)
            t4 = time.perf_counter()

            # Build pattern patch: the two columns that changed
            n = len(tile_list)
            pattern_type_col = np.array([t.pattern_type for t in tile_list], dtype=np.float32)
            blend_factor_col = np.array([t.blend_factor for t in tile_list], dtype=np.float32)

            # Check for interruption before posting Pass 2
            if self._shutdown or generation_id != self._active_generation_id:
                self._finish_worker()
                return

            with self._lock:
                self._staged_patterns = (
                    pattern_type_col, blend_factor_col, stars, bursts,
                    symmetry_tile_ids, generation_id
                )

            # Update tile cache
            self._tile_cache = tiles_dict

            self.logger.debug(
                f"Pass 2: neighbors {(t3-t2)*1000:.1f}ms, "
                f"patterns {(t4-t3)*1000:.1f}ms"
            )

            self._finish_worker()

        except Exception as e:
            self.logger.error(f"Tile generation failed: {e}", exc_info=True)
            self._finish_worker()

    # -------------------------------------------------------------------------
    # Tile generation (pentagrid math)
    # -------------------------------------------------------------------------

    def _generate_tiles(self, gen_bounds, gamma, generation_id=None):
        """Generate OverlayTile objects covering the generation zone (vectorized).

        For each (r, s) direction pair, all (kr, ks) grid intersections are
        computed in bulk using NumPy, then bounds-checked with vectorized ops.
        Only the surviving tiles are constructed as OverlayTile objects.
        """
        min_x, min_y, max_x, max_y = gen_bounds

        # Precompute zeta as numpy complex128 array
        zeta = np.array(self.zeta, dtype=np.complex128)      # (5,)
        gamma_arr = np.array(gamma, dtype=np.float64)         # (5,)

        # shift_offset for ribbon -> camera conversion
        shift_offset = np.sum(zeta * gamma_arr)
        inv_2_5 = 1.0 / 2.5

        # Precompute zeta reciprocals for the k-vector floor computation
        # k[d] = ceil(Re(z0 / zeta[d]) + gamma[d])  (the 0 - -x // 1 trick)
        zeta_inv = 1.0 / zeta  # (5,) complex

        # Viewport center and search radius
        cx = (min_x + max_x) * 0.5
        cy = (min_y + max_y) * 0.5
        hw = (max_x - min_x) * 0.5
        hh = (max_y - min_y) * 0.5
        viewport_radius = max(hw, hh)

        # Center indices for each pentagrid direction
        thetas = 2.0 * math.pi * np.arange(5) / 5.0
        center_indices = cx * np.cos(thetas) + cy * np.sin(thetas) + gamma_arr
        search_radius = int(viewport_radius * 2.5) + 3

        # The 4 vertex corner offsets for each rhombus: (dkr, dks)
        corner_offsets = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=np.float64)  # (4, 2)

        tiles_dict = {}

        for r in range(5):
            kr_center = int(round(center_indices[r]))
            zeta_r = zeta[r]
            for s in range(r + 1, 5):
                if self._shutdown or (generation_id is not None
                                      and generation_id != self._active_generation_id):
                    return tiles_dict

                ks_center = int(round(center_indices[s]))
                zeta_s = zeta[s]
                denom = zeta[s - r].imag  # scalar

                # Build all (kr, ks) pairs for this (r, s) as arrays
                kr_range = np.arange(kr_center - search_radius, kr_center + search_radius + 1, dtype=np.float64)
                ks_range = np.arange(ks_center - search_radius, ks_center + search_radius + 1, dtype=np.float64)
                KR, KS = np.meshgrid(kr_range, ks_range, indexing='ij')
                kr_flat = KR.ravel()  # (M,)
                ks_flat = KS.ravel()  # (M,)
                M = len(kr_flat)

                # ---- Vectorized z0 computation ----
                # z0 = 1j * (zeta[r] * (ks - gamma[s]) - zeta[s] * (kr - gamma[r])) / denom
                z0 = 1j * (zeta_r * (ks_flat - gamma_arr[s]) - zeta_s * (kr_flat - gamma_arr[r])) / denom
                z0 = np.round(z0.real, 5) + 1j * np.round(z0.imag, 5)  # (M,) complex

                # ---- Vectorized k-vector: k[d] = ceil(Re(z0 / zeta[d]) + gamma[d]) ----
                # z0[:, None] / zeta[None, :] -> (M, 5)
                z0_over_zeta = z0[:, None] * zeta_inv[None, :]  # (M, 5) complex
                k_base = np.floor(z0_over_zeta.real + gamma_arr[None, :]).astype(np.float64)
                # The original uses: 0 - -(Re(z0/t) + p) // 1  which equals ceil(...) for non-integer
                # np.floor gives the //1 part; 0 - -x//1 = -(-x//1) = ceil(x) for non-integers
                k_base = -np.floor(-(z0_over_zeta.real + gamma_arr[None, :]))  # (M, 5)

                # ---- Vectorized 4 vertices per tile ----
                # For each corner (dkr, dks), set k[r] = kr + dkr, k[s] = ks + dks
                # vertex = sum(k[d] * zeta[d] for d in range(5))
                # = sum(k_base[d] * zeta[d]) + dkr * zeta[r] + dks * zeta[s]  (since only k[r],k[s] change)
                #
                # base_vertex = sum over d of k_base[d] * zeta[d]
                # but k_base[r] and k_base[s] are overwritten by kr, ks in the original code
                # So: vertex = sum_{d != r,s}(k_base[d] * zeta[d]) + (kr+dkr)*zeta[r] + (ks+dks)*zeta[s]

                # Sum over non-(r,s) directions
                mask = np.ones(5, dtype=bool)
                mask[r] = False
                mask[s] = False
                # base_sum = sum of k_base[d] * zeta[d] for d not in {r, s}
                base_sum = np.sum(k_base[:, mask] * zeta[None, mask], axis=1)  # (M,) complex

                # 4 vertices: shape (M, 4) complex
                all_verts = np.empty((M, 4), dtype=np.complex128)
                for ci, (dkr, dks) in enumerate(corner_offsets):
                    all_verts[:, ci] = base_sum + (kr_flat + dkr) * zeta_r + (ks_flat + dks) * zeta_s
                # Round to 5 decimals
                all_verts = np.round(all_verts.real, 5) + 1j * np.round(all_verts.imag, 5)

                # ---- Vectorized bounds check in camera space ----
                # p_cam = (ribbon - shift_offset) / 2.5
                cam_verts = (all_verts - shift_offset) * inv_2_5  # (M, 4) complex
                cam_x = cam_verts.real  # (M, 4)
                cam_y = cam_verts.imag  # (M, 4)

                # Tile is in bounds if ANY of its 4 vertices is inside gen_bounds
                in_x = (cam_x >= min_x) & (cam_x <= max_x)  # (M, 4) bool
                in_y = (cam_y >= min_y) & (cam_y <= max_y)
                in_bounds = np.any(in_x & in_y, axis=1)  # (M,) bool

                # ---- Create OverlayTile objects only for visible tiles ----
                # Reuse cached tiles when gamma hasn't changed (vertices are identical)
                cache = self._tile_cache
                indices = np.nonzero(in_bounds)[0]
                for idx in indices:
                    ki = int(kr_flat[idx])
                    ksi = int(ks_flat[idx])
                    key = (r, s, ki, ksi)
                    if key not in tiles_dict:
                        cached = cache.get(key)
                        if cached is not None:
                            tiles_dict[key] = cached
                        else:
                            v = all_verts[idx]
                            tile_verts = [v[0], v[1], v[2], v[3]]
                            tiles_dict[key] = OverlayTile(tile_verts, r, s, ki, ksi)

        return tiles_dict

    # -------------------------------------------------------------------------
    # Neighbor calculation (edge hashing)
    # -------------------------------------------------------------------------

    def _calculate_neighbors(self, tile_list):
        """Build neighbor graph using edge hashing. O(N) where N = number of tiles.

        Uses raw vertex values (already rounded to 5dp from generation) as edge
        keys, avoiding the overhead of normalized_edge() / edges() method calls.
        """
        edge_map = {}  # (v_lo, v_hi) -> [tile, ...]

        for tile in tile_list:
            tile.neighbors = []  # reset
            verts = tile.vertices
            n = len(verts)
            for i in range(n):
                v1 = verts[i]
                v2 = verts[(i + 1) % n]
                # Sort by (real, imag) to normalize edge direction
                if (v1.real, v1.imag) < (v2.real, v2.imag):
                    edge_key = (v1, v2)
                else:
                    edge_key = (v2, v1)
                bucket = edge_map.get(edge_key)
                if bucket is None:
                    edge_map[edge_key] = [tile]
                else:
                    bucket.append(tile)

        # Link tiles sharing an edge (direct list append, skip add_neighbor dedup)
        for tiles_on_edge in edge_map.values():
            if len(tiles_on_edge) == 2:
                t0, t1 = tiles_on_edge
                t0.neighbors.append(t1)
                t1.neighbors.append(t0)

    # -------------------------------------------------------------------------
    # Pattern detection with spatial vertex index
    # -------------------------------------------------------------------------

    def _detect_patterns(self, tile_list):
        """
        Detect star and starburst patterns via single-pass vertex index scan.

        Instead of iterating tiles and searching neighbors for common vertices,
        we build a vertex index and scan it directly.  Each vertex maps to all
        tiles sharing it, so pattern detection is just a count + filter:
          - Star:      exactly 5 valid kites at one vertex
          - Starburst: exactly 10 valid darts at one vertex

        Complexity: O(N) for validity + O(V) for vertex scan, where V ~ 2N.
        """
        # ---- Build vertex index using NumPy-rounded keys ----
        # Bulk-extract all vertices into a flat array, round with NumPy,
        # then scatter back into a dict keyed by (rounded_real, rounded_imag).
        n = len(tile_list)
        all_verts_flat = np.empty(n * 4, dtype=np.complex128)
        for i, tile in enumerate(tile_list):
            verts = tile.vertices
            all_verts_flat[i * 4]     = verts[0]
            all_verts_flat[i * 4 + 1] = verts[1]
            all_verts_flat[i * 4 + 2] = verts[2]
            all_verts_flat[i * 4 + 3] = verts[3]

        # Vectorized round to 3dp
        rounded_real = np.round(all_verts_flat.real, 3)
        rounded_imag = np.round(all_verts_flat.imag, 3)

        # Build vertex -> tiles dict using pre-rounded values
        vertex_to_tiles = {}
        for i, tile in enumerate(tile_list):
            base = i * 4
            for j in range(4):
                idx = base + j
                rk = (rounded_real[idx], rounded_imag[idx])
                bucket = vertex_to_tiles.get(rk)
                if bucket is None:
                    vertex_to_tiles[rk] = [tile]
                else:
                    bucket.append(tile)

        # ---- Pre-compute validity flags with fast neighbor counting ----
        # A valid star kite: is_kite=True and exactly 2 dart neighbors
        # A valid starburst dart: is_kite=False and exactly 2 dart neighbors
        valid_star_kite = set()
        valid_burst_dart = set()
        for tile in tile_list:
            # Count dart neighbors using a simple loop (faster than generator + sum)
            dart_count = 0
            for n in tile.neighbors:
                if not n.is_kite:
                    dart_count += 1
            if dart_count == 2:
                if tile.is_kite:
                    valid_star_kite.add(id(tile))
                else:
                    valid_burst_dart.add(id(tile))

        pattern_tiles = set()   # tile ids already claimed by a pattern
        star_groups = []
        burst_groups = []

        # ---- Single pass over vertex index ----
        for tiles_at_v in vertex_to_tiles.values():
            count = len(tiles_at_v)

            # Quick rejection: stars need 5+ tiles, starbursts need 10+
            if count < 5:
                continue

            # --- Star: 5 valid kites sharing this vertex ---
            if count >= 5:
                star_candidates = [t for t in tiles_at_v
                                   if id(t) in valid_star_kite and id(t) not in pattern_tiles]
                if len(star_candidates) == 5:
                    star_groups.append(star_candidates)
                    for t in star_candidates:
                        pattern_tiles.add(id(t))
                    continue

            # --- Starburst: 10 valid darts sharing this vertex ---
            if count >= 10:
                burst_candidates = [t for t in tiles_at_v
                                    if id(t) in valid_burst_dart and id(t) not in pattern_tiles]
                if len(burst_candidates) == 10:
                    burst_groups.append(burst_candidates)
                    for t in burst_candidates:
                        pattern_tiles.add(id(t))

        # ---- Collect star/burst tile IDs ----
        star_ids = set()
        for group in star_groups:
            for t in group:
                star_ids.add(id(t))
        burst_ids = set()
        for group in burst_groups:
            for t in group:
                burst_ids.add(id(t))

        # ---- Detect 5-fold symmetric vertices ----
        # Vertices shared by exactly 5 or 10 tiles are 5-fold symmetric
        # (stars, starbursts, and other Penrose vertex figures)
        symmetry_tile_ids = set()
        for tiles_at_v in vertex_to_tiles.values():
            count = len(tiles_at_v)
            if count == 5 or count == 10:
                for t in tiles_at_v:
                    symmetry_tile_ids.add(id(t))

        # ---- Spatial region blend via iterative neighbor diffusion ----
        # Seed each tile with its is_kite value, then average with neighbors
        # over multiple passes to create smooth spatial regions.
        n = len(tile_list)
        blend = np.array([1.0 if t.is_kite else 0.0 for t in tile_list],
                         dtype=np.float64)

        # Build index lookup for fast neighbor resolution
        tile_to_idx = {id(t): i for i, t in enumerate(tile_list)}

        # Pre-build neighbor index lists (once, reused across passes)
        neighbor_indices = []
        for tile in tile_list:
            indices = []
            for nb in tile.neighbors:
                idx = tile_to_idx.get(id(nb))
                if idx is not None:
                    indices.append(idx)
            neighbor_indices.append(indices)

        # Diffusion: 2 passes, each tile = 40% self + 60% neighbor average
        # Very few passes keeps fine-grained, tile-level variation visible
        for _pass in range(2):
            new_blend = np.empty(n, dtype=np.float64)
            for i in range(n):
                nb_idx = neighbor_indices[i]
                if nb_idx:
                    nb_avg = 0.0
                    for j in nb_idx:
                        nb_avg += blend[j]
                    nb_avg /= len(nb_idx)
                    new_blend[i] = blend[i] * 0.4 + nb_avg * 0.6
                else:
                    new_blend[i] = blend[i]
            blend = new_blend

        # Single smoothstep for gentle contrast boost (preserves granularity)
        blend = blend * blend * (3.0 - 2.0 * blend)

        # ---- Assign pattern data to tiles ----
        for i, tile in enumerate(tile_list):
            tid = id(tile)
            if tid in star_ids:
                tile.pattern_type = 1.0
                tile.blend_factor = 0.3
            elif tid in burst_ids:
                tile.pattern_type = 2.0
                tile.blend_factor = 0.7
            else:
                tile.blend_factor = float(blend[i])
                tile.pattern_type = 0.0

        return len(star_groups), len(burst_groups), symmetry_tile_ids

    # -------------------------------------------------------------------------
    # GPU buffer packing
    # -------------------------------------------------------------------------

    def _pack_gpu_buffers_staged(self, tile_list, gamma):
        """Pack tile geometry into numpy arrays (runs on background thread).
        Returns (gpu_vertices, gpu_tile_data). Uses default pattern values
        since pattern detection has not run yet at this stage.
        """
        n = len(tile_list)
        if n == 0:
            return (np.zeros((0, 4, 2), dtype=np.float32),
                    np.zeros((0, 8), dtype=np.float32))

        shift_offset = sum(z * g for z, g in zip(self.zeta, gamma))
        sx, sy = shift_offset.real, shift_offset.imag

        ribbon = np.array(
            [[(v.real, v.imag) for v in tile.vertices[:4]] for tile in tile_list],
            dtype=np.float32)  # (N, 4, 2)

        ribbon[:, :, 0] -= sx
        ribbon[:, :, 1] -= sy
        ribbon *= (1.0 / 2.5)

        data = np.empty((n, 8), dtype=np.float32)
        data[:, 0] = np.array([1.0 if t.is_kite else 0.0 for t in tile_list], dtype=np.float32)

        # Carry over blend_factor and pattern_type from previous generation
        # so tiles don't flash to flat coloring while Pass 2 computes
        prev = self._prev_blend_map
        if prev:
            for i, t in enumerate(tile_list):
                key = (t.r, t.s, t.kr, t.ks)
                if key in prev:
                    data[i, 1] = prev[key][1]  # pattern_type
                    data[i, 2] = prev[key][0]  # blend_factor
                else:
                    data[i, 1] = 0.0
                    data[i, 2] = 0.5
        else:
            data[:, 1] = 0.0   # pattern_type: default (updated in Pass 2)
            data[:, 2] = 0.5   # blend_factor: default (updated in Pass 2)
        data[:, 3] = 0.0   # selected
        data[:, 4] = 0.0   # hovered
        data[:, 5] = 0.0   # anim_phase
        data[:, 6] = 0.0   # anim_type
        data[:, 7] = np.array([float(hash((t.r, t.s, t.kr, t.ks)) % 10000) / 10000.0
                               for t in tile_list], dtype=np.float32)

        return ribbon, data

    def update_tile_interaction(self, tile_index, selected=None, hovered=None,
                                 anim_phase=None, anim_type=None):
        """
        Update interaction state for a single tile without full regeneration.
        Only touches the gpu_tile_data array (partial update).
        """
        if tile_index < 0 or tile_index >= self.tile_count:
            return

        tile = self.tile_list[tile_index]
        if selected is not None:
            tile.selected = selected
            self.gpu_tile_data[tile_index, 3] = 1.0 if selected else 0.0
        if hovered is not None:
            tile.hovered = hovered
            self.gpu_tile_data[tile_index, 4] = 1.0 if hovered else 0.0
        if anim_phase is not None:
            tile.anim_phase = anim_phase
            self.gpu_tile_data[tile_index, 5] = anim_phase
        if anim_type is not None:
            tile.anim_type = anim_type
            self.gpu_tile_data[tile_index, 6] = float(anim_type)

        self.gpu_data_dirty = True

    def hit_test(self, pentagrid_x, pentagrid_y):
        """
        Find which tile contains the given pentagrid-space point.
        Returns tile index or -1 if no tile found.
        Vectorized numpy point-in-quad test against GPU vertex data.
        """
        if self.gpu_vertices is None or self.tile_count == 0:
            return -1

        n = self.tile_count
        v = self.gpu_vertices[:n]  # (N, 4, 2)
        p = np.array([pentagrid_x, pentagrid_y], dtype=np.float32)

        # Compute cross products for all 4 edges of all tiles at once
        # Edge vectors: v[next] - v[current] for each of 4 edges
        v0 = v[:, 0]  # (N, 2)
        v1 = v[:, 1]
        v2 = v[:, 2]
        v3 = v[:, 3]

        def cross2d(edge, w):
            return edge[:, 0] * w[:, 1] - edge[:, 1] * w[:, 0]

        c0 = cross2d(v1 - v0, p - v0)
        c1 = cross2d(v2 - v1, p - v1)
        c2 = cross2d(v3 - v2, p - v2)
        c3 = cross2d(v0 - v3, p - v3)

        # Point is inside if all cross products have the same sign
        all_pos = (c0 >= 0) & (c1 >= 0) & (c2 >= 0) & (c3 >= 0)
        all_neg = (c0 <= 0) & (c1 <= 0) & (c2 <= 0) & (c3 <= 0)
        inside = all_pos | all_neg

        hits = np.where(inside)[0]
        if len(hits) > 0:
            return int(hits[0])
        return -1

    def get_tile_index(self, tile):
        """O(1) lookup of a tile's index in tile_list. Returns -1 if not found."""
        return self._tile_index_map.get(id(tile), -1)

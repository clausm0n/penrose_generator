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

        # Viewport zones (in world/ribbon space)
        self.gen_bounds = None   # (min_x, min_y, max_x, max_y) - generation zone
        self.comfort_bounds = None  # comfort zone - regen triggers when camera exits this

        # Background thread state
        self._lock = threading.Lock()
        self._worker_thread = None
        self._pending_result = None  # (tiles_dict, tile_list) from background thread
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

        # Current gamma (needed for ribbon→camera space conversion in _pack_gpu_buffers)
        self._current_gamma = [0.0, 0.0, 0.0, 0.0, 0.0]

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

    def _compute_zones(self, camera_x, camera_y, zoom, aspect):
        """Compute generation zone (30% oversized) and comfort zone (15% oversized)."""
        half_h = 3.0 / zoom
        half_w = half_h * aspect

        # Generation zone: 30% larger than viewport
        gen_margin_w = half_w * 0.3
        gen_margin_h = half_h * 0.3
        gen_bounds = (
            camera_x - half_w - gen_margin_w,
            camera_y - half_h - gen_margin_h,
            camera_x + half_w + gen_margin_w,
            camera_y + half_h + gen_margin_h,
        )

        # Comfort zone: 15% larger than viewport
        # User can pan within this without triggering regen
        comfort_margin_w = half_w * 0.15
        comfort_margin_h = half_h * 0.15
        comfort_bounds = (
            camera_x - half_w - comfort_margin_w,
            camera_y - half_h - comfort_margin_h,
            camera_x + half_w + comfort_margin_w,
            camera_y + half_h + comfort_margin_h,
        )

        return gen_bounds, comfort_bounds

    # -------------------------------------------------------------------------
    # Public API: request generation (non-blocking)
    # -------------------------------------------------------------------------

    def request_generation(self, camera_x, camera_y, zoom, aspect, gamma):
        """
        Request tile generation for the given viewport.
        Runs on a background thread. Non-blocking.
        Returns immediately; call poll_results() each frame to check for completion.
        """
        if self._generation_in_progress:
            return  # Already working on it

        gen_bounds, comfort_bounds = self._compute_zones(camera_x, camera_y, zoom, aspect)

        self._generation_in_progress = True
        self._worker_thread = threading.Thread(
            target=self._generate_worker,
            args=(gen_bounds, comfort_bounds, gamma),
            daemon=True
        )
        self._worker_thread.start()

    def poll_results(self):
        """
        Check if background generation is complete.
        If so, swap in the new tile data and mark GPU buffers dirty.
        Returns True if new data was swapped in.
        """
        if self._pending_result is None:
            return False

        with self._lock:
            tiles_dict, tile_list, gen_bounds, comfort_bounds, stars, bursts, gamma = self._pending_result
            self._pending_result = None

        self.tiles = tiles_dict
        self.tile_list = tile_list
        self.gen_bounds = gen_bounds
        self.comfort_bounds = comfort_bounds
        self.star_count = stars
        self.starburst_count = bursts
        self.tile_count = len(tile_list)
        self._current_gamma = gamma

        self._pack_gpu_buffers()
        self.gpu_data_dirty = True
        self._generation_in_progress = False

        self.logger.info(
            f"Tile data ready: {self.tile_count} tiles, "
            f"{self.star_count} stars, {self.starburst_count} starbursts"
        )
        return True

    # -------------------------------------------------------------------------
    # Background worker
    # -------------------------------------------------------------------------

    def _generate_worker(self, gen_bounds, comfort_bounds, gamma):
        """Background thread: generate tiles, neighbors, patterns."""
        try:
            t0 = time.perf_counter()

            tiles_dict = self._generate_tiles(gen_bounds, gamma)
            tile_list = list(tiles_dict.values())
            t1 = time.perf_counter()

            self._calculate_neighbors(tile_list)
            t2 = time.perf_counter()

            stars, bursts = self._detect_patterns(tile_list)
            t3 = time.perf_counter()

            self.logger.debug(
                f"Generation: {len(tile_list)} tiles in {(t1-t0)*1000:.1f}ms, "
                f"neighbors {(t2-t1)*1000:.1f}ms, patterns {(t3-t2)*1000:.1f}ms, "
                f"total {(t3-t0)*1000:.1f}ms"
            )

            with self._lock:
                self._pending_result = (tiles_dict, tile_list, gen_bounds, comfort_bounds, stars, bursts, gamma)

        except Exception as e:
            self.logger.error(f"Tile generation failed: {e}", exc_info=True)
            self._generation_in_progress = False

    # -------------------------------------------------------------------------
    # Tile generation (pentagrid math)
    # -------------------------------------------------------------------------

    def _rhombus_vertices(self, gamma, r, s, kr, ks):
        """Compute 4 vertices of a rhombus at grid intersection (r,s,kr,ks)."""
        z0 = 1j * (self.zeta[r] * (ks - gamma[s]) - self.zeta[s] * (kr - gamma[r])) / self.zeta[s - r].imag
        z0 = complex(round(z0.real, 5), round(z0.imag, 5))

        k = [0 - -(complex(z0 / t).real + p) // 1 for t, p in zip(self.zeta, gamma)]

        verts = []
        for kr_off, ks_off in [(kr, ks), (kr + 1, ks), (kr + 1, ks + 1), (kr, ks + 1)]:
            k[r], k[s] = kr_off, ks_off
            vertex = sum(x * t for t, x in zip(self.zeta, k))
            verts.append(complex(round(vertex.real, 5), round(vertex.imag, 5)))
        return verts

    def _generate_tiles(self, gen_bounds, gamma):
        """Generate OverlayTile objects covering the generation zone.

        Coordinate spaces:
        - gen_bounds are in camera/pentagrid space (same as procedural shader's p)
        - Tile vertices from _rhombus_vertices are in ribbon space
        - ribbon = 2.5 * p + shift_offset, so p = (ribbon - shift_offset) / 2.5
        """
        min_x, min_y, max_x, max_y = gen_bounds

        # Compute shift_offset = Σ zeta[k] * gamma[k]
        shift_offset = sum(z * g for z, g in zip(self.zeta, gamma))

        # Estimate grid index range needed to cover the generation zone.
        # Camera space viewport is roughly (max - min). In ribbon space that's 2.5x larger.
        # Tile edge length in ribbon space is ~1 unit, so we need size ≈ 2.5 * viewport_size / 2
        world_w = max_x - min_x
        world_h = max_y - min_y
        size = int(max(world_w, world_h) * 2.5) + 2

        tiles_dict = {}

        for r in range(5):
            for s in range(r + 1, 5):
                for kr in range(-size, size + 1):
                    for ks in range(-size, size + 1):
                        key = (r, s, kr, ks)
                        if key in tiles_dict:
                            continue

                        verts = self._rhombus_vertices(gamma, r, s, kr, ks)

                        # Check if any vertex falls within generation bounds
                        # Convert ribbon-space vertex to camera space: p = (v - shift_offset) / 2.5
                        in_bounds = False
                        for v in verts:
                            v_cam = (v - shift_offset) / 2.5
                            if min_x <= v_cam.real <= max_x and min_y <= v_cam.imag <= max_y:
                                in_bounds = True
                                break

                        if in_bounds:
                            tile = OverlayTile(verts, r, s, kr, ks)
                            tiles_dict[key] = tile

                        if self._shutdown:
                            return tiles_dict

        return tiles_dict

    # -------------------------------------------------------------------------
    # Neighbor calculation (edge hashing)
    # -------------------------------------------------------------------------

    def _calculate_neighbors(self, tile_list):
        """Build neighbor graph using edge hashing. O(N) where N = number of tiles."""
        edge_map = {}  # normalized_edge -> list of tiles

        for tile in tile_list:
            tile.neighbors = []  # reset
            for edge in tile.edges():
                if edge not in edge_map:
                    edge_map[edge] = []
                edge_map[edge].append(tile)

        # Link tiles sharing an edge
        for tiles_on_edge in edge_map.values():
            if len(tiles_on_edge) == 2:
                tiles_on_edge[0].add_neighbor(tiles_on_edge[1])
                tiles_on_edge[1].add_neighbor(tiles_on_edge[0])

    # -------------------------------------------------------------------------
    # Pattern detection with spatial vertex index
    # -------------------------------------------------------------------------

    def _build_vertex_index(self, tile_list, precision=3):
        """
        Build a spatial index: rounded_vertex -> list of tiles containing that vertex.
        This replaces the O(N) scan in find_star/find_starburst with O(1) lookups.
        """
        vertex_to_tiles = {}
        for tile in tile_list:
            for v in tile.vertices:
                rv = complex(round(v.real, precision), round(v.imag, precision))
                if rv not in vertex_to_tiles:
                    vertex_to_tiles[rv] = []
                vertex_to_tiles[rv].append(tile)
        return vertex_to_tiles

    def _is_valid_star_kite(self, tile):
        """A kite is a valid star candidate if it has exactly 2 dart neighbors."""
        if not tile.is_kite:
            return False
        dart_count = sum(1 for n in tile.neighbors if not n.is_kite)
        return dart_count == 2

    def _is_valid_starburst_dart(self, tile):
        """A dart is a valid starburst candidate if it has exactly 2 dart neighbors."""
        if tile.is_kite:
            return False
        dart_count = sum(1 for n in tile.neighbors if not n.is_kite)
        return dart_count == 2

    def _find_common_vertex(self, tiles, precision=3):
        """Find a vertex shared by all given tiles."""
        if not tiles:
            return None
        vertex_count = {}
        for tile in tiles:
            for v in tile.vertices:
                rv = complex(round(v.real, precision), round(v.imag, precision))
                vertex_count[rv] = vertex_count.get(rv, 0) + 1
        for v, count in vertex_count.items():
            if count >= len(tiles):
                return v
        return None

    def _detect_patterns(self, tile_list):
        """
        Detect star and starburst patterns using spatial vertex index.
        Sets pattern_type and blend_factor on each tile.
        Returns (star_count, starburst_count).
        """
        vertex_index = self._build_vertex_index(tile_list)
        pattern_tiles = set()  # tiles already assigned to a pattern
        stars = []
        starbursts = []

        for tile in tile_list:
            if tile in pattern_tiles:
                continue

            # Try star detection (5 kites sharing a vertex)
            if tile.is_kite and self._is_valid_star_kite(tile):
                kite_neighbors = [n for n in tile.neighbors
                                  if n.is_kite and self._is_valid_star_kite(n)
                                  and n not in pattern_tiles]
                for n1 in kite_neighbors:
                    found = False
                    for n2 in kite_neighbors:
                        if n1 is n2:
                            continue
                        common_v = self._find_common_vertex([tile, n1, n2])
                        if common_v is None:
                            continue
                        # Use vertex index for O(1) lookup instead of scanning all tiles
                        candidates = vertex_index.get(common_v, [])
                        star_tiles = [t for t in candidates
                                      if t.is_kite and self._is_valid_star_kite(t)]
                        if len(star_tiles) == 5:
                            stars.append(star_tiles)
                            pattern_tiles.update(star_tiles)
                            found = True
                            break
                    if found:
                        break

            # Try starburst detection (10 darts sharing a vertex)
            elif not tile.is_kite and self._is_valid_starburst_dart(tile):
                dart_neighbors = [n for n in tile.neighbors
                                  if not n.is_kite and self._is_valid_starburst_dart(n)
                                  and n not in pattern_tiles]
                potential = [tile] + dart_neighbors
                if len(potential) >= 3:
                    common_v = self._find_common_vertex(potential)
                    if common_v is not None:
                        candidates = vertex_index.get(common_v, [])
                        burst_tiles = [t for t in candidates
                                       if not t.is_kite and self._is_valid_starburst_dart(t)]
                        if len(burst_tiles) == 10:
                            starbursts.append(burst_tiles)
                            pattern_tiles.update(burst_tiles)

        # Assign pattern data to tiles
        star_set = set()
        for group in stars:
            star_set.update(group)
        burst_set = set()
        for group in starbursts:
            burst_set.update(group)

        for tile in tile_list:
            if tile in star_set:
                tile.pattern_type = 1.0
                tile.blend_factor = 0.3
            elif tile in burst_set:
                tile.pattern_type = 2.0
                tile.blend_factor = 0.7
            else:
                # Neighbor-based blend
                kite_count = sum(1 for n in tile.neighbors if n.is_kite)
                total = len(tile.neighbors)
                tile.blend_factor = 0.5 if total == 0 else kite_count / total
                tile.pattern_type = 0.0

        return len(stars), len(starbursts)

    # -------------------------------------------------------------------------
    # GPU buffer packing
    # -------------------------------------------------------------------------

    def _pack_gpu_buffers(self):
        """
        Pack tile data into numpy arrays for GPU upload.

        gpu_vertices: float32 (N, 4, 2) - four corners per tile in camera/pentagrid space
            Vertices from _rhombus_vertices are in ribbon space.
            Ribbon space rb_p = 2.5*p + shift_offset (for 5 evenly-spaced unit vectors),
            so we convert: p = (rb_p - shift_offset) / 2.5
        gpu_tile_data: float32 (N, 8) - per-tile attributes:
            [0] is_kite (0.0 or 1.0)
            [1] pattern_type (0=normal, 1=star, 2=starburst)
            [2] blend_factor (0.0-1.0)
            [3] selected (0.0 or 1.0)
            [4] hovered (0.0 or 1.0)
            [5] anim_phase (0.0-1.0)
            [6] anim_type (0=none, 1=flip, 2=cascade, 3=ripple)
            [7] tile_id (hash-based random for seeding)
        """
        n = len(self.tile_list)
        if n == 0:
            self.gpu_vertices = np.zeros((0, 4, 2), dtype=np.float32)
            self.gpu_tile_data = np.zeros((0, 8), dtype=np.float32)
            return

        # Compute shift_offset = Σ zeta[k] * gamma[k]
        # This is the constant offset between ribbon space and 2.5*camera_space
        shift_offset = sum(z * g for z, g in zip(self.zeta, self._current_gamma))

        verts = np.zeros((n, 4, 2), dtype=np.float32)
        data = np.zeros((n, 8), dtype=np.float32)

        for i, tile in enumerate(self.tile_list):
            # Convert vertices from ribbon space to camera/pentagrid space.
            # The procedural shader maps camera-space p to ribbon-space rb_p via:
            #   rb_p = Σ grid[k] * (dot(p, grid[k]) + gamma[k])
            #        = 2.5*p + Σ grid[k]*gamma[k]   (for 5 evenly-spaced unit vectors)
            # So: p = (rb_p - shift_offset) / 2.5
            # where shift_offset = Σ zeta[k] * gamma[k]
            for j, v in enumerate(tile.vertices[:4]):
                rb = complex(v.real, v.imag)
                p_cam = (rb - shift_offset) / 2.5
                verts[i, j, 0] = p_cam.real
                verts[i, j, 1] = p_cam.imag

            data[i, 0] = 1.0 if tile.is_kite else 0.0
            data[i, 1] = tile.pattern_type
            data[i, 2] = tile.blend_factor
            data[i, 3] = 1.0 if tile.selected else 0.0
            data[i, 4] = 1.0 if tile.hovered else 0.0
            data[i, 5] = tile.anim_phase
            data[i, 6] = float(tile.anim_type)
            # Stable tile ID from pentagrid indices
            data[i, 7] = float(hash(tile.key) % 10000) / 10000.0

        self.gpu_vertices = verts
        self.gpu_tile_data = data

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
        Uses point-in-quad test against GPU vertex data (in pentagrid space).
        """
        if self.gpu_vertices is None or self.tile_count == 0:
            return -1

        p = np.array([pentagrid_x, pentagrid_y], dtype=np.float32)

        for i in range(self.tile_count):
            v = self.gpu_vertices[i]  # (4, 2)
            # Cross product winding test
            inside = True
            sign = 0
            for j in range(4):
                e = v[(j + 1) % 4] - v[j]
                w = p - v[j]
                cross = e[0] * w[1] - e[1] * w[0]
                if sign == 0:
                    sign = 1 if cross >= 0 else -1
                elif (sign > 0 and cross < 0) or (sign < 0 and cross > 0):
                    inside = False
                    break
            if inside:
                return i

        return -1

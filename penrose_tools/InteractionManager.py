# penrose_tools/InteractionManager.py
"""
Manages tile interaction state: click, hover, animation ticking, and
neighbor-based effect propagation. Decoupled from rendering — works
across all shader effects as a system-level layer.
"""
import cmath
import logging
import math
import time


class InteractionManager:
    """
    Stateful interaction controller for the tile overlay system.
    Owns click/hover logic, animation scheduling, and cascade propagation.
    Delegates GPU data updates to TileDataManager.

    Performance notes:
    - Tile index lookups are O(1) via TileDataManager._tile_index_map
    - Dirty tile indices are tracked for partial GPU uploads (not full re-uploads)
    - Animation list uses index-based removal to avoid O(N) list.remove()
    """

    # Animation type constants (match GPU tile_data layout)
    ANIM_NONE = 0
    ANIM_CASCADE = 2
    ANIM_RIPPLE = 3
    MASK_STAMP = 4
    ANIM_SYMMETRY = 5

    def __init__(self, tile_manager):
        self.logger = logging.getLogger('InteractionManager')
        self.tile_manager = tile_manager

        # Current hover state
        self._hovered_index = -1

        # Active animations: list of dicts with tile_index, anim_type, phase, speed, delay
        self._animations = []

        # Currently selected tiles (toggle on click)
        self._selected_indices = set()

        # Active interaction mode (what happens on click)
        # 0 = select, 1 = ripple, 2 = symmetry
        self.click_mode = 1  # default to ripple

        # Animation speed multiplier
        self.anim_speed = 2.0

        # Cascade propagation depth (how many neighbor rings)
        self.cascade_depth = 20

        # Cascade stagger delay in seconds per ring
        self.cascade_stagger = 0.2

        # Dirty tracking — indices of tiles whose gpu_tile_data changed since last upload
        self._dirty_indices = set()

        # Mask stamp callback — set by ProceduralRenderer to handle mask generation
        # Signature: callback(pentagrid_x, pentagrid_y)
        self._mask_stamp_callback = None

        # Whether a mask stamp is currently active (visible)
        self._mask_stamp_active = False

        # Tile indices at 5-fold symmetric vertices (populated by ProceduralRenderer)
        self._symmetry_tile_indices = set()

        self.logger.info("InteractionManager initialized")

    def set_click_mode(self, mode):
        """Set what happens when a tile is clicked. 0=select, 1=ripple, 2=symmetry."""
        self.click_mode = max(0, min(2, mode))
        mode_names = ['select', 'ripple', 'symmetry']
        self.logger.info(f"Click mode: {mode_names[self.click_mode]}")

    def cycle_click_mode(self):
        """Cycle to the next click mode. Returns the new mode index."""
        self.click_mode = (self.click_mode + 1) % 3
        mode_names = ['select', 'ripple', 'symmetry']
        self.logger.info(f"Click mode: {mode_names[self.click_mode]}")
        return self.click_mode

    def set_mask_stamp_callback(self, callback):
        """Set the callback for mask stamp clicks. callback(pentagrid_x, pentagrid_y)."""
        self._mask_stamp_callback = callback

    # -------------------------------------------------------------------------
    # Dirty tracking for partial GPU uploads
    # -------------------------------------------------------------------------

    def get_dirty_range(self):
        """Return (min_index, count) of dirty tiles for partial GPU upload.
        Clears the dirty set. Returns (0, 0) if nothing changed."""
        if not self._dirty_indices:
            return 0, 0
        lo = min(self._dirty_indices)
        hi = max(self._dirty_indices)
        count = hi - lo + 1
        self._dirty_indices.clear()
        return lo, count

    def _mark_dirty(self, tile_index):
        """Mark a tile index as needing GPU upload."""
        self._dirty_indices.add(tile_index)

    # -------------------------------------------------------------------------
    # Hover
    # -------------------------------------------------------------------------

    def update_hover(self, pentagrid_x, pentagrid_y):
        """Update hover state based on cursor position in pentagrid space.
        Returns True if hover state changed."""
        hit = self.tile_manager.hit_test(pentagrid_x, pentagrid_y)

        if hit == self._hovered_index:
            return False

        # Clear old hover
        if self._hovered_index >= 0 and self._hovered_index < self.tile_manager.tile_count:
            self.tile_manager.update_tile_interaction(self._hovered_index, hovered=False)
            self._mark_dirty(self._hovered_index)

        # Set new hover
        if hit >= 0:
            self.tile_manager.update_tile_interaction(hit, hovered=True)
            self._mark_dirty(hit)

        self._hovered_index = hit
        return True

    def clear_hover(self):
        """Clear hover when cursor leaves window."""
        if self._hovered_index >= 0 and self._hovered_index < self.tile_manager.tile_count:
            self.tile_manager.update_tile_interaction(self._hovered_index, hovered=False)
            self._mark_dirty(self._hovered_index)
            self._hovered_index = -1

    # -------------------------------------------------------------------------
    # Click
    # -------------------------------------------------------------------------

    def handle_click(self, pentagrid_x, pentagrid_y):
        """Handle a click at the given pentagrid-space position."""
        hit = self.tile_manager.hit_test(pentagrid_x, pentagrid_y)
        if hit < 0:
            return

        if self.click_mode == 0:
            self._toggle_select(hit)
        elif self.click_mode == 1:
            self._start_ripple(hit)
        elif self.click_mode == 2:
            self._start_symmetry_scan(hit)

    def _start_mask_stamp(self, pentagrid_x, pentagrid_y):
        """Place a mask stamp at the given pentagrid position."""
        if self._mask_stamp_callback:
            self._mask_stamp_callback(pentagrid_x, pentagrid_y)
            self._mask_stamp_active = True
            self.logger.info(f"Mask stamp at ({pentagrid_x:.2f}, {pentagrid_y:.2f})")

    def _toggle_select(self, tile_index):
        """Toggle selection on a single tile."""
        if tile_index in self._selected_indices:
            self._selected_indices.discard(tile_index)
            self.tile_manager.update_tile_interaction(tile_index, selected=False)
        else:
            self._selected_indices.add(tile_index)
            self.tile_manager.update_tile_interaction(tile_index, selected=True)
        self._mark_dirty(tile_index)

    def _start_cascade(self, center_index):
        """Start a rotational cascade from the clicked tile outward through neighbors."""
        if center_index < 0 or center_index >= self.tile_manager.tile_count:
            return

        # BFS through neighbor graph to build rings
        visited = {center_index}
        current_ring = [center_index]

        # Ring 0: the clicked tile itself
        self._add_animation(center_index, self.ANIM_CASCADE, speed=self.anim_speed, delay=0.0)

        for depth in range(1, self.cascade_depth + 1):
            next_ring = []
            for idx in current_ring:
                tile = self.tile_manager.tile_list[idx]
                for neighbor in tile.neighbors:
                    # O(1) lookup via identity map
                    n_idx = self.tile_manager.get_tile_index(neighbor)
                    if n_idx >= 0 and n_idx not in visited:
                        visited.add(n_idx)
                        next_ring.append(n_idx)

            delay = depth * self.cascade_stagger
            for idx in next_ring:
                self._add_animation(idx, self.ANIM_CASCADE, speed=self.anim_speed, delay=delay)

            current_ring = next_ring
            if not current_ring:
                break

    def _start_ripple(self, center_index):
        """Start a ripple effect from the clicked tile."""
        if center_index < 0 or center_index >= self.tile_manager.tile_count:
            return

        visited = {center_index}
        current_ring = [center_index]

        self._add_animation(center_index, self.ANIM_RIPPLE, speed=self.anim_speed * 0.7, delay=0.0)

        for depth in range(1, self.cascade_depth + 2):
            next_ring = []
            for idx in current_ring:
                tile = self.tile_manager.tile_list[idx]
                for neighbor in tile.neighbors:
                    n_idx = self.tile_manager.get_tile_index(neighbor)
                    if n_idx >= 0 and n_idx not in visited:
                        visited.add(n_idx)
                        next_ring.append(n_idx)

            delay = depth * self.cascade_stagger * 1.5
            for idx in next_ring:
                self._add_animation(idx, self.ANIM_RIPPLE, speed=self.anim_speed * 0.7, delay=delay)

            current_ring = next_ring
            if not current_ring:
                break

    def set_symmetry_tiles(self, indices):
        """Update the set of tile indices at 5-fold symmetric vertices."""
        self._symmetry_tile_indices = set(indices)

    def _start_symmetry_scan(self, center_index):
        """Start a symmetry-revealing ripple that actively analyzes each ring
        for 5-fold rotational symmetry around the origin.

        If the clicked tile is part of a star or starburst pattern,
        the ripple originates from all tiles in that pattern simultaneously.
        As the ripple expands, each ring is tested for 5-fold symmetry by
        sorting tiles into angular sectors and comparing their signatures.
        """
        if center_index < 0 or center_index >= self.tile_manager.tile_count:
            return

        # Check if clicked tile is part of a star/starburst pattern
        origin_tiles = self._expand_pattern_origin(center_index)

        # Compute origin centroid (center of symmetry analysis)
        tile_list = self.tile_manager.tile_list
        origin_centroids = [tile_list[i].centroid for i in origin_tiles]
        origin_center = sum(origin_centroids) / len(origin_centroids)

        visited = set(origin_tiles)
        current_ring = list(origin_tiles)

        # Ring 0: origin tiles always get symmetry glow
        for idx in origin_tiles:
            self._add_animation(idx, self.ANIM_RIPPLE,
                                speed=self.anim_speed * 0.7, delay=0.0)
            self._add_animation(idx, self.ANIM_SYMMETRY,
                                speed=0.15, delay=0.3)

        for depth in range(1, self.cascade_depth + 2):
            next_ring = []
            for idx in current_ring:
                tile = tile_list[idx]
                for neighbor in tile.neighbors:
                    n_idx = self.tile_manager.get_tile_index(neighbor)
                    if n_idx >= 0 and n_idx not in visited:
                        visited.add(n_idx)
                        next_ring.append(n_idx)

            if not next_ring:
                break

            delay = depth * self.cascade_stagger * 1.5

            # Analyze this ring for 5-fold symmetry
            symmetric_indices = self._check_ring_symmetry(
                next_ring, origin_center, tile_list)

            for idx in next_ring:
                self._add_animation(idx, self.ANIM_RIPPLE,
                                    speed=self.anim_speed * 0.7, delay=delay)
                if idx in symmetric_indices:
                    self._add_animation(idx, self.ANIM_SYMMETRY,
                                        speed=0.15, delay=delay + 0.3)

            current_ring = next_ring

    def _check_ring_symmetry(self, ring_indices, center, tile_list):
        """Analyze a ring of tiles for 5-fold rotational symmetry.

        Divides tiles into 5 angular sectors (72° each) around the center.
        If the sectors have matching tile-type signatures (same count of
        kites and darts in each sector), the ring is 5-fold symmetric.

        Returns the set of tile indices that are part of symmetric rings.
        """
        if len(ring_indices) < 5:
            return set()

        # Build sector signatures: for each of 5 sectors, count (kites, darts)
        # Try multiple rotation offsets to find the best alignment
        sector_count = 5
        sector_width = 2.0 * math.pi / sector_count

        # Compute angle and type for each tile in the ring
        tile_angles = []
        for idx in ring_indices:
            tile = tile_list[idx]
            c = tile.centroid
            dx = c.real - center.real
            dy = c.imag - center.imag
            angle = math.atan2(dy, dx)  # -π to π
            if angle < 0:
                angle += 2.0 * math.pi  # normalize to 0..2π
            tile_angles.append((idx, angle, tile.is_kite))

        # Try 36 rotation offsets (every 10°) to find best sector alignment
        best_offset = 0.0
        best_match = False

        for step in range(36):
            offset = step * (math.pi / 18.0)  # 10° increments

            # Build sector signatures
            sectors = [[] for _ in range(sector_count)]
            for idx, angle, is_kite in tile_angles:
                shifted = (angle - offset) % (2.0 * math.pi)
                sector = int(shifted / sector_width)
                if sector >= sector_count:
                    sector = sector_count - 1
                sectors[sector].append(is_kite)

            # Check if all sectors have the same signature
            # Signature = (kite_count, dart_count) sorted for order invariance
            sigs = []
            for s in sectors:
                kites = sum(1 for k in s if k)
                darts = len(s) - kites
                sigs.append((len(s), kites, darts))

            # All sectors must match and be non-empty
            if sigs[0][0] > 0 and all(s == sigs[0] for s in sigs):
                best_match = True
                best_offset = offset
                break

        if best_match:
            return set(ring_indices)
        return set()

    def _expand_pattern_origin(self, center_index):
        """If the tile at center_index is part of a star/starburst pattern,
        return all tile indices in that connected pattern group.
        Otherwise return just {center_index}."""
        tile = self.tile_manager.tile_list[center_index]
        pt = tile.pattern_type
        if pt < 0.5:
            # Normal tile — single origin
            return {center_index}

        # BFS through neighbors with the same pattern_type to find the full group
        group = {center_index}
        frontier = [center_index]
        while frontier:
            next_frontier = []
            for idx in frontier:
                t = self.tile_manager.tile_list[idx]
                for nb in t.neighbors:
                    n_idx = self.tile_manager.get_tile_index(nb)
                    if n_idx >= 0 and n_idx not in group:
                        if nb.pattern_type == pt:
                            group.add(n_idx)
                            next_frontier.append(n_idx)
            frontier = next_frontier
        return group

    # -------------------------------------------------------------------------
    # Animation system
    # -------------------------------------------------------------------------

    def _add_animation(self, tile_index, anim_type, speed=2.0, delay=0.0):
        """Schedule an animation on a tile. Multiple animations can coexist
        on the same tile — the one with the highest visual intensity wins
        the GPU slot each frame."""
        self._animations.append({
            'tile_index': tile_index,
            'anim_type': anim_type,
            'phase': 0.0,
            'speed': speed,
            'delay': delay,
            'start_time': time.monotonic(),
        })

    def update_animations(self, dt):
        """Advance all active animations by dt seconds.
        Multiple animations can exist per tile — the one with the highest
        visual intensity (based on sin(phase * pi)) wins the GPU slot.
        Returns True if any tile data changed."""
        if not self._animations:
            return False

        now = time.monotonic()
        changed = False

        # Phase 1: advance all animations, collect completed indices
        completed = []
        for i in range(len(self._animations) - 1, -1, -1):
            anim = self._animations[i]
            elapsed = now - anim['start_time']
            if elapsed < anim['delay']:
                continue  # Still waiting for stagger delay

            anim['phase'] += anim['speed'] * dt
            if anim['phase'] >= 1.0:
                completed.append(i)

        # Phase 2: remove completed animations, track which tiles lost an animation
        tiles_with_completed = set()
        for i in sorted(completed, reverse=True):
            tiles_with_completed.add(self._animations[i]['tile_index'])
            self._animations.pop(i)

        # Phase 3: for each remaining animation, pick the strongest per tile
        tile_best = {}  # tile_index → (intensity, anim_type, phase)
        for anim in self._animations:
            idx = anim['tile_index']
            phase = anim['phase']
            if phase <= 0.0:
                continue  # hasn't started yet (still in delay)
            phase_clamped = min(phase, 1.0)
            intensity = math.sin(phase_clamped * math.pi)
            prev = tile_best.get(idx)
            if prev is None or intensity > prev[0]:
                tile_best[idx] = (intensity, anim['anim_type'], phase_clamped)

        # Phase 4: write winning animation state to GPU for each affected tile
        for idx, (intensity, anim_type, phase) in tile_best.items():
            self.tile_manager.update_tile_interaction(
                idx, anim_type=anim_type, anim_phase=phase)
            self._mark_dirty(idx)
            changed = True

        # Phase 5: reset tiles that had completions and have no remaining animations
        for idx in tiles_with_completed:
            if idx not in tile_best:
                self.tile_manager.update_tile_interaction(
                    idx, anim_type=self.ANIM_NONE, anim_phase=0.0)
                self._mark_dirty(idx)
                changed = True

        return changed

    def clear_all(self):
        """Reset all interaction state."""
        for idx in list(self._selected_indices):
            self.tile_manager.update_tile_interaction(idx, selected=False)
            self._mark_dirty(idx)
        self._selected_indices.clear()

        for anim in self._animations:
            idx = anim['tile_index']
            self.tile_manager.update_tile_interaction(
                idx, anim_type=self.ANIM_NONE, anim_phase=0.0)
            self._mark_dirty(idx)
        self._animations.clear()

        self._mask_stamp_active = False
        self.clear_hover()

    def on_tiles_regenerated(self):
        """Called when TileDataManager swaps in a new tile set.
        Old tile indices are invalid — clear all state without writing back."""
        self._hovered_index = -1
        self._selected_indices.clear()
        self._animations.clear()
        self._dirty_indices.clear()
        self._symmetry_tile_indices.clear()

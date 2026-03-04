# penrose_tools/InteractionManager.py
"""
Manages tile interaction state: click, hover, animation ticking, and
neighbor-based effect propagation. Decoupled from rendering — works
across all shader effects as a system-level layer.
"""
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
        # 0 = select, 1 = cascade, 2 = ripple, 3 = mask_stamp
        self.click_mode = 1  # default to cascade

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

        self.logger.info("InteractionManager initialized")

    def set_click_mode(self, mode):
        """Set what happens when a tile is clicked. 0=select, 1=cascade, 2=ripple, 3=mask_stamp."""
        self.click_mode = max(0, min(3, mode))
        mode_names = ['select', 'cascade', 'ripple', 'mask_stamp']
        self.logger.info(f"Click mode: {mode_names[self.click_mode]}")

    def cycle_click_mode(self):
        """Cycle to the next click mode. Returns the new mode index."""
        self.click_mode = (self.click_mode + 1) % 4
        mode_names = ['select', 'cascade', 'ripple', 'mask_stamp']
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
        # Mask stamp doesn't need a tile hit — it works on pentagrid position directly
        if self.click_mode == self.MASK_STAMP:
            self._start_mask_stamp(pentagrid_x, pentagrid_y)
            return

        hit = self.tile_manager.hit_test(pentagrid_x, pentagrid_y)
        if hit < 0:
            return

        if self.click_mode == 0:
            self._toggle_select(hit)
        elif self.click_mode == 1:
            self._start_cascade(hit)
        elif self.click_mode == 2:
            self._start_ripple(hit)

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

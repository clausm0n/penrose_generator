# penrose_tools/OverlayTile.py
"""
Lightweight tile data for the overlay rendering system.
Avoids expensive operations from Tile.__init__ (no angle calc, no trig, no temperature).
Designed for fast construction and GPU buffer packing.
"""
import cmath

__slots_list__ = [
    'vertices', 'r', 's', 'kr', 'ks', 'is_kite',
    'neighbors', 'pattern_type', 'blend_factor',
    'selected', 'hovered', 'anim_phase', 'anim_type',
    'color_override',
]


class OverlayTile:
    """
    Minimal tile representation for the overlay system.
    ~5x faster to construct than Tile due to no angle/trig computation.
    """
    __slots__ = __slots_list__

    def __init__(self, vertices, r, s, kr, ks):
        # Core geometry - vertices as list of complex numbers (ribbon space)
        self.vertices = vertices

        # Pentagrid indices - uniquely identify this tile
        self.r = r
        self.s = s
        self.kr = kr
        self.ks = ks

        # Tile type - determined purely from pentagrid indices (no trig needed)
        diff = s - r
        self.is_kite = (diff == 1 or diff == 4)  # diff == PN - 1

        # Neighbor graph (populated by TileDataManager)
        self.neighbors = []

        # Pattern detection results (populated by TileDataManager)
        self.pattern_type = 0.0   # 0=normal, 1=star, 2=starburst
        self.blend_factor = 0.5   # neighbor-derived blend ratio

        # Interaction state
        self.selected = False
        self.hovered = False
        self.anim_phase = 0.0     # 0.0-1.0 animation progress
        self.anim_type = 0        # 0=none, 1=flip, 2=cascade, 3=ripple

        # Color override (None = use default shader coloring)
        self.color_override = None

    @property
    def key(self):
        """Unique key for this tile based on pentagrid indices."""
        return (self.r, self.s, self.kr, self.ks)

    @property
    def centroid(self):
        """Centroid in ribbon space."""
        return sum(self.vertices) / len(self.vertices)

    @property
    def scaled_centroid(self):
        """Centroid scaled by 0.1 to match shader's tileCentroid."""
        return self.centroid * 0.1

    def add_neighbor(self, other):
        """Add a neighbor if not already present."""
        if other not in self.neighbors:
            self.neighbors.append(other)

    def normalized_edge(self, v1, v2):
        """Create a normalized edge key for neighbor detection."""
        rv1 = complex(round(v1.real, 8), round(v1.imag, 8))
        rv2 = complex(round(v2.real, 8), round(v2.imag, 8))
        return (rv1, rv2) if (rv1.real, rv1.imag) < (rv2.real, rv2.imag) else (rv2, rv1)

    def edges(self):
        """Generate normalized edges for neighbor matching."""
        n = len(self.vertices)
        return [self.normalized_edge(self.vertices[i], self.vertices[(i + 1) % n]) for i in range(n)]

    def __hash__(self):
        return hash(self.key)

    def __eq__(self, other):
        if not isinstance(other, OverlayTile):
            return False
        return self.key == other.key

    def __repr__(self):
        return f"OverlayTile(r={self.r}, s={self.s}, kr={self.kr}, ks={self.ks}, kite={self.is_kite})"


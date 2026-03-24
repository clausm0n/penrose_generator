import cmath
import configparser
from penrose_tools.Tile import Tile

class Operations:


    def __init__(self):
        # Fifth roots of unity.
        self.zeta = [cmath.exp(2j * cmath.pi * i / 5) for i in range(5)]
        self.config = configparser.ConfigParser()

    def write_config_file(self, zoom, gamma, color1, color2, vertex_offset=0.00009):
        """Write complete configuration to file."""
        self.filename = 'config.ini'
        self.config['Settings'] = {
            'zoom': str(zoom),
            'gamma': ','.join(map(str, gamma)),
            'color1': f"({','.join(map(str, color1))})",
            'color2': f"({','.join(map(str, color2))})",
            'vertex_offset': f"{float(vertex_offset):.6f}"
        }
        with open(self.filename, 'w') as configfile:
            self.config.write(configfile)

    def read_config_file(self, config_path):
        """Read and parse the configuration file."""
        self.config.read(config_path)
        settings = {
            'zoom': float(self.config.get('Settings', 'zoom', fallback='1.0')),
            'gamma': [float(x.strip()) for x in self.config.get('Settings', 'gamma').split(',')],
            'color1': self.parse_color(self.config.get('Settings', 'color1')),
            'color2': self.parse_color(self.config.get('Settings', 'color2'))
        }
        
        # Handle vertex_offset with proper parsing
        try:
            settings['vertex_offset'] = float(self.config.get('Settings', 'vertex_offset'))
        except (configparser.NoOptionError, ValueError):
            settings['vertex_offset'] = 0.00009  # Default value if not present or invalid
        
        return settings

    def parse_color(self, color_string):
        """Parse color string from config file."""
        # Remove parentheses and split by comma
        color_values = color_string.strip('()').split(',')
        return [int(x.strip()) for x in color_values]

    def update_config_file(self, config_path, **kwargs):
        """Update the configuration file with new values."""
        # Ensure the configparser instance is set to the correct file
        self.config.read(config_path)
        
        if 'Settings' not in self.config:
            self.config['Settings'] = {}
        
        for key, value in kwargs.items():
            if key == 'vertex_offset':
                # Format vertex_offset with fixed decimal places
                self.config.set('Settings', key, f"{float(value):.6f}")
            elif isinstance(value, list):
                if key in ['color1', 'color2']:
                    # Format color lists as tuples
                    self.config.set('Settings', key, f"({', '.join(str(v) for v in value)})")
                else:
                    # For other lists (like gamma), join with commas
                    self.config.set('Settings', key, ', '.join(str(v) for v in value))
            else:
                self.config.set('Settings', key, str(value))
        
        with open(config_path, 'w') as configfile:
            self.config.write(configfile)


    def spatial_hash(self,tile, grid_size):
        """Hash a tile into one or more grid cells."""
        min_x = min(vertex.real for vertex in tile.vertices)
        max_x = max(vertex.real for vertex in tile.vertices)
        min_y = min(vertex.imag for vertex in tile.vertices)
        max_y = max(vertex.imag for vertex in tile.vertices)
        #print(f"Min_x: {min_x}, Max_x: {max_x}, Min_y: {min_y}, Max_y: {max_y}")  # Debug information
        return {(int((x - min_x) / grid_size), int((y - min_y) / grid_size)) for x in [min_x, max_x] for y in [min_y, max_y]}

    def calculate_neighbors(self, tiles, grid_size=100):
        grid = {}
        edge_map = {}  # Map edges to tiles

        # Hash tiles into grid cells and record edges
        for tile in tiles:
            cells = self.spatial_hash(tile, grid_size)
            for cell in cells:
                if cell not in grid:
                    grid[cell] = []
                grid[cell].append(tile)
            
            # Record edges with more precise vertex comparison
            for i in range(len(tile.vertices)):
                v1 = tile.vertices[i]
                v2 = tile.vertices[(i + 1) % len(tile.vertices)]
                
                # Create a normalized edge key with higher precision
                edge = (
                    complex(round(v1.real, 8), round(v1.imag, 8)),
                    complex(round(v2.real, 8), round(v2.imag, 8))
                )
                edge = tuple(sorted([edge[0], edge[1]], key=lambda x: (x.real, x.imag)))
                
                if edge not in edge_map:
                    edge_map[edge] = set()
                edge_map[edge].add(tile)

        # Filter out non-shared edges
        shared_edges = {edge: tiles for edge, tiles in edge_map.items() if len(tiles) == 2}
        
        # Clear existing neighbors
        for tile in tiles:
            tile.neighbors = []

        # Only connect tiles that actually share an edge
        for tiles_sharing_edge in shared_edges.values():
            tiles_list = list(tiles_sharing_edge)
            if len(tiles_list) == 2:
                tiles_list[0].add_neighbor(tiles_list[1])
                tiles_list[1].add_neighbor(tiles_list[0])

        return shared_edges

    def rhombus_at_intersection(self, gamma, r, s, kr, ks):
        # Intersection point, higher precision
        z0 = 1j * (self.zeta[r]*(ks-gamma[s]) - self.zeta[s]*(kr-gamma[r])) / (self.zeta[s-r].imag)
        z0 = complex(round(z0.real, 5), round(z0.imag, 5))
        
        # Compute k-values
        k = [0--(complex(z0/t).real + p)//1 for t, p in zip(self.zeta, gamma)]
        
        for k[r], k[s] in [(kr, ks), (kr+1, ks), (kr+1, ks+1), (kr, ks+1)]:
            vertex = sum(x*t for t, x in zip(self.zeta, k))
            yield complex(round(vertex.real, 5), round(vertex.imag, 5))


    def tiling(self, gamma, width, height, scale, camera_offset=None):
        """
        Generate Penrose tiling.

        Args:
            gamma: Penrose tiling parameter
            width: Screen width in pixels
            height: Screen height in pixels
            scale: Scale factor (higher = fewer tiles)
            camera_offset: Optional complex number for camera offset in world space
        """
        size = max(width, height) // (scale * 3)
        tiles = []
        center = complex(width // 2, height // 2)

        # If camera offset is provided, adjust the center point
        # camera_offset is in world space, need to convert to screen space
        if camera_offset is not None:
            # Camera offset is in world space (ribbon space scaled by 0.1)
            # Convert to screen space by multiplying by scale
            center = center - complex(camera_offset.real * scale * 10, camera_offset.imag * scale * 10)

        for r in range(5):
            for s in range(r+1, 5):
                for kr in range(-size, size+1):
                    for ks in range(-size, size+1):
                        vertices = list(self.rhombus_at_intersection(gamma, r, s, kr, ks))
                        screen_vertices = self.to_canvas(vertices, scale, center)

                        # Check if any vertex is within the screen bounds
                        if any(0 <= x <= width and 0 <= y <= height for x, y in screen_vertices):
                            color = (0, 255, 255) if (r-s)**2 % 5 == 1 else (0, 255, 0)
                            tile = Tile(vertices, color)
                            # Store pentagrid parameters for matching with procedural shader
                            tile.r = r
                            tile.s = s
                            tile.kr = kr
                            tile.ks = ks
                            tiles.append(tile)

        return tiles

    def to_canvas(self, vertices, scale, center):
        result = []
        for z in vertices:
            w = center + scale * z
            result.append((w.real, w.imag))
        return result

    def find_common_vertex(self, tiles, precision=3):
        """Find a common vertex among a group of tiles with given precision."""
        if not tiles:
            return None
        
        # Collect all vertices from all tiles with specified precision
        all_vertices = [self.clamp_vertices(tile.vertices, precision) for tile in tiles]
        vertex_count = {}
        for vertices in all_vertices:
            for vertex in vertices:
                if vertex in vertex_count:
                    vertex_count[vertex] += 1
                else:
                    vertex_count[vertex] = 1

        # Check for vertices that appear in all tile sets
        for vertex, count in vertex_count.items():
            if count >= len(tiles):  # Vertex must be common to all tiles
                return vertex
        return None
    
    def clamp_vertices(self, vertices, precision=1):
        """Clamp vertices to a specified precision."""
        return [complex(round(v.real, precision), round(v.imag, precision)) for v in vertices]
    
    def find_star(self, tile, tiles):
        """Find if the tile is part of a star (5 kites with a common vertex)."""
        kite_neighbors = [neighbor for neighbor in tile.neighbors if neighbor.is_kite and self.is_valid_star_kite(neighbor)]
        for n1 in kite_neighbors:
            for n2 in kite_neighbors:
                if n1 != n2:
                    possible_star = [tile, n1, n2]
                    common_vertex = self.find_common_vertex(possible_star)
                    if common_vertex:
                        extended_star = [t for t in tiles if any(cmath.isclose(v, common_vertex, abs_tol=1e-3) for v in t.vertices) and t.is_kite and self.is_valid_star_kite(t)]
                        if len(extended_star) == 5:
                            return extended_star
        return []

    def find_starburst(self, tile, tiles):
        """Find if the tile is part of a starburst (10 darts with a common vertex)."""
        dart_neighbors = [neighbor for neighbor in tile.neighbors if not neighbor.is_kite and self.is_valid_starburst_dart(neighbor)]
        potential_starburst = [tile] + dart_neighbors
        if len(potential_starburst) >= 3:
            common_vertex = self.find_common_vertex(potential_starburst)
            if common_vertex:
                extended_starburst = [t for t in tiles if any(cmath.isclose(v, common_vertex, abs_tol=1e-3) for v in t.vertices) and not t.is_kite and self.is_valid_starburst_dart(t)]
                if len(extended_starburst) == 10:
                    return extended_starburst
        return []
    
    def count_kite_and_dart_neighbors(self, tile):
        """Count the number of kite and dart neighbors."""
        kite_count = sum(1 for neighbor in tile.neighbors if neighbor.is_kite)
        dart_count = len(tile.neighbors) - kite_count  # Assuming all non-kite are darts
        return kite_count, dart_count

    def is_valid_star_kite(self,tile):
        """ Check if a kite has exactly two darts as neighbors. """
        dart_neighbors = [neighbor for neighbor in tile.neighbors if not neighbor.is_kite]
        return len(dart_neighbors) == 2

    def is_valid_starburst_dart(self,tile):
        """ Check if a dart has exactly two darts as neighbors. """
        dart_neighbors = [neighbor for neighbor in tile.neighbors if not neighbor.is_kite]
        return len(dart_neighbors) == 2
    

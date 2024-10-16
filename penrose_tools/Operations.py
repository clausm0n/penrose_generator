import math
import numpy as np
import time
import functools
from collections import OrderedDict, deque
from itertools import combinations
import random
import cmath
import os
import configparser
from penrose_tools.Tile import Tile

class Operations:
    def __init__(self):
        # Fifth roots of unity.
        self.zeta = [cmath.exp(2j * cmath.pi * i / 5) for i in range(5)]
        self.config = configparser.ConfigParser()

    def write_config_file(self,scale, size, gamma, color1, color2):
            # Write complete configuration to file
            self.filename = 'config.ini'
            self.config['Settings'] = {
                'scale': str(scale),
                'size': str(size),
                'gamma': ','.join(map(str, gamma)),
                'color1': ','.join(map(str, color1)),
                'color2': ','.join(map(str, color2))
            }
            with open(self.filename, 'w') as configfile:
                self.config.write(configfile)

    def read_config_file(self, config_path):
            self.config.read(config_path)
            settings = {
                'scale': self.config.getint('Settings', 'scale'),
                'size': self.config.getint('Settings', 'size'),
                'gamma': [float(x.strip()) for x in self.config.get('Settings', 'gamma').split(',')],
                'color1': [int(x.strip()) for x in self.config.get('Settings', 'color1').split(',')],
                'color2': [int(x.strip()) for x in self.config.get('Settings', 'color2').split(',')]
            }
            return settings

    def update_config_file(self, config_path, **kwargs):
        # Ensure the configparser instance is set to the correct file
        self.config.read(config_path)
        for key, value in kwargs.items():
            if isinstance(value, list):
                # Sanitize list input by filtering out empty strings and joining correctly
                cleaned_value = ', '.join(str(v).strip() for v in value if str(v).strip())
                self.config.set('Settings', key, cleaned_value)
            else:
                self.config.set('Settings', key, str(value))
        with open(config_path, 'w') as configfile:
            self.config.write(configfile)


    def calculate_centroid(self,vertices):
        """ Calculate the centroid from a list of vertices. """
        x_coords = [v.real for v in vertices]
        y_coords = [v.imag for v in vertices]
        centroid_x = sum(x_coords) / len(vertices)
        centroid_y = sum(y_coords) / len(vertices)
        return complex(centroid_x, centroid_y)  # Ensure returning a single complex number


    def spatial_hash(self,tile, grid_size):
        """Hash a tile into one or more grid cells."""
        min_x = min(vertex.real for vertex in tile.vertices)
        max_x = max(vertex.real for vertex in tile.vertices)
        min_y = min(vertex.imag for vertex in tile.vertices)
        max_y = max(vertex.imag for vertex in tile.vertices)
        #print(f"Min_x: {min_x}, Max_x: {max_x}, Min_y: {min_y}, Max_y: {max_y}")  # Debug information
        return {(int((x - min_x) / grid_size), int((y - min_y) / grid_size)) for x in [min_x, max_x] for y in [min_y, max_y]}

    def point_in_polygon(self,point, polygon):
        """Check if the point is inside the polygon using the ray-casting algorithm."""
        x, y = point
        n = len(polygon)
        inside = False
        p1x, p1y = polygon[0]
        for i in range(n + 1):
            p2x, p2y = polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        return inside

    def calculate_neighbors(self,tiles, grid_size=100):
        grid = {}
        edge_map = {}  # Use a dictionary to map edges to tiles

        # Hash tiles into grid cells and record edges
        for tile in tiles:
            cells = self.spatial_hash(tile, grid_size)
            for cell in cells:
                if cell not in grid:
                    grid[cell] = []
                grid[cell].append(tile)
            for edge in tile.edges():
                if edge not in edge_map:
                    edge_map[edge] = []
                edge_map[edge].append(tile)

        # Find neighbors via shared edges
        for edge, tiles_sharing_edge in edge_map.items():
            for i, tile_a in enumerate(tiles_sharing_edge):
                for tile_b in tiles_sharing_edge[i+1:]:
                    tile_a.add_neighbor(tile_b)
                    tile_b.add_neighbor(tile_a)

        print(f"Tiles processed: {len(tiles)}, Edge pairs registered: {len(edge_map)}")

    def find_connected_components(self,tiles):
        # Using a dictionary to map tiles to component IDs
        visited = {}
        component_id = 0
        components = {}

        def dfs(tile, comp_id):
            stack = [tile]
            while stack:
                current = stack.pop()
                if current not in visited:
                    visited[current] = comp_id
                    if comp_id not in components:
                        components[comp_id] = []
                    components[comp_id].append(current)
                    for neighbor in current.neighbors:
                        if neighbor not in visited:
                            stack.append(neighbor)

        # Run DFS from each unvisited tile to find all components
        for tile in tiles:
            if tile not in visited:
                dfs(tile, component_id)
                component_id += 1

        return components

    def remove_small_components(self,tiles, min_size=5):
        components = self.find_connected_components(tiles)
        # Keep only components that have a size >= min_size
        valid_tiles = [tile for comp in components.values() if len(comp) >= min_size for tile in comp]
        return valid_tiles

    def rhombus_at_intersection(self,gamma, r, s, kr, ks):
        z0 = 1j*(self.zeta[r]*(ks-gamma[s]) - self.zeta[s]*(kr-gamma[r])) / (self.zeta[s-r].imag)
        k = [0--((z0/t).real+p)//1 for t, p in zip(self.zeta, gamma)]
        for k[r], k[s] in [(kr, ks), (kr+1, ks), (kr+1, ks+1), (kr, ks+1)]:
            yield sum(x*t for t, x in zip(self.zeta, k))

    def tiling(self, gamma, width, height, scale):
        size = max(width, height) // scale
        tiles = []
        center = complex(width // 2, height // 2)
        
        for r in range(5):
            for s in range(r+1, 5):
                for kr in range(-size, size+1):
                    for ks in range(-size, size+1):
                        vertices = list(self.rhombus_at_intersection(gamma, r, s, kr, ks))
                        screen_vertices = self.to_canvas(vertices, scale, center)
                        
                        # Check if any vertex is within the screen bounds
                        if any(0 <= x <= width and 0 <= y <= height for x, y in screen_vertices):
                            color = (0, 255, 255) if (r-s)**2 % 5 == 1 else (0, 255, 0)
                            tiles.append(Tile(vertices, color))
        
        return tiles

    def is_tile_visible(self, tile, width, height, scale, center):
        screen_vertices = self.to_canvas(tile.vertices, scale, center)
        return any(0 <= x <= width and 0 <= y <= height for x, y in screen_vertices)

    def to_canvas(self,vertices, scale, center, shrink_factor=5):
        centroid = sum(vertices) / len(vertices)
        result = []
        for z in vertices:
            w = center + scale * (z - shrink_factor * (z - centroid) / scale)
            result.append((w.real, w.imag))
        return result

    def clamp_color(self,color):
        """Ensure all color values are within the legal RGB range."""
        return tuple(max(0, min(255, int(c))) for c in color)

    def kernel_function(self,distance, radius):
        # Simple exponential decay kernel
        return np.exp(-distance**2 / (2 * radius**2))

    def calculate_distance(self,tile1, tile2):
        # Calculate Euclidean distance between the centroids of two tiles
        centroid1 = self.calculate_centroid(tile1.vertices)
        centroid2 = self.calculate_centroid(tile2.vertices)
        return abs(centroid1 - centroid2)
    
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
    
    def find_common_vertex_count(self, tile, precision=2):
        """Find the highest count of common vertices among a given set of tiles with specified precision."""
        # Adjust vertex precision
        precise_vertices = [tile.clamp_vertices([v], precision) for v in tile.vertices]
        tile_vertex_set = {v[0] for v in precise_vertices}

        max_common_count = 0
        for neighbor in tile.neighbors:
            # Use the same precision for neighbor vertices
            neighbor_precise_vertices = [neighbor.clamp_vertices([v], precision) for v in neighbor.vertices]
            neighbor_vertex_set = {v[0] for v in neighbor_precise_vertices}

            common_vertices = tile_vertex_set & neighbor_vertex_set
            common_count = len(common_vertices)
            if common_count > max_common_count:
                max_common_count = common_count

        return max_common_count
    
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
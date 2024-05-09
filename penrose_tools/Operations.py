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

class Operations:
    def __init__(self):
        # Fifth roots of unity.
        self.zeta = [cmath.exp(2j * cmath.pi * i / 5) for i in range(5)]

    # def write_config_file(self,filename, height, width, scale, size):
    #     config = configparser.ConfigParser()
    #     config['Settings'] = {
    #         'height': str(height),
    #         'width': str(width),
    #         'size': str(size),
    #         'scale': str(scale)
    #     }
    #     with open(filename, 'w') as configfile:
    #         config.write(configfile)

    def read_config_file(self, filename):
        config = configparser.ConfigParser()
        config.read(filename)
        settings = config['Settings']
        return {
            'height': config.getint('Settings', 'height'),
            'width': config.getint('Settings', 'width'),
            'size': config.getint('Settings', 'size'),
            'scale': config.getfloat('Settings', 'scale'),
            'gamma': [float(g) for g in config.get('Settings', 'gamma').split(',')],
            'color1': [int(c) for c in config.get('Settings', 'color1').split(',')],
            'color2': [int(c) for c in config.get('Settings', 'color2').split(',')]
        }

    def update_config_file(self, filename, height=None, width=None, scale=None, size=None, gamma=None, color1=None, color2=None):
        config = configparser.ConfigParser()
        config.read(filename)
        
        if height is not None:
            config['Settings']['height'] = str(height)
        if width is not None:
            config['Settings']['width'] = str(width)
        if scale is not None:
            config['Settings']['scale'] = str(scale)
        if size is not None:
            config['Settings']['size'] = str(size)
        if gamma is not None:
            config['Settings']['gamma'] = ', '.join(map(str, gamma))
        if color1 is not None:
            config['Settings']['color1'] = ', '.join(map(str, color1))
        if color2 is not None:
            config['Settings']['color2'] = ', '.join(map(str, color2))

        with open(filename, 'w') as configfile:
            config.write(configfile)

    def calculate_centroid(self,vertices):
        """ Calculate the centroid from a list of vertices. """
        x_coords = [v.real for v in vertices]
        y_coords = [v.imag for v in vertices]
        centroid_x = sum(x_coords) / len(vertices)
        centroid_y = sum(y_coords) / len(vertices)
        return complex(centroid_x, centroid_y)  # Ensure returning a single complex number


    def is_valid_star_kite(self,tile):
        """ Check if a kite has exactly two darts as neighbors. """
        dart_neighbors = [neighbor for neighbor in tile.neighbors if not neighbor.is_kite]
        return len(dart_neighbors) == 2

    def is_valid_starburst_dart(self,tile):
        """ Check if a dart has exactly two darts as neighbors. """
        dart_neighbors = [neighbor for neighbor in tile.neighbors if not neighbor.is_kite]
        return len(dart_neighbors) == 2

    def find_common_vertex(self,kites):
        """ Find a common vertex among a given set of kites. """
        vertex_sets = [set(kite.vertices) for kite in kites]
        common_vertices = set.intersection(*vertex_sets)
        return common_vertices

    def update_star_patterns(self,tiles):
        """ Check each tile to see if it's part of a star pattern. """
        stars_colored = 0
        for tile in tiles:
            if tile.is_kite and self.is_valid_star_kite(tile):
                # Check combinations of two neighbors to find a star
                kite_neighbors = [neighbor for neighbor in tile.neighbors if neighbor.is_kite and self.is_valid_star_kite(neighbor)]
                if len(kite_neighbors) >= 2:
                    for n1 in kite_neighbors:
                        for n2 in kite_neighbors:
                            if n1 is not n2:
                                # Check if these three kites share a common vertex
                                possible_star = [tile, n1, n2]
                                common_vertex = self.find_common_vertex(possible_star)
                                if common_vertex:
                                    # Check for two more kites sharing the same vertex
                                    extended_star = [t for t in tiles if set(t.vertices) & common_vertex and t.is_kite and self.is_valid_star_kite(t)]
                                    if len(extended_star) == 5:
                                        star_color = (255, 215, 0)  # Gold color for star pattern
                                        for star_tile in extended_star:
                                            star_tile.update_color(star_color)
                                        stars_colored += 1
                                        break  # Found a valid star, break out of loops
        return stars_colored


    def update_starburst_patterns(self,tiles):
        """ Check each dart to see if it's part of a starburst pattern. """
        starbursts_colored = 0
        for tile in tiles:
            if not tile.is_kite and self.is_valid_starburst_dart(tile):
                # Ensure the potential starburst darts all share a common vertex
                dart_neighbors = [neighbor for neighbor in tile.neighbors if not neighbor.is_kite and self.is_valid_starburst_dart(neighbor)]
                potential_starburst = [tile] + dart_neighbors
                if len(potential_starburst) >= 3:  # Start checking when there are at least 3 darts
                    common_vertex = self.find_common_vertex(potential_starburst)
                    if common_vertex:
                        # Extend to find all darts sharing this vertex
                        extended_starburst = [t for t in tiles if set(t.vertices) & common_vertex and not t.is_kite and self.is_valid_starburst_dart(t)]
                        if len(extended_starburst) == 10:
                            starburst_color = (255, 165, 0)  # Orange color for starburst pattern
                            for starburst_tile in extended_starburst:
                                starburst_tile.update_color(starburst_color)
                            starbursts_colored += 1
                            break  # Found a valid starburst, break out of loops
        return starbursts_colored

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

    def tiling(self,gamma, size):
        for r in range(5):
            for s in range(r+1, 5):
                for kr in range(-size, size+1):
                    for ks in range(-size, size+1):
                        color = (0, 255, 255) if (r-s)**2 % 5 == 1 else (0, 255, 0)
                        yield list(self.rhombus_at_intersection(gamma, r, s, kr, ks)), color

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
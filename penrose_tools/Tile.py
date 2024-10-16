#Tile.py

import cmath  # For complex number operations
import random

class Tile:
    def __init__(self, vertices, color=(255, 255, 255)):
        self.vertices = self.clamp_vertices(vertices)
        self.neighbors = []
        self.color = self.clamp_color(color)
        self.original_color = self.color
        self.current_temperature = random.uniform(20, 30)
        self.target_temperature = self.current_temperature
        self.highlighted = False
        self.angles = self.calculate_angles()
        self.is_kite = self.is_kite()
        #invert color for highlinghted tiles
        self.highlighted_color = self.clamp_color(tuple(255 - c for c in self.color))

    def __hash__(self):
        # Hash based on a tuple of vertices and color
        return hash((tuple(self.vertices), self.color))
    
    def __eq__(self, other):
        if not isinstance(other, Tile):
            return False
        return self.vertices == other.vertices and self.color == other.color

    def clamp_color(self, color):
        """Ensure all color values are within the legal RGB range."""
        return tuple(max(0, min(255, int(c))) for c in color)
    
    def clamp_vertices(self, vertices, precision=3):
        """Clamp vertices to a specified precision."""
        return [complex(round(v.real, precision), round(v.imag, precision)) for v in vertices]
    
    def calculate_angles(self):
        """Calculate angles at each vertex of the tile using the correct phase calculation."""
        angles = []
        num_vertices = len(self.vertices)
        for i in range(num_vertices):
            a, b, c = self.vertices[i - 1], self.vertices[i], self.vertices[(i + 1) % num_vertices]
            # Calculate vectors from the current vertex to the previous and the next vertices
            ba = a - b
            bc = c - b
            # Calculate angle between vectors ba and bc using the dot product method
            angle_cos = (ba.real * bc.real + ba.imag * bc.imag) / (cmath.sqrt(ba.real**2 + ba.imag**2) * cmath.sqrt(bc.real**2 + bc.imag**2))
            angle = cmath.acos(angle_cos).real  # Get the real part of the angle in radians
            angles.append(angle)
        return angles

    def is_kite(self):
        """Determine if the tile is a kite based on its angles."""
        # Assuming specific angle criteria to differentiate kites and darts
        return all(angle < (2 * cmath.pi / 3) for angle in self.angles)  # Placeholder condition

    def normalized_edge(self,vertex1, vertex2):
        """Sort vertices based on their real parts first, and then imaginary parts if real parts are equal."""
        return (vertex1, vertex2) if (vertex1.real, vertex1.imag) < (vertex2.real, vertex2.imag) else (vertex2, vertex1)
    
    def edges(self):
        """ Generate normalized edges for better comparison efficiency. """
        n_vertices = [self.normalized_edge(self.vertices[i], self.vertices[(i + 1) % len(self.vertices)]) for i in range(len(self.vertices))]
        return n_vertices

    def add_neighbor(self, neighbor_tile):
        """ Add a neighboring tile to the neighbors list if it's not already included. """
        if neighbor_tile not in self.neighbors:
            self.neighbors.append(neighbor_tile)
    


    def update_color(self, new_color):
        """Update the color of the tile, clamping values to ensure validity."""
        self.color = self.clamp_color(new_color)
    
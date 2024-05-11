import pygame  # type: ignore

class Slider:
    def __init__(self, x, y, w, h, min_val, max_val, initial_val, label, step=0.01):
        self.rect = pygame.Rect(x, y, w, h)
        self.min_val = min_val
        self.max_val = max_val
        self.val = initial_val
        self.active = False
        self.label = label
        self.step = step
        self.handle_rect = pygame.Rect(x + (initial_val - min_val) / (max_val - min_val) * w - 5, y - 2, 10, h + 4)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.handle_rect.collidepoint(event.pos):
                self.active = True
        elif event.type == pygame.MOUSEBUTTONUP:
            self.active = False
        elif event.type == pygame.MOUSEMOTION and self.active:
            self.handle_rect.x = max(self.rect.x, min(event.pos[0], self.rect.x + self.rect.width - self.handle_rect.width))
            # Calculate value snapping to the nearest step
            new_val = (self.handle_rect.x - self.rect.x) / self.rect.width * (self.max_val - self.min_val) + self.min_val
            self.val = round((new_val - self.min_val) / self.step) * self.step + self.min_val

    def draw(self, surface):
        pygame.draw.rect(surface, (100, 100, 100), self.rect)
        pygame.draw.rect(surface, (200, 200, 200), self.handle_rect)
        font = pygame.font.Font(None, 24)
        label_surface = font.render(f'{self.label}: {self.val:.2f}', True, (255, 255, 255))
        surface.blit(label_surface, (self.rect.x + self.rect.width + 10, self.rect.y))

    def get_value(self):
        return self.val

import pygame
from classes import *
from configs import *
from functions import _distance
import sys

class Renderer:
    def __init__(self, system):
        pygame.init()
        self.system = system
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("AMR Fleet Simulation")
        self.font = pygame.font.SysFont("Arial", LABEL_SIZE)
        self.clock = pygame.time.Clock()
        self.amr_png = pygame.image.load("assets/magnus.png")
        self.amr_png = pygame.transform.scale_by(self.amr_png, AMR_SCALE)
        self.reset_png = pygame.image.load("assets/reset.png")
        self.reset_png = pygame.transform.scale_by(self.reset_png, 0.1)
        self.mouse_pos = Position()
        self.pause_pos = Position(PAUSE_BUTTON_CENTER[0], PAUSE_BUTTON_CENTER[1])
        self.reset_pos = Position(RESET_BUTTON_CENTER[0], RESET_BUTTON_CENTER[1])
        
    def draw_entity(self, entity, color, label):
        if not isinstance(entity, Station) and not isinstance(entity, AMR) and not isinstance(entity, Parking):
            raise Exception(f"Unexpected entity type: {type(entity)}")
        x, y = int(entity.position.x - entity.width // 2), int(entity.position.y - entity.height // 2)
        # Draw main rectangle
        text_surface = self.font.render(label, True, TEXT_COLOR)
        if isinstance(entity, Station) or isinstance(entity, Parking):
            pygame.draw.rect(self.screen, color, (x, y, entity.width, entity.height), width=entity.margin)
            self.screen.blit(text_surface, (x + entity.width // 2 - text_surface.get_width() // 2, y - (entity.height // 2)+ LABEL_SIZE + 13))
        elif isinstance(entity, AMR):
            amr_rect = self.amr_png.get_rect(center=(x + entity.width // 2, y + entity.height // 2))
            self.screen.blit(self.amr_png, amr_rect)
            self.screen.blit(text_surface, (x + entity.width // 2 - text_surface.get_width() // 2, y - entity.height // 2 + LABEL_SIZE + 11))

        if isinstance(entity, Parking):
            return
        # Draw slots above the rectangle
        slot_x_start = x + (entity.width - (SLOT_SIZE * 4 + SLOT_MARGIN * 3)) // 2
        slot_y = y - SLOT_SIZE - 5
        for i, (slot_status) in enumerate(entity.slots.values()):
            obj_id = slot_status["object_id"]
            slot_x = slot_x_start + i * (SLOT_SIZE + SLOT_MARGIN)
            color = SLOT_COLOR_EMPTY if obj_id is None else SLOT_COLOR_OCCUPIED
            pygame.draw.rect(self.screen, color, (slot_x, slot_y, SLOT_SIZE, SLOT_SIZE))
            if obj_id:
                obj_text = self.font.render(obj_id[-2:], True, TEXT_COLOR)
                self.screen.blit(obj_text, (slot_x + SLOT_SIZE // 2 - obj_text.get_width() // 2, slot_y + SLOT_SIZE // 2 - 6))

    def draw_pause_button(self):
        button_color = BUTTON_BG_ACTIVE if _distance(self.mouse_pos, self.pause_pos) <= BUTTON_RADIUS else BUTTON_BG
        pygame.draw.circle(self.screen, button_color, PAUSE_BUTTON_CENTER, BUTTON_RADIUS)
        if self.system.paused:
            # Draw play icon (▶)
            points = [
                (PAUSE_BUTTON_CENTER[0] - 4, PAUSE_BUTTON_CENTER[1] - 6),
                (PAUSE_BUTTON_CENTER[0] - 4, PAUSE_BUTTON_CENTER[1] + 6),
                (PAUSE_BUTTON_CENTER[0] + 6, PAUSE_BUTTON_CENTER[1]),
            ]
            pygame.draw.polygon(self.screen, BUTTON_COLOR, points)
        else:
            # Draw pause icon (||)
            bar_width = 4
            bar_height = 14
            spacing = 4
            left_bar = pygame.Rect(
                PAUSE_BUTTON_CENTER[0] - spacing - bar_width // 2,
                PAUSE_BUTTON_CENTER[1] - bar_height // 2,
                bar_width,
                bar_height
            )
            right_bar = pygame.Rect(
                PAUSE_BUTTON_CENTER[0] + spacing - bar_width // 2,
                PAUSE_BUTTON_CENTER[1] - bar_height // 2,
                bar_width,
                bar_height
            )
            pygame.draw.rect(self.screen, ICON_COLOR, left_bar)
            pygame.draw.rect(self.screen, ICON_COLOR, right_bar)

    def draw_reset_button(self):
        button_color = BUTTON_BG_ACTIVE if _distance(self.mouse_pos, self.reset_pos) <= BUTTON_RADIUS else BUTTON_BG
        reset_rect = self.reset_png.get_rect(center=RESET_BUTTON_CENTER)
        pygame.draw.circle(self.screen, button_color, RESET_BUTTON_CENTER, BUTTON_RADIUS)
        self.screen.blit(self.reset_png, reset_rect)

    def render(self):
        self.screen.fill(BG_COLOR)
        self.draw_pause_button()
        self.draw_reset_button()
        for station_id, station in self.system.stations.items():
            self.draw_entity(station, STATION_COLOR, station_id)
        for parking_id, parking in self.system.parkings.items():
            self.draw_entity(parking, PARKING_COLOR, parking_id)
        for amr_id, amr in self.system.amrs.items():
            self.draw_entity(amr, AMR_COLOR, amr_id)
        pygame.display.flip()
        self.clock.tick(50)  # FPS

    def handle_events(self):
        self.mouse_pos.x, self.mouse_pos.y = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pause_dist = _distance(self.mouse_pos, self.pause_pos)
                mouse_reset_dist = _distance(self.mouse_pos, self.reset_pos)
                
                if mouse_pause_dist <= BUTTON_RADIUS:
                    self.system.paused = not self.system.paused
                    print(f"System {'paused' if self.system.paused else 'resumed'}")
                    # print(f"Simulation {'paused' if self.paused else 'resumed'}")
                elif mouse_reset_dist <= BUTTON_RADIUS:
                    if RESET_BUTTON_RECT.collidepoint(event.pos):
                        self.system.reset()
                        print("Simulation reset")

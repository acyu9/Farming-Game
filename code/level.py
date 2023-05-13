import pygame
from settings import *
from player import Player
from overlay import Overlay
from sprites import Generic, Water, WildFlower, Tree, Interaction, Particle
from pytmx.util_pygame import load_pygame
from support import *
from transition import Transition
from soil import SoilLayer
from sky import Rain, Sky
from random import randint
from menu import Menu

class Level:
    def __init__(self):
        # Get the display surface
        self.display_surface = pygame.display.get_surface()

        # Sprite groups
        # The Player instance is added to the all_sprites group
        # self.all_sprites = pygame.sprite.Group()
        self.all_sprites = CameraGroup()
        # Put all sprites that player can be collide with in this group
        self.collision_sprites = pygame.sprite.Group()
        self.tree_sprites = pygame.sprite.Group()
        self.interaction_sprites = pygame.sprite.Group()

        self.soil_layer = SoilLayer(self.all_sprites, self.collision_sprites)
        self.setup()
        # player is created in setup
        self.overlay = Overlay(self.player)
        self.transition = Transition(self.reset, self.player)

        # Sky
        self.rain = Rain(self.all_sprites)
        self.raining = randint(0, 10) > 7
        self.soil_layer.raining = self.raining
        self.sky = Sky()

        # Shop
        self.menu = Menu(self.player, self.toggle_shop)
        self.shop_active = False

        # Music
        self.success = pygame.mixer.Sound('./audio/success.wav')
        self.success.set_volume(0.3)
        self.music = pygame.mixer.Sound('./audio/music.mp3')
        self.music.set_volume(0.5)
        self.music.play(loops = -1)
        
    def setup(self):
        tmx_data = load_pygame('./data/map.tmx')

        # House
        # Put HouseFloor first to make sure the carpet is on top of the floor
        for layer in ['HouseFloor', 'HouseFurnitureBottom']:
            for x, y, surf in tmx_data.get_layer_by_name(layer).tiles():
                # (pos, surf, groups, z)
                Generic((x * TILE_SIZE, y * TILE_SIZE), surf, self.all_sprites, LAYERS['house bottom'])

        for layer in ['HouseWalls', 'HouseFurnitureTop']:
            for x, y, surf in tmx_data.get_layer_by_name(layer).tiles():
                # Default is LAYERS['main'] so don't need to add it at the end for z
                Generic((x * TILE_SIZE, y * TILE_SIZE), surf, self.all_sprites)

        # Fence
        for x, y, surf in tmx_data.get_layer_by_name('Fence').tiles():
            Generic((x * TILE_SIZE, y * TILE_SIZE), surf, [self.all_sprites, self.collision_sprites])

        # Water
        water_frames = import_folder('./graphics/water')
        for x, y, surf in tmx_data.get_layer_by_name('Water').tiles():
            Water((x * TILE_SIZE, y * TILE_SIZE), water_frames, self.all_sprites)

        # Trees
        for obj in tmx_data.get_layer_by_name('Trees'):
            Tree(
                pos=(obj.x, obj.y), 
                surf=obj.image, 
                groups=[self.all_sprites, self.collision_sprites, self.tree_sprites], 
                name=obj.name,
                player_add=self.player_add
                )

        # Flowers
        for obj in tmx_data.get_layer_by_name('Decoration'):
            WildFlower((obj.x, obj.y), obj.image, [self.all_sprites, self.collision_sprites])

        # Collision tiles
        # Prevents player from walking onto water, pass through the walls of house, etc.
        for x, y, surf in tmx_data.get_layer_by_name('Collision').tiles():
            # Empty surf with the size of tile
            Generic((x * TILE_SIZE, y * TILE_SIZE), pygame.Surface((TILE_SIZE, TILE_SIZE)), self.collision_sprites)

        # Create player
        # Starting location for player
        for obj in tmx_data.get_layer_by_name('Player'):
            if obj.name == 'Start':
                # pos = (x, y)
                # Player sprite itself is not in the collision sprite, unlike [] in flowers for example
                self.player = Player(
                    pos=(obj.x,obj.y), 
                    group=self.all_sprites, 
                    collision_sprites=self.collision_sprites,
                    tree_sprites=self.tree_sprites,
                    interaction=self.interaction_sprites,
                    soil_layer = self.soil_layer,
                    toggle_shop = self.toggle_shop
                    )
                
            if obj.name == 'Bed':
                Interaction(
                    pos=(obj.x, obj.y),
                    size=(obj.width, obj.height),
                    groups=self.interaction_sprites,
                    name=obj.name
                    )
            
            # Info from Tile
            if obj.name == 'Trader':
                Interaction(
                    pos=(obj.x, obj.y),
                    size=(obj.width, obj.height),
                    groups=self.interaction_sprites,
                    name=obj.name
                    )

        # Create world
        Generic(
            pos=(0,0), 
            surf=pygame.image.load('./graphics/world/ground.png').convert_alpha(), 
            groups=self.all_sprites,
            z = LAYERS['ground']
            )

    def player_add(self, item):
        self.player.item_inventory[item] += 1
        self.success.play()

    def toggle_shop(self):
        self.shop_active = not self.shop_active

    def reset(self):
        # Plants
        self.soil_layer.update_plants()

        # Soil
        self.soil_layer.remove_water()

        # Randomize the rain
        self.raining = randint(0, 10) > 7
        self.soil_layer.raining = self.raining
        # Water existing tiles
        if self.raining:
            self.soil_layer.water_all()

        # Apples on the trees
        for tree in self.tree_sprites.sprites():
            # Destroy old apples
            for apple in tree.apple_sprites.sprites():
                apple.kill()
            # Create new apples
            tree.create_fruit()
        
        # Sky
        self.sky.start_color = [255,255,255]

    def plant_collision(self):
        if self.soil_layer.plant_sprites:
            for plant in self.soil_layer.plant_sprites.sprites():
                if plant.harvestable and plant.rect.colliderect(self.player.hitbox):
                    # Update inventory
                    self.player_add(plant.plant_type)
                    plant.kill()
                    Particle(
                        pos = plant.rect.topleft,
                        surf = plant.image,
                        groups = self.all_sprites,
                        z = LAYERS['main'] 
                    )
                    self.soil_layer.grid[plant.rect.centery // TILE_SIZE][plant.rect.centerx // TILE_SIZE].remove('P')

    def run(self, dt):
        # Drawing logic
        self.display_surface.fill('black')
        # Draw sprites on display surface
        self.all_sprites.custom_draw(self.player)
        
        # Updates
        if self.shop_active:
            self.menu.update()
        else:
            # This will call the update in player.py
            # Calls the update method of each sprite in the self.all_sprites group, including the Player object, which executes its own update method
            self.all_sprites.update(dt)
            self.plant_collision()

        # Weather
        self.overlay.display()
        if self.raining and not self.shop_active:
            self.rain.update()
        self.sky.display(dt)

        # Transition to new day
        if self.player.sleep:
            self.transition.play()

        


class CameraGroup(pygame.sprite.Group):
    def __init__(self):
        super().__init__()
        # Draw camera group on the display surface
        self.display_surface = pygame.display.get_surface()
        self.offset = pygame.math.Vector2()
    
    def custom_draw(self, player):
        # Shift every sprite relative to the player. 
        # Player is always in the center of the camera
        self.offset.x = player.rect.centerx - SCREEN_WIDTH / 2
        self.offset.y = player.rect.centery - SCREEN_HEIGHT / 2

        for layer in LAYERS.values():
            # The further down in y axis sprite will be drawn last so it's in the front
            for sprite in sorted(self.sprites(), key=lambda sprite: sprite.rect.centery):
                if sprite.z == layer:
                    offset_rect = sprite.rect.copy()
                    offset_rect.center -= self.offset
                    self.display_surface.blit(sprite.image, offset_rect)
        
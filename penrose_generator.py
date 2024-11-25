# penrose_generator.py
import os
import numpy as np
import glfw
from OpenGL.GL import *
from threading import Thread
from collections import OrderedDict
from penrose_tools import Operations, Tile, Effects, OptimizedRenderer, run_server, run_bluetooth_server
import logging
import configparser
import signal
import argparse
import asyncio
from penrose_tools.events import update_event, toggle_shader_event, randomize_colors_event, shutdown_event, toggle_regions_event, toggle_gui_event
from threading import Timer
import random
import time
# Configuration and initialization
CONFIG_PATH = 'config.ini'
DEFAULT_CONFIG = {
    'size': 15,
    'scale': 15,
    'gamma': [1.0, 0.7, 0.5, 0.3, 0.1],
    'color1': [205, 255, 255],
    'color2': [0, 0, 255],
    'cycle' : [False,False,False],
    'timer' : 0
}

op = Operations()
gui_visible = False
running = True
width = 0
height = 0

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('Penrose_Generator')

class CycleManager:
    def __init__(self, config_path, update_event, toggle_shader_event, randomize_colors_event):
        self.config_path = config_path
        self.update_event = update_event
        self.toggle_shader_event = toggle_shader_event
        self.randomize_colors_event = randomize_colors_event
        self.timer_thread = None
        self.running = True
        
    def randomize_gamma(self):
        config = configparser.ConfigParser()
        config.read(self.config_path)
        new_gamma = [random.uniform(-1.0, 1.0) for _ in range(5)]
        config['Settings']['gamma'] = ', '.join(map(str, new_gamma))
        with open(self.config_path, 'w') as configfile:
            config.write(configfile)
        self.update_event.set()

    def check_cycles(self):
        while self.running:
            try:
                config = configparser.ConfigParser()
                config.read(self.config_path)
                cycle_str = config['Settings'].get('cycle', '[False, False, False]')
                timer_str = config['Settings'].get('timer', '30')
                
                # Parse cycle settings
                cycle = eval(cycle_str)  # Safely evaluate string to list
                timer = int(timer_str)
                
                if any(cycle):  # If any cycle is enabled
                    if cycle[0]:  # Cycle Effects
                        self.toggle_shader_event.set()
                    
                    if cycle[1]:  # Randomize Gamma
                        self.randomize_gamma()
                    
                    if cycle[2]:  # Cycle Colors
                        self.randomize_colors_event.set()
                    
                    # Add offset to prevent all events happening at once
                    base_sleep = timer
                    if cycle[1]:  # Gamma offset
                        base_sleep += 1
                    if cycle[2]:  # Colors offset
                        base_sleep += 2
                
                time.sleep(max(timer, 5))  # Minimum 5 second delay
                
            except Exception as e:
                logger.error(f"Error in cycle check: {e}")
                time.sleep(5)  # Wait before retry on error

    def start(self):
        self.timer_thread = Thread(target=self.check_cycles, daemon=True)
        self.timer_thread.start()

    def stop(self):
        self.running = False
        if self.timer_thread:
            self.timer_thread.join()

def initialize_config(path):
    if not os.path.isfile(path):
        print("Config file not found. Creating a new one...")
        config = configparser.ConfigParser()
        config['Settings'] = {
            'size': str(DEFAULT_CONFIG['size']),
            'scale': str(DEFAULT_CONFIG['scale']),
            'gamma': ', '.join(map(str, DEFAULT_CONFIG['gamma'])),
            'color1': ', '.join(map(str, DEFAULT_CONFIG['color1'])),
            'color2': ', '.join(map(str, DEFAULT_CONFIG['color2'])),
            'cycle': ', '.join(map(str, DEFAULT_CONFIG['cycle'])),
            'timer': str(DEFAULT_CONFIG['timer'])
        }
        with open(path, 'w') as configfile:
            config.write(configfile)
    return op.read_config_file(path)

config_data = initialize_config(CONFIG_PATH)
tiles_cache = OrderedDict()

def setup_window(fullscreen=False):
    global width, height
    if not glfw.init():
        raise Exception("GLFW can't be initialized")
    
    # Request OpenGL 3.1 context
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 1)
    glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, GL_TRUE)
    
    # Get the primary monitor
    primary_monitor = glfw.get_primary_monitor()
    
    if fullscreen:
        video_mode = glfw.get_video_mode(primary_monitor)
        width, height = video_mode.size.width, video_mode.size.height
        window = glfw.create_window(width, height, "Penrose Tiling", primary_monitor, None)
    else:
        width, height = 1280, 720
        window = glfw.create_window(width, height, "Penrose Tiling", None, None)

    if not window:
        glfw.terminate()
        raise Exception("GLFW window can't be created")
    
    glfw.make_context_current(window)
    return window

def update_toggles(shaders):
    global config_data, running
    logger.debug("Checking for events...")
    if randomize_colors_event.is_set():
        logger.info("Randomize Colors Event Detected")
        for i in range(3):
            config_data['color1'][i] = np.random.randint(0, 256)
            config_data['color2'][i] = np.random.randint(0, 256)
        randomize_colors_event.clear()
        op.update_config_file(CONFIG_PATH, **config_data)
    if update_event.is_set():
        logger.info("Update Event Detected")
        update_event.clear()
        config_data = op.read_config_file(CONFIG_PATH)
    if toggle_shader_event.is_set():
        logger.info("Toggle Shader Event Detected - Before toggle")
        toggle_shader_event.clear()
        next_index = shaders.next_shader()
        logger.info(f"Shader switched to index {next_index}")
    if shutdown_event.is_set():
        logger.info("Shutdown Event Detected")
        running = False
        return False

def main():
    global width, height, config_data

    parser = argparse.ArgumentParser(description="Penrose Tiling Generator")
    parser.add_argument('--fullscreen', action='store_true', help='Run in fullscreen mode')
    parser.add_argument('-bt', '--bluetooth', action='store_true', help='Use Bluetooth server instead of HTTP')
    args = parser.parse_args()

    try:
        logger.info("Starting the penrose generator script.")
        window = setup_window(fullscreen=args.fullscreen)
        
        # Initialize OpenGL settings
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glClearColor(0, 0, 0, 1)
        
        # Setup viewport only - no more matrix mode operations
        glViewport(0, 0, width, height)
        
        # Initialize renderer after OpenGL context is created
        renderer = OptimizedRenderer()
        
        if args.bluetooth:
            server_thread = Thread(target=run_bluetooth_server, 
                                args=(CONFIG_PATH, update_event, toggle_shader_event,
                                     randomize_colors_event, shutdown_event),
                                daemon=True)
        else:
            server_thread = Thread(target=run_server, daemon=True)
        
        server_thread.start()
        logger.info(f"{'Bluetooth' if args.bluetooth else 'HTTP'} server started.")

        last_time = glfw.get_time()
        while not glfw.window_should_close(window) and running:
            glfw.poll_events()
            glClear(GL_COLOR_BUFFER_BIT)

            if any(event.is_set() for event in [update_event, toggle_shader_event, randomize_colors_event]):
                update_toggles(renderer.shader_manager)
            
            cycle_manager = CycleManager(CONFIG_PATH, update_event, toggle_shader_event, randomize_colors_event)
            cycle_manager.start()

            renderer.render_tiles(width, height, config_data)
            glfw.swap_buffers(window)

            # Frame rate limiting
            while glfw.get_time() < last_time + 1.0 / 60.0:
                pass
            last_time = glfw.get_time()

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise
    finally:
        glfw.terminate()
        cycle_manager.stop()
        shutdown_event.set()
        logger.info("Application has been terminated.")

if __name__ == '__main__':
    main()
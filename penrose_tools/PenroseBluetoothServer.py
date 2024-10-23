from bluezero import adapter
from bluezero import peripheral
from bluezero import async_tools
import configparser
import json
import threading
import logging
from typing import List

# Service and characteristic UUIDs
PENROSE_SERVICE = '12345000-1234-1234-1234-123456789abc'
CONFIG_CHAR = '12345001-1234-1234-1234-123456789abc'
COMMAND_CHAR = '12345002-1234-1234-1234-123456789abc'

class PenroseBluetoothServer:
    def __init__(self, config_file: str, update_event: threading.Event, 
                 toggle_shader_event: threading.Event, 
                 randomize_colors_event: threading.Event,
                 shutdown_event: threading.Event):
        self.config_file = config_file
        self.update_event = update_event
        self.toggle_shader_event = toggle_shader_event
        self.randomize_colors_event = randomize_colors_event
        self.shutdown_event = shutdown_event
        self.peripheral = None
        self.logger = logging.getLogger('PenroseBLE')
        self.logger.setLevel(logging.DEBUG)

    def read_config(self) -> List[int]:
        """Read current configuration and convert to bytes"""
        config = configparser.ConfigParser()
        config.read(self.config_file)
        settings = dict(config['Settings'])
        
        formatted_settings = {
            "size": int(settings.get('size', 0)),
            "scale": int(settings.get('scale', 0)),
            "gamma": [float(x.strip()) for x in settings.get('gamma', '').split(',')],
            "color1": [int(x.strip()) for x in settings.get('color1', '').replace('(', '').replace(')', '').split(',')],
            "color2": [int(x.strip()) for x in settings.get('color2', '').replace('(', '').replace(')', '').split(',')]
        }
        
        # Convert to JSON and then to bytes
        return list(json.dumps(formatted_settings).encode())

    def write_config(self, value: List[int]) -> bool:
        """Handle configuration updates from Bluetooth"""
        try:
            # Convert bytes to JSON
            data = json.loads(bytes(value).decode())
            
            config = configparser.ConfigParser()
            config.read(self.config_file)
            
            for key, value in data.items():
                if isinstance(value, list):
                    if key in ['color1', 'color2']:
                        config.set('Settings', key, f"({', '.join(map(str, value))})")
                    else:
                        config.set('Settings', key, ', '.join(map(str, value)))
                else:
                    config.set('Settings', key, str(value))
                    
            with open(self.config_file, 'w') as configfile:
                config.write(configfile)
                
            self.update_event.set()
            return True
        except Exception as e:
            self.logger.error(f"Config write error: {e}")
            return False

    def handle_command(self, value: List[int]) -> bool:
        """Handle commands from Bluetooth"""
        try:
            command = bytes(value).decode()
            command_data = json.loads(command)
            
            if command_data['command'] == 'toggle_shader':
                self.toggle_shader_event.set()
            elif command_data['command'] == 'randomize_colors':
                self.randomize_colors_event.set()
            elif command_data['command'] == 'shutdown':
                self.shutdown_event.set()
            return True
        except Exception as e:
            self.logger.error(f"Command error: {e}")
            return False

    def start_server(self):
        """Initialize and start the Bluetooth server"""
        # Get the default adapter address
        adapter_addr = list(adapter.Adapter.available())[0].address
        
        # Create peripheral
        self.peripheral = peripheral.Peripheral(adapter_addr,
                                             local_name='Penrose Generator',
                                             appearance=0)  # Generic appearance

        # Add main service
        self.peripheral.add_service(srv_id=1, 
                                  uuid=PENROSE_SERVICE,
                                  primary=True)

        # Add configuration characteristic
        self.peripheral.add_characteristic(
            srv_id=1,
            chr_id=1,
            uuid=CONFIG_CHAR,
            value=[],
            flags=['read', 'write'],
            notifying=False,
            read_callback=self.read_config,
            write_callback=self.write_config
        )

        # Add command characteristic
        self.peripheral.add_characteristic(
            srv_id=1,
            chr_id=2,
            uuid=COMMAND_CHAR,
            value=[],
            flags=['write'],
            notifying=False,
            write_callback=self.handle_command
        )

        # Start the server
        self.logger.info("Starting Bluetooth server...")
        self.peripheral.publish()

def run_bluetooth_server(config_file: str,
                        update_event: threading.Event,
                        toggle_shader_event: threading.Event,
                        randomize_colors_event: threading.Event,
                        shutdown_event: threading.Event):
    """Main function to run the Bluetooth server"""
    server = PenroseBluetoothServer(
        config_file,
        update_event,
        toggle_shader_event,
        randomize_colors_event,
        shutdown_event
    )
    
    server.start_server()
    
    # Wait for shutdown event
    shutdown_event.wait()
    server.logger.info("Bluetooth server shutting down...")
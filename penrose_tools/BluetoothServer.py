# penrose_tools/BluetoothServer.py

import logging
import json
import configparser
import threading
import sys
import uuid
import subprocess
import asyncio
import time
import os

from bluezero import peripheral, adapter, async_tools, advertisement

# Static UUIDs for services and characteristics
CONFIG_SERVICE_UUID = '3b0055b8-37ed-40a5-b17f-f38b9417c8cb'
CONFIG_READ_CHAR_UUID = '3b0055b8-37ed-40a5-b17f-f38b9417c8cc'
CONFIG_WRITE_CHAR_UUID = '3b0055b8-37ed-40a5-b17f-f38b9417c8cd'
COMMAND_SERVICE_UUID = '3b0055b8-37ed-40a5-b17f-f38b9417c8ce'
COMMAND_CHAR_UUID = '3b0055b8-37ed-40a5-b17f-f38b9417c8cf'

class ConfigAdvertisement(advertisement.Advertisement):
    def __init__(self, advert_id):
        super().__init__(advert_id, 'peripheral')
        self.include_tx_power = True
        
        # Add service UUIDs
        self.add_service_uuid(CONFIG_SERVICE_UUID)
        self.add_service_uuid(COMMAND_SERVICE_UUID)
        
        # Add AD flags
        self.add_flag(0x06)  # General Discoverable and BR/EDR Not Supported
        
        # Add local name
        self.add_local_name('PenroseServer')
        
        # Add manufacturer data
        # Replace 0x004C with your Company Identifier Code if available
        self.add_manufacturer_data(0x004C, [0x02, 0x15])  # Example manufacturer data

class BluetoothServer:
    def __init__(self, config_path, update_event, toggle_shader_event, randomize_colors_event, shutdown_event, adapter_address=None):
        logging.basicConfig(
            level=logging.DEBUG,  # Changed to DEBUG for more verbose logging
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler("bluetooth_server.log"),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger('BluetoothServer')
        
        # Store parameters
        self.config_path = config_path
        self.update_event = update_event
        self.toggle_shader_event = toggle_shader_event
        self.randomize_colors_event = randomize_colors_event
        self.shutdown_event = shutdown_event

        # Initialize adapter
        self.setup_adapter()
        
        # Initialize Peripheral
        self.setup_peripheral()

    def setup_adapter(self):
        """Initialize and configure the Bluetooth adapter"""
        try:
            # Reset Bluetooth service first
            subprocess.run(['sudo', 'systemctl', 'restart', 'bluetooth'], check=True)
            self.logger.info("Bluetooth service restarted")
            
            # Get available adapters
            self.dongles = adapter.list_adapters()
            self.logger.info(f'Available dongles: {self.dongles}')
            
            if not self.dongles:
                raise Exception("No Bluetooth adapters found")

            self.adapter_obj = adapter.Adapter(self.dongles[0])
            self.adapter_address = self.adapter_obj.address
            
            # Power cycle the adapter
            self.adapter_obj.powered = False
            time.sleep(1)
            self.adapter_obj.powered = True
            
            # Configure adapter
            self.adapter_obj.discoverable = True
            self.adapter_obj.discoverable_timeout = 0  # Always discoverable
            self.adapter_obj.pairable = True
            self.adapter_obj.pairable_timeout = 0  # Always pairable
            self.adapter_obj.alias = 'ConfigServer'

            self.logger.info(f"Adapter configured:")
            self.logger.info(f"  Address: {self.adapter_address}")
            self.logger.info(f"  Powered: {self.adapter_obj.powered}")
            self.logger.info(f"  Discoverable: {self.adapter_obj.discoverable}")
            self.logger.info(f"  Pairable: {self.adapter_obj.pairable}")
            self.logger.info(f"  Name: {self.adapter_obj.name}")
            self.logger.info(f"  Alias: {self.adapter_obj.alias}")

        except Exception as e:
            self.logger.error(f"Failed to initialize adapter: {e}")
            raise

    def setup_peripheral(self):
        """Initialize and configure the peripheral device"""
        try:
            # Create and register advertisement with unique advert_id (e.g., 0)
            self.advertisement = ConfigAdvertisement(advert_id=0)
            
            # Initialize peripheral without manufacturer_data
            self.peripheral = peripheral.Peripheral(
                self.adapter_address,
                local_name='PenroseServer',
                appearance=0x0  # Generic computer
            )
            
            self.add_services()
            
            # Set callbacks
            self.peripheral.on_connect = self.on_device_connect
            self.peripheral.on_disconnect = self.on_device_disconnect
            
            self.logger.info("Peripheral setup completed")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize peripheral: {e}")
            raise

    def add_services(self):
        """Add GATT services and characteristics to the peripheral"""
        # Configuration Service
        config_service = peripheral.Service(CONFIG_SERVICE_UUID, True)

        # Read Characteristic
        read_char = peripheral.Characteristic(
            CONFIG_READ_CHAR_UUID,
            ['read'],
            config_service
        )
        read_char.add_read_callback(self.read_config_callback)

        # Write Characteristic
        write_char = peripheral.Characteristic(
            CONFIG_WRITE_CHAR_UUID,
            ['write'],
            config_service
        )
        write_char.add_write_callback(self.write_config_callback)

        # Command Service
        command_service = peripheral.Service(COMMAND_SERVICE_UUID, True)

        # Command Characteristic
        command_char = peripheral.Characteristic(
            COMMAND_CHAR_UUID,
            ['write'],
            command_service
        )
        command_char.add_write_callback(self.command_callback)

        # Add services to peripheral
        self.peripheral.add_service(config_service)
        self.peripheral.add_service(command_service)

    def publish(self):
        """Publish the peripheral and start advertising"""
        try:
            # Register and start advertising
            self.advertisement.register()
            self.logger.info("Advertisement registered")
            
            # Publish GATT server
            self.peripheral.publish()
            self.logger.info("GATT server published")
            
            while not self.shutdown_event.is_set():
                time.sleep(1)
                
        except Exception as e:
            self.logger.error(f"Error in publish: {e}")
        finally:
            self.unpublish()

    def unpublish(self):
        """Clean up advertising and GATT server"""
        try:
            self.advertisement.release()
            self.logger.info("Advertisement stopped")
            self.peripheral.unpublish()
            self.logger.info("GATT server unpublished")
        except Exception as e:
            self.logger.error(f"Error in unpublish: {e}")

    def read_config_callback(self):
        """
        Callback to handle read requests for configuration data.
        Returns a list of byte values representing the JSON configuration.
        """
        try:
            config = self.read_config()
            config_json = json.dumps(config)
            config_bytes = config_json.encode('utf-8')
            byte_list = list(config_bytes)
            self.logger.info(f"Config Read: {config_json}")
            return byte_list
        except Exception as e:
            self.logger.error(f"Error reading config: {e}")
            error_response = {'status': 'error', 'message': str(e)}
            return list(json.dumps(error_response).encode('utf-8'))

    def write_config_callback(self, value, options):
        """
        Callback to handle write requests for updating configuration data.

        :param value: List of byte values written to the characteristic.
        :param options: Additional options.
        """
        try:
            # Convert list of bytes to bytes object
            value_bytes = bytes(value)
            data_str = value_bytes.decode('utf-8')
            data = json.loads(data_str)
            self.write_config(data)
            self.logger.info(f"Configuration updated: {data}")

            # Trigger the update event
            self.update_event.set()
        except Exception as e:
            self.logger.error(f"Error writing config: {e}")

    def command_callback(self, value, options):
        """
        Callback to handle write requests for executing commands.

        :param value: List of byte values written to the characteristic.
        :param options: Additional options.
        """
        try:
            # Convert list of bytes to bytes object
            value_bytes = bytes(value)
            command = value_bytes.decode('utf-8').strip()
            self.logger.info(f"Received command: {command}")
            response = self.handle_command(command)
        except Exception as e:
            self.logger.error(f"Error handling command: {e}")

    def read_config(self):
        """
        Read the configuration from the config.ini file.

        :return: Dictionary of configuration settings.
        """
        config = configparser.ConfigParser()
        config.read(self.config_path)
        settings = dict(config['Settings'])
        formatted_settings = {
            "size": int(settings.get('size', 0)),
            "scale": int(settings.get('scale', 0)),
            "gamma": [float(x.strip()) for x in settings.get('gamma', '').split(',')],
            "color1": [int(x.strip()) for x in settings.get('color1', '').replace('(', '').replace(')', '').split(',')],
            "color2": [int(x.strip()) for x in settings.get('color2', '').replace('(', '').replace(')', '').split(',')]
        }
        self.logger.debug(f"Formatted settings: {formatted_settings}")
        return formatted_settings

    def write_config(self, new_settings):
        """
        Write the configuration to the config.ini file.

        :param new_settings: Dictionary of new settings to update.
        """
        config = configparser.ConfigParser()
        config.read(self.config_path)
        if 'Settings' not in config.sections():
            config.add_section('Settings')
        for key, value in new_settings.items():
            if isinstance(value, list):
                if key in ['color1', 'color2']:
                    config.set('Settings', key, f"({', '.join(map(str, value))})")
                else:
                    config.set('Settings', key, ', '.join(map(str, value)))
            else:
                config.set('Settings', key, str(value))
        with open(self.config_path, 'w') as configfile:
            config.write(configfile)
        self.logger.debug(f"New settings written to {self.config_path}: {new_settings}")
        self.update_event.set()

    def handle_command(self, command):
        """
        Handle incoming commands and set appropriate events.

        :param command: Command string.
        :return: Response dictionary.
        """
        if command == 'toggle_shader':
            self.toggle_shader_event.set()
            self.logger.info("Shader toggled")
            response = {'status': 'success', 'message': 'Shader toggled'}
        elif command == 'shutdown':
            self.shutdown_event.set()
            self.logger.info("Shutdown initiated")
            response = {'status': 'success', 'message': 'Server is shutting down'}
        elif command == 'randomize_colors':
            self.randomize_colors_event.set()
            self.logger.info("Colors randomized")
            response = {'status': 'success', 'message': 'Colors randomized'}
        else:
            self.logger.warning(f"Unknown command received: {command}")
            response = {'status': 'error', 'message': 'Unknown command'}
        
        return response

    def run_in_thread(self):
        """
        Run the Bluetooth server in a separate daemon thread.
        """
        server_thread = threading.Thread(target=self.publish, daemon=True)
        server_thread.start()
    
    def on_device_connect(self, device):
        """
        Callback for device connections.
        :param device: The connected device object
        """
        try:
            if hasattr(device, 'address'):
                self.logger.info(f"Device connected: {device.address}")
            else:
                self.logger.info(f"Device connected: {device}")
        except Exception as e:
            self.logger.error(f"Error in connection callback: {e}")

    def on_device_disconnect(self, device):
        """
        Callback for device disconnections.
        :param device: The disconnected device object
        """
        try:
            if hasattr(device, 'address'):
                self.logger.info(f"Device disconnected: {device.address}")
            else:
                self.logger.info(f"Device disconnected: {device}")
        except Exception as e:
            self.logger.error(f"Error in disconnection callback: {e}")

if __name__ == "__main__":
    # Example usage
    config_path = "config.ini"
    update_event = threading.Event()
    toggle_shader_event = threading.Event()
    randomize_colors_event = threading.Event()
    shutdown_event = threading.Event()

    server = BluetoothServer(
        config_path,
        update_event,
        toggle_shader_event,
        randomize_colors_event,
        shutdown_event
    )
    server.run_in_thread()

    # Keep the main thread alive
    try:
        while not shutdown_event.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown_event.set()
        server.unpublish()

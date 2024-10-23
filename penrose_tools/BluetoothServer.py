# penrose_tools/BluetoothServer.py

import logging
import json
import configparser
import threading
import sys
import uuid
import subprocess

from bluezero import peripheral, adapter, async_tools
# Static UUIDs for services and characteristics
# Generate your own unique UUIDs using a tool like https://www.uuidgenerator.net/
# Static UUIDs for services and characteristics
CONFIG_SERVICE_UUID = '3b0055b8-37ed-40a5-b17f-f38b9417c8cb'
CONFIG_READ_CHAR_UUID = '3b0055b8-37ed-40a5-b17f-f38b9417c8cc'
CONFIG_WRITE_CHAR_UUID = '3b0055b8-37ed-40a5-b17f-f38b9417c8cd'
COMMAND_SERVICE_UUID = '3b0055b8-37ed-40a5-b17f-f38b9417c8ce'
COMMAND_CHAR_UUID = '3b0055b8-37ed-40a5-b17f-f38b9417c8cf'
NOTIFICATION_CHAR_UUID = '3b0055b8-37ed-40a5-b17f-f38b9417c8cg'  # Optional for notifications

class BluetoothServer:
    def __init__(self, config_path, update_event, toggle_shader_event, randomize_colors_event, shutdown_event, adapter_address=None):
        """
        Initialize the Bluetooth Server with services and characteristics.
        """
        # Initialize logging first
        logging.basicConfig(
            level=logging.INFO,
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

        # Get available adapters
        self.dongles = adapter.list_adapters()
        self.logger.info(f'Available dongles: {self.dongles}')
        
        if not self.dongles:
            self.logger.error("No Bluetooth adapters found")
            sys.exit(1)

        # Initialize adapter
        try:
            self.adapter_obj = adapter.Adapter(self.dongles[0])
            self.adapter_address = self.adapter_obj.address
            self.logger.info(f'Using adapter: {self.adapter_address}')

            # Set adapter properties
            if not self.adapter_obj.powered:
                self.adapter_obj.powered = True
            self.adapter_obj.discoverable = True
            self.adapter_obj.pairable = True
            self.adapter_obj.alias = 'ConfigServer'  # Set a friendly name

            # Log adapter status
            self.logger.info(f"Adapter status:")
            self.logger.info(f"  Powered: {self.adapter_obj.powered}")
            self.logger.info(f"  Discoverable: {self.adapter_obj.discoverable}")
            self.logger.info(f"  Pairable: {self.adapter_obj.pairable}")
            self.logger.info(f"  Name: {self.adapter_obj.name}")
            self.logger.info(f"  Alias: {self.adapter_obj.alias}")

        except Exception as e:
            self.logger.error(f"Failed to initialize adapter: {e}")
            sys.exit(1)

        # Initialize Peripheral
        try:
            self.peripheral = peripheral.Peripheral(
                self.adapter_address,
                local_name='ConfigServer',
                appearance=0
            )
            
            # Add services before publishing
            self.add_services()
            
            # Set both connect and disconnect callbacks
            self.peripheral.on_connect = self.on_device_connect
            self.peripheral.on_disconnect = self.on_device_disconnect
            
        except Exception as e:
            self.logger.error(f"Failed to initialize peripheral: {e}")
            sys.exit(1)

    def add_services(self):
        """Add all services and characteristics."""
        # Add Config Service
        self.peripheral.add_service(
            srv_id=1,
            uuid=CONFIG_SERVICE_UUID,
            primary=True  # This will automatically add it to advertisement
        )
        self.logger.info(f"Added Config Service with UUID: {CONFIG_SERVICE_UUID}")

        # Add Config Read Characteristic
        self.peripheral.add_characteristic(
            srv_id=1,
            chr_id=1,
            uuid=CONFIG_READ_CHAR_UUID,
            flags=['read'],
            read_callback=self.read_config_callback,
            value=[],
            notifying=False
        )
        self.logger.info(f"Added Config Read Characteristic with UUID: {CONFIG_READ_CHAR_UUID}")

        # Add Config Write Characteristic
        self.peripheral.add_characteristic(
            srv_id=1,
            chr_id=2,
            uuid=CONFIG_WRITE_CHAR_UUID,
            flags=['write'],
            write_callback=self.write_config_callback,
            value=[],
            notifying=False
        )
        self.logger.info(f"Added Config Write Characteristic with UUID: {CONFIG_WRITE_CHAR_UUID}")

        # Add Command Service
        self.peripheral.add_service(
            srv_id=2,
            uuid=COMMAND_SERVICE_UUID,
            primary=True  # This will automatically add it to advertisement
        )
        self.logger.info(f"Added Command Service with UUID: {COMMAND_SERVICE_UUID}")

        # Add Command Characteristic
        self.peripheral.add_characteristic(
            srv_id=2,
            chr_id=1,
            uuid=COMMAND_CHAR_UUID,
            flags=['write'],
            write_callback=self.command_callback,
            value=[],
            notifying=False
        )
        self.logger.info(f"Added Command Characteristic with UUID: {COMMAND_CHAR_UUID}")

    def publish(self):
        """Publish the peripheral and start the event loop."""
        try:
            self.peripheral.publish()
            self.logger.info("Bluetooth GATT server is running...")
            
            self.logger.info(f"Advertising primary services...")
            
            while not self.shutdown_event.is_set():
                async_tools.sleep(1)
                
        except Exception as e:
            self.logger.error(f"Error in publish: {e}")
        finally:
            self.unpublish()

    def unpublish(self):
        """
        Unpublish the peripheral and clean up.
        """
        self.peripheral.unpublish()
        self.logger.info("Bluetooth GATT server has been shut down.")

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

            # Notify clients about the update (optional)
            # self.send_notification({'status': 'success', 'message': 'Configuration updated'})

            # Trigger the update event
            self.update_event.set()
        except Exception as e:
            self.logger.error(f"Error writing config: {e}")
            # Optionally, notify clients about the error
            # self.send_notification({'status': 'error', 'message': str(e)})

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

            # Notify clients about the command response (optional)
            # self.send_notification(response)
        except Exception as e:
            self.logger.error(f"Error handling command: {e}")
            # Optionally, notify clients about the error
            # self.send_notification({'status': 'error', 'message': str(e)})

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
        
        # Optional: Notify clients about the response
        # self.send_notification(response)
        
        return response

    def send_notification(self, message):
        """
        Send a notification to subscribed clients.

        :param message: Dictionary to send as JSON.
        """
        try:
            message_json = json.dumps(message)
            message_bytes = message_json.encode('utf-8')
            byte_list = list(message_bytes)
            self.peripheral.send_notify(NOTIFICATION_CHAR_UUID, byte_list)
            self.logger.info(f"Sent notification: {message_json}")
        except Exception as e:
            self.logger.error(f"Error sending notification: {e}")

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
            async_tools.sleep(1)
    except KeyboardInterrupt:
        shutdown_event.set()
        server.unpublish()
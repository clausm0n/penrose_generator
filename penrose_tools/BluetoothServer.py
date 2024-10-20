# penrose_tools/BluetoothServer.py

import logging
import json
import configparser
import threading
import sys
import uuid
import subprocess

from bluezero import peripheral, adapter, async_tools, advertisement

# Static UUIDs for services and characteristics
# Generate your own unique UUIDs using a tool like https://www.uuidgenerator.net/
CONFIG_SERVICE_UUID = '12345678-1234-5678-1234-56789abcdef0'
CONFIG_READ_CHAR_UUID = '12345678-1234-5678-1234-56789abcdef1'
CONFIG_WRITE_CHAR_UUID = '12345678-1234-5678-1234-56789abcdef2'
COMMAND_SERVICE_UUID = '12345678-1234-5678-1234-56789abcdef3'
COMMAND_CHAR_UUID = '12345678-1234-5678-1234-56789abcdef4'
NOTIFICATION_CHAR_UUID = '12345678-1234-5678-1234-56789abcdef5'  # Optional for notifications

class BluetoothServer:
    def __init__(self, config_path, update_event, toggle_shader_event, randomize_colors_event, shutdown_event, adapter_address=None):
        """
        Initialize the Bluetooth Server with services and characteristics.

        :param config_path: Path to the configuration file.
        :param update_event: Event to signal configuration updates.
        :param toggle_shader_event: Event to toggle shaders.
        :param randomize_colors_event: Event to randomize colors.
        :param shutdown_event: Event to signal server shutdown.
        :param adapter_address: (Optional) Bluetooth adapter address.
        """
        # Assign parameters to instance variables
        self.config_path = config_path
        self.update_event = update_event
        self.toggle_shader_event = toggle_shader_event
        self.randomize_colors_event = randomize_colors_event
        self.shutdown_event = shutdown_event
        self.dongles = adapter.list_adapters()
        print('dongles available: ', self.dongles)
        self.adapter_address = adapter.Adapter(self.dongles[0])
        print('address: ', self.adapter_address)
        self.ad_manager = advertisement.AdvertisingManager(self.adapter_address)

        # Initialize Logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler("bluetooth_server.log"),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger('BluetoothServer')

        # Initialize Peripheral
        if not adapter_address:
            adapters = list(adapter.Adapter.available())
            if not adapters:
                self.logger.error("No Bluetooth adapters found")
                sys.exit(1)
            self.adapter_address = adapters[0].address
        else:
            self.adapter_address = adapter_address

        self.peripheral = peripheral.Peripheral(
            self.adapter_address,
            local_name='ConfigServer',
            appearance=0
        )

        # Add Services and Characteristics
        self.add_services()
    
            # Start the Bluetooth Agent in a separate thread
        self.start_bluetooth_agent()
        self.peripheral.on_connect = self.connection_callback

    def start_bluetooth_agent(self):
        """
        Start the Bluetooth Agent as a separate thread.
        """
        agent_thread = threading.Thread(target=self.run_agent, daemon=True)
        agent_thread.start()
        self.logger.info("Bluetooth Agent thread started")

    def run_agent(self):
        """
        Run the Bluetooth Agent script.
        """
        try:
            subprocess.run([sys.executable, "penrose_tools/BluetoothAgent.py"], check=True)
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Bluetooth Agent failed: {e}")

    def add_services(self):
        """
        Define and add services and their characteristics to the peripheral.
        """
        # Add Config Service
        self.peripheral.add_service(
            srv_id=1,
            uuid=CONFIG_SERVICE_UUID,
            primary=True
        )
        self.logger.info(f"Added Config Service with UUID: {CONFIG_SERVICE_UUID}")

        # Add Config Read Characteristic
        self.peripheral.add_characteristic(
            srv_id=1,
            chr_id=1,
            uuid=CONFIG_READ_CHAR_UUID,
            flags=['read'],
            read_callback=self.read_config_callback,
            value=[],          # Initial value
            notifying=False    # Not notifying by default
        )
        self.logger.info(f"Added Config Read Characteristic with UUID: {CONFIG_READ_CHAR_UUID}")

        # Add Config Write Characteristic
        self.peripheral.add_characteristic(
            srv_id=1,
            chr_id=2,
            uuid=CONFIG_WRITE_CHAR_UUID,
            flags=['write'],
            write_callback=self.write_config_callback,
            value=[],          # Initial value
            notifying=False    # Not notifying by default
        )
        self.logger.info(f"Added Config Write Characteristic with UUID: {CONFIG_WRITE_CHAR_UUID}")

        # Add Command Service
        self.peripheral.add_service(
            srv_id=2,
            uuid=COMMAND_SERVICE_UUID,
            primary=True
        )
        self.logger.info(f"Added Command Service with UUID: {COMMAND_SERVICE_UUID}")

        # Add Command Characteristic
        self.peripheral.add_characteristic(
            srv_id=2,
            chr_id=1,
            uuid=COMMAND_CHAR_UUID,
            flags=['write'],
            write_callback=self.command_callback,
            value=[],          # Initial value
            notifying=False    # Not notifying by default
        )
        # Create the Advertisement
        self.advertisement = advertisement.Advertisement(1, 'ConfigServer')
        self.advertisement.service_uuids = [CONFIG_SERVICE_UUID, COMMAND_SERVICE_UUID]

        # Register the advertisement
        try:
            self.ad_manager.register_advertisement(self.advertisement, {})
            self.logger.info("Advertisement registered successfully")
        except Exception as e:
            self.logger.error(f"Failed to register advertisement: {e}")

        self.logger.info(f"Added Command Characteristic with UUID: {COMMAND_CHAR_UUID}")

        # Optional: Add Notification Characteristic for Responses
        # Uncomment the following block if you wish to send notifications back to clients
        """
        self.peripheral.add_characteristic(
            srv_id=2,
            chr_id=2,
            uuid=NOTIFICATION_CHAR_UUID,
            flags=['notify'],
            notify_callback=self.notify_callback,
            value=[],          # Initial value
            notifying=False    # Not notifying by default
        )
        self.logger.info(f"Added Notification Characteristic with UUID: {NOTIFICATION_CHAR_UUID}")
        """

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

    def publish(self):
        """
        Publish the peripheral and start the event loop.
        """
        self.peripheral.publish()
        self.logger.info("Bluetooth GATT server is running...")

        try:
            while not self.shutdown_event.is_set():
                async_tools.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("KeyboardInterrupt received. Shutting down.")
        finally:
            self.unpublish()

    def unpublish(self):
        """
        Unpublish the peripheral and clean up.
        """
        try:
            self.ad_manager.unregister_advertisement(self.advertisement)
            self.logger.info("Advertisement unregistered")
        except Exception as e:
            self.logger.error(f"Error unregistering advertisement: {e}")

        self.peripheral.unpublish()
        self.logger.info("Bluetooth GATT server has been shut down.")

    def run_in_thread(self):
        """
        Run the Bluetooth server in a separate daemon thread.
        """
        server_thread = threading.Thread(target=self.publish, daemon=True)
        server_thread.start()
    
    def connection_callback(self, device_addr, connected):
        if connected:
            self.logger.info(f"Device {device_addr} connected")
        else:
            self.logger.info(f"Device {device_addr} disconnected")

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
import logging
import json
import configparser
import threading
import sys
import uuid

from bluezero import peripheral, adapter, async_tools

# Constants
CONFIG_FILE = 'config.ini'

# Initialize Events
update_event = threading.Event()
toggle_shader_event = threading.Event()
toggle_regions_event = threading.Event()
toggle_gui_event = threading.Event()
shutdown_event = threading.Event()  # Shutdown event
randomize_colors_event = threading.Event()

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('BluetoothServer')


class BluetoothServer:
    def __init__(self, adapter_address=None):
        """
        Initialize the Bluetooth Server with services and characteristics.
        """
        # Generate UUIDs dynamically
        self.CONFIG_SERVICE_UUID = str(uuid.uuid4())
        self.CONFIG_READ_CHAR_UUID = str(uuid.uuid4())
        self.CONFIG_WRITE_CHAR_UUID = str(uuid.uuid4())
        self.COMMAND_SERVICE_UUID = str(uuid.uuid4())
        self.COMMAND_CHAR_UUID = str(uuid.uuid4())

        # Initialize Peripheral
        if not adapter_address:
            adapters = list(adapter.Adapter.available())
            if not adapters:
                logger.error("No Bluetooth adapters found")
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

    def add_services(self):
        """
        Define and add services and their characteristics to the peripheral.
        """
        # Config Service
        config_service = self.peripheral.add_service(
            srv_id=1,
            uuid=self.CONFIG_SERVICE_UUID,
            primary=True
        )
        config_service.add_characteristic(
            uuid=self.CONFIG_READ_CHAR_UUID,
            flags=['read'],
            read_callback=self.read_config_callback
        )
        config_service.add_characteristic(
            uuid=self.CONFIG_WRITE_CHAR_UUID,
            flags=['write'],
            write_callback=self.write_config_callback
        )

        # Command Service
        command_service = self.peripheral.add_service(
            srv_id=2,
            uuid=self.COMMAND_SERVICE_UUID,
            primary=True
        )
        command_service.add_characteristic(
            uuid=self.COMMAND_CHAR_UUID,
            flags=['write'],
            write_callback=self.command_callback
        )

    def read_config_callback(self):
        """
        Callback to handle read requests for configuration data.
        """
        try:
            config = self.read_config()
            response = json.dumps(config).encode('utf-8')
            logger.debug(f"Config Read: {response}")
            return response
        except Exception as e:
            logger.error(f"Error reading config: {e}")
            return json.dumps({'status': 'error', 'message': str(e)}).encode('utf-8')

    def write_config_callback(self, value, options):
        """
        Callback to handle write requests for updating configuration data.
        """
        try:
            data = json.loads(value.decode('utf-8'))
            self.write_config(data)
            logger.info(f"Configuration updated: {data}")
            response = {'status': 'success', 'message': 'Configuration updated'}
            return json.dumps(response).encode('utf-8')
        except Exception as e:
            logger.error(f"Error writing config: {e}")
            response = {'status': 'error', 'message': str(e)}
            return json.dumps(response).encode('utf-8')

    def command_callback(self, value, options):
        """
        Callback to handle write requests for executing commands.
        """
        try:
            command = value.decode('utf-8').strip()
            logger.info(f"Received command: {command}")
            response = self.handle_command(command)
            return json.dumps(response).encode('utf-8')
        except Exception as e:
            logger.error(f"Error handling command: {e}")
            response = {'status': 'error', 'message': str(e)}
            return json.dumps(response).encode('utf-8')

    def read_config(self):
        """
        Read the configuration from the config.ini file.
        """
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE)
        settings = dict(config['Settings'])
        formatted_settings = {
            "size": int(settings.get('size', 0)),
            "scale": int(settings.get('scale', 0)),
            "gamma": [float(x.strip()) for x in settings.get('gamma', '').split(',')],
            "color1": [int(x.strip()) for x in settings.get('color1', '').replace('(', '').replace(')', '').split(',')],
            "color2": [int(x.strip()) for x in settings.get('color2', '').replace('(', '').replace(')', '').split(',')]
        }
        logger.debug(f"Formatted settings: {formatted_settings}")
        return formatted_settings

    def write_config(self, new_settings):
        """
        Write the configuration to the config.ini file.
        """
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE)
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
        with open(CONFIG_FILE, 'w') as configfile:
            config.write(configfile)
        logger.debug(f"New settings written to config.ini: {new_settings}")
        update_event.set()

    def handle_command(self, command):
        """
        Handle incoming commands and set appropriate events.
        """
        if command == 'toggle_shader':
            toggle_shader_event.set()
            logger.info("Shader toggled")
            return {'status': 'success', 'message': 'Shader toggled'}
        elif command == 'shutdown':
            shutdown_event.set()
            logger.info("Shutdown initiated")
            return {'status': 'success', 'message': 'Server is shutting down'}
        elif command == 'randomize_colors':
            randomize_colors_event.set()
            logger.info("Colors randomized")
            return {'status': 'success', 'message': 'Colors randomized'}
        else:
            logger.warning(f"Unknown command received: {command}")
            return {'status': 'error', 'message': 'Unknown command'}

    def publish(self):
        """
        Publish the peripheral and start the event loop.
        """
        self.peripheral.publish()
        logger.info("Bluetooth GATT server is running...")

        try:
            while not shutdown_event.is_set():
                async_tools.sleep(1)
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received. Shutting down.")
        finally:
            self.unpublish()

    def unpublish(self):
        """
        Unpublish the peripheral and clean up.
        """
        self.peripheral.unpublish()
        logger.info("Bluetooth GATT server has been shut down.")


def main():
    """
    Entry point for the Bluetooth server.
    """
    server = BluetoothServer()
    server.publish()


if __name__ == '__main__':
    main()

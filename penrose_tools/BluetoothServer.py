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
import dbus
from gi.repository import GLib

from bluezero import adapter, advertisement, async_tools, localGATT, GATT

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
        self.service_UUIDs = [CONFIG_SERVICE_UUID, COMMAND_SERVICE_UUID]
        self.local_name = 'PenroseServer'

class BluetoothServer:
    def __init__(self, config_path, update_event, toggle_shader_event, randomize_colors_event, shutdown_event, adapter_address=None):
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler("bluetooth_server.log"),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger('BluetoothServer')
        
        # Initialize variables
        self.config_path = config_path
        self.update_event = update_event
        self.toggle_shader_event = toggle_shader_event
        self.randomize_colors_event = randomize_colors_event
        self.shutdown_event = shutdown_event
        self.adapter_address = adapter_address
        self.agent = None
        self.bus = None
        self.mainloop = None
        self.main_context = None
        self.app = None
        self.srv_mng = None
        self.ad_manager = None
        self.advertisement = None

    def shutdown_server(self):
        """Callback to shut down the server."""
        self.logger.info("Shutdown callback invoked by Agent.")
        self.shutdown_event.set()
        if self.mainloop.is_running():
            self.mainloop.quit()


    def start_agent(self):
        """Initialize and start the Bluetooth Agent"""
        try:
            from penrose_tools.BluetoothAgent import Agent, AGENT_PATH, CAPABILITY
            
            self.logger.debug("Attempting to create Agent instance...")
            # Create and register the agent with a shutdown callback
            self.agent = Agent(self.bus, AGENT_PATH, shutdown_callback=self.shutdown_server)
            self.logger.debug("Agent instance created.")

            manager = dbus.Interface(
                self.bus.get_object("org.bluez", "/org/bluez"),
                "org.bluez.AgentManager1"
            )
            
            manager.RegisterAgent(AGENT_PATH, CAPABILITY)
            self.logger.info("Bluetooth Agent registered")
            manager.RequestDefaultAgent(AGENT_PATH)
            self.logger.info("Bluetooth Agent set as default")
        except dbus.exceptions.DBusException as e:
            self.logger.error(f"Agent registration failed: {e}")
                
        # except Exception as e:
        #     self.logger.error(f"Failed to start Bluetooth Agent: {e}")
        #     raise

    def setup_adapter(self):
        """Initialize and configure the Bluetooth adapter"""
        try:
            self.logger.debug("Restarting Bluetooth service...")
            subprocess.run(['sudo', 'systemctl', 'restart', 'bluetooth'], check=True)
            self.logger.info("Bluetooth service restarted")
            
            self.dongles = adapter.list_adapters()
            self.logger.info(f'Available dongles: {self.dongles}')
            
            if not self.dongles:
                raise Exception("No Bluetooth adapters found")

            self.adapter_obj = adapter.Adapter(self.dongles[0])
            self.adapter_address = self.adapter_obj.address
            
            self.adapter_obj.powered = False
            time.sleep(1)
            self.adapter_obj.powered = True
            
            self.adapter_obj.discoverable = True
            self.adapter_obj.discoverable_timeout = 0
            self.adapter_obj.pairable = True
            self.adapter_obj.pairable_timeout = 0
            self.adapter_obj.alias = 'ConfigServer'

            self.logger.info(f"Adapter configured: {self.adapter_address}")

        except Exception as e:
            self.logger.error(f"Failed to initialize adapter: {e}")
            raise

    def setup_peripheral(self):
        """Initialize and configure the peripheral device"""
        try:
            self.logger.debug("Setting up GATT Application...")
            self.app = localGATT.Application()
            self.srv_mng = GATT.GattManager(self.adapter_address)
            self.ad_manager = advertisement.AdvertisingManager(self.adapter_address)
            
            # Create advertisement
            self.advertisement = ConfigAdvertisement(0)
            
            # Add services and characteristics
            self.add_services()
            
            self.logger.info("Peripheral setup completed")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize peripheral: {e}")
            raise

    def add_services(self):
        """Add GATT services and characteristics"""
        try:
            self.logger.debug("Adding GATT services and characteristics...")
            # Configuration Service
            config_service = localGATT.Service(1, CONFIG_SERVICE_UUID, True)
            self.app.add_managed_object(config_service)

            # Read Characteristic
            read_char = localGATT.Characteristic(
                1, 1, CONFIG_READ_CHAR_UUID,
                [], False, ['read'],
                self.read_config_callback, None, None
            )
            self.app.add_managed_object(read_char)

            # Write Characteristic
            write_char = localGATT.Characteristic(
                1, 2, CONFIG_WRITE_CHAR_UUID,
                [], False, ['write'],
                None, self.write_config_callback, None
            )
            self.app.add_managed_object(write_char)

            # Command Service
            command_service = localGATT.Service(2, COMMAND_SERVICE_UUID, True)
            self.app.add_managed_object(command_service)

            # Command Characteristic
            command_char = localGATT.Characteristic(
                2, 1, COMMAND_CHAR_UUID,
                [], False, ['write'],
                None, self.command_callback, None
            )
            self.app.add_managed_object(command_char)

            self.logger.debug("GATT services and characteristics added.")

        except Exception as e:
            self.logger.error(f"Failed to add services: {e}")
            raise

    def start_mainloop(self):
        """Start the GLib main loop in a separate thread."""
        try:
            self.logger.debug("Starting GLib main loop...")
            self.mainloop_thread = threading.Thread(target=self.mainloop.run, daemon=True)
            self.mainloop_thread.start()
            self.logger.debug("GLib main loop started in a separate thread.")
        except Exception as e:
            self.logger.error(f"Failed to start GLib main loop: {e}")
            raise

    def publish(self):
        """Publish the peripheral and set up the Bluetooth services"""
        try:
            self.logger.debug("Initializing D-Bus main loop...")
            # Initialize D-Bus main loop in this thread
            dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
            self.bus = dbus.SystemBus()
            self.mainloop = GLib.MainLoop()
            self.main_context = self.mainloop.get_context()

            self.logger.debug("Starting Bluetooth Agent...")
            # Start the agent
            self.start_agent()

            self.logger.debug("Setting up Bluetooth adapter...")
            # Set up the adapter
            self.setup_adapter()

            self.logger.debug("Setting up peripheral...")
            # Set up the peripheral
            self.setup_peripheral()

            if not self.adapter_obj.powered:
                self.adapter_obj.powered = True

            self.logger.debug("Registering GATT application...")
            self.srv_mng.register_application(self.app, {})
            self.logger.debug("Registering Advertisement...")

            try:
                self.ad_manager.register_advertisement(self.advertisement, {})
                self.logger.info("Advertisement registered successfully.")
            except dbus.exceptions.DBusException as e:
                self.logger.error(f"Failed to register advertisement: {e}")
                raise

            # Mark agent initialization as complete
            if hasattr(self, 'agent') and self.agent is not None:
                self.agent.set_initialization_complete()
                self.logger.info("Agent initialization marked as complete")

            self.logger.info("GATT server published and advertising")

            # Start the GLib main loop in the main thread
            self.mainloop.run()

        except Exception as e:
            self.logger.error(f"Error in publish: {e}")
            self.unpublish()


    def unpublish(self):
        """Clean up advertising and GATT server"""
        try:
            self.logger.debug("Unregistering Advertisement...")
            if self.ad_manager:
                try:
                    self.ad_manager.unregister_advertisement(self.advertisement)
                except Exception as e:
                    self.logger.warning(f"Failed to unregister advertisement: {e}")
                    
            self.logger.debug("Unregistering GATT Application...")
            if self.srv_mng:
                try:
                    self.srv_mng.unregister_application(self.app)
                except Exception as e:
                    self.logger.warning(f"Failed to unregister GATT application: {e}")
                    
            self.logger.info("GATT server unpublished")
            
            # Release the agent last, and only if initialization was complete
            if hasattr(self, 'agent') and self.agent is not None:
                if self.agent.initialization_complete and self.agent.can_shutdown():
                    self.logger.debug("Releasing Bluetooth Agent...")
                    try:
                        self.agent.Release()
                        self.logger.info("Bluetooth Agent released.")
                    except Exception as e:
                        self.logger.error(f"Error releasing agent: {e}")
                else:
                    self.logger.info("Skipping agent release as initialization is incomplete or in grace period")
                    
        except Exception as e:
            self.logger.error(f"Error in unpublish: {e}")

    def read_config_callback(self, options):
        """Callback for configuration read requests"""
        try:
            config = self.read_config()
            config_json = json.dumps(config)
            self.logger.debug("Read config callback called.")
            return list(config_json.encode('utf-8'))
        except Exception as e:
            self.logger.error(f"Error reading config: {e}")
            error_response = {'status': 'error', 'message': str(e)}
            return list(json.dumps(error_response).encode('utf-8'))

    def write_config_callback(self, value, options):
        """Callback for configuration write requests"""
        self.logger.debug("Write config callback called.")
        # Schedule the processing in the main loop using idle_add
        GLib.idle_add(self._write_config_callback, value, options)

    def _write_config_callback(self, value, options):
        """Actual processing of write_config_callback"""
        try:
            data_str = bytes(value).decode('utf-8')
            data = json.loads(data_str)
            self.write_config(data)
            self.update_event.set()
            self.logger.debug("Write config processed.")
            return False  # Remove the idle handler
        except Exception as e:
            self.logger.error(f"Error writing config: {e}")
            return False

    def command_callback(self, value, options):
        """Callback for command requests"""
        self.logger.debug("Command callback called.")
        # Schedule the processing in the main loop using idle_add
        GLib.idle_add(self._command_callback, value, options)

    def _command_callback(self, value, options):
        """Actual processing of command_callback"""
        try:
            command = bytes(value).decode('utf-8').strip()
            self.logger.info(f"Received command: {command}")
            response = self.handle_command(command)
            self.logger.debug(f"Command processed: {response}")
            return False  # Remove the idle handler
        except Exception as e:
            self.logger.error(f"Error handling command: {e}")
            return False

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
            # Notify the server to shut down via the shutdown callback
            # The Agent's Release method will already call the shutdown_callback
        elif command == 'randomize_colors':
            self.randomize_colors_event.set()
            self.logger.info("Colors randomized")
            response = {'status': 'success', 'message': 'Colors randomized'}
        else:
            self.logger.warning(f"Unknown command received: {command}")
            response = {'status': 'error', 'message': 'Unknown command'}
        
        # Depending on the library, you might need to send the response back
        # This example assumes the library handles sending responses based on the return value
        # If not, additional steps may be necessary

        return response

    # Removed run_in_thread since the server manages the main loop

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

    server.publish()

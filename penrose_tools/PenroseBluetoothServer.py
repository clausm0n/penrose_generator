#/penrose_tools/PenroseBluetoothServer.py

from bluezero import adapter
from bluezero import peripheral
from bluezero import async_tools
from bluezero import constants
import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib
import configparser
import json
import threading
import logging
from typing import List
from .Operations import Operations
from .events import update_event, toggle_shader_event, randomize_colors_event, shutdown_event


# Service and characteristic UUIDs
PENROSE_SERVICE = '12345000-1234-1234-1234-123456789abc'
CONFIG_CHAR = '12345001-1234-1234-1234-123456789abc'
COMMAND_CHAR = '12345002-1234-1234-1234-123456789abc'

# Additional Bluetooth constants
AGENT_INTERFACE = 'org.bluez.Agent1'
AGENT_MANAGER_INTERFACE = 'org.bluez.AgentManager1'
AGENT_PATH = "/org/bluez/AutoAgent"

class AutoAcceptAgent(dbus.service.Object):
    """
    Bluetooth agent that automatically accepts pairing requests
    """
    
    def __init__(self, bus, path):
        super().__init__(bus, path)
        self.logger = logging.getLogger('PenroseBLE.Agent')
        
    @dbus.service.method(AGENT_INTERFACE,
                        in_signature="os", out_signature="")
    def AuthorizeService(self, device, uuid):
        """Always authorize the service"""
        self.logger.info(f"Authorizing service {uuid} for device {device}")
        return

    @dbus.service.method(AGENT_INTERFACE,
                        in_signature="o", out_signature="")
    def RequestAuthorization(self, device):
        """Always authorize the device"""
        self.logger.info(f"Authorizing device {device}")
        return

    @dbus.service.method(AGENT_INTERFACE,
                        in_signature="ou", out_signature="")
    def DisplayPasskey(self, device, passkey):
        """Display the passkey (in this case, just log it)"""
        self.logger.info(f"Passkey: {passkey}")
        return

    @dbus.service.method(AGENT_INTERFACE,
                        in_signature="ou", out_signature="")
    def RequestConfirmation(self, device, passkey):
        """Automatically confirm pairing"""
        self.logger.info(f"Auto-accepting pairing request with passkey: {passkey}")
        return

    @dbus.service.method(AGENT_INTERFACE,
                        in_signature="os", out_signature="s")
    def RequestPinCode(self, device, _):
        """Return a default PIN if requested"""
        self.logger.info("Providing default PIN code")
        return "0000"

    @dbus.service.method(AGENT_INTERFACE,
                        in_signature="o", out_signature="u")
    def RequestPasskey(self, device):
        """Return a default passkey if requested"""
        self.logger.info("Providing default passkey")
        return dbus.UInt32(0000)

    @dbus.service.method(AGENT_INTERFACE,
                        in_signature="", out_signature="")
    def Release(self):
        """Release the agent"""
        self.logger.info("Agent released")
        return

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
        
        # Add handler if none exists
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            self.logger.addHandler(handler)

        # Initialize Operations instance
        self.operations = Operations()
        
        # Initialize DBus mainloop
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        self.bus = dbus.SystemBus()
        self.mainloop = GLib.MainLoop()

    def read_config(self) -> List[int]:
        try:
            config_data = self.operations.read_config_file(self.config_file)
            self.logger.debug(f"Read config data: {config_data}")
            
            formatted_settings = {
                "size": config_data['size'],
                "scale": config_data['scale'],
                "gamma": config_data['gamma'],
                "color1": config_data['color1'],
                "color2": config_data['color2']
            }
            
            json_str = json.dumps(formatted_settings)
            self.logger.debug(f"Formatted config JSON: {json_str}")
            
            byte_array = [ord(c) for c in json_str]
            self.logger.debug(f"Converted to byte array length: {len(byte_array)}")
            
            return byte_array
                
        except Exception as e:
            self.logger.error(f"Error reading config: {str(e)}")
            self.logger.exception("Full traceback:")
            return [ord(c) for c in '{"error": "Failed to read config"}']

    def write_config(self, value: list) -> None:
        """Handle configuration updates using Operations class"""
        try:
            self.logger.debug(f"Received config write: {value}")

            # Convert list of bytes to bytes object
            byte_array = bytes(value)

            # Decode the bytes to a UTF-8 string
            json_str = byte_array.decode('utf-8')
            self.logger.debug(f"Decoded config string: {json_str}")

            # Parse the JSON data
            data = json.loads(json_str)
            self.logger.debug(f"Parsed config data: {data}")

            # Use Operations class to update config
            self.operations.update_config_file(
                self.config_file,
                size=data.get('size'),
                scale=data.get('scale'),
                gamma=data.get('gamma'),
                color1=data.get('color1'),
                color2=data.get('color2')
            )

            self.logger.debug("Config written successfully")
            self.update_event.set()

        except Exception as e:
            self.logger.error(f"Config write error: {e}")
            self.logger.exception("Exception occurred while writing config")




    def configure_adapter(self):
        """Configure the Bluetooth adapter"""
        adapters = list(adapter.Adapter.available())
        if not adapters:
            raise RuntimeError("No Bluetooth adapter found")
            
        current_adapter = adapters[0]
        self.logger.info(f"Using adapter: {current_adapter.address}")
        
        # Make adapter discoverable and pairable
        current_adapter.discoverable = True
        current_adapter.pairable = True
        current_adapter.alias = "Penrose Generator"
        
        return current_adapter

    def setup_agent(self):
        """Set up the auto-accept Bluetooth agent"""
        try:
            # Configure adapter first
            self.adapter = self.configure_adapter()
            
            # Create and register agent
            agent = AutoAcceptAgent(self.bus, AGENT_PATH)
            agent_manager = dbus.Interface(
                self.bus.get_object(constants.BLUEZ_SERVICE_NAME, "/org/bluez"),
                AGENT_MANAGER_INTERFACE)
            
            agent_manager.RegisterAgent(AGENT_PATH, "DisplayYesNo")
            agent_manager.RequestDefaultAgent(AGENT_PATH)
            self.logger.info("Bluetooth agent registered for auto-pairing with DisplayYesNo capability")
            
            return agent
            
        except Exception as e:
            self.logger.error(f"Failed to setup Bluetooth agent: {e}")
            raise


    def handle_command(self, value: list, options: dict) -> None:
        try:
            self.logger.debug(f"handle_command called with value: {value} and options: {options}")

            # Convert list of bytes to bytes object
            byte_array = bytes(value)

            # Decode the bytes to a UTF-8 string
            json_str = byte_array.decode('utf-8')
            self.logger.info(f"Decoded command string: {json_str}")

            # Parse the JSON data
            command_data = json.loads(json_str)
            self.logger.info(f"Parsed command data: {command_data}")

            # Set the appropriate event based on the command
            command = command_data.get('command')
            if command == 'toggle_shader':
                self.logger.info("Setting toggle_shader_event")
                self.toggle_shader_event.set()
            elif command == 'randomize_colors':
                self.logger.info("Setting randomize_colors_event")
                self.randomize_colors_event.set()
            elif command == 'shutdown':
                self.logger.info("Setting shutdown_event")
                self.shutdown_event.set()
            else:
                self.logger.warning(f"Unknown command: {command}")

        except Exception as e:
            self.logger.error(f"Command error: {e}")
            self.logger.exception("Exception occurred while handling command")




    def start_server(self):
        """Initialize and start the Bluetooth server"""
        # Setup auto-pairing agent
        self.agent = self.setup_agent()

        initial_config = self.read_config()
        
        # Create peripheral using the configured adapter
        self.peripheral = peripheral.Peripheral(self.adapter.address,
                                             local_name='Penrose Generator',
                                             appearance=0)

        # Add main service
        self.peripheral.add_service(srv_id=1, 
                                  uuid=PENROSE_SERVICE,
                                  primary=True)

        self.peripheral.add_characteristic(
            srv_id=1,
            chr_id=1,
            uuid=CONFIG_CHAR,
            value=initial_config,  # Set initial value
            flags=['read', 'write', 'write-without-response', 'notify'],  # Added notify
            notifying=False,
            read_callback=self.read_config,
            write_callback=self.write_config,
            notify_callback=None,
        )
        
        self.peripheral.add_characteristic(
            srv_id=1,
            chr_id=2,
            uuid=COMMAND_CHAR,
            value=b'',  # Initialize with empty bytes
            flags=['write', 'write-without-response'],
            notifying=False,
            write_callback=self.handle_command,
        )



        self.logger.debug(f"Setting up CONFIG_CHAR with UUID: {CONFIG_CHAR}")
        self.logger.debug(f"Setting up COMMAND_CHAR with UUID: {COMMAND_CHAR}")

        # Start the server
        self.logger.info("Starting Bluetooth server with auto-pairing...")
        self.peripheral.publish()
        
        # Start mainloop for DBus
        threading.Thread(target=self.mainloop.run, daemon=True).start()

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
    server.mainloop.quit()
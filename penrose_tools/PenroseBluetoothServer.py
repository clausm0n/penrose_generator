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
                        in_signature="ouq", out_signature="")
    def RequestConfirmation(self, device, passkey, _):
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

        # Initialize DBus mainloop
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        self.bus = dbus.SystemBus()
        self.mainloop = GLib.MainLoop()

        # Cache for current config
        self._current_config = None

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
            
            agent_manager.RegisterAgent(AGENT_PATH, "NoInputNoOutput")
            agent_manager.RequestDefaultAgent(AGENT_PATH)
            self.logger.info("Bluetooth agent registered for auto-pairing")
            
            return agent
            
        except Exception as e:
            self.logger.error(f"Failed to setup Bluetooth agent: {e}")
            raise

    def read_config(self) -> List[int]:
        """Read current configuration and convert to bytes"""
        try:
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
            
            # Convert to JSON string and then to bytes
            json_str = json.dumps(formatted_settings)
            self.logger.debug(f"Sending config: {json_str}")
            return [ord(c) for c in json_str]  # Convert string to list of bytes
            
        except Exception as e:
            self.logger.error(f"Error reading config: {e}")
            # Return a minimal valid JSON object if there's an error
            return [ord(c) for c in '{"error": "Failed to read config"}']

    def write_config(self, value: List[int]) -> bool:
        """Handle configuration updates from Bluetooth"""
        try:
            # Convert list of integers to bytes and then decode to string
            json_str = bytes(value).decode('utf-8')
            self.logger.debug(f"Received config write: {json_str}")
            
            data = json.loads(json_str)
            config = configparser.ConfigParser()
            
            if not config.has_section('Settings'):
                config.add_section('Settings')
                
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
            self.logger.info("Config written successfully")
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
        # Setup auto-pairing agent
        self.agent = self.setup_agent()
        
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
            value=[],  # Initial empty value
            notifying=False,
            flags=['read', 'write', 'write-without-response', 'proper-read'],  # Added proper-read flag
            read_callback=self.read_config,
            write_callback=self.write_config,
            properties=['read', 'write'],  # Explicit properties
        )

        self.peripheral.add_characteristic(
            srv_id=1,
            chr_id=2,
            uuid=COMMAND_CHAR,
            value=[],
            notifying=False,
            flags=['write', 'write-without-response'],
            write_callback=self.handle_command,
            properties=['write']  # Explicit write-only property
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
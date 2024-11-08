#!/usr/bin/env python3
# penrose_bluetooth_service.py

import dbus
import dbus.exceptions
import dbus.mainloop.glib
import dbus.service
import logging
import json
import configparser
import threading
import sys
import time
from gi.repository import GLib
from bluezero import adapter, peripheral
import os

# Static UUIDs remain the same
CONFIG_SERVICE_UUID = '3b0055b8-37ed-40a5-b17f-f38b9417c8cb'
CONFIG_READ_CHAR_UUID = '3b0055b8-37ed-40a5-b17f-f38b9417c8cc'
CONFIG_WRITE_CHAR_UUID = '3b0055b8-37ed-40a5-b17f-f38b9417c8cd'
COMMAND_SERVICE_UUID = '3b0055b8-37ed-40a5-b17f-f38b9417c8ce'
COMMAND_CHAR_UUID = '3b0055b8-37ed-40a5-b17f-f38b9417c8cf'

# DBus constants for IPC
DBUS_SERVICE_NAME = 'com.penrose.control'
DBUS_OBJECT_PATH = '/com/penrose/control'
DBUS_INTERFACE = 'com.penrose.control.interface'

class PenroseControlService(dbus.service.Object):
    """DBus service for controlling the Penrose generator"""
    
    def __init__(self, bus):
        super().__init__(bus, DBUS_OBJECT_PATH)
        
    @dbus.service.method(DBUS_INTERFACE, in_signature='', out_signature='')
    def UpdateConfig(self):
        """Signal the Penrose generator to update its configuration"""
        os.kill(os.getppid(), signal.SIGUSR1)
        
    @dbus.service.method(DBUS_INTERFACE, in_signature='', out_signature='')
    def ToggleShader(self):
        """Signal the Penrose generator to toggle shader"""
        os.kill(os.getppid(), signal.SIGUSR2)
        
    @dbus.service.method(DBUS_INTERFACE, in_signature='', out_signature='')
    def RandomizeColors(self):
        """Signal the Penrose generator to randomize colors"""
        os.kill(os.getppid(), signal.SIGHUP)
        
    @dbus.service.method(DBUS_INTERFACE, in_signature='', out_signature='')
    def Shutdown(self):
        """Signal the Penrose generator to shutdown"""
        os.kill(os.getppid(), signal.SIGTERM)

class BluetoothServer:
    def __init__(self, config_path):
        # Setup logging
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler("/var/log/penrose-bluetooth.log"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('BluetoothServer')
        
        # Initialize variables
        self.config_path = config_path
        self.peripheral = None
        self.mainloop = None
        
        # Setup DBus
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        self.bus = dbus.SystemBus()
        self.control_service = PenroseControlService(self.bus)
        
    def read_config(self):
        """Read configuration from file"""
        try:
            config = configparser.ConfigParser()
            config.read(self.config_path)
            settings = dict(config['Settings'])
            return {
                "size": int(settings.get('size', 0)),
                "scale": int(settings.get('scale', 0)),
                "gamma": [float(x.strip()) for x in settings.get('gamma', '').split(',')],
                "color1": [int(x.strip()) for x in settings.get('color1', '').replace('(', '').replace(')', '').split(',')],
                "color2": [int(x.strip()) for x in settings.get('color2', '').replace('(', '').replace(')', '').split(',')]
            }
        except Exception as e:
            self.logger.error(f"Error reading config: {e}")
            return {}

    def write_config(self, new_settings):
        """Write configuration to file"""
        try:
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
                
            # Signal the main process to update
            self.control_service.UpdateConfig()
            
        except Exception as e:
            self.logger.error(f"Error writing config: {e}")

    def setup_peripheral(self):
        """Initialize and configure the peripheral device"""
        try:
            # Create peripheral
            self.peripheral = peripheral.Peripheral(
                adapter_addr=None,  # Use default adapter
                local_name='PenroseServer',
                appearance=0
            )
            
            # Add Configuration Service
            self.peripheral.add_service(
                srv_id=1,
                uuid=CONFIG_SERVICE_UUID,
                primary=True
            )
            
            # Add Configuration Read Characteristic
            self.peripheral.add_characteristic(
                srv_id=1,
                chr_id=1,
                uuid=CONFIG_READ_CHAR_UUID,
                value=[],
                notifying=False,
                flags=['read'],
                read_callback=self.read_config_callback,
                write_callback=None
            )
            
            # Add Configuration Write Characteristic
            self.peripheral.add_characteristic(
                srv_id=1,
                chr_id=2,
                uuid=CONFIG_WRITE_CHAR_UUID,
                value=[],
                notifying=False,
                flags=['write'],
                read_callback=None,
                write_callback=self.write_config_callback
            )
            
            # Add Command Service
            self.peripheral.add_service(
                srv_id=2,
                uuid=COMMAND_SERVICE_UUID,
                primary=True
            )
            
            # Add Command Characteristic
            self.peripheral.add_characteristic(
                srv_id=2,
                chr_id=1,
                uuid=COMMAND_CHAR_UUID,
                value=[],
                notifying=False,
                flags=['write'],
                read_callback=None,
                write_callback=self.command_callback
            )
            
            self.logger.info("Peripheral setup completed")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize peripheral: {e}")
            raise

    def read_config_callback(self, options):
        """Callback for configuration read requests"""
        try:
            config = self.read_config()
            return list(json.dumps(config).encode('utf-8'))
        except Exception as e:
            self.logger.error(f"Error in read config callback: {e}")
            return list(json.dumps({'error': str(e)}).encode('utf-8'))

    def write_config_callback(self, value, options):
        """Callback for configuration write requests"""
        try:
            data = json.loads(bytes(value).decode('utf-8'))
            self.write_config(data)
            return True
        except Exception as e:
            self.logger.error(f"Error in write config callback: {e}")
            return False

    def command_callback(self, value, options):
        """Callback for command requests"""
        try:
            command = bytes(value).decode('utf-8').strip()
            self.logger.info(f"Received command: {command}")
            
            if command == 'toggle_shader':
                self.control_service.ToggleShader()
            elif command == 'randomize_colors':
                self.control_service.RandomizeColors()
            elif command == 'shutdown':
                self.control_service.Shutdown()
            else:
                self.logger.warning(f"Unknown command: {command}")
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error in command callback: {e}")
            return False

    def start(self):
        """Start the Bluetooth server"""
        try:
            self.logger.info("Starting Bluetooth server...")
            
            # Setup peripheral
            self.setup_peripheral()
            
            # Start advertising
            self.peripheral.publish()
            
            # Run the main loop
            self.mainloop = GLib.MainLoop()
            self.mainloop.run()
            
        except Exception as e:
            self.logger.error(f"Error starting server: {e}")
            raise
        finally:
            if self.peripheral:
                self.peripheral.unpublish()

def main():
    config_path = "/etc/penrose/config.ini"
    server = BluetoothServer(config_path)
    
    # Handle signals
    def signal_handler(signum, frame):
        server.logger.info("Received signal to terminate")
        if server.mainloop:
            server.mainloop.quit()
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Start the server
    server.start()

if __name__ == "__main__":
    main()
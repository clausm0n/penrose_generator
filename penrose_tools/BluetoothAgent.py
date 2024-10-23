# penrose_tools/BluetoothAgent.py

import dbus
import dbus.exceptions
import dbus.mainloop.glib
import dbus.service
import logging
import sys
from gi.repository import GLib

AGENT_INTERFACE = "org.bluez.Agent1"
AGENT_PATH = "/penrose/tools/bluetooth/agent"
CAPABILITY = "NoInputNoOutput"  # For Just Works pairing

class Rejected(dbus.exceptions.DBusException):
    _dbus_error_name = "org.bluez.Error.Rejected"

class Agent(dbus.service.Object):
    def __init__(self, bus, path, shutdown_callback=None):
        super().__init__(bus, path)
        self.bus = bus
        self.path = path
        self.logger = logging.getLogger('BluetoothAgent')
        self.shutdown_callback = shutdown_callback  # Callback to notify server to shutdown
        self.logger.info("Bluetooth Agent created")

    @dbus.service.method(AGENT_INTERFACE,
                         in_signature="", out_signature="")
    def Release(self):
        self.logger.info("Agent Released")
        if self.shutdown_callback:
            self.shutdown_callback()

    @dbus.service.method(AGENT_INTERFACE, in_signature="o", out_signature="s")
    def RequestPinCode(self, device):
        self.logger.info(f"RequestPinCode: {device}")
        return "000000"

    @dbus.service.method(AGENT_INTERFACE, in_signature="o", out_signature="u")
    def RequestPasskey(self, device):
        self.logger.info(f"RequestPasskey: {device}")
        return dbus.UInt32(000000)

    @dbus.service.method(AGENT_INTERFACE,
                         in_signature="ouq", out_signature="")
    def DisplayPasskey(self, device, passkey, entered):
        self.logger.info(f"DisplayPasskey for device {device}: {passkey}, Entered: {entered}")
        # Optionally, add logic to display the passkey if needed

    @dbus.service.method(AGENT_INTERFACE,
                         in_signature="os", out_signature="")
    def DisplayPinCode(self, device, pincode):
        self.logger.info(f"DisplayPinCode for device {device}: {pincode}")
        # Optionally, add logic to display the pin code if needed

    @dbus.service.method(AGENT_INTERFACE,
                         in_signature="ou", out_signature="")
    def RequestConfirmation(self, device, passkey):
        self.logger.info(f"RequestConfirmation for device {device}: {passkey}")
        # Automatically confirm the passkey
        self.Confirm(device, True)

    @dbus.service.method(AGENT_INTERFACE,
                         in_signature="o", out_signature="")
    def RequestAuthorization(self, device):
        self.logger.info(f"RequestAuthorization for device {device}")
        self.Authorize(device, True)

    @dbus.service.method(AGENT_INTERFACE,
                         in_signature="ou", out_signature="")
    def AuthorizeService(self, device, uuid):
        self.logger.info(f"AuthorizeService for device {device}, UUID: {uuid}")
        self.Authorize(device, True)

    def Confirm(self, device, accept):
        try:
            # device is the object path; retrieve the Address property
            device_obj = self.bus.get_object("org.bluez", device)
            device_props = dbus.Interface(device_obj, "org.freedesktop.DBus.Properties")
            address = device_props.Get("org.bluez.Device1", "Address")
            
            manager = dbus.Interface(
                self.bus.get_object("org.bluez", "/org/bluez"),
                "org.freedesktop.DBus.ObjectManager"
            )
            objects = manager.GetManagedObjects()
            for path, interfaces in objects.items():
                if "org.bluez.Device1" in interfaces:
                    if interfaces["org.bluez.Device1"]["Address"] == address:
                        device_interface = dbus.Interface(device_obj, "org.bluez.Device1")
                        device_interface.Confirm(accept)
                        self.logger.info(f"Confirmed pairing for device {address}")
                        break
        except Exception as e:
            self.logger.error(f"Error in Confirm method: {e}")

    def Authorize(self, device, accept):
        try:
            # device is the object path; retrieve the Address property
            device_obj = self.bus.get_object("org.bluez", device)
            device_props = dbus.Interface(device_obj, "org.freedesktop.DBus.Properties")
            address = device_props.Get("org.bluez.Device1", "Address")
            
            manager = dbus.Interface(
                self.bus.get_object("org.bluez", "/org/bluez"),
                "org.freedesktop.DBus.ObjectManager"
            )
            objects = manager.GetManagedObjects()
            for path, interfaces in objects.items():
                if "org.bluez.Device1" in interfaces:
                    if interfaces["org.bluez.Device1"]["Address"] == address:
                        device_interface = dbus.Interface(device_obj, "org.bluez.Device1")
                        device_interface.Authorize(accept)
                        self.logger.info(f"Authorized device {address}")
                        break
        except Exception as e:
            self.logger.error(f"Error in Authorize method: {e}")

# Remove or comment out the standalone main function
def main():
    """Standalone agent for testing"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("bluetooth_agent.log"),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logger = logging.getLogger('BluetoothAgent')

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    # First, make sure no other agents are registered
    try:
        manager = dbus.Interface(
            bus.get_object("org.bluez", "/org/bluez"),
            "org.bluez.AgentManager1"
        )
        manager.UnregisterAgent(AGENT_PATH)
    except:
        pass  # Ignore if no agent was registered

    # Create and register our agent
    agent = Agent(bus, AGENT_PATH)
    manager = dbus.Interface(
        bus.get_object("org.bluez", "/org/bluez"),
        "org.bluez.AgentManager1"
    )

    manager.RegisterAgent(AGENT_PATH, CAPABILITY)
    logger.info("Bluetooth Agent registered")

    manager.RequestDefaultAgent(AGENT_PATH)
    logger.info("Bluetooth Agent set as default")

    # mainloop = GLib.MainLoop()

    # try:
    #     mainloop.run()
    # except KeyboardInterrupt:
    #     logger.info("Agent stopped by user")
    #     mainloop.quit()
    #     manager.UnregisterAgent(AGENT_PATH)

if __name__ == "__main__":
    main()
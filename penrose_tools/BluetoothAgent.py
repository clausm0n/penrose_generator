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
        manager = dbus.Interface(
            self.bus.get_object("org.bluez", "/org/bluez"),
            "org.freedesktop.DBus.ObjectManager")
        objects = manager.GetManagedObjects()
        for path, interfaces in objects.items():
            if "org.bluez.Device1" in interfaces:
                if interfaces["org.bluez.Device1"]["Address"] == device:
                    device_obj = self.bus.get_object("org.bluez", path)
                    device_interface = dbus.Interface(device_obj, "org.bluez.Device1")
                    device_interface.Confirm(accept)
                    self.logger.info(f"Confirmed pairing for device {device}")
                    break

    def Authorize(self, device, accept):
        manager = dbus.Interface(
            self.bus.get_object("org.bluez", "/org/bluez"),
            "org.freedesktop.DBus.ObjectManager")
        objects = manager.GetManagedObjects()
        for path, interfaces in objects.items():
            if "org.bluez.Device1" in interfaces:
                if interfaces["org.bluez.Device1"]["Address"] == device:
                    device_obj = self.bus.get_object("org.bluez", path)
                    device_interface = dbus.Interface(device_obj, "org.bluez.Device1")
                    device_interface.Authorize(accept)
                    self.logger.info(f"Authorized device {device}")
                    break
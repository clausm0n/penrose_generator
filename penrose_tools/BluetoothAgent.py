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
    def __init__(self, bus, path):
        super().__init__(bus, path)
        self.bus = bus
        self.path = path
        self.logger = logging.getLogger('BluetoothAgent')

    @dbus.service.method(AGENT_INTERFACE, in_signature="", out_signature="")
    def Release(self):
        self.logger.info("Agent Released")

    @dbus.service.method(AGENT_INTERFACE, in_signature="os", out_signature="")
    def AuthorizeService(self, device, uuid):
        self.logger.info(f"AuthorizeService for device {device}, UUID: {uuid}")
        return

    @dbus.service.method(AGENT_INTERFACE, in_signature="o", out_signature="s")
    def RequestPinCode(self, device):
        self.logger.info(f"RequestPinCode for device {device}")
        return "000000"

    @dbus.service.method(AGENT_INTERFACE, in_signature="o", out_signature="u")
    def RequestPasskey(self, device):
        self.logger.info(f"RequestPasskey for device {device}")
        return dbus.UInt32(0)

    @dbus.service.method(AGENT_INTERFACE, in_signature="ouq", out_signature="")
    def DisplayPasskey(self, device, passkey, entered):
        self.logger.info(f"DisplayPasskey for device {device}: {passkey} entered: {entered}")

    @dbus.service.method(AGENT_INTERFACE, in_signature="os", out_signature="")
    def DisplayPinCode(self, device, pincode):
        self.logger.info(f"DisplayPinCode for device {device}: {pincode}")

    @dbus.service.method(AGENT_INTERFACE, in_signature="ou", out_signature="")
    def RequestConfirmation(self, device, passkey):
        self.logger.info(f"RequestConfirmation for device {device}: {passkey}")
        return

    @dbus.service.method(AGENT_INTERFACE, in_signature="o", out_signature="")
    def RequestAuthorization(self, device):
        self.logger.info(f"RequestAuthorization for device {device}")
        return

def setup_agent():
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    agent = Agent(bus, AGENT_PATH)
    obj = bus.get_object("org.bluez", "/org/bluez")
    manager = dbus.Interface(obj, "org.bluez.AgentManager1")
    manager.RegisterAgent(AGENT_PATH, CAPABILITY)
    manager.RequestDefaultAgent(AGENT_PATH)
    return agent

def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("/var/log/bluetooth_agent.log"),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logger = logging.getLogger('BluetoothAgent')

    agent = setup_agent()
    logger.info("Bluetooth Agent registered and set as default")

    mainloop = GLib.MainLoop()
    
    def exit_handler(signum, frame):
        logger.info("Exiting Bluetooth Agent...")
        mainloop.quit()

    import signal
    for sig in [signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGQUIT]:
        GLib.unix_signal_add(GLib.PRIORITY_HIGH, sig, exit_handler, sig)

    try:
        mainloop.run()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        logger.info("Bluetooth Agent terminated")

if __name__ == "__main__":
    main()
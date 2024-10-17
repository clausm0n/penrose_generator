from bluezero import peripheral
from .Operations import Operations
import asyncio

class BluetoothServer:
    def __init__(self, config_path, update_event, toggle_shader_event, randomize_colors_event, shutdown_event):
        self.operations = Operations()
        self.config_path = config_path
        self.update_event = update_event
        self.toggle_shader_event = toggle_shader_event
        self.randomize_colors_event = randomize_colors_event
        self.shutdown_event = shutdown_event

        self.SERVICE_UUID = "12345678-1234-5678-1234-56789abcdef0"
        self.CHARACTERISTIC_UUID = "87654321-1234-5678-1234-56789abcdef0"

        self.peripheral = None

    def handle_read(self):
        return b"Penrose Tiling Generator"

    def handle_write(self, value):
        command = value.decode().strip()
        asyncio.run(self.handle_command(command))

    async def handle_command(self, command):
        if command == "toggle_shader":
            self.toggle_shader_event.set()
        elif command == "randomize_colors":
            self.randomize_colors_event.set()
        elif command.startswith("update_config:"):
            updates = command.split(":")[1].split(",")
            config_data = self.operations.read_config_file(self.config_path)
            for update in updates:
                key, value = update.split("=")
                if key in config_data:
                    if isinstance(config_data[key], list):
                        config_data[key] = [float(x) for x in value.split()]
                    else:
                        config_data[key] = type(config_data[key])(value)
            self.operations.update_config_file(self.config_path, **config_data)
            self.update_event.set()
        elif command == "shutdown":
            self.shutdown_event.set()

    def run(self):
        # Replace 'hci0' with your Bluetooth adapter's MAC address if necessary
        self.peripheral = peripheral.Peripheral(adapter_address='2C:CF:67:02:BB:28', local_name='Penrose Tiling Generator')


        service = peripheral.Service(self.SERVICE_UUID)
        characteristic = peripheral.Characteristic(self.CHARACTERISTIC_UUID,
                                                   ['read', 'write', 'notify'],
                                                   ['read', 'write'],
                                                   self.handle_read,
                                                   self.handle_write)

        service.add_characteristic(characteristic)
        self.peripheral.add_service(service)

        print(f"Bluetooth server started. Service UUID: {self.SERVICE_UUID}")
        self.peripheral.publish()

        try:
            self.shutdown_event.wait()
        except KeyboardInterrupt:
            pass
        finally:
            self.peripheral.stop()
            print("Bluetooth server stopped")

    def run_in_thread(self):
        self.run()

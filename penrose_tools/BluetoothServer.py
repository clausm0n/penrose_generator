import asyncio
from bleak import BleakServer
from bleak.backends.service import BleakGATTServiceCollection
from bleak.backends.characteristic import BleakGATTCharacteristic
from .Operations import Operations

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

    async def handle_read(self, characteristic: BleakGATTCharacteristic, **kwargs):
        return b"Penrose Tiling Generator"

    async def handle_write(self, characteristic: BleakGATTCharacteristic, value: bytearray, **kwargs):
        command = value.decode().strip()
        await self.handle_command(command)

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

    async def run(self):
        services = BleakGATTServiceCollection()
        service = services.add_service(self.SERVICE_UUID)
        char = service.add_characteristic(
            self.CHARACTERISTIC_UUID,
            read=True,
            write=True,
            notify=True,
            properties=["read", "write", "notify"]
        )
        char.set_value(b"Penrose Tiling Generator")

        server = BleakServer(services)
        server.read_request_func = self.handle_read
        server.write_request_func = self.handle_write

        await server.start()
        print(f"Bluetooth server started. Service UUID: {self.SERVICE_UUID}")
        await self.shutdown_event.wait()
        await server.stop()
        print("Bluetooth server stopped")

    def run_in_thread(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.run())
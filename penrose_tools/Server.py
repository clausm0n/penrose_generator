import http.server
import signal
import socketserver
import json
import configparser
import threading
from penrose_tools.Operations import Operations

PORT = 8080
CONFIG_FILE = 'config.ini'

# Events for toggling various features
update_event = threading.Event()
toggle_shader_event = threading.Event()
toggle_regions_event = threading.Event()
toggle_gui_event = threading.Event()
shutdown_event = threading.Event()  # Shutdown event
randomize_colors_event = threading.Event()

class APIRequestHandler(http.server.BaseHTTPRequestHandler):
    operations = Operations()

    def do_OPTIONS(self):
        self.send_response(204)  # No Content
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE)
        settings = dict(config['Settings'])
        self.wfile.write(json.dumps(settings).encode('utf-8'))

    def do_POST(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode())
        response = {'status': 'error', 'message': 'Invalid command'}

        try:
            if 'command' in data:
                self.handle_commands(data, response)
            else:
                config = configparser.ConfigParser()
                config.read(CONFIG_FILE)
                for key, value in data.items():
                    config.set('Settings', key, ', '.join(map(str, value)) if isinstance(value, list) else str(value))
                with open(CONFIG_FILE, 'w') as configfile:
                    config.write(configfile)
                response = {'status': 'success', 'message': 'Configuration updated'}
                update_event.set()
        except Exception as e:
            response = {'status': 'error', 'message': str(e)}
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
        self.wfile.write(json.dumps(response).encode('utf-8'))

    def handle_commands(self, data, response):
        command = data['command']
        if command == 'toggle_shader':
            toggle_shader_event.set()
            response.update({'status': 'success', 'message': 'Shader toggled'})
        elif command == 'shutdown':  # Shutdown command
            shutdown_event.set()  # Set the shutdown event
            response.update({'status': 'success', 'message': 'Server is shutting down'})
        elif command == 'randomize_colors':
            randomize_colors_event.set()
            response.update({'status': 'success', 'message': 'Colors randomized'})


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """Handle requests in a separate thread."""
    pass

def run_server():
    def signal_handler(sig, frame):
        print('Shutting down server...')
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    with ThreadedTCPServer(("", PORT), APIRequestHandler) as server:
        print(f"Serving API at port {PORT}")
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()

        # Wait for the shutdown event
        try:
            shutdown_event.wait()
        except KeyboardInterrupt:
            print('Keyboard interrupt received, exiting.')
        finally:
            server.shutdown()
            server.server_close()

    print('Server shut down successfully.')

if __name__ == '__main__':
    run_server()

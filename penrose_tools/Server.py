import http.server
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
                updated = self.operations.update_config_file(CONFIG_FILE, **data)
                update_event.set()
            else:
                updated = self.operations.update_config_file(CONFIG_FILE, **data)
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
        elif command == 'toggle_regions':
            toggle_regions_event.set()
            response.update({'status': 'success', 'message': 'Regions toggled'})
        elif command == 'toggle_gui':
            toggle_gui_event.set()
            response.update({'status': 'success', 'message': 'GUI toggled'})
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
    with ThreadedTCPServer(("", PORT), APIRequestHandler) as server:
        print(f"Serving API at port {PORT}")
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        shutdown_event.wait()
        server.shutdown()
        server.server_close()

if __name__ == '__main__':
    run_server()

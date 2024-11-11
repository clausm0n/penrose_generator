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
from .events import update_event, toggle_shader_event, randomize_colors_event, shutdown_event

class APIRequestHandler(http.server.BaseHTTPRequestHandler):
    operations = Operations()

    def set_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        self.send_response(204)  # No Content
        self.set_cors_headers()
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.set_cors_headers()
        self.end_headers()
        
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE)
        settings = dict(config['Settings'])
        formatted_settings = {
            "size": int(settings.get('size', 0)),
            "scale": int(settings.get('scale', 0)),
            "gamma": [float(x.strip()) for x in settings.get('gamma', '').split(',')],
            "color1": [int(x.strip()) for x in settings.get('color1', '').replace('(', '').replace(')', '').split(',')],
            "color2": [int(x.strip()) for x in settings.get('color2', '').replace('(', '').replace(')', '').split(',')]
        }
        self.wfile.write(json.dumps(formatted_settings).encode('utf-8'))

    def do_POST(self):
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
                    if isinstance(value, list):
                        if key in ['color1', 'color2']:
                            config.set('Settings', key, f"({', '.join(map(str, value))})")
                        else:
                            config.set('Settings', key, ', '.join(map(str, value)))
                    else:
                        config.set('Settings', key, str(value))
                with open(CONFIG_FILE, 'w') as configfile:
                    config.write(configfile)
                response = {'status': 'success', 'message': 'Configuration updated'}
                update_event.set()
            self.send_response(200)
        except Exception as e:
            response = {'status': 'error', 'message': str(e)}
            self.send_response(500)
        
        self.send_header('Content-type', 'application/json')
        self.set_cors_headers()
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
    with ThreadedTCPServer(("", PORT), APIRequestHandler) as server:
        print(f"Serving API at port {PORT}")
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()

        # Wait for the shutdown event
        shutdown_event.wait()
        server.shutdown()
        server.server_close()
        print('Server shut down successfully.')


if __name__ == '__main__':
    run_server()

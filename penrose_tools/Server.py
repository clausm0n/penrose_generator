import http.server
import socketserver
import json
import configparser
from penrose_tools.Operations import Operations
from threading import Event

PORT = 8080
CONFIG_FILE = 'config.ini'

update_event = Event()
toggle_shader_event = Event()
toggle_regions_event = Event()
toggle_gui_event = Event()

class APIRequestHandler(http.server.BaseHTTPRequestHandler):
    operations = Operations()

    def do_GET(self):
        # Handling CORS
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        # Read configuration and send it back as JSON
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE)
        settings = dict(config['Settings'])
        self.wfile.write(json.dumps(settings).encode('utf-8'))

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode())

        response = {'status': 'error', 'message': 'Invalid command'}
        try:
            if 'command' in data:  # Handle specific commands
                self.handle_commands(data, response)
            else:  # Assume remaining data is for configuration update
                updated = self.operations.update_config_file(CONFIG_FILE, **data)
                response = {'status': 'success', 'message': 'Configuration updated successfully'}
                update_event.set()
                self.send_response(200)
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
            response.update({'status': 'success', 'message': 'Regions display toggled'})
        elif command == 'toggle_gui':
            toggle_gui_event.set()
            response.update({'status': 'success', 'message': 'GUI visibility toggled'})
        self.send_response(200)


def run_server():
    with socketserver.TCPServer(("", PORT), APIRequestHandler) as httpd:
        print(f"Serving API at port {PORT}")
        httpd.serve_forever()

if __name__ == '__main__':
    run_server()

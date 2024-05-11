import http.server
import socketserver
import json
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

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode())

        response = {'status': 'error', 'message': 'Invalid command'}

        # Check if the POST data contains configuration update parameters
        if all(key in data for key in ['height', 'width', 'scale', 'size', 'gamma', 'color1', 'color2']):
            try:
                self.operations.update_config_file(CONFIG_FILE, **data)
                response = {'status': 'success', 'message': 'Configuration updated successfully'}
                update_event.set()
            except Exception as e:
                response = {'status': 'error', 'message': str(e)}
                self.send_response(500)
            else:
                self.send_response(200)
        # Check for specific commands and handle them
        elif 'command' in data:
            try:
                if data['command'] == 'toggle_shader':
                    toggle_shader_event.set()
                    response = {'status': 'success', 'message': 'Shader toggled'}
                elif data['command'] == 'toggle_regions':
                    toggle_regions_event.set()
                    response = {'status': 'success', 'message': 'Regions display toggled'}
                elif data['command'] == 'toggle_gui':
                    toggle_gui_event.set()
                    response = {'status': 'success', 'message': 'GUI visibility toggled'}
            except Exception as e:
                response = {'status': 'error', 'message': str(e)}
                self.send_response(500)
            else:
                self.send_response(200)
        else:
            self.send_response(400)  # Bad Request if neither configuration update nor command provided

        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode('utf-8'))

def run_server():
    with socketserver.TCPServer(("", PORT), APIRequestHandler) as httpd:
        print(f"Serving API at port {PORT}")
        httpd.serve_forever()

if __name__ == '__main__':
    run_server()

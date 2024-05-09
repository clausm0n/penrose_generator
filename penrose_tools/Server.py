import http.server
import socketserver
import json
from penrose_tools.Operations import Operations
from threading import Event

PORT = 8080
CONFIG_FILE = 'config.ini'

update_event = Event()

class APIRequestHandler(http.server.BaseHTTPRequestHandler):
    operations = Operations()

    def do_GET(self):
        # Fetch and send the current configuration settings as JSON
        config_data = self.operations.read_config_file(CONFIG_FILE)
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(config_data).encode('utf-8'))

    def do_POST(self):
        # Read JSON data sent by the client
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode())

        # Use the existing Operations method to update the config file
        try:
            self.operations.update_config_file(CONFIG_FILE, **data)
            response = {'status': 'success', 'message': 'Configuration updated successfully'}
            update_event.set()
            self.send_response(200)  # OK status
        except Exception as e:
            response = {'status': 'error', 'message': str(e)}
            self.send_response(500)  # Internal Server Error status

        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode('utf-8'))

def run_server():
    with socketserver.TCPServer(("", PORT), APIRequestHandler) as httpd:
        print(f"Serving API at port {PORT}")
        httpd.serve_forever()

if __name__ == '__main__':
    run_server()

import http.server
import socketserver
import os
import urllib.request
import urllib.parse
import json

PORT = 5000
DIRECTORY = "frontend"
BACKEND_URL = "http://localhost:8000"

class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)
    
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()
    
    def do_GET(self):
        # Proxy API requests to backend
        if self.path.startswith('/api/'):
            self.proxy_to_backend()
        else:
            # Serve static files
            super().do_GET()
    
    def proxy_to_backend(self):
        """Proxy API requests to the backend server"""
        try:
            # Construct backend URL
            backend_url = f"{BACKEND_URL}{self.path}"
            
            # Forward the request to backend
            req = urllib.request.Request(backend_url)
            with urllib.request.urlopen(req, timeout=30) as response:
                # Read response
                data = response.read()
                
                # Send response to client
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(data)
                
        except Exception as e:
            # Send error response
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            error_response = json.dumps({"error": f"Backend connection failed: {str(e)}"})
            self.wfile.write(error_response.encode())
            print(f"❌ Proxy error: {e}")

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    with socketserver.TCPServer(("0.0.0.0", PORT), MyHTTPRequestHandler) as httpd:
        print(f"Frontend server running at http://0.0.0.0:{PORT}")
        print(f"Serving files from: {os.path.abspath(DIRECTORY)}")
        print(f"Proxying /api/* requests to: {BACKEND_URL}")
        httpd.serve_forever()

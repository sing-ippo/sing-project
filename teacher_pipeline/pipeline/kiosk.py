import http.server
import socketserver
import os

PORT = 3000
os.chdir(os.path.dirname(os.path.abspath(__file__)))

with socketserver.TCPServer(("", PORT), http.server.SimpleHTTPRequestHandler) as httpd:
    print(f"Открой в браузере: http://localhost:{PORT}/kiosk.html")
    httpd.serve_forever()

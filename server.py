import http.server, ssl, os, re

os.chdir(os.path.dirname(os.path.abspath(__file__)))

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # Strip Google image size suffixes like =s120 =s300 =s1600
        self.path = re.sub(r'(\.(?:jpg|jpeg|png|gif|webp|svg))=s\d+', r'\1', self.path)
        # Strip leading slash from paths that have no extension and add .html
        import urllib.parse
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path not in ('/', '') and '.' not in os.path.basename(path):
            self.path = path + '.html' + (('?' + parsed.query) if parsed.query else '')
        super().do_GET()

    def log_message(self, format, *args):
        pass  # silence log spam

server = http.server.HTTPServer(('127.0.0.1', 4443), Handler)
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.load_cert_chain('cert.pem', 'key.pem')
server.socket = ctx.wrap_socket(server.socket, server_side=True)
print("Running at https://127.0.0.1:4443")
server.serve_forever()

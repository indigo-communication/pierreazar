import http.server, ssl, os, re, json, smtplib, urllib.parse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

os.chdir(os.path.dirname(os.path.abspath(__file__)))

import mail_config as cfg

def send_email(name, sender_email, message):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Website Contact: {name}"
    msg["From"]    = f"{cfg.SENDER_NAME} <{cfg.SMTP_USER}>"
    msg["To"]      = cfg.RECIPIENT_EMAIL
    msg["Reply-To"] = sender_email

    body_text = f"Name: {name}\nEmail: {sender_email}\n\nMessage:\n{message}"
    body_html = f"""<html><body style="font-family:Arial,sans-serif;color:#222;">
<p><strong>Name:</strong> {name}<br>
<strong>Email:</strong> <a href="mailto:{sender_email}">{sender_email}</a></p>
<p><strong>Message:</strong><br>{message.replace(chr(10),'<br>')}</p>
</body></html>"""

    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    with smtplib.SMTP(cfg.SMTP_HOST, cfg.SMTP_PORT) as s:
        s.ehlo()
        s.starttls()
        s.login(cfg.SMTP_USER, cfg.SMTP_PASS)
        s.sendmail(cfg.SMTP_USER, cfg.RECIPIENT_EMAIL, msg.as_string())

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # Strip Google image size suffixes like =s120 =s300 =s1600
        self.path = re.sub(r'(\.(?:jpg|jpeg|png|gif|webp|svg))=s\d+', r'\1', self.path)
        # Strip leading slash from paths that have no extension and add .html
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path not in ('/', '') and '.' not in os.path.basename(path):
            self.path = path + '.html' + (('?' + parsed.query) if parsed.query else '')
        super().do_GET()

    def do_POST(self):
        if self.path != '/send-message':
            self.send_response(404); self.end_headers()
            return
        length = int(self.headers.get('Content-Length', 0))
        body   = self.rfile.read(length)
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        try:
            data = json.loads(body)
            name    = str(data.get('name', '')).strip()[:200]
            email   = str(data.get('email', '')).strip()[:200]
            message = str(data.get('message', '')).strip()[:5000]
            if not name or not email or not message:
                raise ValueError("Missing fields")
            if not cfg.SMTP_USER or not cfg.SMTP_PASS:
                raise ValueError("SMTP not configured — fill in mail_config.py")
            send_email(name, email, message)
            self.wfile.write(json.dumps({"ok": True}).encode())
        except Exception as e:
            self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode())

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def log_message(self, format, *args):
        pass  # silence log spam

server = http.server.HTTPServer(('127.0.0.1', 4443), Handler)
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.load_cert_chain('cert.pem', 'key.pem')
server.socket = ctx.wrap_socket(server.socket, server_side=True)
print("Running at https://127.0.0.1:4443")
server.serve_forever()

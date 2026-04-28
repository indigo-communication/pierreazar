import http.server, ssl, os, re, json, smtplib, urllib.parse, hashlib, secrets, io, hmac, base64
import urllib.request
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

os.chdir(os.path.dirname(os.path.abspath(__file__)))

import mail_config as cfg
import content_manager as cm

# ── Data store ──────────────────────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

SUBMISSIONS_FILE    = os.path.join(DATA_DIR, 'submissions.json')
SALES_FILE          = os.path.join(DATA_DIR, 'sales.json')
PAYMENT_CONFIG_FILE = os.path.join(DATA_DIR, 'payment_config.json')
ORDERS_FILE         = os.path.join(DATA_DIR, 'orders.json')
COURSE_TOKENS_FILE  = os.path.join(DATA_DIR, 'course_tokens.json')

# ── Course access: max distinct IPs before token is locked ──────────────────
COURSE_MAX_IPS = 3

def _read_json(path):
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def _write_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ── Payment config helpers ───────────────────────────────────────────────────
_DEFAULT_PAYMENT_CONFIG = {
    'enabled':      False,
    'merchant_id':  '',
    'api_key':      '',
    'secret_key':   '',
    'gateway_url':  'https://gateway.areeba.com',
    'currency':     'USD',
    'course_price': 99.00,
    'course_name':  'Cinematography Course',
    'return_base_url': 'https://pierreazar.com',
}

def get_payment_config():
    if not os.path.exists(PAYMENT_CONFIG_FILE):
        return dict(_DEFAULT_PAYMENT_CONFIG)
    with open(PAYMENT_CONFIG_FILE, 'r', encoding='utf-8') as f:
        cfg_data = json.load(f)
    merged = dict(_DEFAULT_PAYMENT_CONFIG)
    merged.update(cfg_data)
    return merged

def save_payment_config(data):
    allowed = set(_DEFAULT_PAYMENT_CONFIG.keys())
    clean = {k: v for k, v in data.items() if k in allowed}
    # Validate types
    if 'course_price' in clean:
        clean['course_price'] = float(clean['course_price'])
    if 'enabled' in clean:
        clean['enabled'] = bool(clean['enabled'])
    with open(PAYMENT_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(clean, f, indent=2, ensure_ascii=False)

def _masked_config(cfg_data):
    """Return config with secret fields masked for display."""
    out = dict(cfg_data)
    for field in ('api_key', 'secret_key'):
        val = out.get(field, '')
        out[field] = val[:4] + '****' if len(val) > 4 else ('****' if val else '')
    return out

# ── Areeba / MPGS hosted checkout ────────────────────────────────────────────
def _areeba_create_session(cfg_data, order_id, amount, name, email):
    """
    Call the Areeba (MPGS) REST API to create a hosted checkout session.
    Returns (session_id, checkout_url) or raises an exception on failure.
    """
    merchant_id = cfg_data['merchant_id']
    api_key     = cfg_data['api_key']
    gateway_url = cfg_data['gateway_url'].rstrip('/')
    currency    = cfg_data.get('currency', 'USD')
    return_url  = cfg_data.get('return_base_url', 'https://pierreazar.com').rstrip('/') + '/payment-return'

    # Basic auth: username = "merchant.<merchantId>", password = api_key
    auth_str  = f"merchant.{merchant_id}:{api_key}"
    auth_b64  = base64.b64encode(auth_str.encode()).decode()

    # MPGS session creation endpoint
    api_url = f"{gateway_url}/api/rest/version/68/merchant/{merchant_id}/session"

    payload = {
        "apiOperation": "INITIATE_CHECKOUT",
        "order": {
            "id":          order_id,
            "amount":      f"{amount:.2f}",
            "currency":    currency,
            "description": cfg_data.get('course_name', 'Cinematography Course'),
        },
        "interaction": {
            "operation": "PURCHASE",
            "returnUrl": return_url,
            "merchant":  {"name": "Pierre Azar"},
        },
        "customer": {
            "email":     email,
            "firstName": name.split()[0] if name else '',
            "lastName":  name.split()[-1] if len(name.split()) > 1 else '',
        },
    }

    req = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode(),
        headers={
            'Authorization': f'Basic {auth_b64}',
            'Content-Type':  'application/json',
        },
        method='POST',
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode())

    if result.get('result') not in ('SUCCESS', 'PENDING'):
        raise ValueError(result.get('error', {}).get('explanation', 'Gateway error'))

    session_id = result['session']['id']
    success_indicator = result.get('successIndicator', '')

    checkout_url = (
        f"{gateway_url}/checkout/version/68/pay?"
        f"sessionId={urllib.parse.quote(session_id)}"
    )
    return session_id, success_indicator, checkout_url

def _areeba_verify_signature(cfg_data, params):
    """
    Verify an HMAC-SHA256 signature on the payment return params.
    Areeba signs: secret_key + sorted query params (excluding 'signature').
    """
    secret   = cfg_data.get('secret_key', '')
    received = params.get('signature', '')
    to_sign  = ''.join(v for k, v in sorted(params.items()) if k != 'signature')
    expected = hmac.new(secret.encode(), to_sign.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received)

# ── Session store (in-memory; resets on server restart) ─────────────────────
_sessions = {}   # token -> username

def _check_session(cookie_header):
    """Return True if the request carries a valid admin session cookie."""
    if not cookie_header:
        return False
    for part in cookie_header.split(';'):
        part = part.strip()
        if part.startswith('pa_admin='):
            token = part[len('pa_admin='):]
            return token in _sessions
    return False

# ── Course access token helpers ──────────────────────────────────────────────

def _generate_course_token(email, order_id):
    """Create a new course access token, persist it, and return the token string."""
    token = secrets.token_urlsafe(40)
    tokens = _read_json(COURSE_TOKENS_FILE)
    tokens.append({
        'token':      token,
        'email':      email,
        'order_id':   order_id,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'ips':        [],          # list of distinct IPs that have used this token
        'locked':     False,       # True once max IPs exceeded
        'access_count': 0,
    })
    _write_json(COURSE_TOKENS_FILE, tokens)
    return token

def _validate_course_token(token, client_ip):
    """
    Validate a course access token.
    Returns (True, entry) on success, (False, reason_str) on failure.
    Updates IP list and locks the token if COURSE_MAX_IPS is exceeded.
    """
    tokens = _read_json(COURSE_TOKENS_FILE)
    entry  = next((t for t in tokens if t.get('token') == token), None)
    if not entry:
        return False, 'invalid'
    if entry.get('locked'):
        return False, 'locked'
    # Update IP tracking
    ips = entry.setdefault('ips', [])
    if client_ip and client_ip not in ips:
        ips.append(client_ip)
    entry['access_count'] = entry.get('access_count', 0) + 1
    if len(ips) > COURSE_MAX_IPS:
        entry['locked'] = True
        _write_json(COURSE_TOKENS_FILE, tokens)
        return False, 'locked'
    _write_json(COURSE_TOKENS_FILE, tokens)
    return True, entry

def _send_course_access_email(name, email, token, base_url):
    """Send the course access link to the buyer."""
    link = f"{base_url.rstrip('/')}/course?token={token}"
    subject = "Your Cinematography Course Access"
    body_text = (
        f"Hi {name},\n\n"
        f"Thank you for your purchase! Here is your personal access link:\n\n"
        f"{link}\n\n"
        f"IMPORTANT: This link is personal and non-transferable.\n"
        f"It can only be used from up to {COURSE_MAX_IPS} different devices.\n"
        f"Do not share it — sharing will lock your access.\n\n"
        f"Pierre Azar"
    )
    body_html = (
        '<html><body style="font-family:Arial,sans-serif;color:#222;max-width:600px;">'
        f'<p>Hi {name},</p>'
        f'<p>Thank you for your purchase! Here is your personal access link:</p>'
        f'<p><a href="{link}" style="background:#222;color:#fff;padding:12px 24px;'
        f'text-decoration:none;border-radius:4px;display:inline-block;">Access Your Course</a></p>'
        f'<p style="color:#888;font-size:13px;">Or copy this link: {link}</p>'
        f'<hr style="border:none;border-top:1px solid #eee;">'
        f'<p style="color:#c00;font-size:13px;"><strong>Important:</strong> This link is personal '
        f'and non-transferable. It can only be used from up to {COURSE_MAX_IPS} different devices. '
        f'Do not share it — sharing will lock your access.</p>'
        f'<p>Pierre Azar</p>'
        '</body></html>'
    )
    msg = MIMEMultipart("alternative")
    msg["Subject"]  = subject
    msg["From"]     = f"Pierre Azar <{cfg.SMTP_USER}>"
    msg["To"]       = email
    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))
    with smtplib.SMTP(cfg.SMTP_HOST, cfg.SMTP_PORT) as s:
        s.ehlo()
        s.starttls()
        s.login(cfg.SMTP_USER, cfg.SMTP_PASS)
        s.sendmail(cfg.SMTP_USER, email, msg.as_string())

# ── Email sender ─────────────────────────────────────────────────────────────
def send_email(name, sender_email, message):
    msg = MIMEMultipart("alternative")
    msg["Subject"]  = f"Website Contact: {name}"
    msg["From"]     = f"{cfg.SENDER_NAME} <{cfg.SMTP_USER}>"
    msg["To"]       = cfg.RECIPIENT_EMAIL
    msg["Reply-To"] = sender_email

    body_text = f"Name: {name}\nEmail: {sender_email}\n\nMessage:\n{message}"
    body_html = (
        '<html><body style="font-family:Arial,sans-serif;color:#222;">'
        f'<p><strong>Name:</strong> {name}<br>'
        f'<strong>Email:</strong> <a href="mailto:{sender_email}">{sender_email}</a></p>'
        f'<p><strong>Message:</strong><br>{message.replace(chr(10), "<br>")}</p>'
        '</body></html>'
    )

    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    with smtplib.SMTP(cfg.SMTP_HOST, cfg.SMTP_PORT) as s:
        s.ehlo()
        s.starttls()
        s.login(cfg.SMTP_USER, cfg.SMTP_PASS)
        s.sendmail(cfg.SMTP_USER, cfg.RECIPIENT_EMAIL, msg.as_string())


# ── Request Handler ──────────────────────────────────────────────────────────
class Handler(http.server.SimpleHTTPRequestHandler):

    # ---- helpers ----

    def _json_response(self, data, status=200, extra_headers=None):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        return self.rfile.read(length)

    def _require_auth(self):
        """Returns True if authenticated. Sends 401 and returns False otherwise."""
        if _check_session(self.headers.get('Cookie', '')):
            return True
        self._json_response({'ok': False, 'error': 'Unauthorized'}, status=401)
        return False

    def _serve_course_error(self, message, locked=False):
        """Serve a friendly guide page when course access is not available."""
        if locked:
            note = (
                '<div class="alert alert-warn">'
                '<strong>Too many devices detected.</strong> Your personal link has been locked '
                'for security. Please email <a href="mailto:pierre@pierreazar.com">pierre@pierreazar.com</a> '
                'and we will reset your access within 24 hours.'
                '</div>'
            )
            cta_label = 'Contact Pierre'
            cta_href  = 'mailto:pierre@pierreazar.com'
        else:
            note = (
                '<div class="alert alert-info">'
                + message +
                '</div>'
            )
            cta_label = 'Get Access — Enroll Now'
            cta_href  = '/cinematography-course.html'
        html = (
            '<!DOCTYPE html><html lang="en"><head>'
            '<meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta name="robots" content="noindex,nofollow">'
            '<title>Course Access — Pierre Azar</title>'
            '<style>'
            '*{box-sizing:border-box;margin:0;padding:0;}'
            'body{font-family:Arial,sans-serif;background:#0d0d0d;color:#f0f0f0;'
            'min-height:100vh;display:flex;flex-direction:column;}'
            'header{display:flex;align-items:center;justify-content:space-between;'
            'padding:18px 5%;border-bottom:1px solid #1e1e1e;}'
            '.logo{font-size:13px;font-weight:700;letter-spacing:.12em;color:#fff;}'
            '.logo span{font-size:18px;letter-spacing:.15em;}'
            'main{flex:1;display:flex;align-items:center;justify-content:center;padding:40px 5%;}'
            '.box{max-width:520px;width:100%;}'
            'h1{font-size:clamp(20px,4vw,30px);font-weight:700;letter-spacing:.06em;margin-bottom:8px;}'
            'p.sub{color:#777;font-size:14px;line-height:1.7;margin-bottom:28px;}'
            '.alert-info{background:#111a26;border:1px solid #1e3a5f;border-radius:6px;'
            'padding:14px 18px;font-size:14px;color:#7eb8f7;line-height:1.6;margin-bottom:28px;}'
            '.alert-warn{background:#1a1210;border:1px solid #4a2c1a;border-radius:6px;'
            'padding:14px 18px;font-size:14px;color:#c87941;line-height:1.6;margin-bottom:28px;}'
            '.alert-info a,.alert-warn a{color:inherit;font-weight:700;}'
            '.steps{list-style:none;margin-bottom:32px;}'
            '.steps li{display:flex;gap:14px;align-items:flex-start;'
            'padding:14px 0;border-bottom:1px solid #1a1a1a;}'
            '.steps li:last-child{border-bottom:none;}'
            '.step-num{min-width:28px;height:28px;border-radius:50%;background:#1a1a1a;'
            'border:1px solid #333;display:flex;align-items:center;justify-content:center;'
            'font-size:12px;font-weight:700;color:#888;flex-shrink:0;}'
            '.step-text strong{display:block;font-size:14px;margin-bottom:3px;}'
            '.step-text span{font-size:13px;color:#777;}'
            '.cta{display:block;text-align:center;background:#fff;color:#000;'
            'font-weight:700;font-size:15px;padding:14px 28px;border-radius:5px;'
            'text-decoration:none;letter-spacing:.04em;margin-bottom:20px;'
            'transition:opacity .2s;}'
            '.cta:hover{opacity:.85;}'
            '.back{display:block;text-align:center;color:#555;font-size:13px;'
            'text-decoration:none;border-bottom:1px solid #333;'
            'padding-bottom:2px;width:fit-content;margin:0 auto;}'
            '.back:hover{color:#999;border-color:#666;}'
            'footer{text-align:center;padding:20px;font-size:12px;color:#444;'
            'border-top:1px solid #1a1a1a;}'
            '</style></head><body>'
            '<header><div class="logo">PA <span>PIERRE AZAR</span></div></header>'
            '<main><div class="box">'
            '<h1>Cinematography Course</h1>'
            '<p class="sub">This is a paid course. To watch the videos you need a personal access link, '
            'which is sent to your email after purchase.</p>'
            + note +
            '<ul class="steps">'
            '<li><div class="step-num">1</div><div class="step-text">'
            '<strong>Go to the course page</strong>'
            '<span>Read about what you will learn and the course syllabus.</span></div></li>'
            '<li><div class="step-num">2</div><div class="step-text">'
            '<strong>Click &ldquo;Buy Now&rdquo; and complete payment</strong>'
            '<span>Secure checkout powered by Areeba — credit &amp; debit cards accepted.</span></div></li>'
            '<li><div class="step-num">3</div><div class="step-text">'
            '<strong>Check your email for your personal access link</strong>'
            '<span>Your unique link arrives instantly after payment. Bookmark it to watch anytime.</span></div></li>'
            '</ul>'
            f'<a href="{cta_href}" class="cta">{cta_label}</a>'
            '<a href="/" class="back">&#8592; Back to pierreazar.com</a>'
            '</div></main>'
            '<footer>Questions? <a href="mailto:pierre@pierreazar.com" '
            'style="color:#555;">pierre@pierreazar.com</a></footer>'
            '</body></html>'
        ).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(html)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(html)

    # ---- GET ----

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path

        if path == '/api/submissions':
            if not self._require_auth():
                return
            self._json_response({'submissions': _read_json(SUBMISSIONS_FILE)})
            return

        if path == '/api/sales':
            if not self._require_auth():
                return
            self._json_response({'sales': _read_json(SALES_FILE)})
            return

        if path == '/api/content':
            if not self._require_auth():
                return
            try:
                self._json_response({'ok': True, 'content': cm.get_all()})
            except Exception as e:
                self._json_response({'ok': False, 'error': str(e)}, status=500)
            return

        if path == '/api/images':
            if not self._require_auth():
                return
            self._json_response({'ok': True, 'images': cm.list_images()})
            return

        if path == '/api/payment-config':
            if not self._require_auth():
                return
            self._json_response({'ok': True, 'config': _masked_config(get_payment_config())})
            return

        # ---- Payment return callback (from Areeba) ----
        if path == '/payment-return':
            qs      = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
            order_id = qs.get('order_id', '')
            result   = qs.get('resultIndicator', qs.get('result', ''))

            # Load the pending order
            orders = _read_json(ORDERS_FILE)
            order  = next((o for o in orders if o.get('order_id') == order_id), None)

            cfg_data = get_payment_config()
            success  = False

            if order and result:
                # Accept if resultIndicator matches successIndicator stored at session creation
                success = (result == order.get('success_indicator', '')) or (result.lower() == 'success')

            if success and order and order.get('status') != 'paid':
                # Record the sale
                sales = _read_json(SALES_FILE)
                sales.append({
                    'date':     datetime.now(timezone.utc).isoformat(),
                    'name':     order.get('name', ''),
                    'email':    order.get('email', ''),
                    'course':   cfg_data.get('course_name', 'Cinematography Course'),
                    'amount':   order.get('amount', cfg_data.get('course_price', 99)),
                    'status':   'paid',
                    'order_id': order_id,
                    'gateway':  'areeba',
                })
                _write_json(SALES_FILE, sales)
                # Mark order as paid
                for o in orders:
                    if o.get('order_id') == order_id:
                        o['status'] = 'paid'
                _write_json(ORDERS_FILE, orders)
                # Generate course access token and email it to the buyer
                course_token = _generate_course_token(order.get('email', ''), order_id)
                base_url = cfg_data.get('return_base_url', 'https://pierreazar.com')
                try:
                    _send_course_access_email(order.get('name', ''), order.get('email', ''), course_token, base_url)
                except Exception:
                    pass  # Don't block redirect if email fails
                # Redirect to success page with token so buyer can bookmark it immediately
                self.send_response(302)
                self.send_header('Location', f'/payment-success.html?token={course_token}')
                self.end_headers()
            else:
                self.send_response(302)
                self.send_header('Location', '/payment-failed.html')
                self.end_headers()
            return

        # ---- Course access (token-gated) ----
        if path == '/course':
            qs    = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
            token = qs.get('token', '').strip()
            # Get real client IP (behind Apache proxy)
            client_ip = (
                self.headers.get('X-Forwarded-For', '').split(',')[0].strip()
                or self.headers.get('X-Real-IP', '')
                or self.client_address[0]
            )
            if not token:
                self._serve_course_error('It looks like you followed a direct link without a valid token. Please use the personal link from your purchase confirmation email.')
                return
            ok, result = _validate_course_token(token, client_ip)
            if not ok:
                if result == 'locked':
                    self._serve_course_error('', locked=True)
                else:
                    self._serve_course_error('This link is invalid or has expired. If you already purchased the course, please check your email for the correct link.')
                return
            # Serve the gated course player HTML
            course_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'course-player.html')
            try:
                with open(course_file, 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(content)))
                self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
                self.send_header('X-Robots-Tag', 'noindex, nofollow')
                self.end_headers()
                self.wfile.write(content)
            except FileNotFoundError:
                self.send_response(503)
                self.end_headers()
            return

        if path == '/api/admin/course-tokens':
            if not self._require_auth():
                return
            tokens = _read_json(COURSE_TOKENS_FILE)
            # Return sanitised view (no raw token values to admin UI)
            safe = [
                {
                    'email':        t.get('email'),
                    'order_id':     t.get('order_id'),
                    'created_at':   t.get('created_at'),
                    'access_count': t.get('access_count', 0),
                    'ip_count':     len(t.get('ips', [])),
                    'locked':       t.get('locked', False),
                }
                for t in tokens
            ]
            self._json_response({'ok': True, 'tokens': safe})
            return

        # Static file serving
        # Strip Google image size suffixes like =s120 =s300 =s1600
        self.path = re.sub(r'(\.(?:jpg|jpeg|png|gif|webp|svg))=s\d+', r'\1', self.path)
        parsed = urllib.parse.urlparse(self.path)
        p = parsed.path
        if p not in ('/', '') and '.' not in os.path.basename(p):
            self.path = p + '.html' + (('?' + parsed.query) if parsed.query else '')
        super().do_GET()

    # ---- POST ----

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path

        # ---- Contact form ----
        if path == '/send-message':
            body = self._read_body()
            try:
                data    = json.loads(body)
                name    = str(data.get('name', '')).strip()[:200]
                email   = str(data.get('email', '')).strip()[:200]
                message = str(data.get('message', '')).strip()[:5000]
                if not name or not email or not message:
                    raise ValueError("Missing required fields")

                # Save to submissions store
                submissions = _read_json(SUBMISSIONS_FILE)
                submissions.append({
                    'date':    datetime.now(timezone.utc).isoformat(),
                    'name':    name,
                    'email':   email,
                    'message': message,
                    'status':  'new',
                })
                _write_json(SUBMISSIONS_FILE, submissions)

                # Send email if SMTP is configured
                if cfg.SMTP_USER and cfg.SMTP_PASS:
                    send_email(name, email, message)

                self._json_response({'ok': True})
            except Exception as e:
                self._json_response({'ok': False, 'error': str(e)})
            return

        # ---- Admin login ----
        if path == '/admin/login':
            body = self._read_body()
            try:
                data     = json.loads(body)
                username = str(data.get('username', '')).strip()
                password = str(data.get('password', ''))
                # Compare against config; use constant-time comparison
                ok_user = secrets.compare_digest(username, cfg.ADMIN_USER)
                ok_pass = secrets.compare_digest(
                    hashlib.sha256(password.encode()).hexdigest(),
                    hashlib.sha256(cfg.ADMIN_PASS.encode()).hexdigest()
                )
                if ok_user and ok_pass:
                    token = secrets.token_hex(32)
                    _sessions[token] = username
                    self._json_response(
                        {'ok': True},
                        extra_headers={
                            'Set-Cookie': f'pa_admin={token}; Path=/; HttpOnly; SameSite=Strict'
                        }
                    )
                else:
                    self._json_response({'ok': False, 'error': 'Invalid credentials'}, status=401)
            except Exception as e:
                self._json_response({'ok': False, 'error': str(e)}, status=400)
            return

        # ---- Sales (add) ----
        if path == '/api/sales':
            if not self._require_auth():
                return
            body = self._read_body()
            try:
                data   = json.loads(body)
                name   = str(data.get('name', '')).strip()[:200]
                email  = str(data.get('email', '')).strip()[:200]
                course = str(data.get('course', 'Cinematography Course')).strip()[:200]
                amount = float(data.get('amount', 99))
                status = str(data.get('status', 'paid')).strip()
                if not name or not email:
                    raise ValueError("name and email are required")
                sales = _read_json(SALES_FILE)
                sales.append({
                    'date':   datetime.now(timezone.utc).isoformat(),
                    'name':   name,
                    'email':  email,
                    'course': course,
                    'amount': amount,
                    'status': status,
                })
                _write_json(SALES_FILE, sales)
                self._json_response({'ok': True})
            except Exception as e:
                self._json_response({'ok': False, 'error': str(e)}, status=400)
            return

        # ---- Content editor ----
        if path == '/api/content':
            if not self._require_auth():
                return
            body = self._read_body()
            try:
                data = json.loads(body)
                errors = cm.save_content(data)
                if errors:
                    self._json_response({'ok': False, 'errors': errors})
                else:
                    self._json_response({'ok': True})
            except Exception as e:
                self._json_response({'ok': False, 'error': str(e)}, status=400)
            return

        # ---- Payment config (save) ----
        if path == '/api/payment-config':
            if not self._require_auth():
                return
            body = self._read_body()
            try:
                data = json.loads(body)
                # Preserve existing secrets if masked value submitted
                existing = get_payment_config()
                for field in ('api_key', 'secret_key'):
                    if '****' in str(data.get(field, '')):
                        data[field] = existing.get(field, '')
                save_payment_config(data)
                self._json_response({'ok': True})
            except Exception as e:
                self._json_response({'ok': False, 'error': str(e)}, status=400)
            return

        # ---- Initiate payment (public) ----
        if path == '/api/initiate-payment':
            body = self._read_body()
            try:
                data     = json.loads(body)
                name     = str(data.get('name', '')).strip()[:200]
                email    = str(data.get('email', '')).strip()[:200]
                if not name or not email or '@' not in email:
                    raise ValueError("Valid name and email are required")

                cfg_data = get_payment_config()
                if not cfg_data.get('enabled'):
                    raise ValueError("Payment gateway is not enabled")
                if not cfg_data.get('merchant_id') or not cfg_data.get('api_key'):
                    raise ValueError("Payment gateway is not configured")

                order_id = 'PA-' + secrets.token_hex(8).upper()
                amount   = float(cfg_data.get('course_price', 99))

                # Save pending order
                orders = _read_json(ORDERS_FILE)
                pending = {
                    'order_id':          order_id,
                    'date':              datetime.now(timezone.utc).isoformat(),
                    'name':              name,
                    'email':             email,
                    'amount':            amount,
                    'status':            'pending',
                    'success_indicator': '',
                }
                orders.append(pending)
                _write_json(ORDERS_FILE, orders)

                session_id, success_indicator, checkout_url = _areeba_create_session(
                    cfg_data, order_id, amount, name, email
                )

                # Update order with success indicator
                for o in orders:
                    if o['order_id'] == order_id:
                        o['success_indicator'] = success_indicator
                _write_json(ORDERS_FILE, orders)

                self._json_response({'ok': True, 'checkout_url': checkout_url})
            except Exception as e:
                self._json_response({'ok': False, 'error': str(e)}, status=400)
            return

        # ---- Image upload ----
        if path == '/api/upload-image':
            if not self._require_auth():
                return
            ct = self.headers.get('Content-Type', '')
            if 'multipart/form-data' not in ct:
                self._json_response({'ok': False, 'error': 'multipart required'}, status=400)
                return
            try:
                boundary_match = re.search(r'boundary=([^\s;]+)', ct)
                if not boundary_match:
                    self._json_response({'ok': False, 'error': 'No boundary in Content-Type'}, status=400)
                    return
                boundary = boundary_match.group(1).encode()
                length = int(self.headers.get('Content-Length', 0))
                raw = self.rfile.read(length)

                # Parse multipart manually
                parts = {}
                for part in raw.split(b'--' + boundary):
                    if b'Content-Disposition' not in part:
                        continue
                    header_end = part.find(b'\r\n\r\n')
                    if header_end == -1:
                        continue
                    header = part[:header_end].decode('utf-8', errors='ignore')
                    body   = part[header_end + 4:]
                    if body.endswith(b'\r\n'):
                        body = body[:-2]
                    name_m = re.search(r'name="([^"]+)"', header)
                    if name_m:
                        parts[name_m.group(1)] = body

                if 'file' not in parts or 'filename' not in parts:
                    self._json_response({'ok': False, 'error': 'Missing file or filename field'}, status=400)
                    return

                filename  = parts['filename'].decode('utf-8', errors='ignore').strip()
                raw_bytes = parts['file']
                ok, err   = cm.save_image(filename, raw_bytes)
                if ok:
                    self._json_response({'ok': True})
                else:
                    self._json_response({'ok': False, 'error': err}, status=400)
            except Exception as e:
                self._json_response({'ok': False, 'error': str(e)}, status=400)
            return

        self.send_response(404)
        self.end_headers()

    # ---- OPTIONS (CORS preflight) ----

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def log_message(self, format, *args):
        pass  # silence access log spam


# ── Start server ─────────────────────────────────────────────────────────────
# Set PA_NO_SSL=1 and PA_PORT=8080 to run in plain HTTP mode (behind Nginx/Apache).
_no_ssl = os.environ.get('PA_NO_SSL', '0') == '1'
_port   = int(os.environ.get('PA_PORT', '4443'))
_host   = os.environ.get('PA_HOST', '127.0.0.1')

server = http.server.HTTPServer((_host, _port), Handler)

if _no_ssl:
    print(f"Running at http://{_host}:{_port}  [HTTP mode — SSL handled by reverse proxy]")
    print(f"Admin panel: http://{_host}:{_port}/admin/login.html")
else:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain('cert.pem', 'key.pem')
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    print(f"Running at https://{_host}:{_port}")
    print(f"Admin panel: https://{_host}:{_port}/admin/login.html")

server.serve_forever()

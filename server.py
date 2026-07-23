import http.server, http.client, ssl, os, re, json, smtplib, urllib.parse, hashlib, secrets, io, hmac, base64, time, html
import urllib.request, urllib.error
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate

os.chdir(os.path.dirname(os.path.abspath(__file__)))

import mail_config as cfg
import content_manager as cm


def _reload_cm():
    """Reload content_manager so code/JSON changes apply without restarting server.py."""
    global cm
    import importlib
    cm = importlib.reload(cm)
    return cm

# ── Data store ──────────────────────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

SUBMISSIONS_FILE    = os.path.join(DATA_DIR, 'submissions.json')
SALES_FILE          = os.path.join(DATA_DIR, 'sales.json')
PAYMENT_CONFIG_FILE = os.path.join(DATA_DIR, 'payment_config.json')
ORDERS_FILE         = os.path.join(DATA_DIR, 'orders.json')
COURSE_TOKENS_FILE  = os.path.join(DATA_DIR, 'course_tokens.json')
MEMBERS_FILE        = os.path.join(DATA_DIR, 'members.json')
ACTIVATION_CODES_FILE = os.path.join(DATA_DIR, 'activation_codes.json')
PASSWORD_SETUP_TOKENS_FILE = os.path.join(DATA_DIR, 'password_setup_tokens.json')
COUPONS_FILE          = os.path.join(DATA_DIR, 'coupons.json')
BUNNY_STREAM_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bunny-stream')
BUNNY_TOKEN_KEY_FILE = os.path.join(BUNNY_STREAM_DIR, 'token_auth_key.txt')
BUNNY_COURSE_LINK_FILE = os.path.join(BUNNY_STREAM_DIR, 'course_link.txt')

# ── Course access: max distinct IPs before token is locked ──────────────────
COURSE_MAX_IPS = 2
PASSWORD_SETUP_TTL_HOURS = 24
PASSWORD_SETUP_RESEND_SECONDS = 300

def _read_json(path):
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def _write_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def _read_text_file(path):
    if not os.path.exists(path):
        return ''
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def _parse_bunny_course_config():
    """
    Parse bunny-stream/course_link.txt lines:
    - library id line contains digits (first match)
    - video lines contain a UUID + title text
    """
    raw = _read_text_file(BUNNY_COURSE_LINK_FILE)
    library_id = ''
    videos = []
    for line in raw.splitlines():
        s = line.strip()
        if not s or s.startswith('#'):
            continue
        if not library_id:
            m_lib = re.search(r'\b(\d{3,})\b', s)
            if m_lib:
                library_id = m_lib.group(1)
                continue
        m_vid = re.search(r'\b([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})\b', s)
        if m_vid:
            vid = m_vid.group(1)
            title = re.sub(re.escape(vid), '', s, count=1).strip(' -\t')
            videos.append({'video_id': vid, 'title': title or 'Course chapter'})
    return library_id, videos

def _read_bunny_token_key():
    for line in _read_text_file(BUNNY_TOKEN_KEY_FILE).splitlines():
        s = line.strip()
        if s and not s.startswith('#'):
            return s
    return ''

def _build_bunny_embed_url(library_id, video_id, token_key, expires):
    token_input = f'{token_key}{video_id}{expires}'.encode('utf-8')
    token = hashlib.sha256(token_input).hexdigest()
    return (
        f'https://iframe.mediadelivery.net/embed/{library_id}/{video_id}'
        f'?token={token}&expires={expires}'
    )

def _youtube_embed_url(vid):
    return (
        f'https://www.youtube.com/embed/{vid}'
        '?enablejsapi=1&autoplay=1&mute=1&loop=1&controls=1'
        f'&playlist={vid}&rel=0&modestbranding=1&playsinline=1'
    )

def _youtube_is_available(vid):
    if not vid:
        return False
    try:
        url = f'https://www.youtube.com/oembed?format=json&url=https://youtu.be/{urllib.parse.quote(vid)}'
        with urllib.request.urlopen(url, timeout=6) as resp:
            return resp.status == 200
    except Exception:
        return False

def _bunny_embed_is_available(embed_url):
    try:
        with urllib.request.urlopen(embed_url, timeout=8) as resp:
            body = resp.read(4096).decode('utf-8', errors='ignore')
        return '<h1>404</h1>' not in body
    except Exception:
        return False

# Known-good public promo when CMS/Bunny links are stale or unavailable.
_PROMO_YOUTUBE_FALLBACK = 'sIcsHObKmzI'

def _resolve_course_promo_embed():
    """Public homepage/course trailer — never use paid Bunny chapters from course_link.txt."""
    link = ''
    try:
        all_content = cm.get_all()
        link = (
            all_content.get('homepage_course_video_link')
            or all_content.get('course_video_link')
            or ''
        ).strip()
    except Exception:
        link = ''

    source, vid = cm._parse_video_input(link)

    if source == 'youtube' and vid and _youtube_is_available(vid):
        return {'ok': True, 'provider': 'youtube', 'embed_url': _youtube_embed_url(vid)}

    if source == 'vimeo' and vid:
        url = (
            f'https://player.vimeo.com/video/{vid}'
            '?autoplay=1&loop=1&title=0&byline=0&badge=0&muted=1'
        )
        return {'ok': True, 'provider': 'vimeo', 'embed_url': url}

    if _youtube_is_available(_PROMO_YOUTUBE_FALLBACK):
        return {
            'ok': True,
            'provider': 'youtube',
            'embed_url': _youtube_embed_url(_PROMO_YOUTUBE_FALLBACK),
            'fallback': True,
        }

    return {'ok': False, 'error': 'No promo video configured'}

# ── Payment config helpers ───────────────────────────────────────────────────
_DEFAULT_PAYMENT_CONFIG = {
    'enabled':      False,
    'demo_mode':    False,
    'gateway_type': 'cybersource',
    'merchant_id':  '',
    'api_key':      '',
    'secret_key':   '',
    'gateway_url':  'apitest.cybersource.com',
    'currency':     'USD',
    'course_price': 99.00,
    'course_name':  'Cinematography Workshop',
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
        clean['course_price'] = round(float(clean['course_price']), 2)
    if 'enabled' in clean:
        clean['enabled'] = bool(clean['enabled'])
    if 'demo_mode' in clean:
        clean['demo_mode'] = bool(clean['demo_mode'])
    with open(PAYMENT_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(clean, f, indent=2, ensure_ascii=False)

def _masked_config(cfg_data):
    """Return config with secret fields masked for display."""
    out = dict(cfg_data)
    for field in ('api_key', 'secret_key'):
        val = out.get(field, '')
        out[field] = val[:4] + '****' if len(val) > 4 else ('****' if val else '')
    return out

def _payment_gateway_host(cfg_data):
    host = (cfg_data.get('gateway_url') or 'apitest.cybersource.com').strip()
    host = host.replace('https://', '').replace('http://', '').rstrip('/')
    return host or 'apitest.cybersource.com'

def _payment_allowed_origins(cfg_data):
    """Apex + www variants of the configured site URL (Cybersource needs an exact match)."""
    base = (cfg_data.get('return_base_url') or 'https://pierreazar.com').rstrip('/')
    allowed = {base}
    if '://www.' in base:
        allowed.add(base.replace('://www.', '://', 1))
    else:
        scheme, sep, rest = base.partition('://')
        if sep and rest:
            allowed.add(f'{scheme}://www.{rest}')
    return allowed

def _payment_target_origins(cfg_data, page_origin=None):
    """
    Cybersource UNUSED_TARGET_ORIGINS fires when JWT origins don't match
    window.location.origin exactly — including www vs non-www.
    Pass only the current page origin (must be on the allowlist).
    """
    allowed = _payment_allowed_origins(cfg_data)
    origin = (page_origin or '').strip().rstrip('/')
    if origin in allowed:
        return [origin]
    return [next(iter(sorted(allowed)))]

def _format_money(amount):
    return f'{float(amount):.2f}'

def _cybersource_bill_to(name, email):
    """Cybersource requires bill_address1, bill_city, bill_country for auth."""
    parts = (name or '').split()
    first_name = parts[0] if parts else 'Guest'
    last_name = parts[-1] if len(parts) > 1 else first_name
    return {
        'firstName': first_name,
        'lastName': last_name,
        'email': email,
        'address1': 'Beirut',
        'locality': 'Beirut',
        'administrativeArea': 'Beirut',
        'country': 'LB',
        'postalCode': '1103',
    }

def _cybersource_digest(body):
    digest = base64.b64encode(hashlib.sha256(body.encode('utf-8')).digest()).decode('utf-8')
    return f'SHA-256={digest}'

def _cybersource_signature(cfg_data, host, date_hdr, method, request_target, body):
    merchant_id = cfg_data['merchant_id']
    secret_key  = cfg_data['secret_key']
    digest_hdr  = _cybersource_digest(body)
    target      = f'{method.lower()} {request_target}'
    signing = (
        f'host: {host}\n'
        f'date: {date_hdr}\n'
        f'(request-target): {target}\n'
        f'digest: {digest_hdr}\n'
        f'v-c-merchant-id: {merchant_id}'
    )
    secret = base64.b64decode(secret_key)
    sig = base64.b64encode(hmac.new(secret, signing.encode('utf-8'), hashlib.sha256).digest()).decode('utf-8')
    key_id = cfg_data['api_key']
    signature_header = (
        f'keyid="{key_id}", algorithm="HmacSHA256", '
        f'headers="host date (request-target) digest v-c-merchant-id", '
        f'signature="{sig}"'
    )
    return digest_hdr, signature_header

def _cybersource_api_request(cfg_data, method, request_target, body_obj=None):
    host = _payment_gateway_host(cfg_data)
    body = json.dumps(body_obj, separators=(',', ':')) if body_obj is not None else ''
    date_hdr = formatdate(timeval=None, localtime=False, usegmt=True)
    digest_hdr, signature_header = _cybersource_signature(cfg_data, host, date_hdr, method, request_target, body)
    conn = http.client.HTTPSConnection(host, timeout=30)
    try:
        conn.request(
            method,
            request_target,
            body=body.encode('utf-8') if body else None,
            headers={
                'Host': host,
                'Date': date_hdr,
                'Digest': digest_hdr,
                'v-c-merchant-id': cfg_data['merchant_id'],
                'Signature': signature_header,
                'Content-Type': 'application/json',
            },
        )
        resp = conn.getresponse()
        raw = resp.read().decode('utf-8')
        if resp.status >= 400:
            raise ValueError(f'Cybersource error ({resp.status}): {raw[:500]}')
        return raw
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f'Cybersource connection error: {e}') from e
    finally:
        conn.close()

# Unified Checkout UI branding (matches payment-checkout.css light theme).
_CYBERSOURCE_APPEARANCE = {
    'variables': {
        'backgroundColor': '#ffffff',
        'textColor': '#18181b',
        'headerBackground': '#ffffff',
        'headerForeground': '#18181b',
        'headerAvatarBackgroundColor': '#18181b',
        'headerAvatarForegroundColor': '#ffffff',
        'inputBackground': '#ffffff',
        'inputColor': '#18181b',
        'inputPlaceholderColor': '#a1a1aa',
        'inputBorderColor': '#e4e4e7',
        'inputBorderRadius': '8px',
        'inputFocusedBorderColor': '#18181b',
        'buttonBackground': '#18181b',
        'buttonForeground': '#ffffff',
        'buttonBorderRadius': '8px',
        'buttonHoverBackground': '#000000',
        'buttonHoverForeground': '#ffffff',
        'fontFamily': 'Arial, sans-serif',
        'borderRadius': '8px',
    }
}

def _cybersource_create_capture_context(cfg_data, order_id, amount, name, email, page_origin=None):
    """Create a Cybersource Unified Checkout capture context JWT."""
    currency = cfg_data.get('currency', 'USD')
    payload = {
        'targetOrigins': _payment_target_origins(cfg_data, page_origin),
        'allowedCardNetworks': ['VISA', 'MASTERCARD', 'AMEX'],
        'allowedPaymentTypes': ['PANENTRY'],
        'country': 'LB',
        'locale': 'en_US',
        'appearance': _CYBERSOURCE_APPEARANCE,
        'data': {
            'clientReferenceInformation': {'code': order_id},
            'orderInformation': {
                'amountDetails': {
                    'totalAmount': _format_money(amount),
                    'currency': currency,
                },
                'billTo': _cybersource_bill_to(name, email),
            },
        },
        'completeMandate': {'type': 'CAPTURE'},
        'captureMandate': {
            'billingType': 'FULL',
            'requestEmail': False,
            'requestPhone': False,
            'requestShipping': False,
        },
    }
    raw = _cybersource_api_request(cfg_data, 'POST', '/uc/v1/sessions', payload)

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            token = parsed.get('captureContext') or parsed.get('jwt') or parsed.get('keyId')
            if token:
                return token
    except json.JSONDecodeError:
        pass
    token = raw.strip().strip('"')
    if token.count('.') >= 2:
        return token
    raise ValueError('Unexpected Cybersource capture context response')

def _decode_jwt_payload(token):
    if not token or token.count('.') < 2:
        return {}
    segment = token.split('.')[1]
    pad = '=' * (-len(segment) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(segment + pad))
    except Exception:
        return {}

def _cybersource_extract_payment_id(payload):
    if not isinstance(payload, dict):
        return ''
    for key in ('id', 'transactionId'):
        val = str(payload.get(key, '')).strip()
        if val:
            return val
    details = payload.get('details')
    if isinstance(details, dict):
        val = str(details.get('id', '')).strip()
        if val:
            return val
    return ''

def _cybersource_reason_ok(reason):
    return str(reason).strip() in ('', '100', '110')

def _cybersource_tss_find_transaction(cfg_data, query):
    payload = {
        'save': False,
        'timezone': 'Etc/UTC',
        'query': query,
        'offset': 0,
        'limit': 5,
        'sort': 'submitTimeUtc:desc',
    }
    raw = _cybersource_api_request(cfg_data, 'POST', '/tss/v2/searches', payload)
    data = json.loads(raw)
    return data.get('_embedded', {}).get('transactionSummaries', [])

def _cybersource_transaction_approved(txn, order):
    if not txn:
        return False, 'Transaction not found in Cybersource'
    app = txn.get('applicationInformation') or {}
    reason = str(app.get('reasonCode', '')).strip()
    rflag = str(app.get('rFlag', '')).strip().upper()
    if reason and not _cybersource_reason_ok(reason):
        msg = app.get('rMessage') or f'Cybersource reason code {reason}'
        return False, msg
    if rflag.startswith('D'):
        return False, app.get('rMessage') or f'Cybersource flag {rflag}'
    for sub in app.get('applications') or []:
        if sub.get('name') == 'ics_auth':
            sub_reason = str(sub.get('reasonCode', '')).strip()
            if sub_reason and not _cybersource_reason_ok(sub_reason):
                return False, sub.get('rMessage') or f'Authorization failed ({sub_reason})'
    ref = (txn.get('clientReferenceInformation') or {}).get('code', '')
    if ref and ref != order.get('order_id'):
        return False, f'Order reference mismatch ({ref})'
    amount_details = (txn.get('orderInformation') or {}).get('amountDetails') or {}
    if amount_details:
        expected = f"{float(order.get('amount', 0)):.2f}"
        got = str(amount_details.get('totalAmount', '')).strip()
        if got and got != expected:
            return False, f'Amount mismatch (expected {expected}, got {got})'
    return True, reason or '100'

def _cybersource_find_approved_transaction(cfg_data, order, payment_id=None):
    order_id = order.get('order_id', '')
    queries = []
    if payment_id:
        queries.append(f'id:{payment_id}')
    if order_id:
        queries.append(f'clientReferenceInformation.code:{order_id}')
    for query in queries:
        txns = _cybersource_tss_find_transaction(cfg_data, query)
        for txn in txns:
            ok, detail = _cybersource_transaction_approved(txn, order)
            if ok:
                return txn, detail
    return None, None

def _cybersource_verify_payment(cfg_data, order, payment_id=None):
    last_err = 'Transaction not found in Cybersource'
    for attempt in range(4):
        txn, detail = _cybersource_find_approved_transaction(cfg_data, order, payment_id)
        if txn:
            return {
                'ok': True,
                'cybersource_id': txn.get('id', payment_id or ''),
                'status': 'AUTHORIZED',
                'gateway_reason': detail,
                'source': 'tss_verify',
            }
        if attempt < 3:
            time.sleep(1.0)
    raise ValueError(last_err)

def _cybersource_extract_status(payload):
    """Return payment status string if present. Do not invent success."""
    if not isinstance(payload, dict):
        return ''
    for key in ('status', 'outcome', 'paymentStatus'):
        val = str(payload.get(key, '')).strip().upper()
        if val:
            return val
    details = payload.get('details')
    if isinstance(details, dict):
        for key in ('status', 'outcome', 'paymentStatus'):
            val = str(details.get(key, '')).strip().upper()
            if val:
                return val
    ctx = payload.get('ctx')
    if isinstance(ctx, list):
        for item in ctx:
            if isinstance(item, dict) and isinstance(item.get('data'), dict):
                st = _cybersource_extract_status(item['data'])
                if st:
                    return st
    return ''

def _cybersource_is_authorized_status(status):
    # Only real settlement outcomes count as paid. Never PENDING/ACCEPTED alone.
    return status in {'AUTHORIZED', 'CAPTURED', 'PARTIAL_AUTHORIZED'}

def _cybersource_payload_succeeded(payload):
    if not payload or not isinstance(payload, dict):
        return False
    fail_values = {'DECLINED', 'FAILED', 'REJECTED', 'VOIDED', 'CANCELLED', 'ERROR', 'INVALID_REQUEST'}
    status = _cybersource_extract_status(payload)
    if status in fail_values:
        return False
    if _cybersource_is_authorized_status(status):
        return True
    # Walk only for explicit status fields — never treat token id/details as success
    stack = [payload]
    while stack:
        node = stack.pop()
        if not isinstance(node, dict):
            continue
        for key in ('status', 'outcome', 'paymentStatus'):
            val = str(node.get(key, '')).strip().upper()
            if val in fail_values:
                return False
            if _cybersource_is_authorized_status(val):
                return True
        for val in node.values():
            if isinstance(val, dict):
                stack.append(val)
            elif isinstance(val, list):
                stack.extend(x for x in val if isinstance(x, dict))
    processor = payload.get('processorInformation')
    reason = ''
    if isinstance(processor, dict):
        reason = str(processor.get('responseCode', ''))
    if not reason:
        reason = str(payload.get('reasonCode', ''))
    if reason in ('100', '110') and status:
        return _cybersource_is_authorized_status(status)
    return False

def _cybersource_normalize_result(result_raw):
    if result_raw is None or result_raw == '':
        return '', {}
    if isinstance(result_raw, dict):
        for key in ('jwt', 'token', 'transientTokenJwt', 'result'):
            token = result_raw.get(key)
            if isinstance(token, str) and token.strip():
                jwt = token.strip()
                payload = _decode_jwt_payload(jwt)
                return jwt, payload or result_raw
        return '', result_raw
    token = str(result_raw).strip()
    if token.startswith('{') and token.endswith('}'):
        try:
            return _cybersource_normalize_result(json.loads(token))
        except json.JSONDecodeError:
            pass
    return token, _decode_jwt_payload(token)

def _cybersource_is_transient_token(payload, jwt_str):
    if not jwt_str or jwt_str.count('.') < 2:
        return False
    if payload and _cybersource_payload_succeeded(payload):
        return False
    if not payload:
        return True
    # Completed payment JWTs include transaction status/id from UC autoProcessing
    if _cybersource_extract_status(payload):
        return False
    token_type = str(payload.get('type', '')).lower()
    if token_type.startswith(('mf-', 'api-', 'gda-', 'uc-', 'flex')):
        return True
    if 'flex' in str(payload.get('iss', '')).lower():
        return True
    data = payload.get('data')
    if isinstance(data, dict) and data.get('type') in ('001', '002', '003', '004'):
        return True
    # JWT without payment status is a token to charge, not a success receipt
    if not payload.get('details') and not payload.get('id'):
        return True
    return False

def _cybersource_charge_transient_token(cfg_data, order, transient_jwt):
    amount = float(order.get('amount', cfg_data.get('course_price', 0)))
    currency = cfg_data.get('currency', 'USD')
    payload = {
        'clientReferenceInformation': {'code': order.get('order_id', '')},
        'processingInformation': {'capture': True},
        'tokenInformation': {'transientTokenJwt': transient_jwt},
        'orderInformation': {
            'amountDetails': {
                'totalAmount': _format_money(amount),
                'currency': currency,
            },
            'billTo': _cybersource_bill_to(order.get('name', ''), order.get('email', '')),
        },
    }
    raw = _cybersource_api_request(cfg_data, 'POST', '/pts/v2/payments', payload)
    try:
        resp = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f'Invalid payment response from Cybersource: {raw[:200]}') from e
    status = _cybersource_extract_status(resp)
    if not _cybersource_is_authorized_status(status):
        err = (resp.get('errorInformation') or {}).get('message') or status or 'unknown'
        raise ValueError(f'Payment not approved by Cybersource ({err})')
    payment_id = _cybersource_extract_payment_id(resp)
    if not payment_id:
        raise ValueError('Cybersource did not return a transaction id')
    return _cybersource_verify_payment(cfg_data, order, payment_id)

def _cybersource_process_payment(cfg_data, order, result_raw):
    """Confirm payment only when Cybersource TSS shows an approved txn for this order."""
    jwt_str, payload = _cybersource_normalize_result(result_raw)
    jwt_payload = payload or (_decode_jwt_payload(jwt_str) if jwt_str else {})
    payment_id = _cybersource_extract_payment_id(jwt_payload)

    if jwt_str and _cybersource_is_transient_token(jwt_payload, jwt_str):
        return _cybersource_charge_transient_token(cfg_data, order, jwt_str)

    status = _cybersource_extract_status(jwt_payload)
    if status in {'DECLINED', 'FAILED', 'REJECTED', 'VOIDED', 'CANCELLED', 'ERROR', 'INVALID_REQUEST'}:
        raise ValueError(f'Payment declined ({status})')

    return _cybersource_verify_payment(cfg_data, order, payment_id or None)

def _cybersource_payment_succeeded(result_jwt):
    try:
        return bool(_cybersource_process_payment(get_payment_config(), {}, result_jwt).get('ok'))
    except Exception:
        return False

def _receipt_access_key(order_id, email):
    cfg = get_payment_config()
    pepper = (cfg.get('merchant_id') or 'pierreazar') + ':receipt'
    raw = f'{order_id}:{email.strip().lower()}'
    return hmac.new(pepper.encode(), raw.encode(), hashlib.sha256).hexdigest()[:32]

def _payment_success_redirect(order_id, email, course_token=None):
    key = _receipt_access_key(order_id, email)
    qs = urllib.parse.urlencode({'order': order_id, 'key': key})
    if course_token:
        qs += '&' + urllib.parse.urlencode({'token': course_token})
    return f'/payment-success.html?{qs}'

def _find_paid_order(order_id, email=None):
    orders = _read_json(ORDERS_FILE)
    order = next((o for o in orders if o.get('order_id') == order_id), None)
    if not order or order.get('status') != 'paid':
        return None
    if email and order.get('email', '').strip().lower() != email.strip().lower():
        return None
    return order

def _order_from_course_token(token):
    if not token:
        return None
    entry = next((t for t in _read_json(COURSE_TOKENS_FILE) if t.get('token') == token), None)
    if not entry:
        return None
    return _find_paid_order(entry.get('order_id', ''), entry.get('email', ''))

def _build_receipt_html(order, cfg_data):
    amount = float(order.get('amount', cfg_data.get('course_price', 0)))
    currency = cfg_data.get('currency', 'USD')
    course = cfg_data.get('course_name', 'Cinematography Workshop')
    order_id = order.get('order_id', '')
    name = order.get('name', '')
    email = order.get('email', '')
    date_raw = order.get('date', '')
    try:
        dt = datetime.fromisoformat(date_raw.replace('Z', '+00:00'))
        date_display = dt.strftime('%d %B %Y, %H:%M UTC')
    except Exception:
        date_display = date_raw or datetime.now(timezone.utc).strftime('%d %B %Y')
    gateway_host = _payment_gateway_host(cfg_data)
    test_mode = 'apitest' in gateway_host or 'test' in gateway_host
    test_banner = (
        '<div style="background:#fff3cd;color:#856404;padding:10px 14px;border-radius:6px;'
        'margin-bottom:20px;font-size:13px;border:1px solid #ffeeba;">'
        '<strong>TEST TRANSACTION</strong> — This is a sandbox payment receipt. '
        'No real charge was made to your card.</div>'
    ) if test_mode else ''
    amount_display = f'${_format_money(amount)} {currency}' if currency == 'USD' else f'{_format_money(amount)} {currency}'
    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        '<title>Receipt ' + order_id + ' — Pierre Azar</title>'
        '<style>'
        'body{font-family:Arial,sans-serif;color:#111;max-width:640px;margin:40px auto;padding:0 24px;}'
        'h1{font-size:22px;margin:0 0 4px;} .meta{color:#666;font-size:13px;margin-bottom:24px;}'
        'table{width:100%;border-collapse:collapse;margin:20px 0;} '
        'td{padding:10px 0;border-bottom:1px solid #eee;vertical-align:top;} '
        'td.label{color:#666;width:38%;} .total td{font-weight:700;font-size:16px;border-top:2px solid #111;}'
        '.footer{margin-top:32px;padding-top:16px;border-top:1px solid #ddd;color:#666;font-size:12px;line-height:1.6;}'
        '@media print{body{margin:0;} .no-print{display:none;}}'
        '</style></head><body>'
        + test_banner +
        '<h1>Payment Receipt</h1>'
        '<p class="meta">Pierre Azar — Cinematography Workshop</p>'
        '<table>'
        f'<tr><td class="label">Receipt #</td><td>{order_id}</td></tr>'
        f'<tr><td class="label">Date</td><td>{date_display}</td></tr>'
        f'<tr><td class="label">Customer</td><td>{name}<br><span style="color:#666;font-size:13px;">{email}</span></td></tr>'
        f'<tr><td class="label">Item</td><td>{course}</td></tr>'
        f'<tr><td class="label">Payment method</td><td>Card (Areeba / Cybersource)</td></tr>'
        f'<tr class="total"><td class="label">Amount paid</td><td>{amount_display}</td></tr>'
        '</table>'
        '<div class="footer">'
        'Thank you for your purchase. Course access details are sent separately by email.<br>'
        'For support: <a href="mailto:contact@pierreazar.com">contact@pierreazar.com</a>'
        '</div>'
        '<p class="no-print" style="margin-top:24px;">'
        '<button onclick="window.print()" style="padding:10px 18px;cursor:pointer;">Print / Save as PDF</button>'
        '</p>'
        '</body></html>'
    )

def _finalize_paid_order(order_id, cfg_data, gateway_name='cybersource', payment_meta=None):
    """Idempotently record payment, grant Premium access, and notify parties."""
    payment_meta = payment_meta or {}
    orders = _read_json(ORDERS_FILE)
    order = next((o for o in orders if o.get('order_id') == order_id), None)
    if not order:
        return {'ok': False, 'redirect': '/payment-failed.html'}
    already_paid = order.get('status') == 'paid'
    paid_at = str(order.get('paid_at') or datetime.now(timezone.utc).isoformat())

    if not already_paid:
        sales = _read_json(SALES_FILE)
        if not any(s.get('order_id') == order_id for s in sales):
            sales.append({
                'date': paid_at,
                'name': order.get('name', ''),
                'email': order.get('email', ''),
                'course': cfg_data.get('course_name', 'Cinematography Workshop'),
                'amount': order.get('amount', cfg_data.get('course_price', 99)),
                'status': 'paid',
                'order_id': order_id,
                'gateway': gateway_name,
                'cybersource_id': payment_meta.get('cybersource_id', ''),
                'gateway_status': payment_meta.get('status', ''),
            })
            _write_json(SALES_FILE, sales)

        order['status'] = 'paid'
        order['paid_at'] = paid_at
        if payment_meta.get('cybersource_id'):
            order['cybersource_id'] = payment_meta['cybersource_id']
        if payment_meta.get('status'):
            order['gateway_status'] = payment_meta['status']

        coupon_used = order.get('coupon_code', '').strip()
        if coupon_used:
            _use_coupon(coupon_used)

    buyer_email = order.get('email', '').strip().lower()
    buyer_name  = order.get('name', '')
    base_url    = cfg_data.get('return_base_url', 'https://pierreazar.com')
    order['paid_at'] = paid_at
    account = _upsert_premium_buyer(order)
    receipt_url = f"{base_url.rstrip('/')}/api/receipt?{urllib.parse.urlencode({'order': order_id, 'key': _receipt_access_key(order_id, buyer_email), 'download': '1'})}"

    if not order.get('buyer_access_emailed'):
        try:
            if account['needs_password_setup']:
                _issue_password_setup_email(order, base_url, receipt_url=receipt_url)
                order['buyer_email_type'] = 'password_setup'
            else:
                _send_premium_access_email(
                    buyer_name,
                    buyer_email,
                    base_url,
                    order_id=order_id,
                    receipt_url=receipt_url,
                )
                order['buyer_email_type'] = 'premium_access'
            order['buyer_access_emailed'] = True
            order['buyer_access_emailed_at'] = datetime.now(timezone.utc).isoformat()
        except Exception as e:
            _log_email_error(f'buyer_access:{order_id}', e)

    if not order.get('merchant_notified'):
        try:
            _send_purchase_notification_email(order, cfg_data, payment_meta)
            order['merchant_notified'] = True
            order['merchant_notified_at'] = datetime.now(timezone.utc).isoformat()
        except Exception as e:
            _log_email_error(f'purchase_notify:{order_id}', e)

    _write_json(ORDERS_FILE, orders)
    return {'ok': True, 'redirect': _payment_success_redirect(order_id, buyer_email)}

# ── Areeba / MPGS hosted checkout ────────────────────────────────────────────
def _areeba_create_session(cfg_data, order_id, amount, name, email):
    """
    Call the Areeba (MPGS) REST API to create a hosted checkout session.
    Returns (session_id, checkout_url) or raises an exception on failure.
    """
    merchant_id = cfg_data['merchant_id']
    api_key     = cfg_data['api_key']
    gateway_url = _payment_gateway_host(cfg_data)
    if 'areeba.com' in gateway_url and 'cybersource' not in gateway_url:
        gateway_url = 'epayment.areeba.com'
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
            "description": cfg_data.get('course_name', 'Cinematography Workshop'),
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

# ── Session store (persisted to disk; survives restarts) ────────────────────
ADMIN_SESSIONS_FILE  = os.path.join(DATA_DIR, 'admin_sessions.json')
MEMBER_SESSIONS_FILE = os.path.join(DATA_DIR, 'member_sessions.json')
SESSION_TTL_DAYS     = 30   # sessions expire after 30 days

def _load_sessions(path):
    """Load session dict from disk, pruning expired entries."""
    raw = _read_json(path)  # list of {token, value, expires}
    cutoff = datetime.now(timezone.utc).isoformat()
    valid  = {e['token']: e['value'] for e in raw
              if isinstance(e, dict) and e.get('expires', '') > cutoff}
    return valid

def _save_sessions(path, sessions_dict):
    """Persist sessions dict to disk with expiry timestamps."""
    from datetime import timedelta
    expires = (datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS)).isoformat()
    raw = [{'token': t, 'value': v, 'expires': expires} for t, v in sessions_dict.items()]
    _write_json(path, raw)

# Load persisted sessions on startup
_sessions        = _load_sessions(ADMIN_SESSIONS_FILE)   # token -> username
_member_sessions = _load_sessions(MEMBER_SESSIONS_FILE)  # token -> email

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

def _get_member_session(cookie_header):
    """Return member email if valid member cookie, else None."""
    if not cookie_header:
        return None
    for part in cookie_header.split(';'):
        part = part.strip()
        if part.startswith('pa_member='):
            token = part[len('pa_member='):]
            return _member_sessions.get(token)
    return None

# ── Member helpers ──────────────────────────────────────────────────────────

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

def _hash_password(password):
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 200_000)
    return salt + ':' + h.hex()

def _verify_password(password, stored):
    try:
        salt, h = stored.split(':', 1)
        expected = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 200_000).hex()
        return secrets.compare_digest(expected, h)
    except Exception:
        return False

def _normalize_email(email):
    return str(email or '').strip().lower()

def _create_member_session(email):
    token = secrets.token_hex(32)
    _member_sessions[token] = _normalize_email(email)
    _save_sessions(MEMBER_SESSIONS_FILE, _member_sessions)
    return token

def _upsert_premium_buyer(order, migration_version=None):
    """Idempotently grant Premium membership for a verified paid order."""
    email = _normalize_email(order.get('email'))
    if not email or not _EMAIL_RE.match(email):
        raise ValueError('Paid order has an invalid buyer email')
    order_id = str(order.get('order_id', '')).strip()
    if not order_id:
        raise ValueError('Paid order has no order ID')

    name = str(order.get('name', '')).strip()
    paid_at = str(
        order.get('paid_at')
        or order.get('date')
        or datetime.now(timezone.utc).isoformat()
    )
    members = _read_json(MEMBERS_FILE)
    member = next((m for m in members if _normalize_email(m.get('email')) == email), None)
    created = member is None

    if created:
        member = {
            'email': email,
            'name': name,
            'password': '',
            'password_pending': True,
            'created_at': paid_at,
            'last_login': '',
            'active': True,
            'premium': True,
            'premium_since': paid_at,
            'source_order_ids': [order_id],
        }
        members.append(member)
    else:
        member['email'] = email
        if name and not member.get('name'):
            member['name'] = name
        member['active'] = True
        member['premium'] = True
        existing_since = str(member.get('premium_since', '') or '')
        member['premium_since'] = min(
            [value for value in (existing_since, paid_at) if value]
        )
        source_orders = member.setdefault('source_order_ids', [])
        if order_id not in source_orders:
            source_orders.append(order_id)
        if member.get('password'):
            member['password_pending'] = False
        else:
            member['password_pending'] = True

    if migration_version:
        migrations = member.setdefault('migrations', [])
        if migration_version not in migrations:
            migrations.append(migration_version)

    _write_json(MEMBERS_FILE, members)
    return {
        'member': member,
        'created': created,
        'needs_password_setup': bool(member.get('password_pending')),
    }

def _password_setup_digest(raw_token):
    return hashlib.sha256(str(raw_token).encode('utf-8')).hexdigest()

def _create_password_setup_token(email, order_id):
    """Create an expiring setup token; persist only its SHA-256 digest."""
    email = _normalize_email(email)
    now = datetime.now(timezone.utc)
    tokens = _read_json(PASSWORD_SETUP_TOKENS_FILE)
    for entry in tokens:
        if (
            _normalize_email(entry.get('email')) == email
            and not entry.get('consumed_at')
            and not entry.get('invalidated_at')
        ):
            entry['invalidated_at'] = now.isoformat()

    raw_token = secrets.token_urlsafe(48)
    tokens.append({
        'token_hash': _password_setup_digest(raw_token),
        'email': email,
        'order_id': str(order_id or ''),
        'created_at': now.isoformat(),
        'expires_at': (now + timedelta(hours=PASSWORD_SETUP_TTL_HOURS)).isoformat(),
        'consumed_at': '',
        'invalidated_at': '',
    })
    _write_json(PASSWORD_SETUP_TOKENS_FILE, tokens)
    return raw_token

def _setup_resend_allowed(email):
    email = _normalize_email(email)
    tokens = _read_json(PASSWORD_SETUP_TOKENS_FILE)
    recent = [
        str(entry.get('created_at', ''))
        for entry in tokens
        if _normalize_email(entry.get('email')) == email
    ]
    if not recent:
        return True
    try:
        latest = datetime.fromisoformat(max(recent))
        return datetime.now(timezone.utc) - latest >= timedelta(seconds=PASSWORD_SETUP_RESEND_SECONDS)
    except (TypeError, ValueError):
        return True

def _find_verified_paid_order_for_email(email):
    email = _normalize_email(email)
    sales = _read_json(SALES_FILE)
    paid_sale_ids = {
        str(s.get('order_id', '')).strip()
        for s in sales
        if s.get('status') == 'paid' and s.get('order_id')
    }
    orders = _read_json(ORDERS_FILE)
    matches = [
        order for order in orders
        if order.get('status') == 'paid'
        and str(order.get('order_id', '')).strip() in paid_sale_ids
        and _normalize_email(order.get('email')) == email
    ]
    return matches[-1] if matches else None

def _consume_password_setup_token(raw_token, password):
    if len(password) < 8:
        raise ValueError('Password must be at least 8 characters')
    digest = _password_setup_digest(raw_token)
    tokens = _read_json(PASSWORD_SETUP_TOKENS_FILE)
    entry = next((t for t in tokens if secrets.compare_digest(
        str(t.get('token_hash', '')), digest
    )), None)
    if not entry or entry.get('consumed_at') or entry.get('invalidated_at'):
        raise ValueError('This setup link is invalid or has already been used')
    try:
        if datetime.fromisoformat(str(entry.get('expires_at', ''))) <= datetime.now(timezone.utc):
            raise ValueError('This setup link has expired')
    except (TypeError, ValueError) as exc:
        if isinstance(exc, ValueError) and str(exc) == 'This setup link has expired':
            raise
        raise ValueError('This setup link is invalid') from exc

    email = _normalize_email(entry.get('email'))
    members = _read_json(MEMBERS_FILE)
    member = next((m for m in members if _normalize_email(m.get('email')) == email), None)
    if not member or not member.get('premium'):
        raise ValueError('Premium account not found')
    if not member.get('active', True):
        raise ValueError('Account is disabled')

    member['password'] = _hash_password(password)
    member['password_pending'] = False
    member['password_set_at'] = datetime.now(timezone.utc).isoformat()
    entry['consumed_at'] = datetime.now(timezone.utc).isoformat()
    _write_json(MEMBERS_FILE, members)
    _write_json(PASSWORD_SETUP_TOKENS_FILE, tokens)
    return member

# ── Activation code helpers ──────────────────────────────────────────────────

def _generate_activation_code(email):
    """Generate a one-time activation code tied to email and persist it."""
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'  # no 0/O/1/I
    code = ''.join(secrets.choice(alphabet) for _ in range(4)) + '-' + \
           ''.join(secrets.choice(alphabet) for _ in range(4))
    codes = _read_json(ACTIVATION_CODES_FILE)
    codes.append({
        'code':       code,
        'email':      email,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'used':       False,
    })
    _write_json(ACTIVATION_CODES_FILE, codes)
    return code

def _log_email_error(context, exc):
    try:
        log_path = os.path.join(DATA_DIR, 'email.log')
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f"{datetime.now(timezone.utc).isoformat()} [{context}] {exc}\n")
    except Exception:
        pass

def _log_email_ok(context, to_addr):
    try:
        log_path = os.path.join(DATA_DIR, 'email.log')
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f"{datetime.now(timezone.utc).isoformat()} [OK {context}] to={to_addr}\n")
    except Exception:
        pass

def _smtp_send(msg, recipients, include_notify_cc=False):
    """Send via Hostinger SMTP. recipients: str or list."""
    if isinstance(recipients, str):
        recipients = [recipients]
    recipients = [r for r in recipients if r]
    if not recipients:
        raise ValueError('No email recipients')
    # Hostinger often hides/drops mailbox self-mail (From==To same account).
    if include_notify_cc:
        configured_cc = getattr(cfg, 'NOTIFY_CC', '') or []
        if isinstance(configured_cc, str):
            configured_cc = [part.strip() for part in configured_cc.split(',')]
        cc_recipients = []
        known = {r.lower() for r in recipients}
        for cc in configured_cc:
            cc = str(cc).strip()
            if cc and cc.lower() not in known:
                recipients.append(cc)
                cc_recipients.append(cc)
                known.add(cc.lower())
        if cc_recipients and not msg.get('Cc'):
            msg['Cc'] = ', '.join(cc_recipients)
    with smtplib.SMTP(cfg.SMTP_HOST, cfg.SMTP_PORT, timeout=30) as s:
        s.ehlo()
        s.starttls()
        s.ehlo()
        s.login(cfg.SMTP_USER, cfg.SMTP_PASS)
        refused = s.sendmail(cfg.SMTP_USER, recipients, msg.as_string())
    if refused:
        raise ValueError(f'SMTP refused: {refused}')
    return recipients

def _send_password_setup_email(name, email, raw_token, base_url, order_id='', receipt_url=None):
    setup_url = (
        f"{base_url.rstrip('/')}/member/set-password"
        f"#token={urllib.parse.quote(raw_token)}"
    )
    subject = "Welcome to the Cinematography Workshop!"
    receipt_line = f"\nDownload your receipt: {receipt_url}\n" if receipt_url else ''
    body_text = (
        f"Hi {name or email},\n\n"
        "Welcome to the Cinematography Workshop!\n\n"
        "Thank you for joining. I’m excited to have you here.\n\n"
        "This isn’t a traditional classroom course—it’s a practical workshop where you’ll "
        "learn the same techniques I use on professional film sets.\n\n"
        "Your workshop is ready.\n\n"
        "Create your password and start watching here:\n"
        f"{setup_url}\n"
        f"{receipt_line}\n"
        f"The link expires in {PASSWORD_SETUP_TTL_HOURS} hours and can be used once.\n"
        "If it expires, request a new link from the member login page.\n\n"
        "Enjoy the workshop, and thank you for being part of this journey.\n\n"
        "— Pierre Azar\n"
        "contact@pierreazar.com"
    )
    receipt_html = (
        f'<p><a href="{receipt_url}" style="color:#222;">Download your payment receipt</a></p>'
        if receipt_url else ''
    )
    body_html = (
        '<html><body style="font-family:Arial,sans-serif;color:#222;max-width:600px;">'
        f'<p>Hi {html.escape(name or email)},</p>'
        '<h2>Welcome to the Cinematography Workshop!</h2>'
        '<p>Thank you for joining. I’m excited to have you here.</p>'
        '<p>This isn’t a traditional classroom course—it’s a practical workshop where '
        'you’ll learn the same techniques I use on professional film sets.</p>'
        '<p><strong>Your workshop is ready.</strong></p>'
        f'<p><a href="{setup_url}" style="background:#222;color:#fff;padding:12px 24px;'
        'text-decoration:none;border-radius:4px;display:inline-block;">'
        'Create Password &amp; Start Watching</a></p>'
        f'<p style="color:#888;font-size:13px;">This secure link expires in '
        f'{PASSWORD_SETUP_TTL_HOURS} hours and can be used once.</p>'
        f'{receipt_html}'
        '<p style="color:#888;font-size:12px;">If the link expires, request a new one '
        'from the member login page.</p>'
        '<p>Enjoy the workshop, and thank you for being part of this journey.</p>'
        '<p>— Pierre Azar<br><a href="mailto:contact@pierreazar.com">'
        'contact@pierreazar.com</a></p></body></html>'
    )
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f'{getattr(cfg, "SENDER_NAME", "Pierre Azar Website")} <{cfg.SMTP_USER}>'
    msg['To'] = email
    msg['Date'] = formatdate(timeval=None, localtime=False, usegmt=True)
    msg['Message-ID'] = f'<password-setup-{secrets.token_hex(8)}@pierreazar.com>'
    msg.attach(MIMEText(body_text, 'plain'))
    msg.attach(MIMEText(body_html, 'html'))
    sent_to = _smtp_send(msg, email)
    _log_email_ok(f'password_setup:{email}:{order_id}', ','.join(sent_to))
    return sent_to

def _issue_password_setup_email(order, base_url, receipt_url=None):
    email = _normalize_email(order.get('email'))
    order_id = str(order.get('order_id', '')).strip()
    raw_token = _create_password_setup_token(email, order_id)
    _send_password_setup_email(
        order.get('name', ''),
        email,
        raw_token,
        base_url,
        order_id=order_id,
        receipt_url=receipt_url,
    )
    return raw_token

def _send_premium_access_email(name, email, base_url, order_id='', receipt_url=None):
    login_url = f"{base_url.rstrip('/')}/member-login.html?next=/course"
    subject = "Welcome to the Cinematography Workshop!"
    receipt_line = f"\nDownload your receipt: {receipt_url}\n" if receipt_url else ''
    body_text = (
        f"Hi {name or email},\n\n"
        "Welcome to the Cinematography Workshop!\n\n"
        "Thank you for joining. I’m excited to have you here.\n\n"
        "This isn’t a traditional classroom course—it’s a practical workshop where you’ll "
        "learn the same techniques I use on professional film sets.\n\n"
        "Your workshop is ready.\n\n"
        f"Start watching here: {login_url}\n"
        f"{receipt_line}\n"
        "Enjoy the workshop, and thank you for being part of this journey.\n\n"
        "— Pierre Azar\n"
        "contact@pierreazar.com"
    )
    receipt_html = (
        f'<p><a href="{receipt_url}" style="color:#222;">Download your payment receipt</a></p>'
        if receipt_url else ''
    )
    body_html = (
        '<html><body style="font-family:Arial,sans-serif;color:#222;max-width:600px;">'
        f'<p>Hi {html.escape(name or email)},</p>'
        '<h2>Welcome to the Cinematography Workshop!</h2>'
        '<p>Thank you for joining. I’m excited to have you here.</p>'
        '<p>This isn’t a traditional classroom course—it’s a practical workshop where '
        'you’ll learn the same techniques I use on professional film sets.</p>'
        '<p><strong>Your workshop is ready.</strong></p>'
        f'<p><a href="{login_url}" style="background:#222;color:#fff;padding:12px 24px;'
        'text-decoration:none;border-radius:4px;display:inline-block;">Start Watching</a></p>'
        f'{receipt_html}'
        '<p>Enjoy the workshop, and thank you for being part of this journey.</p>'
        '<p>— Pierre Azar<br><a href="mailto:contact@pierreazar.com">'
        'contact@pierreazar.com</a></p></body></html>'
    )
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f'{getattr(cfg, "SENDER_NAME", "Pierre Azar Website")} <{cfg.SMTP_USER}>'
    msg['To'] = email
    msg['Date'] = formatdate(timeval=None, localtime=False, usegmt=True)
    msg['Message-ID'] = f'<premium-access-{secrets.token_hex(8)}@pierreazar.com>'
    msg.attach(MIMEText(body_text, 'plain'))
    msg.attach(MIMEText(body_html, 'html'))
    sent_to = _smtp_send(msg, email)
    _log_email_ok(f'premium_access:{email}:{order_id}', ','.join(sent_to))
    return sent_to

def _send_purchase_notification_email(order, cfg_data, payment_meta=None):
    """Notify Pierre Azar when a new course purchase is completed."""
    payment_meta = payment_meta or {}
    order_id = order.get('order_id', '')
    name = order.get('name', '')
    email = order.get('email', '')
    amount = _format_money(order.get('amount', cfg_data.get('course_price', 0)))
    currency = cfg_data.get('currency', 'USD')
    course = cfg_data.get('course_name', 'Cinematography Workshop')
    cybersource_id = payment_meta.get('cybersource_id') or order.get('cybersource_id', '')
    subject = f'New course purchase — {order_id}'
    body_text = (
        f'A new course purchase was completed on pierreazar.com.\n\n'
        f'Order: {order_id}\n'
        f'Customer: {name}\n'
        f'Email: {email}\n'
        f'Course: {course}\n'
        f'Amount: {amount} {currency}\n'
    )
    if cybersource_id:
        body_text += f'Cybersource ID: {cybersource_id}\n'
    body_text += f'\nAdmin sales: https://pierreazar.com/admin/course-sales.html\n'
    body_html = (
        '<html><body style="font-family:Arial,sans-serif;color:#222;max-width:600px;">'
        '<h2 style="margin:0 0 12px;">New course purchase</h2>'
        '<table style="width:100%;border-collapse:collapse;">'
        f'<tr><td style="padding:6px 0;color:#666;">Order</td><td>{order_id}</td></tr>'
        f'<tr><td style="padding:6px 0;color:#666;">Customer</td><td>{name}</td></tr>'
        f'<tr><td style="padding:6px 0;color:#666;">Email</td><td><a href="mailto:{email}">{email}</a></td></tr>'
        f'<tr><td style="padding:6px 0;color:#666;">Course</td><td>{course}</td></tr>'
        f'<tr><td style="padding:6px 0;color:#666;">Amount</td><td><strong>{amount} {currency}</strong></td></tr>'
    )
    if cybersource_id:
        body_html += f'<tr><td style="padding:6px 0;color:#666;">Cybersource ID</td><td>{cybersource_id}</td></tr>'
    body_html += (
        '</table>'
        '<p style="margin-top:20px;">'
        '<a href="https://pierreazar.com/admin/course-sales.html" '
        'style="background:#222;color:#fff;padding:10px 18px;text-decoration:none;border-radius:4px;">'
        'View in admin</a></p>'
        '</body></html>'
    )
    to_addr = (getattr(cfg, 'NOTIFY_EMAIL', None) or cfg.RECIPIENT_EMAIL).strip()
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    # Match contact-form headers (those already deliver to Pierre).
    msg['From'] = f'{getattr(cfg, "SENDER_NAME", "Pierre Azar Website")} <{cfg.SMTP_USER}>'
    msg['To'] = to_addr
    if email:
        msg['Reply-To'] = email
    msg['Date'] = formatdate(timeval=None, localtime=False, usegmt=True)
    msg['Message-ID'] = f'<purchase-{order_id}-{secrets.token_hex(6)}@pierreazar.com>'
    msg.attach(MIMEText(body_text, 'plain'))
    msg.attach(MIMEText(body_html, 'html'))
    sent_to = _smtp_send(msg, to_addr, include_notify_cc=True)
    _log_email_ok(f'purchase_notify:{order_id}', ','.join(sent_to))
    return sent_to

def _send_activation_email(name, email, code, base_url):
    """Send the one-time activation code to the buyer."""
    activate_url = f"{base_url.rstrip('/')}/member/activate"
    subject = "Your Cinematography Workshop — Activation Code"
    body_text = (
        f"Hi {name or email},\n\n"
        f"Thank you for your purchase! Use the code below to activate your full course access:\n\n"
        f"    {code}\n\n"
        f"Go to: {activate_url}\n"
        f"Log in if prompted, then enter the code above.\n\n"
        f"This code is one-time use only. It will bind your access to the device you activate from.\n\n"
        f"Pierre Azar"
    )
    body_html = (
        '<html><body style="font-family:Arial,sans-serif;color:#222;max-width:600px;">'
        f'<p>Hi {name or email},</p>'
        f'<p>Thank you for your purchase! Use the code below to activate your full course access:</p>'
        f'<div style="background:#f5f5f5;border:2px dashed #ccc;border-radius:8px;'
        f'padding:20px;text-align:center;margin:24px 0;">'
        f'<p style="font-size:11px;color:#888;letter-spacing:.1em;margin-bottom:8px;">ACTIVATION CODE</p>'
        f'<p style="font-size:36px;font-weight:700;letter-spacing:.15em;color:#111;">'
        f'{code}</p></div>'
        f'<p><a href="{activate_url}" style="background:#222;color:#fff;padding:12px 24px;'
        f'text-decoration:none;border-radius:4px;display:inline-block;">Activate My Access</a></p>'
        f'<p style="color:#888;font-size:13px;">Or visit: {activate_url}</p>'
        f'<hr style="border:none;border-top:1px solid #eee;">'
        f'<p style="color:#888;font-size:12px;">This code is one-time use only. '
        f'It will bind your course access to the device you activate from.</p>'
        f'<p>Pierre Azar</p>'
        '</body></html>'
    )
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From']    = f'{getattr(cfg, "SENDER_NAME", "Pierre Azar Website")} <{cfg.SMTP_USER}>'
    msg['To']      = email
    msg['Date'] = formatdate(timeval=None, localtime=False, usegmt=True)
    msg['Message-ID'] = f'<activation-{secrets.token_hex(8)}@pierreazar.com>'
    msg.attach(MIMEText(body_text, 'plain'))
    msg.attach(MIMEText(body_html, 'html'))
    sent_to = _smtp_send(msg, email)
    _log_email_ok(f'activation_email:{email}', ','.join(sent_to))

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

def _send_course_access_email(name, email, token, base_url, receipt_url=None):
    """Send the course access link to the buyer."""
    link = f"{base_url.rstrip('/')}/course?token={token}"
    subject = "Your Cinematography Workshop Access"
    receipt_line = f"\nDownload your receipt: {receipt_url}\n" if receipt_url else ''
    body_text = (
        f"Hi {name},\n\n"
        f"Thank you for your purchase! Here is your personal access link:\n\n"
        f"{link}\n"
        f"{receipt_line}\n"
        f"IMPORTANT: This link is personal and non-transferable.\n"
        f"It can only be used from up to {COURSE_MAX_IPS} different devices.\n"
        f"Do not share it — sharing will lock your access.\n\n"
        f"Pierre Azar"
    )
    receipt_html = ''
    if receipt_url:
        receipt_html = (
            f'<p><a href="{receipt_url}" style="color:#222;">Download your payment receipt</a></p>'
        )
    body_html = (
        '<html><body style="font-family:Arial,sans-serif;color:#222;max-width:600px;">'
        f'<p>Hi {name},</p>'
        f'<p>Thank you for your purchase! Here is your personal access link:</p>'
        f'<p><a href="{link}" style="background:#222;color:#fff;padding:12px 24px;'
        f'text-decoration:none;border-radius:4px;display:inline-block;">Access Your Course</a></p>'
        f'<p style="color:#888;font-size:13px;">Or copy this link: {link}</p>'
        f'{receipt_html}'
        f'<hr style="border:none;border-top:1px solid #eee;">'
        f'<p style="color:#c00;font-size:13px;"><strong>Important:</strong> This link is personal '
        f'and non-transferable. It can only be used from up to {COURSE_MAX_IPS} different devices. '
        f'Do not share it — sharing will lock your access.</p>'
        f'<p>Pierre Azar</p>'
        '</body></html>'
    )
    msg = MIMEMultipart("alternative")
    msg["Subject"]  = subject
    msg["From"]     = f'{getattr(cfg, "SENDER_NAME", "Pierre Azar Website")} <{cfg.SMTP_USER}>'
    msg["To"]       = email
    msg["Date"] = formatdate(timeval=None, localtime=False, usegmt=True)
    msg["Message-ID"] = f'<course-access-{secrets.token_hex(8)}@pierreazar.com>'
    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))
    sent_to = _smtp_send(msg, email)
    _log_email_ok(f'course_access_email:{email}', ','.join(sent_to))
    return sent_to

# ── Coupon helpers ───────────────────────────────────────────────────────────
def _generate_coupon_code():
    """Generate a branded coupon code like INDIGO-A3F9K2."""
    chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    suffix = ''.join(secrets.choice(chars) for _ in range(6))
    return f'INDIGO-{suffix}'

def _find_coupon(code):
    """Return the coupon dict if active, not expired, and has uses remaining, else None."""
    from datetime import date, timedelta
    coupons = _read_json(COUPONS_FILE)
    code = code.strip().upper()
    today = date.today()
    for c in coupons:
        if c.get('code', '').upper() != code:
            continue
        if not c.get('active', True):
            return None
        # Expiry: 30 days after creation date
        created_str = c.get('created', '')
        if created_str:
            try:
                created_date = date.fromisoformat(created_str[:10])
                if today > created_date + timedelta(days=30):
                    return None  # expired
            except ValueError:
                pass
        max_uses = c.get('max_uses', 1)
        uses     = c.get('uses', 0)
        if max_uses == 0 or uses < max_uses:
            return c
    return None

def _use_coupon(code):
    """Increment usage counter for the coupon. Call after payment confirmed."""
    coupons = _read_json(COUPONS_FILE)
    code = code.strip().upper()
    for c in coupons:
        if c.get('code', '').upper() == code:
            c['uses'] = c.get('uses', 0) + 1
            max_uses  = c.get('max_uses', 1)
            if max_uses > 0 and c['uses'] >= max_uses:
                c['active'] = False
            break
    _write_json(COUPONS_FILE, coupons)

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

    sent_to = _smtp_send(msg, cfg.RECIPIENT_EMAIL, include_notify_cc=True)
    _log_email_ok(f'contact_form:{sender_email}', ','.join(sent_to))
    return sent_to


def _send_contact_confirmation_email(name, email, message):
    """Confirm to the submitting client that their message was received."""
    safe_name = html.escape(name or email)
    safe_message = html.escape(message).replace('\n', '<br>')
    subject = "We received your message — Pierre Azar"
    body_text = (
        f"Hi {name or email},\n\n"
        "Thank you for contacting Pierre Azar. Your message has been received "
        "and we will get back to you as soon as possible.\n\n"
        f"Your message:\n{message}\n\n"
        "Pierre Azar"
    )
    body_html = (
        '<html><body style="font-family:Arial,sans-serif;color:#222;max-width:600px;">'
        f'<p>Hi {safe_name},</p>'
        '<p>Thank you for contacting Pierre Azar. Your message has been received '
        'and we will get back to you as soon as possible.</p>'
        '<div style="margin:20px 0;padding:16px;background:#f5f5f5;border-left:3px solid #222;">'
        f'{safe_message}</div>'
        '<p>Pierre Azar</p>'
        '</body></html>'
    )
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{cfg.SENDER_NAME} <{cfg.SMTP_USER}>"
    msg["To"] = email
    msg["Date"] = formatdate(timeval=None, localtime=False, usegmt=True)
    msg["Message-ID"] = f"<contact-confirmation-{secrets.token_hex(8)}@pierreazar.com>"
    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))
    sent_to = _smtp_send(msg, email)
    _log_email_ok(f'contact_confirmation:{email}', ','.join(sent_to))
    return sent_to


# ── Request Handler ──────────────────────────────────────────────────────────
_PAYMENT_CSP = (
    "default-src 'self'; "
    "script-src 'self' https://up.cybersource.com https://flex.cybersource.com "
    "https://testup.cybersource.com https://testflex.cybersource.com; "
    "style-src 'self' 'unsafe-inline' https://up.cybersource.com https://flex.cybersource.com "
    "https://testup.cybersource.com https://testflex.cybersource.com; "
    "style-src-elem 'self' 'unsafe-inline' https://up.cybersource.com https://flex.cybersource.com "
    "https://testup.cybersource.com https://testflex.cybersource.com; "
    "frame-src 'self' https://up.cybersource.com https://flex.cybersource.com "
    "https://testup.cybersource.com https://testflex.cybersource.com "
    "https://*.cardinalcommerce.com https://cas.client.cardinaltrusted.com; "
    "connect-src 'self' https://up.cybersource.com https://flex.cybersource.com "
    "https://testup.cybersource.com https://testflex.cybersource.com "
    "https://*.cardinalcommerce.com; "
    "img-src 'self' data: https:; "
    "font-src 'self' data: https:;"
)

class Handler(http.server.SimpleHTTPRequestHandler):

    # ---- static asset caching ----

    def send_head(self):
        """Add long-lived Cache-Control for static assets."""
        path = urllib.parse.urlparse(self.path).path.lower()
        ext = os.path.splitext(path)[1]
        f = super().send_head()
        return f

    def end_headers(self):
        path = urllib.parse.urlparse(self.path).path.lower()
        ext = os.path.splitext(path)[1]
        if path in ('/payment-checkout.html', '/payment-checkout.js', '/payment-checkout.css'):
            self.send_header('Content-Security-Policy', _PAYMENT_CSP)
        if ext in ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.ico',
                   '.woff', '.woff2', '.ttf', '.otf'):
            self.send_header('Cache-Control', 'public, max-age=86400, must-revalidate')
        elif ext in ('.css', '.js'):
            self.send_header('Cache-Control', 'public, max-age=86400')
        elif ext == '.html':
            self.send_header('Cache-Control', 'no-store')
        super().end_headers()

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
                'for security. Please email <a href="mailto:contact@pierreazar.com">contact@pierreazar.com</a> '
                'and we will reset your access within 24 hours.'
                '</div>'
            )
            cta_label = 'Contact Pierre'
            cta_href  = 'mailto:contact@pierreazar.com'
        else:
            note = (
                '<div class="alert alert-info">'
                + message +
                '</div>'
            )
            cta_label = 'Get Access — Enroll Now'
            cfg_data  = get_payment_config()
            cta_href  = '/cinematography-course.html#checkout' if cfg_data.get('enabled') else '/cinematography-course.html'
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
            '<h1>Cinematography Workshop</h1>'
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
            '<footer>Questions? <a href="mailto:contact@pierreazar.com" '
            'style="color:#555;">contact@pierreazar.com</a></footer>'
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
                _reload_cm()
                self._json_response(
                    {'ok': True, 'content': cm.get_all()},
                    extra_headers={'Cache-Control': 'no-store, no-cache, must-revalidate', 'Pragma': 'no-cache'},
                )
            except Exception as e:
                self._json_response({'ok': False, 'error': str(e)}, status=500)
            return

        if path == '/api/images':
            if not self._require_auth():
                return
            self._json_response({'ok': True, 'images': cm.list_images()})
            return

        if path == '/api/page-images':
            if not self._require_auth():
                return
            qs = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
            page = qs.get('page', '')
            allowed = ['index.html', 'portfolio.html', 'onset-experience.html',
                       'get-in-touch.html', 'cinematography-course.html']
            if page not in allowed:
                self._json_response({'ok': False, 'error': 'Invalid page'}, status=400)
                return
            imgs = cm.get_page_images(page)
            self._json_response({'ok': True, 'page': page, 'images': imgs})
            return

        if path == '/api/page-videos':
            if not self._require_auth():
                return
            qs = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
            page = qs.get('page', '')
            allowed = ['index.html', 'portfolio.html', 'onset-experience.html',
                       'get-in-touch.html', 'cinematography-course.html']
            if page not in allowed:
                self._json_response({'ok': False, 'error': 'Invalid page'}, status=400)
                return
            vids = cm.get_page_videos(page)
            self._json_response({'ok': True, 'page': page, 'videos': vids})
            return

        if path == '/api/payment-config':
            if not self._require_auth():
                return
            self._json_response({'ok': True, 'config': _masked_config(get_payment_config())})
            return

        # ---- Admin: list coupons ----
        if path == '/api/coupons':
            if not self._require_auth():
                return
            self._json_response({'ok': True, 'coupons': _read_json(COUPONS_FILE)})
            return

        # ---- Public: payment receipt ----
        if path == '/api/receipt':
            qs = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
            order_id = str(qs.get('order', '')).strip()
            key = str(qs.get('key', '')).strip()
            token = str(qs.get('token', '')).strip()
            order = None
            if order_id and key:
                candidate = _find_paid_order(order_id)
                if candidate and secrets.compare_digest(_receipt_access_key(order_id, candidate.get('email', '')), key):
                    order = candidate
            elif token:
                order = _order_from_course_token(token)
            if not order:
                self.send_response(404)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(b'<h1>Receipt not found</h1><p>Invalid or expired receipt link.</p>')
                return
            html = _build_receipt_html(order, get_payment_config()).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(html)))
            if qs.get('download') == '1':
                fname = f'receipt-{order.get("order_id", "order")}.html'
                self.send_header('Content-Disposition', f'attachment; filename="{fname}"')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(html)
            return

        # ---- Public: validate a coupon ----
        if path == '/api/validate-coupon':
            qs   = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
            code = qs.get('code', '').strip().upper()
            if not code:
                self._json_response({'ok': False, 'error': 'No code provided'}, status=400)
                return
            coupon = _find_coupon(code)
            if coupon:
                self._json_response({'ok': True, 'discount_pct': coupon.get('discount_pct', 50), 'code': coupon['code']})
            else:
                self._json_response({'ok': False, 'error': 'Invalid or expired coupon'}, status=404)
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
                cfg_data = get_payment_config()
                result_info = _finalize_paid_order(order_id, cfg_data, gateway_name='areeba')
                self.send_response(302)
                self.send_header('Location', result_info.get('redirect', '/payment-failed.html'))
                self.end_headers()
            else:
                self.send_response(302)
                self.send_header('Location', '/payment-failed.html')
                self.end_headers()
            return

        # ---- Demo payment page ----
        if path == '/payment-demo':
            qs     = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
            order  = qs.get('order', 'DEMO')
            name   = qs.get('name', 'Test User')
            amount = qs.get('amount', '99')
            html = (
                '<!DOCTYPE html><html lang="en"><head>'
                '<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                '<title>Secure Payment — Areeba</title>'
                '<style>'
                '*{box-sizing:border-box;margin:0;padding:0;}'
                'body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;'
                'background:#f4f6f9;min-height:100vh;display:flex;align-items:center;'
                'justify-content:center;padding:20px;}'
                '.card{background:#fff;border-radius:10px;box-shadow:0 4px 24px rgba(0,0,0,.1);'
                'max-width:420px;width:100%;overflow:hidden;}'
                '.header{background:#1a1a2e;padding:18px 24px;display:flex;align-items:center;justify-content:space-between;}'
                '.header-brand{color:#fff;font-size:18px;font-weight:700;letter-spacing:.02em;}'
                '.header-secure{display:flex;align-items:center;gap:6px;color:#8892b0;font-size:12px;}'
                '.demo-banner{background:#fff8e1;border-bottom:1px solid #ffe082;padding:8px 24px;'
                'font-size:12px;color:#795548;display:flex;align-items:center;gap:6px;}'
                '.body{padding:24px;}'
                '.merchant-row{display:flex;align-items:center;gap:12px;margin-bottom:20px;'
                'padding-bottom:16px;border-bottom:1px solid #eee;}'
                '.merchant-icon{width:40px;height:40px;background:#1a1a2e;border-radius:8px;'
                'display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;font-size:16px;}'
                '.merchant-name{font-weight:700;font-size:15px;color:#1a1a2e;}'
                '.merchant-sub{font-size:12px;color:#888;margin-top:2px;}'
                '.amount-row{text-align:center;margin-bottom:22px;}'
                '.amount-label{font-size:12px;color:#888;text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px;}'
                '.amount-val{font-size:32px;font-weight:700;color:#1a1a2e;}'
                '.amount-currency{font-size:16px;font-weight:400;color:#888;margin-left:4px;}'
                'label{display:block;font-size:12px;font-weight:600;color:#555;margin-bottom:6px;margin-top:14px;}'
                'input[type=text],input[type=tel]{width:100%;border:1.5px solid #ddd;border-radius:6px;'
                'padding:11px 14px;font-size:15px;color:#1a1a2e;outline:none;transition:border-color .2s;}'
                'input[type=text]:focus,input[type=tel]:focus{border-color:#1a1a2e;}'
                '.row-2{display:flex;gap:12px;}'
                '.row-2>div{flex:1;}'
                '.pay-btn{display:block;width:100%;margin-top:22px;padding:14px;'
                'background:#1a1a2e;color:#fff;font-weight:700;font-size:15px;'
                'border:none;border-radius:6px;cursor:pointer;transition:background .2s;}'
                '.pay-btn:hover{background:#2d2d4e;}'
                '.fail-link{display:block;text-align:center;margin-top:12px;font-size:13px;'
                'color:#e74c3c;cursor:pointer;background:none;border:none;width:100%;}'
                '.footer{padding:14px 24px;border-top:1px solid #eee;display:flex;align-items:center;'
                'justify-content:center;gap:8px;color:#aaa;font-size:11px;}'
                '.card-icons{display:flex;gap:6px;margin-top:8px;}'
                '.card-icon{background:#f4f6f9;border:1px solid #ddd;border-radius:4px;'
                'padding:3px 8px;font-size:11px;font-weight:700;color:#555;}'
                '</style></head><body>'
                '<div class="card">'
                '<div class="header">'
                '<span class="header-brand">areeba</span>'
                '<span class="header-secure">'
                '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>'
                'Secure Payment'
                '</span>'
                '</div>'
                '<div class="demo-banner">'
                '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>'
                'DEMO MODE — No real charge will be made'
                '</div>'
                '<div class="body">'
                '<div class="merchant-row">'
                '<div class="merchant-icon">P</div>'
                '<div><div class="merchant-name">Pierre Azar</div>'
                '<div class="merchant-sub">pierreazar.com</div></div>'
                '</div>'
                '<div class="amount-row">'
                '<div class="amount-label">Amount Due</div>'
                f'<div class="amount-val">${amount}<span class="amount-currency">USD</span></div>'
                '</div>'
                '<div class="card-icons">'
                '<span class="card-icon">VISA</span>'
                '<span class="card-icon">MC</span>'
                '<span class="card-icon">AMEX</span>'
                '</div>'
                '<label>Card Number</label>'
                '<input type="tel" id="cn" placeholder="0000 0000 0000 0000" maxlength="19" '
                'oninput="var v=this.value.replace(/\D/g,\'\').substring(0,16);this.value=v.replace(/(.{4})/g,\'$1 \').trim();">'
                '<label>Name on Card</label>'
                f'<input type="text" id="ch" value="{name}" placeholder="Name as on card">'
                '<div class="row-2">'
                '<div><label>Expiry Date</label>'
                '<input type="tel" id="exp" placeholder="MM / YY" maxlength="7" '
                'oninput="var v=this.value.replace(/\D/g,\'\').substring(0,4);if(v.length>=2)v=v.substring(0,2)+\' / \'+v.substring(2);this.value=v;"></div>'
                '<div><label>CVV</label>'
                '<input type="tel" id="cvv" placeholder="•••" maxlength="4" '
                'oninput="this.value=this.value.replace(/\D/g,\'\')"></div>'
                '</div>'
                f'<button class="pay-btn" onclick="doPay()">Pay ${amount} USD</button>'
                '<button class="fail-link" onclick="doFail()">Decline / Cancel</button>'
                '</div>'
                '<div class="footer">'
                '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>'
                'Payments secured by Areeba MPGS'
                '</div>'
                '</div>'
                '<script>'
                'function doPay(){'
                '  var cn=document.getElementById("cn").value.replace(/\s/g,"");'
                '  var exp=document.getElementById("exp").value;'
                '  var cvv=document.getElementById("cvv").value;'
                '  if(cn.length<15||!exp||cvv.length<3){'
                '    alert("Please fill in all card details.");return;}'
                f'  window.location.href="/payment-success.html?demo=1&order={order}";'
                '}'
                f'function doFail(){{window.location.href="/payment-failed.html?demo=1";}}'
                '</script>'
                '</body></html>'
            ).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(html)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(html)
            return

        # ---- Member: who am I ----
        if path == '/member/me':
            email = _get_member_session(self.headers.get('Cookie', ''))
            if email:
                members = _read_json(MEMBERS_FILE)
                member  = next((m for m in members if m.get('email') == email), {})
                if member.get('active', True):
                    self._json_response({
                        'ok':           True,
                        'email':        email,
                        'name':         member.get('name', ''),
                        'premium':      member.get('premium', False),
                        'premium_since': member.get('premium_since', ''),
                    })
                else:
                    self._json_response({'ok': False})
            else:
                # Keep guest checks quiet in browser Network panel.
                self._json_response({'ok': False})
            return

        # ---- Course: signed Bunny chapter URLs ----
        if path == '/api/course-promo-embed':
            self._json_response(_resolve_course_promo_embed())
            return

        if path == '/api/course-videos':
            # Access allowed for premium member session or valid token query.
            member_email = _get_member_session(self.headers.get('Cookie', ''))
            has_access = False
            if member_email:
                members = _read_json(MEMBERS_FILE)
                member = next((m for m in members if m.get('email') == member_email), {})
                has_access = bool(
                    member.get('active', True) and member.get('premium', False)
                )
            else:
                qs = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
                token = qs.get('token', '').strip()
                client_ip = (
                    self.headers.get('X-Forwarded-For', '').split(',')[0].strip()
                    or self.headers.get('X-Real-IP', '')
                    or self.client_address[0]
                )
                if token:
                    ok, _ = _validate_course_token(token, client_ip)
                    has_access = ok
            if not has_access:
                self._json_response({'ok': False, 'error': 'Unauthorized'}, status=401)
                return

            library_id, videos = _parse_bunny_course_config()
            token_key = _read_bunny_token_key()
            if not library_id or not videos:
                self._json_response({'ok': False, 'error': 'Bunny course is not configured'})
                return
            if not token_key:
                self._json_response({'ok': False, 'error': 'Bunny token key is missing'})
                return

            expires  = int(time.time()) + (60 * 60 * 6)  # 6-hour signed URL
            chapters = []
            for idx, v in enumerate(videos):
                embed_url = _build_bunny_embed_url(library_id, v['video_id'], token_key, expires)
                embed_url += '&autoplay=true&preload=true'
                chapters.append({
                    'title': v.get('title') or f'Chapter {idx + 1}',
                    'video_id': v['video_id'],
                    'embed_url': embed_url,
                    'duration': ''
                })
            self._json_response({'ok': True, 'library_id': library_id, 'chapters': chapters})
            return

        # ---- Member: upgrade page ----
        if path == '/member/upgrade':
            upgrade_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'member-upgrade.html')
            try:
                with open(upgrade_file, 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(content)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(content)
            except FileNotFoundError:
                self.send_response(404)
                self.end_headers()
            return

        # ---- Member: activate page ----
        if path == '/member/activate':
            activate_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'member-activate.html')
            try:
                with open(activate_file, 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(content)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(content)
            except FileNotFoundError:
                self.send_response(404)
                self.end_headers()
            return

        # ---- Member: password setup page ----
        if path == '/member/set-password':
            setup_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'member-set-password.html')
            try:
                with open(setup_file, 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(content)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Referrer-Policy', 'no-referrer')
                self.end_headers()
                self.wfile.write(content)
            except FileNotFoundError:
                self.send_response(404)
                self.end_headers()
            return

        # ---- Course access (token-gated OR member session) ----
        if path == '/course':
            # Allow access via member session cookie — only if premium
            member_email = _get_member_session(self.headers.get('Cookie', ''))
            if member_email:
                members = _read_json(MEMBERS_FILE)
                member  = next((m for m in members if m.get('email') == member_email), {})
                if not member.get('active', True):
                    self._serve_course_error(
                        'This member account is disabled. Please contact '
                        '<a href="mailto:contact@pierreazar.com">contact@pierreazar.com</a>.'
                    )
                    return
                if not member.get('premium', False):
                    # Not premium yet — redirect to upgrade page
                    self.send_response(302)
                    self.send_header('Location', '/member/upgrade')
                    self.end_headers()
                    return
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

        # ---- Admin: list members ----
        if path == '/api/admin/members':
            if not self._require_auth():
                return
            members = _read_json(MEMBERS_FILE)
            safe = [
                {
                    'email':         m.get('email'),
                    'name':          m.get('name', ''),
                    'created_at':    m.get('created_at'),
                    'last_login':    m.get('last_login', ''),
                    'active':        m.get('active', True),
                    'premium':       m.get('premium', False),
                    'premium_since': m.get('premium_since', ''),
                }
                for m in members
            ]
            self._json_response({'ok': True, 'members': safe})
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

                email_sent = False
                email_error = None
                confirmation_sent = False
                confirmation_error = None
                if cfg.SMTP_USER and cfg.SMTP_PASS:
                    try:
                        send_email(name, email, message)
                        email_sent = True
                    except Exception as mail_err:
                        email_error = str(mail_err)
                    try:
                        _send_contact_confirmation_email(name, email, message)
                        confirmation_sent = True
                    except Exception as confirmation_err:
                        confirmation_error = str(confirmation_err)

                self._json_response({
                    'ok': True,
                    'saved': True,
                    'email_sent': email_sent,
                    'email_error': email_error,
                    'confirmation_sent': confirmation_sent,
                    'confirmation_error': confirmation_error,
                })
            except ValueError as e:
                self._json_response({'ok': False, 'error': str(e)})
            except Exception as e:
                self._json_response({'ok': False, 'error': str(e)})
            return

        # ---- Member: complete paid-buyer password setup ----
        if path == '/member/setup-password':
            body = self._read_body()
            try:
                data = json.loads(body) if body else {}
                raw_token = str(data.get('token', '')).strip()
                password = str(data.get('password', ''))
                if not raw_token:
                    raise ValueError('Setup token is required')
                member = _consume_password_setup_token(raw_token, password)
                session_token = _create_member_session(member.get('email'))
                self._json_response(
                    {'ok': True, 'redirect': '/course'},
                    extra_headers={
                        'Set-Cookie': f'pa_member={session_token}; Path=/; HttpOnly; '
                        'SameSite=Strict; Secure; Max-Age=2592000'
                    }
                )
            except ValueError as e:
                self._json_response({'ok': False, 'error': str(e)}, status=400)
            except Exception as e:
                self._json_response({'ok': False, 'error': 'Could not set password'}, status=500)
                _log_email_error('password_setup_complete', e)
            return

        # ---- Member: resend paid-buyer password setup link ----
        if path == '/member/resend-setup':
            body = self._read_body()
            try:
                data = json.loads(body) if body else {}
                email = _normalize_email(data.get('email'))[:200]
                if email and _EMAIL_RE.match(email):
                    members = _read_json(MEMBERS_FILE)
                    member = next(
                        (m for m in members if _normalize_email(m.get('email')) == email),
                        None,
                    )
                    order = _find_verified_paid_order_for_email(email)
                    if (
                        member
                        and member.get('premium')
                        and member.get('active', True)
                        and member.get('password_pending')
                        and order
                        and _setup_resend_allowed(email)
                    ):
                        _issue_password_setup_email(
                            order,
                            get_payment_config().get('return_base_url', 'https://pierreazar.com'),
                        )
                # Always return the same response to avoid disclosing membership.
                self._json_response({
                    'ok': True,
                    'message': 'If this email has a paid account, a setup link has been sent.',
                })
            except Exception as e:
                _log_email_error('password_setup_resend', e)
                self._json_response({
                    'ok': True,
                    'message': 'If this email has a paid account, a setup link has been sent.',
                })
            return

        # ---- Member: register ----
        if path == '/member/register':
            body = self._read_body()
            try:
                data     = json.loads(body)
                email    = str(data.get('email', '')).strip().lower()[:200]
                password = str(data.get('password', ''))
                name     = str(data.get('name', '')).strip()[:200]
                if not email or not _EMAIL_RE.match(email):
                    raise ValueError('Valid email is required')
                if len(password) < 8:
                    raise ValueError('Password must be at least 8 characters')
                members = _read_json(MEMBERS_FILE)
                existing = next((m for m in members if _normalize_email(m.get('email')) == email), None)
                if existing:
                    response = {'ok': False, 'error': 'Email already registered'}
                    if existing.get('password_pending'):
                        response['setup_required'] = True
                        response['error'] = 'A paid account exists for this email. Request a password setup link.'
                    self._json_response(response, status=409)
                    return
                members.append({
                    'email':        email,
                    'name':         name,
                    'password':     _hash_password(password),
                    'created_at':   datetime.now(timezone.utc).isoformat(),
                    'last_login':   '',
                    'active':       True,
                    'premium':      False,
                    'premium_since': '',
                })
                _write_json(MEMBERS_FILE, members)
                # Auto-login after registration
                token = _create_member_session(email)
                self._json_response(
                    {'ok': True},
                    extra_headers={
                        'Set-Cookie': f'pa_member={token}; Path=/; HttpOnly; SameSite=Strict; Secure; Max-Age=2592000'
                    }
                )
            except ValueError as e:
                self._json_response({'ok': False, 'error': str(e)}, status=400)
            except Exception as e:
                self._json_response({'ok': False, 'error': str(e)}, status=500)
            return

        # ---- Member: activate (redeem one-time code) ----
        if path == '/member/activate':
            member_email = _get_member_session(self.headers.get('Cookie', ''))
            if not member_email:
                self._json_response({'ok': False, 'error': 'Not logged in'}, status=401)
                return
            body = self._read_body()
            try:
                data = json.loads(body)
                raw  = str(data.get('code', '')).strip().upper().replace(' ', '')
                # Accept with or without dash
                if len(raw) == 8:
                    raw = raw[:4] + '-' + raw[4:]
                codes = _read_json(ACTIVATION_CODES_FILE)
                entry = next((c for c in codes
                              if c.get('code') == raw
                              and c.get('email') == member_email
                              and not c.get('used')), None)
                if not entry:
                    self._json_response({'ok': False, 'error': 'Invalid or already used code.'}, status=400)
                    return
                # Mark code used
                entry['used']    = True
                entry['used_at'] = datetime.now(timezone.utc).isoformat()
                _write_json(ACTIVATION_CODES_FILE, codes)
                # Get client IP and mark member premium
                client_ip = (
                    self.headers.get('X-Forwarded-For', '').split(',')[0].strip()
                    or self.headers.get('X-Real-IP', '')
                    or self.client_address[0]
                )
                paid_at = entry.get('created_at', datetime.now(timezone.utc).isoformat())
                members = _read_json(MEMBERS_FILE)
                for m in members:
                    if m.get('email') == member_email:
                        m['premium']        = True
                        m['premium_since']  = paid_at
                        m['activated_ip']   = client_ip
                _write_json(MEMBERS_FILE, members)
                self._json_response({'ok': True})
            except Exception as e:
                self._json_response({'ok': False, 'error': str(e)}, status=500)
            return

        # ---- Member: login ----
        if path == '/member/login':
            body = self._read_body()
            try:
                data     = json.loads(body)
                email    = str(data.get('email', '')).strip().lower()[:200]
                password = str(data.get('password', ''))
                members  = _read_json(MEMBERS_FILE)
                member   = next((m for m in members if _normalize_email(m.get('email')) == email), None)
                if member and not member.get('active', True):
                    self._json_response({'ok': False, 'error': 'Account is disabled'}, status=403)
                    return
                if member and member.get('password_pending'):
                    self._json_response({
                        'ok': False,
                        'error': 'Create your password using the link sent after purchase.',
                        'setup_required': True,
                    }, status=403)
                    return
                if not member or not _verify_password(password, member.get('password', '')):
                    self._json_response({'ok': False, 'error': 'Invalid email or password'}, status=401)
                    return
                # Update last_login
                for m in members:
                    if m.get('email') == email:
                        m['last_login'] = datetime.now(timezone.utc).isoformat()
                _write_json(MEMBERS_FILE, members)
                token = _create_member_session(email)
                self._json_response(
                    {'ok': True},
                    extra_headers={
                        'Set-Cookie': f'pa_member={token}; Path=/; HttpOnly; SameSite=Strict; Secure; Max-Age=2592000'
                    }
                )
            except Exception as e:
                self._json_response({'ok': False, 'error': str(e)}, status=500)
            return

        # ---- Member: logout ----
        if path == '/member/logout':
            cookie = self.headers.get('Cookie', '')
            for part in cookie.split(';'):
                part = part.strip()
                if part.startswith('pa_member='):
                    token = part[len('pa_member='):]
                    _member_sessions.pop(token, None)
            _save_sessions(MEMBER_SESSIONS_FILE, _member_sessions)
            self._json_response(
                {'ok': True},
                extra_headers={
                    'Set-Cookie': 'pa_member=; Path=/; HttpOnly; SameSite=Strict; Secure; Max-Age=0'
                }
            )
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
                    _save_sessions(ADMIN_SESSIONS_FILE, _sessions)
                    self._json_response(
                        {'ok': True},
                        extra_headers={
                            'Set-Cookie': f'pa_admin={token}; Path=/; HttpOnly; SameSite=Strict; Secure; Max-Age=2592000'
                        }
                    )
                else:
                    self._json_response({'ok': False, 'error': 'Invalid credentials'}, status=401)
            except Exception as e:
                self._json_response({'ok': False, 'error': str(e)}, status=400)
            return

        # ---- Admin change password ----
        if path == '/admin/change-password':
            if not self._require_auth():
                return
            body = self._read_body()
            try:
                data         = json.loads(body)
                current_pass = str(data.get('current_password', ''))
                new_pass     = str(data.get('new_password', ''))
                # Validate current password
                ok_pass = secrets.compare_digest(
                    hashlib.sha256(current_pass.encode()).hexdigest(),
                    hashlib.sha256(cfg.ADMIN_PASS.encode()).hexdigest()
                )
                if not ok_pass:
                    self._json_response({'ok': False, 'error': 'Current password is incorrect'}, status=403)
                    return
                if len(new_pass) < 8:
                    self._json_response({'ok': False, 'error': 'New password must be at least 8 characters'}, status=400)
                    return
                # Write new password to mail_config.py
                cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mail_config.py')
                with open(cfg_path, 'r', encoding='utf-8') as f:
                    cfg_text = f.read()
                # Replace ADMIN_PASS line
                import re as _re
                cfg_text = _re.sub(
                    r'^(ADMIN_PASS\s*=\s*)["\'].*?["\']',
                    lambda m: m.group(1) + json.dumps(new_pass),
                    cfg_text, flags=_re.MULTILINE
                )
                with open(cfg_path, 'w', encoding='utf-8') as f:
                    f.write(cfg_text)
                # Reload cfg module so new password takes effect immediately
                import importlib
                importlib.reload(cfg)
                self._json_response({'ok': True})
            except Exception as e:
                self._json_response({'ok': False, 'error': str(e)}, status=500)
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
                course = str(data.get('course', 'Cinematography Workshop')).strip()[:200]
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

        # ---- Admin: add portfolio video ----
        if path == '/api/portfolio/add-video':
            if not self._require_auth():
                return
            body = self._read_body()
            try:
                _reload_cm()
                data = json.loads(body) if body else {}
                video_url = data.get('video_url', '').strip()
                if not video_url:
                    self._json_response({'ok': False, 'error': 'video_url required'}, status=400)
                    return
                field = cm.add_portfolio_video(video_url)
                self._json_response({'ok': True, 'field': field})
            except Exception as e:
                self._json_response({'ok': False, 'error': str(e)}, status=400)
            return

        # ---- Admin: delete portfolio video ----
        if path == '/api/portfolio/delete-video':
            if not self._require_auth():
                return
            body = self._read_body()
            try:
                _reload_cm()
                data = json.loads(body) if body else {}
                index = int(data.get('index', -1))
                cm.delete_portfolio_video(index)
                self._json_response({'ok': True})
            except Exception as e:
                self._json_response({'ok': False, 'error': str(e)}, status=400)
            return

        # ---- Admin: create coupon ----
        if path == '/api/coupons':
            if not self._require_auth():
                return
            body = self._read_body()
            try:
                data        = json.loads(body) if body else {}
                action      = data.get('action', 'create')
                if action == 'delete':
                    code = data.get('code', '').strip().upper()
                    coupons = _read_json(COUPONS_FILE)
                    coupons = [c for c in coupons if c.get('code','').upper() != code]
                    _write_json(COUPONS_FILE, coupons)
                    self._json_response({'ok': True})
                elif action == 'toggle':
                    code    = data.get('code', '').strip().upper()
                    coupons = _read_json(COUPONS_FILE)
                    for c in coupons:
                        if c.get('code','').upper() == code:
                            c['active'] = not c.get('active', True)
                    _write_json(COUPONS_FILE, coupons)
                    self._json_response({'ok': True})
                else:
                    from datetime import date, timedelta
                    code         = _generate_coupon_code()
                    discount_pct = int(data.get('discount_pct', 50))
                    max_uses     = int(data.get('max_uses', 1))
                    note         = str(data.get('note', '')).strip()[:200]
                    created_date = date.today()
                    expires_date = created_date + timedelta(days=30)
                    coupon = {
                        'code':         code,
                        'discount_pct': discount_pct,
                        'max_uses':     max_uses,
                        'uses':         0,
                        'active':       True,
                        'created':      created_date.isoformat(),
                        'expires':      expires_date.isoformat(),
                        'note':         note,
                    }
                    coupons = _read_json(COUPONS_FILE)
                    coupons.append(coupon)
                    _write_json(COUPONS_FILE, coupons)
                    self._json_response({'ok': True, 'coupon': coupon})
            except Exception as e:
                self._json_response({'ok': False, 'error': str(e)}, status=400)
            return

        # ---- Initiate payment (public) ----
        if path == '/api/initiate-payment':
            body = self._read_body()
            try:
                data        = json.loads(body)
                name        = str(data.get('name', '')).strip()[:200]
                email       = str(data.get('email', '')).strip()[:200]
                coupon_code = str(data.get('coupon_code', '')).strip().upper()
                if not name or not email or '@' not in email:
                    raise ValueError("Valid name and email are required")

                cfg_data = get_payment_config()
                # Demo mode bypasses the enabled requirement
                if not cfg_data.get('enabled') and not cfg_data.get('demo_mode'):
                    raise ValueError("Payment gateway is not enabled")

                order_id = 'PA-' + secrets.token_hex(8).upper()
                amount   = round(float(cfg_data.get('course_price', 99)), 2)

                # Apply coupon discount
                applied_coupon = None
                if coupon_code:
                    applied_coupon = _find_coupon(coupon_code)
                    if not applied_coupon:
                        raise ValueError("Invalid or expired coupon code")
                    discount_pct = applied_coupon.get('discount_pct', 50)
                    amount = round(amount * (1 - discount_pct / 100), 2)

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
                    'coupon_code':       coupon_code if applied_coupon else '',
                }
                orders.append(pending)
                _write_json(ORDERS_FILE, orders)

                # Demo mode — skip Areeba, redirect to demo page
                if cfg_data.get('demo_mode'):
                    demo_url = '/payment-demo?order=' + order_id + '&name=' + urllib.parse.quote(name) + '&amount=' + str(int(amount))
                    self._json_response({'ok': True, 'checkout_url': demo_url})
                    return

                if not cfg_data.get('merchant_id') or not cfg_data.get('api_key'):
                    raise ValueError("Payment gateway is not configured")

                gateway_type = (cfg_data.get('gateway_type') or 'cybersource').lower()
                if gateway_type == 'cybersource':
                    capture_context = _cybersource_create_capture_context(
                        cfg_data, order_id, amount, name, email
                    )
                    self._json_response({
                        'ok': True,
                        'gateway': 'cybersource',
                        'order_id': order_id,
                        'capture_context': capture_context,
                    })
                    return

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

        # ---- Refresh Cybersource capture context for a pending order ----
        if path == '/api/refresh-capture-context':
            body = self._read_body()
            try:
                data = json.loads(body) if body else {}
                order_id = str(data.get('order_id', '')).strip()
                if not order_id:
                    raise ValueError('order_id is required')

                cfg_data = get_payment_config()
                if not cfg_data.get('enabled') and not cfg_data.get('demo_mode'):
                    raise ValueError('Payment gateway is not enabled')
                if (cfg_data.get('gateway_type') or 'cybersource').lower() != 'cybersource':
                    raise ValueError('Capture context refresh is only for Cybersource')
                if not cfg_data.get('merchant_id') or not cfg_data.get('api_key'):
                    raise ValueError('Payment gateway is not configured')

                orders = _read_json(ORDERS_FILE)
                order = next((o for o in orders if o.get('order_id') == order_id), None)
                if not order:
                    raise ValueError('Order not found')
                if order.get('status') != 'pending':
                    raise ValueError('Order is no longer pending')

                page_origin = str(data.get('origin', '')).strip()
                capture_context = _cybersource_create_capture_context(
                    cfg_data,
                    order_id,
                    float(order.get('amount', cfg_data.get('course_price', 99))),
                    order.get('name', ''),
                    order.get('email', ''),
                    page_origin=page_origin,
                )
                self._json_response({
                    'ok': True,
                    'order_id': order_id,
                    'capture_context': capture_context,
                })
            except Exception as e:
                self._json_response({'ok': False, 'error': str(e)}, status=400)
            return

        # ---- Cybersource payment result (public) ----
        if path == '/api/payment-complete':
            body = self._read_body()
            try:
                data = json.loads(body) if body else {}
                order_id = str(data.get('order_id', '')).strip()
                result_raw = data.get('result')
                if not order_id or result_raw is None or result_raw == '':
                    raise ValueError('order_id and result are required')

                orders = _read_json(ORDERS_FILE)
                order = next((o for o in orders if o.get('order_id') == order_id), None)
                if not order:
                    raise ValueError('Order not found')
                if order.get('email', '').strip().lower() != str(data.get('email', order.get('email', ''))).strip().lower():
                    raise ValueError('Order verification failed')

                cfg_data = get_payment_config()
                try:
                    payment_meta = _cybersource_process_payment(cfg_data, order, result_raw)
                except ValueError:
                    payment_meta = _cybersource_verify_payment(cfg_data, order, None)
                if not payment_meta or not payment_meta.get('ok'):
                    raise ValueError('Payment was not completed')

                result_info = _finalize_paid_order(
                    order_id, cfg_data, gateway_name='cybersource', payment_meta=payment_meta
                )
                self._json_response({
                    'ok': True,
                    'redirect': result_info.get('redirect', '/payment-success.html'),
                })
            except Exception as e:
                self._json_response({'ok': False, 'error': str(e)}, status=400)
            return

        # ---- Image upload ----
        if path in ('/api/upload-image', '/api/images'):
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
                thumb_field = parts.get('thumb_field', b'').decode('utf-8', errors='ignore').strip()
                if thumb_field:
                    safe_path = cm.recommended_video_thumbnail_path(thumb_field)
                    if safe_path:
                        filename = safe_path
                raw_bytes = parts['file']
                ok, err   = cm.save_image(filename, raw_bytes)
                if ok:
                    self._json_response({'ok': True, 'path': filename})
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
def _run_server():
    no_ssl = os.environ.get('PA_NO_SSL', '0') == '1'
    port = int(os.environ.get('PA_PORT', '4443'))
    host = os.environ.get('PA_HOST', '127.0.0.1')
    server = http.server.HTTPServer((host, port), Handler)

    if no_ssl:
        print(f"Running at http://{host}:{port}  [HTTP mode — SSL handled by reverse proxy]")
        print(f"Admin panel: http://{host}:{port}/admin/login.html")
    else:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain('cert.pem', 'key.pem')
        server.socket = ctx.wrap_socket(server.socket, server_side=True)
        print(f"Running at https://{host}:{port}")
        print(f"Admin panel: https://{host}:{port}/admin/login.html")

    server.serve_forever()

if __name__ == '__main__':
    _run_server()

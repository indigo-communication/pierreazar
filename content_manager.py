"""
content_manager.py
Handles reading and writing editable content fields directly in the HTML files.
"""
import re, os, glob

BASE = os.path.dirname(os.path.abspath(__file__))

PUBLIC_PAGES = [
    'index.html',
    'portfolio.html',
    'onset-experience.html',
    'get-in-touch.html',
    'cinematography-course.html',
]


# ── File helpers ─────────────────────────────────────────────────────────────

def _read(fname):
    path = os.path.join(BASE, fname)
    if not os.path.exists(path):
        return ''
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def _write(fname, content):
    with open(os.path.join(BASE, fname), 'w', encoding='utf-8') as f:
        f.write(content)

def _sub(pattern, new_value, content, flags=0):
    """re.sub using a lambda so new_value is treated as a literal string."""
    compiled = re.compile(pattern, flags)
    def repl(m):
        parts = []
        for i in range(1, compiled.groups + 1):
            parts.append(m.group(i))
        # Insert new_value between group 1 and group 2
        return parts[0] + new_value + parts[1]
    return compiled.sub(repl, content)


# ── Read all editable fields ──────────────────────────────────────────────────

def get_all():
    result = {}

    # ── Course page ─────────────────────────────────────────────────────────
    c = _read('cinematography-course.html')

    # Vimeo video ID (from iframe src)
    m = re.search(
        r'id="element-676387d0a7f9742-vidframe"\s+src="https://player\.vimeo\.com/video/(\d+)',
        c
    )
    result['course_vimeo_id'] = m.group(1) if m else '291044785'

    # Course price
    m = re.search(r'<span class="real-price">\s*([\d.]+)\s*</span>', c)
    result['course_price'] = m.group(1).strip() if m else '99'

    # Buy button text
    m = re.search(r'id="vbid-c1e000b4-nold91wb"[^>]*>([^<]+)</span>', c)
    result['course_buy_text'] = m.group(1).strip() if m else 'Buy Now'

    # Buy button URL
    m = re.search(r'<a class="removable-parent" href="([^"]*)" data-link-type="BUY"', c)
    result['course_buy_url'] = m.group(1) if m else '/'

    # ── Homepage ─────────────────────────────────────────────────────────────
    idx = _read('index.html')

    # Hero quote text
    m = re.search(r'id="vbid-38497da5-zc2jpxkd"[^>]*>(.*?)</h2>', idx, re.DOTALL)
    result['homepage_quote'] = m.group(1).strip() if m else ''

    # About body (raw HTML)
    m = re.search(r'(<div id="vbid-38497da5-t14shpss"[^>]*>)(.*?)(</div>)', idx, re.DOTALL)
    result['homepage_about'] = m.group(2).strip() if m else ''

    # Hero reel Vimeo ID (element-741e899e73dd9a3 is the primary one)
    m = re.search(
        r'id="element-741e899e73dd9a3-vidframe"\s+src="https://player\.vimeo\.com/video/(\d+)',
        idx
    )
    result['homepage_reel_vimeo_id'] = m.group(1) if m else '1000452483'

    # ── Social links (read from index.html) ──────────────────────────────────
    m = re.search(
        r'id="FACEBOOK"[^>]*>.*?<a class=[\'"]social-link-url[\'"] href="([^"]*)"',
        idx, re.DOTALL
    )
    result['social_facebook'] = m.group(1) if m else 'https://www.facebook.com/'

    m = re.search(
        r'id="INSTAGRAM"[^>]*>.*?<a class=[\'"]social-link-url[\'"] href="([^"]*)"',
        idx, re.DOTALL
    )
    result['social_instagram'] = m.group(1) if m else 'https://www.instagram.com'

    m = re.search(
        r'id="VIMEO"[^>]*>.*?<a class=[\'"]social-link-url[\'"] href="([^"]*)"',
        idx, re.DOTALL
    )
    result['social_vimeo'] = m.group(1) if m else 'https://www.vimeo.com'

    return result


# ── Write editable fields ─────────────────────────────────────────────────────

def save_content(data):
    """Apply content changes. data = {field: new_value}. Returns list of errors."""
    errors = []

    # ── Course page ──────────────────────────────────────────────────────────
    course_keys = [k for k in data if k.startswith('course_')]
    if course_keys:
        c = _read('cinematography-course.html')

        if 'course_vimeo_id' in data:
            vid = re.sub(r'[^\d]', '', str(data['course_vimeo_id']))
            if vid:
                # Update iframe src
                c = re.compile(
                    r'(id="element-676387d0a7f9742-vidframe"\s+src="https://player\.vimeo\.com/video/)\d+'
                ).sub(lambda m: m.group(1) + vid, c)
                # Update data-spimeVIDEO_ID attribute
                c = re.compile(
                    r"(data-spimeVIDEO_ID\s*=\s*')\d+('\s*data-spimeVBID\s*=\s*'element-676387d0a7f9742')"
                ).sub(lambda m: m.group(1) + vid + m.group(2), c)

        if 'course_price' in data:
            price = re.sub(r'[^\d.]', '', str(data['course_price']))
            if price:
                c = re.compile(
                    r'(<span class="real-price">[\s\n]*)[\d.]+([\s\n]*</span>)'
                ).sub(lambda m: m.group(1) + price + m.group(2), c)

        if 'course_buy_text' in data:
            text = str(data['course_buy_text']).strip()
            if text:
                c = re.compile(
                    r'(id="vbid-c1e000b4-nold91wb"[^>]*>)[^<]*(</span>)'
                ).sub(lambda m: m.group(1) + text + m.group(2), c)

        if 'course_buy_url' in data:
            url = str(data['course_buy_url']).strip()
            c = re.compile(
                r'(<a class="removable-parent" href=")[^"]*(" data-link-type="BUY")'
            ).sub(lambda m: m.group(1) + url + m.group(2), c)

        try:
            _write('cinematography-course.html', c)
        except Exception as e:
            errors.append(f'course page: {e}')

    # ── Homepage ─────────────────────────────────────────────────────────────
    homepage_keys = [k for k in data if k.startswith('homepage_')]
    if homepage_keys:
        idx = _read('index.html')

        if 'homepage_quote' in data:
            quote = str(data['homepage_quote']).strip()
            if quote:
                idx = re.compile(
                    r'(id="vbid-38497da5-zc2jpxkd"[^>]*>)(.*?)(</h2>)',
                    re.DOTALL
                ).sub(lambda m: m.group(1) + quote + m.group(3), idx)

        if 'homepage_about' in data:
            about = str(data['homepage_about']).strip()
            if about:
                idx = re.compile(
                    r'(<div id="vbid-38497da5-t14shpss"[^>]*>)(.*?)(</div>)',
                    re.DOTALL
                ).sub(lambda m: m.group(1) + '\n\t\t' + about + '\n\t\t' + m.group(3), idx)

        if 'homepage_reel_vimeo_id' in data:
            vid = re.sub(r'[^\d]', '', str(data['homepage_reel_vimeo_id']))
            if vid:
                for elem_id in [
                    'element-741e899e73dd9a3',
                    'element-a040d6d7a932d90',
                    'element-8a4e9ff9e6eb6c1',
                ]:
                    idx = re.compile(
                        r'(id="' + elem_id + r'-vidframe"\s+src="https://player\.vimeo\.com/video/)\d+'
                    ).sub(lambda m: m.group(1) + vid, idx)
                    idx = re.compile(
                        r"(data-spimeVIDEO_ID\s*=\s*')\d+('\s*data-spimeVBID\s*=\s*'" + elem_id + r"')"
                    ).sub(lambda m: m.group(1) + vid + m.group(2), idx)

        try:
            _write('index.html', idx)
        except Exception as e:
            errors.append(f'homepage: {e}')

    # ── Social links (update all public pages) ────────────────────────────────
    social_keys = [k for k in data if k.startswith('social_')]
    if social_keys:
        for page in PUBLIC_PAGES:
            content = _read(page)
            if not content:
                continue

            if 'social_facebook' in data:
                url = str(data['social_facebook']).strip()
                content = re.compile(
                    r"(id=\"FACEBOOK\"[^>]*>.*?<a class=['\"]social-link-url['\"] href=\")[^\"]*\"",
                    re.DOTALL
                ).sub(lambda m, u=url: m.group(1) + u + '"', content)

            if 'social_instagram' in data:
                url = str(data['social_instagram']).strip()
                content = re.compile(
                    r"(id=\"INSTAGRAM\"[^>]*>.*?<a class=['\"]social-link-url['\"] href=\")[^\"]*\"",
                    re.DOTALL
                ).sub(lambda m, u=url: m.group(1) + u + '"', content)

            if 'social_vimeo' in data:
                url = str(data['social_vimeo']).strip()
                content = re.compile(
                    r"(id=\"VIMEO\"[^>]*>.*?<a class=['\"]social-link-url['\"] href=\")[^\"]*\"",
                    re.DOTALL
                ).sub(lambda m, u=url: m.group(1) + u + '"', content)

            try:
                _write(page, content)
            except Exception as e:
                errors.append(f'{page}: {e}')

    return errors


# ── Image management ──────────────────────────────────────────────────────────

def list_images():
    photos_dir = os.path.join(BASE, 'images', 'photos')
    images = []
    if os.path.exists(photos_dir):
        for f in sorted(os.listdir(photos_dir)):
            if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif')):
                images.append(f)
    return images


def save_image(filename, raw_bytes):
    """Replace an existing image in images/photos/. Returns (ok, error_msg)."""
    safe_name = re.sub(r'[^a-zA-Z0-9._\-]', '_', os.path.basename(filename))
    if not safe_name or '..' in safe_name:
        return False, 'Invalid filename'
    ext = os.path.splitext(safe_name)[1].lower()
    if ext not in ('.jpg', '.jpeg', '.png', '.webp', '.gif'):
        return False, 'Only JPG, PNG, WebP, GIF images allowed'

    photos_dir = os.path.join(BASE, 'images', 'photos')
    target = os.path.join(photos_dir, safe_name)

    # Security: only allow replacing existing files (no new filenames)
    if not os.path.exists(target):
        return False, f'Target image not found: {safe_name}'

    try:
        with open(target, 'wb') as f:
            f.write(raw_bytes)
        return True, None
    except Exception as e:
        return False, str(e)

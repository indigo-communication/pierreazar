"""
content_manager.py
Handles reading and writing editable content fields directly in the HTML files.
"""
import re, os, glob, json

BASE = os.path.dirname(os.path.abspath(__file__))

PUBLIC_PAGES = [
    'index.html',
    'portfolio.html',
    'onset-experience.html',
    'get-in-touch.html',
    'cinematography-course.html',
]

# Portfolio Vimeo video element VBID → field name mapping (order matches page order)
PORTFOLIO_VIDEOS = [
    ('portfolio_video_0', 'vbid-5582618c-ravlhl84'),   # Film reel / promo
    ('portfolio_video_1', 'vbid-ffeb6a49-17vdtkfy'),   # Item 1
    ('portfolio_video_2', 'vbid-59730bcc-17vdtkfy'),   # Item 2
    ('portfolio_video_3', 'vbid-89015478-17vdtkfy'),   # Item 3
    ('portfolio_video_4', 'vbid-ec30163e-17vdtkfy'),   # Item 4
    ('portfolio_video_5', 'vbid-d92e5830-17vdtkfy'),   # Item 5
    ('portfolio_video_6', 'vbid-42a2fb8d-17vdtkfy'),   # Item 6
    ('portfolio_video_7', 'vbid-1088fcb3-17vdtkfy'),   # Item 7
    ('portfolio_video_8', 'vbid-da7defbd-ngplle3l'),   # Item 8
]

# Allowed image subfolders (relative to images/)
IMAGE_FOLDERS = ['photos', 'hq', 'icons']

# Course section videos stored in data/course_videos.json
COURSE_VIDEOS_FILE = os.path.join(BASE, 'data', 'course_videos.json')
COURSE_PARTS = ['course_part_1_url', 'course_part_2_url', 'course_part_3_url',
                'course_part_4_url', 'course_part_5_url']


def _read_course_videos():
    if os.path.exists(COURSE_VIDEOS_FILE):
        try:
            with open(COURSE_VIDEOS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {k: '' for k in COURSE_PARTS}


def _write_course_videos(data):
    os.makedirs(os.path.dirname(COURSE_VIDEOS_FILE), exist_ok=True)
    with open(COURSE_VIDEOS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def get_page_images(page_file):
    """Scan an HTML file and return list of image paths it uses (images/... only)."""
    content = _read(page_file)
    if not content:
        return []
    found = re.findall(r'(?:data-bgimg|src)="(images/[^"]+)"', content)
    # Deduplicate, keep order, filter to image extensions
    seen = set()
    result = []
    for img in found:
        ext = os.path.splitext(img)[1].lower()
        if ext in ('.jpg', '.jpeg', '.png', '.webp', '.gif') and img not in seen:
            seen.add(img)
            result.append(img)
    return sorted(result)


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

    # ── Course section videos (Bunny Stream / any embed URL) ─────────────────
    result.update(_read_course_videos())

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

    # Selected Works Video 1 (element-a040d6d7a932d90)
    m = re.search(
        r'id="element-a040d6d7a932d90-vidframe"\s+src="https://player\.vimeo\.com/video/(\d+)',
        idx
    )
    result['homepage_selected_video_1'] = m.group(1) if m else '1000452483'

    # Selected Works Video 2 (element-8a4e9ff9e6eb6c1)
    m = re.search(
        r'id="element-8a4e9ff9e6eb6c1-vidframe"\s+src="https://player\.vimeo\.com/video/(\d+)',
        idx
    )
    result['homepage_selected_video_2'] = m.group(1) if m else '1000452483'

    # Selected Works Video 3 (element-6d74b124fdb89cc)
    m = re.search(
        r'id="element-6d74b124fdb89cc-vidframe"\s+src="https://player\.vimeo\.com/video/(\d+)',
        idx
    )
    result['homepage_selected_video_3'] = m.group(1) if m else '471331461'

    # Course promo on homepage (element-676387d0a7f9742)
    m = re.search(
        r'id="element-676387d0a7f9742-vidframe"\s+src="https://player\.vimeo\.com/video/(\d+)',
        idx
    )
    result['homepage_course_vimeo_id'] = m.group(1) if m else '291044785'

    # ── Portfolio page ───────────────────────────────────────────────────────
    pf = _read('portfolio.html')
    for field, vbid in PORTFOLIO_VIDEOS:
        # Match: data-spimeVIDEO_ID = '\d+' ... data-spimeVBID = 'vbid-...'
        m = re.search(
            r"data-spimeVIDEO_ID\s*=\s*'(\d+)'\s+data-spimeVID_COVER[^>]*data-spimeVBID\s*=\s*'" + re.escape(vbid) + r"'",
            pf
        )
        if not m:
            # Fallback: search iframe src
            m2 = re.search(
                r'id="' + re.escape(vbid) + r'-vidframe"\s+src="https://player\.vimeo\.com/video/(\d+)',
                pf
            )
            result[field] = m2.group(1) if m2 else ''
        else:
            result[field] = m.group(1)

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
                # Update iframe src in course page
                c = re.compile(
                    r'(id="element-676387d0a7f9742-vidframe"\s+src="https://player\.vimeo\.com/video/)\d+'
                ).sub(lambda m: m.group(1) + vid, c)
                # Update data-spimeVIDEO_ID attribute in course page
                c = re.compile(
                    r"(data-spimeVIDEO_ID\s*=\s*')\d+('\s*data-spimeVBID\s*=\s*'element-676387d0a7f9742')"
                ).sub(lambda m: m.group(1) + vid + m.group(2), c)
                # Also update the homepage course promo (same element, index.html)
                _idx = _read('index.html')
                _idx = re.compile(
                    r'(id="element-676387d0a7f9742-vidframe"\s+src="https://player\.vimeo\.com/video/)\d+'
                ).sub(lambda m: m.group(1) + vid, _idx)
                _idx = re.compile(
                    r"(data-spimeVIDEO_ID\s*=\s*')\d+('\s*data-spimeVBID\s*=\s*'element-676387d0a7f9742')"
                ).sub(lambda m: m.group(1) + vid + m.group(2), _idx)
                try:
                    _write('index.html', _idx)
                except Exception as e:
                    errors.append(f'homepage course promo: {e}')

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

    # ── Course section videos (Bunny Stream / any embed URL) ─────────────────
    course_part_keys = [k for k in data if k in COURSE_PARTS]
    if course_part_keys:
        cv = _read_course_videos()
        for k in course_part_keys:
            cv[k] = str(data[k]).strip()
        try:
            _write_course_videos(cv)
        except Exception as e:
            errors.append(f'course videos: {e}')

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
                idx = re.compile(
                    r'(id="element-741e899e73dd9a3-vidframe"\s+src="https://player\.vimeo\.com/video/)\d+'
                ).sub(lambda m: m.group(1) + vid, idx)
                idx = re.compile(
                    r"(data-spimeVIDEO_ID\s*=\s*')\d+('\s*data-spimeVBID\s*=\s*'element-741e899e73dd9a3')"
                ).sub(lambda m: m.group(1) + vid + m.group(2), idx)

        for field, elem_id in [
            ('homepage_selected_video_1', 'element-a040d6d7a932d90'),
            ('homepage_selected_video_2', 'element-8a4e9ff9e6eb6c1'),
            ('homepage_selected_video_3', 'element-6d74b124fdb89cc'),
        ]:
            if field in data:
                sv = re.sub(r'[^\d]', '', str(data[field]))
                if sv:
                    idx = re.compile(
                        r'(id="' + elem_id + r'-vidframe"\s+src="https://player\.vimeo\.com/video/)\d+'
                    ).sub(lambda m, v=sv: m.group(1) + v, idx)
                    idx = re.compile(
                        r"(data-spimeVIDEO_ID\s*=\s*')\d+('\s*data-spimeVBID\s*=\s*'" + elem_id + r"')"
                    ).sub(lambda m, v=sv: m.group(1) + v + m.group(2), idx)

        if 'homepage_course_vimeo_id' in data:
            vidc = re.sub(r'[^\d]', '', str(data['homepage_course_vimeo_id']))
            if vidc:
                idx = re.compile(
                    r'(id="element-676387d0a7f9742-vidframe"\s+src="https://player\.vimeo\.com/video/)\d+'
                ).sub(lambda m: m.group(1) + vidc, idx)
                idx = re.compile(
                    r"(data-spimeVIDEO_ID\s*=\s*')\d+('\s*data-spimeVBID\s*=\s*'element-676387d0a7f9742')"
                ).sub(lambda m: m.group(1) + vidc + m.group(2), idx)

        try:
            _write('index.html', idx)
        except Exception as e:
            errors.append(f'homepage: {e}')

    # ── Portfolio page ───────────────────────────────────────────────────────
    portfolio_keys = [k for k in data if k.startswith('portfolio_video_')]
    if portfolio_keys:
        pf = _read('portfolio.html')
        for field, vbid in PORTFOLIO_VIDEOS:
            if field not in data:
                continue
            vid = re.sub(r'[^\d]', '', str(data[field]))
            if not vid:
                continue
            # Update data-spimeVIDEO_ID attribute
            pf = re.compile(
                r"(data-spimeVIDEO_ID\s*=\s*')\d+('\s+data-spimeVID_COVER[^>]*data-spimeVBID\s*=\s*'" + re.escape(vbid) + r"')"
            ).sub(lambda m, v=vid: m.group(1) + v + m.group(2), pf)
            # Update iframe src
            pf = re.compile(
                r'(id="' + re.escape(vbid) + r'-vidframe"\s+src="https://player\.vimeo\.com/video/)\d+'
            ).sub(lambda m, v=vid: m.group(1) + v, pf)
            # Update player_id query param video ID
            pf = re.compile(
                r'(player_id=' + re.escape(vbid) + r'-vidframe&[^"]*video/)\d+'
            ).sub(lambda m, v=vid: m.group(1) + v, pf)
        try:
            _write('portfolio.html', pf)
        except Exception as e:
            errors.append(f'portfolio: {e}')

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
    """Return all images from allowed subdirectories as list of dicts."""
    result = []
    for folder in IMAGE_FOLDERS:
        dir_path = os.path.join(BASE, 'images', folder)
        if not os.path.exists(dir_path):
            continue
        for f in sorted(os.listdir(dir_path)):
            if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif')):
                result.append({
                    'folder': folder,
                    'filename': f,
                    'url': '/images/' + folder + '/' + f,
                })
    return result


def save_image(filename, raw_bytes):
    """Replace an existing image. filename may be 'photos/img_001.jpg' or plain 'img_001.jpg'.
    Returns (ok, error_msg)."""
    # Strip leading slash/images prefix if present
    filename = filename.lstrip('/')
    if filename.startswith('images/'):
        filename = filename[len('images/'):]

    # Determine folder and basename
    if '/' in filename:
        parts = filename.split('/', 1)
        folder, basename = parts[0], parts[1]
    else:
        folder, basename = 'photos', filename   # legacy default

    if folder not in IMAGE_FOLDERS:
        return False, f'Invalid image folder: {folder}'

    safe_name = re.sub(r'[^a-zA-Z0-9._\-]', '_', os.path.basename(basename))
    if not safe_name or '..' in safe_name:
        return False, 'Invalid filename'
    ext = os.path.splitext(safe_name)[1].lower()
    if ext not in ('.jpg', '.jpeg', '.png', '.webp', '.gif'):
        return False, 'Only JPG, PNG, WebP, GIF images allowed'

    target = os.path.join(BASE, 'images', folder, safe_name)

    # Security: only allow replacing existing files
    if not os.path.exists(target):
        return False, f'Target image not found: {folder}/{safe_name}'

    try:
        with open(target, 'wb') as f:
            f.write(raw_bytes)
        return True, None
    except Exception as e:
        return False, str(e)

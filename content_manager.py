"""
content_manager.py
Handles reading and writing editable content fields directly in HTML files.
"""
import json
import os
import re
import random
import shutil
import string

BASE = os.path.dirname(os.path.abspath(__file__))

PUBLIC_PAGES = [
    'index.html',
    'portfolio.html',
    'onset-experience.html',
    'get-in-touch.html',
    'cinematography-course.html',
]

# Video + thumbnail mapping per page
VIDEO_FIELDS = {
    'homepage_reel_video_link': ('index.html', 'element-741e899e73dd9a3', 'vbid-38497da5-v22rkfln'),
    'homepage_selected_video_1': ('index.html', 'element-a040d6d7a932d90', 'vbid-6fed10fa-dfbcl8qf'),
    'homepage_selected_video_2': ('index.html', 'element-8a4e9ff9e6eb6c1', 'vbid-6fed10fa-c3w2mmzm'),
    'homepage_selected_video_3': ('index.html', 'element-6d74b124fdb89cc', 'vbid-6fed10fa-5tl59pta'),
    'homepage_course_video_link': ('index.html', 'element-676387d0a7f9742', 'vbid-c1e000b4-3ybmwuzg'),
    'course_video_link': ('cinematography-course.html', 'element-676387d0a7f9742', 'vbid-c1e000b4-3ybmwuzg'),
    'portfolio_video_0': ('portfolio.html', 'vbid-5582618c-ravlhl84', 'vbid-5582618c-2rslueob'),
    'portfolio_video_1': ('portfolio.html', 'vbid-ffeb6a49-17vdtkfy', 'vbid-ffeb6a49-upubmm8p'),
    'portfolio_video_2': ('portfolio.html', 'vbid-59730bcc-17vdtkfy', 'vbid-59730bcc-upubmm8p'),
    'portfolio_video_3': ('portfolio.html', 'vbid-89015478-17vdtkfy', 'vbid-89015478-upubmm8p'),
    'portfolio_video_4': ('portfolio.html', 'vbid-ec30163e-17vdtkfy', 'vbid-ec30163e-upubmm8p'),
    'portfolio_video_5': ('portfolio.html', 'vbid-d92e5830-17vdtkfy', 'vbid-d92e5830-upubmm8p'),
    'portfolio_video_6': ('portfolio.html', 'vbid-42a2fb8d-17vdtkfy', 'vbid-42a2fb8d-upubmm8p'),
    'portfolio_video_7': ('portfolio.html', 'vbid-1088fcb3-17vdtkfy', 'vbid-1088fcb3-upubmm8p'),
    'portfolio_video_8': ('portfolio.html', 'vbid-da7defbd-ngplle3l', 'vbid-da7defbd-n1bsrkfs'),
}

THUMBNAIL_FIELDS = {
    field.replace('_video_link', '_thumbnail') if field.endswith('_video_link') else field + '_thumbnail': (page, thumb_id)
    for field, (page, _video_id, thumb_id) in VIDEO_FIELDS.items()
}

# First item in the main portfolio video grid (do NOT use the generic #items-holder —
# portfolio.html contains three of those; only this anchor is the featured grid).
PORTFOLIO_GRID_ANCHOR = 'vbid-5582618c-fadru3ag'
PORTFOLIO_DYNAMIC_FILE = os.path.join(BASE, 'data', 'portfolio_dynamic.json')

def _build_portfolio_item_html(wrapper_id, video_id, img_id, source, vid,
                               iframe_src, iframe_class, thumb_path):
    """Build portfolio grid item HTML — nesting must match static items for matrix layout."""
    return (
        f'<div id="{wrapper_id}" class="sub item-box  page-box style-5582618c-u4ta6ilj" '
        f'data-holder-type="page" data-child-type="STYLE" data-styleid="style-5582618c-u4ta6ilj" '
        f'data-preview-styleid="style-5582618c-u4ta6ilj" data-preset-type-id="UNRESOLVED">\n'
        f'\t\t\t<div class="page-wrapper item-wrapper">\n'
        f'\t\t\t\t\t<div class="item-content leaf multi_layout page content -container" '
        f'data-self="{wrapper_id}" data-preview-style="style-5582618c-u4ta6ilj" '
        f'data-style="style-ed018-yjvbvfoyx6" data-orig-thumb-height="344" '
        f'data-orig-thumb-width="489" data-vbid="{wrapper_id}" data-bgimg="{thumb_path}">\n'
        f'<div class="multi-container preview image-cover">\n'
        f'\t<div class="Picture item-preview">\n'
        f'\t\t<div class="preview-image-holder">\n'
        f'\t\t\t<div id="no-image" class="background-image-div preview-element image-source '
        f'magic-circle-holder unfold-left load-high-res" data-menu-name="BACKGROUND_IMAGE" style=""></div>\n'
        f'\t\t\t<div class="helper-div bottom-center">\n'
        f'\t\t\t<div class="pic-side">\n'
        f'\t\t\t\t<div class="vertical-aligner">\n'
        f'\t\t\t\t\t<div id="{img_id}-holder" class="preview-image-holder inner-pic-holder" '
        f'data-menu-name="PREVIEW_INLINE_IMAGE_HOLDER">\n'
        f'    <a class="image-link top-layer not-wrapping" href="#{wrapper_id}" '
        f'data-link-type="LIGHTBOX" target="_self"></a>\n'
        f'    <div id="{img_id}" class="inner-pic preview-element magic-circle-holder load-high-res" '
        f'data-menu-name="PREVIEW_INLINE_IMAGE" style="background-image:url({thumb_path});" '
        f'data-orig-width="489" data-orig-height="344">\n'
        f'<div class="preview-video-holder removable-parent">\n'
        f'\t<div id="{video_id}" class="preview-element preview-video-source magic-circle-holder '
        f'vid-cover allow-mobile-hide" data-menu-name="PREVIEW_VIDEO" data-json-name="PREVIEW_VIDEO" '
        f'data-spimeTEXT=\'{vid}\' data-spimeVIDEO_ID=\'{vid}\' data-spimeVID_COVER=\'True\' '
        f'data-spimeSOURCE=\'{source}\' data-spimeCONTEXT=\'PREVIEW\' data-spimeVBID=\'{video_id}\'>\n'
        f'\t\t<iframe class="{iframe_class} preview video-frame" id="{video_id}-vidframe" '
        f'src="{iframe_src}" frameborder="0" width="100%" height="100%"></iframe>\n'
        f'\t</div>\n'
        f'</div>\n'
        f'    </div>\n'
        f'</div>\n'
        f'\t\t\t\t</div>\n'
        f'\t\t\t</div>\n'
        f'\t\t\t\t<div class="text-side shrinker-parent">\n'
        f'\t\t\t\t\t<div class="vertical-aligner">\n'
        f'\t\t\t\t\t\t<div class="item-details preview-content-wrapper multi" style="position:relative;">\n'
        f'\t\t\t\t\t\t\t<div class="preview-content-holder shrinker-content"></div>\n'
        f'\t\t\t\t\t\t</div>\n'
        f'\t\t\t\t\t</div>\n'
        f'\t\t\t\t</div>\n'
        f'\t\t\t</div>\n'
        f'\t\t</div>\n'
        f'\t</div>\n'
        f'</div>\n'
        f'</div>\n'
        f'\n'
        f'<div class="layout-settings" style="display:none;" data-type="multi"></div>\n'
        f'\t\t\t\t\t\n'
        f'\t\t\t</div>\n'
        f'\t\t</div>\n'
    )


def _iframe_parts(source, video_id, vid):
    if source == 'youtube':
        params = 'enablejsapi=1&rel=0&modestbranding=1&playsinline=1&autoplay=0&mute=0&loop=0&controls=1'
        return (
            f'https://www.youtube.com/embed/{vid}?{params}',
            'ytplayer',
        )
    return (
        f'https://player.vimeo.com/video/{vid}?api=1&player_id={video_id}-vidframe',
        'vimplayer',
    )


def _remove_portfolio_block(portfolio, wrapper_id):
    wid = re.escape(wrapper_id)
    patterns = [
        # Full block — always remove wrapper + page-wrapper closing tags
        (
            r'<div id="' + wid + r'"[^>]*>.*?'
            r'<div class="layout-settings"[^>]*data-type="multi"[^>]*></div>\s*'
            r'(?:\t*\n)?\t*\t*\t*\t*\n?\t*\t*\t*</div>\s*'
            r'(?:\t*\n)?\t*\t*</div>'
        ),
        # Legacy one-line blocks (malformed nesting)
        (
            r'<div id="' + wid + r'"[^>]*>.*?'
            r'<div class="layout-settings"[^>]*data-type="multi"[^>]*></div>'
        ),
    ]
    for pattern in patterns:
        new_portfolio, n = re.subn(pattern, '', portfolio, count=1, flags=re.DOTALL)
        if n:
            return repair_portfolio_featured_grid_structure(new_portfolio)
    raise RuntimeError(f'Could not find wrapper block for {wrapper_id} in portfolio.html')


def repair_portfolio_featured_grid_structure(portfolio=None):
    """
    Fix featured portfolio grid when #items-holder was closed early (after a bad delete).
    Removes orphan closes between items-holder open and the first static grid item.
    """
    if portfolio is None:
        portfolio = _read('portfolio.html')
        write_back = True
    else:
        write_back = False

    anchor_markers = (
        f'<div  id="{PORTFOLIO_GRID_ANCHOR}"',
        f'<div id="{PORTFOLIO_GRID_ANCHOR}"',
    )
    anchor_pos = -1
    for marker in anchor_markers:
        pos = portfolio.find(marker)
        if pos != -1:
            anchor_pos = pos
            break
    if anchor_pos == -1:
        if write_back:
            return False
        return portfolio

    holder_open = '<div id="items-holder">'
    holder_pos = portfolio.rfind(holder_open, 0, anchor_pos)
    if holder_pos == -1:
        if write_back:
            return False
        return portfolio

    head = holder_pos + len(holder_open)
    between = portfolio[head:anchor_pos]
    cleaned = re.sub(
        r'^\s*(?:</div>\s*){1,4}',
        '',
        between,
        count=1,
        flags=re.DOTALL,
    )
    if cleaned == between:
        if write_back:
            return False
        return portfolio

    portfolio = portfolio[:head] + cleaned + portfolio[anchor_pos:]
    if write_back:
        _write('portfolio.html', portfolio)
    return portfolio


def repair_portfolio_dynamic_blocks():
    """Rebuild all dynamic portfolio items with correct HTML structure."""
    items = _load_dynamic_items()
    if not items:
        return 0
    portfolio = _read('portfolio.html')
    thumbs = {}
    for item in items:
        thumbs[item['wrapper_id']] = (
            item.get('thumb')
            or _extract_inline_image_path(portfolio, item['img_id'])
            or 'images/photos/img_028.jpg'
        )
        portfolio = _remove_portfolio_block(portfolio, item['wrapper_id'])
    blocks = []
    for item in sorted(items, key=lambda x: x['index'], reverse=True):
        thumb = thumbs[item['wrapper_id']]
        iframe_src, iframe_class = _iframe_parts(item['source'], item['video_id'], item['vid'])
        blocks.append(_build_portfolio_item_html(
            item['wrapper_id'], item['video_id'], item['img_id'],
            item['source'], item['vid'], iframe_src, iframe_class, thumb,
        ))
    insert = '\n'.join(blocks)
    portfolio = _insert_portfolio_block(portfolio, insert)
    _write('portfolio.html', portfolio)
    return len(items)


def _new_uid():
    """Short random ID: 8hex-8hex."""
    chars = string.ascii_lowercase + string.digits
    a = ''.join(random.choices(chars, k=8))
    b = ''.join(random.choices(chars, k=8))
    return f'{a}-{b}'


def _unique_portfolio_thumbnail(source_path='images/photos/img_028.jpg'):
    """Copy source thumb to a new unique path so each video has its own thumbnail file."""
    src = os.path.join(BASE, source_path.lstrip('/'))
    while True:
        name = f'images/photos/pa_dyn_{"".join(random.choices(string.ascii_lowercase + string.digits, k=8))}.jpg'
        dst = os.path.join(BASE, name)
        if not os.path.exists(dst):
            break
    if os.path.isfile(src):
        shutil.copy2(src, dst)
    return name


def _count_video_thumb_usage(thumb_path, page_file=None, page_content=None):
    """How many video slots on a page reference the same thumbnail path."""
    if not thumb_path:
        return 0
    count = 0
    for _field, (page, _video_id, thumb_id) in VIDEO_FIELDS.items():
        if page_file and page != page_file:
            continue
        content = page_content if (page_content is not None and page == page_file) else _read(page)
        if _extract_inline_image_path(content, thumb_id) == thumb_path:
            count += 1
    return count


def dedicated_video_thumbnail_path(thumbnail_field, ext='.jpg'):
    slug = thumbnail_field.replace('_thumbnail', '').replace('_', '-')
    return f'images/photos/{slug}{ext}'


def recommended_video_thumbnail_path(thumbnail_field):
    """
    Safe path for the next thumbnail upload.
    If the current thumb file is shared by multiple videos, return a dedicated path
    so uploading does not overwrite other videos' images.
    """
    if thumbnail_field not in THUMBNAIL_FIELDS:
        return ''
    page, thumb_id = THUMBNAIL_FIELDS[thumbnail_field]
    content = _read(page)
    current = _extract_inline_image_path(content, thumb_id)
    if current and _count_video_thumb_usage(current, page, content) <= 1:
        return current
    ext = os.path.splitext(current or '.jpg')[1] or '.jpg'
    return dedicated_video_thumbnail_path(thumbnail_field, ext)


def _copy_image_if_exists(src_rel, dst_rel):
    src = os.path.join(BASE, src_rel.lstrip('/'))
    dst = os.path.join(BASE, dst_rel.lstrip('/'))
    if src == dst or not os.path.isfile(src):
        return dst_rel
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    return dst_rel


def resolve_video_thumbnail_save(thumbnail_field, requested_path, page_content, page_file):
    """Pick a non-shared thumbnail path; copy uploaded bytes if we had to fork."""
    requested = str(requested_path or '').strip()
    if not requested:
        return requested
    if _count_video_thumb_usage(requested, page_file, page_content) <= 1:
        return requested
    dedicated = recommended_video_thumbnail_path(thumbnail_field)
    return _copy_image_if_exists(requested, dedicated)


def _update_dynamic_item_thumb(thumbnail_field, thumb_path):
    m = re.match(r'portfolio_video_(\d+)_thumbnail$', thumbnail_field)
    if not m:
        return
    index = int(m.group(1))
    if index < 9:
        return
    items = _load_dynamic_items()
    updated = False
    for item in items:
        if item.get('index') == index:
            item['thumb'] = thumb_path
            updated = True
            break
    if updated:
        _save_dynamic_items(items)


def assign_unique_thumbnails_for_dynamic_items():
    """Give each dynamic portfolio video its own thumbnail file (fixes shared-thumb warning)."""
    items = _load_dynamic_items()
    if not items:
        return 0
    portfolio = _read('portfolio.html')
    changed = 0
    for item in items:
        field = f'portfolio_video_{item["index"]}_thumbnail'
        dedicated = dedicated_video_thumbnail_path(field)
        current = _extract_inline_image_path(portfolio, item['img_id'])
        src = current or item.get('thumb') or 'images/photos/img_028.jpg'
        if not os.path.isfile(os.path.join(BASE, dedicated.lstrip('/'))):
            _copy_image_if_exists(src, dedicated)
        portfolio = _set_video_thumbnail_paths(portfolio, item['img_id'], dedicated)
        item['thumb'] = dedicated
        changed += 1
    if changed:
        _write('portfolio.html', portfolio)
        _save_dynamic_items(items)
    return changed


def _load_dynamic_items():
    """Return list of dynamic portfolio item dicts (ordered newest-first)."""
    try:
        with open(PORTFOLIO_DYNAMIC_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_dynamic_items(items):
    os.makedirs(os.path.dirname(PORTFOLIO_DYNAMIC_FILE), exist_ok=True)
    with open(PORTFOLIO_DYNAMIC_FILE, 'w') as f:
        json.dump(items, f, indent=2)


def _extend_video_fields():
    """Register dynamic portfolio items into VIDEO_FIELDS / THUMBNAIL_FIELDS at runtime."""
    for item in _load_dynamic_items():
        field = f'portfolio_video_{item["index"]}'
        VIDEO_FIELDS[field] = ('portfolio.html', item['video_id'], item['img_id'])
        THUMBNAIL_FIELDS[f'{field}_thumbnail'] = ('portfolio.html', item['img_id'])


# Run once on import so save_content() sees all fields immediately
_extend_video_fields()


def _insert_portfolio_block(portfolio, html_block):
    """Insert a new portfolio item at the top-left of the featured video grid."""
    for anchor in (
        f'<div  id="{PORTFOLIO_GRID_ANCHOR}"',
        f'<div id="{PORTFOLIO_GRID_ANCHOR}"',
    ):
        if anchor in portfolio:
            return portfolio.replace(anchor, html_block + '\n\t\t' + anchor, 1)
    raise RuntimeError(
        f'Could not locate portfolio grid anchor "{PORTFOLIO_GRID_ANCHOR}" in portfolio.html'
    )


def add_portfolio_video(video_url, thumb_path=None):
    """
    Insert a new portfolio video at the TOP of portfolio.html.
    Returns the new field name (e.g. 'portfolio_video_9').
    """
    source, vid = _parse_video_input(video_url)
    if not source or not vid:
        raise ValueError('Invalid video URL – could not detect YouTube or Vimeo ID.')

    items = _load_dynamic_items()
    next_index = 9 + len(items)

    wrapper_id = f'pa-dyn-{_new_uid()}'
    video_id   = f'pa-vid-{_new_uid()}'
    img_id     = f'pa-img-{_new_uid()}'

    if not thumb_path:
        thumb_path = dedicated_video_thumbnail_path(f'portfolio_video_{next_index}_thumbnail')
        _copy_image_if_exists('images/photos/img_028.jpg', thumb_path)

    iframe_src, iframe_class = _iframe_parts(source, video_id, vid)

    html_block = _build_portfolio_item_html(
        wrapper_id, video_id, img_id, source, vid,
        iframe_src, iframe_class, thumb_path,
    )

    # Insert at top of the featured portfolio grid (not the first #items-holder on the page)
    portfolio = _read('portfolio.html')
    portfolio = _insert_portfolio_block(portfolio, html_block)
    _write('portfolio.html', portfolio)

    # Persist the new item (newest first in list → appears first in HTML)
    new_item = {
        'index': next_index,
        'video_id': video_id,
        'img_id': img_id,
        'wrapper_id': wrapper_id,
        'source': source,
        'vid': vid,
        'thumb': thumb_path,
    }
    items.append(new_item)
    _save_dynamic_items(items)

    # Register at runtime
    field = f'portfolio_video_{next_index}'
    VIDEO_FIELDS[field] = ('portfolio.html', video_id, img_id)
    THUMBNAIL_FIELDS[f'{field}_thumbnail'] = ('portfolio.html', img_id)

    return field


def delete_portfolio_video(index):
    """
    Remove a dynamic portfolio video (index >= 9) from portfolio.html and the registry.
    Raises ValueError if index is a static item (< 9) or not found.
    """
    if index < 9:
        raise ValueError('Cannot delete a built-in portfolio item (indices 0-8).')

    items = _load_dynamic_items()
    target = next((it for it in items if it['index'] == index), None)
    if not target:
        raise ValueError(f'Dynamic portfolio item {index} not found.')

    # Remove HTML block by wrapper_id
    portfolio = _read('portfolio.html')
    portfolio = _remove_portfolio_block(portfolio, target['wrapper_id'])
    _write('portfolio.html', portfolio)

    # Remove from dynamic list
    items = [it for it in items if it['index'] != index]
    _save_dynamic_items(items)

    # Fix grid nesting if delete left orphan closing tags
    repair_portfolio_featured_grid_structure()

    # Unregister from runtime dicts
    field = f'portfolio_video_{index}'
    VIDEO_FIELDS.pop(field, None)
    THUMBNAIL_FIELDS.pop(f'{field}_thumbnail', None)


HEADER_FIELDS = {
    # top shared menu heading
    'site_header_title': ('index.html', 'vbid-6d830c27-9ybxwvat'),
    'site_header_subtitle': ('index.html', 'element-bb8218412079d9e'),
    # homepage
    'homepage_selected_works_title': ('index.html', 'vbid-6fed10fa-kkspkfk3'),
    'homepage_selected_works_subtitle': ('index.html', 'vbid-6fed10fa-0sinf33q'),
    # portfolio
    'portfolio_featured_projects_title': ('portfolio.html', 'vbid-5582618c-nhssypbg'),
    # course
    'course_hero_title': ('cinematography-course.html', 'vbid-ca1eb861-lqbei8re'),
    'course_section_title': ('cinematography-course.html', 'vbid-c1e000b4-yvymc7bz'),
    # onset
    'onset_hero_title': ('onset-experience.html', 'vbid-ca1eb861-lqbei8re'),
    # contact
    'contact_hero_title': ('get-in-touch.html', 'vbid-d257e66b-rekun94h'),
    'contact_form_title': ('get-in-touch.html', 'vbid-d2ba6020-qfysclsq'),
}

PAGE_TITLE_FIELDS = {
    'homepage_page_title': 'index.html',
    'portfolio_page_title': 'portfolio.html',
    'course_page_title': 'cinematography-course.html',
    'onset_page_title': 'onset-experience.html',
    'contact_page_title': 'get-in-touch.html',
}

# Allowed image subfolders (relative to images/)
IMAGE_FOLDERS = ['photos', 'hq', 'icons', 'backgrounds']

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
    """Scan an HTML file and return image paths it uses (images/... only)."""
    content = _read(page_file)
    if not content:
        return []
    found = []
    found.extend(re.findall(r'(?:data-bgimg|src)="(images/[^"]+)"', content))
    found.extend(re.findall(r'background-image:url\((images/[^)]+)\)', content))

    seen = set()
    result = []
    for img in found:
        ext = os.path.splitext(img)[1].lower()
        # Keep editable visual assets only; ignore icon sprite assets to avoid
        # mixing social/UI icons with page images in admin galleries.
        if img.startswith('images/icons/'):
            continue
        if ext in ('.jpg', '.jpeg', '.png', '.webp', '.gif') and img not in seen:
            seen.add(img)
            result.append(img)
    # Homepage admin gallery should only show:
    # - Hero image (1)
    # - "Brands I Work With" logos (10)
    # Video thumbnails are edited via the video section, so exclude them here.
    if page_file == 'index.html':
        curated = ['images/photos/img_006.jpg'] + [
            f'images/photos/img_{i:03d}.jpg' for i in range(11, 21)
        ]
        curated_existing = [img for img in curated if img in seen]
        if curated_existing:
            return curated_existing
    return result


def get_page_videos(page_file):
    """Return videos and related thumbnail paths for a page."""
    content = _read(page_file)
    if not content:
        return []
    out = []
    for field, (page, video_id, thumb_id) in VIDEO_FIELDS.items():
        if page != page_file:
            continue
        src = _extract_video_src(content, video_id)
        source, video_ref = _parse_video_from_src(src)
        thumb = _extract_inline_image_path(content, thumb_id)
        out.append({
            'field': field,
            'video_id': video_id,
            'thumbnail_field': field.replace('_video_link', '_thumbnail') if field.endswith('_video_link') else field + '_thumbnail',
            'source': source,
            'value': _video_link_from_parts(source, video_ref),
            'thumbnail': thumb,
        })
    thumb_count = {}
    for v in out:
        t = v.get('thumbnail') or ''
        if t:
            thumb_count[t] = thumb_count.get(t, 0) + 1
    for v in out:
        t = v.get('thumbnail') or ''
        v['thumbnail_conflict'] = bool(t and thumb_count.get(t, 0) > 1)
        v['upload_path'] = recommended_video_thumbnail_path(v['thumbnail_field'])
    return out


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

def _extract_page_title(content):
    m = re.search(r'(<title>\s*)(.*?)(\s*</title>)', content, re.DOTALL | re.IGNORECASE)
    return (m.group(2).strip() if m else '')


def _set_page_title(content, value):
    return re.sub(
        r'(<title>\s*)(.*?)(\s*</title>)',
        lambda m: m.group(1) + value + m.group(3),
        content,
        count=1,
        flags=re.DOTALL | re.IGNORECASE
    )


def _extract_text_by_id(content, element_id):
    m = re.search(
        r'(?:<h1|<h2|<h3|<span)\s+id="' + re.escape(element_id) + r'"[^>]*>(.*?)</(?:h1|h2|h3|span)>',
        content,
        re.DOTALL
    )
    return m.group(1).strip() if m else ''


def _set_text_by_id(content, element_id, value):
    return re.sub(
        r'((?:<h1|<h2|<h3|<span)\s+id="' + re.escape(element_id) + r'"[^>]*>)(.*?)(</(?:h1|h2|h3|span)>)',
        lambda m: m.group(1) + value + m.group(3),
        content,
        flags=re.DOTALL
    )


def _extract_inline_image_path(content, element_id):
    m = re.search(
        r'<div id="' + re.escape(element_id) + r'"[^>]*style="[^"]*background-image:url\(([^)]+)\)[^"]*"',
        content,
        re.DOTALL
    )
    if not m:
        return ''
    return m.group(1).strip().strip('"').strip("'")


def _set_inline_image_path(content, element_id, img_path):
    if not img_path:
        return content
    normalized = _normalize_image_path(img_path)
    tag_pattern = r'<div id="' + re.escape(element_id) + r'"[^>]*>'

    def rebuild_tag(match):
        tag = match.group(0)
        cleaned = re.sub(r'\s+style="[^"]*"', '', tag.rstrip('>'))
        return cleaned + f' style="background-image:url({normalized});">'

    replaced, count = re.subn(tag_pattern, rebuild_tag, content, count=1, flags=re.DOTALL)
    return replaced if count else content


def _set_video_thumbnail_paths(content, element_id, img_path):
    """Update inline preview image and the nearest data-bgimg on the same portfolio item."""
    if not img_path:
        return content
    normalized = _normalize_image_path(img_path)
    content = _set_inline_image_path(content, element_id, normalized)

    marker = f'id="{element_id}"'
    pos = content.find(marker)
    if pos == -1:
        return content

    chunk_start = max(0, pos - 4000)
    chunk = content[chunk_start:pos]
    bgimg_matches = list(re.finditer(r'data-bgimg="([^"]*)"', chunk))
    if not bgimg_matches:
        return content
    last = bgimg_matches[-1]
    abs_start = chunk_start + last.start(1)
    abs_end = chunk_start + last.end(1)
    return content[:abs_start] + normalized + content[abs_end:]


def _extract_video_src(content, element_id):
    m = re.search(
        r'id="' + re.escape(element_id) + r'-vidframe"\s+src="([^"]+)"',
        content
    )
    return m.group(1).strip() if m else ''


def _parse_video_input(value):
    raw = str(value or '').strip()
    if not raw:
        return '', ''
    lower = raw.lower()
    if 'youtube.com' in lower or 'youtu.be' in lower:
        y = re.search(r'(?:v=|\/embed\/|youtu\.be\/)([A-Za-z0-9_-]{6,})', raw)
        return ('youtube', y.group(1)) if y else ('', '')
    if 'vimeo.com' in lower:
        v = re.search(r'vimeo\.com/(?:video/)?(\d+)', raw)
        return ('vimeo', v.group(1)) if v else ('', '')
    if re.fullmatch(r'\d+', raw):
        return 'vimeo', raw
    if re.fullmatch(r'[A-Za-z0-9_-]{6,}', raw):
        return 'youtube', raw
    return '', ''


def _parse_video_from_src(src):
    if not src:
        return '', ''
    s = src.lower()
    if 'youtube.com/embed/' in s:
        m = re.search(r'youtube\.com/embed/([A-Za-z0-9_-]{6,})', src, re.IGNORECASE)
        return ('youtube', m.group(1) if m else '')
    if 'player.vimeo.com/video/' in s:
        m = re.search(r'player\.vimeo\.com/video/(\d+)', src, re.IGNORECASE)
        return ('vimeo', m.group(1) if m else '')
    return '', ''


def _video_link_from_parts(source, vid):
    if not source or not vid:
        return ''
    if source == 'youtube':
        return 'https://youtu.be/' + vid
    return 'https://vimeo.com/' + vid


def _update_video_block(content, element_id, source, vid):
    if source not in ('vimeo', 'youtube') or not vid:
        return content
    # source + id attributes
    content = re.sub(
        r'(<div id="' + re.escape(element_id) + r'"[^>]*data-spimeSOURCE\s*=\s*[\'"])[^\'"]*([\'"])',
        lambda m: m.group(1) + source + m.group(2),
        content
    )
    content = re.sub(
        r'(<div id="' + re.escape(element_id) + r'"[^>]*data-spimeVIDEO_ID\s*=\s*[\'"])[^\'"]*([\'"])',
        lambda m: m.group(1) + vid + m.group(2),
        content
    )
    # maintain compatibility with templates that read data-spimeTEXT
    content = re.sub(
        r'(<div id="' + re.escape(element_id) + r'"[^>]*data-spimeTEXT\s*=\s*[\'"])[^\'"]*([\'"])',
        lambda m: m.group(1) + vid + m.group(2),
        content
    )

    container_match = re.search(r'<div id="' + re.escape(element_id) + r'"[^>]*>', content)
    cls = container_match.group(0) if container_match else ''
    autoplay = 'vid-autoplay' in cls
    loop = 'vid-loop' in cls
    mute = 'vid-mute' in cls

    if source == 'youtube':
        params = [
            'enablejsapi=1',
            'rel=0',
            'modestbranding=1',
            'playsinline=1',
            f'autoplay={1 if autoplay else 0}',
            f'mute={1 if mute else 0}',
            f'loop={1 if loop else 0}',
            'controls=0' if autoplay else 'controls=1',
        ]
        if loop:
            params.append('playlist=' + vid)
        src = 'https://www.youtube.com/embed/' + vid + '?' + '&'.join(params)
        iframe_class = 'ytplayer preview video-frame'
    else:
        src = (
            f'https://player.vimeo.com/video/{vid}?api=1&player_id={element_id}-vidframe'
            f'&autoplay={1 if autoplay else 0}'
            f'&loop={1 if loop else 0}'
            f'&title=0&byline=0&badge=0'
        )
        iframe_class = 'vimplayer preview video-frame'

    iframe_pattern = re.compile(
        r'<iframe[^>]*id="' + re.escape(element_id) + r'-vidframe"[^>]*>',
        re.DOTALL
    )

    def _rewrite_iframe_tag(m):
        tag = m.group(0)
        if 'class="' in tag:
            tag = re.sub(r'(class=")[^"]*(")', lambda c: c.group(1) + iframe_class + c.group(2), tag, count=1)
        else:
            tag = tag[:-1] + f' class="{iframe_class}">'
        if 'src="' in tag:
            tag = re.sub(r'(src=")[^"]*(")', lambda s: s.group(1) + src + s.group(2), tag, count=1)
        else:
            tag = tag[:-1] + f' src="{src}">'
        return tag

    content = iframe_pattern.sub(_rewrite_iframe_tag, content)

    # Some templates (home/course promo block) also mirror the same video in a
    # secondary container (`#pa-video-col`). Keep that fallback iframe in sync
    # so Vimeo does not persist after switching source to YouTube.
    if element_id == 'element-676387d0a7f9742':
        if source == 'youtube':
            pa_src = (
                f'https://www.youtube.com/embed/{vid}'
                '?autoplay=1&mute=1&loop=1&controls=0'
                f'&playlist={vid}&rel=0&modestbranding=1&playsinline=1'
            )
        else:
            pa_src = (
                f'https://player.vimeo.com/video/{vid}'
                '?autoplay=1&loop=1&title=0&byline=0&badge=0&muted=1'
            )
        content = re.sub(
            r'(<div id="pa-video-col"><iframe[^>]*src=")[^"]*(")',
            lambda m: m.group(1) + pa_src + m.group(2),
            content,
            count=1
        )
    return content


def _normalize_image_path(path):
    p = str(path or '').strip().strip('"').strip("'")
    p = p.lstrip('/')
    if p.startswith('images/'):
        return p
    if p.startswith('photos/') or p.startswith('hq/') or p.startswith('icons/') or p.startswith('backgrounds/'):
        return 'images/' + p
    return 'images/photos/' + p


# ── Read all editable fields ──────────────────────────────────────────────────

def get_all():
    result = {}

    # ── Course page ─────────────────────────────────────────────────────────
    c = _read('cinematography-course.html')

    # Main course video link
    source, video_ref = _parse_video_from_src(_extract_video_src(c, 'element-676387d0a7f9742'))
    result['course_video_link'] = _video_link_from_parts(source, video_ref)
    # Backward-compatible field
    result['course_vimeo_id'] = (video_ref if source == 'vimeo' else '')

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

    static_video_fields = [
        'homepage_reel_video_link',
        'homepage_selected_video_1',
        'homepage_selected_video_2',
        'homepage_selected_video_3',
        'homepage_course_video_link',
        'course_video_link',
        'portfolio_video_0',
        'portfolio_video_1',
        'portfolio_video_2',
        'portfolio_video_3',
        'portfolio_video_4',
        'portfolio_video_5',
        'portfolio_video_6',
        'portfolio_video_7',
        'portfolio_video_8',
    ]
    # Include any dynamically-added portfolio items
    dynamic_fields = [f'portfolio_video_{it["index"]}' for it in _load_dynamic_items()]
    for field in static_video_fields + dynamic_fields:
        if field not in VIDEO_FIELDS:
            continue
        page, video_id, thumb_id = VIDEO_FIELDS[field]
        page_content = _read(page)
        src = _extract_video_src(page_content, video_id)
        source, video_ref = _parse_video_from_src(src)
        result[field] = _video_link_from_parts(source, video_ref)
        thumb_key = field.replace('_video_link', '_thumbnail') if field.endswith('_video_link') else field + '_thumbnail'
        result[thumb_key] = _extract_inline_image_path(page_content, thumb_id)
    # Expose dynamic item metadata so the dashboard knows which are deletable
    result['_dynamic_portfolio_indices'] = [it['index'] for it in _load_dynamic_items()]

    # Backward-compatible values expected by existing admin inputs
    hs, hv = _parse_video_from_src(_extract_video_src(idx, 'element-741e899e73dd9a3'))
    result['homepage_reel_vimeo_id'] = hv if hs == 'vimeo' else ''
    hs, hv = _parse_video_from_src(_extract_video_src(idx, 'element-676387d0a7f9742'))
    result['homepage_course_vimeo_id'] = hv if hs == 'vimeo' else ''

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

    # ── Header/title fields ───────────────────────────────────────────────────
    for field, (page, element_id) in HEADER_FIELDS.items():
        content = _read(page)
        result[field] = _extract_text_by_id(content, element_id)

    # ── HTML <title> fields ───────────────────────────────────────────────────
    for field, page in PAGE_TITLE_FIELDS.items():
        content = _read(page)
        result[field] = _extract_page_title(content)

    return result


# ── Write editable fields ─────────────────────────────────────────────────────

def save_content(data):
    """Apply content changes. data = {field: new_value}. Returns list of errors."""
    errors = []
    pages = {page: _read(page) for page in PUBLIC_PAGES}

    # Backward compatibility aliases
    if 'homepage_reel_vimeo_id' in data and 'homepage_reel_video_link' not in data:
        data['homepage_reel_video_link'] = str(data['homepage_reel_vimeo_id'])
    if 'homepage_course_vimeo_id' in data and 'homepage_course_video_link' not in data:
        data['homepage_course_video_link'] = str(data['homepage_course_vimeo_id'])
    if 'course_vimeo_id' in data and 'course_video_link' not in data:
        data['course_video_link'] = str(data['course_vimeo_id'])

    # ── Video links + thumbnails ─────────────────────────────────────────────
    for field, (page, video_id, thumb_id) in VIDEO_FIELDS.items():
        if field in data:
            source, vid = _parse_video_input(data[field])
            if source and vid:
                pages[page] = _update_video_block(pages[page], video_id, source, vid)

    # homepage course + course page should stay in sync
    if 'homepage_course_video_link' in data and 'course_video_link' not in data:
        data['course_video_link'] = data['homepage_course_video_link']
        source, vid = _parse_video_input(data['course_video_link'])
        if source and vid:
            pages['cinematography-course.html'] = _update_video_block(
                pages['cinematography-course.html'],
                'element-676387d0a7f9742',
                source,
                vid
            )
    if 'course_video_link' in data and 'homepage_course_video_link' not in data:
        data['homepage_course_video_link'] = data['course_video_link']
        source, vid = _parse_video_input(data['homepage_course_video_link'])
        if source and vid:
            pages['index.html'] = _update_video_block(
                pages['index.html'],
                'element-676387d0a7f9742',
                source,
                vid
            )

    for thumb_field, (page, thumb_id) in THUMBNAIL_FIELDS.items():
        if thumb_field in data and str(data[thumb_field]).strip():
            requested = str(data[thumb_field]).strip()
            thumb_path = resolve_video_thumbnail_save(
                thumb_field, requested, pages[page], page,
            )
            pages[page] = _set_video_thumbnail_paths(pages[page], thumb_id, thumb_path)
            _update_dynamic_item_thumb(thumb_field, thumb_path)

    # ── Course page ──────────────────────────────────────────────────────────
    if 'course_price' in data:
        price = re.sub(r'[^\d.]', '', str(data['course_price']))
        if price:
            pages['cinematography-course.html'] = re.compile(
                r'(<span class="real-price">[\s\n]*)[\d.]+([\s\n]*</span>)'
            ).sub(lambda m: m.group(1) + price + m.group(2), pages['cinematography-course.html'])

    if 'course_buy_text' in data:
        text = str(data['course_buy_text']).strip()
        if text:
            pages['cinematography-course.html'] = re.compile(
                r'(id="vbid-c1e000b4-nold91wb"[^>]*>)[^<]*(</span>)'
            ).sub(lambda m: m.group(1) + text + m.group(2), pages['cinematography-course.html'])

    if 'course_buy_url' in data:
        url = str(data['course_buy_url']).strip()
        pages['cinematography-course.html'] = re.compile(
            r'(<a class="removable-parent" href=")[^"]*(" data-link-type="BUY")'
        ).sub(lambda m: m.group(1) + url + m.group(2), pages['cinematography-course.html'])

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

    # ── Homepage text ────────────────────────────────────────────────────────
    if 'homepage_quote' in data:
        quote = str(data['homepage_quote']).strip()
        if quote:
            pages['index.html'] = re.compile(
                r'(id="vbid-38497da5-zc2jpxkd"[^>]*>)(.*?)(</h2>)',
                re.DOTALL
            ).sub(lambda m: m.group(1) + quote + m.group(3), pages['index.html'])

    if 'homepage_about' in data:
        about = str(data['homepage_about']).strip()
        if about:
            pages['index.html'] = re.compile(
                r'(<div id="vbid-38497da5-t14shpss"[^>]*>)(.*?)(</div>)',
                re.DOTALL
            ).sub(lambda m: m.group(1) + '\n\t\t' + about + '\n\t\t' + m.group(3), pages['index.html'])

    # ── Header text fields ───────────────────────────────────────────────────
    for field, (page, element_id) in HEADER_FIELDS.items():
        if field in data:
            val = str(data[field]).strip()
            if val:
                pages[page] = _set_text_by_id(pages[page], element_id, val)

    # ── HTML <title> fields ──────────────────────────────────────────────────
    for field, page in PAGE_TITLE_FIELDS.items():
        if field in data:
            val = str(data[field]).strip()
            if val:
                pages[page] = _set_page_title(pages[page], val)

    # ── Social links (update all public pages) ────────────────────────────────
    social_keys = [k for k in data if k.startswith('social_')]
    if social_keys:
        for page in PUBLIC_PAGES:
            content = pages[page]
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
                pages[page] = content
            except Exception as e:
                errors.append(f'{page}: {e}')

    for page, content in pages.items():
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

    # Never allow overwriting UI/social icon assets via the admin upload tool.
    if folder == 'icons':
        return False, 'Icon assets cannot be replaced via upload'

    safe_name = re.sub(r'[^a-zA-Z0-9._\-]', '_', os.path.basename(basename))
    if not safe_name or '..' in safe_name:
        return False, 'Invalid filename'
    ext = os.path.splitext(safe_name)[1].lower()
    if ext not in ('.jpg', '.jpeg', '.png', '.webp', '.gif'):
        return False, 'Only JPG, PNG, WebP, GIF images allowed'

    target = os.path.join(BASE, 'images', folder, safe_name)

    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, 'wb') as f:
            f.write(raw_bytes)
        return True, None
    except Exception as e:
        return False, str(e)

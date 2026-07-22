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
import time

BASE = os.path.dirname(os.path.abspath(__file__))
BUNNY_COURSE_LINK_FILE = os.path.join(BASE, 'bunny-stream', 'course_link.txt')

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
PORTFOLIO_GALLERY_VBID = 'vbid-5582618c-l2dkyfxl'
PORTFOLIO_GRID_ITEM_CLASS = 'sub item-box  page-box style-5582618c-u4ta6ilj'
PORTFOLIO_SLOT8_WRAPPER = 'vbid-da7defbd-95tfi4qu'
PORTFOLIO_SLOT8_ITEM_CLOSES = '\n\t\t\t\t\t\n\t\t\t</div>\n\t\t</div>'
PORTFOLIO_GALLERY_TAIL = (
    '\n\t\t\n\t\t\n\t\t\n\t\n\t\t\n\t\t\t</div>\n\t\t</div>\n\t\t\n\t\t\n\t\n\t</div>\n</div>\n'
    '\t\t\t\t\t\n\t\t\t</div>\n\t\t</div>\n\t\t'
)
PORTFOLIO_DYNAMIC_FILE = os.path.join(BASE, 'data', 'portfolio_dynamic.json')
PORTFOLIO_ITEM_TEMPLATE_SLOT = 'vbid-1088fcb3-wzf22a8v'
PORTFOLIO_ITEM_TEMPLATE_VIDEO = 'vbid-1088fcb3-17vdtkfy'
PORTFOLIO_ITEM_TEMPLATE_IMG = 'vbid-1088fcb3-upubmm8p'
PORTFOLIO_ITEM_TEMPLATE_LIGHTBOX = 'vbid-1088fcb3-bxuolnsw'
PORTFOLIO_ITEM_TEMPLATE_VID = 'xH02vPx-61U'
_portfolio_item_template_cache = None


def _get_portfolio_item_template():
    """Return a complete static portfolio grid item used as the dynamic-item HTML template."""
    global _portfolio_item_template_cache
    if _portfolio_item_template_cache is not None:
        return _portfolio_item_template_cache

    portfolio = _read('portfolio.html')
    region_start, region_end = _featured_portfolio_grid_region(portfolio)
    append_at = _portfolio_item_append_point(
        portfolio, PORTFOLIO_ITEM_TEMPLATE_SLOT, region_start, region_end
    )
    wrapper_match = re.search(
        r'<div\s+id="' + re.escape(PORTFOLIO_ITEM_TEMPLATE_SLOT) + r'"[^>]*>',
        portfolio[region_start:region_end],
    )
    if not wrapper_match:
        raise RuntimeError(
            f'Could not locate portfolio item template "{PORTFOLIO_ITEM_TEMPLATE_SLOT}"'
        )
    block_start = region_start + wrapper_match.start()
    _portfolio_item_template_cache = portfolio[block_start:append_at]
    return _portfolio_item_template_cache


def _build_portfolio_item_html(wrapper_id, video_id, img_id, source, vid,
                               iframe_src, iframe_class, thumb_path):
    """Build portfolio grid item HTML by cloning a static slot so matrix layout stays valid."""
    block = _get_portfolio_item_template()
    block = block.replace(PORTFOLIO_ITEM_TEMPLATE_SLOT, wrapper_id)
    block = block.replace(PORTFOLIO_ITEM_TEMPLATE_VIDEO, video_id)
    block = block.replace(PORTFOLIO_ITEM_TEMPLATE_IMG, img_id)
    block = block.replace(f'{PORTFOLIO_ITEM_TEMPLATE_IMG}-holder', f'{img_id}-holder')
    block = block.replace(PORTFOLIO_ITEM_TEMPLATE_LIGHTBOX, wrapper_id)
    block = block.replace(f'/{PORTFOLIO_ITEM_TEMPLATE_LIGHTBOX}', f'#{wrapper_id}')
    block = block.replace(f'#{PORTFOLIO_ITEM_TEMPLATE_LIGHTBOX}', f'#{wrapper_id}')

    block = re.sub(
        r'background-image:url\([^)]+\)',
        f'background-image:url({thumb_path})',
        block,
        count=1,
    )
    block = re.sub(
        r'data-bgimg="[^"]*"',
        f'data-bgimg="{thumb_path}"',
        block,
        count=1,
    )

    if source == 'youtube':
        video_inner = (
            f'<div class="yt-facade" data-vid="{vid}" onclick="playYT(this)">'
            f'<img src="https://img.youtube.com/vi/{vid}/hqdefault.jpg" alt="Video thumbnail" loading="lazy">'
            f'<button class="yt-play-btn" aria-label="Play">'
            f'<svg viewBox="0 0 68 48"><path d="M66.52 7.74c-.78-2.93-2.49-5.41-5.42-6.19C55.79.13 34 0 34 0S12.21.13 6.9 1.55c-2.93.78-4.63 3.26-5.42 6.19C.06 13.05 0 24 0 24s.06 10.95 1.48 16.26c.78 2.93 2.49 5.41 5.42 6.19C12.21 47.87 34 48 34 48s21.79-.13 27.1-1.55c2.93-.78 4.64-3.26 5.42-6.19C67.94 34.95 68 24 68 24s-.06-10.95-1.48-16.26z" fill="#f00"/>'
            f'<path d="M45 24 27 14v20z" fill="#fff"/></svg></button></div>'
        )
    else:
        video_inner = (
            f'<iframe class="{iframe_class} preview video-frame" id="{video_id}-vidframe" '
            f'src="{iframe_src}" frameborder="0" width="100%" height="100%"></iframe>'
        )

    video_open = (
        r'(<div id="' + re.escape(video_id) + r'" class="preview-element preview-video-source[^"]*"[^>]*>)'
    )
    block = re.sub(
        video_open + r'.*?(</div>\s*</div>\s*\n\s*</div>\s*\n</div>)',
        lambda m: (
            m.group(1)
            + f" data-spimeTEXT = '{vid}'  data-spimeVIDEO_ID = '{vid}'  "
            f"data-spimeVID_COVER = 'True'  data-spimeSOURCE = '{source}'  "
            f"data-spimeCONTEXT = 'PREVIEW'  data-spimeVBID = '{video_id}'  >\n\t\t"
            + video_inner
            + '\n\t\t\n\t</div>\n</div>\n \n         \n        \n    </div>\n</div>'
        ),
        block,
        count=1,
        flags=re.DOTALL,
    )
    return block


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
    try:
        region_start, region_end = _featured_portfolio_grid_region(portfolio)
        if wrapper_id in portfolio[region_start:region_end]:
            wrapper_match = re.search(
                r'<div\s+id="' + re.escape(wrapper_id) + r'"[^>]*>',
                portfolio[region_start:region_end],
            )
            if wrapper_match:
                block_start = region_start + wrapper_match.start()
                block_end = _portfolio_item_append_point(
                    portfolio, wrapper_id, region_start, region_end
                )
                portfolio = portfolio[:block_start] + portfolio[block_end:]
                return repair_portfolio_featured_grid_structure(portfolio)
    except RuntimeError:
        pass

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


def _featured_portfolio_grid_region(portfolio):
    """Return (start, end) slice bounds for the featured portfolio video gallery."""
    gallery_pos = portfolio.find(f'data-vbid="{PORTFOLIO_GALLERY_VBID}"')
    if gallery_pos == -1:
        raise RuntimeError(
            f'Could not locate portfolio gallery "{PORTFOLIO_GALLERY_VBID}" in portfolio.html'
        )
    end_marker = '<!-- GALLERIES END -->'
    end_pos = portfolio.find(end_marker, gallery_pos)
    if end_pos == -1:
        raise RuntimeError('Could not locate featured portfolio gallery end in portfolio.html')
    return gallery_pos, end_pos


def _portfolio_grid_wrapper_ids(portfolio, region_start, region_end):
    region = portfolio[region_start:region_end]
    return [
        match.group(1)
        for match in re.finditer(
            r'<div\s+id="([^"]+)"\s+class="' + re.escape(PORTFOLIO_GRID_ITEM_CLASS),
            region,
        )
    ]


PORTFOLIO_ITEM_END_AFTER_LAYOUT_RE = (
    r'<div class="layout-settings"[^>]*data-type="multi"[^>]*></div>\s*'
    r'(?:\t*\n)?\t*\t*\t*\t*\n?\t*\t*\t*</div>\s*'
    r'(?:\t*\n)?\t*\t*</div>'
)


def _portfolio_item_append_point(portfolio, wrapper_id, region_start, region_end):
    """Return the index immediately after a full grid item block."""
    wrapper_match = re.search(
        r'<div\s+id="' + re.escape(wrapper_id) + r'"[^>]*>',
        portfolio[region_start:region_end],
    )
    if not wrapper_match:
        raise RuntimeError(
            f'Could not locate portfolio grid item "{wrapper_id}" in portfolio.html'
        )

    tail_start = region_start + wrapper_match.start()
    end_match = re.search(
        PORTFOLIO_ITEM_END_AFTER_LAYOUT_RE,
        portfolio[tail_start:region_end],
        flags=re.DOTALL,
    )
    if not end_match:
        raise RuntimeError(
            f'Could not locate end of portfolio grid item "{wrapper_id}" in portfolio.html'
        )
    return tail_start + end_match.end()


def _insert_portfolio_block(portfolio, html_block):
    """Append a new portfolio item after the last item in the featured video grid."""
    region_start, region_end = _featured_portfolio_grid_region(portfolio)
    wrapper_ids = _portfolio_grid_wrapper_ids(portfolio, region_start, region_end)
    if not wrapper_ids:
        raise RuntimeError('Could not locate any portfolio grid items in portfolio.html')

    insert_at = _portfolio_item_append_point(
        portfolio, wrapper_ids[-1], region_start, region_end
    )
    return portfolio[:insert_at] + '\n\n\t' + html_block + portfolio[insert_at:]


def cleanup_orphan_dynamic_items():
    """Remove dynamic registry entries whose HTML block is missing from portfolio.html."""
    items = _load_dynamic_items()
    if not items:
        return 0

    portfolio = _read('portfolio.html')
    kept = [item for item in items if item['wrapper_id'] in portfolio]
    removed = len(items) - len(kept)
    if not removed:
        return 0

    _save_dynamic_items(kept)
    for item in items:
        if item in kept:
            continue
        field = f'portfolio_video_{item["index"]}'
        VIDEO_FIELDS.pop(field, None)
        THUMBNAIL_FIELDS.pop(f'{field}_thumbnail', None)
    return removed


def repair_portfolio_dynamic_blocks():
    """Rebuild dynamic portfolio items as proper grid siblings after slot 8."""
    global _portfolio_item_template_cache
    _portfolio_item_template_cache = None
    items = sorted(_load_dynamic_items(), key=lambda x: x['index'])
    portfolio = _read('portfolio.html')
    region_start, region_end = _featured_portfolio_grid_region(portfolio)

    slot8_pos = portfolio.find(f'id="{PORTFOLIO_SLOT8_WRAPPER}"', region_start, region_end)
    if slot8_pos == -1:
        raise RuntimeError(f'Could not locate portfolio slot 8 "{PORTFOLIO_SLOT8_WRAPPER}"')

    ls_match = re.search(
        r'<div class="layout-settings"[^>]*data-type="multi"[^>]*></div>',
        portfolio[slot8_pos:region_end],
    )
    if not ls_match:
        raise RuntimeError('Could not locate portfolio slot 8 layout marker')

    cut_start = slot8_pos + ls_match.end()
    galleries_end = portfolio.find('<!-- GALLERIES END -->', cut_start)
    if galleries_end == -1:
        raise RuntimeError('Could not locate portfolio gallery end marker')

    blocks = []
    for item in items:
        thumb = (
            item.get('thumb')
            or _extract_inline_image_path(portfolio, item['img_id'])
            or 'images/photos/img_028.jpg'
        )
        iframe_src, iframe_class = _iframe_parts(item['source'], item['video_id'], item['vid'])
        blocks.append(_build_portfolio_item_html(
            item['wrapper_id'], item['video_id'], item['img_id'],
            item['source'], item['vid'], iframe_src, iframe_class, thumb,
        ))

    dynamic_html = '\n\n\t'.join(blocks)
    replacement = PORTFOLIO_SLOT8_ITEM_CLOSES
    if dynamic_html:
        replacement += '\n\n\t' + dynamic_html
    replacement += PORTFOLIO_GALLERY_TAIL

    portfolio = portfolio[:cut_start] + replacement + portfolio[galleries_end:]
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
        try:
            shutil.copy2(src, dst)
        except OSError as e:
            raise OSError(
                f'Cannot write thumbnail {name}: {e}. '
                'Run: chown -R aynbeirut:aynbeirut on the site files.'
            ) from e
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
    try:
        shutil.copy2(src, dst)
    except OSError as e:
        raise OSError(
            f'Cannot write thumbnail {dst_rel}: {e}. '
            'Fix file ownership on the server (chown aynbeirut:aynbeirut) or use a new thumbnail path.'
        ) from e
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


def _refresh_dynamic_video_fields():
    """Sync runtime VIDEO_FIELDS / THUMBNAIL_FIELDS with portfolio_dynamic.json."""
    for key in list(VIDEO_FIELDS.keys()):
        m = re.match(r'portfolio_video_(\d+)$', key)
        if m and int(m.group(1)) >= 9:
            VIDEO_FIELDS.pop(key, None)
            THUMBNAIL_FIELDS.pop(f'{key}_thumbnail', None)
    for item in _load_dynamic_items():
        field = f'portfolio_video_{item["index"]}'
        VIDEO_FIELDS[field] = ('portfolio.html', item['video_id'], item['img_id'])
        THUMBNAIL_FIELDS[f'{field}_thumbnail'] = ('portfolio.html', item['img_id'])


def _extend_video_fields():
    """Register dynamic portfolio items into VIDEO_FIELDS / THUMBNAIL_FIELDS at runtime."""
    _refresh_dynamic_video_fields()


def normalize_dynamic_portfolio_indices():
    """Ensure dynamic items use unique sequential indices (9+) in registry order."""
    items = _load_dynamic_items()
    if not items:
        return 0
    changed = False
    for i, item in enumerate(items):
        want = 9 + i
        if item.get('index') != want:
            item['index'] = want
            changed = True
    if not changed:
        return 0
    _save_dynamic_items(items)
    _refresh_dynamic_video_fields()
    return len(items)


# Run once on import so save_content() sees all fields immediately
normalize_dynamic_portfolio_indices()
_extend_video_fields()


def add_portfolio_video(video_url, thumb_path=None):
    """
    Append a new portfolio video after the last item in the featured grid.
    Returns the new field name (e.g. 'portfolio_video_9').
    """
    normalize_dynamic_portfolio_indices()

    source, vid = _parse_video_input(video_url)
    if not source or not vid:
        raise ValueError('Invalid video URL – could not detect YouTube or Vimeo ID.')

    items = _load_dynamic_items()
    next_index = max((it['index'] for it in items), default=8) + 1

    if not thumb_path:
        thumb_path = _unique_portfolio_thumbnail('images/photos/img_028.jpg')

    new_item = {
        'index': next_index,
        'video_id': f'pa-vid-{_new_uid()}',
        'img_id': f'pa-img-{_new_uid()}',
        'wrapper_id': f'pa-dyn-{_new_uid()}',
        'source': source,
        'vid': vid,
        'thumb': thumb_path,
    }
    items.append(new_item)
    _save_dynamic_items(items)
    _refresh_dynamic_video_fields()
    repair_portfolio_dynamic_blocks()

    return f'portfolio_video_{next_index}'


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

    items = [it for it in items if it['index'] != index]
    _save_dynamic_items(items)
    normalize_dynamic_portfolio_indices()
    _refresh_dynamic_video_fields()
    repair_portfolio_dynamic_blocks()

    return True


HEADER_FIELDS = {
    # top shared menu heading
    'site_header_title': ('index.html', 'vbid-6d830c27-9ybxwvat'),
    'site_header_subtitle': ('index.html', 'element-bb8218412079d9e'),
    # homepage
    'homepage_selected_works_title': ('index.html', 'vbid-6fed10fa-kkspkfk3'),
    'homepage_selected_works_subtitle': ('index.html', 'vbid-6fed10fa-0sinf33q'),
    # portfolio
    'portfolio_hero_title': ('portfolio.html', 'vbid-b3e6bf42-lqbei8re'),
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
    # Strict per-page curation for admin image galleries.
    # This keeps only intentionally editable visual assets and avoids
    # showing lightbox/ui helper images as "extra" replace items.
    curated_by_page = {
        # Homepage: 1 hero + 10 "Brands I Work With" logos.
        'index.html': ['images/photos/img_006.jpg'] + [
            f'images/photos/img_{i:03d}.jpg' for i in range(11, 21)
        ],
        # Portfolio: page hero image only (video thumbnails handled in Videos).
        'portfolio.html': ['images/photos/img_028.jpg'],
        # Cinematography course setup panel: 4 feature icons only.
        'cinematography-course.html': [
            'images/photos/img_040.jpg',
            'images/photos/img_041.jpg',
            'images/photos/img_042.jpg',
            'images/photos/img_043.jpg',
        ],
        # Onset experience page: hero image only.
        'onset-experience.html': ['images/photos/img_030.jpg'],
        # Contact page: no standalone replaceable images.
        'get-in-touch.html': [],
    }
    if page_file in curated_by_page:
        curated = curated_by_page[page_file]
        return [img for img in curated if img in seen]

    # Fallback for any future page: exclude video thumbs from image gallery.
    video_thumbs = {
        v.get('thumbnail') for v in get_page_videos(page_file)
        if v.get('thumbnail')
    }
    return [img for img in result if img not in video_thumbs]


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


def _clear_inline_image_path(content, element_id):
    tag_pattern = r'<div id="' + re.escape(element_id) + r'"[^>]*>'

    def rebuild_tag(match):
        tag = match.group(0)
        cleaned = re.sub(r'\s+style="[^"]*"', '', tag.rstrip('>'))
        return cleaned + ' style="">'

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


def _clear_video_thumbnail_paths(content, element_id):
    """Clear inline preview image and nearest data-bgimg value for a video card."""
    content = _clear_inline_image_path(content, element_id)

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
    return content[:abs_start] + '' + content[abs_end:]


def _extract_video_src(content, element_id):
    m = re.search(
        r'id="' + re.escape(element_id) + r'-vidframe"\s+src="([^"]+)"',
        content
    )
    if m:
        return m.group(1).strip()

    block_m = re.search(r'<div id="' + re.escape(element_id) + r'"[^>]*>', content)
    if not block_m:
        return ''

    chunk = content[block_m.start():block_m.start() + 2500]

    yt_m = re.search(r'class="yt-facade"\s+data-vid="([A-Za-z0-9_-]+)"', chunk)
    if yt_m:
        return f'https://www.youtube.com/embed/{yt_m.group(1)}'

    src_m = re.search(r"data-spimeSOURCE\s*=\s*['\"](\w+)['\"]", chunk)
    vid_m = re.search(r"data-spimeVIDEO_ID\s*=\s*['\"]([^'\"]+)['\"]", chunk)
    if src_m and vid_m:
        source, vid = src_m.group(1), vid_m.group(1)
        if source == 'youtube':
            return f'https://www.youtube.com/embed/{vid}'
        if source == 'vimeo':
            return f'https://player.vimeo.com/video/{vid}'

    return ''


def _bunny_library_id():
    if not os.path.exists(BUNNY_COURSE_LINK_FILE):
        return ''
    for line in open(BUNNY_COURSE_LINK_FILE, encoding='utf-8'):
        s = line.strip()
        if not s or s.startswith('#'):
            continue
        m = re.search(r'\b(\d{3,})\b', s)
        if m:
            return m.group(1)
    return ''


def _parse_video_input(value):
    raw = str(value or '').strip()
    if not raw:
        return '', ''
    lower = raw.lower()
    if 'mediadelivery.net' in lower:
        m = re.search(r'/embed/(\d+)/([0-9a-fA-F-]{36})', raw)
        if m:
            return 'bunny', m.group(2)
    if re.fullmatch(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', raw):
        return 'bunny', raw
    if 'youtube.com' in lower or 'youtu.be' in lower:
        y = re.search(
            r'(?:v=|/embed/|/shorts/|/live/|youtu\.be/)([A-Za-z0-9_-]{6,})',
            raw,
            re.IGNORECASE,
        )
        return ('youtube', y.group(1)) if y else ('', '')
    if 'vimeo.com' in lower or 'player.vimeo.com' in lower:
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
    if 'mediadelivery.net/embed/' in s:
        m = re.search(r'/embed/\d+/([0-9a-fA-F-]{36})', src, re.IGNORECASE)
        return ('bunny', m.group(1) if m else '')
    return '', ''


def _video_link_from_parts(source, vid):
    if not source or not vid:
        return ''
    if source == 'youtube':
        return 'https://youtu.be/' + vid
    if source == 'bunny':
        lib = _bunny_library_id() or '659916'
        return f'https://iframe.mediadelivery.net/embed/{lib}/{vid}'
    return 'https://vimeo.com/' + vid


_YT_PLAY_SVG = (
    '<svg viewBox="0 0 68 48">'
    '<path d="M66.52 7.74c-.78-2.93-2.49-5.41-5.42-6.19C55.79.13 34 0 34 0S12.21.13 6.9 1.55c-2.93.78-4.63 3.26-5.42 6.19C.06 13.05 0 24 0 24s.06 10.95 1.48 16.26c.78 2.93 2.49 5.41 5.42 6.19C12.21 47.87 34 48 34 48s21.79-.13 27.1-1.55c2.93-.78 4.64-3.26 5.42-6.19C67.94 34.95 68 24 68 24s-.06-10.95-1.48-16.26z" fill="#f00"/>'
    '<path d="M45 24 27 14v20z" fill="#fff"/></svg>'
)


def _youtube_facade_html(vid):
    return (
        f'<div class="yt-facade" data-vid="{vid}" onclick="playYT(this)">'
        f'<img src="https://img.youtube.com/vi/{vid}/hqdefault.jpg" alt="Video thumbnail" loading="lazy">'
        f'<button class="yt-play-btn" aria-label="Play">{_YT_PLAY_SVG}</button></div>'
    )


def _video_iframe_html(element_id, src, iframe_class):
    return (
        f'<iframe class="{iframe_class} preview video-frame" id="{element_id}-vidframe" '
        f'src="{src}" frameborder="0" width="100%" height="100%"></iframe>'
    )


def _use_youtube_facade(element_id, cls, autoplay):
    if autoplay or 'vid-autoplay' in cls:
        return False
    return element_id.startswith('vbid-') or element_id.startswith('pa-vid-')


def _replace_video_inner(content, element_id, new_inner):
    eid = re.escape(element_id)
    facade_pat = re.compile(
        r'(<div id="' + eid + r'"[^>]*>)\s*<div class="yt-facade"[^>]*>.*?</div>(\s*</div>)',
        re.DOTALL,
    )
    if facade_pat.search(content):
        return facade_pat.sub(lambda m: m.group(1) + '\n\t\t' + new_inner + m.group(2), content, count=1)

    iframe_pat = re.compile(
        r'(<div id="' + eid + r'"[^>]*>)\s*<iframe[^>]*id="' + eid + r'-vidframe"[^>]*>.*?</iframe>(\s*</div>)',
        re.DOTALL,
    )
    if iframe_pat.search(content):
        return iframe_pat.sub(lambda m: m.group(1) + '\n\t\t' + new_inner + m.group(2), content, count=1)

    open_pat = re.compile(r'(<div id="' + eid + r'"[^>]*>)')
    return open_pat.sub(lambda m: m.group(1) + '\n\t\t' + new_inner + '\n\t', content, count=1)


def _update_video_block(content, element_id, source, vid):
    if source not in ('vimeo', 'youtube', 'bunny') or not vid:
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

    if source == 'bunny':
        src = 'about:blank'
        iframe_class = 'bunnyplayer preview video-frame'
    elif source == 'youtube':
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
            f'&muted={1 if mute or autoplay else 0}'
            f'&controls=1'
            f'&title=0&byline=0&badge=0&background=0&autopause=0&dnt=1'
        )
        iframe_class = 'vimplayer preview video-frame'

    if source == 'youtube' and _use_youtube_facade(element_id, cls, autoplay):
        new_inner = _youtube_facade_html(vid)
    else:
        new_inner = _video_iframe_html(element_id, src, iframe_class)

    content = _replace_video_inner(content, element_id, new_inner)

    # Some templates (home/course promo block) also mirror the same video in a
    # secondary container (`#pa-video-col`). Keep that fallback iframe in sync
    # so Vimeo does not persist after switching source to YouTube.
    if element_id == 'element-676387d0a7f9742':
        if source == 'youtube':
            pa_src = (
                f'https://www.youtube.com/embed/{vid}'
                '?enablejsapi=1&autoplay=1&mute=1&loop=1&controls=1'
                f'&playlist={vid}&rel=0&modestbranding=1&playsinline=1'
            )
        elif source == 'bunny':
            pa_src = ''
        else:
            pa_src = (
                f'https://player.vimeo.com/video/{vid}'
                '?autoplay=1&loop=1&title=0&byline=0&badge=0&muted=1'
            )
        content = re.sub(
            r'(<iframe id="pa-course-iframe"[^>]*src=")[^"]*(")',
            lambda m: m.group(1) + pa_src + m.group(2),
            content,
            count=1,
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
    normalize_dynamic_portfolio_indices()
    _refresh_dynamic_video_fields()
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
    result['course_price'] = m.group(1).strip() if m else '149'

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
    dynamic_indices = [it['index'] for it in _load_dynamic_items()]
    result['dynamic_portfolio_indices'] = dynamic_indices
    result['_dynamic_portfolio_indices'] = dynamic_indices

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
            raw = str(data[field]).strip()
            if not raw:
                continue
            source, vid = _parse_video_input(raw)
            if source and vid:
                pages[page] = _update_video_block(pages[page], video_id, source, vid)
            else:
                errors.append(
                    f'{field}: could not parse video link — paste a YouTube or Vimeo URL/ID'
                )

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
        if thumb_field in data:
            requested = str(data[thumb_field]).strip()
            if requested:
                thumb_path = resolve_video_thumbnail_save(
                    thumb_field, requested, pages[page], page,
                )
                pages[page] = _set_video_thumbnail_paths(pages[page], thumb_id, thumb_path)
                _update_dynamic_item_thumb(thumb_field, thumb_path)
            else:
                pages[page] = _clear_video_thumbnail_paths(pages[page], thumb_id)
                _update_dynamic_item_thumb(thumb_field, '')

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


def _bump_image_cache_references(rel_path):
    """Append ?v=timestamp to HTML references after an image file is replaced."""
    rel_path = rel_path.lstrip('/')
    if rel_path.startswith('images/'):
        rel_path = rel_path[len('images/'):]
    paths = {rel_path, 'images/' + rel_path}
    ts = str(int(time.time()))
    for page in PUBLIC_PAGES:
        content = _read(page)
        orig = content
        for p in paths:
            content = re.sub(
                re.escape(p) + r'(\?v=\d+)?',
                p + '?v=' + ts,
                content
            )
        if content != orig:
            _write(page, content)


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
        rel = f'{folder}/{safe_name}'
        _bump_image_cache_references(rel)
        return True, None
    except Exception as e:
        return False, str(e)

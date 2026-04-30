# Pierre Azar Web — Project README

## Overview
Website for Pierre Azar (pierreazar.com), built on the Indigo website builder platform.

**VPS:** 104.207.71.117 | AlmaLinux 9.7 | Apache  
**Python server:** `server.py` running as `aynbeirut`, `PA_NO_SSL=1 PA_PORT=8080`  
**Document root:** `/home/aynbeirut/public_html/pierreazar.com/`  
**Local workspace:** `/home/anwar/Documents/pierre azar web/`  
**GitHub:** `indigo-communication/pierreazar`, master branch  
**GitHub CLI switch:** `gh auth switch --user indigo-communication` before push

---

## Admin Panel
Located at `/admin/`. Auth via `pa_admin` cookie (managed by `server.py`).  
**Admin login:** contact@pierreazar.com / 2025pa.

### Admin Pages
| Page | Purpose |
|------|---------|
| `admin/index.html` | Dashboard — real member stats + contact form submissions |
| `admin/members.html` | Member list with search, stats (total/active/premium) |
| `admin/submissions.html` | Contact form submissions |
| `admin/course-sales.html` | Course sales / orders |
| `admin/finance.html` | Finance overview |
| `admin/reports.html` | Reports |
| `admin/contacts.html` | Contacts |
| `admin/task.html` | Task management |
| `admin/content-editor.html` | Site content editor |
| `admin/payment-settings.html` | Payment gateway settings |
| `admin/change-password.html` | Admin password change |

---

## Files
| File | Purpose |
|------|---------|
| `index.html` | Home page |
| `cinematography-course.html` | Cinematography course page |
| `get-in-touch.html` | Contact page (sends to `/send-message`) |
| `member-login.html` | Member login portal |
| `member-activate.html` | Member activation flow |
| `member-upgrade.html` | Member upgrade to premium |
| `server.py` | Python HTTP server — handles auth, API, email, member CRUD |
| `mail_config.py` | SMTP config (gitignored — credentials) |

---

## Session History

---

### Session: April 29, 2026 — Hero, Course, Stats

#### What was done
1. **Hero section:** Image+video container nudged right via `translateX(4%)` on `#vbid-38497da5-v22rkfln-holder`. Image offset left `translateX(-4%)`. Click on image fades to video (1.2s CSS transition).
2. **Stats section:** Centered `#vbid-9f13b7c7-tbpwoygg` using flex + justify-content:center.
3. **"About the Course" section:** 2-column layout — Vimeo iframe left (`#pa-video-col`), text right. Vimeo video ID `291044785`.
4. **Course video:** Set to click-to-play only (no autoplay).

#### Known issues
- Platform's `vid-cover` JS rebuilds iframes from `data-spime*` attributes, overriding src changes. Videos 1–4 autoplay override attempts failed.

---

### Session: April 30, 2026 — Admin Panel Overhaul

#### What was done

1. **`admin/change-password.html` created** — dedicated admin password change page. Calls `POST /admin/change-password`.

2. **"Change Password" nav link added to all 13 admin pages** — appears in the SETTINGS section of every page sidebar.

3. **Removed "Change Password" form from `content-editor.html`** — it was previously embedded there.

4. **Removed duplicate `editor.html` nav link from 8 pages** — old legacy nav item (`editor.html`) removed from: index, customer, finance, contacts, index-2, task, reports, editor itself.

5. **`server.py` updated** — `/api/admin/members` now returns `premium` and `premium_since` fields in addition to email, name, created_at, last_login, active.

6. **Dashboard (`admin/index.html`) rebuilt** — replaced the entire fake demo template content with:
   - 4 stat cards: Total Members, Premium Members, Free Members, Active Today (all live from `/api/admin/members`)
   - Recent Members table (latest 10, sorted by joined date)
   - Contact Form Submissions table (from `/api/submissions`, newest first, with "New" badge count)

7. **`admin/members.html` loading fix** — page was stuck on preloader because it loaded `custom.min.js` which doesn't contain the preloader-hiding code. Fixed by replacing with `custom.js` + `deznav-init.js` (matches all other pages).

8. **Members nav icon added to all admin pages** — the Members sidebar link was only on the dashboard. Added to all 11 active admin pages.

#### What worked
- All changes deployed to VPS via SCP and server restarted.
- Preloader fix confirmed (root cause: custom.min.js vs custom.js).

#### What to verify in browser
- Dashboard stats load correctly from live member data
- Contact form submissions display in dashboard
- Members page opens without infinite loading
- All pages show the Members icon in sidebar

#### Where to continue next session
- Consider adding "mark as read" action on contact form submissions
- Consider adding disable/enable member toggle on members page
- If Pierre approves: switch background videos 1–4 to YouTube embeds for reliable silent autoplay

---

## Deploy Commands

### Single file
```bash
scp "/home/anwar/Documents/pierre azar web/admin/FILE.html" root@104.207.71.117:/home/aynbeirut/public_html/pierreazar.com/admin/
```

### Server restart
```bash
ssh root@104.207.71.117 "kill \$(pgrep -f 'python3 server.py') 2>/dev/null; sleep 1; cd /home/aynbeirut/public_html/pierreazar.com && PA_NO_SSL=1 PA_PORT=8080 nohup python3 server.py > /tmp/pa_server.log 2>&1 &"
```

## Git Push
```bash
cd "/home/anwar/Documents/pierre azar web"
gh auth switch --user indigo-communication
git add -A
git commit -m "message"
git push origin master
gh auth switch --user AynBeirut
```


**VPS:** 104.207.71.117 | AlmaLinux 9.7 | Apache  
**Document root:** `/home/aynbeirut/public_html/pierreazar.com/`  
**Local workspace:** `/home/anwar/Documents/pierre azar web/`  
**GitHub:** `indigo-communication/pierreazar`, master branch  
**GitHub CLI switch:** `gh auth switch --user indigo-communication` before push

---

## Files
| File | Purpose |
|------|---------|
| `index.html` | Home page — all CSS/JS injected before `</head>` and `</body>` |
| `cinematography-course.html` | Cinematography course page |

---

## Current State (Session: April 29, 2026)

### What was done
1. **Hero section (top):** Image+video container nudged right via `translateX(4%)` on `#vbid-38497da5-v22rkfln-holder`. Image container independently offset left `translateX(-4%)` on `#vbid-38497da5-v22rkfln` to fine-tune position. Click on image fades to video with 1.2s CSS transition (JS injected before `</body>`).
2. **Stats section:** Centered (`#vbid-9f13b7c7-tbpwoygg`) using flex + justify-content:center on `.text-side`.
3. **"About the Course" section:** 2-column layout injected — Vimeo iframe left (`#pa-video-col`), text right. Vimeo video ID `291044785`.
4. **Course video (both instances):** Set to click-to-play only (no autoplay, no loop) — `src` ends with `?title=0&byline=0&portrait=0`.

### Known issues / pending
- **Videos 1–4 autoplay silent:** The platform's `vid-cover` JS rebuilds iframes from `data-spime*` attributes, overriding any src changes. Multiple approaches failed (MutationObserver, createElement interceptor — the latter broke all video playback). Currently left with platform default (plays with sound when browser allows).
- **Next step:** Client may agree to switch background videos (1–4) to YouTube embeds (free, reliable silent autoplay via `?autoplay=1&mute=1&loop=1`). If yes, replace Vimeo iframes and `data-spimeSOURCE`/`data-spimeVIDEO_ID` attributes.
- **Git push pending:** `index.html` and `cinematography-course.html` not yet committed to `indigo-communication/pierreazar`.

### Key CSS injected (before `</head>`)
- `#vbid-c1e000b4-ylaf0aoi` — 2-col About section  
- `#vbid-9f13b7c7-tbpwoygg` — Stats centering  
- `#vbid-38497da5-v22rkfln-holder` — Hero container translateX(4%)  
- `#vbid-38497da5-v22rkfln` — Hero image translateX(-4%), overflow:hidden  
- `.preview-video-holder` on hero — opacity:0 → 1 via `pa-visible` class on click  

### Key JS injected (before `</body>`)
- Hero image click → fades to video (`pa-visible` class, 1.2s transition, then removes background-image)

---

## Section IDs Reference
| Section | VBID |
|---------|------|
| Hero section item | `vbid-38497da5-0pcncze1` |
| Hero image+video holder | `vbid-38497da5-v22rkfln-holder` |
| Hero image+video inner | `vbid-38497da5-v22rkfln` |
| Hero video (Vimeo 1000452483) | `element-741e899e73dd9a3` |
| 3-item gallery section | `vbid-6fed10fa-*` |
| Stats section | `vbid-9f13b7c7-tbpwoygg` |
| About the Course section | `vbid-c1e000b4-ylaf0aoi` |

---

## Deploy Command
```bash
scp "/home/anwar/Documents/pierre azar web/index.html" root@104.207.71.117:/home/aynbeirut/public_html/pierreazar.com/
```

## Git Push (when ready)
```bash
gh auth switch --user indigo-communication
git add "pierre azar web/cinematography-course.html" "pierre azar web/index.html"
git commit -m "Home page + course page: 2-col layout, stats centered, hero video positioned"
git push origin master
gh auth switch --user AynBeirut
```

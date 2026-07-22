# Pierre Azar Web — Project README

## Overview
Website for Pierre Azar (pierreazar.com), built on the Indigo website builder platform.

**VPS:** 104.207.71.117 | AlmaLinux 9.7 | Apache  
**Python server:** `server.py` running as `aynbeirut`, `PA_NO_SSL=1 PA_PORT=8080`  
**Document root:** `/home/aynbeirut/public_html/pierreazar.com/`  
**Local workspace:** `/home/anwar/Documents/pierre azar web/`  
**GitHub:** `indigo-communication/pierreazar`, master branch  
**GitHub CLI switch:** `gh auth switch --user indigo-communication` before push

## Current status — Premium Buyer Accounts
- Verified payments now idempotently create or upgrade a Premium Member.
- Existing member password hashes are preserved. New paid buyers receive a
  single-use, hashed, 24-hour password setup link by email.
- Buyers can request a replacement setup link from `member-login.html`; the
  response is neutral and requests are throttled for five minutes.
- Legacy activation codes and course bearer links remain valid for existing users.
- Production migration exercise completed on July 18, 2026: 8 gateway-verified
  test orders mapped to 4 test accounts. Anwar confirmed there have been no real
  buyers yet, so these records must not be reported as customer revenue.
- Nine older paid-marked orders lacked gateway evidence and were excluded for
  manual review. No order, sale, activation-code, or legacy course-token records
  were deleted.
- Current blocker: Premium login and course authorization work, but all five
  configured Bunny Stream embeds return Bunny's 404 player. Both local and
  production token keys fail, and no Bunny dashboard/API access is filed in the
  project credentials or access documentation.
- Buyer purchase emails now include Pierre's workshop welcome text and route
  new buyers through password setup or existing members through login.
- `pierre@pierreazar.com` was removed from code and runtime member/session/
  activation data in favor of `contact@pierreazar.com`. Contact's password was
  preserved. Three named test members were deactivated, not deleted.
- Member cleanup backup:
  `data/backups/member-cleanup-20260718T191435Z/`.
- Admin translation initialization no longer crashes when a page omits the
  optional translation bundle. The Members page explicitly loads i18n before the
  shared initializer; both initializer variants also guard missing bundles.
- Active membership is currently restricted to `contact@pierreazar.com` and
  `azarpierre1@gmail.com`. Four specified test accounts were deactivated; their
  sessions, unused setup links, and legacy course links were revoked.
- Deactivation backup:
  `data/backups/member-deactivation-20260718T200403Z/`.

---

## Admin Panel
Located at `/admin/`. Auth via `pa_admin` cookie (managed by `server.py`).  
Admin credentials are stored only in the gitignored `.credentials.md` and
`mail_config.py`.

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
| `member-set-password.html` | Secure paid-buyer password setup page |
| `member-activate.html` | Member activation flow |
| `member-upgrade.html` | Member upgrade to premium |
| `server.py` | Python HTTP server — handles auth, API, email, member CRUD |
| `migrate_paid_buyers.py` | Dry-run/apply migration for verified paid buyers |
| `test_premium_buyer_accounts.py` | Premium provisioning and token regression checks |
| `mail_config.py` | SMTP config (gitignored — credentials) |
| `mail_config.example.py` | Safe template for local SMTP/admin configuration |

---

## Session History

---

### Incident: July 18, 2026 — Gmail suppressed transactional emails

#### Problem
- Hostinger SMTP accepted buyer emails, but no Gmail recipient received them.
- Non-Gmail owner/developer notifications continued to arrive.

#### Method / Approach
- Traced a delivered message's full headers and public authoritative DNS.
- Confirmed MailChannels classified the message as `X-MC-Relay: Junk`.
- Found that SPF authorized only the VPS while the application sends through
  Hostinger, and Hostinger's `hostingermail-a` DKIM selector was absent.
- Backed up the authoritative zone, added Hostinger SPF and all three official
  DKIM CNAME records, incremented the serial, validated the zone, and reloaded it.

#### Results
- Authoritative DNS now publishes Hostinger SPF and DKIM.
- Zone backup: `/var/named/pierreazar.com.zone.bak-20260718T183533Z`.
- Incoming mail was also misrouted to the VPS (`MX 0 pierreazar.com`), which
  rejected external senders with 554. After confirming all active
  `@pierreazar.com` mailboxes are on Hostinger, MX was changed to
  `mx1.hostinger.com` priority 5 and `mx2.hostinger.com` priority 10.
- MX backup: `/var/named/pierreazar.com.zone.bak-mx-20260718T190622Z`.
- Recursive resolvers still showed cached old records immediately after the fix;
  delivery must be rechecked after DNS cache expiry.

#### Next Steps
- Do not issue more setup links until public resolvers return the new records.
- Send one Gmail delivery check after propagation and inspect its authentication
  results before declaring the incident closed.

---

### Session: July 18, 2026 — Premium Buyer Accounts

#### Problem
- Paid buyers depended on activation codes or personal course links and were not
  automatically represented as Premium Members.
- Buyers had no self-service recovery path when an activation email was missing.

#### Method / Approach
- Added idempotent paid-order provisioning, password-pending accounts, hashed
  one-time setup tokens, a password setup page, neutral resend support, and
  duplicate-notification guards.
- Added an evidence-gated historical migration that cross-checks paid orders
  against paid sales and requires gateway proof.
- Backed up production data before applying the migration.

#### Results
- Seven automated regression checks pass for new/existing buyers, duplicate
  completion, expired/used/replaced setup tokens, and legacy course links.
- Production moved from 5 to 9 members. All 5 original password hashes were
  unchanged; 4 migrated accounts are Premium and awaiting password setup.
- Migration backup:
  `data/backups/premium-migration-20260718T181152Z/`.
- Live setup/login pages and neutral API responses return successfully.

#### Next Steps
- Confirm the first real buyer completes the emailed setup link and opens
  `/course`; the raw setup token exists only in that buyer's email.
- Review the 9 excluded historical paid-marked orders before granting access.
- Local changes are not committed or pushed.

---

### Incident: July 18, 2026 — Public site connection refused

#### Problem
- `pierreazar.com` refused HTTP/HTTPS connections.

#### Method / Approach
- Verified DNS/VPS reachability, Apache status, listening ports, and the Python
  backend.
- Started Apache and enabled its automatic startup.

#### Results
- Root cause: Apache (`httpd`) was inactive and disabled; the Python backend on
  port 8080 remained healthy.
- Apache is active/enabled; homepage and course page return HTTP 200 over HTTPS.

#### Next Steps
- If Apache stops again without a reboot, inspect Webuzo/Apache error logs for
  the initiating stop or crash.

---

### Session: July 18, 2026 — Offer and syllabus labels

#### Problem
- Promotional label needed to read “Limited offer”.
- Course heading was misspelled “COURSE SYLLABOUS”.

#### Method / Approach
- Updated the offer label on the home and course pages.
- Corrected the syllabus heading in all matching pages.

#### Results
- Production now displays “Limited offer” and “COURSE SYLLABUS”.
- The supplied legal portfolio/affiliation disclaimer now appears below the
  course syllabus.
- Owner notifications go to `contact@pierreazar.com`, with developer test CC
  to `info@emoove.co` and backup owner CC to `azarpierre1@gmail.com`.
- Get in Touch clients receive a separate submission confirmation.
- Purchase clients receive their separate course-access email.
- All four email paths were SMTP-tested without charging a payment.
- The course promo banner now reads “Master the Art of Cinematic Lighting” and
  uses the enlarged desktop/mobile heading style.
- The custom Sound On and volume controls were removed from the course video on
  both the home and course pages.
- Video normalization now uses the modern iframe `allow` policy without
  redundant legacy fullscreen attributes.
- Payment configuration was not changed.

#### Next Steps
- None for this text-only update.

---

### Session: July 8, 2026 — Areeba false success + $0.20 receipt

#### Problem
- Areeba validation: site showed payment success while gateway reported not successful.
- Receipt showed **$0.20** (test amount left live by mistake).
- Client embarrassed; Areeba requesting meeting.

#### Method / Approach
1. Restored **course_price = 149** on VPS + course HTML display.
2. Hardened `/api/payment-complete`: mark paid **only** when Cybersource returns `AUTHORIZED` / `CAPTURED` (UC result JWT or `POST /pts/v2/payments`). Store `cybersource_id`.
3. Removed loose success paths (`PENDING`/`ACCEPTED`/token-id-as-success).

#### Results
- Live price **$149**; hardened verification deployed; server on 8080.
- Meeting reply draft ready for Anwar → Areeba.

#### Next Steps
1. Anwar confirms two meeting slots → send apology/availability email to Areeba.
2. Join call; walk transaction flow with Online Payment team.
3. After OK: switch to live credentials + `api.cybersource.com`.

---

### Session: July 22, 2026 — Portfolio dynamic grid alignment fix

#### Problem
- New videos added via admin appeared in a **vertical column on the right** instead of continuing the 3-column grid.
- Root cause: dynamic blocks were inserted after `layout-settings` but **before** the two closing `</div>` tags that complete each grid item — nesting them inside slot 8's wrapper.

#### Method
- Rewrote `repair_portfolio_dynamic_blocks()` to cut misaligned HTML after slot 8 and rebuild dynamic items as proper grid siblings.
- Fixed `_portfolio_item_append_point()` / `_insert_portfolio_block()` to append after the full item block.
- Deployed `content_manager.py` to VPS; ran repair on 3 live dynamic videos (indices 9–11).

#### Results
- Repair rebuilt 3 videos as grid siblings after slot 8.
- Verified 4th-video add/delete cycle works on VPS after repair.
- Synced repaired `portfolio.html` + `data/portfolio_dynamic.json` to local workspace.

#### Next Steps
1. Hard-refresh `pierreazar.com/portfolio.html` and confirm row 4+ layout.
2. Client QA: add video, change thumb, delete.

---

### Session: May 23, 2026 — Dynamic Portfolio Videos + Admin Fixes

#### Problem
- Client needed to add portfolio videos on demand (new videos at top-left of grid).
- New video thumbnails were linked (shared `img_028.jpg`) — changing one changed others.
- Delete video API failed with `name 'content_manager' is not defined`.

#### Method / Approach
- `content_manager.py`: dynamic items in `data/portfolio_dynamic.json`, insert at featured grid anchor, dedicated thumb paths per video (`portfolio-video-N.jpg`), server-side upload fork via `thumb_field`.
- `server.py`: `POST /api/portfolio/add-video`, `POST /api/portfolio/delete-video` (fixed `cm.` import).
- `admin/content-editor.html`: Add New Video, delete buttons, per-video Replace Thumb with safe upload path.

#### Results
- Add video works; grid layout fixed (side-by-side in featured grid).
- Thumbnail linking fixed — each video gets its own file; upload enforced server-side.
- Delete API fixed and verified on VPS (`200 OK`).
- Live dynamic portfolio list currently **empty** (test videos removed). Static slots 0–8 unchanged.

#### Next Steps (tomorrow)
1. **Clean admin dashboard** — UI polish, remove test clutter, verify all sections load cleanly.
2. **Finish project** — final QA on portfolio add/delete/thumb flow, client handoff checklist.
3. Optional: commit local changes (`content_manager.py`, `server.py`, `admin/content-editor.html`) when tests pass.
4. Do not push/deploy to production without explicit confirmation after tests.

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

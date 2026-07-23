# Backlog — Pierre Azar Web

## In Progress
_None currently active._

## Pending / Next Steps

### Done this session (UI)
- [x] Course/home price UI: strike $149 + show $99 offer (display only; backend charge unchanged)
- [x] Replaced “1-month offer” with “Limited offer” on home/course UI
- [x] Corrected “COURSE SYLLABOUS” to “COURSE SYLLABUS” site-wide
- [x] Deployed and verified the updated HTML pages
- [x] Added and deployed the legal portfolio disclaimer below the course syllabus
- [x] Added CC support to Get in Touch notifications
- [x] Sent Get in Touch and no-charge purchase-notification tests to info@emoove.co
- [x] Verified SMTP acceptance and success logs for both tests
- [x] Routed owner notifications to contact@pierreazar.com with info@emoove.co CC
- [x] Added a Get in Touch confirmation email to the submitting client
- [x] Verified client, owner, and developer routing for contact and purchase emails
- [x] Enlarged and deployed the “Upgrade your cinematography techniques” heading
- [x] Removed and deployed the course video sound/volume controls
- [x] Renamed and deployed the promo heading to “Master the Art of Cinematic Lighting”
- [x] Stopped local background processes tied to this project
- [x] Slightly enlarged and deployed the cinematic lighting heading
- [x] Removed redundant iframe fullscreen attributes and refreshed the script cache
- [x] Added and verified azarpierre1@gmail.com as backup CC for owner notifications

### Done this session (Premium Buyer Accounts)
- [x] Automatically upsert verified buyers as Premium Members
- [x] Preserve existing member passwords and create password-pending new accounts
- [x] Add hashed, single-use, 24-hour password setup links
- [x] Add neutral, throttled setup-link resend from member login
- [x] Keep legacy activation codes and course links operational
- [x] Add idempotent evidence-gated historical migration with backups
- [x] Exercise migration with 8 gateway-verified test orders across 4 test accounts
- [x] Confirm all 4 migration setup emails were accepted without reported failure
- [x] Verify original member password hashes and order/sale data were unchanged
- [x] Deploy backend/member pages and restart only the Python server
- [x] Add Pierre's workshop welcome copy and course action to both buyer email paths
- [x] Replace stale `pierre@pierreazar.com` support references with Contact
- [x] Deactivate `test@example.com`, `httpstest@example.com`, and `anwar@emoove.co`
- [x] Merge/remove the obsolete Pierre member while preserving Contact's password
  and migrating the active session/legacy activation record
- [x] Deactivate the four specified test accounts and revoke their sessions,
  password-setup links, and legacy course links
- [x] Confirm only `contact@pierreazar.com` and `azarpierre1@gmail.com` remain active

### Premium buyer follow-up
- [x] Bunny Stream course videos restored — library `711140`, 5 chapters, token auth live (Jul 23)
- [x] Bunny dashboard security configured (Anwar): embed token auth, allowed domains,
  block direct URL access
- [x] Public promo fixed — homepage/course show YouTube trailer only; paid chapters stay
  behind login + signed `/api/course-videos`
- [x] Paid buyers reactivate on new purchase (`active: true` even if old test account was disabled)
- [x] First end-to-end purchase test: pay → password setup → course access verified
- [ ] **Premium device/account limits** — enforce “stream on up to 2 devices” for Premium
  member sessions (legacy bearer tokens already use `COURSE_MAX_IPS = 2`; login-based
  course access is not limited yet)
- [ ] After Bunny trial, add billing + low-balance alerts/auto-recharge so library `711140`
  is not suspended
- [ ] Evaluate **Volume delivery tier** after real traffic; confirm MENA playback before
  making permanent
- [ ] Measure actual encoded traffic per full workshop view in Bunny analytics before
  recording any per-student or monthly cost
- [ ] Manually review 9 historical paid-marked orders excluded for missing gateway
  evidence; do not grant access without proof
- [x] Diagnose Gmail suppression from delivered MailChannels headers
- [x] Back up and repair authoritative Hostinger SPF/DKIM records
- [x] Replace obsolete VPS MX with Hostinger `mx1`/`mx2` after confirming all active
  Pierre Azar mailboxes are hosted there
- [ ] Send one Gmail setup-link delivery check and confirm SPF/DKIM on received headers

### Admin Panel
- [x] Fix `translations is not defined` in shared admin initialization and load
  the translation bundle before `deznav-init.js` on Members
- [x] Portfolio dynamic add: append new videos at bottom of grid (Option 2),
  orphan JSON cleanup, ghost index 9 removed on VPS, add/delete verified
- [x] Portfolio add-video: YouTube Shorts URL parsing + clearer admin error messages (Jul 22)
- [x] Portfolio add-video: fix Permission denied on 2nd add (root-owned thumb files from scp deploys)
- [ ] "Mark as read" action on contact form submissions (admin/index.html + admin/submissions.html)
- [ ] Disable / enable member toggle on admin/members.html
- [ ] Verify dashboard stats load correctly from live member data
- [ ] Verify contact form submissions display in dashboard
- [ ] Verify all pages show Members icon in sidebar

### Home / Course Page
- [ ] Confirm with Pierre: swap background videos 1–4 from Vimeo to YouTube embeds (`?autoplay=1&mute=1&loop=1`) for reliable silent autoplay
- [ ] Git push `index.html` and `cinematography-course.html` to `indigo-communication/pierreazar` (pending test confirmation)

### Website Edits (May 13, 2026)
- [ ] TBD — user has not yet specified the edits

## Done
- [x] Hero section: image+video layout, click-to-play fade (Apr 29)
- [x] Stats section: centered (Apr 29)
- [x] "About the Course" 2-column layout (Apr 29)
- [x] Admin panel: 13 pages updated, dashboard rebuilt with live data (Apr 30)
- [x] admin/change-password.html created + linked in all pages (Apr 30)
- [x] admin/members.html preloader fix (Apr 30)
- [x] Cursor CoC rules configured: global + project-level (May 13)

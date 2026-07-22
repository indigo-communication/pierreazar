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
- [ ] **BLOCKER:** Restore Bunny Stream course videos; all five configured
  library/video IDs currently return the Bunny 404 player
- [ ] Obtain verified Bunny dashboard/API access or corrected library/video IDs
  and token-auth key; none are filed in project access records
- [ ] After Bunny restores or recreates the video library, evaluate and configure
  the **Volume delivery tier** for cost-sensitive course streaming
- [ ] Confirm MENA playback performance on Volume before making it permanent;
  switch back to Standard if latency or buffering is unacceptable
- [ ] Measure actual encoded traffic per full workshop view in Bunny analytics
  before recording any per-student or monthly cost
- [ ] Configure low-balance alerts/auto-recharge so Stream is not suspended again
- [ ] Confirm the first real buyer completes password setup from the emailed link
  and opens the course
- [ ] Manually review 9 historical paid-marked orders excluded for missing
  gateway evidence; do not grant access without proof
- [x] Diagnose Gmail suppression from delivered MailChannels headers
- [x] Back up and repair authoritative Hostinger SPF/DKIM records
- [x] Replace obsolete VPS MX with Hostinger `mx1`/`mx2` after confirming all
  active Pierre Azar mailboxes are hosted there
- [ ] After DNS cache expiry, send one Gmail setup-link check and confirm
  SPF/DKIM authentication before resuming purchase-email tests

### Admin Panel
- [x] Fix `translations is not defined` in shared admin initialization and load
  the translation bundle before `deznav-init.js` on Members
- [x] Portfolio dynamic add: append new videos at bottom of grid (Option 2),
  orphan JSON cleanup, ghost index 9 removed on VPS, add/delete verified
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

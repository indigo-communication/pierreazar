# Decision Log — Pierre Azar Web

## 2026-07-18
- The `$149` list price remains struck through while the UI displays `$99`.
- The promotional label is “Limited offer”.
- This is a display-only change; payment configuration is unchanged.
- The supplied portfolio/affiliation disclaimer appears immediately below the
  course syllabus on the cinematography workshop page.
- Email roles: `contact@pierreazar.com` is the website owner and receives
  contact/purchase notifications as To; `info@emoove.co` is the developer test
  CC; `azarpierre1@gmail.com` is the owner backup CC; the web user receives a
  contact confirmation or course-access email.
- Verified future payments provision Premium membership automatically; new
  buyers set their password through a single-use 24-hour email link.
- Setup tokens are stored only as SHA-256 hashes. Raw tokens appear only in URL
  fragments so they are not sent to the server in page requests or referrers.
- Existing member password hashes must never be replaced during payment or
  migration.
- Legacy activation codes and course links remain operational during transition.
- Historical migration requires a paid order, a matching paid sale, and gateway
  evidence. Nine paid-marked records without gateway evidence were excluded
  rather than assumed valid.
- Production migration applied 8 gateway-verified test orders across 4 test
  accounts after backup. Anwar subsequently confirmed there have been no real
  buyers, so these transactions are not customer revenue.
- SMTP acceptance alone is not treated as recipient delivery. A delivered
  MailChannels header showed `X-MC-Relay: Junk`, missing Hostinger DKIM DNS, and
  SPF that did not authorize the Hostinger relay.
- Authoritative DNS now retains VPS authorization and also includes
  `_spf.mail.hostinger.com`; official `hostingermail-a/b/c` DKIM CNAME records
  were added. Gmail delivery will be rechecked only after DNS cache expiry.
- All active `@pierreazar.com` mailboxes were confirmed as Hostinger-hosted, so
  the obsolete local `MX 0 pierreazar.com` route was replaced by Hostinger
  `mx1`/`mx2` MX records. This prevents the VPS from rejecting inbound mail with
  554 while the actual mailbox remains active at Hostinger.
- Buyer purchase emails now use Pierre's supplied welcome/workshop copy. New
  buyers receive the password-setup action; existing members receive the direct
  member-login action. Owner/developer purchase notifications remain unchanged.
- `contact@pierreazar.com` is the sole Pierre member/support identity.
  `pierre@pierreazar.com` was merged into Contact without replacing Contact's
  password; its active session and legacy activation record were reassigned.
- The three named test members were deactivated rather than deleted so their
  audit history remains available.
- Shared admin initialization must treat translation assets as optional. Members
  now loads `i18n.js`/`translator.js` before `deznav-init.js`, while both standard
  and construction initializers safely skip translation when bundles are absent.
- Only `contact@pierreazar.com` and `azarpierre1@gmail.com` remain active members.
  Deactivating a member also requires session revocation, invalidation of unused
  setup links, locking legacy course tokens, and active-state enforcement on
  password setup, member identity, course pages, and video APIs.
- When Bunny Stream is restored, Volume is the preferred delivery-tier candidate
  for the workshop because Bunny positions it for large files/video at lower cost.
  It is not accepted blindly: MENA playback must be checked against Standard.
- GPT-provided bandwidth/cost estimates are not treated as measured project data.
  Actual encoded traffic and current official Bunny pricing must be captured
  before documenting per-view or monthly costs.

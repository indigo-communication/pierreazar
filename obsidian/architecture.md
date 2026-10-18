# Architecture — Pierre Azar Web

## Overview
Static HTML/CSS/JavaScript website served by Apache, with a Python `server.py`
application on port 8080 for payment, authentication, email, and admin APIs.

## Key paths
- Public pages: `index.html`, `cinematography-course.html`
- Payment UI: `payment-checkout.html`, `payment-checkout.js`
- Member UI: `member-login.html`, `member-set-password.html`
- Backend: `server.py`
- Runtime data: `data/`
- Production document root: `/home/aynbeirut/public_html/pierreazar.com/`

## Premium buyer flow
1. Cybersource confirms an authorized/captured payment.
2. `_finalize_paid_order` records the sale once and upserts the normalized buyer
   email in `data/members.json`.
3. Existing members keep their password and become Premium immediately. New
   buyers receive a Premium account with `password_pending: true`.
4. A random setup token is emailed in the URL fragment. Only its SHA-256 digest
   is stored in `data/password_setup_tokens.json`; it expires after 24 hours and
   is invalidated after use or replacement.
5. `/member/setup-password` sets the password, consumes the token, and creates a
   30-day `pa_member` session. Premium sessions can open `/course`.

## Compatibility and recovery
- `data/course_tokens.json` and `data/activation_codes.json` remain supported for
  pre-migration access.
- `/member/resend-setup` returns a neutral response and throttles eligible sends
  to one per five minutes.
- `migrate_paid_buyers.py` is dry-run by default. Apply mode backs up member,
  order, sale, and setup-token data before idempotent writes.

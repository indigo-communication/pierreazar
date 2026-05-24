# Product Description — Pierre Azar Web

## What is this?
Personal/professional website for **Pierre Azar** — filmmaker and cinematographer.

## Purpose
- Showcase Pierre's portfolio and cinematography work
- Sell/host a cinematography course (member-gated)
- Accept contact/inquiry submissions
- Manage members (free + premium tiers)

## Audience
- Aspiring filmmakers and cinematographers
- Industry professionals
- Potential clients

## Core Features
| Feature | Status |
|---------|--------|
| Portfolio/home page | Live |
| Cinematography course page | Live |
| Course player (member-only) | Live |
| Contact form | Live |
| Member login / activation | Live |
| Premium upgrade (payment) | Live |
| Admin panel (13 pages) | Live |

## Tech Stack
- **Frontend:** Static HTML, CSS, JS (Indigo website builder platform)
- **Backend:** Python (`server.py`) — custom HTTP server
- **Hosting:** VPS, AlmaLinux 9.7, Apache reverse proxy, port 8080
- **Email:** SMTP via `mail_config.py`
- **Payments:** Integrated (gateway configured in admin)
- **Auth:** Cookie-based (`pa_admin` for admin, session tokens for members)

## Design Language
- Dark, cinematic aesthetic
- Vimeo-hosted video content
- Platform (Indigo) manages most layout via VBID element system
- Custom overrides injected before `</head>` (CSS) and `</body>` (JS)

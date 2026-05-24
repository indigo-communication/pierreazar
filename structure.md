# Project Structure — Pierre Azar Web

## Root
```
/
├── index.html                  # Home page
├── cinematography-course.html  # Course sales page
├── course-player.html          # Course video player (members)
├── get-in-touch.html           # Contact page → POST /send-message
├── member-login.html           # Member login portal
├── member-activate.html        # Activation flow
├── member-upgrade.html         # Upgrade to premium
├── onset-experience.html       # Onset experience page
├── payment-success.html        # Post-payment success
├── payment-failed.html         # Post-payment failure
├── server.py                   # Python HTTP server (auth, API, email, member CRUD)
├── mail_config.py              # SMTP config (gitignored)
├── style.css                   # Global stylesheet
├── css/                        # Additional stylesheets
├── js/                         # JavaScript files
├── images/                     # Images
├── fonts/                      # Web fonts
├── data/                       # Data files (member DB, submissions, etc.)
└── admin/                      # Admin panel (Apache-accessible, cookie-auth)
    ├── index.html              # Dashboard — live stats + submissions
    ├── members.html            # Member list
    ├── submissions.html        # Contact form submissions
    ├── course-sales.html       # Orders
    ├── finance.html            # Finance overview
    ├── reports.html            # Reports
    ├── contacts.html           # Contacts
    ├── task.html               # Task management
    ├── content-editor.html     # Site content editor
    ├── payment-settings.html   # Payment gateway settings
    └── change-password.html    # Admin password change
```

## Server Endpoints (server.py)
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/send-message` | POST | Contact form → email |
| `/api/admin/members` | GET | Member list (auth required) |
| `/api/submissions` | GET | Contact form submissions |
| `/admin/change-password` | POST | Admin password change |
| `/member/login` | POST | Member authentication |
| `/member/activate` | POST | Account activation |

## Deploy
- **VPS:** `root@104.207.71.117`
- **Doc root:** `/home/aynbeirut/public_html/pierreazar.com/`
- **SCP single file:** `scp "FILE" root@104.207.71.117:/home/aynbeirut/public_html/pierreazar.com/`
- **GitHub:** `indigo-communication/pierreazar`, master branch

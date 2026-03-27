# ForgeForth Africa — cPanel Shared Hosting Deployment Guide

## What cPanel gives you (no extra installs needed)

| Resource | cPanel Provides | Notes |
|---|---|---|
| **MySQL / MariaDB** | Yes, natively | Create via cPanel → MySQL Databases |
| **Python** | Yes, via Setup Python App | Choose Python 3.9+ |
| **pip** | Yes, inside the virtual env | Used by start.py |
| **File system** | Yes | Upload code via File Manager or FTP |
| **Passenger / WSGI** | Yes | Serves the Django app via `passenger_wsgi.py` |
| **Redis** | Usually NO | Celery falls back to synchronous mode |
| **PostgreSQL** | Usually NO | Use MySQL instead |

---

## Step 1: Create the MySQL Database

1. Log in to cPanel
2. Go to **MySQL Databases**
3. Create a new database, e.g. `forgeforth`
   - Full name will be: `cpanelusername_forgeforth`
4. Create a database user, e.g. `ff_user`
   - Full name will be: `cpanelusername_ff_user`
5. Set a strong password (save it!)
6. Add the user to the database — grant **ALL PRIVILEGES**

---

## Step 2: Set Up Python App

1. Go to **Setup Python App** in cPanel
2. Click **Create Application**
3. Choose:
   - Python version: **3.9** or higher
   - Application root: `forgeforth` (this is where your code lives)
   - Application URL: your domain, e.g. `forgeforthafrica.com`
   - Application startup file: `passenger_wsgi.py`
4. Click **Create** — cPanel creates a virtual environment automatically

---

## Step 3: Upload Your Code

Upload the entire contents of `/forgeforth/forgeforth/` to the application root folder on the server (e.g. `/home/cpanelusername/forgeforth/`).

You can use:
- cPanel **File Manager** (zip and upload, then extract)
- **FTP** (FileZilla etc.)
- **Git** if cPanel Git Version Control is available

---

## Step 4: Configure .env on the Server

In the application root, edit `.env` and set:

```env
DJANGO_ENV=production
DEBUG=False
SECRET_KEY=generate-a-new-50-char-random-key-here

# MySQL database — use YOUR cpanel username and credentials
DATABASE_URL=mysql://cpanelusername_ff_user:yourpassword@localhost/cpanelusername_forgeforth

# Single database mode — all subsystems share one DB (correct for shared hosting)
USE_SINGLE_DATABASE=True

# Allowed hosts
ALLOWED_HOSTS=forgeforthafrica.com,www.forgeforthafrica.com

# Email (use SendGrid or your host's SMTP)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=your-sendgrid-key
DEFAULT_FROM_EMAIL=ForgeForth Africa <hello@forgeforthafrica.com>

# Cache — shared hosting usually has no Redis; use local memory
CACHE_URL=locmemcache://

# Celery — no Redis on shared hosting; tasks run synchronously
CELERY_BROKER_URL=memory://localhost/

# CSRF
CSRF_TRUSTED_ORIGINS=https://forgeforthafrica.com,https://www.forgeforthafrica.com

# Site
SITE_URL=https://forgeforthafrica.com
SITE_NAME=ForgeForth Africa
```

**Generate SECRET_KEY** (run this locally):
```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

---

## Step 5: Run the Startup Script

In the cPanel **Terminal** (or via SSH):

```bash
cd ~/forgeforth
python start.py
```

`start.py` will automatically:
1. Detect Python version
2. Install requirements (including `mysqlclient` and `PyMySQL`)
3. Validate `.env`
4. Run `manage.py migrate` — creates all tables in your MySQL database
5. Run `collectstatic`
6. Start Gunicorn

---

## Step 6: Configure passenger_wsgi.py

Make sure `passenger_wsgi.py` in your app root looks like this:

```python
import sys
import os

# Add the app directory to path
sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'forgeforth.settings')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

---

## Notes on Limitations of Shared cPanel

| Feature | Status | Workaround |
|---|---|---|
| Redis / Celery | Not available | Tasks run synchronously (still works) |
| Background workers | Not available | No periodic tasks — use cron jobs instead |
| WebSockets | Not available | Disabled until upgraded hosting |
| Multiple databases | Not needed | `USE_SINGLE_DATABASE=True` puts everything in one MySQL DB |
| PostgreSQL | Not available | MySQL works identically for all platform features |

---

## Upgrading Later

When you move to a VPS (recommended as you scale):

1. Set `USE_SINGLE_DATABASE=False` in `.env`
2. Add per-subsystem `DATABASE_URL` entries
3. Switch `DATABASE_URL` to PostgreSQL
4. Run `python start.py` — it migrates automatically

Everything else stays the same.


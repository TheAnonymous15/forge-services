"""
diagnose.py - Debug why passenger_wsgi.py fails on cPanel
==========================================================
Run this on the server:  python diagnose.py
It simulates what Passenger does and captures every error into diagnose.log
"""

import os
import sys
import traceback
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

LOG = os.path.join(HERE, "diagnose.log")

def w(msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = "[{}] {}".format(ts, msg)
    print(line)
    with open(LOG, "a") as f:
        f.write(line + "\n")

w("=" * 60)
w("  DIAGNOSE START")
w("=" * 60)

# 1. Python info
w("Python: {}.{}.{}".format(*sys.version_info[:3]))
w("sys.executable: {}".format(sys.executable))
w("cwd: {}".format(os.getcwd()))
w("__file__: {}".format(os.path.abspath(__file__)))

# 2. sys.path
w("")
w("--- sys.path ---")
for p in sys.path:
    w("  {}".format(p))

# 3. Check virtualenv site-packages
w("")
w("--- Virtualenv Detection ---")
home = os.path.expanduser("~")
found_venv = False
for pyver in ("3.12", "3.11", "3.10", "3.9"):
    venv_path = os.path.join(
        home, "virtualenv", "forgeforth", pyver,
        "lib", "python" + pyver, "site-packages",
    )
    exists = os.path.isdir(venv_path)
    in_path = venv_path in sys.path
    w("  Python {}: exists={}, in_sys.path={}  ({})".format(pyver, exists, in_path, venv_path))
    if exists and not in_path:
        sys.path.insert(0, venv_path)
        w("    -> ADDED to sys.path")
        found_venv = True
    elif exists and in_path:
        found_venv = True

if not found_venv:
    w("  WARNING: No virtualenv site-packages found!")

# 4. Check critical files exist
w("")
w("--- Critical Files ---")
for fname in ("manage.py", "passenger_wsgi.py", ".env", "config.json",
              "forgeforth/__init__.py", "forgeforth/settings.py", "forgeforth/wsgi.py",
              "website/__init__.py", "website/views.py", "website/middleware.py",
              "website/jinja2_env.py"):
    fpath = os.path.join(HERE, fname)
    w("  {} : {}".format(fname, "OK" if os.path.isfile(fpath) else "MISSING"))

# 5. Check .env loading
w("")
w("--- .env Check ---")
env_path = os.path.join(HERE, ".env")
if os.path.isfile(env_path):
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key = line.partition("=")[0].strip()
            # Don't log secret values
            if "KEY" in key.upper() or "SECRET" in key.upper() or "PASSWORD" in key.upper():
                w("  {} = ***REDACTED***".format(key))
            else:
                w("  {} = {}".format(key, line.partition("=")[2].strip()))
else:
    w("  .env NOT FOUND")

# 6. Try importing Django
w("")
w("--- Django Import Test ---")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "forgeforth.settings")
w("DJANGO_SETTINGS_MODULE = {}".format(os.environ.get("DJANGO_SETTINGS_MODULE")))

try:
    import django
    w("django version: {}".format(django.__version__))
    w("django location: {}".format(django.__file__))
except Exception:
    w("FAILED to import django:")
    w(traceback.format_exc())

# 7. Try django.setup()
w("")
w("--- Django Setup Test ---")
try:
    django.setup()
    w("django.setup() OK")
except Exception:
    w("FAILED django.setup():")
    w(traceback.format_exc())

# 8. Try importing settings
w("")
w("--- Settings Import Test ---")
try:
    from django.conf import settings
    w("DEBUG = {}".format(settings.DEBUG))
    w("ALLOWED_HOSTS = {}".format(settings.ALLOWED_HOSTS))
    w("INSTALLED_APPS count = {}".format(len(settings.INSTALLED_APPS)))
    w("TEMPLATES count = {}".format(len(settings.TEMPLATES)))
    w("ROOT_URLCONF = {}".format(settings.ROOT_URLCONF))
    w("STATIC_ROOT = {}".format(settings.STATIC_ROOT))
    w("STATIC_URL = {}".format(settings.STATIC_URL))
except Exception:
    w("FAILED settings import:")
    w(traceback.format_exc())

# 9. Try importing WSGI application
w("")
w("--- WSGI Application Test ---")
try:
    from django.core.wsgi import get_wsgi_application
    application = get_wsgi_application()
    w("WSGI application loaded: {}".format(type(application)))
    w("WSGI application OK")
except Exception:
    w("FAILED to load WSGI application:")
    w(traceback.format_exc())

# 10. Try importing URL conf
w("")
w("--- URL Conf Test ---")
try:
    from django.urls import reverse
    w("reverse('website:home') = {}".format(reverse("website:home")))
    w("URL conf OK")
except Exception:
    w("FAILED URL conf test:")
    w(traceback.format_exc())

# 11. Try importing each installed app
w("")
w("--- App Import Test ---")
try:
    for app_name in settings.INSTALLED_APPS:
        try:
            __import__(app_name)
            w("  {} : OK".format(app_name))
        except Exception as e:
            w("  {} : FAILED ({})".format(app_name, e))
except Exception:
    w("Could not iterate INSTALLED_APPS")

# 12. Try importing middleware
w("")
w("--- Middleware Import Test ---")
try:
    for mw in settings.MIDDLEWARE:
        module_path = mw.rsplit(".", 1)[0]
        try:
            __import__(module_path)
            w("  {} : OK".format(mw))
        except Exception as e:
            w("  {} : FAILED ({})".format(mw, e))
except Exception:
    w("Could not iterate MIDDLEWARE")

# 13. Try importing Jinja2 env
w("")
w("--- Jinja2 Environment Test ---")
try:
    from website.jinja2_env import environment
    env = environment(loader=None)
    w("Jinja2 environment OK: {}".format(type(env)))
except Exception:
    w("FAILED Jinja2 env:")
    w(traceback.format_exc())

# 14. Check template directories
w("")
w("--- Template Directories ---")
try:
    for tpl_conf in settings.TEMPLATES:
        backend = tpl_conf.get("BACKEND", "unknown")
        dirs = tpl_conf.get("DIRS", [])
        app_dirs = tpl_conf.get("APP_DIRS", False)
        w("  Backend: {}".format(backend))
        w("  DIRS: {}".format(dirs))
        w("  APP_DIRS: {}".format(app_dirs))
        if dirs:
            for d in dirs:
                w("    {} : {}".format(d, "EXISTS" if os.path.isdir(d) else "MISSING"))
except Exception:
    w("Could not check template dirs")

# 15. Simulate a request to /
w("")
w("--- Simulate GET / ---")
try:
    from django.test import RequestFactory
    from website.views import home
    factory = RequestFactory()
    request = factory.get("/")
    # Add session attribute (middleware would normally do this)
    from django.contrib.sessions.backends.db import SessionStore
    request.session = SessionStore()
    response = home(request)
    w("Response status: {}".format(response.status_code))
    w("Response content length: {}".format(len(response.content)))
    if response.status_code >= 400:
        w("Response body (first 500 chars):")
        w(response.content.decode("utf-8", errors="replace")[:500])
    else:
        w("Response OK (first 200 chars):")
        w(response.content.decode("utf-8", errors="replace")[:200])
except Exception:
    w("FAILED to simulate request:")
    w(traceback.format_exc())

w("")
w("=" * 60)
w("  DIAGNOSE COMPLETE")
w("  Full log at: {}".format(LOG))
w("=" * 60)


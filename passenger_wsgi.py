# passenger_wsgi.py
# =============================================================
# cPanel Phusion Passenger entry point for ForgeForth Africa
# =============================================================
# cPanel fields:
#   Application Root:         forgeforth
#   Application Startup File: passenger_wsgi.py
#   Application Entry Point:  application
# =============================================================

import os
import sys
import datetime
import traceback

# -- Debug log (written FIRST before anything else) ---------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
PASSENGER_LOG = os.path.join(HERE, "passenger_debug.log")

def _plog(msg):
    """Write to passenger_debug.log — survives even if Django fails to load."""
    try:
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(PASSENGER_LOG, "a") as f:
            f.write("[{}] {}\n".format(ts, msg))
    except Exception:
        pass

_plog("=" * 60)
_plog("passenger_wsgi.py loaded by Passenger")
_plog("Python: {}.{}.{}".format(*sys.version_info[:3]))
_plog("sys.executable: {}".format(sys.executable))
_plog("__file__: {}".format(os.path.abspath(__file__)))
_plog("cwd: {}".format(os.getcwd()))
_plog("HERE: {}".format(HERE))
_plog("uid: {} gid: {}".format(os.getuid(), os.getgid()))
_plog("sys.path: {}".format(sys.path))

# -- Paths --------------------------------------------------------------------
if HERE not in sys.path:
    sys.path.insert(0, HERE)
    _plog("Added HERE to sys.path")

# -- Virtualenv ---------------------------------------------------------------
HOME_DIR = os.path.expanduser("~")
_plog("HOME_DIR: {}".format(HOME_DIR))

venv_found = False
for pyver in ("3.12", "3.11", "3.10", "3.9"):
    # Check both lib and lib64 (some cPanel setups use lib64)
    for libdir in ("lib", "lib64"):
        venv_path = os.path.join(
            HOME_DIR, "virtualenv", "forgeforth", pyver,
            libdir, "python" + pyver, "site-packages",
        )
        if os.path.isdir(venv_path):
            if venv_path not in sys.path:
                sys.path.insert(0, venv_path)
                _plog("Added venv to sys.path: {}".format(venv_path))
            else:
                _plog("Venv already in sys.path: {}".format(venv_path))
            venv_found = True

if not venv_found:
    _plog("WARNING: No virtualenv site-packages found!")

_plog("Final sys.path: {}".format(sys.path))

# -- .env loading (before Django) ---------------------------------------------
env_file = os.path.join(HERE, ".env")
if os.path.isfile(env_file):
    try:
        with open(env_file, "r") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if key and key not in os.environ:
                    os.environ[key] = value
        _plog(".env loaded")
    except Exception as e:
        _plog(".env load ERROR: {}".format(e))
else:
    _plog(".env NOT FOUND at {}".format(env_file))

# -- Django settings ----------------------------------------------------------
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "forgeforth.settings")
_plog("DJANGO_SETTINGS_MODULE: {}".format(os.environ.get("DJANGO_SETTINGS_MODULE")))

# -- Logging ------------------------------------------------------------------
try:
    os.makedirs(os.path.join(HERE, "logs"), exist_ok=True)
except Exception:
    pass

# -- WSGI application --------------------------------------------------------
try:
    _plog("Importing Django...")
    import django
    _plog("Django {} from {}".format(django.__version__, django.__file__))

    _plog("Importing get_wsgi_application...")
    from django.core.wsgi import get_wsgi_application

    _plog("Calling get_wsgi_application()...")
    application = get_wsgi_application()

    _plog("WSGI application loaded OK: {}".format(type(application)))
except Exception as e:
    _plog("FATAL: Failed to load WSGI application")
    _plog(traceback.format_exc())
    # Re-raise so Passenger shows the error
    raise


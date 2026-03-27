"""
start.py - A-Z Production Deployment & Startup Script for ForgeForth Africa (Django)
=====================================================================================
Handles the ENTIRE deployment pipeline:
  1. Python version check
  2. Virtual-env detection / activation
  3. pip upgrade & requirements installation
  4. .env file validation
  5. config.json initialization
  6. Directory scaffolding (logs, staticfiles, mediafiles)
  7. Django system checks (--deploy in production)
  8. Database migrations
  9. Static file collection
 10. Superuser seeding (if none exists)
 11. Gunicorn startup

Usage:
  python start.py              # normal start
  python start.py --skip-pip   # skip pip install (faster restarts)
  python start.py --dev        # run Django dev server instead of gunicorn

All output is written to start.log in the same directory.
"""

import os
import sys
import json
import shutil
import subprocess
import multiprocessing
import argparse
import traceback
import datetime

# =========================================================================
# 0. CONSTANTS & LOGGING (before anything else)
# =========================================================================
HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

LOG_FILE = os.path.join(HERE, "start.log")

# Open the log file immediately — every single line gets written here
_log_fh = open(LOG_FILE, "a")


def _write_log(msg):
    """Write a timestamped line to start.log AND print to stdout."""
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = "[{}] {}".format(ts, msg)
    try:
        print(line)
        sys.stdout.flush()
    except Exception:
        pass
    try:
        _log_fh.write(line + "\n")
        _log_fh.flush()
    except Exception:
        pass


def log(msg, level="INFO"):
    tag = {"INFO": ">>", "OK": "OK", "WARN": "!!", "ERR": "XX", "STEP": "=>"}
    prefix = tag.get(level, ">>")
    _write_log("[start.py] {} {}".format(prefix, msg))


def heading(title):
    width = 60
    _write_log("")
    _write_log("=" * width)
    _write_log("  {}".format(title))
    _write_log("=" * width)


# =========================================================================
# LOG STARTUP IMMEDIATELY
# =========================================================================
_write_log("=" * 60)
_write_log("  start.py launched")
_write_log("  Python: {}.{}.{}".format(*sys.version_info[:3]))
_write_log("  sys.executable: {}".format(sys.executable))
_write_log("  __file__: {}".format(os.path.abspath(__file__)))
_write_log("  cwd: {}".format(os.getcwd()))
_write_log("=" * 60)

# =========================================================================
# FIND REAL PYTHON (cPanel fix)
# =========================================================================

def _find_real_python():
    """
    Find the real Python interpreter path.
    On cPanel sys.executable can point to a wrapper script — we need the real binary.
    """
    exe = sys.executable
    script_path = os.path.abspath(__file__)

    # If sys.executable resolves to THIS script or something ending in .py, find the real one
    if os.path.abspath(exe) == script_path or exe.endswith(".py"):
        _write_log("[python-detect] sys.executable ({}) points to a .py file, searching for real binary...".format(exe))
        search_dirs = [
            os.path.dirname(exe),
            os.path.join(os.path.dirname(exe), "..", "bin"),
        ]
        for d in search_dirs:
            for name in ("python3", "python", "python3.9", "python3.10", "python3.11", "python3.12"):
                candidate = os.path.abspath(os.path.join(d, name))
                if os.path.isfile(candidate) and not candidate.endswith(".py"):
                    _write_log("[python-detect] Found real python: {}".format(candidate))
                    return candidate
        _write_log("[python-detect] WARN: Could not find real python, falling back to 'python3'")
        return "python3"

    _write_log("[python-detect] Using sys.executable: {}".format(exe))
    return exe


PYTHON = _find_real_python()

# =========================================================================
# CONSTANTS (continued)
# =========================================================================
REQUIREMENTS_FILE = os.path.join(HERE, "requirements.txt")
REQUIREMENTS_PROD = os.path.join(HERE, "requirements.production.txt")
ENV_FILE = os.path.join(HERE, ".env")
ENV_PROD_TEMPLATE = os.path.join(HERE, ".env.production")
CONFIG_JSON = os.path.join(HERE, "config.json")

REQUIRED_DIRS = [
    os.path.join(HERE, "logs"),
    os.path.join(HERE, "staticfiles"),
    os.path.join(HERE, "mediafiles"),
]

MIN_PYTHON = (3, 9)

# =========================================================================
# LOAD .env EARLY
# =========================================================================

def _load_env_file():
    """
    Parse the .env file early so DJANGO_ENV, DEBUG, etc. are available
    to start.py BEFORE Django boots.
    """
    _write_log("[env] Looking for .env at {}".format(ENV_FILE))
    if not os.path.isfile(ENV_FILE):
        _write_log("[env] .env file not found — skipping")
        return
    try:
        with open(ENV_FILE, "r") as fh:
            count = 0
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if key and key not in os.environ:
                    os.environ[key] = value
                    count += 1
        _write_log("[env] Loaded {} vars from .env".format(count))
    except Exception as e:
        _write_log("[env] ERROR reading .env: {}".format(e))


_load_env_file()

IS_PRODUCTION = os.environ.get("DJANGO_ENV", "development").lower() == "production"
IS_DEBUG = os.environ.get("DEBUG", "True").lower() in ("true", "1", "yes")

_write_log("[env] DJANGO_ENV={}, IS_PRODUCTION={}, DEBUG={}".format(
    os.environ.get("DJANGO_ENV", "NOT SET"), IS_PRODUCTION, IS_DEBUG))

# =========================================================================
# HELPERS
# =========================================================================

def run(cmd, fail_msg=None, capture=True, env_override=None):
    """Run a subprocess command; return (stdout, stderr). Exit on failure."""
    log("Running: {}".format(" ".join(cmd)))
    merged_env = os.environ.copy()
    if env_override:
        merged_env.update(env_override)
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            env=merged_env,
        )
    except Exception as e:
        log("Exception running command: {}".format(e), "ERR")
        _write_log(traceback.format_exc())
        sys.exit(1)

    if result.returncode != 0:
        log(fail_msg or "Command failed (exit {}): {}".format(result.returncode, " ".join(cmd)), "ERR")
        if capture:
            if result.stdout:
                _write_log("[stdout] {}".format(result.stdout))
            if result.stderr:
                _write_log("[stderr] {}".format(result.stderr))
        sys.exit(1)
    return result.stdout or "", result.stderr or ""

# =========================================================================
# 1. PYTHON VERSION CHECK
# =========================================================================

def check_python():
    heading("1/10  Python Version Check")
    v = sys.version_info
    log("Python {}.{}.{} at {}".format(v.major, v.minor, v.micro, PYTHON))
    if (v.major, v.minor) < MIN_PYTHON:
        log("Python {}.{}+ is required. Current: {}.{}".format(
            MIN_PYTHON[0], MIN_PYTHON[1], v.major, v.minor), "ERR")
        sys.exit(1)
    log("Python version OK", "OK")

# =========================================================================
# 2. VIRTUALENV DETECTION
# =========================================================================

def detect_virtualenv():
    heading("2/10  Virtual Environment Detection")
    venv = os.environ.get("VIRTUAL_ENV", "")
    if venv:
        log("Active virtualenv: {}".format(venv), "OK")
        return

    home = os.path.expanduser("~")
    for pyver in ("3.12", "3.11", "3.10", "3.9"):
        venv_site = os.path.join(
            home, "virtualenv", "forgeforth", pyver,
            "lib", "python" + pyver, "site-packages",
        )
        if os.path.isdir(venv_site):
            if venv_site not in sys.path:
                sys.path.insert(0, venv_site)
            log("Detected cPanel virtualenv (Python {}): {}".format(pyver, venv_site), "OK")
            return

    log("No virtualenv detected - using system Python", "WARN")

# =========================================================================
# 3. PIP UPGRADE & REQUIREMENTS INSTALL
# =========================================================================

def install_requirements(skip_pip=False):
    heading("3/10  Pip & Requirements Installation")
    if skip_pip:
        log("--skip-pip flag set, skipping requirements install", "WARN")
        return

    req_file = REQUIREMENTS_PROD if (IS_PRODUCTION and os.path.isfile(REQUIREMENTS_PROD)) else REQUIREMENTS_FILE

    if not os.path.isfile(req_file):
        log("No requirements file found at {}".format(req_file), "ERR")
        sys.exit(1)

    log("Using requirements: {}".format(os.path.basename(req_file)))

    # Upgrade pip
    log("Upgrading pip...")
    result = subprocess.run(
        [PYTHON, "-m", "pip", "install", "--upgrade", "pip", "--quiet"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        log("pip upgrade failed (non-fatal): {}".format((result.stderr or "").strip()), "WARN")
    else:
        log("pip upgraded", "OK")

    # Install requirements
    log("Installing requirements...")
    result = subprocess.run(
        [PYTHON, "-m", "pip", "install", "-r", req_file, "--quiet"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr or ""
        if "Requires-Python" in stderr or "No matching distribution" in stderr:
            log("PYTHON VERSION MISMATCH DETECTED", "ERR")
        else:
            log("Failed to install requirements", "ERR")
        _write_log("[pip stderr] {}".format(stderr))
        sys.exit(1)
    log("All requirements installed", "OK")

# =========================================================================
# 4. .ENV FILE VALIDATION
# =========================================================================

def validate_env():
    heading("4/10  Environment File Validation")
    if os.path.isfile(ENV_FILE):
        log(".env file found", "OK")

        with open(ENV_FILE, "r") as f:
            content = f.read()
        if "SECRET_KEY=" not in content:
            log(".env is missing SECRET_KEY", "ERR")
            sys.exit(1)

        if IS_PRODUCTION and "change-this-in-production" in content:
            log("SECURITY: .env contains placeholder SECRET_KEY in production!", "ERR")
            sys.exit(1)

        log(".env validated", "OK")
    else:
        if os.path.isfile(ENV_PROD_TEMPLATE):
            log("No .env found. Copying from .env.production template...")
            shutil.copy2(ENV_PROD_TEMPLATE, ENV_FILE)
            log(".env created from template - REVIEW AND UPDATE SECRETS!", "WARN")
        else:
            log("No .env file found and no template available.", "ERR")
            sys.exit(1)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "forgeforth.settings")
    log("DJANGO_SETTINGS_MODULE = {}".format(os.environ.get("DJANGO_SETTINGS_MODULE")))

# =========================================================================
# 5. CONFIG.JSON INITIALIZATION
# =========================================================================

def init_config():
    heading("5/10  Config File Initialization")
    default_config = {
        "maintenance_mode": 0,
        "oncoming": 0,
    }

    if os.path.isfile(CONFIG_JSON):
        try:
            with open(CONFIG_JSON, "r") as f:
                existing = json.load(f)
            updated = False
            for key, val in default_config.items():
                if key not in existing:
                    existing[key] = val
                    updated = True
            if updated:
                with open(CONFIG_JSON, "w") as f:
                    json.dump(existing, f, indent=2)
                log("config.json updated with missing keys", "OK")
            else:
                log("config.json OK (maintenance_mode={}, oncoming={})".format(
                    existing.get("maintenance_mode", 0),
                    existing.get("oncoming", 0),
                ), "OK")
        except (json.JSONDecodeError, IOError) as e:
            log("config.json is corrupt ({}), resetting to defaults".format(e), "WARN")
            with open(CONFIG_JSON, "w") as f:
                json.dump(default_config, f, indent=2)
    else:
        with open(CONFIG_JSON, "w") as f:
            json.dump(default_config, f, indent=2)
        log("config.json created with defaults", "OK")

# =========================================================================
# 6. DIRECTORY SCAFFOLDING
# =========================================================================

def create_directories():
    heading("6/10  Directory Scaffolding")
    for d in REQUIRED_DIRS:
        os.makedirs(d, exist_ok=True)
    log("Directories verified: logs, staticfiles, mediafiles", "OK")

# =========================================================================
# 7. DJANGO SYSTEM CHECKS
# =========================================================================

def django_checks():
    heading("7/10  Django System Checks")
    cmd = [PYTHON, "manage.py", "check"]

    if IS_PRODUCTION:
        cmd.append("--deploy")
        log("Running with --deploy flag (production checks)")
    else:
        log("Running development checks")

    stdout, _ = run(cmd, fail_msg="Django system check FAILED")
    if stdout.strip():
        _write_log(stdout.strip())
    log("System checks passed", "OK")

# =========================================================================
# 8. DATABASE MIGRATIONS
# =========================================================================

def run_migrations():
    heading("8/10  Database Migrations")

    # Detect single vs multi database mode from .env
    use_single = os.environ.get("USE_SINGLE_DATABASE", "True").lower() in ("true", "1", "yes")
    db_url = os.environ.get("DATABASE_URL", "")

    if use_single:
        # ── Single-database mode (cPanel MySQL or SQLite dev) ──────────────
        # All subsystem aliases point to the same physical DB.
        # A single `manage.py migrate` (no --database flag) handles everything.
        log("Single-database mode detected ({})".format(
            "MySQL/cPanel" if "mysql" in db_url else
            "SQLite (dev)" if "sqlite" in db_url else "unknown"
        ))
        log("Checking for unmigrated changes ...")
        result = subprocess.run(
            [PYTHON, "manage.py", "migrate", "--noinput"],
            capture_output=True, text=True,
            env={**os.environ, "DJANGO_SETTINGS_MODULE": "forgeforth.settings"},
        )
        if result.returncode == 0:
            lines = [l for l in result.stdout.strip().split("\n") if l.strip()]
            for line in lines[-5:]:          # show last 5 lines
                log("  {}".format(line))
            log("Migrations applied", "OK")
        else:
            err = (result.stderr or result.stdout or "").strip()
            log("migrate FAILED:\n{}".format(err), "ERR")
            sys.exit(1)
    else:
        # ── Multi-database mode (separate DB per subsystem) ─────────────────
        ALL_DATABASES = [
            "default",
            "accounts_db",
            "profiles_db",
            "organizations_db",
            "applications_db",
            "media_db",
            "intelligence_db",
            "communications_db",
            "analytics_db",
            "administration_db",
            "security_db",
            "central_db",
        ]
        ok_count   = 0
        fail_count = 0
        for db_alias in ALL_DATABASES:
            log("Migrating: {} ...".format(db_alias))
            result = subprocess.run(
                [PYTHON, "manage.py", "migrate", "--database={}".format(db_alias), "--noinput"],
                capture_output=True, text=True,
                env={**os.environ, "DJANGO_SETTINGS_MODULE": "forgeforth.settings"},
            )
            if result.returncode == 0:
                lines = [l for l in result.stdout.strip().split("\n") if l.strip()]
                summary = lines[-1] if lines else "OK"
                log("  {} -> {}".format(db_alias, summary), "OK")
                ok_count += 1
            else:
                err = (result.stderr or result.stdout or "unknown error").strip().split("\n")[-1]
                log("  {} -> FAILED: {}".format(db_alias, err), "WARN")
                fail_count += 1

        if fail_count == 0:
            log("All {} databases migrated".format(ok_count), "OK")
        else:
            log("{} migrated, {} FAILED".format(ok_count, fail_count), "WARN")

# =========================================================================
# 9. STATIC FILES COLLECTION
# =========================================================================

def collect_static():
    heading("9/10  Static Files Collection")
    log("Collecting static files...")
    stdout, _ = run(
        [PYTHON, "manage.py", "collectstatic", "--noinput", "--clear"],
        fail_msg="collectstatic FAILED",
    )
    lines = [l for l in stdout.strip().split("\n") if l.strip()]
    if lines:
        log("  {}".format(lines[-1]))
    log("Static files collected", "OK")

# =========================================================================
# 10. SUPERUSER SEEDING
# =========================================================================

def seed_superuser():
    heading("10/10  Superuser Check")
    check_script = (
        "import django; django.setup(); "
        "from django.contrib.auth import get_user_model; "
        "User = get_user_model(); "
        "count = User.objects.filter(is_superuser=True).count(); "
        "print(count)"
    )
    result = subprocess.run(
        [PYTHON, "-c", check_script],
        capture_output=True, text=True,
        env={**os.environ, "DJANGO_SETTINGS_MODULE": "forgeforth.settings"},
    )
    if result.returncode == 0:
        count = result.stdout.strip()
        if count == "0":
            log("No superuser found - you can create one with:", "WARN")
            log("  python manage.py createsuperuser", "WARN")
        else:
            log("{} superuser(s) exist".format(count), "OK")
    else:
        log("Could not check superuser status (accounts app may not be migrated yet)", "WARN")
        _write_log("[superuser stderr] {}".format(result.stderr or ""))

# =========================================================================
# SERVER STARTUP
# =========================================================================

def start_dev_server(port):
    """Start Django development server."""
    heading("Starting Development Server")
    log("Running Django dev server on 0.0.0.0:{}".format(port))
    _log_fh.close()
    os.execv(PYTHON, [
        PYTHON, "manage.py", "runserver", "0.0.0.0:{}".format(port),
    ])


def start_gunicorn(port):
    """Start Gunicorn production server."""
    heading("Starting Gunicorn Production Server")

    cpu_count = multiprocessing.cpu_count()
    workers = min((2 * cpu_count) + 1, 4)
    timeout = 120
    log_level = "warning" if IS_PRODUCTION else "info"
    access_log = os.path.join(HERE, "logs", "access.log")
    error_log = os.path.join(HERE, "logs", "error.log")

    cmd = [
        PYTHON, "-m", "gunicorn",
        "forgeforth.wsgi:application",
        "--workers", str(workers),
        "--worker-class", "sync",
        "--bind", "0.0.0.0:{}".format(port),
        "--timeout", str(timeout),
        "--graceful-timeout", "30",
        "--keep-alive", "5",
        "--max-requests", "1000",
        "--max-requests-jitter", "50",
        "--log-level", log_level,
        "--access-logfile", access_log,
        "--error-logfile", error_log,
        "--capture-output",
        "--forwarded-allow-ips", "*",
        "--preload",
    ]

    log("Gunicorn on 0.0.0.0:{} with {} worker(s)".format(port, workers))
    log("Access log: {}".format(access_log))
    log("Error log:  {}".format(error_log))
    log("Command: {}".format(" ".join(cmd)))
    _log_fh.close()
    os.execv(PYTHON, cmd)

# =========================================================================
# MAIN
# =========================================================================

def main():
    parser = argparse.ArgumentParser(description="ForgeForth Africa - Deployment & Startup")
    parser.add_argument("--skip-pip", action="store_true", help="Skip pip install step")
    parser.add_argument("--dev", action="store_true", help="Run Django dev server instead of Gunicorn")
    parser.add_argument("--port", type=int, default=None, help="Port to bind to (default: 8000 or $PORT)")
    parser.add_argument("--skip-checks", action="store_true", help="Skip Django system checks")
    parser.add_argument("--skip-migrate", action="store_true", help="Skip database migrations")
    parser.add_argument("--skip-static", action="store_true", help="Skip collectstatic")
    parser.add_argument("--setup-only", action="store_true",
                        help="Run setup steps only (no server) — use on cPanel where Passenger serves the app")
    args = parser.parse_args()

    port = args.port or int(os.environ.get("PORT", "8000"))

    heading("ForgeForth Africa - Deployment Pipeline")
    log("Python: {}.{}.{}".format(*sys.version_info[:3]))
    log("Real Python binary: {}".format(PYTHON))
    log("DJANGO_ENV: {}".format("production" if IS_PRODUCTION else "development"))
    log("DEBUG: {}".format(IS_DEBUG))
    if args.setup_only:
        log("Mode: Setup only (Passenger will serve the app)")
    else:
        log("Server: {}".format("Django Dev" if args.dev else "Gunicorn"))
        log("Port: {}".format(port))

    # Pipeline
    check_python()
    detect_virtualenv()
    install_requirements(skip_pip=args.skip_pip)
    validate_env()
    init_config()
    create_directories()

    if not args.skip_checks:
        django_checks()
    else:
        log("Skipping Django system checks (--skip-checks)", "WARN")

    if not args.skip_migrate:
        run_migrations()
    else:
        log("Skipping migrations (--skip-migrate)", "WARN")

    if not args.skip_static:
        collect_static()
    else:
        log("Skipping collectstatic (--skip-static)", "WARN")

    seed_superuser()

    # On cPanel, Passenger serves the app — we just do setup
    if args.setup_only:
        log("")
        log("=" * 50)
        log("  SETUP COMPLETE")
        log("  Passenger will serve the app via passenger_wsgi.py")
        log("  Restart the app in cPanel if needed:")
        log("    touch tmp/restart.txt")
        log("=" * 50)
        _log_fh.close()
        sys.exit(0)

    # Start server (only for VPS/Docker, not cPanel)
    if args.dev:
        start_dev_server(port)
    else:
        start_gunicorn(port)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        _write_log("[start.py] Exiting.")
        _log_fh.close()
        raise
    except Exception:
        _write_log("[start.py] FATAL UNHANDLED EXCEPTION:")
        _write_log(traceback.format_exc())
        _log_fh.close()
        sys.exit(1)


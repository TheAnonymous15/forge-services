"""
pip.py - Install production requirements for ForgeForth Africa
===============================================================
Standalone installer that works on cPanel / shared hosting (Python 3.9+).
Installs packages one-by-one so a single failure does not block the rest.

Uses pip's internal API directly to avoid sys.executable conflicts on cPanel
where the Python binary name can cause recursion back into this script.

Usage:
    python pip.py                # install all production requirements
    python pip.py --check        # show what is installed vs missing
    python pip.py --upgrade      # upgrade pip first, then install
"""

import subprocess
import sys
import os
import importlib

HERE = os.path.dirname(os.path.abspath(__file__))
REQ_FILE = os.path.join(HERE, "requirements.production.txt")


def _find_real_python():
    """
    Find the real Python interpreter path, avoiding this script.
    On cPanel, sys.executable can point to a wrapper that causes recursion.
    """
    exe = sys.executable
    # If sys.executable ends with pip.py or points to this script, find the real one
    if exe.endswith("pip.py") or os.path.basename(exe) == "pip.py":
        # Try common locations
        for candidate in [
            os.path.join(os.path.dirname(exe), "python3"),
            os.path.join(os.path.dirname(exe), "python"),
            os.path.join(os.path.dirname(exe), "python3.9"),
            os.path.join(os.path.dirname(exe), "python3.9_bin"),
            # cPanel virtualenv pattern
            os.path.join(os.path.dirname(exe), "..", "bin", "python3"),
            os.path.join(os.path.dirname(exe), "..", "bin", "python"),
        ]:
            candidate = os.path.abspath(candidate)
            if os.path.isfile(candidate) and candidate != os.path.abspath(__file__):
                return candidate
        # Last resort: use the path from the shebang or just "python3"
        return "python3"
    return exe


PYTHON = _find_real_python()


def parse_requirements(path):
    """Parse a requirements file into a list of package specs (skips comments/blanks)."""
    packages = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            packages.append(line)
    return packages


def pip_run(args):
    """
    Run a pip command using the real Python interpreter.
    Returns (returncode, stdout, stderr).
    """
    cmd = [PYTHON, "-m", "pip"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout or "", result.stderr or ""


def pip_install(package, quiet=True):
    """Install a single package. Returns (success: bool, output: str)."""
    args = ["install", package]
    if quiet:
        args.append("--quiet")
    code, stdout, stderr = pip_run(args)
    return code == 0, (stdout + stderr).strip()


def pip_check_installed(package):
    """Check if a package spec is already satisfied."""
    name = package.split("=")[0].split(">")[0].split("<")[0].strip()
    code, _, _ = pip_run(["show", name])
    return code == 0


def upgrade_pip():
    """Upgrade pip itself."""
    print("[pip.py] Upgrading pip...")
    args = ["install", "--upgrade", "pip", "--quiet"]
    code, stdout, stderr = pip_run(args)
    if code == 0:
        print("[pip.py] OK pip upgraded")
    else:
        print("[pip.py] !! pip upgrade failed: {}".format((stdout + stderr).strip()))
    return code == 0


def install_all(req_file, do_upgrade=False):
    """Install all packages from requirements file, one by one."""
    if not os.path.isfile(req_file):
        print("[pip.py] XX File not found: {}".format(req_file))
        sys.exit(1)

    packages = parse_requirements(req_file)
    if not packages:
        print("[pip.py] XX No packages found in {}".format(os.path.basename(req_file)))
        sys.exit(1)

    print("[pip.py] Python: {}.{}.{} ({})".format(
        sys.version_info.major, sys.version_info.minor, sys.version_info.micro,
        PYTHON,
    ))
    print("[pip.py] Requirements: {}".format(os.path.basename(req_file)))
    print("[pip.py] Packages to install: {}".format(len(packages)))
    print("")

    if do_upgrade:
        upgrade_pip()
        print("")

    installed = 0
    failed = 0
    skipped = 0
    failures = []

    for i, pkg in enumerate(packages, 1):
        label = "[{}/{}]".format(i, len(packages))

        # Check if already installed
        if pip_check_installed(pkg):
            print("  {} SKIP  {}  (already installed)".format(label, pkg))
            skipped += 1
            continue

        # Install
        print("  {} INSTALL  {} ...".format(label, pkg), end="", flush=True)
        ok, out = pip_install(pkg, quiet=True)
        if ok:
            print("  OK")
            installed += 1
        else:
            print("  FAILED")
            failed += 1
            failures.append((pkg, out))

    # Summary
    print("")
    print("=" * 50)
    print("  DONE")
    print("  Installed: {}".format(installed))
    print("  Skipped:   {} (already present)".format(skipped))
    print("  Failed:    {}".format(failed))
    print("=" * 50)

    if failures:
        print("")
        print("Failed packages:")
        for pkg, out in failures:
            print("  - {}".format(pkg))
            # Show last 3 lines of error
            lines = [l for l in out.split("\n") if l.strip()]
            for line in lines[-3:]:
                print("      {}".format(line))
        print("")
        sys.exit(1)


def check_all(req_file):
    """Show status of each package (installed / missing)."""
    packages = parse_requirements(req_file)
    print("[pip.py] Checking {} packages...\n".format(len(packages)))

    missing = []
    for pkg in packages:
        if pip_check_installed(pkg):
            print("  OK     {}".format(pkg))
        else:
            print("  MISS   {}".format(pkg))
            missing.append(pkg)

    print("")
    if missing:
        print("{} package(s) missing:".format(len(missing)))
        for pkg in missing:
            print("  - {}".format(pkg))
    else:
        print("All packages installed.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ForgeForth Africa - pip installer")
    parser.add_argument("--check", action="store_true", help="Check installed vs missing")
    parser.add_argument("--upgrade", action="store_true", help="Upgrade pip before installing")
    parser.add_argument("--file", default=REQ_FILE, help="Requirements file path")
    args = parser.parse_args()

    if args.check:
        check_all(args.file)
    else:
        install_all(args.file, do_upgrade=args.upgrade)


#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Services Manager
====================================
Start, stop, and manage all microservices.

Usage:
    python services.py start all          # Start all services
    python services.py start auth         # Start auth service only
    python services.py start talent       # Start talent portal only
    python services.py stop all           # Stop all services
    python services.py status             # Show status of all services
    python services.py ports              # Show port assignments
"""
import os
import sys
import subprocess
import signal
import time
import argparse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Service definitions
SERVICES = {
    'website': {
        'name': 'Main Website',
        'port': 9880,
        'start_cmd': ['python', 'manage.py', 'runserver', '0.0.0.0:9880'],
        'check_file': 'manage.py'
    },
    'admin': {
        'name': 'Admin Portal',
        'port': 9001,
        'start_cmd': ['python', '-c', 'print("Admin portal not yet implemented")'],
        'check_file': None
    },
    'auth': {
        'name': 'Auth Service',
        'port': 9002,
        'start_cmd': ['python', 'start_auth.py', '--no-ssl'],  # Use --no-ssl for dev
        'check_file': 'start_auth.py'
    },
    'talent': {
        'name': 'Talent Portal',
        'port': 9003,
        'start_cmd': ['python', 'start_talent.py'],
        'check_file': 'start_talent.py'
    },
    'org': {
        'name': 'Org/Employer Portal',
        'port': 9004,
        'start_cmd': ['python', '-c', 'print("Org portal not yet implemented")'],
        'check_file': None
    }
}

# PID storage
PID_DIR = BASE_DIR / 'pids'


def ensure_pid_dir():
    """Ensure PID directory exists."""
    PID_DIR.mkdir(exist_ok=True)


def get_pid_file(service: str) -> Path:
    """Get PID file path for a service."""
    return PID_DIR / f'{service}.pid'


def is_running(service: str) -> bool:
    """Check if a service is running."""
    pid_file = get_pid_file(service)
    if pid_file.exists():
        pid = int(pid_file.read_text().strip())
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            # Process not running, clean up PID file
            pid_file.unlink()
    return False


def start_service(service: str) -> bool:
    """Start a service."""
    if service not in SERVICES:
        print(f"[ERROR] Unknown service: {service}")
        return False

    config = SERVICES[service]

    if is_running(service):
        print(f"[--] {config['name']} already running on port {config['port']}")
        return True

    if config['check_file'] and not (BASE_DIR / config['check_file']).exists():
        print(f"[ERROR] {config['name']} startup file not found")
        return False

    print(f"[>>] Starting {config['name']} on port {config['port']}...")

    try:
        # Start the process
        log_file = BASE_DIR / 'logs' / f'{service}.log'
        log_file.parent.mkdir(exist_ok=True)

        with open(log_file, 'a') as log:
            process = subprocess.Popen(
                config['start_cmd'],
                cwd=str(BASE_DIR),
                stdout=log,
                stderr=log,
                start_new_session=True
            )

        # Save PID
        ensure_pid_dir()
        get_pid_file(service).write_text(str(process.pid))

        # Wait a moment and check if it started
        time.sleep(2)
        if is_running(service):
            print(f"[OK] {config['name']} started (PID: {process.pid})")
            return True
        else:
            print(f"[ERROR] {config['name']} failed to start - check logs/{service}.log")
            return False

    except Exception as e:
        print(f"[ERROR] Failed to start {config['name']}: {e}")
        return False


def stop_service(service: str) -> bool:
    """Stop a service."""
    if service not in SERVICES:
        print(f"[ERROR] Unknown service: {service}")
        return False

    config = SERVICES[service]

    if not is_running(service):
        print(f"[--] {config['name']} not running")
        return True

    pid_file = get_pid_file(service)
    pid = int(pid_file.read_text().strip())

    print(f"[>>] Stopping {config['name']} (PID: {pid})...")

    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
        time.sleep(2)

        # Force kill if still running
        try:
            os.kill(pid, 0)
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except OSError:
            pass

        pid_file.unlink(missing_ok=True)
        print(f"[OK] {config['name']} stopped")
        return True

    except Exception as e:
        print(f"[ERROR] Failed to stop {config['name']}: {e}")
        return False


def show_status():
    """Show status of all services."""
    print()
    print("=" * 60)
    print("  ForgeForth Africa - Service Status")
    print("=" * 60)
    print()
    print(f"{'Service':<20} {'Port':<8} {'Status':<12} {'PID':<10}")
    print("-" * 60)

    for service, config in SERVICES.items():
        if is_running(service):
            pid = get_pid_file(service).read_text().strip()
            status = "\033[92mRUNNING\033[0m"
        else:
            pid = "-"
            status = "\033[91mSTOPPED\033[0m"

        print(f"{config['name']:<20} {config['port']:<8} {status:<20} {pid:<10}")

    print()


def show_ports():
    """Show port assignments."""
    print()
    print("=" * 60)
    print("  ForgeForth Africa - Port Assignments")
    print("=" * 60)
    print()
    print(f"{'Service':<25} {'Port':<8} {'URL'}")
    print("-" * 60)

    for service, config in SERVICES.items():
        url = f"http://localhost:{config['port']}"
        print(f"{config['name']:<25} {config['port']:<8} {url}")

    print()
    print("Note: In production, use reverse proxy (nginx) to route traffic")
    print()


def main():
    parser = argparse.ArgumentParser(description='ForgeForth Africa Services Manager')
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Start command
    start_parser = subparsers.add_parser('start', help='Start services')
    start_parser.add_argument('service', choices=['all', 'website', 'admin', 'auth', 'talent', 'org'],
                             help='Service to start')

    # Stop command
    stop_parser = subparsers.add_parser('stop', help='Stop services')
    stop_parser.add_argument('service', choices=['all', 'website', 'admin', 'auth', 'talent', 'org'],
                            help='Service to stop')

    # Status command
    subparsers.add_parser('status', help='Show service status')

    # Ports command
    subparsers.add_parser('ports', help='Show port assignments')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == 'start':
        if args.service == 'all':
            for service in SERVICES:
                start_service(service)
        else:
            start_service(args.service)

    elif args.command == 'stop':
        if args.service == 'all':
            for service in SERVICES:
                stop_service(service)
        else:
            stop_service(args.service)

    elif args.command == 'status':
        show_status()

    elif args.command == 'ports':
        show_ports()


if __name__ == '__main__':
    main()


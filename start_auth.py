#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Auth Service Startup Script
================================================
Start the central authentication service on port 9002.

Usage:
    python start_auth.py [--no-ssl] [--debug]
"""
import os
import sys
import argparse

# Ensure we're in the right directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)


def main():
    parser = argparse.ArgumentParser(description='Start ForgeForth Auth Service')
    parser.add_argument('--no-ssl', action='store_true', help='Disable SSL (development only)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()

    # Load environment
    from dotenv import load_dotenv
    load_dotenv()

    # Override settings from args
    if args.no_ssl:
        os.environ['AUTH_SSL_ENABLED'] = 'False'
    if args.debug:
        os.environ['DEBUG'] = 'True'

    print()
    print("=" * 60)
    print("  ForgeForth Africa - Auth Service")
    print("=" * 60)

    # Check dependencies
    required_packages = ['fastapi', 'uvicorn', 'bcrypt', 'sqlalchemy', 'httpx', 'websockets']
    missing = []

    for pkg in required_packages:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"\n[ERROR] Missing required packages: {', '.join(missing)}")
        print("\nInstall with:")
        print("  pip install fastapi uvicorn bcrypt sqlalchemy[asyncio] aiosqlite httpx websockets python-dotenv")
        sys.exit(1)

    print("[OK] All dependencies installed")

    # Create required directories
    os.makedirs(os.path.join(BASE_DIR, 'logs'), exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, 'certs'), exist_ok=True)

    # Import and run the app
    from auth_service.app import main as run_app
    run_app()


if __name__ == "__main__":
    main()


#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Talent Portal Startup Script
================================================
Start the Talent Portal microservice on port 9003.

Usage:
    python start_talent.py
"""
import os
import sys

# Ensure we're in the right directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)


def main():
    print("=" * 60)
    print("  ForgeForth Africa - Talent Portal")
    print("=" * 60)

    # Load environment
    from dotenv import load_dotenv
    load_dotenv()

    port = int(os.getenv('TALENT_PORTAL_PORT', 9003))
    host = os.getenv('TALENT_PORTAL_HOST', '0.0.0.0')
    debug = os.getenv('DEBUG', 'False').lower() == 'true'

    print(f"  Host: {host}")
    print(f"  Port: {port}")
    print(f"  Debug: {debug}")
    print(f"  Auth Service: {os.getenv('AUTH_SERVICE_URL', 'http://localhost:9002')}")
    print(f"  API Service: {os.getenv('API_SERVICE_URL', 'http://localhost:8000')}")
    print("=" * 60)
    print()

    # Check dependencies
    try:
        import fastapi
        import uvicorn
        import httpx
        import jinja2
        print("[OK] All dependencies installed")
    except ImportError as e:
        print(f"[ERROR] Missing dependency: {e}")
        print("\nInstall with: pip install fastapi uvicorn httpx jinja2 python-multipart itsdangerous python-dotenv")
        sys.exit(1)

    # Create logs directory
    log_dir = os.path.join(BASE_DIR, 'logs')
    os.makedirs(log_dir, exist_ok=True)

    # Start server
    print()
    print(f"[>>] Starting Talent Portal on http://{host}:{port}")
    print(f"[>>] Login: http://{host}:{port}/auth/login")
    print(f"[>>] Register: http://{host}:{port}/auth/register")
    print()

    import uvicorn
    uvicorn.run(
        "talent_portal.app:app",
        host=host,
        port=port,
        reload=debug,
        log_level="debug" if debug else "info"
    )


if __name__ == "__main__":
    main()


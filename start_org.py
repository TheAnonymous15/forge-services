#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Organization Portal Startup Script
=====================================================
Start the Organization Portal microservice on port 9004.

Usage:
    python start_org.py
"""
import os
import sys

# Ensure we're in the right directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)


def main():
    print("=" * 60)
    print("  ForgeForth Africa - Organization Portal")
    print("=" * 60)

    # Load environment
    from dotenv import load_dotenv
    load_dotenv()

    port = int(os.getenv('ORG_PORTAL_PORT', 9004))
    host = os.getenv('ORG_PORTAL_HOST', '0.0.0.0')
    debug = os.getenv('DEBUG', 'False').lower() == 'true'

    print(f"  Host: {host}")
    print(f"  Port: {port}")
    print(f"  Debug: {debug}")
    print(f"  Auth Service: {os.getenv('AUTH_SERVICE_URL', 'http://localhost:9002')}")
    print(f"  API Service: {os.getenv('API_SERVICE_URL', 'http://localhost:9880')}")
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

    # Start server
    print(f"\n[INFO] Starting Organization Portal on http://{host}:{port}")
    print("[INFO] Press CTRL+C to stop\n")

    import uvicorn
    uvicorn.run(
        "org_portal.main:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info" if debug else "warning"
    )


if __name__ == "__main__":
    main()


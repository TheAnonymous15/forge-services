# -*- coding: utf-8 -*-
"""
Maintenance Mode Middleware for ForgeForth Africa.

Reads config.json with caching (max once per second) to avoid
file I/O on every request.
"""

import json
import os
import time
import logging

from django.http import HttpResponse

logger = logging.getLogger("forgeforth")

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(_BASE_DIR, "config.json")
MAINTENANCE_TEMPLATE = os.path.join(
    _BASE_DIR, "website", "templates", "website", "maintenance.html",
)
COMING_SOON_TEMPLATE = os.path.join(
    _BASE_DIR, "website", "templates", "website", "coming_soon.html",
)

# Paths that should remain accessible even during maintenance / oncoming
ALLOWED_PATHS = (
    "/health",
    "/admin",
    "/static",
    "/media",
)

# Cache for config to avoid reading file on every request
_config_cache = {"data": {}, "time": 0}
_CACHE_TTL = 1.0  # seconds


def _read_config() -> dict:
    """Read config.json with caching (max once per second)."""
    now = time.time()
    if now - _config_cache["time"] < _CACHE_TTL:
        return _config_cache["data"]

    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r") as fh:
                _config_cache["data"] = json.load(fh)
                _config_cache["time"] = now
    except Exception as exc:
        logger.warning("Could not read config.json: %s", exc)
    return _config_cache["data"]


def _is_maintenance_on() -> bool:
    return int(_read_config().get("maintenance_mode", 0)) == 1


def _is_oncoming_on() -> bool:
    return int(_read_config().get("oncoming", 0)) == 1


def _serve_static_page(template_path: str, fallback_title: str, status: int = 503) -> HttpResponse:
    """Return a standalone HTML page from a template file."""
    try:
        with open(template_path, "r") as fh:
            html = fh.read()
    except FileNotFoundError:
        html = (
            "<html><body style='display:flex;align-items:center;"
            "justify-content:center;height:100vh;font-family:sans-serif;'>"
            f"<h1>{fallback_title}</h1></body></html>"
        )
    return HttpResponse(
        html,
        status=status,
        content_type="text/html",
        headers={
            "Retry-After": "1800",
            "Cache-Control": "no-cache, no-store, must-revalidate",
        },
    )


class MaintenanceModeMiddleware:
    """
    Django middleware that intercepts every request and returns:
    - 503 Coming Soon page when config.json has "oncoming": 1
    - 503 Maintenance page when config.json has "maintenance_mode": 1
    Oncoming mode takes priority over maintenance mode.
    Changes to config.json take effect immediately — no restart required.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # Always let allowed paths through
        is_allowed = any(path.startswith(p) for p in ALLOWED_PATHS)

        if not is_allowed:
            # Oncoming mode takes priority
            if _is_oncoming_on():
                return _serve_static_page(COMING_SOON_TEMPLATE, "Coming Soon")

            if _is_maintenance_on():
                return _serve_static_page(MAINTENANCE_TEMPLATE, "Under Maintenance")

        return self.get_response(request)


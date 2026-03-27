# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Organization Portal
=======================================
FastAPI application for organizations and employers.
"""
import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Form, UploadFile, File, Query, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
import httpx

# Configuration
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# Environment
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://localhost:9002")
API_BASE_URL = os.getenv("API_SERVICE_URL", "http://localhost:9880/api/v1")
SECRET_KEY = os.getenv("ORG_PORTAL_SECRET", "org-portal-secret-change-in-production")
MAIN_SITE_URL = os.getenv("SITE_URL", "http://localhost:9880")

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("org_portal")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Organization Portal starting...")
    yield
    logger.info("Organization Portal shutting down...")


# Create FastAPI app
app = FastAPI(
    title="ForgeForth Africa - Organization Portal",
    description="Portal for organizations to manage opportunities and review candidates",
    version="1.0.0",
    lifespan=lifespan
)

# Middleware
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# Static files
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# =============================================================================
# HELPERS
# =============================================================================

def get_session_user(request: Request) -> Optional[Dict]:
    """Get user from session."""
    return request.session.get("user")


def get_access_token(request: Request) -> Optional[str]:
    """Get access token from session."""
    return request.session.get("access_token")


def template_context(request: Request, **kwargs) -> Dict[str, Any]:
    """Build template context."""
    user = get_session_user(request)
    return {
        "request": request,
        "user": user,
        "site_name": "ForgeForth Africa",
        "main_site_url": MAIN_SITE_URL,
        **kwargs
    }


def login_required(func):
    """Decorator to require login."""
    from functools import wraps
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        user = get_session_user(request)
        if not user:
            return RedirectResponse(url="/auth/login", status_code=302)
        request.state.user = user
        return await func(request, *args, **kwargs)
    return wrapper


class APIClient:
    """Client for API requests."""

    def __init__(self):
        self.base_url = API_BASE_URL
        self.timeout = 30.0

    async def _request(self, method: str, endpoint: str, token: str = None,
                       data: Dict = None, params: Dict = None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.request(
                    method=method,
                    url=f"{self.base_url}{endpoint}",
                    headers=headers,
                    json=data,
                    params=params
                )
                return response.json(), response.status_code
            except Exception as e:
                logger.error(f"API error: {e}")
                return {"error": str(e)}, 500

    async def get_organization(self, token: str):
        result, _ = await self._request("GET", "/organizations/me", token)
        return result

    async def get_opportunities(self, token: str, page: int = 1):
        result, _ = await self._request("GET", "/organizations/opportunities", token, params={"page": page})
        return result

    async def get_opportunity(self, token: str, opp_id: str):
        result, _ = await self._request("GET", f"/organizations/opportunities/{opp_id}", token)
        return result

    async def create_opportunity(self, token: str, data: Dict):
        return await self._request("POST", "/organizations/opportunities", token, data)

    async def update_opportunity(self, token: str, opp_id: str, data: Dict):
        return await self._request("PUT", f"/organizations/opportunities/{opp_id}", token, data)

    async def get_applications(self, token: str, opportunity_id: str = None, page: int = 1):
        params = {"page": page}
        if opportunity_id:
            params["opportunity"] = opportunity_id
        result, _ = await self._request("GET", "/applications/received", token, params=params)
        return result

    async def get_application(self, token: str, app_id: str):
        result, _ = await self._request("GET", f"/applications/{app_id}", token)
        return result

    async def update_application_status(self, token: str, app_id: str, status: str, notes: str = ""):
        return await self._request("POST", f"/applications/{app_id}/status", token,
                                   {"status": status, "notes": notes})

    async def get_team(self, token: str):
        result, _ = await self._request("GET", "/organizations/team", token)
        return result

    async def invite_member(self, token: str, email: str, role: str):
        return await self._request("POST", "/organizations/team/invite", token,
                                   {"email": email, "role": role})


api_client = APIClient()


# =============================================================================
# PUBLIC ROUTES
# =============================================================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Redirect to dashboard or login."""
    user = get_session_user(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    return RedirectResponse(url="/auth/login", status_code=302)


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy", "service": "org_portal"}


# =============================================================================
# AUTHENTICATION
# =============================================================================

@app.get("/auth/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page."""
    if get_session_user(request):
        return RedirectResponse(url="/dashboard", status_code=302)

    return templates.TemplateResponse("auth/login.html", template_context(
        request,
        page_title="Organization Sign In"
    ))


@app.post("/auth/login")
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...)
):
    """Handle login."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{AUTH_SERVICE_URL}/api/auth/login",
                json={"email": email, "password": password, "role": "organization"}
            )
            result = response.json()

            if response.status_code == 200 and result.get("success"):
                request.session["access_token"] = result["tokens"]["access"]
                request.session["refresh_token"] = result["tokens"]["refresh"]
                request.session["user"] = result["user"]
                return RedirectResponse(url="/dashboard", status_code=302)

            return templates.TemplateResponse("auth/login.html", template_context(
                request,
                page_title="Organization Sign In",
                error=result.get("error", "Login failed"),
                email=email
            ))

    except Exception as e:
        logger.error(f"Login error: {e}")
        return templates.TemplateResponse("auth/login.html", template_context(
            request,
            page_title="Organization Sign In",
            error="Service unavailable. Please try again.",
            email=email
        ))


@app.get("/auth/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Registration page."""
    if get_session_user(request):
        return RedirectResponse(url="/dashboard", status_code=302)

    return templates.TemplateResponse("auth/register.html", template_context(
        request,
        page_title="Register Your Organization"
    ))


@app.post("/auth/register")
async def register_submit(
    request: Request,
    organization_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    industry: str = Form(...),
    country: str = Form(...),
    website: str = Form(""),
    consent_terms: bool = Form(False)
):
    """Handle registration."""
    errors = {}

    if password != confirm_password:
        errors["confirm_password"] = "Passwords do not match"

    if not consent_terms:
        errors["consent_terms"] = "You must accept the terms"

    if errors:
        return templates.TemplateResponse("auth/register.html", template_context(
            request,
            page_title="Register Your Organization",
            errors=errors,
            organization_name=organization_name,
            email=email,
            industry=industry,
            country=country
        ))

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{AUTH_SERVICE_URL}/api/auth/register",
                json={
                    "email": email,
                    "password": password,
                    "role": "organization",
                    "organization_name": organization_name,
                    "industry": industry,
                    "country": country,
                    "website": website
                }
            )
            result = response.json()

            if response.status_code == 201:
                return templates.TemplateResponse("auth/register_success.html", template_context(
                    request,
                    page_title="Registration Successful",
                    email=email
                ))

            return templates.TemplateResponse("auth/register.html", template_context(
                request,
                page_title="Register Your Organization",
                errors={"general": result.get("error", "Registration failed")},
                organization_name=organization_name,
                email=email
            ))

    except Exception as e:
        logger.error(f"Registration error: {e}")
        return templates.TemplateResponse("auth/register.html", template_context(
            request,
            page_title="Register Your Organization",
            errors={"general": "Service unavailable"},
            organization_name=organization_name,
            email=email
        ))


@app.get("/auth/logout")
async def logout(request: Request):
    """Logout."""
    request.session.clear()
    return RedirectResponse(url="/auth/login", status_code=302)


# =============================================================================
# DASHBOARD (Protected)
# =============================================================================

@app.get("/dashboard", response_class=HTMLResponse)
@login_required
async def dashboard(request: Request):
    """Main dashboard."""
    token = get_access_token(request)

    try:
        org = await api_client.get_organization(token)
        opportunities = await api_client.get_opportunities(token)
        applications = await api_client.get_applications(token)
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        org = {}
        opportunities = {"results": [], "count": 0}
        applications = {"results": [], "count": 0}

    # Calculate stats
    stats = {
        "total_opportunities": opportunities.get("count", 0),
        "active_opportunities": len([o for o in opportunities.get("results", []) if o.get("status") == "active"]),
        "total_applications": applications.get("count", 0),
        "pending_review": len([a for a in applications.get("results", []) if a.get("status") == "pending"])
    }

    return templates.TemplateResponse("dashboard/index.html", template_context(
        request,
        page_title="Dashboard",
        organization=org,
        stats=stats,
        recent_applications=applications.get("results", [])[:5]
    ))


# =============================================================================
# OPPORTUNITIES (Protected)
# =============================================================================

@app.get("/opportunities", response_class=HTMLResponse)
@login_required
async def opportunities_list(request: Request, page: int = Query(1)):
    """List opportunities."""
    token = get_access_token(request)
    opportunities = await api_client.get_opportunities(token, page)

    return templates.TemplateResponse("opportunities/list.html", template_context(
        request,
        page_title="Opportunities",
        opportunities=opportunities,
        current_page=page
    ))


@app.get("/opportunities/new", response_class=HTMLResponse)
@login_required
async def opportunity_create_page(request: Request):
    """Create opportunity form."""
    return templates.TemplateResponse("opportunities/edit.html", template_context(
        request,
        page_title="Create Opportunity",
        opportunity=None
    ))


@app.post("/opportunities/new")
@login_required
async def opportunity_create_submit(
    request: Request,
    title: str = Form(...),
    description: str = Form(...),
    opportunity_type: str = Form(...),
    location: str = Form(...),
    remote_option: str = Form("onsite"),
    salary_min: int = Form(None),
    salary_max: int = Form(None),
    requirements: str = Form(""),
    benefits: str = Form("")
):
    """Create new opportunity."""
    token = get_access_token(request)

    data = {
        "title": title,
        "description": description,
        "opportunity_type": opportunity_type,
        "location": location,
        "remote_option": remote_option,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "requirements": requirements,
        "benefits": benefits
    }

    result, status = await api_client.create_opportunity(token, data)

    if status == 201:
        return RedirectResponse(url="/opportunities?created=1", status_code=302)

    return templates.TemplateResponse("opportunities/edit.html", template_context(
        request,
        page_title="Create Opportunity",
        opportunity=data,
        error=result.get("error", "Failed to create opportunity")
    ))


@app.get("/opportunities/{opp_id}", response_class=HTMLResponse)
@login_required
async def opportunity_detail(request: Request, opp_id: str):
    """View opportunity details."""
    token = get_access_token(request)
    opportunity = await api_client.get_opportunity(token, opp_id)
    applications = await api_client.get_applications(token, opportunity_id=opp_id)

    if not opportunity or "error" in opportunity:
        return templates.TemplateResponse("errors/404.html", template_context(
            request, page_title="Not Found"
        ), status_code=404)

    return templates.TemplateResponse("opportunities/detail.html", template_context(
        request,
        page_title=opportunity.get("title", "Opportunity"),
        opportunity=opportunity,
        applications=applications
    ))


@app.get("/opportunities/{opp_id}/edit", response_class=HTMLResponse)
@login_required
async def opportunity_edit_page(request: Request, opp_id: str):
    """Edit opportunity form."""
    token = get_access_token(request)
    opportunity = await api_client.get_opportunity(token, opp_id)

    if not opportunity:
        return RedirectResponse(url="/opportunities", status_code=302)

    return templates.TemplateResponse("opportunities/edit.html", template_context(
        request,
        page_title=f"Edit: {opportunity.get('title', 'Opportunity')}",
        opportunity=opportunity
    ))


@app.post("/opportunities/{opp_id}/edit")
@login_required
async def opportunity_edit_submit(
    request: Request,
    opp_id: str,
    title: str = Form(...),
    description: str = Form(...),
    opportunity_type: str = Form(...),
    location: str = Form(...),
    remote_option: str = Form("onsite"),
    salary_min: int = Form(None),
    salary_max: int = Form(None),
    requirements: str = Form(""),
    benefits: str = Form(""),
    status: str = Form("active")
):
    """Update opportunity."""
    token = get_access_token(request)

    data = {
        "title": title,
        "description": description,
        "opportunity_type": opportunity_type,
        "location": location,
        "remote_option": remote_option,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "requirements": requirements,
        "benefits": benefits,
        "status": status
    }

    result, status_code = await api_client.update_opportunity(token, opp_id, data)

    if status_code == 200:
        return RedirectResponse(url=f"/opportunities/{opp_id}?updated=1", status_code=302)

    return templates.TemplateResponse("opportunities/edit.html", template_context(
        request,
        page_title=f"Edit: {title}",
        opportunity=data,
        error=result.get("error", "Failed to update opportunity")
    ))


# =============================================================================
# APPLICATIONS (Protected)
# =============================================================================

@app.get("/applications", response_class=HTMLResponse)
@login_required
async def applications_list(request: Request, page: int = Query(1), status: str = Query(None)):
    """List received applications."""
    token = get_access_token(request)
    applications = await api_client.get_applications(token, page=page)

    # Filter by status if provided
    if status and applications.get("results"):
        applications["results"] = [a for a in applications["results"] if a.get("status") == status]

    return templates.TemplateResponse("applications/list.html", template_context(
        request,
        page_title="Applications",
        applications=applications,
        current_page=page,
        filter_status=status
    ))


@app.get("/applications/{app_id}", response_class=HTMLResponse)
@login_required
async def application_detail(request: Request, app_id: str):
    """View application details."""
    token = get_access_token(request)
    application = await api_client.get_application(token, app_id)

    if not application or "error" in application:
        return templates.TemplateResponse("errors/404.html", template_context(
            request, page_title="Not Found"
        ), status_code=404)

    return templates.TemplateResponse("applications/detail.html", template_context(
        request,
        page_title="Application Review",
        application=application
    ))


@app.post("/applications/{app_id}/status")
@login_required
async def update_application_status(
    request: Request,
    app_id: str,
    status: str = Form(...),
    notes: str = Form("")
):
    """Update application status."""
    token = get_access_token(request)

    result, status_code = await api_client.update_application_status(token, app_id, status, notes)

    if status_code == 200:
        return RedirectResponse(url=f"/applications/{app_id}?updated=1", status_code=302)

    return JSONResponse(content={"error": result.get("error")}, status_code=status_code)


@app.post("/applications/{app_id}/notes")
@login_required
async def save_application_notes(
    request: Request,
    app_id: str,
    notes: str = Form(...)
):
    """Save internal notes for application."""
    token = get_access_token(request)

    # Save notes via API
    result, status_code = await api_client._request(
        "PATCH", f"/applications/{app_id}", token, {"internal_notes": notes}
    )

    if status_code == 200:
        return JSONResponse(content={"success": True})

    return JSONResponse(content={"error": "Failed to save notes"}, status_code=400)


# =============================================================================
# TEAM (Protected)
# =============================================================================

@app.get("/team", response_class=HTMLResponse)
@login_required
async def team_page(request: Request):
    """Team management page."""
    token = get_access_token(request)
    team = await api_client.get_team(token)

    return templates.TemplateResponse("team/index.html", template_context(
        request,
        page_title="Team",
        team=team
    ))


@app.post("/team/invite")
@login_required
async def invite_member(
    request: Request,
    email: str = Form(...),
    role: str = Form(...)
):
    """Invite team member."""
    token = get_access_token(request)

    result, status = await api_client.invite_member(token, email, role)

    if status == 201:
        return RedirectResponse(url="/team?invited=1", status_code=302)

    return templates.TemplateResponse("team/index.html", template_context(
        request,
        page_title="Team",
        error=result.get("error", "Failed to send invite")
    ))


# =============================================================================
# SETTINGS (Protected)
# =============================================================================

@app.get("/settings", response_class=HTMLResponse)
@login_required
async def settings_page(request: Request):
    """Settings page."""
    token = get_access_token(request)
    org = await api_client.get_organization(token)

    return templates.TemplateResponse("settings/index.html", template_context(
        request,
        page_title="Settings",
        organization=org
    ))


@app.post("/settings")
@login_required
async def update_settings(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    website: str = Form(""),
    industry: str = Form(...),
    size: str = Form(""),
    founded_year: int = Form(None)
):
    """Update organization settings."""
    token = get_access_token(request)

    data = {
        "name": name,
        "description": description,
        "website": website,
        "industry": industry,
        "size": size,
        "founded_year": founded_year
    }

    result, status = await api_client._request("PATCH", "/organizations/me", token, data)

    if status == 200:
        return RedirectResponse(url="/settings?updated=1", status_code=302)

    return templates.TemplateResponse("settings/index.html", template_context(
        request,
        page_title="Settings",
        organization=data,
        error=result.get("error", "Failed to update settings")
    ))


# =============================================================================
# ERROR HANDLERS
# =============================================================================

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return templates.TemplateResponse("errors/404.html", template_context(
        request, page_title="Not Found"
    ), status_code=404)


@app.exception_handler(500)
async def server_error_handler(request: Request, exc):
    return templates.TemplateResponse("errors/500.html", template_context(
        request, page_title="Server Error"
    ), status_code=500)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("ORG_PORTAL_PORT", "9004"))
    uvicorn.run(app, host="0.0.0.0", port=port, reload=True)


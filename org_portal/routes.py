# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Organization Portal Routes
===============================================
Web routes for the organization portal.
"""
import logging
from typing import Optional
from fastapi import APIRouter, Request, Form, UploadFile, File, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import httpx

from .config import config
from .auth import auth_client, login_required, get_session_user, get_access_token
from .api_client import api_client

logger = logging.getLogger('org_portal.routes')

router = APIRouter()
templates = Jinja2Templates(directory=str(config.TEMPLATES_DIR))


def template_context(request: Request, **kwargs):
    """Build template context with common variables."""
    user = get_session_user(request)
    org = request.session.get('organization')
    return {
        'request': request,
        'user': user,
        'organization': org,
        'site_name': config.SITE_NAME,
        'main_site_url': config.MAIN_SITE_URL,
        **kwargs
    }


# =============================================================================
# PUBLIC ROUTES
# =============================================================================

@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Landing page / redirect to dashboard if logged in."""
    user = get_session_user(request)
    if user:
        return RedirectResponse(url='/dashboard', status_code=302)
    return RedirectResponse(url='/auth/login', status_code=302)


# =============================================================================
# AUTHENTICATION ROUTES
# =============================================================================

@router.get("/auth/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page."""
    user = get_session_user(request)
    if user:
        return RedirectResponse(url='/dashboard', status_code=302)

    return templates.TemplateResponse("auth/login.html", template_context(
        request,
        page_title="Organization Sign In",
        next_url=request.query_params.get('next', '/dashboard')
    ))


@router.post("/auth/login")
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next_url: str = Form('/dashboard')
):
    """Handle login form submission."""
    try:
        result, status_code = await auth_client.login(email, password, role='organization')

        if status_code == 200 and result.get('success'):
            # Store tokens in session
            request.session['access_token'] = result['tokens']['access']
            request.session['refresh_token'] = result['tokens']['refresh']
            request.session['user'] = result['user']

            # Fetch organization data
            try:
                org = await api_client.get_my_organization(result['tokens']['access'])
                request.session['organization'] = org
            except:
                pass

            logger.info(f"Organization user logged in: {email}")
            return RedirectResponse(url=next_url, status_code=302)

        else:
            error = result.get('error', 'Login failed')
            return templates.TemplateResponse("auth/login.html", template_context(
                request,
                page_title="Organization Sign In",
                error=error,
                email=email,
                next_url=next_url
            ))

    except Exception as e:
        logger.error(f"Login error: {e}")
        return templates.TemplateResponse("auth/login.html", template_context(
            request,
            page_title="Organization Sign In",
            error="An error occurred. Please try again.",
            email=email,
            next_url=next_url
        ))


@router.get("/auth/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Registration page."""
    user = get_session_user(request)
    if user:
        return RedirectResponse(url='/dashboard', status_code=302)

    return templates.TemplateResponse("auth/register.html", template_context(
        request,
        page_title="Register Your Organization"
    ))


@router.post("/auth/register")
async def register_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    organization_name: str = Form(...),
    organization_type: str = Form(...),
    industry: str = Form(''),
    contact_person: str = Form(''),
    phone_number: str = Form(''),
    country: str = Form(''),
    consent_privacy: bool = Form(False),
    consent_terms: bool = Form(False)
):
    """Handle registration form submission."""
    errors = {}

    if password != confirm_password:
        errors['confirm_password'] = "Passwords do not match"

    if not consent_privacy:
        errors['consent_privacy'] = "You must accept the privacy policy"

    if not consent_terms:
        errors['consent_terms'] = "You must accept the terms of service"

    if errors:
        return templates.TemplateResponse("auth/register.html", template_context(
            request,
            page_title="Register Your Organization",
            errors=errors,
            email=email,
            organization_name=organization_name,
            organization_type=organization_type,
            industry=industry,
            contact_person=contact_person,
            phone_number=phone_number,
            country=country
        ))

    try:
        result, status_code = await auth_client.register(
            email=email,
            password=password,
            role='organization',
            first_name=contact_person,
            phone_number=phone_number,
            consent_privacy=consent_privacy,
            consent_terms=consent_terms,
            extra_data={
                'organization_name': organization_name,
                'organization_type': organization_type,
                'industry': industry,
                'country': country
            }
        )

        if status_code == 201 and result.get('success'):
            logger.info(f"New organization registered: {organization_name} ({email})")
            return templates.TemplateResponse("auth/register_success.html", template_context(
                request,
                page_title="Registration Successful",
                email=email,
                organization_name=organization_name
            ))
        else:
            error = result.get('error', 'Registration failed')
            errors['general'] = error
            return templates.TemplateResponse("auth/register.html", template_context(
                request,
                page_title="Register Your Organization",
                errors=errors,
                email=email,
                organization_name=organization_name,
                organization_type=organization_type,
                industry=industry,
                contact_person=contact_person,
                phone_number=phone_number,
                country=country
            ))

    except Exception as e:
        logger.error(f"Registration error: {e}")
        return templates.TemplateResponse("auth/register.html", template_context(
            request,
            page_title="Register Your Organization",
            errors={'general': "An error occurred. Please try again."},
            email=email,
            organization_name=organization_name,
            organization_type=organization_type,
            industry=industry,
            contact_person=contact_person,
            phone_number=phone_number,
            country=country
        ))


@router.get("/auth/logout")
async def logout(request: Request):
    """Logout user."""
    refresh_token = request.session.get('refresh_token')

    if refresh_token:
        try:
            await auth_client.logout(refresh_token)
        except Exception as e:
            logger.error(f"Logout error: {e}")

    request.session.clear()
    return RedirectResponse(url='/auth/login', status_code=302)


# =============================================================================
# DASHBOARD (Protected)
# =============================================================================

@router.get("/dashboard", response_class=HTMLResponse)
@login_required
async def dashboard(request: Request):
    """Main dashboard."""
    access_token = get_access_token(request)
    user = get_session_user(request)

    try:
        org = await api_client.get_my_organization(access_token)
        opportunities = await api_client.get_organization_opportunities(access_token)
        applications = await api_client.get_received_applications(access_token)
        stats = await api_client.get_organization_stats(access_token)
    except Exception as e:
        logger.error(f"Dashboard data fetch error: {e}")
        org = request.session.get('organization', {})
        opportunities = {'results': [], 'count': 0}
        applications = {'results': [], 'count': 0}
        stats = {'total_opportunities': 0, 'active_opportunities': 0, 'total_applications': 0, 'pending_review': 0}

    return templates.TemplateResponse("dashboard/index.html", template_context(
        request,
        page_title="Dashboard",
        organization=org,
        opportunities=opportunities,
        applications=applications,
        stats=stats
    ))


# =============================================================================
# OPPORTUNITIES MANAGEMENT
# =============================================================================

@router.get("/opportunities", response_class=HTMLResponse)
@login_required
async def opportunities_list(request: Request):
    """List organization's opportunities."""
    access_token = get_access_token(request)

    status_filter = request.query_params.get('status', '')
    search = request.query_params.get('search', '')
    page = int(request.query_params.get('page', 1))

    try:
        opportunities = await api_client.get_organization_opportunities(
            access_token,
            status=status_filter,
            search=search,
            page=page
        )
    except Exception as e:
        logger.error(f"Opportunities fetch error: {e}")
        opportunities = {'results': [], 'count': 0}

    return templates.TemplateResponse("opportunities/list.html", template_context(
        request,
        page_title="Manage Opportunities",
        opportunities=opportunities,
        current_status=status_filter,
        search_query=search,
        current_page=page
    ))


@router.get("/opportunities/create", response_class=HTMLResponse)
@login_required
async def opportunity_create_page(request: Request):
    """Create opportunity form."""
    return templates.TemplateResponse("opportunities/edit.html", template_context(
        request,
        page_title="Create Opportunity",
        opportunity=None,
        is_new=True
    ))


@router.post("/opportunities/create")
@login_required
async def opportunity_create_submit(
    request: Request,
    title: str = Form(...),
    description: str = Form(...),
    opportunity_type: str = Form(...),
    location: str = Form(''),
    remote_type: str = Form('onsite'),
    salary_min: Optional[int] = Form(None),
    salary_max: Optional[int] = Form(None),
    salary_currency: str = Form('USD'),
    experience_level: str = Form(''),
    skills_required: str = Form(''),
    application_deadline: str = Form(''),
    status: str = Form('draft')
):
    """Create new opportunity."""
    access_token = get_access_token(request)

    try:
        data = {
            'title': title,
            'description': description,
            'opportunity_type': opportunity_type,
            'location': location,
            'remote_type': remote_type,
            'salary_min': salary_min,
            'salary_max': salary_max,
            'salary_currency': salary_currency,
            'experience_level': experience_level,
            'skills_required': [s.strip() for s in skills_required.split(',') if s.strip()],
            'application_deadline': application_deadline or None,
            'status': status
        }

        result = await api_client.create_opportunity(access_token, data)

        if result.get('id'):
            logger.info(f"Opportunity created: {title}")
            return RedirectResponse(url=f'/opportunities/{result["id"]}', status_code=302)
        else:
            error = result.get('error', 'Failed to create opportunity')
            return templates.TemplateResponse("opportunities/edit.html", template_context(
                request,
                page_title="Create Opportunity",
                opportunity=data,
                is_new=True,
                error=error
            ))

    except Exception as e:
        logger.error(f"Opportunity creation error: {e}")
        return templates.TemplateResponse("opportunities/edit.html", template_context(
            request,
            page_title="Create Opportunity",
            opportunity=None,
            is_new=True,
            error="An error occurred. Please try again."
        ))


@router.get("/opportunities/{opportunity_id}", response_class=HTMLResponse)
@login_required
async def opportunity_detail(request: Request, opportunity_id: str):
    """View opportunity details."""
    access_token = get_access_token(request)

    try:
        opportunity = await api_client.get_opportunity(access_token, opportunity_id)
        applications = await api_client.get_opportunity_applications(access_token, opportunity_id)
    except Exception as e:
        logger.error(f"Opportunity fetch error: {e}")
        return templates.TemplateResponse("errors/404.html", template_context(
            request,
            page_title="Not Found"
        ), status_code=404)

    return templates.TemplateResponse("opportunities/detail.html", template_context(
        request,
        page_title=opportunity.get('title', 'Opportunity Details'),
        opportunity=opportunity,
        applications=applications
    ))


@router.get("/opportunities/{opportunity_id}/edit", response_class=HTMLResponse)
@login_required
async def opportunity_edit_page(request: Request, opportunity_id: str):
    """Edit opportunity form."""
    access_token = get_access_token(request)

    try:
        opportunity = await api_client.get_opportunity(access_token, opportunity_id)
    except Exception as e:
        logger.error(f"Opportunity fetch error: {e}")
        return templates.TemplateResponse("errors/404.html", template_context(
            request,
            page_title="Not Found"
        ), status_code=404)

    return templates.TemplateResponse("opportunities/edit.html", template_context(
        request,
        page_title=f"Edit: {opportunity.get('title', '')}",
        opportunity=opportunity,
        is_new=False
    ))


@router.post("/opportunities/{opportunity_id}/edit")
@login_required
async def opportunity_edit_submit(
    request: Request,
    opportunity_id: str,
    title: str = Form(...),
    description: str = Form(...),
    opportunity_type: str = Form(...),
    location: str = Form(''),
    remote_type: str = Form('onsite'),
    salary_min: Optional[int] = Form(None),
    salary_max: Optional[int] = Form(None),
    salary_currency: str = Form('USD'),
    experience_level: str = Form(''),
    skills_required: str = Form(''),
    application_deadline: str = Form(''),
    status: str = Form('draft')
):
    """Update opportunity."""
    access_token = get_access_token(request)

    try:
        data = {
            'title': title,
            'description': description,
            'opportunity_type': opportunity_type,
            'location': location,
            'remote_type': remote_type,
            'salary_min': salary_min,
            'salary_max': salary_max,
            'salary_currency': salary_currency,
            'experience_level': experience_level,
            'skills_required': [s.strip() for s in skills_required.split(',') if s.strip()],
            'application_deadline': application_deadline or None,
            'status': status
        }

        result = await api_client.update_opportunity(access_token, opportunity_id, data)

        if result.get('id'):
            logger.info(f"Opportunity updated: {title}")
            return RedirectResponse(url=f'/opportunities/{opportunity_id}', status_code=302)
        else:
            error = result.get('error', 'Failed to update opportunity')
            return templates.TemplateResponse("opportunities/edit.html", template_context(
                request,
                page_title=f"Edit: {title}",
                opportunity=data,
                is_new=False,
                error=error
            ))

    except Exception as e:
        logger.error(f"Opportunity update error: {e}")
        return templates.TemplateResponse("opportunities/edit.html", template_context(
            request,
            page_title="Edit Opportunity",
            opportunity=None,
            is_new=False,
            error="An error occurred. Please try again."
        ))


@router.post("/opportunities/{opportunity_id}/delete")
@login_required
async def opportunity_delete(request: Request, opportunity_id: str):
    """Delete opportunity."""
    access_token = get_access_token(request)

    try:
        await api_client.delete_opportunity(access_token, opportunity_id)
        logger.info(f"Opportunity deleted: {opportunity_id}")
    except Exception as e:
        logger.error(f"Opportunity deletion error: {e}")

    return RedirectResponse(url='/opportunities', status_code=302)


# =============================================================================
# APPLICATIONS REVIEW
# =============================================================================

@router.get("/applications", response_class=HTMLResponse)
@login_required
async def applications_list(request: Request):
    """List received applications."""
    access_token = get_access_token(request)

    status_filter = request.query_params.get('status', '')
    opportunity_id = request.query_params.get('opportunity', '')
    page = int(request.query_params.get('page', 1))

    try:
        applications = await api_client.get_received_applications(
            access_token,
            status=status_filter,
            opportunity_id=opportunity_id,
            page=page
        )
        opportunities = await api_client.get_organization_opportunities(access_token)
    except Exception as e:
        logger.error(f"Applications fetch error: {e}")
        applications = {'results': [], 'count': 0}
        opportunities = {'results': []}

    return templates.TemplateResponse("applications/list.html", template_context(
        request,
        page_title="Review Applications",
        applications=applications,
        opportunities=opportunities.get('results', []),
        current_status=status_filter,
        current_opportunity=opportunity_id,
        current_page=page
    ))


@router.get("/applications/{application_id}", response_class=HTMLResponse)
@login_required
async def application_detail(request: Request, application_id: str):
    """View application details."""
    access_token = get_access_token(request)

    try:
        application = await api_client.get_application(access_token, application_id)
        candidate = await api_client.get_candidate_profile(access_token, application.get('talent_id'))
    except Exception as e:
        logger.error(f"Application fetch error: {e}")
        return templates.TemplateResponse("errors/404.html", template_context(
            request,
            page_title="Not Found"
        ), status_code=404)

    return templates.TemplateResponse("applications/detail.html", template_context(
        request,
        page_title="Application Review",
        application=application,
        candidate=candidate
    ))


@router.post("/applications/{application_id}/status")
@login_required
async def application_update_status(
    request: Request,
    application_id: str,
    status: str = Form(...),
    notes: str = Form('')
):
    """Update application status."""
    access_token = get_access_token(request)

    try:
        result = await api_client.update_application_status(
            access_token,
            application_id,
            status=status,
            notes=notes
        )
        logger.info(f"Application {application_id} status updated to: {status}")
    except Exception as e:
        logger.error(f"Application status update error: {e}")

    return RedirectResponse(url=f'/applications/{application_id}', status_code=302)


@router.post("/applications/{application_id}/notes")
@login_required
async def application_save_notes(
    request: Request,
    application_id: str,
    notes: str = Form('')
):
    """Save notes for application."""
    access_token = get_access_token(request)

    try:
        await api_client.save_application_notes(access_token, application_id, notes)
        logger.info(f"Notes saved for application: {application_id}")
    except Exception as e:
        logger.error(f"Application notes save error: {e}")

    return RedirectResponse(url=f'/applications/{application_id}', status_code=302)


# =============================================================================
# TEAM MANAGEMENT
# =============================================================================

@router.get("/team", response_class=HTMLResponse)
@login_required
async def team_list(request: Request):
    """View team members."""
    access_token = get_access_token(request)

    try:
        members = await api_client.get_team_members(access_token)
        pending_invites = await api_client.get_pending_invites(access_token)
    except Exception as e:
        logger.error(f"Team fetch error: {e}")
        members = []
        pending_invites = []

    return templates.TemplateResponse("team/index.html", template_context(
        request,
        page_title="Team Members",
        members=members,
        pending_invites=pending_invites
    ))


@router.post("/team/invite")
@login_required
async def team_invite(
    request: Request,
    email: str = Form(...),
    role: str = Form('member')
):
    """Invite team member."""
    access_token = get_access_token(request)

    try:
        result = await api_client.invite_team_member(access_token, email, role)
        if result.get('success'):
            logger.info(f"Team invite sent to: {email}")
        else:
            logger.warning(f"Team invite failed for: {email}")
    except Exception as e:
        logger.error(f"Team invite error: {e}")

    return RedirectResponse(url='/team', status_code=302)


@router.post("/team/{member_id}/remove")
@login_required
async def team_remove_member(request: Request, member_id: str):
    """Remove team member."""
    access_token = get_access_token(request)

    try:
        await api_client.remove_team_member(access_token, member_id)
        logger.info(f"Team member removed: {member_id}")
    except Exception as e:
        logger.error(f"Team member removal error: {e}")

    return RedirectResponse(url='/team', status_code=302)


# =============================================================================
# SETTINGS
# =============================================================================

@router.get("/settings", response_class=HTMLResponse)
@login_required
async def settings_page(request: Request):
    """Organization settings."""
    access_token = get_access_token(request)

    try:
        organization = await api_client.get_my_organization(access_token)
    except Exception as e:
        logger.error(f"Organization fetch error: {e}")
        organization = {}

    return templates.TemplateResponse("settings/index.html", template_context(
        request,
        page_title="Organization Settings",
        organization=organization
    ))


@router.post("/settings")
@login_required
async def settings_update(
    request: Request,
    organization_name: str = Form(...),
    description: str = Form(''),
    website: str = Form(''),
    industry: str = Form(''),
    company_size: str = Form(''),
    headquarters: str = Form(''),
    contact_email: str = Form(''),
    contact_phone: str = Form('')
):
    """Update organization settings."""
    access_token = get_access_token(request)

    try:
        data = {
            'name': organization_name,
            'description': description,
            'website': website,
            'industry': industry,
            'company_size': company_size,
            'headquarters': headquarters,
            'contact_email': contact_email,
            'contact_phone': contact_phone
        }

        result = await api_client.update_organization(access_token, data)

        if result.get('id'):
            request.session['organization'] = result
            success = True
            error = None
        else:
            success = False
            error = result.get('error', 'Failed to update settings')

    except Exception as e:
        logger.error(f"Settings update error: {e}")
        success = False
        error = "An error occurred. Please try again."

    organization = await api_client.get_my_organization(access_token) if success else data

    return templates.TemplateResponse("settings/index.html", template_context(
        request,
        page_title="Organization Settings",
        organization=organization,
        success=success,
        error=error
    ))


@router.post("/settings/logo")
@login_required
async def settings_upload_logo(
    request: Request,
    logo: UploadFile = File(...)
):
    """Upload organization logo."""
    access_token = get_access_token(request)

    try:
        result = await api_client.upload_organization_logo(access_token, logo)
        if result.get('logo_url'):
            logger.info("Organization logo uploaded")
    except Exception as e:
        logger.error(f"Logo upload error: {e}")

    return RedirectResponse(url='/settings', status_code=302)


# =============================================================================
# ERROR HANDLERS
# =============================================================================

@router.get("/404", response_class=HTMLResponse)
async def not_found(request: Request):
    """404 page."""
    return templates.TemplateResponse("errors/404.html", template_context(
        request,
        page_title="Page Not Found"
    ), status_code=404)


@router.get("/500", response_class=HTMLResponse)
async def server_error(request: Request):
    """500 page."""
    return templates.TemplateResponse("errors/500.html", template_context(
        request,
        page_title="Server Error"
    ), status_code=500)


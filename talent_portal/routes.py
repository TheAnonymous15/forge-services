# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Talent Portal Routes
========================================
Web routes for the talent portal.
"""
import logging
from typing import Optional
from fastapi import APIRouter, Request, Form, UploadFile, File, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from .config import config
from .auth import auth_client, login_required, verified_email_required, get_session_user, get_access_token
from .api_client import api_client

logger = logging.getLogger('talent_portal.routes')

router = APIRouter()
templates = Jinja2Templates(directory=str(config.TEMPLATES_DIR))


def template_context(request: Request, **kwargs):
    """Build template context with common variables."""
    user = get_session_user(request)
    return {
        'request': request,
        'user': user,
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
        page_title="Sign In",
        next_url=request.query_params.get('next', '/dashboard')
    ))


@router.post("/auth/login")
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    otp_code: Optional[str] = Form(None),
    next_url: str = Form('/dashboard')
):
    """Handle login form submission."""
    try:
        result, status_code = await auth_client.login(email, password, otp_code)

        if status_code == 200 and result.get('success'):
            # Store tokens in session
            request.session['access_token'] = result['tokens']['access']
            request.session['refresh_token'] = result['tokens']['refresh']
            request.session['user'] = result['user']

            logger.info(f"User logged in: {email}")

            # Redirect to intended destination
            return RedirectResponse(url=next_url, status_code=302)

        elif result.get('requires_2fa'):
            # Show 2FA form
            return templates.TemplateResponse("auth/2fa.html", template_context(
                request,
                page_title="Two-Factor Authentication",
                email=email,
                password=password,  # Hidden field for resubmission
                next_url=next_url
            ))

        else:
            error = result.get('error', 'Login failed')
            return templates.TemplateResponse("auth/login.html", template_context(
                request,
                page_title="Sign In",
                error=error,
                email=email,
                next_url=next_url
            ))

    except Exception as e:
        logger.error(f"Login error: {e}")
        return templates.TemplateResponse("auth/login.html", template_context(
            request,
            page_title="Sign In",
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
        page_title="Create Your Account"
    ))


@router.post("/auth/register")
async def register_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    first_name: str = Form(''),
    last_name: str = Form(''),
    phone_number: str = Form(''),
    consent_privacy: bool = Form(False),
    consent_terms: bool = Form(False),
    consent_marketing: bool = Form(False)
):
    """Handle registration form submission."""
    errors = {}

    # Validation
    if password != confirm_password:
        errors['confirm_password'] = "Passwords do not match"

    if not consent_privacy:
        errors['consent_privacy'] = "You must accept the privacy policy"

    if not consent_terms:
        errors['consent_terms'] = "You must accept the terms of service"

    if errors:
        return templates.TemplateResponse("auth/register.html", template_context(
            request,
            page_title="Create Your Account",
            errors=errors,
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number
        ))

    try:
        result, status_code = await auth_client.register(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
            consent_privacy=consent_privacy,
            consent_terms=consent_terms,
            consent_marketing=consent_marketing
        )

        if status_code == 201 and result.get('success'):
            logger.info(f"New user registered: {email}")

            # Redirect to verification notice
            return templates.TemplateResponse("auth/register_success.html", template_context(
                request,
                page_title="Registration Successful",
                email=email
            ))

        else:
            error = result.get('error', 'Registration failed')
            field = result.get('field')
            if field:
                errors[field] = error
            else:
                errors['general'] = error

            return templates.TemplateResponse("auth/register.html", template_context(
                request,
                page_title="Create Your Account",
                errors=errors,
                email=email,
                first_name=first_name,
                last_name=last_name,
                phone_number=phone_number
            ))

    except Exception as e:
        logger.error(f"Registration error: {e}")
        return templates.TemplateResponse("auth/register.html", template_context(
            request,
            page_title="Create Your Account",
            errors={'general': "An error occurred. Please try again."},
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number
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


@router.get("/auth/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    """Forgot password page."""
    return templates.TemplateResponse("auth/forgot_password.html", template_context(
        request,
        page_title="Forgot Password"
    ))


@router.post("/auth/forgot-password")
async def forgot_password_submit(request: Request, email: str = Form(...)):
    """Handle forgot password form."""
    try:
        result, _ = await auth_client.forgot_password(email)

        return templates.TemplateResponse("auth/forgot_password_sent.html", template_context(
            request,
            page_title="Check Your Email",
            email=email
        ))

    except Exception as e:
        logger.error(f"Forgot password error: {e}")
        return templates.TemplateResponse("auth/forgot_password.html", template_context(
            request,
            page_title="Forgot Password",
            error="An error occurred. Please try again."
        ))


@router.get("/auth/reset-password/{token}", response_class=HTMLResponse)
async def reset_password_page(request: Request, token: str):
    """Reset password page."""
    return templates.TemplateResponse("auth/reset_password.html", template_context(
        request,
        page_title="Reset Password",
        token=token
    ))


@router.post("/auth/reset-password/{token}")
async def reset_password_submit(
    request: Request,
    token: str,
    password: str = Form(...),
    confirm_password: str = Form(...)
):
    """Handle reset password form."""
    if password != confirm_password:
        return templates.TemplateResponse("auth/reset_password.html", template_context(
            request,
            page_title="Reset Password",
            token=token,
            error="Passwords do not match"
        ))

    try:
        result, status_code = await auth_client.reset_password(token, password)

        if status_code == 200 and result.get('success'):
            return templates.TemplateResponse("auth/reset_password_success.html", template_context(
                request,
                page_title="Password Reset Successful"
            ))
        else:
            error = result.get('error', 'Password reset failed')
            return templates.TemplateResponse("auth/reset_password.html", template_context(
                request,
                page_title="Reset Password",
                token=token,
                error=error
            ))

    except Exception as e:
        logger.error(f"Reset password error: {e}")
        return templates.TemplateResponse("auth/reset_password.html", template_context(
            request,
            page_title="Reset Password",
            token=token,
            error="An error occurred. Please try again."
        ))


@router.get("/auth/verify-email/{token}")
async def verify_email(request: Request, token: str):
    """Verify email with token."""
    try:
        result, status_code = await auth_client.verify_email(token)

        if status_code == 200 and result.get('success'):
            return templates.TemplateResponse("auth/email_verified.html", template_context(
                request,
                page_title="Email Verified"
            ))
        else:
            return templates.TemplateResponse("auth/email_verification_failed.html", template_context(
                request,
                page_title="Verification Failed",
                error=result.get('error', 'Verification failed')
            ))

    except Exception as e:
        logger.error(f"Email verification error: {e}")
        return templates.TemplateResponse("auth/email_verification_failed.html", template_context(
            request,
            page_title="Verification Failed",
            error="An error occurred. Please try again."
        ))


# =============================================================================
# DASHBOARD (Protected)
# =============================================================================

@router.get("/dashboard", response_class=HTMLResponse)
@login_required
async def dashboard(request: Request):
    """Main dashboard."""
    access_token = get_access_token(request)
    user = get_session_user(request)

    # Fetch dashboard data
    try:
        profile = await api_client.get_profile(access_token)
        applications = await api_client.get_my_applications(access_token)
        matches = await api_client.get_matches(access_token)
        notifications = await api_client.get_notifications(access_token, unread_only=True)
    except Exception as e:
        logger.error(f"Dashboard data fetch error: {e}")
        profile = None
        applications = {'results': [], 'count': 0}
        matches = {'results': [], 'count': 0}
        notifications = []

    return templates.TemplateResponse("dashboard/index.html", template_context(
        request,
        page_title="Dashboard",
        profile=profile,
        applications=applications,
        matches=matches,
        notifications=notifications
    ))


# =============================================================================
# PROFILE (Protected)
# =============================================================================

@router.get("/profile", response_class=HTMLResponse)
@login_required
async def profile_view(request: Request):
    """View profile."""
    access_token = get_access_token(request)

    try:
        profile = await api_client.get_profile(access_token)
        skills = await api_client.get_skills(access_token)
        experience = await api_client.get_experience(access_token)
        education = await api_client.get_education(access_token)
    except Exception as e:
        logger.error(f"Profile fetch error: {e}")
        profile = None
        skills = []
        experience = []
        education = []

    return templates.TemplateResponse("profile/view.html", template_context(
        request,
        page_title="My Profile",
        profile=profile,
        skills=skills,
        experience=experience,
        education=education
    ))


@router.get("/profile/edit", response_class=HTMLResponse)
@login_required
async def profile_edit(request: Request):
    """Edit profile page."""
    access_token = get_access_token(request)

    try:
        profile = await api_client.get_profile(access_token)
    except Exception as e:
        logger.error(f"Profile fetch error: {e}")
        profile = None

    return templates.TemplateResponse("profile/edit.html", template_context(
        request,
        page_title="Edit Profile",
        profile=profile
    ))


@router.post("/profile/edit")
@login_required
async def profile_update(
    request: Request,
    headline: str = Form(''),
    bio: str = Form(''),
    location: str = Form(''),
    website: str = Form(''),
    linkedin: str = Form(''),
    github: str = Form('')
):
    """Update profile."""
    access_token = get_access_token(request)

    try:
        result, status_code = await api_client.update_profile(access_token, {
            'headline': headline,
            'bio': bio,
            'location': location,
            'website': website,
            'linkedin': linkedin,
            'github': github
        })

        if status_code == 200:
            return RedirectResponse(url='/profile?updated=1', status_code=302)
        else:
            return templates.TemplateResponse("profile/edit.html", template_context(
                request,
                page_title="Edit Profile",
                error=result.get('error', 'Update failed'),
                profile=result
            ))

    except Exception as e:
        logger.error(f"Profile update error: {e}")
        return templates.TemplateResponse("profile/edit.html", template_context(
            request,
            page_title="Edit Profile",
            error="An error occurred. Please try again."
        ))


# =============================================================================
# OPPORTUNITIES (Protected)
# =============================================================================

@router.get("/opportunities", response_class=HTMLResponse)
@login_required
async def opportunities_list(
    request: Request,
    q: str = Query(None),
    location: str = Query(None),
    type: str = Query(None),
    page: int = Query(1)
):
    """Browse opportunities."""
    access_token = get_access_token(request)

    try:
        opportunities = await api_client.search_opportunities(
            access_token,
            query=q,
            location=location,
            job_type=type,
            page=page
        )
    except Exception as e:
        logger.error(f"Opportunities fetch error: {e}")
        opportunities = {'results': [], 'count': 0}

    return templates.TemplateResponse("opportunities/list.html", template_context(
        request,
        page_title="Browse Opportunities",
        opportunities=opportunities,
        query=q,
        location=location,
        job_type=type,
        current_page=page
    ))


@router.get("/opportunities/{opportunity_id}", response_class=HTMLResponse)
@login_required
async def opportunity_detail(request: Request, opportunity_id: str):
    """View opportunity details."""
    access_token = get_access_token(request)

    try:
        opportunity = await api_client.get_opportunity(access_token, opportunity_id)
    except Exception as e:
        logger.error(f"Opportunity fetch error: {e}")
        opportunity = None

    if not opportunity:
        return templates.TemplateResponse("errors/404.html", template_context(
            request,
            page_title="Not Found"
        ), status_code=404)

    return templates.TemplateResponse("opportunities/detail.html", template_context(
        request,
        page_title=opportunity.get('title', 'Opportunity'),
        opportunity=opportunity
    ))


# =============================================================================
# APPLICATIONS (Protected)
# =============================================================================

@router.get("/applications", response_class=HTMLResponse)
@login_required
async def applications_list(request: Request, page: int = Query(1)):
    """View my applications."""
    access_token = get_access_token(request)

    try:
        applications = await api_client.get_my_applications(access_token, page)
    except Exception as e:
        logger.error(f"Applications fetch error: {e}")
        applications = {'results': [], 'count': 0}

    return templates.TemplateResponse("applications/list.html", template_context(
        request,
        page_title="My Applications",
        applications=applications,
        current_page=page
    ))


@router.get("/applications/{application_id}", response_class=HTMLResponse)
@login_required
async def application_detail(request: Request, application_id: str):
    """View application details."""
    access_token = get_access_token(request)

    try:
        application = await api_client.get_application(access_token, application_id)
    except Exception as e:
        logger.error(f"Application fetch error: {e}")
        application = None

    if not application:
        return templates.TemplateResponse("errors/404.html", template_context(
            request,
            page_title="Not Found"
        ), status_code=404)

    return templates.TemplateResponse("applications/detail.html", template_context(
        request,
        page_title="Application Details",
        application=application
    ))


@router.post("/applications/{application_id}/withdraw")
@login_required
async def withdraw_application(request: Request, application_id: str):
    """Withdraw an application."""
    access_token = get_access_token(request)

    try:
        result, status_code = await api_client.withdraw_application(access_token, application_id)

        if status_code == 200:
            return RedirectResponse(url='/applications?withdrawn=1', status_code=302)
        else:
            return JSONResponse(content={'error': result.get('error')}, status_code=status_code)

    except Exception as e:
        logger.error(f"Withdraw application error: {e}")
        return JSONResponse(content={'error': 'Failed to withdraw application'}, status_code=500)


# =============================================================================
# MATCHES (Protected)
# =============================================================================

@router.get("/matches", response_class=HTMLResponse)
@login_required
async def matches_list(request: Request, page: int = Query(1)):
    """View recommended matches."""
    access_token = get_access_token(request)

    try:
        matches = await api_client.get_matches(access_token, page)
    except Exception as e:
        logger.error(f"Matches fetch error: {e}")
        matches = {'results': [], 'count': 0}

    return templates.TemplateResponse("matches/list.html", template_context(
        request,
        page_title="Recommended For You",
        matches=matches,
        current_page=page
    ))


# =============================================================================
# SETTINGS (Protected)
# =============================================================================

@router.get("/settings", response_class=HTMLResponse)
@login_required
async def settings_page(request: Request):
    """Settings page."""
    return templates.TemplateResponse("settings/index.html", template_context(
        request,
        page_title="Settings"
    ))


@router.get("/settings/notifications", response_class=HTMLResponse)
@login_required
async def notification_settings(request: Request):
    """Notification settings."""
    return templates.TemplateResponse("settings/notifications.html", template_context(
        request,
        page_title="Notification Settings"
    ))


@router.get("/settings/security", response_class=HTMLResponse)
@login_required
async def security_settings(request: Request):
    """Security settings (password, 2FA)."""
    return templates.TemplateResponse("settings/security.html", template_context(
        request,
        page_title="Security Settings"
    ))


# =============================================================================
# PROFILE API ROUTES (For AJAX calls from profile editor)
# =============================================================================

@router.post("/api/profile/skills")
@login_required
async def add_skill_api(request: Request):
    """Add skill via API."""
    access_token = get_access_token(request)
    data = await request.json()

    result, status = await api_client.add_skill(access_token, data)
    return JSONResponse(content=result, status_code=status)


@router.delete("/api/profile/skills/{skill_id}")
@login_required
async def delete_skill_api(request: Request, skill_id: str):
    """Delete skill via API."""
    access_token = get_access_token(request)
    result, status = await api_client.delete_skill(access_token, skill_id)
    return JSONResponse(content=result, status_code=status)


@router.delete("/api/profile/experience/{exp_id}")
@login_required
async def delete_experience_api(request: Request, exp_id: str):
    """Delete experience via API."""
    access_token = get_access_token(request)
    result, status = await api_client.delete_experience(access_token, exp_id)
    return JSONResponse(content=result, status_code=status)


@router.delete("/api/profile/education/{edu_id}")
@login_required
async def delete_education_api(request: Request, edu_id: str):
    """Delete education via API."""
    access_token = get_access_token(request)
    result, status = await api_client.delete_education(access_token, edu_id)
    return JSONResponse(content=result, status_code=status)


@router.post("/profile/photo")
@login_required
async def upload_photo(request: Request, photo: UploadFile = File(...)):
    """Upload profile photo."""
    access_token = get_access_token(request)

    try:
        file_data = await photo.read()
        result, status = await api_client.upload_photo(access_token, file_data, photo.filename)

        if status == 200:
            return RedirectResponse(url='/profile/edit?updated=1', status_code=302)
        else:
            return templates.TemplateResponse("profile/edit.html", template_context(
                request,
                page_title="Edit Profile",
                error=result.get('error', 'Photo upload failed')
            ))
    except Exception as e:
        logger.error(f"Photo upload error: {e}")
        return templates.TemplateResponse("profile/edit.html", template_context(
            request,
            page_title="Edit Profile",
            error="Photo upload failed. Please try again."
        ))


# =============================================================================
# EXPERIENCE ROUTES
# =============================================================================

@router.get("/profile/experience/add", response_class=HTMLResponse)
@login_required
async def experience_add_page(request: Request):
    """Add experience form."""
    return templates.TemplateResponse("profile/experience_form.html", template_context(
        request,
        page_title="Add Work Experience",
        experience=None
    ))


@router.post("/profile/experience/add")
@login_required
async def experience_add_submit(
    request: Request,
    title: str = Form(...),
    company: str = Form(...),
    location: str = Form(''),
    start_date: str = Form(...),
    end_date: str = Form(''),
    is_current: bool = Form(False),
    description: str = Form('')
):
    """Submit new experience."""
    access_token = get_access_token(request)

    data = {
        'title': title,
        'company': company,
        'location': location,
        'start_date': start_date,
        'end_date': end_date if not is_current else None,
        'is_current': is_current,
        'description': description
    }

    result, status = await api_client.add_experience(access_token, data)

    if status == 201:
        return RedirectResponse(url='/profile/edit', status_code=302)
    else:
        return templates.TemplateResponse("profile/experience_form.html", template_context(
            request,
            page_title="Add Work Experience",
            error=result.get('error', 'Failed to add experience'),
            experience=data
        ))


@router.get("/profile/experience/{exp_id}/edit", response_class=HTMLResponse)
@login_required
async def experience_edit_page(request: Request, exp_id: str):
    """Edit experience form."""
    access_token = get_access_token(request)
    experience_list = await api_client.get_experience(access_token)
    experience = next((e for e in experience_list if str(e.get('id')) == exp_id), None)

    if not experience:
        return RedirectResponse(url='/profile/edit', status_code=302)

    return templates.TemplateResponse("profile/experience_form.html", template_context(
        request,
        page_title="Edit Work Experience",
        experience=experience
    ))


@router.post("/profile/experience/{exp_id}/edit")
@login_required
async def experience_edit_submit(
    request: Request,
    exp_id: str,
    title: str = Form(...),
    company: str = Form(...),
    location: str = Form(''),
    start_date: str = Form(...),
    end_date: str = Form(''),
    is_current: bool = Form(False),
    description: str = Form('')
):
    """Submit experience update."""
    access_token = get_access_token(request)

    data = {
        'title': title,
        'company': company,
        'location': location,
        'start_date': start_date,
        'end_date': end_date if not is_current else None,
        'is_current': is_current,
        'description': description
    }

    result, status = await api_client.update_experience(access_token, exp_id, data)

    if status == 200:
        return RedirectResponse(url='/profile/edit', status_code=302)
    else:
        return templates.TemplateResponse("profile/experience_form.html", template_context(
            request,
            page_title="Edit Work Experience",
            error=result.get('error', 'Failed to update experience'),
            experience=data
        ))


# =============================================================================
# EDUCATION ROUTES
# =============================================================================

@router.get("/profile/education/add", response_class=HTMLResponse)
@login_required
async def education_add_page(request: Request):
    """Add education form."""
    return templates.TemplateResponse("profile/education_form.html", template_context(
        request,
        page_title="Add Education",
        education=None
    ))


@router.post("/profile/education/add")
@login_required
async def education_add_submit(
    request: Request,
    institution: str = Form(...),
    degree: str = Form(...),
    field_of_study: str = Form(...),
    start_year: int = Form(...),
    end_year: int = Form(None),
    is_current: bool = Form(False),
    grade: str = Form(''),
    description: str = Form('')
):
    """Submit new education."""
    access_token = get_access_token(request)

    data = {
        'institution': institution,
        'degree': degree,
        'field_of_study': field_of_study,
        'start_year': start_year,
        'end_year': end_year if not is_current else None,
        'is_current': is_current,
        'grade': grade,
        'description': description
    }

    result, status = await api_client.add_education(access_token, data)

    if status == 201:
        return RedirectResponse(url='/profile/edit', status_code=302)
    else:
        return templates.TemplateResponse("profile/education_form.html", template_context(
            request,
            page_title="Add Education",
            error=result.get('error', 'Failed to add education'),
            education=data
        ))


@router.get("/profile/education/{edu_id}/edit", response_class=HTMLResponse)
@login_required
async def education_edit_page(request: Request, edu_id: str):
    """Edit education form."""
    access_token = get_access_token(request)
    education_list = await api_client.get_education(access_token)
    education = next((e for e in education_list if str(e.get('id')) == edu_id), None)

    if not education:
        return RedirectResponse(url='/profile/edit', status_code=302)

    return templates.TemplateResponse("profile/education_form.html", template_context(
        request,
        page_title="Edit Education",
        education=education
    ))


@router.post("/profile/education/{edu_id}/edit")
@login_required
async def education_edit_submit(
    request: Request,
    edu_id: str,
    institution: str = Form(...),
    degree: str = Form(...),
    field_of_study: str = Form(...),
    start_year: int = Form(...),
    end_year: int = Form(None),
    is_current: bool = Form(False),
    grade: str = Form(''),
    description: str = Form('')
):
    """Submit education update."""
    access_token = get_access_token(request)

    data = {
        'institution': institution,
        'degree': degree,
        'field_of_study': field_of_study,
        'start_year': start_year,
        'end_year': end_year if not is_current else None,
        'is_current': is_current,
        'grade': grade,
        'description': description
    }

    result, status = await api_client.update_education(access_token, edu_id, data)

    if status == 200:
        return RedirectResponse(url='/profile/edit', status_code=302)
    else:
        return templates.TemplateResponse("profile/education_form.html", template_context(
            request,
            page_title="Edit Education",
            error=result.get('error', 'Failed to update education'),
            education=data
        ))


# =============================================================================
# OPPORTUNITY APPLICATION ROUTES
# =============================================================================

@router.get("/opportunities/{opportunity_id}/apply", response_class=HTMLResponse)
@login_required
async def apply_to_opportunity(request: Request, opportunity_id: str):
    """Application form."""
    access_token = get_access_token(request)

    opportunity = await api_client.get_opportunity(access_token, opportunity_id)
    if not opportunity:
        return templates.TemplateResponse("errors/404.html", template_context(
            request, page_title="Not Found"
        ), status_code=404)

    profile = await api_client.get_profile(access_token)

    return templates.TemplateResponse("opportunities/apply.html", template_context(
        request,
        page_title=f"Apply - {opportunity.get('title', 'Opportunity')}",
        opportunity=opportunity,
        profile=profile
    ))


@router.post("/opportunities/{opportunity_id}/apply")
@login_required
async def submit_application(
    request: Request,
    opportunity_id: str,
    cover_letter: str = Form(''),
    resume: UploadFile = File(None),
    answers: str = Form('{}')  # JSON string of screening question answers
):
    """Submit job application."""
    access_token = get_access_token(request)

    try:
        import json
        answers_data = json.loads(answers) if answers else {}

        application_data = {
            'opportunity_id': opportunity_id,
            'cover_letter': cover_letter,
            'answers': answers_data
        }

        # Create application
        result, status = await api_client.create_application(access_token, application_data)

        if status == 201:
            # Upload resume if provided
            if resume and resume.filename:
                # TODO: Upload resume to application
                pass

            return RedirectResponse(url='/applications?applied=1', status_code=302)
        else:
            opportunity = await api_client.get_opportunity(access_token, opportunity_id)
            return templates.TemplateResponse("opportunities/apply.html", template_context(
                request,
                page_title=f"Apply - {opportunity.get('title', 'Opportunity')}",
                opportunity=opportunity,
                error=result.get('error', 'Failed to submit application'),
                cover_letter=cover_letter
            ))

    except Exception as e:
        logger.error(f"Application submission error: {e}")
        return RedirectResponse(url=f'/opportunities/{opportunity_id}/apply?error=1', status_code=302)


# =============================================================================
# SETTINGS ROUTES
# =============================================================================

@router.post("/settings/password")
@login_required
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...)
):
    """Change password."""
    access_token = get_access_token(request)

    if new_password != confirm_password:
        return templates.TemplateResponse("settings/security.html", template_context(
            request,
            page_title="Security Settings",
            error="New passwords do not match"
        ))

    result, status = await api_client.change_password(access_token, current_password, new_password)

    if status == 200:
        return RedirectResponse(url='/settings/security?success=1', status_code=302)
    else:
        return templates.TemplateResponse("settings/security.html", template_context(
            request,
            page_title="Security Settings",
            error=result.get('error', 'Failed to change password')
        ))


@router.post("/settings/notifications")
@login_required
async def update_notification_settings(request: Request):
    """Update notification preferences."""
    access_token = get_access_token(request)
    form_data = await request.form()

    data = {
        'email_notifications': form_data.get('email_notifications') == 'on',
        'push_notifications': form_data.get('push_notifications') == 'on',
        'sms_notifications': form_data.get('sms_notifications') == 'on',
        'marketing_emails': form_data.get('marketing_emails') == 'on'
    }

    result, status = await api_client.update_privacy_settings(access_token, data)
    return RedirectResponse(url='/settings/notifications?success=1', status_code=302)


@router.post("/settings/privacy")
@login_required
async def update_privacy_settings(request: Request):
    """Update privacy settings."""
    access_token = get_access_token(request)
    form_data = await request.form()

    data = {
        'profile_visibility': form_data.get('profile_visibility', 'public'),
        'show_email': form_data.get('show_email') == 'on',
        'show_phone': form_data.get('show_phone') == 'on',
        'searchable': form_data.get('searchable') == 'on'
    }

    result, status = await api_client.update_privacy_settings(access_token, data)
    return RedirectResponse(url='/settings?success=1', status_code=302)


@router.post("/settings/delete-account")
@login_required
async def delete_account(request: Request, password: str = Form(...)):
    """Delete account."""
    access_token = get_access_token(request)

    result, status = await api_client.delete_account(access_token, password)

    if status == 200:
        request.session.clear()
        return RedirectResponse(url='/auth/login?deleted=1', status_code=302)
    else:
        return templates.TemplateResponse("settings/index.html", template_context(
            request,
            page_title="Settings",
            error=result.get('error', 'Failed to delete account')
        ))


# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Unified Portal Views
========================================
Integrated portal views for talent and organization dashboards.
All portals run on the same server, authenticated via JWT.

Full-Scale Talent Portal Features:
- Dashboard with metrics and insights
- Profile management (complete profile builder)
- Opportunities browsing and search
- Applications tracking and management
- Saved opportunities
- Messages and notifications
- Settings and preferences
- CV/Resume builder
- Interview scheduler
- Skill assessments
- Career recommendations
"""
import logging
import json
from functools import wraps
from datetime import datetime, timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.contrib.auth import get_user_model
from django.conf import settings
from django.db import models
from django.db.models import Q, Count, Avg, F
from django.utils import timezone
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError

User = get_user_model()
logger = logging.getLogger(__name__)


# =============================================================================
# AUTHENTICATION HELPERS
# =============================================================================

def get_user_from_session(request):
    """Get authenticated user from session."""
    user_id = request.session.get('user_id')
    if user_id:
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            pass
    return None


def get_user_from_token(request):
    """Get user from JWT token in Authorization header or session."""
    # Try Authorization header first
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        token_str = auth_header[7:]
        try:
            token = AccessToken(token_str)
            user_id = token.get('user_id') or token.get('sub')
            return User.objects.get(id=user_id)
        except (TokenError, User.DoesNotExist):
            pass

    # Fall back to session token
    token_str = request.session.get('access_token')
    if token_str:
        try:
            token = AccessToken(token_str)
            user_id = token.get('user_id') or token.get('sub')
            return User.objects.get(id=user_id)
        except (TokenError, User.DoesNotExist):
            pass

    return None


def portal_login_required(allowed_roles=None):
    """
    Decorator to require portal login.
    Optionally restrict to specific roles.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = get_user_from_session(request) or get_user_from_token(request)

            if not user:
                # Redirect to appropriate login page
                next_url = request.get_full_path()
                return redirect(f'/portal/login?next={next_url}')

            if not user.is_active:
                return redirect('/portal/login?error=account_inactive')

            if allowed_roles and user.role not in allowed_roles:
                return redirect('/portal/login?error=unauthorized')

            # Attach user to request
            request.portal_user = user
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def talent_required(view_func):
    """Decorator for talent-only views."""
    return portal_login_required(allowed_roles=['talent'])(view_func)


def employer_required(view_func):
    """Decorator for employer/org admin views."""
    return portal_login_required(allowed_roles=['employer', 'org_admin'])(view_func)


# =============================================================================
# PORTAL CONTEXT HELPER
# =============================================================================

def portal_context(request, **extra):
    """Build context for portal templates."""
    user = getattr(request, 'portal_user', None)
    return {
        'request': request,
        'user': user,
        'site_name': 'ForgeForth Africa',
        'is_talent': user and user.role == 'talent',
        'is_employer': user and user.role in ['employer', 'org_admin'],
        **extra
    }


# =============================================================================
# UNIFIED LOGIN/LOGOUT
# =============================================================================

@require_GET
def portal_login_page(request):
    """Unified portal login page."""
    if get_user_from_session(request):
        # Already logged in, redirect to appropriate dashboard
        user = get_user_from_session(request)
        if user.role in ['employer', 'org_admin']:
            return redirect('/portal/org/dashboard')
        return redirect('/portal/talent/dashboard')

    next_url = request.GET.get('next', '')
    error = request.GET.get('error', '')

    error_messages = {
        'account_inactive': 'Your account has been deactivated.',
        'unauthorized': 'You do not have permission to access that page.',
        'session_expired': 'Your session has expired. Please login again.',
        'invalid_credentials': 'Invalid email or password.',
        'not_verified': 'Please verify your email before logging in.',
    }

    return render(request, 'website/portal/login.html', {
        'page_title': 'Portal Login',
        'next_url': next_url,
        'error': error_messages.get(error, error) if error else None,
    })


@csrf_exempt
@require_POST
def portal_login_submit(request):
    """Handle portal login submission."""
    import json
    from rest_framework_simplejwt.tokens import RefreshToken

    try:
        data = json.loads(request.body)
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')

        if not email or not password:
            return JsonResponse({
                'success': False,
                'error': 'Email and password are required'
            }, status=400)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Invalid email or password'
            }, status=401)

        if not user.check_password(password):
            user.increment_failed_login()
            return JsonResponse({
                'success': False,
                'error': 'Invalid email or password'
            }, status=401)

        if not user.is_active:
            return JsonResponse({
                'success': False,
                'error': 'Your account has been deactivated'
            }, status=403)

        if not user.is_verified:
            return JsonResponse({
                'success': False,
                'error': 'Please verify your email before logging in',
                'requires_verification': True
            }, status=403)

        # Reset failed login attempts
        user.reset_failed_login()

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        # Store in session
        request.session['user_id'] = str(user.id)
        request.session['access_token'] = access_token
        request.session['refresh_token'] = str(refresh)
        request.session['user_role'] = user.role

        # Determine redirect URL
        if user.role in ['employer', 'org_admin']:
            redirect_url = '/portal/org/dashboard'
        else:
            redirect_url = '/portal/talent/dashboard'

        next_url = data.get('next_url', '')
        if next_url and next_url.startswith('/portal/'):
            redirect_url = next_url

        logger.info(f"Portal login successful: {email}")

        return JsonResponse({
            'success': True,
            'message': 'Login successful',
            'redirect_url': redirect_url,
            'user': {
                'id': str(user.id),
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role': user.role,
            },
            'tokens': {
                'access': access_token,
                'refresh': str(refresh),
            }
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid request data'
        }, status=400)
    except Exception as e:
        logger.error(f"Portal login error: {e}")
        return JsonResponse({
            'success': False,
            'error': 'An error occurred. Please try again.'
        }, status=500)


def portal_logout(request):
    """Handle portal logout."""
    request.session.flush()
    return redirect('/portal/login')


# =============================================================================
# TALENT PORTAL VIEWS
# =============================================================================

@talent_required
def talent_dashboard(request):
    """Talent dashboard page with comprehensive metrics and insights."""
    from profiles.models import TalentProfile, TalentSkill
    from applications.models import Application, SavedOpportunity
    from matching.models import Recommendation
    from organizations.models import Opportunity
    from communications.models import Notification, Message

    user = request.portal_user

    # Get or create profile
    profile, _ = TalentProfile.objects.get_or_create(user=user)

    # Get application stats
    app_stats = get_application_stats(user)

    # Get recent applications with full details
    recent_applications = Application.objects.filter(
        applicant=user
    ).select_related('opportunity', 'opportunity__organization').order_by('-created_at')[:5]

    # Get recommendations (not dismissed and not expired)
    recommendations = Recommendation.objects.filter(
        user=user,
        is_dismissed=False
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
    ).order_by('-relevance_score')[:6]

    # Get saved opportunities
    saved_opportunities = SavedOpportunity.objects.filter(
        user=user
    ).select_related('opportunity', 'opportunity__organization').order_by('-created_at')[:5]

    # Get upcoming interviews (applications with interview status and scheduled date)
    upcoming_interviews = Application.objects.filter(
        applicant=user,
        status='interview'
    ).select_related('opportunity', 'opportunity__organization').order_by('updated_at')[:3]

    # Get recent notifications
    recent_notifications = Notification.objects.filter(
        recipient=user
    ).order_by('-created_at')[:5]

    # Get unread counts
    unread_notifications = Notification.objects.filter(recipient=user, is_read=False).count()
    unread_messages = Message.objects.filter(recipient=user, is_read=False).count()
    saved_count = SavedOpportunity.objects.filter(user=user).count()

    # Get profile completion details
    profile_completion = get_profile_completion_details(profile)

    # Get matching opportunities based on skills
    user_skills = TalentSkill.objects.filter(profile=profile).values_list('skill__name', flat=True)
    matching_opportunities = Opportunity.objects.filter(
        status='active'
    ).order_by('-created_at')[:10]  # Will be filtered by ML engine in production

    # Get activity timeline
    activity_timeline = []

    # Add applications to timeline
    for app in Application.objects.filter(applicant=user).order_by('-created_at')[:10]:
        activity_timeline.append({
            'type': 'application',
            'title': f'Applied to {app.opportunity.title}',
            'subtitle': app.opportunity.organization.name if app.opportunity.organization else '',
            'date': app.created_at,
            'status': app.status,
            'icon': 'document',
        })

    # Add saves to timeline
    for save in SavedOpportunity.objects.filter(user=user).order_by('-created_at')[:5]:
        activity_timeline.append({
            'type': 'save',
            'title': f'Saved {save.opportunity.title}',
            'subtitle': save.opportunity.organization.name if save.opportunity.organization else '',
            'date': save.created_at,
            'icon': 'bookmark',
        })

    # Sort by date and take top 10
    activity_timeline = sorted(activity_timeline, key=lambda x: x['date'], reverse=True)[:10]

    # Calculate application response rate
    total_apps = app_stats['total']
    responded_apps = app_stats['interview'] + app_stats['offered'] + app_stats['rejected']
    response_rate = int((responded_apps / total_apps * 100)) if total_apps > 0 else 0

    return render(request, 'website/portal/talent/dashboard.html', portal_context(
        request,
        page_title='Dashboard',
        profile=profile,
        profile_completion=profile_completion,
        recent_applications=recent_applications,
        recommendations=recommendations,
        saved_opportunities=saved_opportunities,
        upcoming_interviews=upcoming_interviews,
        recent_notifications=recent_notifications,
        matching_opportunities=matching_opportunities,
        activity_timeline=activity_timeline,
        unread_notifications=unread_notifications,
        unread_messages=unread_messages,
        saved_count=saved_count,
        response_rate=response_rate,
        stats=app_stats,
        user_skills=list(user_skills),
    ))


@talent_required
def talent_profile(request):
    """Talent profile management page with full profile builder."""
    from profiles.models import TalentProfile, Education, WorkExperience, Skill, TalentSkill

    user = request.portal_user
    profile, _ = TalentProfile.objects.get_or_create(user=user)

    education = Education.objects.filter(profile=profile).order_by('-end_date')
    experience = WorkExperience.objects.filter(profile=profile).order_by('-end_date')
    skills = TalentSkill.objects.filter(profile=profile).select_related('skill')
    all_skills = Skill.objects.all().order_by('name')

    # Get detailed profile completion
    profile_completion = get_profile_completion_details(profile)

    return render(request, 'website/portal/talent/profile_new.html', portal_context(
        request,
        page_title='My Profile',
        profile=profile,
        education=education,
        experience=experience,
        skills=skills,
        all_skills=all_skills,
        profile_completion=profile_completion,
    ))


@talent_required
def talent_opportunities(request):
    """Browse opportunities page."""
    from organizations.models import Opportunity

    # Get filters from query params
    search = request.GET.get('q', '')
    category = request.GET.get('category', '')
    location = request.GET.get('location', '')
    opportunity_type = request.GET.get('type', '')

    opportunities = Opportunity.objects.filter(
        status='active'
    ).select_related('organization')

    if search:
        opportunities = opportunities.filter(
            title__icontains=search
        ) | opportunities.filter(
            description__icontains=search
        )

    if category:
        opportunities = opportunities.filter(category=category)

    if location:
        opportunities = opportunities.filter(location__icontains=location)

    if opportunity_type:
        opportunities = opportunities.filter(opportunity_type=opportunity_type)

    opportunities = opportunities.order_by('-created_at')[:50]

    return render(request, 'website/portal/talent/opportunities.html', portal_context(
        request,
        page_title='Opportunities',
        opportunities=opportunities,
        search=search,
        filters={'category': category, 'location': location, 'type': opportunity_type}
    ))


@talent_required
def talent_applications(request):
    """My applications page."""
    from applications.models import Application

    user = request.portal_user
    status_filter = request.GET.get('status', '')

    applications = Application.objects.filter(
        applicant=user
    ).select_related('opportunity', 'opportunity__organization')

    if status_filter:
        applications = applications.filter(status=status_filter)

    applications = applications.order_by('-created_at')

    return render(request, 'website/portal/talent/applications.html', portal_context(
        request,
        page_title='My Applications',
        applications=applications,
        status_filter=status_filter,
    ))


@talent_required
def talent_settings(request):
    """Talent settings page."""
    from profiles.models import TalentProfile

    user = request.portal_user
    profile, _ = TalentProfile.objects.get_or_create(user=user)

    return render(request, 'website/portal/talent/settings.html', portal_context(
        request,
        page_title='Settings',
        profile=profile,
    ))


@talent_required
def talent_help(request):
    """Help and support page."""
    return render(request, 'website/portal/talent/help.html', portal_context(
        request,
        page_title='Help & Support',
    ))


@talent_required
def talent_resume(request):
    """Resume builder page with AI-powered features."""
    from profiles.models import TalentProfile, Education, WorkExperience, TalentSkill, Certification
    from website.services.resume_builder import ResumeBuilder, ATSOptimizer, ContentSuggestionEngine

    user = request.portal_user
    profile, _ = TalentProfile.objects.get_or_create(user=user)

    education = Education.objects.filter(profile=profile).order_by('-end_date')
    experience = WorkExperience.objects.filter(profile=profile).order_by('-end_date')
    skills = TalentSkill.objects.filter(profile=profile).select_related('skill')
    certifications = Certification.objects.filter(profile=profile).order_by('-issue_date')

    # Initialize resume builder and load from profile
    resume_builder = ResumeBuilder(user)
    resume_builder.load_from_profile(profile)

    # Get ATS score and suggestions
    ats_analysis = resume_builder.get_ats_score()
    content_suggestions = resume_builder.get_suggestions()

    # Available templates
    templates = [
        {'id': 'professional', 'name': 'Professional', 'desc': 'Classic clean design', 'preview': '/static/images/resume/professional.png'},
        {'id': 'modern', 'name': 'Modern', 'desc': 'Contemporary sleek layout', 'preview': '/static/images/resume/modern.png'},
        {'id': 'minimal', 'name': 'Minimal', 'desc': 'Simple and elegant', 'preview': '/static/images/resume/minimal.png'},
        {'id': 'creative', 'name': 'Creative', 'desc': 'Stand out design', 'preview': '/static/images/resume/creative.png'},
        {'id': 'executive', 'name': 'Executive', 'desc': 'Senior professional', 'preview': '/static/images/resume/executive.png'},
        {'id': 'tech', 'name': 'Tech', 'desc': 'Tech-focused layout', 'preview': '/static/images/resume/tech.png'},
    ]

    return render(request, 'website/portal/talent/resume.html', portal_context(
        request,
        page_title='Resume Builder',
        profile=profile,
        education=education,
        experience=experience,
        skills=skills,
        certifications=certifications,
        ats_score=ats_analysis.get('score', 0),
        ats_grade=ats_analysis.get('grade', 'N/A'),
        ats_grade_label=ats_analysis.get('grade_label', 'Unknown'),
        ats_issues=ats_analysis.get('issues', []),
        ats_suggestions=ats_analysis.get('suggestions', []),
        ats_strengths=ats_analysis.get('strengths', []),
        content_suggestions=content_suggestions,
        templates=templates,
        resume_data=resume_builder.to_dict(),
    ))


@talent_required
def talent_interviews(request):
    """Interviews page - upcoming and past interviews."""
    from applications.models import Application, Interview

    user = request.portal_user

    # Get applications with interview status
    upcoming_interviews = Application.objects.filter(
        applicant=user,
        status='interview'
    ).select_related('opportunity', 'opportunity__organization').order_by('updated_at')

    # Get completed interviews
    past_interviews = Application.objects.filter(
        applicant=user,
        status__in=['offered', 'rejected', 'hired']
    ).select_related('opportunity', 'opportunity__organization').order_by('-updated_at')[:10]

    return render(request, 'website/portal/talent/interviews.html', portal_context(
        request,
        page_title='Interviews',
        upcoming_interviews=upcoming_interviews,
        past_interviews=past_interviews,
    ))


@talent_required
def talent_recommendations(request):
    """AI-powered job recommendations."""
    from matching.models import Recommendation
    from organizations.models import Opportunity

    user = request.portal_user

    # Get active recommendations
    recommendations = Recommendation.objects.filter(
        user=user,
        is_dismissed=False
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
    ).order_by('-relevance_score')

    # Paginate
    paginator = Paginator(recommendations, 12)
    page = request.GET.get('page', 1)

    try:
        recommendation_list = paginator.page(page)
    except PageNotAnInteger:
        recommendation_list = paginator.page(1)
    except EmptyPage:
        recommendation_list = paginator.page(paginator.num_pages)

    return render(request, 'website/portal/talent/recommendations.html', portal_context(
        request,
        page_title='AI Recommendations',
        recommendations=recommendation_list,
        total_count=paginator.count,
    ))


@talent_required
def talent_skills(request):
    """Skill assessment and management page."""
    from profiles.models import TalentProfile, Skill, TalentSkill
    from intelligence.models import SkillTaxonomy

    user = request.portal_user
    profile, _ = TalentProfile.objects.get_or_create(user=user)

    # Get user's skills with proficiency levels
    user_skills = TalentSkill.objects.filter(profile=profile).select_related('skill').order_by('-level')

    # Get skill categories for exploration
    skill_categories = SkillTaxonomy.objects.filter(parent__isnull=True).order_by('name')

    # Get recommended skills based on profile
    recommended_skills = Skill.objects.exclude(
        id__in=user_skills.values_list('skill_id', flat=True)
    ).order_by('?')[:12]

    return render(request, 'website/portal/talent/skills.html', portal_context(
        request,
        page_title='Skill Assessment',
        profile=profile,
        user_skills=user_skills,
        skill_categories=skill_categories,
        recommended_skills=recommended_skills,
    ))


@talent_required
def talent_certifications(request):
    """Certifications page."""
    from profiles.models import TalentProfile, Certification

    user = request.portal_user
    profile, _ = TalentProfile.objects.get_or_create(user=user)

    certifications = Certification.objects.filter(profile=profile).order_by('-issue_date')

    return render(request, 'website/portal/talent/certifications.html', portal_context(
        request,
        page_title='Certifications',
        profile=profile,
        certifications=certifications,
    ))


@talent_required
def talent_learning(request):
    """Learning hub - courses and resources."""
    return render(request, 'website/portal/talent/learning.html', portal_context(
        request,
        page_title='Learning Hub',
    ))


@talent_required
def talent_documents(request):
    """My Documents - comprehensive document management system."""
    from media.models import MediaFile, Document

    user = request.portal_user

    # Get all documents for the user
    documents = Document.objects.filter(owner=user).select_related('media_file').order_by('-created_at')

    # Group documents by type
    resumes = documents.filter(media_file__file_type='cv')
    cover_letters = documents.filter(media_file__file_type='cover_letter')
    certificates = documents.filter(media_file__file_type='certificate')
    portfolios = documents.filter(media_file__file_type='portfolio')
    other_docs = documents.filter(media_file__file_type='other')

    # Get primary resume
    primary_resume = resumes.filter(is_primary=True).first()

    # Stats
    total_documents = documents.count()
    total_size = sum(doc.media_file.file_size for doc in documents if doc.media_file)

    # Storage limit (50MB per user for MVP)
    storage_limit = 50 * 1024 * 1024  # 50MB in bytes
    storage_used_percent = min(int((total_size / storage_limit) * 100), 100) if storage_limit > 0 else 0

    # Recent documents (last 5)
    recent_documents = documents[:5]

    # Documents pending processing
    pending_docs = documents.filter(media_file__status='pending')
    processing_docs = documents.filter(media_file__status='processing')

    # Document type counts
    type_counts = {
        'cv': resumes.count(),
        'cover_letter': cover_letters.count(),
        'certificate': certificates.count(),
        'portfolio': portfolios.count(),
        'other': other_docs.count(),
    }

    # Document types for upload dropdown
    document_types = [
        ('cv', 'Resume / CV', 'Primary document for job applications'),
        ('cover_letter', 'Cover Letter', 'Personalized cover letters'),
        ('certificate', 'Certificate', 'Professional certifications and awards'),
        ('portfolio', 'Portfolio Item', 'Work samples and projects'),
        ('other', 'Other Document', 'Miscellaneous documents'),
    ]

    # Allowed file extensions
    allowed_extensions = {
        'cv': ['.pdf', '.doc', '.docx'],
        'cover_letter': ['.pdf', '.doc', '.docx'],
        'certificate': ['.pdf', '.jpg', '.jpeg', '.png'],
        'portfolio': ['.pdf', '.jpg', '.jpeg', '.png', '.zip'],
        'other': ['.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png', '.txt'],
    }

    # Max file sizes
    max_file_sizes = {
        'cv': 5 * 1024 * 1024,  # 5MB
        'cover_letter': 2 * 1024 * 1024,  # 2MB
        'certificate': 5 * 1024 * 1024,  # 5MB
        'portfolio': 10 * 1024 * 1024,  # 10MB
        'other': 5 * 1024 * 1024,  # 5MB
    }

    return render(request, 'website/portal/talent/documents.html', portal_context(
        request,
        page_title='My Documents',
        documents=documents,
        resumes=resumes,
        cover_letters=cover_letters,
        certificates=certificates,
        portfolios=portfolios,
        other_docs=other_docs,
        primary_resume=primary_resume,
        recent_documents=recent_documents,
        pending_docs=pending_docs,
        processing_docs=processing_docs,
        total_documents=total_documents,
        total_size=total_size,
        storage_limit=storage_limit,
        storage_used_percent=storage_used_percent,
        type_counts=type_counts,
        document_types=document_types,
        allowed_extensions=allowed_extensions,
        max_file_sizes=max_file_sizes,
    ))


@talent_required
def talent_progress(request):
    """My Progress - track career progress and milestones."""
    from profiles.models import TalentProfile, TalentSkill
    from applications.models import Application
    from media.models import Document

    user = request.portal_user
    profile, _ = TalentProfile.objects.get_or_create(user=user)

    # Get stats
    applications_count = Application.objects.filter(applicant=user).count()
    applications_this_month = Application.objects.filter(
        applicant=user,
        created_at__month=timezone.now().month
    ).count()
    skills_count = TalentSkill.objects.filter(profile=profile).count()
    interviews_count = Application.objects.filter(
        applicant=user,
        status__in=['interview', 'interview_scheduled']
    ).count()
    has_resume = Document.objects.filter(owner=user, media_file__file_type='cv').exists()
    completion = get_profile_completion_details(profile)

    return render(request, 'website/portal/talent/progress.html', portal_context(
        request,
        page_title='My Progress',
        profile_completion=completion.get('percentage', 0),
        applications_count=applications_count,
        applications_this_month=applications_this_month,
        skills_count=skills_count,
        interviews_count=interviews_count,
        has_resume=has_resume,
    ))


@talent_required
def talent_goals(request):
    """My Goals - set and track career goals."""
    # Goals feature - placeholder data for now
    return render(request, 'website/portal/talent/goals.html', portal_context(
        request,
        page_title='My Goals',
        total_goals=0,
        completed_goals=0,
        in_progress_goals=0,
        upcoming_goals=0,
        short_term_goals=[],
        long_term_goals=[],
    ))


@talent_required
def talent_activities(request):
    """Activities - view activity timeline and history."""
    # Activities feature - placeholder data for now
    return render(request, 'website/portal/talent/activities.html', portal_context(
        request,
        page_title='Activities',
        activities=[],
        has_more=False,
        application_activities=0,
        profile_activities=0,
        interview_activities=0,
        skill_activities=0,
    ))


@talent_required
def talent_contributions(request):
    """My Contributions - track giving back to the community."""
    # Contributions feature - placeholder data for now
    return render(request, 'website/portal/talent/contributions.html', portal_context(
        request,
        page_title='My Contributions',
        impact_score=0,
        mentees_helped=0,
        hours_contributed=0,
        resources_shared=0,
        help_count=0,
        has_mentor_badge=False,
    ))


@talent_required
def talent_skillsets(request):
    """My Skills - manage and showcase your skill sets."""
    from profiles.models import TalentProfile, Skill, TalentSkill

    user = request.portal_user
    profile, _ = TalentProfile.objects.get_or_create(user=user)

    # Get user's skills
    user_skills = TalentSkill.objects.filter(profile=profile).select_related('skill').order_by('-level')

    # Get all available skills for adding
    all_skills = Skill.objects.exclude(
        id__in=user_skills.values_list('skill_id', flat=True)
    ).order_by('name')[:50]

    return render(request, 'website/portal/talent/skillsets.html', portal_context(
        request,
        page_title='My Skills',
        profile=profile,
        user_skills=user_skills,
        all_skills=all_skills,
    ))


@talent_required
def talent_connections(request):
    """Professional network connections."""
    return render(request, 'website/portal/talent/connections.html', portal_context(
        request,
        page_title='My Network',
    ))


@talent_required
def talent_mentors(request):
    """Find and connect with mentors."""
    return render(request, 'website/portal/talent/mentors.html', portal_context(
        request,
        page_title='Find Mentors',
    ))


@talent_required
def talent_become_mentor(request):
    """Become a mentor - give back to the community."""
    return render(request, 'website/portal/talent/become_mentor.html', portal_context(
        request,
        page_title='Become a Mentor',
    ))


@talent_required
def talent_saved(request):
    """Saved opportunities page."""
    from applications.models import SavedOpportunity

    user = request.portal_user

    saved = SavedOpportunity.objects.filter(
        user=user
    ).select_related('opportunity', 'opportunity__organization').order_by('-created_at')

    # Paginate
    paginator = Paginator(saved, 12)
    page = request.GET.get('page', 1)

    try:
        saved_opportunities = paginator.page(page)
    except PageNotAnInteger:
        saved_opportunities = paginator.page(1)
    except EmptyPage:
        saved_opportunities = paginator.page(paginator.num_pages)

    return render(request, 'website/portal/talent/saved.html', portal_context(
        request,
        page_title='Saved Opportunities',
        saved_opportunities=saved_opportunities,
        total_count=paginator.count,
    ))


@talent_required
def talent_messages(request):
    """Messages inbox page."""
    from communications.models import Message

    user = request.portal_user
    folder = request.GET.get('folder', 'inbox')

    if folder == 'sent':
        messages = Message.objects.filter(sender=user).order_by('-created_at')
    else:
        messages = Message.objects.filter(recipient=user).order_by('-created_at')

    # Paginate
    paginator = Paginator(messages, 20)
    page = request.GET.get('page', 1)

    try:
        message_list = paginator.page(page)
    except PageNotAnInteger:
        message_list = paginator.page(1)
    except EmptyPage:
        message_list = paginator.page(paginator.num_pages)

    unread_count = Message.objects.filter(recipient=user, is_read=False).count()

    return render(request, 'website/portal/talent/messages.html', portal_context(
        request,
        page_title='Messages',
        messages=message_list,
        folder=folder,
        unread_count=unread_count,
    ))


@talent_required
def talent_notifications(request):
    """Notifications page."""
    from communications.models import Notification

    user = request.portal_user

    notifications = Notification.objects.filter(recipient=user).order_by('-created_at')

    # Mark as read option
    if request.GET.get('mark_all_read'):
        notifications.filter(is_read=False).update(is_read=True)
        return redirect('/portal/talent/notifications/')

    # Paginate
    paginator = Paginator(notifications, 20)
    page = request.GET.get('page', 1)

    try:
        notification_list = paginator.page(page)
    except PageNotAnInteger:
        notification_list = paginator.page(1)
    except EmptyPage:
        notification_list = paginator.page(paginator.num_pages)

    unread_count = Notification.objects.filter(recipient=user, is_read=False).count()

    return render(request, 'website/portal/talent/notifications.html', portal_context(
        request,
        page_title='Notifications',
        notifications=notification_list,
        unread_count=unread_count,
    ))


@talent_required
def talent_opportunity_detail(request, slug):
    """View single opportunity details."""
    from organizations.models import Opportunity
    from applications.models import Application, SavedOpportunity

    user = request.portal_user
    opportunity = get_object_or_404(Opportunity, slug=slug, status='active')

    # Check if already applied
    has_applied = Application.objects.filter(applicant=user, opportunity=opportunity).exists()
    application = Application.objects.filter(applicant=user, opportunity=opportunity).first()

    # Check if saved
    is_saved = SavedOpportunity.objects.filter(user=user, opportunity=opportunity).exists()

    # Get similar opportunities
    similar = Opportunity.objects.filter(
        status='active',
        category=opportunity.category
    ).exclude(id=opportunity.id).order_by('-created_at')[:6]

    # Increment view count
    opportunity.views_count = F('views_count') + 1
    opportunity.save(update_fields=['views_count'])

    return render(request, 'website/portal/talent/opportunity_detail.html', portal_context(
        request,
        page_title=opportunity.title,
        opportunity=opportunity,
        has_applied=has_applied,
        application=application,
        is_saved=is_saved,
        similar_opportunities=similar,
    ))


@talent_required
@require_POST
def talent_apply_opportunity(request, opportunity_id):
    """Apply to an opportunity."""
    from organizations.models import Opportunity
    from applications.models import Application
    from profiles.models import TalentProfile

    user = request.portal_user

    try:
        opportunity = Opportunity.objects.get(id=opportunity_id, status='active')
    except Opportunity.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Opportunity not found'}, status=404)

    # Check if already applied
    if Application.objects.filter(applicant=user, opportunity=opportunity).exists():
        return JsonResponse({'success': False, 'error': 'You have already applied to this opportunity'}, status=400)

    # Get cover letter from request
    data = json.loads(request.body) if request.body else {}
    cover_letter = data.get('cover_letter', '')

    # Create application
    application = Application.objects.create(
        applicant=user,
        opportunity=opportunity,
        cover_letter=cover_letter,
        status='pending'
    )

    # Update application count on opportunity
    opportunity.applications_count = F('applications_count') + 1
    opportunity.save(update_fields=['applications_count'])

    logger.info(f"New application: {user.email} -> {opportunity.title}")

    return JsonResponse({
        'success': True,
        'message': 'Application submitted successfully',
        'application_id': str(application.id)
    })


@talent_required
@require_POST
def talent_save_opportunity(request, opportunity_id):
    """Save/unsave an opportunity."""
    from organizations.models import Opportunity
    from applications.models import SavedOpportunity

    user = request.portal_user

    try:
        opportunity = Opportunity.objects.get(id=opportunity_id)
    except Opportunity.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Opportunity not found'}, status=404)

    # Toggle save
    saved, created = SavedOpportunity.objects.get_or_create(
        user=user,
        opportunity=opportunity
    )

    if not created:
        saved.delete()
        return JsonResponse({'success': True, 'saved': False, 'message': 'Opportunity removed from saved'})

    return JsonResponse({'success': True, 'saved': True, 'message': 'Opportunity saved'})


@talent_required
@require_POST
def talent_withdraw_application(request, application_id):
    """Withdraw an application."""
    from applications.models import Application

    user = request.portal_user

    try:
        application = Application.objects.get(id=application_id, applicant=user)
    except Application.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Application not found'}, status=404)

    if application.status in ['offered', 'hired']:
        return JsonResponse({'success': False, 'error': 'Cannot withdraw this application'}, status=400)

    application.status = 'withdrawn'
    application.save(update_fields=['status', 'updated_at'])

    return JsonResponse({'success': True, 'message': 'Application withdrawn'})


@talent_required
def talent_application_detail(request, application_id):
    """View single application details."""
    from applications.models import Application, ApplicationStatusHistory

    user = request.portal_user
    application = get_object_or_404(Application, id=application_id, applicant=user)

    # Get status history
    status_history = ApplicationStatusHistory.objects.filter(
        application=application
    ).order_by('-changed_at')

    return render(request, 'website/portal/talent/application_detail.html', portal_context(
        request,
        page_title=f'Application - {application.opportunity.title}',
        application=application,
        status_history=status_history,
    ))


# =============================================================================
# PROFILE API ENDPOINTS
# =============================================================================

@talent_required
@require_POST
@csrf_exempt
def talent_update_profile(request):
    """Update profile information."""
    from profiles.models import TalentProfile

    user = request.portal_user
    profile, _ = TalentProfile.objects.get_or_create(user=user)

    try:
        data = json.loads(request.body)

        # Update allowed fields
        allowed_fields = [
            'headline', 'bio', 'phone_number', 'country', 'city',
            'state_province', 'linkedin_url', 'github_url', 'portfolio_url',
            'website', 'employment_status', 'availability', 'remote_preference',
            'willing_to_relocate', 'expected_salary_min', 'expected_salary_max',
            'salary_currency', 'nationality', 'gender'
        ]

        for field in allowed_fields:
            if field in data:
                setattr(profile, field, data[field])

        profile.save()

        # Update user's first/last name if provided
        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']
        user.save(update_fields=['first_name', 'last_name'])

        return JsonResponse({
            'success': True,
            'message': 'Profile updated successfully',
            'profile_completion': calculate_profile_completion(profile)
        })

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid data'}, status=400)
    except Exception as e:
        logger.error(f"Profile update error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@talent_required
@require_POST
@csrf_exempt
def talent_add_education(request):
    """Add education entry."""
    from profiles.models import TalentProfile, Education

    user = request.portal_user
    profile, _ = TalentProfile.objects.get_or_create(user=user)

    try:
        data = json.loads(request.body)

        education = Education.objects.create(
            profile=profile,
            institution=data.get('institution', ''),
            degree=data.get('degree', ''),
            field_of_study=data.get('field_of_study', ''),
            start_date=data.get('start_date'),
            end_date=data.get('end_date'),
            is_current=data.get('is_current', False),
            description=data.get('description', ''),
            grade=data.get('grade', '')
        )

        return JsonResponse({
            'success': True,
            'message': 'Education added',
            'id': str(education.id)
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@talent_required
@require_POST
@csrf_exempt
def talent_add_experience(request):
    """Add work experience entry."""
    from profiles.models import TalentProfile, WorkExperience

    user = request.portal_user
    profile, _ = TalentProfile.objects.get_or_create(user=user)

    try:
        data = json.loads(request.body)

        experience = WorkExperience.objects.create(
            profile=profile,
            company=data.get('company', ''),
            job_title=data.get('job_title', ''),
            employment_type=data.get('employment_type', 'full_time'),
            location=data.get('location', ''),
            start_date=data.get('start_date'),
            end_date=data.get('end_date'),
            is_current=data.get('is_current', False),
            description=data.get('description', ''),
        )

        return JsonResponse({
            'success': True,
            'message': 'Experience added',
            'id': str(experience.id)
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@talent_required
@require_POST
@csrf_exempt
def talent_add_skill(request):
    """Add skill to profile."""
    from profiles.models import TalentProfile, Skill, TalentSkill

    user = request.portal_user
    profile, _ = TalentProfile.objects.get_or_create(user=user)

    try:
        data = json.loads(request.body)
        skill_name = data.get('skill_name', '').strip()
        level = data.get('level', data.get('proficiency', 'intermediate'))

        if not skill_name:
            return JsonResponse({'success': False, 'error': 'Skill name required'}, status=400)

        # Get or create skill
        skill, _ = Skill.objects.get_or_create(
            name__iexact=skill_name,
            defaults={'name': skill_name}
        )

        # Add to profile
        talent_skill, created = TalentSkill.objects.get_or_create(
            profile=profile,
            skill=skill,
            defaults={'level': level}
        )

        if not created:
            talent_skill.level = level
            talent_skill.save()

        return JsonResponse({
            'success': True,
            'message': 'Skill added',
            'id': str(talent_skill.id)
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@talent_required
@require_POST
@csrf_exempt
def talent_remove_skill(request, skill_id):
    """Remove skill from profile."""
    from profiles.models import TalentSkill

    user = request.portal_user

    try:
        talent_skill = TalentSkill.objects.get(id=skill_id, profile__user=user)
        talent_skill.delete()
        return JsonResponse({'success': True, 'message': 'Skill removed'})
    except TalentSkill.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Skill not found'}, status=404)


@talent_required
@require_POST
@csrf_exempt
def talent_delete_education(request, education_id):
    """Delete education entry."""
    from profiles.models import Education

    user = request.portal_user

    try:
        education = Education.objects.get(id=education_id, profile__user=user)
        education.delete()
        return JsonResponse({'success': True, 'message': 'Education deleted'})
    except Education.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Education not found'}, status=404)


@talent_required
@require_POST
@csrf_exempt
def talent_delete_experience(request, experience_id):
    """Delete experience entry."""
    from profiles.models import WorkExperience

    user = request.portal_user

    try:
        experience = WorkExperience.objects.get(id=experience_id, profile__user=user)
        experience.delete()
        return JsonResponse({'success': True, 'message': 'Experience deleted'})
    except WorkExperience.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Experience not found'}, status=404)


# =============================================================================
# DOCUMENT API ENDPOINTS
# =============================================================================

@talent_required
@require_POST
@csrf_exempt
def talent_upload_document(request):
    """Upload a new document via centralized storage service."""
    from media.models import MediaFile, Document
    from storage.services import store_file, FileCategory, get_storage_service
    import os

    user = request.portal_user

    try:
        if 'file' not in request.FILES:
            return JsonResponse({'success': False, 'error': 'No file provided'}, status=400)

        uploaded_file = request.FILES['file']
        file_type = request.POST.get('file_type', 'other')
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        is_primary = request.POST.get('is_primary', 'false').lower() == 'true'

        # Validate file type
        valid_types = ['cv', 'cover_letter', 'certificate', 'portfolio', 'other']
        if file_type not in valid_types:
            return JsonResponse({'success': False, 'error': 'Invalid file type'}, status=400)

        # Get file extension
        original_filename = uploaded_file.name
        ext = os.path.splitext(original_filename)[1].lower()

        # Validate extension based on type
        allowed_extensions = {
            'cv': ['.pdf', '.doc', '.docx'],
            'cover_letter': ['.pdf', '.doc', '.docx'],
            'certificate': ['.pdf', '.jpg', '.jpeg', '.png'],
            'portfolio': ['.pdf', '.jpg', '.jpeg', '.png', '.zip'],
            'other': ['.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png', '.txt'],
        }

        if ext not in allowed_extensions.get(file_type, []):
            return JsonResponse({
                'success': False,
                'error': f'Invalid file extension. Allowed: {", ".join(allowed_extensions[file_type])}'
            }, status=400)

        # Validate file size
        max_sizes = {
            'cv': 5 * 1024 * 1024,
            'cover_letter': 2 * 1024 * 1024,
            'certificate': 5 * 1024 * 1024,
            'portfolio': 10 * 1024 * 1024,
            'other': 5 * 1024 * 1024,
        }

        if uploaded_file.size > max_sizes.get(file_type, 5 * 1024 * 1024):
            max_mb = max_sizes[file_type] / (1024 * 1024)
            return JsonResponse({
                'success': False,
                'error': f'File too large. Maximum size: {max_mb}MB'
            }, status=400)

        # Map file_type to storage FileCategory
        type_to_category = {
            'cv': FileCategory.RESUME,
            'cover_letter': FileCategory.COVER_LETTER,
            'certificate': FileCategory.CERTIFICATE,
            'portfolio': FileCategory.PORTFOLIO,
            'other': FileCategory.OTHER,
        }
        storage_category = type_to_category.get(file_type, FileCategory.OTHER)

        # Use storage service to store the file
        storage_result = store_file(
            data=uploaded_file,
            filename=original_filename,
            category=storage_category,
            owner_id=str(user.id),
            owner_type='user',
            related_entity_type='document',
            description=description,
            metadata={
                'file_type': file_type,
                'is_primary': is_primary,
                'title': title or original_filename,
            },
            request_context={
                'user_id': str(user.id),
                'ip_address': request.META.get('REMOTE_ADDR'),
            }
        )

        if not storage_result.get('success'):
            return JsonResponse({
                'success': False,
                'error': storage_result.get('error', 'Storage failed')
            }, status=400)

        # Create MediaFile record linked to storage
        media_file = MediaFile.objects.create(
            owner=user,
            file_type=file_type,
            status='ready',
            original_filename=original_filename,
            stored_filename=storage_result.get('file_id', ''),
            file_path=storage_result.get('storage_path', ''),
            file_size=uploaded_file.size,
            mime_type=storage_result.get('mime_type', uploaded_file.content_type),
            extension=ext,
            checksum_sha256=storage_result.get('checksum', ''),
            is_sanitised=True,
            metadata={
                'storage_file_id': storage_result.get('file_id'),
                'storage_category': storage_category,
            }
        )

        # If setting as primary, unset other primary documents of same type
        if is_primary and file_type == 'cv':
            Document.objects.filter(
                owner=user,
                media_file__file_type='cv',
                is_primary=True
            ).update(is_primary=False)

        # Create Document record
        document = Document.objects.create(
            media_file=media_file,
            owner=user,
            title=title or original_filename,
            description=description,
            is_primary=is_primary if file_type == 'cv' else False,
        )

        logger.info(f"Document uploaded via storage service: {user.email} -> {original_filename}")

        return JsonResponse({
            'success': True,
            'message': 'Document uploaded successfully',
            'document': {
                'id': str(document.id),
                'title': document.title,
                'filename': original_filename,
                'file_type': file_type,
                'size': uploaded_file.size,
                'is_primary': document.is_primary,
            }
        })

    except Exception as e:
        logger.error(f"Document upload error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@talent_required
@require_POST
@csrf_exempt
def talent_delete_document(request, document_id):
    """Delete a document."""
    from media.models import Document
    from django.core.files.storage import default_storage

    user = request.portal_user

    try:
        document = Document.objects.get(id=document_id, owner=user)
        media_file = document.media_file

        # Delete physical file
        if media_file and media_file.file_path:
            try:
                default_storage.delete(media_file.file_path)
            except Exception as e:
                logger.warning(f"Could not delete file: {e}")

        # Delete records
        if media_file:
            media_file.delete()
        document.delete()

        return JsonResponse({'success': True, 'message': 'Document deleted'})

    except Document.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Document not found'}, status=404)
    except Exception as e:
        logger.error(f"Document delete error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@talent_required
@require_POST
@csrf_exempt
def talent_rename_document(request, document_id):
    """Rename a document."""
    from media.models import Document

    user = request.portal_user

    try:
        data = json.loads(request.body)
        new_title = data.get('title', '').strip()

        if not new_title:
            return JsonResponse({'success': False, 'error': 'Title is required'}, status=400)

        document = Document.objects.get(id=document_id, owner=user)
        document.title = new_title
        document.save(update_fields=['title', 'updated_at'])

        return JsonResponse({
            'success': True,
            'message': 'Document renamed',
            'title': new_title
        })

    except Document.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Document not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@talent_required
@require_POST
@csrf_exempt
def talent_set_primary_document(request, document_id):
    """Set document as primary (for CVs)."""
    from media.models import Document

    user = request.portal_user

    try:
        document = Document.objects.get(id=document_id, owner=user)

        # Only CVs can be primary
        if document.media_file.file_type != 'cv':
            return JsonResponse({
                'success': False,
                'error': 'Only resumes/CVs can be set as primary'
            }, status=400)

        # Unset other primary CVs
        Document.objects.filter(
            owner=user,
            media_file__file_type='cv',
            is_primary=True
        ).update(is_primary=False)

        # Set this one as primary
        document.is_primary = True
        document.save(update_fields=['is_primary', 'updated_at'])

        return JsonResponse({
            'success': True,
            'message': 'Document set as primary resume'
        })

    except Document.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Document not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@talent_required
@require_POST
@csrf_exempt
def talent_update_document(request, document_id):
    """Update document metadata."""
    from media.models import Document

    user = request.portal_user

    try:
        data = json.loads(request.body)
        document = Document.objects.get(id=document_id, owner=user)

        if 'title' in data:
            document.title = data['title'].strip()
        if 'description' in data:
            document.description = data['description'].strip()

        document.save(update_fields=['title', 'description', 'updated_at'])

        return JsonResponse({
            'success': True,
            'message': 'Document updated'
        })

    except Document.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Document not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@talent_required
@require_GET
def talent_document_preview(request, document_id):
    """Get document preview/download URL."""
    from media.models import Document
    from django.core.files.storage import default_storage

    user = request.portal_user

    try:
        document = Document.objects.get(id=document_id, owner=user)
        media_file = document.media_file

        if not media_file or not media_file.file_path:
            return JsonResponse({'success': False, 'error': 'File not found'}, status=404)

        # Generate URL
        file_url = default_storage.url(media_file.file_path)

        return JsonResponse({
            'success': True,
            'url': file_url,
            'filename': media_file.original_filename,
            'mime_type': media_file.mime_type,
            'size': media_file.file_size,
            'is_image': media_file.is_image,
        })

    except Document.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Document not found'}, status=404)


@talent_required
@require_GET
def talent_download_document(request, document_id):
    """Download a document."""
    from media.models import Document
    from django.core.files.storage import default_storage
    from django.http import FileResponse

    user = request.portal_user

    try:
        document = Document.objects.get(id=document_id, owner=user)
        media_file = document.media_file

        if not media_file or not media_file.file_path:
            return HttpResponse('File not found', status=404)

        file_handle = default_storage.open(media_file.file_path, 'rb')
        response = FileResponse(
            file_handle,
            content_type=media_file.mime_type or 'application/octet-stream'
        )
        response['Content-Disposition'] = f'attachment; filename="{media_file.original_filename}"'
        return response

    except Document.DoesNotExist:
        return HttpResponse('Document not found', status=404)
    except Exception as e:
        logger.error(f"Document download error: {e}")
        return HttpResponse('Error downloading file', status=500)


@talent_required
@require_GET
def talent_document_stats(request):
    """Get document statistics."""
    from media.models import Document

    user = request.portal_user

    documents = Document.objects.filter(owner=user).select_related('media_file')

    total_size = sum(doc.media_file.file_size for doc in documents if doc.media_file)
    storage_limit = 50 * 1024 * 1024

    type_counts = {}
    for doc in documents:
        ftype = doc.media_file.file_type if doc.media_file else 'other'
        type_counts[ftype] = type_counts.get(ftype, 0) + 1

    return JsonResponse({
        'success': True,
        'stats': {
            'total_documents': documents.count(),
            'total_size': total_size,
            'storage_limit': storage_limit,
            'storage_used_percent': min(int((total_size / storage_limit) * 100), 100),
            'type_counts': type_counts,
        }
    })

@talent_required
@require_POST
@csrf_exempt
def talent_mark_notification_read(request, notification_id):
    """Mark notification as read."""
    from communications.models import Notification

    user = request.portal_user

    try:
        notification = Notification.objects.get(id=notification_id, user=user)
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return JsonResponse({'success': True})
    except Notification.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Not found'}, status=404)


@talent_required
@require_POST
@csrf_exempt
def talent_dismiss_recommendation(request, recommendation_id):
    """Dismiss a recommendation."""
    from matching.models import Recommendation

    user = request.portal_user

    try:
        rec = Recommendation.objects.get(id=recommendation_id, user=user)
        rec.is_dismissed = True
        rec.save(update_fields=['is_dismissed'])
        return JsonResponse({'success': True})
    except Recommendation.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Not found'}, status=404)


# =============================================================================
# ORGANIZATION PORTAL VIEWS
# =============================================================================

@employer_required
def org_dashboard(request):
    """Organization dashboard page."""
    from organizations.models import Organization, Opportunity, OrganizationMember
    from applications.models import Application

    user = request.portal_user

    # Get user's organization
    membership = OrganizationMember.objects.filter(
        user=user,
        is_active=True
    ).select_related('organization').first()

    if not membership:
        return render(request, 'website/portal/org/no_organization.html', portal_context(
            request,
            page_title='No Organization',
        ))

    org = membership.organization

    # Get stats
    active_opportunities = Opportunity.objects.filter(
        organization=org,
        status='active'
    ).count()

    total_applications = Application.objects.filter(
        opportunity__organization=org
    ).count()

    pending_review = Application.objects.filter(
        opportunity__organization=org,
        status='pending'
    ).count()

    # Recent applications
    recent_applications = Application.objects.filter(
        opportunity__organization=org
    ).select_related('applicant', 'opportunity').order_by('-created_at')[:10]

    return render(request, 'website/portal/org/dashboard.html', portal_context(
        request,
        page_title='Dashboard',
        organization=org,
        membership=membership,
        stats={
            'active_opportunities': active_opportunities,
            'total_applications': total_applications,
            'pending_review': pending_review,
        },
        recent_applications=recent_applications,
    ))


@employer_required
def org_opportunities(request):
    """Organization opportunities management page."""
    from organizations.models import Organization, Opportunity, OrganizationMember

    user = request.portal_user
    membership = OrganizationMember.objects.filter(
        user=user, is_active=True
    ).select_related('organization').first()

    if not membership:
        return redirect('/portal/org/dashboard')

    org = membership.organization
    status_filter = request.GET.get('status', '')

    opportunities = Opportunity.objects.filter(organization=org)

    if status_filter:
        opportunities = opportunities.filter(status=status_filter)

    opportunities = opportunities.order_by('-created_at')

    return render(request, 'website/portal/org/opportunities.html', portal_context(
        request,
        page_title='Opportunities',
        organization=org,
        opportunities=opportunities,
        status_filter=status_filter,
    ))


@employer_required
def org_applications(request):
    """Organization applications review page."""
    from organizations.models import OrganizationMember
    from applications.models import Application

    user = request.portal_user
    membership = OrganizationMember.objects.filter(
        user=user, is_active=True
    ).select_related('organization').first()

    if not membership:
        return redirect('/portal/org/dashboard')

    org = membership.organization
    status_filter = request.GET.get('status', '')
    opportunity_filter = request.GET.get('opportunity', '')

    applications = Application.objects.filter(
        opportunity__organization=org
    ).select_related('applicant', 'opportunity')

    if status_filter:
        applications = applications.filter(status=status_filter)

    if opportunity_filter:
        applications = applications.filter(opportunity_id=opportunity_filter)

    applications = applications.order_by('-created_at')

    return render(request, 'website/portal/org/applications.html', portal_context(
        request,
        page_title='Applications',
        organization=org,
        applications=applications,
        status_filter=status_filter,
    ))


@employer_required
def org_team(request):
    """Organization team management page."""
    from organizations.models import Organization, OrganizationMember

    user = request.portal_user
    membership = OrganizationMember.objects.filter(
        user=user, is_active=True
    ).select_related('organization').first()

    if not membership:
        return redirect('/portal/org/dashboard')

    org = membership.organization
    team_members = OrganizationMember.objects.filter(
        organization=org,
        is_active=True
    ).select_related('user').order_by('role', 'user__first_name')

    return render(request, 'website/portal/org/team.html', portal_context(
        request,
        page_title='Team',
        organization=org,
        team_members=team_members,
        current_membership=membership,
    ))


@employer_required
def org_settings(request):
    """Organization settings page."""
    from organizations.models import OrganizationMember

    user = request.portal_user
    membership = OrganizationMember.objects.filter(
        user=user, is_active=True
    ).select_related('organization').first()

    if not membership:
        return redirect('/portal/org/dashboard')

    return render(request, 'website/portal/org/settings.html', portal_context(
        request,
        page_title='Settings',
        organization=membership.organization,
        membership=membership,
    ))


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def calculate_profile_completion(profile):
    """Calculate profile completion percentage with detailed breakdown."""
    if not profile:
        return 0

    from profiles.models import Education, WorkExperience, TalentSkill

    fields = {
        'headline': bool(profile.headline),
        'bio': bool(profile.bio),
        'location': bool(profile.country or profile.city),
        'contact': bool(profile.phone_number),
        'resume': bool(getattr(profile, 'resume', None)),
        'education': Education.objects.filter(profile=profile).exists(),
        'experience': WorkExperience.objects.filter(profile=profile).exists(),
        'skills': TalentSkill.objects.filter(profile=profile).exists(),
        'linkedin': bool(profile.linkedin_url),
        'availability': bool(profile.availability),
    }

    completed = sum(1 for f in fields.values() if f)
    return int((completed / len(fields)) * 100)


def get_profile_completion_details(profile):
    """Get detailed profile completion status."""
    if not profile:
        return {'percentage': 0, 'items': [], 'missing': []}

    # Check related objects safely
    from profiles.models import Education, WorkExperience, TalentSkill

    has_education = Education.objects.filter(profile=profile).exists()
    has_experience = WorkExperience.objects.filter(profile=profile).exists()
    has_skills = TalentSkill.objects.filter(profile=profile).exists()

    items = [
        {'key': 'headline', 'name': 'Professional Headline', 'completed': bool(profile.headline), 'weight': 10},
        {'key': 'bio', 'name': 'About / Bio', 'completed': bool(profile.bio), 'weight': 15},
        {'key': 'location', 'name': 'Location', 'completed': bool(profile.country or profile.city), 'weight': 10},
        {'key': 'contact', 'name': 'Contact Number', 'completed': bool(profile.phone_number), 'weight': 10},
        {'key': 'education', 'name': 'Education', 'completed': has_education, 'weight': 15},
        {'key': 'experience', 'name': 'Work Experience', 'completed': has_experience, 'weight': 15},
        {'key': 'skills', 'name': 'Skills', 'completed': has_skills, 'weight': 15},
        {'key': 'linkedin', 'name': 'LinkedIn Profile', 'completed': bool(profile.linkedin_url), 'weight': 5},
        {'key': 'portfolio', 'name': 'Portfolio/Website', 'completed': bool(getattr(profile, 'portfolio_url', None) or getattr(profile, 'website', None)), 'weight': 5},
    ]

    total_weight = sum(item['weight'] for item in items)
    completed_weight = sum(item['weight'] for item in items if item['completed'])
    percentage = int((completed_weight / total_weight) * 100) if total_weight > 0 else 0

    missing = [item for item in items if not item['completed']]

    return {
        'percentage': percentage,
        'items': items,
        'missing': missing,
        'completed_count': len([i for i in items if i['completed']]),
        'total_count': len(items)
    }


def get_application_stats(user):
    """Get comprehensive application statistics."""
    from applications.models import Application

    total = Application.objects.filter(applicant=user).count()
    by_status = Application.objects.filter(applicant=user).values('status').annotate(count=Count('id'))

    status_map = {item['status']: item['count'] for item in by_status}

    # Calculate this month vs last month
    now = timezone.now()
    this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_start = (this_month_start - timedelta(days=1)).replace(day=1)

    this_month = Application.objects.filter(applicant=user, created_at__gte=this_month_start).count()
    last_month = Application.objects.filter(applicant=user, created_at__gte=last_month_start, created_at__lt=this_month_start).count()

    change_percent = 0
    if last_month > 0:
        change_percent = int(((this_month - last_month) / last_month) * 100)

    return {
        'total': total,
        'pending': status_map.get('pending', 0),
        'reviewing': status_map.get('reviewing', 0),
        'interview': status_map.get('interview', 0),
        'offered': status_map.get('offered', 0),
        'rejected': status_map.get('rejected', 0),
        'withdrawn': status_map.get('withdrawn', 0),
        'this_month': this_month,
        'last_month': last_month,
        'change_percent': change_percent,
    }


def get_saved_opportunities_count(user):
    """Get count of saved opportunities."""
    from applications.models import SavedOpportunity
    return SavedOpportunity.objects.filter(user=user).count()


def get_unread_notifications_count(user):
    """Get count of unread notifications."""
    from communications.models import Notification
    return Notification.objects.filter(recipient=user, is_read=False).count()


def get_unread_messages_count(user):
    """Get count of unread messages."""
    from communications.models import Message
    return Message.objects.filter(recipient=user, is_read=False).count()


# =============================================================================
# RESUME BUILDER API VIEWS
# =============================================================================

@talent_required
@require_POST
@csrf_exempt
def talent_resume_analyze(request):
    """Analyze resume for ATS optimization - returns real-time score."""
    from profiles.models import TalentProfile
    from website.services.resume_builder import ResumeBuilder

    user = request.portal_user
    profile, _ = TalentProfile.objects.get_or_create(user=user)

    try:
        # Check if custom data was sent
        import json
        if request.body:
            custom_data = json.loads(request.body)
            resume_builder = ResumeBuilder(user)
            resume_builder.from_dict(custom_data)
        else:
            # Load from profile
            resume_builder = ResumeBuilder(user)
            resume_builder.load_from_profile(profile)

        analysis = resume_builder.get_ats_score()

        return JsonResponse({
            'success': True,
            'analysis': analysis
        })

    except Exception as e:
        logger.error(f"Resume analysis error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@talent_required
@require_GET
def talent_resume_suggestions(request):
    """Get AI-powered content suggestions for resume."""
    from profiles.models import TalentProfile
    from website.services.resume_builder import ResumeBuilder

    user = request.portal_user
    profile, _ = TalentProfile.objects.get_or_create(user=user)

    try:
        resume_builder = ResumeBuilder(user)
        resume_builder.load_from_profile(profile)

        suggestions = resume_builder.get_suggestions()

        return JsonResponse({
            'success': True,
            'suggestions': suggestions
        })

    except Exception as e:
        logger.error(f"Resume suggestions error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@talent_required
@require_POST
@csrf_exempt
def talent_resume_export_pdf(request):
    """Export resume as PDF."""
    from profiles.models import TalentProfile
    from website.services.resume_builder import ResumeBuilder, ResumeExporter

    user = request.portal_user
    profile, _ = TalentProfile.objects.get_or_create(user=user)

    try:
        import json

        # Get template preference
        data = {}
        if request.body:
            data = json.loads(request.body)

        template = data.get('template', 'professional')

        # Load resume from profile
        resume_builder = ResumeBuilder(user)
        resume_builder.load_from_profile(profile)

        # If custom data provided, merge it
        if data.get('resume_data'):
            resume_builder.from_dict(data['resume_data'])

        # Export to PDF
        pdf_bytes = ResumeExporter.to_pdf(resume_builder.resume_data, template)

        # Create response
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        filename = f"{user.first_name or 'Resume'}_{user.last_name or ''}_{timezone.now().strftime('%Y%m%d')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response

    except Exception as e:
        logger.error(f"Resume PDF export error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@talent_required
@require_GET
def talent_resume_export_html(request):
    """Export resume as HTML for preview."""
    from profiles.models import TalentProfile
    from website.services.resume_builder import ResumeBuilder, ResumeExporter

    user = request.portal_user
    profile, _ = TalentProfile.objects.get_or_create(user=user)

    try:
        template = request.GET.get('template', 'professional')

        resume_builder = ResumeBuilder(user)
        resume_builder.load_from_profile(profile)

        html_content = ResumeExporter.to_html(resume_builder.resume_data, template)

        return HttpResponse(html_content, content_type='text/html')

    except Exception as e:
        logger.error(f"Resume HTML export error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@talent_required
@require_POST
@csrf_exempt
def talent_resume_save(request):
    """Save resume data/preferences to user profile."""
    from profiles.models import TalentProfile
    import json

    user = request.portal_user
    profile, _ = TalentProfile.objects.get_or_create(user=user)

    try:
        data = json.loads(request.body) if request.body else {}

        # Save resume preferences to profile metadata
        resume_settings = {
            'template': data.get('template', 'professional'),
            'section_order': data.get('section_order'),
            'color_scheme': data.get('color_scheme'),
            'font_family': data.get('font_family'),
            'updated_at': timezone.now().isoformat(),
        }

        # Update profile metadata
        metadata = profile.metadata or {}
        metadata['resume_settings'] = resume_settings
        profile.metadata = metadata
        profile.save(update_fields=['metadata'])

        return JsonResponse({
            'success': True,
            'message': 'Resume settings saved'
        })

    except Exception as e:
        logger.error(f"Resume save error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

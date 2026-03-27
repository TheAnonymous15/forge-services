# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Permissions (MVP1)
=======================================
Role-based permission classes and utilities.
"""
from rest_framework import permissions
from functools import wraps
from django.http import HttpResponseForbidden


# =============================================================================
# PERMISSION CONSTANTS
# =============================================================================

class Permissions:
    """Permission constants."""

    # Profile permissions
    VIEW_OWN_PROFILE = 'view_own_profile'
    EDIT_OWN_PROFILE = 'edit_own_profile'
    VIEW_ANY_PROFILE = 'view_any_profile'

    # Opportunity permissions
    VIEW_OPPORTUNITIES = 'view_opportunities'
    CREATE_OPPORTUNITY = 'create_opportunity'
    EDIT_OWN_OPPORTUNITY = 'edit_own_opportunity'
    EDIT_ANY_OPPORTUNITY = 'edit_any_opportunity'
    DELETE_OPPORTUNITY = 'delete_opportunity'

    # Application permissions
    APPLY_TO_OPPORTUNITY = 'apply_to_opportunity'
    VIEW_OWN_APPLICATIONS = 'view_own_applications'
    VIEW_ORG_APPLICATIONS = 'view_org_applications'
    REVIEW_APPLICATIONS = 'review_applications'

    # Organization permissions
    CREATE_ORGANIZATION = 'create_organization'
    EDIT_OWN_ORGANIZATION = 'edit_own_organization'
    MANAGE_ORG_MEMBERS = 'manage_org_members'

    # Admin permissions
    VIEW_ALL_USERS = 'view_all_users'
    MANAGE_USERS = 'manage_users'
    VIEW_ANALYTICS = 'view_analytics'
    MANAGE_SYSTEM = 'manage_system'


# =============================================================================
# ROLE-PERMISSION MAPPING
# =============================================================================

ROLE_PERMISSIONS = {
    'talent': [
        Permissions.VIEW_OWN_PROFILE,
        Permissions.EDIT_OWN_PROFILE,
        Permissions.VIEW_OPPORTUNITIES,
        Permissions.APPLY_TO_OPPORTUNITY,
        Permissions.VIEW_OWN_APPLICATIONS,
    ],
    'employer': [
        Permissions.VIEW_OWN_PROFILE,
        Permissions.EDIT_OWN_PROFILE,
        Permissions.VIEW_OPPORTUNITIES,
        Permissions.CREATE_OPPORTUNITY,
        Permissions.EDIT_OWN_OPPORTUNITY,
        Permissions.VIEW_ORG_APPLICATIONS,
        Permissions.REVIEW_APPLICATIONS,
    ],
    'org_admin': [
        Permissions.VIEW_OWN_PROFILE,
        Permissions.EDIT_OWN_PROFILE,
        Permissions.VIEW_OPPORTUNITIES,
        Permissions.CREATE_OPPORTUNITY,
        Permissions.EDIT_OWN_OPPORTUNITY,
        Permissions.DELETE_OPPORTUNITY,
        Permissions.VIEW_ORG_APPLICATIONS,
        Permissions.REVIEW_APPLICATIONS,
        Permissions.EDIT_OWN_ORGANIZATION,
        Permissions.MANAGE_ORG_MEMBERS,
    ],
    'staff': [
        Permissions.VIEW_OWN_PROFILE,
        Permissions.EDIT_OWN_PROFILE,
        Permissions.VIEW_ANY_PROFILE,
        Permissions.VIEW_OPPORTUNITIES,
        Permissions.VIEW_ALL_USERS,
        Permissions.VIEW_ANALYTICS,
    ],
    'admin': [
        # Admins have all permissions
        Permissions.VIEW_OWN_PROFILE,
        Permissions.EDIT_OWN_PROFILE,
        Permissions.VIEW_ANY_PROFILE,
        Permissions.VIEW_OPPORTUNITIES,
        Permissions.CREATE_OPPORTUNITY,
        Permissions.EDIT_OWN_OPPORTUNITY,
        Permissions.EDIT_ANY_OPPORTUNITY,
        Permissions.DELETE_OPPORTUNITY,
        Permissions.APPLY_TO_OPPORTUNITY,
        Permissions.VIEW_OWN_APPLICATIONS,
        Permissions.VIEW_ORG_APPLICATIONS,
        Permissions.REVIEW_APPLICATIONS,
        Permissions.CREATE_ORGANIZATION,
        Permissions.EDIT_OWN_ORGANIZATION,
        Permissions.MANAGE_ORG_MEMBERS,
        Permissions.VIEW_ALL_USERS,
        Permissions.MANAGE_USERS,
        Permissions.VIEW_ANALYTICS,
        Permissions.MANAGE_SYSTEM,
    ],
}


def has_permission(user, permission):
    """Check if user has a specific permission."""
    if not user or not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    role = user.role
    return permission in ROLE_PERMISSIONS.get(role, [])


def has_any_permission(user, permissions):
    """Check if user has any of the specified permissions."""
    return any(has_permission(user, p) for p in permissions)


def has_all_permissions(user, permissions):
    """Check if user has all specified permissions."""
    return all(has_permission(user, p) for p in permissions)


# =============================================================================
# DRF PERMISSION CLASSES
# =============================================================================

class IsTalent(permissions.BasePermission):
    """Allow only talent users."""
    message = 'Only talent users can perform this action.'

    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role == 'talent'
        )


class IsEmployer(permissions.BasePermission):
    """Allow only employer/org_admin users."""
    message = 'Only employer users can perform this action.'

    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role in ['employer', 'org_admin']
        )


class IsStaff(permissions.BasePermission):
    """Allow only staff users."""
    message = 'Only staff users can perform this action.'

    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            (request.user.role in ['staff', 'admin'] or request.user.is_staff)
        )


class IsAdmin(permissions.BasePermission):
    """Allow only admin users."""
    message = 'Only administrators can perform this action.'

    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            (request.user.role == 'admin' or request.user.is_superuser)
        )


class IsVerified(permissions.BasePermission):
    """Require email verification."""
    message = 'Please verify your email to perform this action.'

    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.is_verified
        )


class HasPermission(permissions.BasePermission):
    """Generic permission checker using permission constants."""
    required_permission = None

    def has_permission(self, request, view):
        if self.required_permission is None:
            return True
        return has_permission(request.user, self.required_permission)


class CanCreateOpportunity(HasPermission):
    """Permission to create opportunities."""
    required_permission = Permissions.CREATE_OPPORTUNITY
    message = 'You do not have permission to create opportunities.'


class CanReviewApplications(HasPermission):
    """Permission to review applications."""
    required_permission = Permissions.REVIEW_APPLICATIONS
    message = 'You do not have permission to review applications.'


class CanManageOrgMembers(HasPermission):
    """Permission to manage organization members."""
    required_permission = Permissions.MANAGE_ORG_MEMBERS
    message = 'You do not have permission to manage organization members.'


class CanViewAnalytics(HasPermission):
    """Permission to view analytics."""
    required_permission = Permissions.VIEW_ANALYTICS
    message = 'You do not have permission to view analytics.'


# =============================================================================
# DECORATORS
# =============================================================================

def permission_required(permission):
    """Decorator for view functions requiring a specific permission."""
    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            if not has_permission(request.user, permission):
                return HttpResponseForbidden('Permission denied')
            return func(request, *args, **kwargs)
        return wrapper
    return decorator


def any_permission_required(*perms):
    """Decorator for view functions requiring any of the specified permissions."""
    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            if not has_any_permission(request.user, perms):
                return HttpResponseForbidden('Permission denied')
            return func(request, *args, **kwargs)
        return wrapper
    return decorator


def role_required(*roles):
    """Decorator for view functions requiring specific roles."""
    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return HttpResponseForbidden('Authentication required')
            if request.user.role not in roles and not request.user.is_superuser:
                return HttpResponseForbidden('Permission denied')
            return func(request, *args, **kwargs)
        return wrapper
    return decorator


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_user_permissions(user):
    """Get all permissions for a user."""
    if not user or not user.is_authenticated:
        return []

    if user.is_superuser:
        # Return all permissions
        return [p for perms in ROLE_PERMISSIONS.values() for p in perms]

    return ROLE_PERMISSIONS.get(user.role, [])


def check_object_permission(user, obj, permission):
    """
    Check permission for a specific object.

    This handles object-level permissions like:
    - Editing only own profile
    - Managing only own organization's opportunities
    """
    if not user or not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    # Basic permission check
    if not has_permission(user, permission):
        return False

    # Object-level checks
    if hasattr(obj, 'user') and permission in [Permissions.EDIT_OWN_PROFILE]:
        return obj.user == user

    if hasattr(obj, 'organization'):
        from organizations.models import OrganizationMember
        return OrganizationMember.objects.filter(
            organization=obj.organization,
            user=user,
            is_active=True
        ).exists()

    if hasattr(obj, 'applicant') and permission == Permissions.VIEW_OWN_APPLICATIONS:
        return obj.applicant == user

    return True


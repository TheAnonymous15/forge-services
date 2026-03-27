# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Email Service (MVP1)
=========================================
Email sending utilities for verification, notifications, etc.
"""
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags
import logging

logger = logging.getLogger('forgeforth.email')


class EmailService:
    """Service for sending emails."""

    @staticmethod
    def send_email(to_email, subject, template_name, context, from_email=None):
        """
        Send an email using a template.

        Args:
            to_email: Recipient email address
            subject: Email subject
            template_name: Template name (without extension)
            context: Context dictionary for template
            from_email: Sender email (defaults to DEFAULT_FROM_EMAIL)

        Returns:
            bool: True if sent successfully
        """
        if from_email is None:
            from_email = settings.DEFAULT_FROM_EMAIL

        try:
            # Render HTML template
            html_content = render_to_string(f'emails/{template_name}.html', context)
            text_content = strip_tags(html_content)

            # Create email
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=from_email,
                to=[to_email]
            )
            email.attach_alternative(html_content, 'text/html')

            # Send
            email.send(fail_silently=False)

            logger.info(f"Email sent: {template_name} to {to_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email {template_name} to {to_email}: {str(e)}")
            return False

    @staticmethod
    def send_verification_email(user, token):
        """Send email verification email."""
        context = {
            'user': user,
            'token': token,
            'verification_url': f"{settings.SITE_URL}/verify-email?token={token}",
            'site_name': settings.SITE_NAME,
        }

        return EmailService.send_email(
            to_email=user.email,
            subject=f'Verify your email - {settings.SITE_NAME}',
            template_name='verification',
            context=context
        )

    @staticmethod
    def send_password_reset_email(user, token):
        """Send password reset email."""
        context = {
            'user': user,
            'token': token,
            'reset_url': f"{settings.SITE_URL}/reset-password?token={token}",
            'site_name': settings.SITE_NAME,
            'expiry_hours': 24,
        }

        return EmailService.send_email(
            to_email=user.email,
            subject=f'Reset your password - {settings.SITE_NAME}',
            template_name='password_reset',
            context=context
        )

    @staticmethod
    def send_welcome_email(user):
        """Send welcome email after registration."""
        context = {
            'user': user,
            'site_name': settings.SITE_NAME,
            'site_url': settings.SITE_URL,
        }

        return EmailService.send_email(
            to_email=user.email,
            subject=f'Welcome to {settings.SITE_NAME}!',
            template_name='welcome',
            context=context
        )

    @staticmethod
    def send_password_changed_email(user):
        """Send notification when password is changed."""
        context = {
            'user': user,
            'site_name': settings.SITE_NAME,
        }

        return EmailService.send_email(
            to_email=user.email,
            subject=f'Your password was changed - {settings.SITE_NAME}',
            template_name='password_changed',
            context=context
        )

    @staticmethod
    def send_application_submitted_email(application):
        """Send confirmation when application is submitted."""
        context = {
            'user': application.applicant,
            'opportunity': application.opportunity,
            'organization': application.opportunity.organization,
            'site_name': settings.SITE_NAME,
        }

        return EmailService.send_email(
            to_email=application.applicant.email,
            subject=f'Application submitted - {application.opportunity.title}',
            template_name='application_submitted',
            context=context
        )

    @staticmethod
    def send_application_status_email(application, new_status):
        """Send notification when application status changes."""
        context = {
            'user': application.applicant,
            'opportunity': application.opportunity,
            'organization': application.opportunity.organization,
            'status': new_status,
            'site_name': settings.SITE_NAME,
        }

        return EmailService.send_email(
            to_email=application.applicant.email,
            subject=f'Application update - {application.opportunity.title}',
            template_name='application_status',
            context=context
        )

    @staticmethod
    def send_interview_scheduled_email(interview):
        """Send notification when interview is scheduled."""
        application = interview.application
        context = {
            'user': application.applicant,
            'interview': interview,
            'opportunity': application.opportunity,
            'organization': application.opportunity.organization,
            'site_name': settings.SITE_NAME,
        }

        return EmailService.send_email(
            to_email=application.applicant.email,
            subject=f'Interview scheduled - {application.opportunity.title}',
            template_name='interview_scheduled',
            context=context
        )

    @staticmethod
    def send_new_application_email(application):
        """Send notification to employer when new application received."""
        # Get org admins/recruiters
        from organizations.models import OrganizationMember

        members = OrganizationMember.objects.filter(
            organization=application.opportunity.organization,
            role__in=['owner', 'admin', 'recruiter', 'hiring_manager'],
            is_active=True
        ).select_related('user')

        context = {
            'applicant': application.applicant,
            'opportunity': application.opportunity,
            'organization': application.opportunity.organization,
            'site_name': settings.SITE_NAME,
        }

        sent_count = 0
        for member in members:
            if EmailService.send_email(
                to_email=member.user.email,
                subject=f'New application - {application.opportunity.title}',
                template_name='new_application',
                context={**context, 'user': member.user}
            ):
                sent_count += 1

        return sent_count


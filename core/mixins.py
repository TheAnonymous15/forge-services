# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Cross-Database Mixins
==========================================
Mixins for models that need to reference entities in other databases
using UUIDs instead of ForeignKeys.

This enables true microservices-style database isolation where each
subsystem has its own database but can still reference users and
other entities via UUID.
"""

import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _


class UserReferenceMixin(models.Model):
    """
    Mixin for models that need to reference a User from another database.

    Instead of ForeignKey to User (which requires same database),
    we store the user's UUID. The application layer handles lookups.

    Usage:
        class MyModel(UserReferenceMixin, models.Model):
            # your fields here
            pass

        # To get the user:
        user = my_instance.get_user()

        # To set the user:
        my_instance.set_user(user)
    """

    # UUID reference to user in accounts database
    user_id = models.UUIDField(
        db_index=True,
        null=True,
        blank=True,
        help_text=_('UUID reference to user in accounts database')
    )

    # Cached user email for display (denormalized for performance)
    user_email = models.EmailField(
        blank=True,
        default='',
        help_text=_('Cached user email for display')
    )

    class Meta:
        abstract = True

    def get_user(self):
        """
        Fetch the User object from the accounts database.
        Returns None if user_id is not set or user doesn't exist.
        """
        if not self.user_id:
            return None

        from accounts.models import User
        try:
            return User.objects.using('accounts_db').get(id=self.user_id)
        except User.DoesNotExist:
            return None

    def set_user(self, user):
        """
        Set the user reference from a User object.
        Also caches the email for display purposes.
        """
        if user:
            self.user_id = user.id
            self.user_email = user.email
        else:
            self.user_id = None
            self.user_email = ''

    @property
    def user(self):
        """Property to get user (cached per request if needed)."""
        if not hasattr(self, '_user_cache'):
            self._user_cache = self.get_user()
        return self._user_cache

    @user.setter
    def user(self, value):
        """Property setter for user."""
        self.set_user(value)
        self._user_cache = value


class OrganizationReferenceMixin(models.Model):
    """
    Mixin for models that need to reference an Organization from another database.
    """

    organization_id = models.UUIDField(
        db_index=True,
        null=True,
        blank=True,
        help_text=_('UUID reference to organization')
    )

    organization_name = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text=_('Cached organization name for display')
    )

    class Meta:
        abstract = True

    def get_organization(self):
        """Fetch the Organization object from the organizations database."""
        if not self.organization_id:
            return None

        from organizations.models import Organization
        try:
            return Organization.objects.using('organizations_db').get(id=self.organization_id)
        except Organization.DoesNotExist:
            return None

    def set_organization(self, org):
        """Set the organization reference."""
        if org:
            self.organization_id = org.id
            self.organization_name = org.name
        else:
            self.organization_id = None
            self.organization_name = ''


class OpportunityReferenceMixin(models.Model):
    """
    Mixin for models that need to reference an Opportunity from another database.
    """

    opportunity_id = models.UUIDField(
        db_index=True,
        null=True,
        blank=True,
        help_text=_('UUID reference to opportunity')
    )

    opportunity_title = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text=_('Cached opportunity title for display')
    )

    class Meta:
        abstract = True

    def get_opportunity(self):
        """Fetch the Opportunity object."""
        if not self.opportunity_id:
            return None

        from organizations.models import Opportunity
        try:
            return Opportunity.objects.using('organizations_db').get(id=self.opportunity_id)
        except Opportunity.DoesNotExist:
            return None

    def set_opportunity(self, opp):
        """Set the opportunity reference."""
        if opp:
            self.opportunity_id = opp.id
            self.opportunity_title = opp.title
        else:
            self.opportunity_id = None
            self.opportunity_title = ''


class TalentProfileReferenceMixin(models.Model):
    """
    Mixin for models that need to reference a TalentProfile from another database.
    """

    talent_profile_id = models.UUIDField(
        db_index=True,
        null=True,
        blank=True,
        help_text=_('UUID reference to talent profile')
    )

    class Meta:
        abstract = True

    def get_talent_profile(self):
        """Fetch the TalentProfile object."""
        if not self.talent_profile_id:
            return None

        from profiles.models import TalentProfile
        try:
            return TalentProfile.objects.using('profiles_db').get(id=self.talent_profile_id)
        except TalentProfile.DoesNotExist:
            return None

    def set_talent_profile(self, profile):
        """Set the talent profile reference."""
        if profile:
            self.talent_profile_id = profile.id
        else:
            self.talent_profile_id = None


class CreatedByMixin(models.Model):
    """
    Mixin for tracking who created/modified a record across databases.
    """

    created_by_id = models.UUIDField(
        null=True,
        blank=True,
        help_text=_('UUID of user who created this record')
    )

    updated_by_id = models.UUIDField(
        null=True,
        blank=True,
        help_text=_('UUID of user who last updated this record')
    )

    class Meta:
        abstract = True

    def get_created_by(self):
        """Fetch the user who created this record."""
        if not self.created_by_id:
            return None
        from accounts.models import User
        try:
            return User.objects.using('accounts_db').get(id=self.created_by_id)
        except User.DoesNotExist:
            return None

    def get_updated_by(self):
        """Fetch the user who last updated this record."""
        if not self.updated_by_id:
            return None
        from accounts.models import User
        try:
            return User.objects.using('accounts_db').get(id=self.updated_by_id)
        except User.DoesNotExist:
            return None


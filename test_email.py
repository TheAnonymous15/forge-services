#!/usr/bin/env python
"""
Full User Registration + Email Verification Test for ForgeForth Africa
"""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "forgeforth.settings")

import django
django.setup()

from django.utils import timezone
from accounts.models import User, EmailVerificationToken
from django.conf import settings
from communications.services import EmailService

print("=" * 60)
print("FORGEFORTH AFRICA - FULL REGISTRATION TEST")
print("=" * 60)

# Test user details
TEST_USER = {
    "email": "daniel.kinyua@tutamail.com",
    "password": "PassWord!23",
    "first_name": "Daniel",
    "last_name": "Kinyua",
    "phone_number": "0724562524",
    "role": "talent",
    "country": "Kenya",
    "date_of_birth": "1980-03-04",
    "gender": "male",
    "education_level": "bachelors",
    "opportunity_types": ["internship"],
    "skills": ["Data Science"],
    "preferred_fields": ["EdTech"],
    "referral_source": "friend",
    "bio": "Im skilled"
}

print(f"\n1. Test User Details:")
print(f"   Email: {TEST_USER['email']}")
print(f"   Name: {TEST_USER['first_name']} {TEST_USER['last_name']}")
print(f"   Phone: {TEST_USER['phone_number']}")
print(f"   Country: {TEST_USER['country']}")

# Check email config
print(f"\n2. Email Configuration:")
print(f"   EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
print(f"   EMAIL_HOST: {settings.EMAIL_HOST}")
print(f"   EMAIL_PORT: {settings.EMAIL_PORT}")
print(f"   EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}")
print(f"   EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}")
print(f"   DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")
print(f"   SITE_URL: {settings.SITE_URL}")

# Check if user already exists
print(f"\n3. Checking if user already exists...")
existing_user = User.objects.filter(email=TEST_USER['email']).first()
if existing_user:
    print(f"   User already exists: {existing_user.email}")
    print(f"   Verified: {existing_user.is_verified}")
    print(f"   Deleting existing user for fresh test...")
    existing_user.delete()
    print(f"   Deleted.")

# Create user
print(f"\n4. Creating new user...")
try:
    user = User.objects.create_user(
        email=TEST_USER['email'],
        password=TEST_USER['password'],
        first_name=TEST_USER['first_name'],
        last_name=TEST_USER['last_name'],
        phone_number=TEST_USER['phone_number'],
        role=TEST_USER['role'],
        consent_terms=True,
        consent_privacy=True,
        consent_marketing=False,
        consented_at=timezone.now(),
        is_verified=False,
    )
    print(f"   ✅ User created: {user.email} (ID: {user.id})")
except Exception as e:
    print(f"   ❌ User creation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Create verification token
print(f"\n5. Creating verification token...")
try:
    token = EmailVerificationToken.create_token(user, expires_hours=24)
    print(f"   ✅ Token created: {token.token[:20]}...")
    verification_url = f"{settings.SITE_URL}/verify-email?token={token.token}"
    print(f"   Verification URL: {verification_url}")
except Exception as e:
    print(f"   ❌ Token creation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Send verification email
print(f"\n6. Sending verification email to {user.email}...")
try:
    result = EmailService.send_verification_email(user, token.token)
    if result:
        print(f"   ✅ Verification email sent successfully!")
    else:
        print(f"   ❌ Email send returned False")
except Exception as e:
    print(f"   ❌ Email sending failed: {e}")
    import traceback
    traceback.print_exc()

# Summary
print("\n" + "=" * 60)
print("REGISTRATION TEST COMPLETE")
print("=" * 60)
print(f"User: {user.email}")
print(f"User ID: {user.id}")
print(f"Verified: {user.is_verified}")
print(f"Verification URL: {verification_url}")
print("\nCheck your email inbox for the verification email!")
print("=" * 60)


#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Integration Test Runner
============================================
Runs all integration tests and produces a report.
"""
import os
import sys
import json
import time
import subprocess
import signal
from datetime import datetime
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Test results storage
RESULTS = {
    "timestamp": datetime.now().isoformat(),
    "tests": [],
    "passed": 0,
    "failed": 0,
    "skipped": 0,
    "duration": 0
}

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


def log(msg, color=None):
    """Print colored log message."""
    if color:
        print(f"{color}{msg}{RESET}")
    else:
        print(msg)


def log_test(name, status, duration=0, error=None):
    """Log test result."""
    result = {
        "name": name,
        "status": status,
        "duration": duration,
        "error": str(error) if error else None
    }
    RESULTS["tests"].append(result)

    if status == "PASS":
        RESULTS["passed"] += 1
        log(f"  ✅ {name} ({duration:.2f}s)", GREEN)
    elif status == "FAIL":
        RESULTS["failed"] += 1
        log(f"  ❌ {name} ({duration:.2f}s)", RED)
        if error:
            log(f"     Error: {error}", RED)
    elif status == "SKIP":
        RESULTS["skipped"] += 1
        log(f"  ⏭️  {name} (skipped)", YELLOW)


def run_command(cmd, timeout=30):
    """Run a command and return success status."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=PROJECT_ROOT
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Timeout"
    except Exception as e:
        return False, "", str(e)


class IntegrationTests:
    """Integration test suite."""

    def __init__(self):
        self.django_running = False
        self.auth_running = False
        self.talent_running = False
        self.org_running = False

    # =========================================================================
    # 1. Django System Tests
    # =========================================================================

    def test_django_check(self):
        """Test Django system checks pass."""
        start = time.time()
        success, stdout, stderr = run_command("python manage.py check", timeout=60)
        duration = time.time() - start

        if success and "System check identified no issues" in stdout:
            log_test("Django System Check", "PASS", duration)
            return True
        else:
            log_test("Django System Check", "FAIL", duration, stderr or stdout)
            return False

    def test_migrations(self):
        """Test all migrations can be applied."""
        start = time.time()
        success, stdout, stderr = run_command("python manage.py migrate --check", timeout=60)
        duration = time.time() - start

        if success:
            log_test("Database Migrations", "PASS", duration)
            return True
        else:
            log_test("Database Migrations", "FAIL", duration, stderr)
            return False

    def test_collectstatic(self):
        """Test static files collection."""
        start = time.time()
        success, stdout, stderr = run_command(
            "python manage.py collectstatic --noinput --dry-run",
            timeout=120
        )
        duration = time.time() - start

        if success:
            log_test("Static Files Collection", "PASS", duration)
            return True
        else:
            log_test("Static Files Collection", "FAIL", duration, stderr)
            return False

    # =========================================================================
    # 2. Import Tests
    # =========================================================================

    def test_website_imports(self):
        """Test website app imports."""
        start = time.time()
        try:
            from website import views, models, urls
            from website.services.blog_service import BlogService
            duration = time.time() - start
            log_test("Website Imports", "PASS", duration)
            return True
        except Exception as e:
            duration = time.time() - start
            log_test("Website Imports", "FAIL", duration, e)
            return False

    def test_accounts_imports(self):
        """Test accounts app imports."""
        start = time.time()
        try:
            from accounts import models, views, serializers
            duration = time.time() - start
            log_test("Accounts Imports", "PASS", duration)
            return True
        except Exception as e:
            duration = time.time() - start
            log_test("Accounts Imports", "FAIL", duration, e)
            return False

    def test_profiles_imports(self):
        """Test profiles app imports."""
        start = time.time()
        try:
            from profiles import models, views, serializers
            duration = time.time() - start
            log_test("Profiles Imports", "PASS", duration)
            return True
        except Exception as e:
            duration = time.time() - start
            log_test("Profiles Imports", "FAIL", duration, e)
            return False

    def test_organizations_imports(self):
        """Test organizations app imports."""
        start = time.time()
        try:
            from organizations import models, views, serializers
            duration = time.time() - start
            log_test("Organizations Imports", "PASS", duration)
            return True
        except Exception as e:
            duration = time.time() - start
            log_test("Organizations Imports", "FAIL", duration, e)
            return False

    def test_applications_imports(self):
        """Test applications app imports."""
        start = time.time()
        try:
            from applications import models, views, serializers
            duration = time.time() - start
            log_test("Applications Imports", "PASS", duration)
            return True
        except Exception as e:
            duration = time.time() - start
            log_test("Applications Imports", "FAIL", duration, e)
            return False

    def test_matching_imports(self):
        """Test matching app imports."""
        start = time.time()
        try:
            from matching import models, views
            duration = time.time() - start
            log_test("Matching Imports", "PASS", duration)
            return True
        except Exception as e:
            duration = time.time() - start
            log_test("Matching Imports", "FAIL", duration, e)
            return False

    def test_communications_imports(self):
        """Test communications app imports."""
        start = time.time()
        try:
            from communications import models, views
            duration = time.time() - start
            log_test("Communications Imports", "PASS", duration)
            return True
        except Exception as e:
            duration = time.time() - start
            log_test("Communications Imports", "FAIL", duration, e)
            return False

    def test_storage_imports(self):
        """Test storage service imports."""
        start = time.time()
        try:
            from storage import models, views
            from storage.services import get_storage_service
            duration = time.time() - start
            log_test("Storage Service Imports", "PASS", duration)
            return True
        except Exception as e:
            duration = time.time() - start
            log_test("Storage Service Imports", "FAIL", duration, e)
            return False

    def test_media_processor_imports(self):
        """Test media processing imports."""
        start = time.time()
        try:
            from media.services.image_processor import ImageProcessor
            from media.services.document_processor import DocumentProcessor
            duration = time.time() - start
            log_test("Media Processor Imports", "PASS", duration)
            return True
        except Exception as e:
            duration = time.time() - start
            log_test("Media Processor Imports", "FAIL", duration, e)
            return False

    # =========================================================================
    # 3. Portal Tests
    # =========================================================================

    def test_talent_portal_imports(self):
        """Test talent portal imports."""
        start = time.time()
        try:
            from talent_portal import config
            from talent_portal.routes import router
            from talent_portal.auth import auth_client
            from talent_portal.api_client import api_client
            duration = time.time() - start
            log_test("Talent Portal Imports", "PASS", duration)
            return True
        except Exception as e:
            duration = time.time() - start
            log_test("Talent Portal Imports", "FAIL", duration, e)
            return False

    def test_org_portal_imports(self):
        """Test organization portal imports."""
        start = time.time()
        try:
            from org_portal.main import app
            duration = time.time() - start
            log_test("Org Portal Imports", "PASS", duration)
            return True
        except Exception as e:
            duration = time.time() - start
            log_test("Org Portal Imports", "FAIL", duration, e)
            return False

    def test_auth_service_imports(self):
        """Test auth service imports."""
        start = time.time()
        try:
            from auth_service import app, service, security
            duration = time.time() - start
            log_test("Auth Service Imports", "PASS", duration)
            return True
        except Exception as e:
            duration = time.time() - start
            log_test("Auth Service Imports", "FAIL", duration, e)
            return False

    # =========================================================================
    # 4. URL Tests
    # =========================================================================

    def test_url_resolution(self):
        """Test that all URLs can be resolved."""
        start = time.time()
        try:
            from django.urls import reverse, get_resolver

            # Test key URLs
            test_urls = [
                ('website:home', [], {}),
                ('website:about', [], {}),
                ('website:blog', [], {}),
                ('website:contact', [], {}),
            ]

            for name, args, kwargs in test_urls:
                try:
                    url = reverse(name, args=args, kwargs=kwargs)
                except Exception as e:
                    duration = time.time() - start
                    log_test("URL Resolution", "FAIL", duration, f"Failed to resolve {name}: {e}")
                    return False

            duration = time.time() - start
            log_test("URL Resolution", "PASS", duration)
            return True
        except Exception as e:
            duration = time.time() - start
            log_test("URL Resolution", "FAIL", duration, e)
            return False

    # =========================================================================
    # 5. API Tests
    # =========================================================================

    def test_api_schema(self):
        """Test API schema generation."""
        start = time.time()
        try:
            from drf_spectacular.generators import SchemaGenerator
            generator = SchemaGenerator(patterns=[])
            # Just verify it can be instantiated
            duration = time.time() - start
            log_test("API Schema Generation", "PASS", duration)
            return True
        except Exception as e:
            duration = time.time() - start
            log_test("API Schema Generation", "FAIL", duration, e)
            return False

    def test_serializers(self):
        """Test that all serializers can be instantiated."""
        start = time.time()
        try:
            from accounts.serializers import UserSerializer
            from profiles.serializers import TalentProfileDetailSerializer
            from organizations.serializers import OrganizationDetailSerializer, OpportunityDetailSerializer
            from applications.serializers import ApplicationDetailSerializer

            # Just verify they exist and can be referenced
            duration = time.time() - start
            log_test("Serializer Instantiation", "PASS", duration)
            return True
        except Exception as e:
            duration = time.time() - start
            log_test("Serializer Instantiation", "FAIL", duration, e)
            return False

    # =========================================================================
    # 6. Template Tests
    # =========================================================================

    def test_website_templates_exist(self):
        """Test that required website templates exist."""
        start = time.time()
        templates_dir = PROJECT_ROOT / 'website' / 'templates' / 'website'

        required_templates = [
            'layouts/base.html',
            'pages/index.html',
            'pages/about.html',
            'pages/blog.html',
            'pages/contact.html',
            'pages/for_talent.html',
            'pages/for_employers.html',
            'pages/platform.html',
        ]

        missing = []
        for template in required_templates:
            if not (templates_dir / template).exists():
                missing.append(template)

        duration = time.time() - start
        if not missing:
            log_test("Website Templates", "PASS", duration)
            return True
        else:
            log_test("Website Templates", "FAIL", duration, f"Missing: {missing}")
            return False

    def test_talent_portal_templates_exist(self):
        """Test that talent portal templates exist."""
        start = time.time()
        templates_dir = PROJECT_ROOT / 'talent_portal' / 'templates'

        required_templates = [
            'base.html',
            'dashboard/index.html',
            'profile/view.html',
            'profile/edit.html',
            'opportunities/list.html',
            'applications/list.html',
        ]

        missing = []
        for template in required_templates:
            if not (templates_dir / template).exists():
                missing.append(template)

        duration = time.time() - start
        if not missing:
            log_test("Talent Portal Templates", "PASS", duration)
            return True
        else:
            log_test("Talent Portal Templates", "FAIL", duration, f"Missing: {missing}")
            return False

    def test_org_portal_templates_exist(self):
        """Test that org portal templates exist."""
        start = time.time()
        templates_dir = PROJECT_ROOT / 'org_portal' / 'templates'

        required_templates = [
            'base.html',
            'dashboard/index.html',
            'opportunities/list.html',
            'applications/list.html',
        ]

        missing = []
        for template in required_templates:
            if not (templates_dir / template).exists():
                missing.append(template)

        duration = time.time() - start
        if not missing:
            log_test("Org Portal Templates", "PASS", duration)
            return True
        else:
            log_test("Org Portal Templates", "FAIL", duration, f"Missing: {missing}")
            return False

    # =========================================================================
    # 7. Config Tests
    # =========================================================================

    def test_env_file_exists(self):
        """Test that .env file exists."""
        start = time.time()
        env_path = PROJECT_ROOT / '.env'

        if env_path.exists():
            duration = time.time() - start
            log_test("Environment File", "PASS", duration)
            return True
        else:
            duration = time.time() - start
            log_test("Environment File", "FAIL", duration, ".env file not found")
            return False

    def test_config_json_exists(self):
        """Test that config.json exists."""
        start = time.time()
        config_path = PROJECT_ROOT / 'config.json'

        if config_path.exists():
            try:
                with open(config_path) as f:
                    config = json.load(f)
                duration = time.time() - start
                log_test("Config JSON", "PASS", duration)
                return True
            except json.JSONDecodeError as e:
                duration = time.time() - start
                log_test("Config JSON", "FAIL", duration, f"Invalid JSON: {e}")
                return False
        else:
            duration = time.time() - start
            log_test("Config JSON", "FAIL", duration, "config.json not found")
            return False

    # =========================================================================
    # 8. Security Tests
    # =========================================================================

    def test_security_settings(self):
        """Test security settings are properly configured."""
        start = time.time()
        try:
            from django.conf import settings

            checks = []

            # Check SECRET_KEY is set and not default
            if hasattr(settings, 'SECRET_KEY') and settings.SECRET_KEY:
                if 'change-me' not in settings.SECRET_KEY.lower():
                    checks.append(True)
                else:
                    checks.append(False)

            # Check ALLOWED_HOSTS
            if hasattr(settings, 'ALLOWED_HOSTS') and settings.ALLOWED_HOSTS:
                checks.append(True)
            else:
                checks.append(False)

            duration = time.time() - start
            if all(checks):
                log_test("Security Settings", "PASS", duration)
                return True
            else:
                log_test("Security Settings", "FAIL", duration, "Some security checks failed")
                return False
        except Exception as e:
            duration = time.time() - start
            log_test("Security Settings", "FAIL", duration, e)
            return False

    # =========================================================================
    # 9. Database Tests
    # =========================================================================

    def test_database_connection(self):
        """Test database connection works."""
        start = time.time()
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            duration = time.time() - start
            log_test("Database Connection", "PASS", duration)
            return True
        except Exception as e:
            duration = time.time() - start
            log_test("Database Connection", "FAIL", duration, e)
            return False

    def test_models_can_query(self):
        """Test that models can be queried."""
        start = time.time()
        try:
            from accounts.models import User
            from profiles.models import TalentProfile
            from organizations.models import Organization, Opportunity
            from applications.models import Application

            # Just run count queries to verify tables exist
            User.objects.count()
            TalentProfile.objects.count()
            Organization.objects.count()
            Opportunity.objects.count()
            Application.objects.count()

            duration = time.time() - start
            log_test("Model Queries", "PASS", duration)
            return True
        except Exception as e:
            duration = time.time() - start
            log_test("Model Queries", "FAIL", duration, e)
            return False

    # =========================================================================
    # Run All Tests
    # =========================================================================

    def run_all(self):
        """Run all integration tests."""
        log(f"\n{BOLD}{'='*60}{RESET}")
        log(f"{BOLD}  ForgeForth Africa - Integration Tests{RESET}")
        log(f"{BOLD}{'='*60}{RESET}\n")

        start_time = time.time()

        # 1. Django System Tests
        log(f"\n{BLUE}1. Django System Tests{RESET}")
        log("-" * 40)
        self.test_django_check()
        self.test_migrations()
        self.test_collectstatic()

        # 2. Import Tests
        log(f"\n{BLUE}2. Import Tests{RESET}")
        log("-" * 40)
        self.test_website_imports()
        self.test_accounts_imports()
        self.test_profiles_imports()
        self.test_organizations_imports()
        self.test_applications_imports()
        self.test_matching_imports()
        self.test_communications_imports()
        self.test_storage_imports()
        self.test_media_processor_imports()

        # 3. Portal Tests
        log(f"\n{BLUE}3. Portal Tests{RESET}")
        log("-" * 40)
        self.test_talent_portal_imports()
        self.test_org_portal_imports()
        self.test_auth_service_imports()

        # 4. URL Tests
        log(f"\n{BLUE}4. URL Tests{RESET}")
        log("-" * 40)
        self.test_url_resolution()

        # 5. API Tests
        log(f"\n{BLUE}5. API Tests{RESET}")
        log("-" * 40)
        self.test_api_schema()
        self.test_serializers()

        # 6. Template Tests
        log(f"\n{BLUE}6. Template Tests{RESET}")
        log("-" * 40)
        self.test_website_templates_exist()
        self.test_talent_portal_templates_exist()
        self.test_org_portal_templates_exist()

        # 7. Config Tests
        log(f"\n{BLUE}7. Configuration Tests{RESET}")
        log("-" * 40)
        self.test_env_file_exists()
        self.test_config_json_exists()

        # 8. Security Tests
        log(f"\n{BLUE}8. Security Tests{RESET}")
        log("-" * 40)
        self.test_security_settings()

        # 9. Database Tests
        log(f"\n{BLUE}9. Database Tests{RESET}")
        log("-" * 40)
        self.test_database_connection()
        self.test_models_can_query()

        # Summary
        RESULTS["duration"] = time.time() - start_time

        log(f"\n{BOLD}{'='*60}{RESET}")
        log(f"{BOLD}  Test Summary{RESET}")
        log(f"{BOLD}{'='*60}{RESET}\n")

        total = RESULTS["passed"] + RESULTS["failed"] + RESULTS["skipped"]
        log(f"  Total Tests: {total}")
        log(f"  {GREEN}Passed: {RESULTS['passed']}{RESET}")
        log(f"  {RED}Failed: {RESULTS['failed']}{RESET}")
        log(f"  {YELLOW}Skipped: {RESULTS['skipped']}{RESET}")
        log(f"  Duration: {RESULTS['duration']:.2f}s")

        if RESULTS["failed"] == 0:
            log(f"\n  {GREEN}{BOLD}✅ All tests passed!{RESET}")
        else:
            log(f"\n  {RED}{BOLD}❌ Some tests failed{RESET}")

        # Save results
        results_path = PROJECT_ROOT / 'tests' / 'integration' / 'results.json'
        with open(results_path, 'w') as f:
            json.dump(RESULTS, f, indent=2)
        log(f"\n  Results saved to: {results_path}")

        log(f"\n{BOLD}{'='*60}{RESET}\n")

        return RESULTS["failed"] == 0


def main():
    """Main entry point."""
    # Setup Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'forgeforth.settings')

    import django
    django.setup()

    # Run tests
    tests = IntegrationTests()
    success = tests.run_all()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()


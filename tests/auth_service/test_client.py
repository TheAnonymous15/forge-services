# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Auth Service Client Tests
=============================================
Tests for the AuthClient library used by other services.

Run with: python -m pytest tests/auth_service/test_client.py -v
Or standalone: python tests/auth_service/test_client.py
"""
import sys
import os
import asyncio

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from auth_service.client import (
    AuthClient,
    AuthResponse,
    RequestSigner,
    ResponseVerifier,
    SecurityLevel,
)
from auth_service.config import config


class TestColors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_test(name: str, passed: bool, details: str = ""):
    status = f"{TestColors.GREEN}PASS{TestColors.RESET}" if passed else f"{TestColors.RED}FAIL{TestColors.RESET}"
    print(f"  [{status}] {name}")
    if details and not passed:
        print(f"         {TestColors.YELLOW}{details}{TestColors.RESET}")


def print_section(name: str):
    print(f"\n{TestColors.BLUE}{TestColors.BOLD}=== {name} ==={TestColors.RESET}")


class TestRequestSigner:
    """Test RequestSigner class."""

    def __init__(self):
        self.hmac_key = config.HMAC_SECRET_KEY
        self.service_name = 'talent'

    def test_signer_creation(self) -> bool:
        """Test signer can be created."""
        try:
            signer = RequestSigner(self.hmac_key, self.service_name)
            assert signer is not None
            assert signer.service_name == self.service_name
            return True
        except Exception as e:
            print(f"         Error: {e}")
            return False

    def test_sign_data(self) -> bool:
        """Test signing data."""
        try:
            signer = RequestSigner(self.hmac_key, self.service_name)
            signed = signer.sign({'test': 'data'}, SecurityLevel.HIGH)

            assert 'data' in signed
            assert 'meta' in signed
            assert signed['data']['test'] == 'data'
            assert 'signature' in signed['meta']
            assert 'request_id' in signed['meta']
            return True
        except Exception as e:
            print(f"         Error: {e}")
            return False

    def test_different_security_levels(self) -> bool:
        """Test different security levels produce different algorithms."""
        try:
            signer = RequestSigner(self.hmac_key, self.service_name)

            standard = signer.sign({'level': 'standard'}, SecurityLevel.STANDARD)
            high = signer.sign({'level': 'high'}, SecurityLevel.HIGH)
            quantum = signer.sign({'level': 'quantum'}, SecurityLevel.QUANTUM_SAFE)

            assert standard['meta']['algorithm'] == 'hmac-sha256'
            assert high['meta']['algorithm'] == 'hmac-sha512'
            assert quantum['meta']['algorithm'] == 'pq-hybrid-sha512'
            return True
        except Exception as e:
            print(f"         Error: {e}")
            return False

    def test_unique_request_ids(self) -> bool:
        """Test that each request gets unique ID."""
        try:
            signer = RequestSigner(self.hmac_key, self.service_name)

            ids = set()
            for _ in range(100):
                signed = signer.sign({'n': _}, SecurityLevel.STANDARD)
                ids.add(signed['meta']['request_id'])

            assert len(ids) == 100, "All request IDs should be unique"
            return True
        except Exception as e:
            print(f"         Error: {e}")
            return False

    def run_all(self) -> tuple:
        print_section("RequestSigner Tests")

        tests = [
            ("Signer creation", self.test_signer_creation),
            ("Sign data", self.test_sign_data),
            ("Different security levels", self.test_different_security_levels),
            ("Unique request IDs", self.test_unique_request_ids),
        ]

        passed = 0
        for name, test_fn in tests:
            result = test_fn()
            print_test(name, result)
            if result:
                passed += 1

        return passed, len(tests)


class TestResponseVerifier:
    """Test ResponseVerifier class."""

    def __init__(self):
        self.hmac_key = config.HMAC_SECRET_KEY
        self.service_id = config.SERVICE_ID

    def test_verifier_creation(self) -> bool:
        """Test verifier can be created."""
        try:
            verifier = ResponseVerifier(self.hmac_key, self.service_id)
            assert verifier is not None
            return True
        except Exception as e:
            print(f"         Error: {e}")
            return False

    def test_verify_valid_response(self) -> bool:
        """Test verification of valid response."""
        try:
            from auth_service.security import sign_response

            request_id = 'req_test_verify'
            signed = sign_response({'success': True}, request_id, SecurityLevel.HIGH)

            verifier = ResponseVerifier(self.hmac_key, self.service_id)
            is_valid, msg = verifier.verify(signed, request_id)

            assert is_valid, f"Verification failed: {msg}"
            return True
        except Exception as e:
            print(f"         Error: {e}")
            return False

    def test_reject_wrong_binding(self) -> bool:
        """Test rejection of wrong request binding."""
        try:
            from auth_service.security import sign_response

            signed = sign_response({'success': True}, 'req_original', SecurityLevel.HIGH)

            verifier = ResponseVerifier(self.hmac_key, self.service_id)
            is_valid, msg = verifier.verify(signed, 'req_different')

            assert not is_valid, "Should reject wrong binding"
            return True
        except Exception as e:
            print(f"         Error: {e}")
            return False

    def test_reject_wrong_service_id(self) -> bool:
        """Test rejection of response from wrong service."""
        try:
            from auth_service.security import sign_response

            signed = sign_response({'success': True}, 'req_test', SecurityLevel.HIGH)

            # Create verifier expecting different service ID
            verifier = ResponseVerifier(self.hmac_key, 'wrong-service-id')
            is_valid, msg = verifier.verify(signed, 'req_test')

            assert not is_valid, "Should reject wrong service ID"
            return True
        except Exception as e:
            print(f"         Error: {e}")
            return False

    def run_all(self) -> tuple:
        print_section("ResponseVerifier Tests")

        tests = [
            ("Verifier creation", self.test_verifier_creation),
            ("Verify valid response", self.test_verify_valid_response),
            ("Reject wrong request binding", self.test_reject_wrong_binding),
            ("Reject wrong service ID", self.test_reject_wrong_service_id),
        ]

        passed = 0
        for name, test_fn in tests:
            result = test_fn()
            print_test(name, result)
            if result:
                passed += 1

        return passed, len(tests)


class TestAuthClient:
    """Test AuthClient class."""

    def test_client_creation(self) -> bool:
        """Test client can be created."""
        try:
            client = AuthClient(
                service_name='talent',
                api_key='test_key',
                hmac_key=config.HMAC_SECRET_KEY,
                expected_service_id=config.SERVICE_ID,
                ssl_verify=False
            )
            assert client is not None
            assert client.service_name == 'talent'
            return True
        except Exception as e:
            print(f"         Error: {e}")
            return False

    def test_client_from_env(self) -> bool:
        """Test client can load config from environment."""
        try:
            # Set environment variables
            os.environ['TALENT_AUTH_KEY'] = 'test_talent_key'
            os.environ['AUTH_SERVICE_URL'] = 'https://localhost:9002'
            os.environ['AUTH_HMAC_SECRET'] = config.HMAC_SECRET_KEY
            os.environ['AUTH_SERVICE_ID'] = config.SERVICE_ID

            client = AuthClient(service_name='talent')

            assert client.api_key == 'test_talent_key'
            assert 'localhost:9002' in client.auth_url
            return True
        except Exception as e:
            print(f"         Error: {e}")
            return False

    def test_client_has_signer(self) -> bool:
        """Test client creates signer when HMAC key provided."""
        try:
            client = AuthClient(
                service_name='talent',
                hmac_key=config.HMAC_SECRET_KEY,
                expected_service_id=config.SERVICE_ID
            )
            assert client.signer is not None
            return True
        except Exception as e:
            print(f"         Error: {e}")
            return False

    def test_client_has_verifier(self) -> bool:
        """Test client creates verifier when HMAC key provided."""
        try:
            client = AuthClient(
                service_name='talent',
                hmac_key=config.HMAC_SECRET_KEY,
                expected_service_id=config.SERVICE_ID
            )
            assert client.verifier is not None
            return True
        except Exception as e:
            print(f"         Error: {e}")
            return False

    def test_auth_response_dataclass(self) -> bool:
        """Test AuthResponse dataclass."""
        try:
            response = AuthResponse(
                raw={'data': {'success': True, 'user': {'id': '123'}}},
                data={'success': True, 'user': {'id': '123'}},
                verified=True,
                success=True,
                request_id='req_123'
            )

            assert response.verified == True
            assert response.success == True
            assert response.is_authentic == True
            assert response.user['id'] == '123'
            assert response.requires_2fa == False
            return True
        except Exception as e:
            print(f"         Error: {e}")
            return False

    def test_auth_response_not_authentic(self) -> bool:
        """Test AuthResponse when not verified."""
        try:
            response = AuthResponse(
                raw={},
                data={'success': True},
                verified=False,
                success=True,
                error="Verification failed"
            )

            # Even if success=True, is_authentic should be False
            assert response.is_authentic == False
            return True
        except Exception as e:
            print(f"         Error: {e}")
            return False

    def run_all(self) -> tuple:
        print_section("AuthClient Tests")

        tests = [
            ("Client creation", self.test_client_creation),
            ("Client from environment", self.test_client_from_env),
            ("Client has signer", self.test_client_has_signer),
            ("Client has verifier", self.test_client_has_verifier),
            ("AuthResponse dataclass", self.test_auth_response_dataclass),
            ("AuthResponse not authentic check", self.test_auth_response_not_authentic),
        ]

        passed = 0
        for name, test_fn in tests:
            result = test_fn()
            print_test(name, result)
            if result:
                passed += 1

        return passed, len(tests)


def run_all_tests():
    """Run all client tests."""
    from datetime import datetime

    print(f"\n{TestColors.BOLD}{'='*60}")
    print("  FORGEFORTH AFRICA - AUTH CLIENT TESTS")
    print(f"{'='*60}{TestColors.RESET}")
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    total_passed = 0
    total_tests = 0

    test_classes = [
        TestRequestSigner(),
        TestResponseVerifier(),
        TestAuthClient(),
    ]

    for test_class in test_classes:
        passed, total = test_class.run_all()
        total_passed += passed
        total_tests += total

    print(f"\n{TestColors.BOLD}{'='*60}")
    print(f"  TEST SUMMARY")
    print(f"{'='*60}{TestColors.RESET}")

    pass_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0

    if total_passed == total_tests:
        print(f"  {TestColors.GREEN}ALL TESTS PASSED!{TestColors.RESET}")
    else:
        print(f"  {TestColors.RED}SOME TESTS FAILED{TestColors.RESET}")

    print(f"  Passed: {total_passed}/{total_tests} ({pass_rate:.1f}%)")
    print(f"{'='*60}\n")

    return total_passed == total_tests


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)


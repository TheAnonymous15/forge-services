# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Auth Service Security Tests
===============================================
Comprehensive tests for the mutual authentication security module.

Tests cover:
1. Request signing and verification
2. Response signing and verification
3. Tamper detection
4. Request-response binding
5. Replay attack prevention (nonce)
6. Timestamp validation
7. Post-quantum hybrid signatures
8. API key verification

Run with: python -m pytest tests/auth_service/test_security.py -v
Or standalone: python tests/auth_service/test_security.py
"""
import sys
import os
import copy
import time
from datetime import datetime, timezone, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from auth_service.security import (
    sign_request,
    verify_request,
    sign_response,
    verify_response,
    SecurityLevel,
    SignatureError,
    auth_manager,
)
from auth_service.config import config


class TestColors:
    """ANSI colors for terminal output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_test(name: str, passed: bool, details: str = ""):
    """Print test result."""
    status = f"{TestColors.GREEN}PASS{TestColors.RESET}" if passed else f"{TestColors.RED}FAIL{TestColors.RESET}"
    print(f"  [{status}] {name}")
    if details and not passed:
        print(f"         {TestColors.YELLOW}{details}{TestColors.RESET}")


def print_section(name: str):
    """Print section header."""
    print(f"\n{TestColors.BLUE}{TestColors.BOLD}=== {name} ==={TestColors.RESET}")


class TestRequestSigning:
    """Test request signing functionality."""

    def __init__(self):
        self.service_name = 'talent'
        self.api_key = config.SERVICE_API_KEYS.get('talent', 'tal_sk_5a6b7c8d9e0f1g2h3i4j5k6l7m8n9o0p')
        self.test_data = {'email': 'test@example.com', 'password': 'SecurePass123'}

    def test_sign_request_standard(self) -> bool:
        """Test standard security level signing."""
        try:
            signed = sign_request(self.test_data, self.service_name, self.api_key, SecurityLevel.STANDARD)
            assert 'data' in signed
            assert 'meta' in signed
            assert signed['meta']['algorithm'] == 'hmac-sha256'
            assert 'signature' in signed['meta']
            assert 'timestamp' in signed['meta']
            assert 'nonce' in signed['meta']
            assert 'request_id' in signed['meta']
            return True
        except Exception as e:
            print(f"         Error: {e}")
            return False

    def test_sign_request_high(self) -> bool:
        """Test high security level signing."""
        try:
            signed = sign_request(self.test_data, self.service_name, self.api_key, SecurityLevel.HIGH)
            assert signed['meta']['algorithm'] == 'hmac-sha512'
            return True
        except Exception as e:
            print(f"         Error: {e}")
            return False

    def test_sign_request_quantum(self) -> bool:
        """Test post-quantum security level signing."""
        try:
            signed = sign_request(self.test_data, self.service_name, self.api_key, SecurityLevel.QUANTUM_SAFE)
            assert signed['meta']['algorithm'] == 'pq-hybrid-sha512'
            return True
        except Exception as e:
            print(f"         Error: {e}")
            return False

    def test_invalid_api_key(self) -> bool:
        """Test that invalid API key is rejected."""
        try:
            sign_request(self.test_data, self.service_name, 'invalid_key', SecurityLevel.HIGH)
            return False  # Should have raised an error
        except SignatureError:
            return True
        except Exception as e:
            print(f"         Unexpected error: {e}")
            return False

    def test_unknown_service(self) -> bool:
        """Test that unknown service is rejected."""
        try:
            sign_request(self.test_data, 'unknown_service', 'some_key', SecurityLevel.HIGH)
            return False  # Should have raised an error
        except SignatureError:
            return True
        except Exception as e:
            print(f"         Unexpected error: {e}")
            return False

    def run_all(self) -> int:
        """Run all request signing tests."""
        print_section("Request Signing Tests")

        tests = [
            ("Standard security signing", self.test_sign_request_standard),
            ("High security signing (SHA-512)", self.test_sign_request_high),
            ("Post-quantum hybrid signing", self.test_sign_request_quantum),
            ("Invalid API key rejection", self.test_invalid_api_key),
            ("Unknown service rejection", self.test_unknown_service),
        ]

        passed = 0
        for name, test_fn in tests:
            result = test_fn()
            print_test(name, result)
            if result:
                passed += 1

        return passed, len(tests)


class TestRequestVerification:
    """Test request verification functionality."""

    def __init__(self):
        self.service_name = 'talent'
        self.api_key = config.SERVICE_API_KEYS.get('talent', 'tal_sk_5a6b7c8d9e0f1g2h3i4j5k6l7m8n9o0p')
        self.test_data = {'email': 'verify@example.com', 'action': 'login'}

    def test_verify_valid_request(self) -> bool:
        """Test verification of valid signed request."""
        try:
            signed = sign_request(self.test_data, self.service_name, self.api_key, SecurityLevel.HIGH)
            is_valid, msg, request_id = verify_request(signed)
            assert is_valid, f"Verification failed: {msg}"
            assert request_id == signed['meta']['request_id']
            return True
        except Exception as e:
            print(f"         Error: {e}")
            return False

    def test_detect_tampered_data(self) -> bool:
        """Test detection of tampered request data."""
        try:
            signed = sign_request(self.test_data, self.service_name, self.api_key, SecurityLevel.HIGH)

            # Tamper with the data
            tampered = copy.deepcopy(signed)
            tampered['data']['email'] = 'attacker@evil.com'

            is_valid, msg, _ = verify_request(tampered)
            assert not is_valid, "Tampered request should be rejected"
            return True
        except Exception as e:
            print(f"         Error: {e}")
            return False

    def test_detect_tampered_signature(self) -> bool:
        """Test detection of tampered signature."""
        try:
            signed = sign_request(self.test_data, self.service_name, self.api_key, SecurityLevel.HIGH)

            # Tamper with the signature
            tampered = copy.deepcopy(signed)
            tampered['meta']['signature'] = 'invalid_signature_' + tampered['meta']['signature'][20:]

            is_valid, msg, _ = verify_request(tampered)
            assert not is_valid, "Tampered signature should be rejected"
            return True
        except Exception as e:
            print(f"         Error: {e}")
            return False

    def test_nonce_replay_prevention(self) -> bool:
        """Test that same nonce cannot be used twice."""
        try:
            signed = sign_request(self.test_data, self.service_name, self.api_key, SecurityLevel.HIGH)

            # First verification should succeed
            is_valid1, _, _ = verify_request(signed)

            # Second verification with same nonce should fail
            is_valid2, msg, _ = verify_request(signed)

            assert is_valid1, "First verification should pass"
            assert not is_valid2, "Replay should be detected"
            assert "nonce" in msg.lower() or "replay" in msg.lower(), "Should mention nonce/replay"
            return True
        except Exception as e:
            print(f"         Error: {e}")
            return False

    def run_all(self) -> tuple:
        """Run all request verification tests."""
        print_section("Request Verification Tests")

        tests = [
            ("Verify valid signed request", self.test_verify_valid_request),
            ("Detect tampered data", self.test_detect_tampered_data),
            ("Detect tampered signature", self.test_detect_tampered_signature),
            ("Prevent nonce replay attack", self.test_nonce_replay_prevention),
        ]

        passed = 0
        for name, test_fn in tests:
            result = test_fn()
            print_test(name, result)
            if result:
                passed += 1

        return passed, len(tests)


class TestResponseSigning:
    """Test response signing functionality."""

    def test_sign_response_standard(self) -> bool:
        """Test standard response signing."""
        try:
            signed = sign_response({'success': True}, 'req_123', SecurityLevel.STANDARD)
            assert signed['meta']['algorithm'] == 'hmac-sha256'
            assert signed['meta']['request_id'] == 'req_123'
            return True
        except Exception as e:
            print(f"         Error: {e}")
            return False

    def test_sign_response_high(self) -> bool:
        """Test high security response signing."""
        try:
            signed = sign_response({'success': True, 'user': {'id': '456'}}, 'req_456', SecurityLevel.HIGH)
            assert signed['meta']['algorithm'] == 'hmac-sha512'
            return True
        except Exception as e:
            print(f"         Error: {e}")
            return False

    def test_sign_response_quantum(self) -> bool:
        """Test post-quantum response signing."""
        try:
            signed = sign_response({'quantum': True}, 'req_pq', SecurityLevel.QUANTUM_SAFE)
            assert signed['meta']['algorithm'] == 'pq-hybrid-sha512'
            return True
        except Exception as e:
            print(f"         Error: {e}")
            return False

    def test_response_contains_request_id(self) -> bool:
        """Test that response is bound to request ID."""
        try:
            request_id = 'req_binding_test_789'
            signed = sign_response({'success': True}, request_id, SecurityLevel.HIGH)
            assert signed['meta']['request_id'] == request_id
            return True
        except Exception as e:
            print(f"         Error: {e}")
            return False

    def run_all(self) -> tuple:
        """Run all response signing tests."""
        print_section("Response Signing Tests")

        tests = [
            ("Standard response signing", self.test_sign_response_standard),
            ("High security response signing", self.test_sign_response_high),
            ("Post-quantum response signing", self.test_sign_response_quantum),
            ("Response bound to request ID", self.test_response_contains_request_id),
        ]

        passed = 0
        for name, test_fn in tests:
            result = test_fn()
            print_test(name, result)
            if result:
                passed += 1

        return passed, len(tests)


class TestResponseVerification:
    """Test response verification functionality."""

    def test_verify_valid_response(self) -> bool:
        """Test verification of valid response."""
        try:
            request_id = 'req_valid_resp_test'
            signed = sign_response({'success': True}, request_id, SecurityLevel.HIGH)

            is_valid, data = verify_response(signed, request_id)
            assert is_valid, f"Verification failed: {data}"
            assert data['success'] == True
            return True
        except Exception as e:
            print(f"         Error: {e}")
            return False

    def test_detect_tampered_response(self) -> bool:
        """Test detection of tampered response data."""
        try:
            request_id = 'req_tamper_test'
            signed = sign_response({'success': True, 'user': {'id': '123'}}, request_id, SecurityLevel.HIGH)

            # Tamper with response data
            tampered = copy.deepcopy(signed)
            tampered['data']['success'] = False

            is_valid, result = verify_response(tampered, request_id)
            assert not is_valid, "Tampered response should be rejected"
            return True
        except Exception as e:
            print(f"         Error: {e}")
            return False

    def test_wrong_request_binding(self) -> bool:
        """Test that response cannot be used for different request."""
        try:
            signed = sign_response({'success': True}, 'req_original', SecurityLevel.HIGH)

            # Try to verify with different request ID
            is_valid, result = verify_response(signed, 'req_different')
            assert not is_valid, "Wrong binding should be rejected"
            assert 'error' in result
            return True
        except Exception as e:
            print(f"         Error: {e}")
            return False

    def test_response_nonce_replay(self) -> bool:
        """Test that response cannot be replayed."""
        try:
            request_id = 'req_replay_test'
            signed = sign_response({'success': True}, request_id, SecurityLevel.HIGH)

            # First verification
            is_valid1, _ = verify_response(signed, request_id)

            # Second verification (replay attempt)
            is_valid2, result = verify_response(signed, request_id)

            assert is_valid1, "First verification should pass"
            assert not is_valid2, "Replay should be detected"
            return True
        except Exception as e:
            print(f"         Error: {e}")
            return False

    def test_verify_quantum_response(self) -> bool:
        """Test verification of post-quantum signed response."""
        try:
            request_id = 'req_pq_verify'
            signed = sign_response({'quantum_safe': True}, request_id, SecurityLevel.QUANTUM_SAFE)

            is_valid, data = verify_response(signed, request_id)
            assert is_valid, "PQ response verification should pass"
            assert data['quantum_safe'] == True
            return True
        except Exception as e:
            print(f"         Error: {e}")
            return False

    def run_all(self) -> tuple:
        """Run all response verification tests."""
        print_section("Response Verification Tests")

        tests = [
            ("Verify valid response", self.test_verify_valid_response),
            ("Detect tampered response", self.test_detect_tampered_response),
            ("Reject wrong request binding", self.test_wrong_request_binding),
            ("Prevent response replay", self.test_response_nonce_replay),
            ("Verify post-quantum response", self.test_verify_quantum_response),
        ]

        passed = 0
        for name, test_fn in tests:
            result = test_fn()
            print_test(name, result)
            if result:
                passed += 1

        return passed, len(tests)


class TestEndToEndSecurity:
    """Test complete request-response flow."""

    def __init__(self):
        self.service_name = 'talent'
        self.api_key = config.SERVICE_API_KEYS.get('talent', 'tal_sk_5a6b7c8d9e0f1g2h3i4j5k6l7m8n9o0p')

    def test_full_auth_flow(self) -> bool:
        """Test complete authentication flow with mutual auth."""
        try:
            # 1. Client signs request
            request_data = {'email': 'user@example.com', 'password': 'pass123', 'role': 'talent'}
            signed_request = sign_request(request_data, self.service_name, self.api_key, SecurityLevel.HIGH)

            # 2. Server verifies request
            is_valid, msg, request_id = verify_request(signed_request)
            assert is_valid, f"Request verification failed: {msg}"

            # 3. Server processes and signs response
            response_data = {'success': True, 'user': {'id': 'user_123', 'email': 'user@example.com'}}
            signed_response = sign_response(response_data, request_id, SecurityLevel.HIGH)

            # 4. Client verifies response
            is_valid, data = verify_response(signed_response, request_id)
            assert is_valid, "Response verification failed"
            assert data['success'] == True
            assert data['user']['id'] == 'user_123'

            return True
        except Exception as e:
            print(f"         Error: {e}")
            return False

    def test_attacker_cannot_forge_request(self) -> bool:
        """Test that attacker cannot forge a valid request."""
        try:
            # Attacker tries to create request without valid API key
            try:
                sign_request({'evil': 'data'}, 'talent', 'fake_api_key', SecurityLevel.HIGH)
                return False  # Should have failed
            except SignatureError:
                pass  # Expected

            # Attacker tries to modify a captured request
            valid_request = sign_request({'legit': 'data'}, self.service_name, self.api_key, SecurityLevel.HIGH)

            # Modify and try to verify
            modified = copy.deepcopy(valid_request)
            modified['data']['evil'] = 'injection'

            is_valid, _, _ = verify_request(modified)
            assert not is_valid, "Modified request should be rejected"

            return True
        except Exception as e:
            print(f"         Error: {e}")
            return False

    def test_attacker_cannot_forge_response(self) -> bool:
        """Test that attacker cannot forge a valid response."""
        try:
            request_id = 'req_attacker_test'

            # Legitimate response
            legit_response = sign_response({'success': False, 'error': 'Invalid'}, request_id, SecurityLevel.HIGH)

            # Attacker intercepts and modifies
            forged = copy.deepcopy(legit_response)
            forged['data']['success'] = True
            forged['data']['user'] = {'id': 'attacker', 'role': 'admin'}

            # Verification should fail
            is_valid, _ = verify_response(forged, request_id)
            assert not is_valid, "Forged response should be rejected"

            return True
        except Exception as e:
            print(f"         Error: {e}")
            return False

    def test_attacker_cannot_replay_response(self) -> bool:
        """Test that attacker cannot replay a response to different request."""
        try:
            # Original flow
            orig_request = sign_request({'action': 'get_balance'}, self.service_name, self.api_key, SecurityLevel.HIGH)
            _, _, orig_request_id = verify_request(orig_request)

            orig_response = sign_response({'balance': 1000}, orig_request_id, SecurityLevel.HIGH)
            is_valid, data = verify_response(orig_response, orig_request_id)
            assert is_valid and data['balance'] == 1000

            # Attacker captures response, tries to replay for new request
            new_request = sign_request({'action': 'get_balance'}, self.service_name, self.api_key, SecurityLevel.HIGH)
            _, _, new_request_id = verify_request(new_request)

            # Try to use old response for new request
            is_valid, _ = verify_response(orig_response, new_request_id)
            assert not is_valid, "Replayed response should be rejected (wrong binding)"

            return True
        except Exception as e:
            print(f"         Error: {e}")
            return False

    def run_all(self) -> tuple:
        """Run all end-to-end security tests."""
        print_section("End-to-End Security Tests")

        tests = [
            ("Complete auth flow with mutual auth", self.test_full_auth_flow),
            ("Attacker cannot forge request", self.test_attacker_cannot_forge_request),
            ("Attacker cannot forge response", self.test_attacker_cannot_forge_response),
            ("Attacker cannot replay response", self.test_attacker_cannot_replay_response),
        ]

        passed = 0
        for name, test_fn in tests:
            result = test_fn()
            print_test(name, result)
            if result:
                passed += 1

        return passed, len(tests)


class TestAPIKeyVerification:
    """Test API key verification."""

    def test_valid_api_key(self) -> bool:
        """Test valid API key verification."""
        try:
            for service_name, api_key in config.SERVICE_API_KEYS.items():
                result = auth_manager.verify_api_key(api_key, service_name)
                assert result, f"Valid key for {service_name} should pass"
            return True
        except Exception as e:
            print(f"         Error: {e}")
            return False

    def test_invalid_api_key(self) -> bool:
        """Test invalid API key rejection."""
        try:
            result = auth_manager.verify_api_key('invalid_key', 'talent')
            assert not result, "Invalid key should be rejected"
            return True
        except Exception as e:
            print(f"         Error: {e}")
            return False

    def test_wrong_service_key_combo(self) -> bool:
        """Test that keys cannot be used for wrong service."""
        try:
            talent_key = config.SERVICE_API_KEYS.get('talent', '')
            result = auth_manager.verify_api_key(talent_key, 'admin')
            assert not result, "Key should not work for different service"
            return True
        except Exception as e:
            print(f"         Error: {e}")
            return False

    def run_all(self) -> tuple:
        """Run all API key tests."""
        print_section("API Key Verification Tests")

        tests = [
            ("Valid API key accepted", self.test_valid_api_key),
            ("Invalid API key rejected", self.test_invalid_api_key),
            ("Wrong service-key combo rejected", self.test_wrong_service_key_combo),
        ]

        passed = 0
        for name, test_fn in tests:
            result = test_fn()
            print_test(name, result)
            if result:
                passed += 1

        return passed, len(tests)


def run_all_tests():
    """Run all security tests."""
    print(f"\n{TestColors.BOLD}{'='*60}")
    print("  FORGEFORTH AFRICA - AUTH SERVICE SECURITY TESTS")
    print(f"{'='*60}{TestColors.RESET}")
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Service ID: {config.SERVICE_ID}")

    total_passed = 0
    total_tests = 0

    # Run all test classes
    test_classes = [
        TestRequestSigning(),
        TestRequestVerification(),
        TestResponseSigning(),
        TestResponseVerification(),
        TestEndToEndSecurity(),
        TestAPIKeyVerification(),
    ]

    for test_class in test_classes:
        passed, total = test_class.run_all()
        total_passed += passed
        total_tests += total

    # Print summary
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


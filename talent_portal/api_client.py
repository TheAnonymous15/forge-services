# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Talent Portal API Client
=============================================
HTTP client for communicating with the main API.
"""
import logging
import httpx
from typing import Optional, Dict, Any, Tuple
from .config import config

logger = logging.getLogger('talent_portal.api_client')


class APIClient:
    """API client for the main ForgeForth API."""

    def __init__(self):
        self.base_url = config.API_BASE_URL
        self.timeout = 30.0

    def _headers(self, access_token: Optional[str] = None) -> Dict[str, str]:
        """Build request headers."""
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        if access_token:
            headers['Authorization'] = f'Bearer {access_token}'
        return headers

    async def _request(
        self,
        method: str,
        endpoint: str,
        access_token: Optional[str] = None,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Tuple[Dict[str, Any], int]:
        """Make an HTTP request to the API."""
        url = f"{self.base_url}{endpoint}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=self._headers(access_token),
                    json=data,
                    params=params
                )

                try:
                    result = response.json()
                except Exception:
                    result = {'raw': response.text}

                return result, response.status_code

        except httpx.TimeoutException:
            logger.error(f"Request timeout: {method} {url}")
            return {'error': 'Request timed out'}, 504

        except Exception as e:
            logger.error(f"Request error: {method} {url} - {e}")
            return {'error': str(e)}, 500

    # =========================================================================
    # PROFILE ENDPOINTS
    # =========================================================================

    async def get_profile(self, access_token: str) -> Optional[Dict]:
        """Get current user's profile."""
        result, status = await self._request('GET', '/api/v1/profiles/me', access_token)
        return result if status == 200 else None

    async def get_profile_completion(self, access_token: str) -> Optional[Dict]:
        """Get profile completion status."""
        result, status = await self._request('GET', '/api/v1/profiles/me/completion', access_token)
        return result if status == 200 else None

    async def update_profile(self, access_token: str, data: Dict) -> Tuple[Dict, int]:
        """Update profile."""
        return await self._request('PATCH', '/api/v1/profiles/me', access_token, data)

    async def upload_photo(self, access_token: str, file_data: bytes, filename: str) -> Tuple[Dict, int]:
        """Upload profile photo."""
        url = f"{self.base_url}/api/v1/profiles/me/photo"
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                files = {'photo': (filename, file_data)}
                headers = {'Authorization': f'Bearer {access_token}'}
                response = await client.post(url, files=files, headers=headers)
                return response.json(), response.status_code
        except Exception as e:
            logger.error(f"Photo upload error: {e}")
            return {'error': str(e)}, 500

    # =========================================================================
    # SKILLS ENDPOINTS
    # =========================================================================

    async def get_skills(self, access_token: str) -> list:
        """Get user's skills."""
        result, status = await self._request('GET', '/api/v1/profiles/me/skills', access_token)
        return result.get('results', []) if status == 200 else []

    async def add_skill(self, access_token: str, data: Dict) -> Tuple[Dict, int]:
        """Add a skill."""
        return await self._request('POST', '/api/v1/profiles/me/skills', access_token, data)

    async def update_skill(self, access_token: str, skill_id: str, data: Dict) -> Tuple[Dict, int]:
        """Update a skill."""
        return await self._request('PUT', f'/api/v1/profiles/me/skills/{skill_id}', access_token, data)

    async def delete_skill(self, access_token: str, skill_id: str) -> Tuple[Dict, int]:
        """Delete a skill."""
        return await self._request('DELETE', f'/api/v1/profiles/me/skills/{skill_id}', access_token)

    async def bulk_add_skills(self, access_token: str, skills: list) -> Tuple[Dict, int]:
        """Bulk add skills."""
        return await self._request('POST', '/api/v1/profiles/me/skills/bulk', access_token, {'skills': skills})

    # =========================================================================
    # EXPERIENCE ENDPOINTS
    # =========================================================================

    async def get_experience(self, access_token: str) -> list:
        """Get work experience."""
        result, status = await self._request('GET', '/api/v1/profiles/me/experience', access_token)
        return result.get('results', []) if status == 200 else []

    async def add_experience(self, access_token: str, data: Dict) -> Tuple[Dict, int]:
        """Add work experience."""
        return await self._request('POST', '/api/v1/profiles/me/experience', access_token, data)

    async def update_experience(self, access_token: str, exp_id: str, data: Dict) -> Tuple[Dict, int]:
        """Update work experience."""
        return await self._request('PUT', f'/api/v1/profiles/me/experience/{exp_id}', access_token, data)

    async def delete_experience(self, access_token: str, exp_id: str) -> Tuple[Dict, int]:
        """Delete work experience."""
        return await self._request('DELETE', f'/api/v1/profiles/me/experience/{exp_id}', access_token)

    # =========================================================================
    # EDUCATION ENDPOINTS
    # =========================================================================

    async def get_education(self, access_token: str) -> list:
        """Get education entries."""
        result, status = await self._request('GET', '/api/v1/profiles/me/education', access_token)
        return result.get('results', []) if status == 200 else []

    async def add_education(self, access_token: str, data: Dict) -> Tuple[Dict, int]:
        """Add education entry."""
        return await self._request('POST', '/api/v1/profiles/me/education', access_token, data)

    async def update_education(self, access_token: str, edu_id: str, data: Dict) -> Tuple[Dict, int]:
        """Update education entry."""
        return await self._request('PUT', f'/api/v1/profiles/me/education/{edu_id}', access_token, data)

    async def delete_education(self, access_token: str, edu_id: str) -> Tuple[Dict, int]:
        """Delete education entry."""
        return await self._request('DELETE', f'/api/v1/profiles/me/education/{edu_id}', access_token)

    # =========================================================================
    # CERTIFICATIONS ENDPOINTS
    # =========================================================================

    async def get_certifications(self, access_token: str) -> list:
        """Get certifications."""
        result, status = await self._request('GET', '/api/v1/profiles/me/certifications', access_token)
        return result.get('results', []) if status == 200 else []

    async def add_certification(self, access_token: str, data: Dict) -> Tuple[Dict, int]:
        """Add certification."""
        return await self._request('POST', '/api/v1/profiles/me/certifications', access_token, data)

    async def update_certification(self, access_token: str, cert_id: str, data: Dict) -> Tuple[Dict, int]:
        """Update certification."""
        return await self._request('PUT', f'/api/v1/profiles/me/certifications/{cert_id}', access_token, data)

    async def delete_certification(self, access_token: str, cert_id: str) -> Tuple[Dict, int]:
        """Delete certification."""
        return await self._request('DELETE', f'/api/v1/profiles/me/certifications/{cert_id}', access_token)

    # =========================================================================
    # LANGUAGES ENDPOINTS
    # =========================================================================

    async def get_languages(self, access_token: str) -> list:
        """Get languages."""
        result, status = await self._request('GET', '/api/v1/profiles/me/languages', access_token)
        return result.get('results', []) if status == 200 else []

    async def add_language(self, access_token: str, data: Dict) -> Tuple[Dict, int]:
        """Add language."""
        return await self._request('POST', '/api/v1/profiles/me/languages', access_token, data)

    async def delete_language(self, access_token: str, lang_id: str) -> Tuple[Dict, int]:
        """Delete language."""
        return await self._request('DELETE', f'/api/v1/profiles/me/languages/{lang_id}', access_token)

    # =========================================================================
    # PORTFOLIO ENDPOINTS
    # =========================================================================

    async def get_portfolio(self, access_token: str) -> list:
        """Get portfolio items."""
        result, status = await self._request('GET', '/api/v1/profiles/me/portfolio', access_token)
        return result.get('results', []) if status == 200 else []

    async def add_portfolio_item(self, access_token: str, data: Dict) -> Tuple[Dict, int]:
        """Add portfolio item."""
        return await self._request('POST', '/api/v1/profiles/me/portfolio', access_token, data)

    async def delete_portfolio_item(self, access_token: str, item_id: str) -> Tuple[Dict, int]:
        """Delete portfolio item."""
        return await self._request('DELETE', f'/api/v1/profiles/me/portfolio/{item_id}', access_token)

    # =========================================================================
    # OPPORTUNITIES ENDPOINTS
    # =========================================================================

    async def search_opportunities(
        self,
        access_token: str,
        query: Optional[str] = None,
        location: Optional[str] = None,
        job_type: Optional[str] = None,
        industry: Optional[str] = None,
        page: int = 1
    ) -> Dict:
        """Search opportunities."""
        params = {'page': page}
        if query:
            params['search'] = query
        if location:
            params['location'] = location
        if job_type:
            params['opportunity_type'] = job_type
        if industry:
            params['industry'] = industry

        result, status = await self._request(
            'GET', '/api/v1/organizations/opportunities',
            access_token, params=params
        )
        return result if status == 200 else {'results': [], 'count': 0}

    async def get_opportunity(self, access_token: str, opportunity_id: str) -> Optional[Dict]:
        """Get opportunity details."""
        result, status = await self._request(
            'GET', f'/api/v1/organizations/opportunities/{opportunity_id}',
            access_token
        )
        return result if status == 200 else None

    async def save_opportunity(self, access_token: str, opportunity_id: str) -> Tuple[Dict, int]:
        """Save an opportunity."""
        return await self._request(
            'POST', '/api/v1/applications/saved',
            access_token, {'opportunity_id': opportunity_id}
        )

    async def unsave_opportunity(self, access_token: str, saved_id: str) -> Tuple[Dict, int]:
        """Remove saved opportunity."""
        return await self._request('DELETE', f'/api/v1/applications/saved/{saved_id}', access_token)

    async def get_saved_opportunities(self, access_token: str) -> list:
        """Get saved opportunities."""
        result, status = await self._request('GET', '/api/v1/applications/saved', access_token)
        return result.get('results', []) if status == 200 else []

    # =========================================================================
    # APPLICATIONS ENDPOINTS
    # =========================================================================

    async def get_my_applications(self, access_token: str, page: int = 1) -> Dict:
        """Get my applications."""
        result, status = await self._request(
            'GET', '/api/v1/applications/my',
            access_token, params={'page': page}
        )
        return result if status == 200 else {'results': [], 'count': 0}

    async def get_application(self, access_token: str, application_id: str) -> Optional[Dict]:
        """Get application details."""
        result, status = await self._request(
            'GET', f'/api/v1/applications/{application_id}',
            access_token
        )
        return result if status == 200 else None

    async def get_application_stats(self, access_token: str) -> Dict:
        """Get application statistics."""
        result, status = await self._request('GET', '/api/v1/applications/my/stats', access_token)
        return result if status == 200 else {}

    async def create_application(self, access_token: str, data: Dict) -> Tuple[Dict, int]:
        """Create a new application."""
        return await self._request('POST', '/api/v1/applications/create', access_token, data)

    async def submit_application(self, access_token: str, application_id: str) -> Tuple[Dict, int]:
        """Submit an application."""
        return await self._request('POST', f'/api/v1/applications/{application_id}/submit', access_token)

    async def withdraw_application(self, access_token: str, application_id: str) -> Tuple[Dict, int]:
        """Withdraw an application."""
        return await self._request('POST', f'/api/v1/applications/{application_id}/withdraw', access_token)

    async def get_application_history(self, access_token: str, application_id: str) -> list:
        """Get application status history."""
        result, status = await self._request(
            'GET', f'/api/v1/applications/{application_id}/history',
            access_token
        )
        return result.get('results', []) if status == 200 else []

    # =========================================================================
    # MATCHES ENDPOINTS
    # =========================================================================

    async def get_matches(self, access_token: str, page: int = 1) -> Dict:
        """Get recommended matches."""
        result, status = await self._request(
            'GET', '/api/v1/matching/recommendations',
            access_token, params={'page': page}
        )
        return result if status == 200 else {'results': [], 'count': 0}

    # =========================================================================
    # NOTIFICATIONS ENDPOINTS
    # =========================================================================

    async def get_notifications(self, access_token: str, unread_only: bool = False) -> list:
        """Get notifications."""
        params = {'unread': 'true'} if unread_only else {}
        result, status = await self._request(
            'GET', '/api/v1/communications/notifications',
            access_token, params=params
        )
        return result.get('results', []) if status == 200 else []

    async def mark_notification_read(self, access_token: str, notification_id: str) -> Tuple[Dict, int]:
        """Mark notification as read."""
        return await self._request(
            'POST', f'/api/v1/communications/notifications/{notification_id}/read',
            access_token
        )

    # =========================================================================
    # SETTINGS ENDPOINTS
    # =========================================================================

    async def change_password(self, access_token: str, current: str, new: str) -> Tuple[Dict, int]:
        """Change password."""
        return await self._request(
            'POST', '/api/v1/auth/password/change',
            access_token, {'current_password': current, 'new_password': new}
        )

    async def update_privacy_settings(self, access_token: str, data: Dict) -> Tuple[Dict, int]:
        """Update privacy settings."""
        return await self._request('PATCH', '/api/v1/profiles/me', access_token, data)

    async def deactivate_account(self, access_token: str, password: str) -> Tuple[Dict, int]:
        """Deactivate account."""
        return await self._request(
            'POST', '/api/v1/auth/deactivate',
            access_token, {'password': password}
        )

    async def delete_account(self, access_token: str, password: str) -> Tuple[Dict, int]:
        """Delete account."""
        return await self._request(
            'POST', '/api/v1/auth/delete',
            access_token, {'password': password}
        )

    # =========================================================================
    # 2FA ENDPOINTS
    # =========================================================================

    async def enable_2fa(self, access_token: str) -> Tuple[Dict, int]:
        """Enable 2FA - get QR code."""
        return await self._request('POST', '/api/v1/auth/2fa/enable', access_token)

    async def confirm_2fa(self, access_token: str, code: str) -> Tuple[Dict, int]:
        """Confirm 2FA setup."""
        return await self._request('POST', '/api/v1/auth/2fa/confirm', access_token, {'code': code})

    async def disable_2fa(self, access_token: str, password: str) -> Tuple[Dict, int]:
        """Disable 2FA."""
        return await self._request('POST', '/api/v1/auth/2fa/disable', access_token, {'password': password})


# Singleton instance
api_client = APIClient()


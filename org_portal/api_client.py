# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Organization Portal API Client
=================================================
Client for communicating with the main Django API.
"""
import logging
from typing import Dict, Any, Optional, List
import httpx
from fastapi import UploadFile

from .config import config

logger = logging.getLogger('org_portal.api_client')


class APIClient:
    """Client for main Django API."""

    def __init__(self):
        self.base_url = config.API_BASE_URL.rstrip('/')
        self.timeout = 15

    def _headers(self, token: str) -> Dict:
        """Build headers with auth token."""
        return {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }

    # =========================================================================
    # ORGANIZATION
    # =========================================================================

    async def get_my_organization(self, token: str) -> Dict:
        """Get current user's organization."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/organizations/me/",
                headers=self._headers(token),
                timeout=self.timeout
            )
            if response.status_code == 200:
                return response.json()
            return {}

    async def update_organization(self, token: str, data: Dict) -> Dict:
        """Update organization profile."""
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{self.base_url}/organizations/me/",
                headers=self._headers(token),
                json=data,
                timeout=self.timeout
            )
            return response.json()

    async def upload_organization_logo(self, token: str, file: UploadFile) -> Dict:
        """Upload organization logo."""
        async with httpx.AsyncClient() as client:
            files = {'logo': (file.filename, await file.read(), file.content_type)}
            response = await client.post(
                f"{self.base_url}/organizations/me/logo/",
                headers={'Authorization': f'Bearer {token}'},
                files=files,
                timeout=self.timeout
            )
            return response.json()

    async def get_organization_stats(self, token: str) -> Dict:
        """Get organization statistics."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/organizations/me/stats/",
                headers=self._headers(token),
                timeout=self.timeout
            )
            if response.status_code == 200:
                return response.json()
            return {
                'total_opportunities': 0,
                'active_opportunities': 0,
                'total_applications': 0,
                'pending_review': 0
            }

    # =========================================================================
    # OPPORTUNITIES
    # =========================================================================

    async def get_organization_opportunities(
        self,
        token: str,
        status: str = '',
        search: str = '',
        page: int = 1
    ) -> Dict:
        """Get organization's opportunities."""
        async with httpx.AsyncClient() as client:
            params = {'page': page}
            if status:
                params['status'] = status
            if search:
                params['search'] = search

            response = await client.get(
                f"{self.base_url}/organizations/opportunities/",
                headers=self._headers(token),
                params=params,
                timeout=self.timeout
            )
            if response.status_code == 200:
                return response.json()
            return {'results': [], 'count': 0}

    async def get_opportunity(self, token: str, opportunity_id: str) -> Dict:
        """Get single opportunity."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/organizations/opportunities/{opportunity_id}/",
                headers=self._headers(token),
                timeout=self.timeout
            )
            if response.status_code == 200:
                return response.json()
            raise Exception("Opportunity not found")

    async def create_opportunity(self, token: str, data: Dict) -> Dict:
        """Create new opportunity."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/organizations/opportunities/",
                headers=self._headers(token),
                json=data,
                timeout=self.timeout
            )
            return response.json()

    async def update_opportunity(self, token: str, opportunity_id: str, data: Dict) -> Dict:
        """Update opportunity."""
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{self.base_url}/organizations/opportunities/{opportunity_id}/",
                headers=self._headers(token),
                json=data,
                timeout=self.timeout
            )
            return response.json()

    async def delete_opportunity(self, token: str, opportunity_id: str) -> bool:
        """Delete opportunity."""
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.base_url}/organizations/opportunities/{opportunity_id}/",
                headers=self._headers(token),
                timeout=self.timeout
            )
            return response.status_code == 204

    # =========================================================================
    # APPLICATIONS
    # =========================================================================

    async def get_received_applications(
        self,
        token: str,
        status: str = '',
        opportunity_id: str = '',
        page: int = 1
    ) -> Dict:
        """Get applications received by organization."""
        async with httpx.AsyncClient() as client:
            params = {'page': page}
            if status:
                params['status'] = status
            if opportunity_id:
                params['opportunity'] = opportunity_id

            response = await client.get(
                f"{self.base_url}/applications/received/",
                headers=self._headers(token),
                params=params,
                timeout=self.timeout
            )
            if response.status_code == 200:
                return response.json()
            return {'results': [], 'count': 0}

    async def get_opportunity_applications(self, token: str, opportunity_id: str) -> Dict:
        """Get applications for a specific opportunity."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/organizations/opportunities/{opportunity_id}/applications/",
                headers=self._headers(token),
                timeout=self.timeout
            )
            if response.status_code == 200:
                return response.json()
            return {'results': [], 'count': 0}

    async def get_application(self, token: str, application_id: str) -> Dict:
        """Get single application."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/applications/{application_id}/",
                headers=self._headers(token),
                timeout=self.timeout
            )
            if response.status_code == 200:
                return response.json()
            raise Exception("Application not found")

    async def update_application_status(
        self,
        token: str,
        application_id: str,
        status: str,
        notes: str = ''
    ) -> Dict:
        """Update application status."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/applications/{application_id}/status/",
                headers=self._headers(token),
                json={'status': status, 'notes': notes},
                timeout=self.timeout
            )
            return response.json()

    async def save_application_notes(self, token: str, application_id: str, notes: str) -> Dict:
        """Save notes for application."""
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{self.base_url}/applications/{application_id}/",
                headers=self._headers(token),
                json={'reviewer_notes': notes},
                timeout=self.timeout
            )
            return response.json()

    async def get_candidate_profile(self, token: str, talent_id: str) -> Dict:
        """Get candidate's profile."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/profiles/{talent_id}/",
                headers=self._headers(token),
                timeout=self.timeout
            )
            if response.status_code == 200:
                return response.json()
            return {}

    # =========================================================================
    # TEAM
    # =========================================================================

    async def get_team_members(self, token: str) -> List[Dict]:
        """Get organization team members."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/organizations/me/team/",
                headers=self._headers(token),
                timeout=self.timeout
            )
            if response.status_code == 200:
                return response.json()
            return []

    async def get_pending_invites(self, token: str) -> List[Dict]:
        """Get pending team invites."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/organizations/me/invites/",
                headers=self._headers(token),
                timeout=self.timeout
            )
            if response.status_code == 200:
                return response.json()
            return []

    async def invite_team_member(self, token: str, email: str, role: str) -> Dict:
        """Invite new team member."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/organizations/me/invites/",
                headers=self._headers(token),
                json={'email': email, 'role': role},
                timeout=self.timeout
            )
            return response.json()

    async def remove_team_member(self, token: str, member_id: str) -> bool:
        """Remove team member."""
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.base_url}/organizations/me/team/{member_id}/",
                headers=self._headers(token),
                timeout=self.timeout
            )
            return response.status_code == 204


# Singleton instance
api_client = APIClient()


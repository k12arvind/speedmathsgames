#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
google_auth.py

Google OAuth 2.0 authentication handler for the CLAT preparation app.
Handles login flow, token exchange, and user info verification.
"""

import os
import json
from typing import Dict, Optional, Tuple
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from google_auth_oauthlib.flow import Flow
import secrets


class GoogleAuth:
    """Google OAuth 2.0 authentication handler."""

    def __init__(self):
        """Initialize Google Auth with client configuration."""
        self.client_id = os.getenv('GOOGLE_CLIENT_ID')
        self.client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
        self.redirect_uri = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:8001/auth/google/callback')

        if not self.client_id or not self.client_secret:
            raise ValueError("GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set in environment")

        # OAuth scopes
        self.scopes = [
            'openid',
            'https://www.googleapis.com/auth/userinfo.email',
            'https://www.googleapis.com/auth/userinfo.profile'
        ]

        # Client configuration
        self.client_config = {
            "web": {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [self.redirect_uri]
            }
        }

    def get_authorization_url(self) -> Tuple[str, str]:
        """
        Generate Google OAuth authorization URL.

        Returns:
            Tuple of (authorization_url, state)
        """
        flow = Flow.from_client_config(
            self.client_config,
            scopes=self.scopes,
            redirect_uri=self.redirect_uri
        )

        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='select_account'
        )

        return authorization_url, state

    def exchange_code_for_token(self, code: str, state: str) -> Tuple[Dict, any]:
        """
        Exchange authorization code for access token and user info.

        Args:
            code: Authorization code from callback
            state: State parameter for CSRF protection

        Returns:
            Tuple of (user_info dict, credentials object)
        """
        flow = Flow.from_client_config(
            self.client_config,
            scopes=self.scopes,
            redirect_uri=self.redirect_uri,
            state=state
        )

        flow.fetch_token(code=code)
        credentials = flow.credentials

        # Get user info from ID token
        user_info = self.verify_token(credentials.id_token)

        return user_info, credentials

    def verify_token(self, token: str) -> Dict:
        """
        Verify Google ID token and extract user info.

        Args:
            token: Google ID token

        Returns:
            Dictionary with user info (google_id, email, name, picture)
        """
        try:
            idinfo = id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                self.client_id
            )

            # Extract user information
            user_info = {
                'google_id': idinfo['sub'],
                'email': idinfo['email'],
                'name': idinfo.get('name', ''),
                'picture': idinfo.get('picture', ''),
                'email_verified': idinfo.get('email_verified', False)
            }

            return user_info

        except ValueError as e:
            raise ValueError(f"Invalid token: {str(e)}")

    @staticmethod
    def generate_session_token() -> str:
        """
        Generate a secure random session token.

        Returns:
            64-character hex session token
        """
        return secrets.token_hex(32)

    @staticmethod
    def generate_state_token() -> str:
        """
        Generate a secure random state token for CSRF protection.

        Returns:
            32-character hex state token
        """
        return secrets.token_hex(16)


if __name__ == '__main__':
    # Quick test
    print("Google Auth Module")
    print("=" * 60)

    try:
        auth = GoogleAuth()
        print("✅ Google Auth initialized successfully")
        print(f"Client ID: {auth.client_id[:20]}...")
        print(f"Redirect URI: {auth.redirect_uri}")

        # Generate auth URL
        auth_url, state = auth.get_authorization_url()
        print(f"\n🔗 Authorization URL generated")
        print(f"State: {state}")

    except ValueError as e:
        print(f"❌ Error: {e}")
        print("\nMake sure to set environment variables:")
        print("  export GOOGLE_CLIENT_ID='your_client_id'")
        print("  export GOOGLE_CLIENT_SECRET='your_client_secret'")

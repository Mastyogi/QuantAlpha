"""
OAuth2 provider integrations.

Supports:
  - Google OAuth2 (openid, email, profile)
  - GitHub OAuth (user:email)

Both use the standard authorization-code flow with PKCE-style state verification.
When credentials are not configured, falls back to demo/dev mode.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import urllib.parse
from typing import Optional, Dict, Tuple

import requests


GOOGLE_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USER_URL  = "https://www.googleapis.com/oauth2/v3/userinfo"

GITHUB_AUTH_URL  = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL  = "https://api.github.com/user"
GITHUB_EMAIL_URL = "https://api.github.com/user/emails"


class OAuthProvider:
    """Base OAuth2 provider."""

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id     = client_id
        self.client_secret = client_secret
        self.redirect_uri  = redirect_uri

    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def generate_state(self) -> str:
        return secrets.token_urlsafe(32)

    def verify_state(self, expected: str, received: str) -> bool:
        return hmac.compare_digest(expected, received)


class GoogleOAuth(OAuthProvider):
    """Google OAuth2 (OpenID Connect)."""

    def get_authorization_url(self, state: str) -> str:
        params = {
            "client_id":     self.client_id,
            "redirect_uri":  self.redirect_uri,
            "response_type": "code",
            "scope":         "openid email profile",
            "state":         state,
            "access_type":   "offline",
            "prompt":        "select_account",
        }
        return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"

    def exchange_code(self, code: str) -> Tuple[bool, Dict]:
        """Exchange authorization code for tokens. Returns (success, user_info)."""
        try:
            resp = requests.post(GOOGLE_TOKEN_URL, data={
                "code":          code,
                "client_id":     self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri":  self.redirect_uri,
                "grant_type":    "authorization_code",
            }, timeout=10)
            if resp.status_code != 200:
                return False, {"error": resp.text}
            tokens = resp.json()
            access_token = tokens.get("access_token")
            if not access_token:
                return False, {"error": "no access token"}

            user_resp = requests.get(
                GOOGLE_USER_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10,
            )
            if user_resp.status_code != 200:
                return False, {"error": "failed to fetch user info"}

            info = user_resp.json()
            return True, {
                "email":      info.get("email", ""),
                "name":       info.get("name", ""),
                "picture":    info.get("picture", ""),
                "provider":   "google",
                "provider_id": info.get("sub", ""),
            }
        except requests.RequestException as e:
            return False, {"error": str(e)}


class GitHubOAuth(OAuthProvider):
    """GitHub OAuth2."""

    def get_authorization_url(self, state: str) -> str:
        params = {
            "client_id":    self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope":        "user:email read:user",
            "state":        state,
        }
        return f"{GITHUB_AUTH_URL}?{urllib.parse.urlencode(params)}"

    def exchange_code(self, code: str) -> Tuple[bool, Dict]:
        try:
            resp = requests.post(GITHUB_TOKEN_URL, data={
                "code":          code,
                "client_id":     self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri":  self.redirect_uri,
            }, headers={"Accept": "application/json"}, timeout=10)
            if resp.status_code != 200:
                return False, {"error": resp.text}
            tokens = resp.json()
            access_token = tokens.get("access_token")
            if not access_token:
                return False, {"error": "no access token"}

            user_resp = requests.get(
                GITHUB_USER_URL,
                headers={"Authorization": f"token {access_token}",
                         "Accept": "application/json"},
                timeout=10,
            )
            user = user_resp.json()

            # GitHub may not return email in user endpoint, fetch separately
            email = user.get("email") or ""
            if not email:
                email_resp = requests.get(
                    GITHUB_EMAIL_URL,
                    headers={"Authorization": f"token {access_token}"},
                    timeout=10,
                )
                if email_resp.status_code == 200:
                    for e in email_resp.json():
                        if e.get("primary") and e.get("verified"):
                            email = e["email"]
                            break

            return True, {
                "email":       email,
                "name":        user.get("name") or user.get("login", ""),
                "picture":     user.get("avatar_url", ""),
                "provider":    "github",
                "provider_id": str(user.get("id", "")),
            }
        except requests.RequestException as e:
            return False, {"error": str(e)}


def make_demo_user(email: str = "demo@tradingbot.local") -> Dict:
    """Create a demo user for local dev when OAuth is not configured."""
    return {
        "email":       email,
        "name":        "Demo Trader",
        "picture":     "",
        "provider":    "demo",
        "provider_id": "demo-001",
    }


def get_google_provider(redirect_base: str) -> GoogleOAuth:
    from config.settings import settings
    return GoogleOAuth(
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        redirect_uri=f"{redirect_base}/auth/google/callback",
    )


def get_github_provider(redirect_base: str) -> GitHubOAuth:
    from config.settings import settings
    return GitHubOAuth(
        client_id=settings.github_client_id,
        client_secret=settings.github_client_secret,
        redirect_uri=f"{redirect_base}/auth/github/callback",
    )

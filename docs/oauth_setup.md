# OAuth & Web Dashboard Setup Guide

## Architecture

```
User → Landing Page (/) → OAuth Provider → /auth/<provider>/callback
                                              ↓
                                        JWT Cookie Set
                                              ↓
                                      Protected Dashboard (/dashboard)
```

---

## Quick Start — Demo Mode (No OAuth Setup Required)

The dashboard works immediately with demo login:

```bash
python -m src.web.app
# Open: http://localhost:8080
# Click: "Continue as Demo User"
```

---

## Google OAuth2 Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project or select existing
3. Enable the **Google+ API** and **Google OAuth2 API**
4. Go to **Credentials** → **Create Credentials** → **OAuth 2.0 Client ID**
5. Application type: **Web application**
6. Authorized redirect URIs:
   - `http://localhost:8080/auth/google/callback` (dev)
   - `https://yourdomain.com/auth/google/callback` (production)
7. Copy Client ID and Client Secret

```bash
# .env
GOOGLE_CLIENT_ID=1234567890-abc.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-your-secret
OAUTH_REDIRECT_BASE=http://localhost:8080
```

---

## GitHub OAuth Setup

1. Go to [GitHub Developer Settings](https://github.com/settings/developers)
2. Click **New OAuth App**
3. Homepage URL: `http://localhost:8080`
4. Authorization callback URL: `http://localhost:8080/auth/github/callback`
5. Copy Client ID and Client Secret

```bash
# .env
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret
```

---

## Restricting Access by Email

```bash
# .env — comma-separated list of allowed emails
ALLOWED_EMAILS=admin@company.com,trader@company.com
# Leave empty to allow any authenticated user
ALLOWED_EMAILS=
```

---

## JWT Configuration

```bash
# Generate a secure key:
python -c "import secrets; print(secrets.token_hex(32))"

JWT_SECRET_KEY=your-64-char-hex-string
JWT_EXPIRE_HOURS=24   # Token lifetime
```

---

## Dashboard Features

| URL | Description |
|-----|-------------|
| `/` | Landing page with sign-in |
| `/dashboard` | Main dashboard (equity, signals, positions) |
| `/dashboard/signals` | All recent signals |
| `/dashboard/trades` | Trade history |
| `/dashboard/pnl` | P&L analysis |
| `/dashboard/risk` | Risk monitor |
| `/dashboard/markets` | Live market prices |
| `/api/v1/status` | JSON API status |
| `/api/v1/signals` | JSON signals feed |
| `/api/v1/market-prices` | JSON price feed |

---

## Production Deployment

```bash
# docker-compose up
docker compose up web -d

# With nginx reverse proxy + SSL (recommended)
OAUTH_REDIRECT_BASE=https://trading.yourdomain.com
```

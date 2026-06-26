# ADR 006: JWT Authentication Scoped to POC

## Status
Accepted

## Date
2026-05-14

## Context
The platform requires user authentication to:
- Isolate projects and test data between users.
- Protect API endpoints from unauthorized access.
- Demonstrate a complete end-to-end workflow in the demo (register → login → use platform).

For a production system, we would need OAuth 2.0 / OpenID Connect integration, multi-factor authentication (MFA), refresh token rotation, password complexity policies, and rate-limited login endpoints.

This is an 8-week internship POC. The authentication system needs to be functional and demonstrable, not production-hardened.

## Decision
Implement **simple JWT-based authentication** with email/password registration and login.

The implementation (`app/auth/`):
- **Registration:** `POST /api/v1/auth/register` — creates a user with bcrypt-hashed password.
- **Login:** `POST /api/v1/auth/login` — validates credentials, returns a JWT access token (HS256, 24-hour expiry).
- **Protected routes:** `Depends(get_current_user)` extracts and validates the JWT from the `Authorization: Bearer` header.

Configuration:
```
JWT_SECRET=<random-secret>
JWT_ALGORITHM=HS256
JWT_EXPIRES_MINUTES=1440  # 24 hours
```

## Alternatives Considered

| Alternative | Reason for Rejection |
|---|---|
| **OAuth 2.0 / OIDC (Auth0, Keycloak)** | Requires external identity provider setup, redirect flows, callback URL configuration, and token exchange logic. Adds 1-2 weeks of development time for features not relevant to the core POC thesis (agentic test generation). |
| **Session-based auth (cookies)** | Works well for server-rendered apps but adds complexity for an SPA + API architecture. Requires CSRF protection, session store management, and cross-origin cookie configuration. |
| **API key auth (no user accounts)** | Simpler but loses user isolation. Cannot demonstrate the multi-tenant workflow (each user sees only their projects). |
| **No auth (open endpoints)** | Not viable — the demo needs to show a realistic workflow. An unauthenticated API also cannot demonstrate ownership-based access control. |

## Consequences

### Positive
- **Minimal implementation time:** JWT auth with FastAPI took ~1 day to implement, including registration, login, token validation, and the `CurrentUser` dependency.
- **SPA-friendly:** The frontend stores the JWT in memory/localStorage and sends it as a Bearer token. No cookie management complexity.
- **Demonstrable:** The demo shows a complete register → login → dashboard flow, proving the platform handles multi-user scenarios.

### Negative
- **No refresh tokens:** The 24-hour JWT expiry means users must re-login daily. Acceptable for a POC where demo sessions are short.
- **No MFA:** Single-factor auth is not production-ready. Documented as a known limitation.
- **HS256 signing:** Symmetric key signing means the server secret must be carefully managed. RS256 with key rotation would be more appropriate for production.
- **No rate limiting:** Login endpoint is not rate-limited against brute-force attacks. In production, this would need rate limiting or account lockout policies.

### Known Limitations (Documented for Future Work)
- Implement refresh token rotation for long-lived sessions.
- Add OAuth 2.0 integration for enterprise SSO.
- Switch to RS256 asymmetric signing for zero-trust environments.
- Add rate limiting to auth endpoints.

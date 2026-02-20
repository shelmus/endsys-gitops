# OAuth Integration with PocketID

Patterns for integrating applications with PocketID as the OIDC identity provider.

## Overview

PocketID is a lightweight, passkey-based OIDC provider. Unlike Authentik, it requires no bundled database or Redis — it uses SQLite by default.

OIDC clients are configured via the PocketID web UI (no blueprints or declarative config).

## Architecture

```
┌────────────┐     OIDC          ┌─────────────┐
│   Client   │ ◄───────────────► │  PocketID   │
│  (Immich)  │                   │   Server    │
└────────────┘                   └──────┬──────┘
                                        │
                                  ┌─────┴──────┐
                                  │   SQLite   │
                                  │  (Longhorn) │
                                  └────────────┘
```

## Adding an OIDC Client

1. Log into PocketID admin at `https://auth.endsys.cloud`
2. Navigate to **OIDC Clients** → **Add OIDC Client**
3. Configure:
   - **Name**: Application name (e.g., "Immich")
   - **Callback URLs**: List of allowed redirect URIs
4. Copy the generated **Client ID** and **Client Secret**
5. Store the client secret in Bitwarden Secrets Manager
6. Reference via ExternalSecret in the application

## Immich OAuth Example

### PocketID OIDC Client Setup

Create an OIDC client in the PocketID UI with:

- **Name**: Immich
- **Callback URLs**:
  - `https://immich.endsys.cloud/auth/login`
  - `https://immich.endsys.cloud/api/oauth/mobile-redirect`
  - `app.immich:///oauth-callback`

### Immich Configuration

In Immich HelmRelease:

```yaml
controllers:
  main:
    containers:
      main:
        env:
          IMMICH_OAUTH_ENABLED: "true"
          IMMICH_OAUTH_ISSUER_URL: https://auth.endsys.cloud
          IMMICH_OAUTH_CLIENT_ID: immich
          IMMICH_OAUTH_CLIENT_SECRET:
            valueFrom:
              secretKeyRef:
                name: immich-oauth
                key: client-secret
          IMMICH_OAUTH_SCOPE: "openid email profile"
          IMMICH_OAUTH_AUTO_REGISTER: "true"
          IMMICH_OAUTH_BUTTON_TEXT: "Login with PocketID"
```

## Required Secrets

For each OAuth integration, store in Bitwarden:

| Secret Name | Purpose |
|-------------|---------|
| `{app}-oauth-client-secret` | Client secret from PocketID OIDC client |
| `pocket-id-encryption-key` | PocketID encryption key (generate with `openssl rand -base64 32`) |

## URLs

### PocketID Endpoints

| Endpoint | URL |
|----------|-----|
| Issuer | `https://auth.endsys.cloud` |
| OIDC Discovery | `https://auth.endsys.cloud/.well-known/openid-configuration` |
| Admin UI | `https://auth.endsys.cloud` |

## Troubleshooting

### Check PocketID Logs

```bash
kubectl logs -n pocket-id statefulset/pocket-id
```

### Verify OIDC Discovery

```bash
curl https://auth.endsys.cloud/.well-known/openid-configuration
```

### Test OAuth Flow

1. Clear browser cookies
2. Visit app (e.g., https://immich.endsys.cloud)
3. Click "Login with PocketID"
4. Should redirect to PocketID passkey authentication

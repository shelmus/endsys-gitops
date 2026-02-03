# OAuth Integration with Authentik

Patterns for integrating applications with Authentik as the identity provider.

## Overview

Authentik serves as the central OAuth2/OIDC provider. Applications integrate using:
1. **Blueprints** - Declarative configuration in Git
2. **OAuth2 providers** - App-specific OAuth configurations
3. **Applications** - Authentik application entries

## Architecture

```
┌────────────┐     OAuth2/OIDC     ┌─────────────┐
│   Client   │ ◄─────────────────► │  Authentik  │
│  (Immich)  │                     │   Server    │
└────────────┘                     └──────┬──────┘
                                          │
                                   ┌──────┴──────┐
                                   │  Blueprint  │
                                   │  ConfigMap  │
                                   └─────────────┘
```

## Blueprint Pattern

Authentik Blueprints allow GitOps-style configuration of OAuth providers.

### Blueprint ConfigMap

**Location**: `kubernetes/apps/authentik/authentik/app/blueprint-{app}.yaml`

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: authentik-blueprint-{app}
data:
  {app}.yaml: |
    version: 1
    metadata:
      name: {App} OAuth Provider
    entries:
      # OAuth2 Provider
      - model: authentik_providers_oauth2.oauth2provider
        id: {app}-provider
        state: present
        attrs:
          name: {App}
          authorization_flow: !Find [authentik_flows.flow, [slug, default-provider-authorization-implicit-consent]]
          client_type: confidential
          client_id: {app}
          client_secret: !Env [APP_OAUTH_CLIENT_SECRET]
          redirect_uris: |
            https://{app}.endsys.cloud/callback
          property_mappings:
            - !Find [authentik_providers_oauth2.scopemapping, [managed, goauthentik.io/providers/oauth2/scope-openid]]
            - !Find [authentik_providers_oauth2.scopemapping, [managed, goauthentik.io/providers/oauth2/scope-email]]
            - !Find [authentik_providers_oauth2.scopemapping, [managed, goauthentik.io/providers/oauth2/scope-profile]]

      # Application
      - model: authentik_core.application
        state: present
        attrs:
          name: {App}
          slug: {app}
          provider: !KeyOf {app}-provider
          meta_launch_url: https://{app}.endsys.cloud
```

### Mount Blueprint in Authentik

Update the Authentik HelmRelease to mount the blueprint:

```yaml
worker:
  env:
    - name: APP_OAUTH_CLIENT_SECRET
      valueFrom:
        secretKeyRef:
          name: authentik-secrets
          key: app-oauth-client-secret
  volumeMounts:
    - name: blueprints-{app}
      mountPath: /blueprints/custom/{app}.yaml
      subPath: {app}.yaml
  volumes:
    - name: blueprints-{app}
      configMap:
        name: authentik-blueprint-{app}
```

## Immich OAuth Example

### Blueprint

```yaml
entries:
  - model: authentik_providers_oauth2.oauth2provider
    id: immich-provider
    state: present
    attrs:
      name: Immich
      authorization_flow: !Find [authentik_flows.flow, [slug, default-provider-authorization-implicit-consent]]
      client_type: confidential
      client_id: immich
      client_secret: !Env [IMMICH_OAUTH_CLIENT_SECRET]
      redirect_uris: |
        https://immich.endsys.cloud/auth/login
        https://immich.endsys.cloud/api/oauth/mobile-redirect
        app.immich:///oauth-callback
      property_mappings:
        - !Find [authentik_providers_oauth2.scopemapping, [managed, goauthentik.io/providers/oauth2/scope-openid]]
        - !Find [authentik_providers_oauth2.scopemapping, [managed, goauthentik.io/providers/oauth2/scope-email]]
        - !Find [authentik_providers_oauth2.scopemapping, [managed, goauthentik.io/providers/oauth2/scope-profile]]
```

### Immich Configuration

In Immich HelmRelease:

```yaml
controllers:
  main:
    containers:
      main:
        env:
          IMMICH_OAUTH_ENABLED: "true"
          IMMICH_OAUTH_ISSUER_URL: https://authentik.endsys.cloud/application/o/immich/
          IMMICH_OAUTH_CLIENT_ID: immich
          IMMICH_OAUTH_CLIENT_SECRET:
            valueFrom:
              secretKeyRef:
                name: immich-oauth
                key: client-secret
          IMMICH_OAUTH_SCOPE: "openid email profile"
          IMMICH_OAUTH_AUTO_REGISTER: "true"
          IMMICH_OAUTH_BUTTON_TEXT: "Login with Authentik"
```

## User Management via Blueprint

Users can be created declaratively:

```yaml
entries:
  - model: authentik_core.user
    id: user-sean
    state: present
    attrs:
      username: sean
      name: Sean
      email: sean@endsys.cloud
      is_active: true
      password: !Env [AUTHENTIK_USER_SEAN_PASSWORD]
      groups:
        - !Find [authentik_core.group, [name, authentik Admins]]
```

## Required Secrets

For each OAuth integration, store in Bitwarden:

| Secret Name | Purpose |
|-------------|---------|
| `{app}-oauth-client-secret` | Client secret for OAuth provider |
| `user-{name}-password` | User password (if managing users via blueprint) |

## URLs

### Authentik Endpoints

| Endpoint | URL |
|----------|-----|
| Authorization | `https://authentik.endsys.cloud/application/o/authorize/` |
| Token | `https://authentik.endsys.cloud/application/o/token/` |
| User Info | `https://authentik.endsys.cloud/application/o/userinfo/` |
| OIDC Discovery | `https://authentik.endsys.cloud/application/o/{app}/.well-known/openid-configuration` |

### App-Specific Issuer URL

```
https://authentik.endsys.cloud/application/o/{app}/
```

## Troubleshooting

### Check Blueprint Applied

```bash
# View Authentik worker logs
kubectl logs -n authentik deployment/authentik-worker | grep -i blueprint
```

### Verify OAuth Provider

1. Log into Authentik admin: https://authentik.endsys.cloud/if/admin/
2. Navigate to Applications > Providers
3. Verify provider exists with correct settings

### Test OAuth Flow

1. Clear browser cookies
2. Visit app (e.g., https://immich.endsys.cloud)
3. Click "Login with Authentik"
4. Should redirect to Authentik login page

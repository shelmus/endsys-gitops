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

> **⚠️ Authentik 2025.x Changes**: Blueprint syntax changed significantly. See [Common Errors](#common-blueprint-errors) if migrating from older versions.

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
        identifiers:
          name: {App}
        attrs:
          authorization_flow: !Find [authentik_flows.flow, [slug, default-provider-authorization-implicit-consent]]
          invalidation_flow: !Find [authentik_flows.flow, [slug, default-provider-invalidation-flow]]
          client_type: confidential
          client_id: {app}
          client_secret: !Env APP_OAUTH_CLIENT_SECRET
          redirect_uris:
            - matching_mode: strict
              url: https://{app}.endsys.cloud/callback
          property_mappings:
            - !Find [authentik_providers_oauth2.scopemapping, [managed, goauthentik.io/providers/oauth2/scope-openid]]
            - !Find [authentik_providers_oauth2.scopemapping, [managed, goauthentik.io/providers/oauth2/scope-email]]
            - !Find [authentik_providers_oauth2.scopemapping, [managed, goauthentik.io/providers/oauth2/scope-profile]]

      # Application
      - model: authentik_core.application
        state: present
        identifiers:
          slug: {app}
        attrs:
          name: {App}
          provider: !KeyOf {app}-provider
          meta_launch_url: https://{app}.endsys.cloud
```

### Key Blueprint Fields (Authentik 2025.x)

| Field | Required | Purpose |
|-------|----------|---------|
| `identifiers` | **Yes** | Unique fields to find/update existing objects |
| `invalidation_flow` | **Yes** | Required for OAuth2 providers |
| `redirect_uris` | **Yes** | Must be list of objects with `url` and `matching_mode` |
| `!Env VAR` | - | Scalar syntax (not `!Env [VAR]`) |

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
    identifiers:
      name: Immich
    attrs:
      authorization_flow: !Find [authentik_flows.flow, [slug, default-provider-authorization-implicit-consent]]
      invalidation_flow: !Find [authentik_flows.flow, [slug, default-provider-invalidation-flow]]
      client_type: confidential
      client_id: immich
      client_secret: !Env IMMICH_OAUTH_CLIENT_SECRET
      redirect_uris:
        - matching_mode: strict
          url: https://immich.endsys.cloud/auth/login
        - matching_mode: strict
          url: https://immich.endsys.cloud/api/oauth/mobile-redirect
        - matching_mode: strict
          url: app.immich:///oauth-callback
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
    identifiers:
      username: sean
    attrs:
      name: Sean
      email: sean@endsys.cloud
      is_active: true
      password: !Env AUTHENTIK_USER_SEAN_PASSWORD
      groups:
        - !Find [authentik_core.group, [name, authentik Admins]]
```

> **Note**: The `username` moves to `identifiers` (not `attrs`) so Authentik can find existing users to update.

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

## Common Blueprint Errors

### IndexError: list index out of range

**Cause**: Using `!Env [VAR_NAME]` bracket syntax in Authentik 2025.x

**Fix**: Use scalar syntax without brackets:
```yaml
# Wrong (pre-2025)
client_secret: !Env [MY_SECRET]

# Correct (2025.x)
client_secret: !Env MY_SECRET
```

### No or invalid identifiers

**Cause**: Missing `identifiers` field in blueprint entry

**Fix**: Add `identifiers` with the unique field for that model:
```yaml
- model: authentik_core.user
  state: present
  identifiers:        # Add this section
    username: sean    # Unique identifier
  attrs:
    name: Sean
    # ... other fields
```

### invalidation_flow: This field is required

**Cause**: OAuth2Provider requires `invalidation_flow` in Authentik 2025.x

**Fix**: Add the invalidation flow reference:
```yaml
attrs:
  authorization_flow: !Find [authentik_flows.flow, [slug, default-provider-authorization-implicit-consent]]
  invalidation_flow: !Find [authentik_flows.flow, [slug, default-provider-invalidation-flow]]  # Add this
```

### redirect_uris: Expected a dictionary, but got str

**Cause**: Using string URLs instead of object format

**Fix**: Convert to list of objects:
```yaml
# Wrong (pre-2025)
redirect_uris: |
  https://app.example.com/callback

# Correct (2025.x)
redirect_uris:
  - matching_mode: strict
    url: https://app.example.com/callback
```

### Blueprint status: error

**Check blueprint status**:
```bash
kubectl exec -n authentik deployment/authentik-worker -- ak shell -c "
from authentik.blueprints.models import BlueprintInstance
for bp in BlueprintInstance.objects.all():
    print(f'{bp.name}: {bp.status}')
"
```

**Force re-apply**:
```bash
kubectl exec -n authentik deployment/authentik-worker -- ak apply_blueprint /blueprints/custom/{app}.yaml
```

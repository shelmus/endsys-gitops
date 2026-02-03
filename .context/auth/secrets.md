# Secret Management

Strategy and patterns for managing secrets in the cluster.

## Overview

Secrets flow from **Bitwarden Secrets Manager** → **External Secrets Operator** → **Kubernetes Secrets**.

```
┌─────────────────────────┐
│  Bitwarden Secrets      │
│      Manager            │
│  (Source of Truth)      │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  External Secrets       │
│      Operator           │
│  (Sync Controller)      │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Kubernetes Secrets     │
│  (Runtime Consumption)  │
└─────────────────────────┘
```

## Components

### ClusterSecretStore

Cluster-wide configuration pointing to Bitwarden:

**Location**: `kubernetes/apps/external-secrets/external-secrets/stores/clustersecretstore.yaml`

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: bitwarden-secretsmanager
spec:
  provider:
    bitwardensecretsmanager:
      apiURL: https://vault.bitwarden.com/api
      identityURL: https://vault.bitwarden.com/identity
      bitwardenServerSDKURL: https://bitwarden-sdk-server.external-secrets.svc.cluster.local:9998
      organizationID: "${SECRET_BITWARDEN_ORGANIZATION_ID}"
      projectID: "${SECRET_BITWARDEN_PROJECT_ID}"
      auth:
        secretRef:
          credentials:
            name: bitwarden-access-token
            key: token
            namespace: external-secrets
```

### ExternalSecret

Per-app resources that sync specific secrets:

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: my-app-secrets
spec:
  refreshInterval: 1h
  secretStoreRef:
    kind: ClusterSecretStore
    name: bitwarden-secretsmanager
  target:
    name: my-app-secrets         # K8s Secret name
    creationPolicy: Owner
    deletionPolicy: Retain
  data:
    - secretKey: api-key         # Key in K8s Secret
      remoteRef:
        key: my-app-api-key      # Key name in Bitwarden
```

## Creating Secrets

### 1. Add to Bitwarden

In Bitwarden Secrets Manager:
1. Navigate to your project
2. Create new secret with naming convention: `{app}-{purpose}`
3. Examples:
   - `immich-oauth-client-secret`
   - `authentik-postgresql-password`
   - `n8n-encryption-key`

### 2. Create ExternalSecret

```yaml
---
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: my-app-secrets
  labels:
    app.kubernetes.io/name: my-app
spec:
  refreshInterval: 1h
  secretStoreRef:
    kind: ClusterSecretStore
    name: bitwarden-secretsmanager
  target:
    name: my-app-secrets
    creationPolicy: Owner
    deletionPolicy: Retain
  data:
    - secretKey: password
      remoteRef:
        key: my-app-database-password
```

### 3. Reference in App

In HelmRelease values:

```yaml
values:
  env:
    DATABASE_PASSWORD:
      valueFrom:
        secretKeyRef:
          name: my-app-secrets
          key: password
```

Or via `valuesFrom`:

```yaml
valuesFrom:
  - kind: Secret
    name: my-app-secrets
    valuesKey: password
    targetPath: database.password
```

## Secret Naming Conventions

| Pattern | Example |
|---------|---------|
| `{app}-secrets` | `authentik-secrets` |
| `{app}-{purpose}` | `immich-oauth-client-secret` |
| `{app}-{service}-password` | `authentik-postgresql-password` |
| `{app}-secret-key` | `authentik-secret-key` |

## CNPG Auto-Generated Secrets

CloudNativePG automatically creates secrets for database credentials:

| Secret Name | Contents |
|-------------|----------|
| `{cluster}-app` | `username`, `password`, `host`, `port`, `dbname`, `uri` |
| `{cluster}-superuser` | Superuser credentials |

Example: For `immich-postgres` cluster → `immich-postgres-app` secret.

## Troubleshooting

### Check ExternalSecret Status

```bash
kubectl get externalsecret -A
kubectl describe externalsecret my-app-secrets -n my-app
```

### Verify Secret Sync

```bash
# Check if secret exists
kubectl get secret my-app-secrets -n my-app

# View secret keys (not values)
kubectl get secret my-app-secrets -n my-app -o jsonpath='{.data}' | jq 'keys'
```

### Force Refresh

Delete the synced secret to trigger re-sync:

```bash
kubectl delete secret my-app-secrets -n my-app
```

## Migration from SOPS

Legacy SOPS secrets (`secret.sops.yaml`) still exist in some apps.
See [debt.md](../debt.md) TD-006 for migration status.

To migrate:
1. Create secret in Bitwarden
2. Create ExternalSecret CR
3. Update app to reference new secret
4. Remove SOPS file

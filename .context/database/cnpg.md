# CloudNativePG Patterns

Patterns for deploying PostgreSQL databases using CloudNativePG (CNPG) operator.

## Overview

CloudNativePG is a Kubernetes operator for managing PostgreSQL clusters with:
- Automated failover
- Backup/restore
- Rolling updates
- Connection pooling

## Architecture

```
┌─────────────────────────────────────────────┐
│            CNPG Operator                     │
│         (cnpg-system namespace)              │
└─────────────────────┬───────────────────────┘
                      │ manages
          ┌───────────┼───────────┐
          ▼           ▼           ▼
     ┌─────────┐ ┌─────────┐ ┌─────────┐
     │ immich- │ │  n8n-   │ │ future- │
     │postgres │ │postgres │ │postgres │
     └────┬────┘ └────┬────┘ └────┬────┘
          │           │           │
          ▼           ▼           ▼
       PVCs for persistent storage
```

## Operator Deployment

**Location**: `kubernetes/apps/cnpg-system/cnpg-operator/`

```yaml
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: cnpg-operator
  namespace: cnpg-system
spec:
  chart:
    spec:
      chart: cloudnative-pg
      version: 0.23.0
      sourceRef:
        kind: HelmRepository
        name: cnpg
        namespace: flux-system
```

## Cluster Custom Resource

### Basic Cluster

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: my-app-postgres
spec:
  instances: 1
  storage:
    size: 10Gi
  bootstrap:
    initdb:
      database: my_app
      owner: my_app
```

### With Extensions (Immich Example)

Immich requires vector search extensions:

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: immich-postgres
spec:
  instances: 1
  imageName: ghcr.io/tensorchord/cloudnative-vectorchord:16.9-0.4.3
  postgresql:
    shared_preload_libraries:
      - "vchord.so"
  bootstrap:
    initdb:
      database: immich
      owner: immich
      postInitApplicationSQL:
        - CREATE EXTENSION IF NOT EXISTS vchord CASCADE;
        - CREATE EXTENSION IF NOT EXISTS earthdistance CASCADE;
  storage:
    size: 20Gi
```

## Auto-Generated Secrets

CNPG automatically creates secrets for database access:

| Secret Name | Contents |
|-------------|----------|
| `{cluster}-app` | Application credentials: `username`, `password`, `host`, `port`, `dbname`, `uri`, `jdbc-uri` |
| `{cluster}-superuser` | Postgres superuser credentials |
| `{cluster}-ca` | CA certificate for TLS |

### Using App Secret

Reference in HelmRelease:

```yaml
env:
  DB_HOSTNAME: my-app-postgres-rw
  DB_PORT: "5432"
  DB_USERNAME: my_app
  DB_DATABASE_NAME: my_app
  DB_PASSWORD:
    valueFrom:
      secretKeyRef:
        name: my-app-postgres-app
        key: password
```

## Service Endpoints

CNPG creates multiple services:

| Service | Purpose |
|---------|---------|
| `{cluster}-rw` | Read-write (primary) |
| `{cluster}-ro` | Read-only (replicas) |
| `{cluster}-r` | Any (round-robin) |

For single-instance, always use `{cluster}-rw`.

## Dependencies

Apps using CNPG must wait for the operator:

```yaml
# In ks.yaml
spec:
  dependsOn:
    - name: cnpg-operator
      namespace: cnpg-system
```

## High Availability

For production, increase instances:

```yaml
spec:
  instances: 3
  postgresql:
    pg_hba:
      - host all all 10.0.0.0/8 md5
```

See [debt.md](../debt.md) TD-003 for current HA status.

## Backup Configuration

Example with S3-compatible storage:

```yaml
spec:
  backup:
    barmanObjectStore:
      destinationPath: s3://backups/postgres
      endpointURL: https://s3.example.com
      s3Credentials:
        accessKeyId:
          name: backup-creds
          key: access-key
        secretAccessKey:
          name: backup-creds
          key: secret-key
    retentionPolicy: "30d"
```

## Monitoring

Check cluster status:

```bash
# Get all clusters
kubectl get cluster -A

# Describe cluster
kubectl describe cluster immich-postgres -n immich

# Check pods
kubectl get pods -n immich -l cnpg.io/cluster=immich-postgres

# View logs
kubectl logs -n immich immich-postgres-1
```

## Troubleshooting

### Cluster Not Ready

```bash
# Check operator logs
kubectl logs -n cnpg-system deployment/cnpg-operator

# Check cluster events
kubectl get events -n immich --field-selector involvedObject.name=immich-postgres
```

### Connection Refused

Ensure app uses `-rw` service:
```yaml
DB_HOSTNAME: my-app-postgres-rw  # Not just 'my-app-postgres'
```

### Extension Not Found

Verify image supports required extensions:
- Standard extensions: Use default CNPG image
- Vector extensions: Use `ghcr.io/tensorchord/cloudnative-vectorchord`

## Migration from Embedded DB

When migrating from Helm subchart PostgreSQL:

1. Deploy CNPG Cluster
2. Backup data from old database
3. Restore to CNPG cluster
4. Update app to use `{cluster}-rw` hostname
5. Update app to use `{cluster}-app` secret
6. Disable old subchart

## Resource Sizing

| Use Case | CPU Request | Memory Request | Storage |
|----------|-------------|----------------|---------|
| Development | 50m | 256Mi | 5Gi |
| Small app | 100m | 512Mi | 10Gi |
| Medium app | 250m | 1Gi | 20Gi |
| Production | 500m+ | 2Gi+ | 50Gi+ |

# Dragonfly Cache Patterns

Patterns for deploying Dragonfly as a Redis-compatible in-memory cache.

## Overview

Dragonfly is a modern Redis replacement offering:
- **25x better performance** than Redis
- **80% less memory** usage
- Drop-in Redis protocol compatibility
- Modern architecture with io_uring

## When to Use Dragonfly

| Use Case | Dragonfly | Notes |
|----------|-----------|-------|
| Session storage | Yes | Fast, ephemeral data |
| Application cache | Yes | Frequently accessed data |
| Queue backend (BullMQ, Sidekiq) | Yes | Requires `--allow-undeclared-keys` flag |
| Pub/sub messaging | Yes | Redis-compatible |
| Persistent data | No | Use PostgreSQL/CNPG instead |

## Architecture

```
┌─────────────────┐     Redis Protocol     ┌─────────────────┐
│   Application   │ ◄────────────────────► │   Dragonfly     │
│   (Immich)      │      Port 6379         │   StatefulSet   │
└─────────────────┘                        └────────┬────────┘
                                                    │
                                              ┌─────┴─────┐
                                              │    PVC    │
                                              │  (2-10Gi) │
                                              └───────────┘
```

## Deployment Pattern

**Location**: `kubernetes/apps/{namespace}/{app}/app/dragonfly.yaml`

### Basic HelmRelease

```yaml
---
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: dragonfly
spec:
  interval: 1h
  chart:
    spec:
      chart: dragonfly
      version: v1.26.0
      sourceRef:
        kind: HelmRepository
        name: dragonfly
        namespace: flux-system
  values:
    replicaCount: 1
    storage:
      enabled: true
      requests: 2Gi
    resources:
      requests:
        cpu: 100m
        memory: 256Mi
      limits:
        memory: 512Mi
```

### With BullMQ Compatibility (Immich)

BullMQ requires undeclared keys support. Immich also uses emulated cluster mode and limits proactor threads for resource-constrained environments:

```yaml
values:
  extraArgs:
    - --proactor_threads=1
    - --cluster_mode=emulated
    - --default_lua_flags=allow-undeclared-keys
  storage:
    enabled: true
    requests: 2Gi
```

## Current Deployments

| App | Namespace | Purpose | Storage |
|-----|-----------|---------|---------|
| Immich | immich | Job queue (BullMQ), caching | 2Gi |

## Connecting from Applications

### Environment Variables

```yaml
env:
  REDIS_HOSTNAME: dragonfly
  REDIS_PORT: "6379"
  # No password by default - add if configured
```

### Connection String

```
redis://dragonfly:6379
```

## HelmRepository

**Location**: `kubernetes/flux/meta/repos/dragonfly.yaml`

```yaml
---
apiVersion: source.toolkit.fluxcd.io/v1
kind: HelmRepository
metadata:
  name: dragonfly
  namespace: flux-system
spec:
  type: oci
  interval: 24h
  url: oci://ghcr.io/dragonflydb/dragonfly/helm
```

## Resource Sizing

| Use Case | CPU Request | Memory Request | Storage |
|----------|-------------|----------------|---------|
| Development | 50m | 128Mi | 1Gi |
| Small app | 100m | 256Mi | 2Gi |
| Medium app | 250m | 512Mi | 5Gi |
| Production | 500m+ | 1Gi+ | 10Gi+ |

## Monitoring

```bash
# Check Dragonfly pods
kubectl get pods -n {namespace} -l app.kubernetes.io/name=dragonfly

# View logs
kubectl logs -n {namespace} dragonfly-0

# Check memory usage
kubectl exec -n {namespace} dragonfly-0 -- redis-cli INFO memory
```

## Troubleshooting

### Connection Refused

Ensure service name is correct:
```yaml
REDIS_HOSTNAME: dragonfly  # Not 'redis' or 'dragonfly-master'
```

### BullMQ Errors

If using BullMQ (like Immich), ensure the flag is set:
```yaml
extraArgs:
  - --default_lua_flags=allow-undeclared-keys
```

### High Memory Usage

Dragonfly uses less memory than Redis, but still needs limits:
```yaml
resources:
  limits:
    memory: 512Mi  # Adjust based on workload
```

## Migration from Redis

Dragonfly is protocol-compatible with Redis:

1. Deploy Dragonfly alongside Redis
2. Update app to point to Dragonfly service
3. Verify functionality
4. Remove Redis deployment

No data migration needed for cache data (ephemeral by nature).

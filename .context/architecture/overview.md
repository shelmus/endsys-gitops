# Architecture Overview

System design and infrastructure patterns for the endsys-gitops cluster.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              Internet                                    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Cloudflare Tunnels                               │
│                    (cloudflared → external gateway)                      │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        Gateway API (Cilium)                              │
│              internal / external Gateways → HTTPRoutes                   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
              ┌─────────┐    ┌─────────┐    ┌─────────┐
              │ Immich  │    │Authentik│    │   n8n   │
              └────┬────┘    └────┬────┘    └────┬────┘
                   │              │              │
              ┌────┴────┐    ┌────┴────┐         │
              │  CNPG   │    │ Bitnami │*        │
              │Postgres │    │Postgres │         │
              └─────────┘    └─────────┘         │
                   │                             │
              ┌────┴────┐                   ┌────┴────┐
              │Dragonfly│                   │  (no    │
              │ (cache) │                   │   DB)   │
              └─────────┘                   └─────────┘

* Authentik uses embedded Bitnami DBs - see debt.md TD-001 for migration plan
```

## Infrastructure Layers

### Layer 1: Cluster Foundation
- **Talos Linux**: Immutable, API-driven OS
- **Cilium CNI**: eBPF networking, Gateway API implementation
- **cert-manager**: Automated TLS certificates via Let's Encrypt

### Layer 2: GitOps
- **FluxCD**: Continuous reconciliation from Git
  - Source Controller: Git/OCI repositories
  - Kustomize Controller: Kustomization resources
  - Helm Controller: HelmRelease resources
  - Notification Controller: Alerts

### Layer 3: Data Services
- **CloudNativePG (CNPG)**: PostgreSQL operator for stateful workloads
- **Dragonfly**: Redis-compatible cache (replaces Redis)
- **Longhorn**: Distributed block storage
- **NFS CSI**: Network file storage for media

### Layer 4: Security
- **External Secrets Operator**: Syncs secrets from Bitwarden
- **Authentik**: Identity provider, OAuth2/OIDC

### Layer 5: Applications

| App | Namespace | Purpose | Database |
|-----|-----------|---------|----------|
| Immich | immich | Photo management | CNPG + Dragonfly |
| Authentik | authentik | Identity provider | Bitnami (embedded)* |
| n8n | n8n | Workflow automation | - |
| Velero | velero | Cluster backup | - |
| Gatus | gatus | Uptime monitoring | - |
| Prometheus | kube-prometheus-stack | Metrics collection | - |
| Pelican | pelican | Game server panel | - |
| Pricebuddy | pricebuddy | Price tracking | MariaDB (embedded) |
| Otterwiki | default | Wiki | SQLite |
| SeaweedFS | seaweedfs | Object storage | - |

*See [debt.md](../debt.md) TD-001 for migration plan

## Dependency Chain

FluxCD reconciles resources in dependency order:

```
flux-system (bootstrap)
└── cluster-meta (HelmRepositories, OCIRepositories)
    └── cluster-apps
        ├── infrastructure
        │   ├── cilium (CNI + Gateway API)
        │   ├── cert-manager (TLS certificates)
        │   ├── cnpg-operator (PostgreSQL)
        │   ├── external-secrets (secret sync)
        │   └── csi-driver-nfs (NFS storage)
        ├── configs
        │   └── external-secrets-stores (ClusterSecretStore)
        └── apps
            ├── authentik (depends on: external-secrets-stores)
            ├── immich (depends on: cnpg-operator, external-secrets-stores, csi-driver-nfs)
            ├── gatus
            ├── kube-prometheus-stack
            ├── pelican
            ├── pricebuddy
            └── ...
```

**Key**: Apps declare dependencies via `dependsOn` in their `ks.yaml` to ensure prerequisites are ready.

## Network Architecture

### Ingress Flow
1. External traffic → Cloudflare Tunnel
2. Tunnel terminates at `external` Gateway
3. HTTPRoute matches hostname/path
4. Traffic routed to Service → Pod

### Internal Services
- Use `internal` Gateway for cluster-only access
- k8s-gateway provides DNS resolution for `*.endsys.cloud`

### Gateway Types

| Gateway | Namespace | Purpose |
|---------|-----------|---------|
| `internal` | `kube-system` | Private network access |
| `external` | `kube-system` | Public internet via Cloudflare |

## Storage Architecture

| Type | Provider | Use Case |
|------|----------|----------|
| Block | Longhorn | Pod persistent storage |
| NFS | NFS CSI | Shared media libraries |
| Object | SeaweedFS | S3-compatible storage |

### NFS Configuration
- Server: `10.127.0.5`
- Paths:
  - `/data/photos` - Immich library
  - `/data/seaweedfs` - Object storage
  - `/data/velero` - Backup storage

## Helm Repositories

**Location**: `kubernetes/flux/meta/repos/`

| Name | Type | URL | Used By |
|------|------|-----|---------|
| authentik | HTTP | charts.goauthentik.io | Authentik |
| cnpg | HTTP | cloudnative-pg.io/charts | CNPG operator |
| dragonfly | OCI | ghcr.io/dragonflydb/dragonfly/helm | Dragonfly cache |
| immich | OCI | ghcr.io/immich-app/immich-charts | Immich |
| external-secrets | HTTP | charts.external-secrets.io | ESO |
| longhorn | HTTP | charts.longhorn.io | Longhorn storage |
| bitwarden | HTTP | charts.bitwarden.com | Bitwarden SDK |
| prometheus | HTTP | prometheus-community.github.io/helm-charts | Monitoring |

## Key Design Decisions

1. **Gateway API over Ingress**: Modern routing with better extensibility
2. **CNPG over embedded databases**: Proper PostgreSQL lifecycle management
3. **Dragonfly over Redis**: 25x performance, 80% less memory
4. **External Secrets over SOPS**: Centralized secret management (migration in progress)
5. **OCI over HTTP repos**: Better caching, signed artifacts

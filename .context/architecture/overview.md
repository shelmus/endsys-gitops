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
              │ Immich  │    │PocketID │    │   n8n   │
              └────┬────┘    └────┬────┘    └────┬────┘
                   │              │              │
              ┌────┴────┐    ┌────┴────┐         │
              │  CNPG   │    │ SQLite  │         │
              │Postgres │    │(Longhorn│         │
              └─────────┘    └─────────┘         │
                   │                             │
              ┌────┴────┐                   ┌────┴────┐
              │Dragonfly│                   │  (no    │
              │ (cache) │                   │   DB)   │
              └─────────┘                   └─────────┘
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
- **PocketID**: Lightweight OIDC provider (passkey-based)

### Layer 5: Applications

| App | Namespace | Purpose | Database |
|-----|-----------|---------|----------|
| Immich | immich | Photo management | CNPG + Dragonfly |
| PocketID | pocket-id | OIDC identity provider | SQLite (Longhorn PVC) |
| n8n | n8n | Workflow automation | - |
| Velero | velero | Cluster backup | - |
| Gatus | gatus | Uptime monitoring | - |
| kube-prometheus-stack | kube-prometheus-stack | Metrics, alerting, dashboards | - |
| Pelican | pelican | Game server panel | - |
| Pricebuddy | pricebuddy | Price tracking | MySQL (embedded) |
| Otterwiki | default | Wiki | SQLite |
| SeaweedFS | seaweedfs | Object storage | - |
| Cloudflare Tunnel | network | Public ingress via Cloudflare | - |
| Cloudflare DNS | network | External DNS (Cloudflare) | - |
| Pi-hole DNS | network | External DNS (Pi-hole) | - |
| k8s-gateway | network | Internal DNS for *.endsys.cloud | - |
| Echo | network | HTTP echo test server | - |

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
            ├── pocket-id (depends on: external-secrets-stores)
            ├── immich (depends on: cnpg-operator, external-secrets-stores, csi-driver-nfs)
            ├── kube-prometheus-stack (depends on: external-secrets-stores)
            ├── gatus
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
| anza-labs | HTTP | anza-labs.github.io/charts | PocketID |
| backube | HTTP | backube.github.io/helm-charts | VolSync |
| bitwarden | HTTP | charts.bitwarden.com | Bitwarden SDK |
| cnpg | HTTP | cloudnative-pg.io/charts | CNPG operator |
| csi-driver-nfs | HTTP | raw.githubusercontent.com/kubernetes-csi/csi-driver-nfs | NFS CSI |
| dragonfly | OCI | ghcr.io/dragonflydb/dragonfly/helm | Dragonfly cache |
| external-secrets | HTTP | charts.external-secrets.io | ESO |
| immich | OCI | ghcr.io/immich-app/immich-charts | Immich |
| kube-prometheus-stack | HTTP | prometheus-community.github.io/helm-charts | Monitoring |
| longhorn | HTTP | charts.longhorn.io | Longhorn storage |
| n8n | HTTP | community-charts.github.io/helm-charts | n8n |
| otterwiki | HTTP | charts.otterwiki.com | Otterwiki |
| seaweedfs | HTTP | seaweedfs.github.io/seaweedfs/helm | SeaweedFS |
| twin | HTTP | twin.github.io/helm-charts | Gatus |
| vmware-tanzu | HTTP | vmware-tanzu.github.io/helm-charts | Velero |

## Key Design Decisions

1. **Gateway API over Ingress**: Modern routing with better extensibility
2. **CNPG over embedded databases**: Proper PostgreSQL lifecycle management
3. **Dragonfly over Redis**: 25x performance, 80% less memory
4. **External Secrets over SOPS**: Centralized secret management (migration in progress)
5. **OCI over HTTP repos**: Better caching, signed artifacts

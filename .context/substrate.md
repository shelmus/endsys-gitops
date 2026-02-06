# endsys-gitops Context Documentation

Entry point for AI-assisted development on this GitOps Kubernetes infrastructure.

## Repository Overview

This is a **FluxCD GitOps** repository managing a **Talos Linux** Kubernetes cluster. All infrastructure is declaratively defined in Git and automatically reconciled.

## Quick Navigation

| Document | Purpose |
|----------|---------|
| [architecture/overview.md](architecture/overview.md) | System design and patterns |
| [architecture/app-structure.md](architecture/app-structure.md) | Standard app deployment pattern |
| [architecture/networking.md](architecture/networking.md) | DNS, gateways, and ingress routing |
| [auth/secrets.md](auth/secrets.md) | Secret management strategy |
| [auth/oauth.md](auth/oauth.md) | Authentik OAuth integration |
| [database/cnpg.md](database/cnpg.md) | CloudNativePG patterns |
| [cache/dragonfly.md](cache/dragonfly.md) | Dragonfly cache patterns |
| [monitoring/alerting.md](monitoring/alerting.md) | Prometheus alerts and Discord notifications |
| [glossary.md](glossary.md) | Project terminology |
| [debt.md](debt.md) | Known technical debt |
| [conventions.md](conventions.md) | Naming and coding standards |

## Core Technology Stack

- **OS**: Talos Linux
- **GitOps**: FluxCD (source, kustomize, helm controllers)
- **CNI**: Cilium
- **Ingress**: Gateway API + Cloudflare Tunnels
- **Secrets**: External Secrets Operator + Bitwarden
- **Database**: CloudNativePG (PostgreSQL)
- **Cache**: Dragonfly (Redis-compatible)
- **Certs**: cert-manager + Let's Encrypt
- **Storage**: NFS CSI, Longhorn, SeaweedFS

## Repository Structure

```
kubernetes/
├── apps/                    # Application deployments by namespace
│   ├── {namespace}/
│   │   └── {app}/
│   │       ├── ks.yaml      # Flux Kustomization
│   │       └── app/         # App resources
├── components/
│   └── common/              # Shared Kustomize component
└── flux/
    ├── cluster/             # Bootstrap Kustomizations
    └── meta/repos/          # HelmRepositories
```

## Dependency Chain

```
flux-system
└── cluster-meta (HelmRepositories)
    └── cluster-apps
        ├── infrastructure (cilium, cert-manager, cnpg-operator)
        ├── configs (external-secrets-stores)
        └── apps (immich, authentik, etc.)
```

## Key Patterns

1. **Gateway API over Ingress**: Use HTTPRoute resources
2. **CNPG over embedded DBs**: Prefer CloudNativePG Cluster CRs
3. **External Secrets over SOPS**: Bitwarden as secret source
4. **Dragonfly over Redis**: Better performance, less memory
5. **OCI over HTTP repos**: Prefer OCI HelmRepositories

## AI Assistant Guidelines

When working with this codebase:

1. Always check existing patterns in similar apps before creating new resources
2. Use the standard app structure (ks.yaml + app/ directory)
3. Reference the common component for namespace creation
4. Add appropriate `dependsOn` entries in Kustomizations
5. Use HTTPRoute (not Ingress) for exposing services
6. Prefer CNPG Cluster CRs for PostgreSQL databases
7. Store secrets in Bitwarden, reference via ExternalSecret

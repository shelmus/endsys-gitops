# Glossary

Project-specific terminology for the endsys-gitops repository.

## Flux CD Terms

| Term | Definition |
|------|------------|
| **Kustomization** | Flux CRD that reconciles a path from a Git source |
| **HelmRelease** | Flux CRD that reconciles a Helm chart |
| **GitRepository** | Flux source pointing to a Git repo |
| **OCIRepository** | Flux source pointing to an OCI artifact (Helm chart as container) |
| **Reconciliation** | Process of applying desired state to cluster |
| **dependsOn** | Ordering constraint between Kustomizations |

## Infrastructure Terms

| Term | Definition |
|------|------------|
| **CNPG** | CloudNativePG - PostgreSQL operator for Kubernetes |
| **Dragonfly** | Redis-compatible in-memory store (25x faster, 80% less memory) |
| **ESO** | External Secrets Operator - syncs secrets from external providers |
| **Gateway API** | Kubernetes API for ingress/routing (replaces Ingress) |
| **HTTPRoute** | Gateway API resource defining HTTP routing rules |
| **Talos** | Immutable Linux OS designed for Kubernetes |
| **Cilium** | eBPF-based CNI providing networking and security |

## App Structure Terms

| Term | Definition |
|------|------------|
| **ks.yaml** | Flux Kustomization file (top-level app orchestrator) |
| **helmrelease.yaml** | HelmRelease definition for Helm-deployed apps |
| **httproute.yaml** | Gateway API routing for the app |
| **externalsecret.yaml** | ESO ExternalSecret referencing Bitwarden |
| **postgres-cluster.yaml** | CNPG Cluster CR for PostgreSQL |
| **common component** | Shared Kustomize component at `kubernetes/components/common/` |

## Secret Management Terms

| Term | Definition |
|------|------------|
| **ClusterSecretStore** | Cluster-wide ESO store (bitwarden-secretsmanager) |
| **ExternalSecret** | ESO CRD that syncs a secret from external provider |
| **SOPS** | Mozilla's Secrets OPerationS - encrypts files in Git |
| **Age** | Modern encryption tool used with SOPS |
| **Bitwarden SM** | Bitwarden Secrets Manager - enterprise secret storage |

## Gateway Terms

| Term | Definition |
|------|------------|
| **internal** | Gateway for private network access (k8s-gateway DNS) |
| **external** | Gateway for public internet (Cloudflare tunnel) |
| **parentRefs** | HTTPRoute reference to parent Gateway |
| **sectionName** | Gateway listener (e.g., `https`) |

## Database Terms

| Term | Definition |
|------|------------|
| **Cluster CR** | CNPG Cluster Custom Resource |
| **{name}-rw** | CNPG read-write service endpoint |
| **{name}-app** | CNPG auto-generated secret with credentials |
| **vectorchord** | PostgreSQL extension for AI vector embeddings |
| **postInitApplicationSQL** | SQL run after CNPG database creation |

## Domain Conventions

| Pattern | Example |
|---------|---------|
| `{app}.endsys.cloud` | `immich.endsys.cloud`, `authentik.endsys.cloud` |
| Internal DNS | Resolved by k8s-gateway |
| External DNS | Managed by external-dns + Cloudflare |

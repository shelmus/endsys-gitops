## Rules

<<<<<<< HEAD
### Entry Point
- `.context/substrate.md` - **Start here.** Repository overview, tech stack, and AI guidelines.

### Core Context Files
| File | Purpose |
|------|---------|
| `.context/glossary.md` | Project-specific terminology (Flux, CNPG, etc.) |
| `.context/conventions.md` | Naming standards for files, resources, and secrets |
| `.context/debt.md` | Known technical debt to avoid compounding |

### Architecture
| File | Purpose |
|------|---------|
| `.context/architecture/overview.md` | System design, dependency chain, Flux patterns |
| `.context/architecture/app-structure.md` | Standard app deployment structure (ks.yaml + app/) |
| `.context/architecture/networking.md` | DNS, gateways, Cloudflare tunnel, ingress routing |

### Authentication & Secrets
| File | Purpose |
|------|---------|
| `.context/auth/secrets.md` | External Secrets + Bitwarden integration |
| `.context/auth/oauth.md` | Authentik OAuth/OIDC provider patterns |

### Database & Cache
| File | Purpose |
|------|---------|
| `.context/database/cnpg.md` | CloudNativePG cluster patterns and configuration |
| `.context/cache/dragonfly.md` | Dragonfly (Redis-compatible) cache patterns |

### Backup & Restore
| File | Purpose |
|------|---------|
| `.context/backup-restore.md` | Velero backup strategy, restore procedures, disaster recovery |

### Monitoring
| File | Purpose |
|------|---------|
| `.context/monitoring/alerting.md` | Prometheus alerts, Alertmanager, Discord notifications |

### Architecture Decision Records
| File | Purpose |
|------|---------|
| `.context/decisions/README.md` | ADR template and index |

## Instructions for Claude Code

### Before Generating Manifests
1. Read `.context/substrate.md` first for project orientation
2. Read `.context/conventions.md` for naming standards
3. Check existing apps in `kubernetes/apps/` for reference patterns

### Task-Specific Context

**Adding a new application:**
Read `.context/architecture/app-structure.md`, `.context/conventions.md`

**OAuth/SSO integration:**
Read `.context/auth/oauth.md`, `.context/auth/secrets.md`

**Secret management:**
Read `.context/auth/secrets.md`

**PostgreSQL database setup:**
Read `.context/database/cnpg.md`

**Redis/cache setup:**
Read `.context/cache/dragonfly.md`

**Understanding dependencies:**
Read `.context/architecture/overview.md`

**Networking, DNS, or ingress:**
Read `.context/architecture/networking.md`

**Monitoring or alerting:**
Read `.context/monitoring/alerting.md`

**Backup, restore, or disaster recovery:**
Read `.context/backup-restore.md`

### Code Standards
- Follow naming conventions from `.context/conventions.md`
- Use standard app structure from `.context/architecture/app-structure.md`
- Reference the `common` component for namespace creation
- Add appropriate `dependsOn` entries in Flux Kustomizations
- Use HTTPRoute (not Ingress) for exposing services
- Prefer CNPG Cluster CRs for PostgreSQL databases
- Store secrets in Bitwarden, reference via ExternalSecret
- Use `external-secrets.io/v1` API version (not `v1beta1`)
- Use `Recreate` deployment strategy for apps with ReadWriteOnce PVCs
- Add health probes using dedicated endpoints (`/up`, `/health`), not `/` (avoids redirect issues)
- For containers behind the Gateway, set proxy env vars (e.g., `BEHIND_PROXY=true`) to disable built-in TLS
- Pin container images to specific version tags — never use `latest`

### Do Not
- Generate manifests without checking similar existing apps first
- Use Ingress resources (use HTTPRoute with Gateway API)
- Embed databases in Helm charts (use CNPG operator)
- Store secrets directly in Git (use External Secrets)
- Skip `dependsOn` for resources that need prerequisites
- Override established naming conventions without clear rationale
- Use `external-secrets.io/v1beta1` (cluster runs `v1`)
- Use `RollingUpdate` strategy with ReadWriteOnce PVCs (causes volume deadlock)
- Use `/` as a health probe path (often redirects to HTTPS, failing the probe)
- Change Deployment `spec.selector.matchLabels` on existing resources (field is immutable)
- Use `latest` image tags (non-reproducible, no rollback capability)

### When Making Changes
- Update relevant `.context/` files when adding new patterns
=======
- Use HTTPRoute (Gateway API), never Ingress
- Use CNPG Cluster CRs for PostgreSQL, never embedded Helm subcharts
- Use ExternalSecret + Bitwarden for secrets, never store secrets in Git
- Add `dependsOn` in ks.yaml for all prerequisites
- Reference `common` component at **namespace level**, not app level
- Check existing apps in `kubernetes/apps/` for patterns before creating new ones
- Start YAML files with `---`, use 2-space indentation
- When adding new patterns, update relevant `.context/` files
>>>>>>> 8b0fa57 (change immich to new NAS)
- Document architectural decisions in `.context/decisions/`

## Stack

Talos Linux | FluxCD | Cilium | Gateway API + Cloudflare Tunnels | External Secrets + Bitwarden | CloudNativePG | Dragonfly | cert-manager | NFS CSI, Longhorn, Garage

## Structure

```
kubernetes/
├── apps/{namespace}/{app}/ks.yaml + app/   # App deployments
├── components/common/                       # Shared namespace component
└── flux/                                    # Bootstrap + HelmRepositories
```

Dependency chain: `flux-system` → `cluster-meta` → `cluster-apps` → `{ infrastructure, configs, apps }`

## Naming

| Type | Pattern | Example |
|------|---------|---------|
| Namespace | lowercase, hyphenated; system: `-system` suffix | `immich`, `cnpg-system` |
| Domain | `{app}.endsys.cloud` | `immich.endsys.cloud` |
| Files | `ks.yaml`, `helmrelease.yaml`, `httproute.yaml`, `externalsecret.yaml`, `postgres-cluster.yaml` | |
| HelmRelease / Kustomization | `{app}` | `immich` |
| CNPG Cluster | `{app}-postgres` | `immich-postgres` |
| Secret | `{app}-secrets` or `{app}-{purpose}` | `pocket-id-secrets` |
| Bitwarden key | `{app}-{purpose}` | `immich-oauth-client-secret` |

## Gateways

| Gateway | IP | Purpose |
|---------|-----|---------|
| `internal` | 10.127.0.51 | Private LAN access |
| `external` | 10.127.0.52 | Public via Cloudflare Tunnel |

## Templates

### ks.yaml

```yaml
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: &app my-app
  namespace: &namespace my-app
spec:
  commonMetadata:
    labels:
      app.kubernetes.io/name: *app
  dependsOn:
    - name: external-secrets-stores
      namespace: external-secrets
    # - name: cnpg-operator
    #   namespace: cnpg-system
    # - name: csi-driver-nfs
    #   namespace: kube-system
  interval: 1h
  path: ./kubernetes/apps/my-app/my-app/app
  prune: true
  sourceRef:
    kind: GitRepository
    name: flux-system
    namespace: flux-system
  targetNamespace: *namespace
  timeout: 5m
```

### Namespace kustomization.yaml

```yaml
---
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: my-namespace
components:
  - ../../components/common
resources:
  - ./my-app/ks.yaml
```

### App kustomization.yaml

```yaml
---
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ./helmrelease.yaml
  - ./httproute.yaml
  - ./externalsecret.yaml
```

### HTTPRoute

```yaml
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: my-app
spec:
  parentRefs:
    - name: internal    # or 'external' for public
      namespace: kube-system
      sectionName: https
  hostnames:
    - my-app.endsys.cloud
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /
      backendRefs:
        - name: my-app
          port: 80
```

### ExternalSecret

```yaml
---
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
    name: my-app-secrets
    creationPolicy: Owner
    deletionPolicy: Retain
  data:
    - secretKey: password
      remoteRef:
        key: my-app-database-password
```

### CNPG Cluster

```yaml
---
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

Auto-created secrets: `{cluster}-app` (credentials), `{cluster}-superuser`. Services: `{cluster}-rw` (primary), `{cluster}-ro` (replicas).

## Deep Dives

Only read these for tasks that specifically need detailed procedures:

| Task | File |
|------|------|
| Backup/restore procedures | `.context/backup-restore.md` |
| Alerting rules & Alertmanager config | `.context/monitoring/alerting.md` |
| Dragonfly/BullMQ setup details | `.context/cache/dragonfly.md` |
| OAuth/OIDC with PocketID | `.context/auth/oauth.md` |
| Full DNS/networking architecture | `.context/architecture/networking.md` |
| Technical debt registry | `.context/debt.md` |
| Terminology definitions | `.context/glossary.md` |
| USB device passthrough (Talos) | `.context/hardware/usb-passthrough.md` |
| System design & Flux patterns | `.context/architecture/overview.md` |
| Full app structure details | `.context/architecture/app-structure.md` |
| Secret management details | `.context/auth/secrets.md` |

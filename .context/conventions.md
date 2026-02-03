# Naming Conventions & Standards

## Namespace Naming

- Lowercase, hyphenated
- System namespaces end with `-system`: `kube-system`, `flux-system`, `cnpg-system`
- App namespaces match app name: `immich`, `authentik`, `n8n`

## File Naming

| File Type | Convention | Example |
|-----------|------------|---------|
| Flux Kustomization | `ks.yaml` | `kubernetes/apps/immich/immich/ks.yaml` |
| Kustomize file | `kustomization.yaml` | `kubernetes/apps/immich/immich/app/kustomization.yaml` |
| HelmRelease | `helmrelease.yaml` | `kubernetes/apps/immich/immich/app/helmrelease.yaml` |
| HTTPRoute | `httproute.yaml` | `kubernetes/apps/immich/immich/app/httproute.yaml` |
| ExternalSecret | `externalsecret.yaml` | `kubernetes/apps/immich/immich/app/externalsecret.yaml` |
| CNPG Cluster | `postgres-cluster.yaml` | `kubernetes/apps/immich/immich/app/postgres-cluster.yaml` |
| SOPS Secret | `secret.sops.yaml` | `kubernetes/apps/velero/velero/app/secret.sops.yaml` |
| PersistentVolume | `{name}-pv.yaml` | `library-pv.yaml` |
| PersistentVolumeClaim | `{name}-pvc.yaml` | `library-pvc.yaml` |

## Resource Naming

| Resource | Pattern | Example |
|----------|---------|---------|
| HelmRelease | `{app-name}` | `immich`, `authentik` |
| Kustomization | `{app-name}` | `immich`, `cluster-meta` |
| CNPG Cluster | `{app}-postgres` | `immich-postgres` |
| Secret (general) | `{app}-secrets` | `authentik-secrets` |
| Secret (OAuth) | `{app}-oauth` | `immich-oauth` |
| Secret (CNPG auto) | `{cluster}-app` | `immich-postgres-app` |
| Service | `{app}` or `{app}-{component}` | `immich-server` |
| ConfigMap | `{app}-config` or `{app}-{purpose}` | `authentik-blueprint-immich` |

## Domain Naming

```
{app-name}.endsys.cloud
```

Examples:
- `immich.endsys.cloud`
- `authentik.endsys.cloud`
- `grafana.endsys.cloud`

## Label Standards

Always include Kubernetes recommended labels:

```yaml
labels:
  app.kubernetes.io/name: {app-name}
  app.kubernetes.io/instance: {instance-name}
  app.kubernetes.io/component: {component}
  app.kubernetes.io/part-of: {system}
```

## YAML Standards

### Indentation
- 2 spaces (no tabs)

### Schema Annotations
Include YAML language server schema for IDE support:

```yaml
# yaml-language-server: $schema=https://json.schemastore.org/kustomization
```

Common schemas:
- Kustomization: `https://json.schemastore.org/kustomization`
- Flux Kustomization: `https://raw.githubusercontent.com/fluxcd-community/flux2-schemas/main/kustomization-kustomize-v1.json`
- HelmRelease: `https://kubernetes-schemas.pages.dev/helm.toolkit.fluxcd.io/helmrelease_v2.json`

### Document Separators
Start each file with `---`:

```yaml
---
apiVersion: v1
kind: ConfigMap
```

## Directory Structure

Standard app layout:

```
kubernetes/apps/{namespace}/{app-name}/
├── ks.yaml                  # Flux Kustomization
└── app/
    ├── kustomization.yaml   # Resources list
    ├── helmrelease.yaml     # Helm chart
    ├── httproute.yaml       # Ingress
    └── [additional resources]
```

Namespace-level kustomization:

```
kubernetes/apps/{namespace}/
└── kustomization.yaml       # References common component + app ks.yaml
```

## Bitwarden Secret Naming

Secrets in Bitwarden Secrets Manager:

| Pattern | Example |
|---------|---------|
| `{app}-{purpose}` | `immich-oauth-client-secret` |
| `{app}-{service}-password` | `authentik-postgresql-password` |
| `{app}-secret-key` | `authentik-secret-key` |

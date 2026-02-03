# Application Structure

Standard deployment pattern for applications in this GitOps repository.

## Directory Layout

```
kubernetes/apps/{namespace}/{app-name}/
├── ks.yaml                    # Flux Kustomization (orchestrates the app)
└── app/
    ├── kustomization.yaml     # Kustomize resources list
    ├── helmrelease.yaml       # HelmRelease (if Helm-based)
    ├── httproute.yaml         # Gateway API routing
    ├── externalsecret.yaml    # External Secrets (if secrets needed)
    ├── postgres-cluster.yaml  # CNPG Cluster (if database needed)
    └── [additional resources]
```

## File Descriptions

### ks.yaml - Flux Kustomization

The top-level orchestrator that tells Flux what to deploy and when.

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
    - name: cnpg-operator
      namespace: cnpg-system
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

Key fields:
- `dependsOn`: Ensures prerequisites are ready before deploying
- `path`: Points to the app/ directory
- `targetNamespace`: Where resources are created

### kustomization.yaml - Resource List

Lists all resources to deploy. Uses common component for namespace creation.

```yaml
---
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: my-app
components:
  - ../../../../components/common
resources:
  - ./helmrelease.yaml
  - ./httproute.yaml
  - ./externalsecret.yaml
  - ./postgres-cluster.yaml
```

### helmrelease.yaml - Helm Deployment

Defines the Helm chart and values.

```yaml
---
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: my-app
spec:
  interval: 1h
  chart:
    spec:
      chart: my-app
      version: 1.0.0
      sourceRef:
        kind: HelmRepository
        name: my-repo
        namespace: flux-system
  values:
    # Chart-specific values
```

### httproute.yaml - Ingress Routing

Gateway API HTTPRoute for external access.

```yaml
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: my-app
spec:
  parentRefs:
    - name: internal          # or 'external' for public access
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

## Namespace-Level Kustomization

Each namespace has a top-level kustomization that includes all apps:

```
kubernetes/apps/{namespace}/
└── kustomization.yaml
```

```yaml
---
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: my-namespace
components:
  - ../../components/common
resources:
  - ./app-one/ks.yaml
  - ./app-two/ks.yaml
```

## Common Component

Located at `kubernetes/components/common/`, this shared component:
- Creates the namespace
- Applies standard labels
- Sets up any namespace-level defaults

## Dependency Patterns

### Database Dependencies
Apps using CNPG must depend on the operator:

```yaml
dependsOn:
  - name: cnpg-operator
    namespace: cnpg-system
```

### Secret Dependencies
Apps using External Secrets must wait for the store:

```yaml
dependsOn:
  - name: external-secrets-stores
    namespace: external-secrets
```

### Storage Dependencies
Apps using NFS must wait for the CSI driver:

```yaml
dependsOn:
  - name: csi-driver-nfs
    namespace: kube-system
```

## Example: Complete App

For an app with database, secrets, and ingress:

```
kubernetes/apps/my-app/my-app/
├── ks.yaml                    # dependsOn: cnpg-operator, external-secrets-stores
└── app/
    ├── kustomization.yaml     # Lists all resources
    ├── helmrelease.yaml       # Helm chart deployment
    ├── httproute.yaml         # my-app.endsys.cloud routing
    ├── externalsecret.yaml    # Syncs secrets from Bitwarden
    └── postgres-cluster.yaml  # CNPG PostgreSQL cluster
```

## Adding a New Application

1. Create directory structure under `kubernetes/apps/{namespace}/{app}/`
2. Create `ks.yaml` with appropriate `dependsOn`
3. Create `app/kustomization.yaml` with common component
4. Create `app/helmrelease.yaml` or raw manifests
5. Create `app/httproute.yaml` if external access needed
6. Create `app/externalsecret.yaml` if secrets needed
7. Add `ks.yaml` reference to namespace `kustomization.yaml`
8. Commit and push - Flux will reconcile automatically

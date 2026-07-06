# Hindsight Kubernetes + Ollama Implementation Plan

> **For Hermes:** This is a planning artifact only. Do not apply cluster changes until Sean explicitly approves implementation.

**Goal:** Add a self-hosted Hindsight instance to the Talos/Flux Kubernetes cluster and connect it to the existing local Ollama service on Yggdrasil so Hermes/Mimir can use it as an agent memory backend.

**Architecture:** Deploy Hindsight with its upstream OCI Helm chart through Flux. Use the existing Gateway API pattern for access, the local Yggdrasil Ollama endpoint for LLM calls, and CloudNativePG for PostgreSQL instead of the chart's embedded PostgreSQL. Start with a conservative single-replica deployment, local Hindsight embeddings/reranker, observations disabled, and low LLM concurrency.

**Tech Stack:** FluxCD, OCIRepository, HelmRelease, Gateway API HTTPRoute, External Secrets + Bitwarden, CloudNativePG, Longhorn, Hindsight chart `oci://ghcr.io/vectorize-io/charts/hindsight`, local Ollama at `10.127.0.4:11434`.

---

## Confirmed Context

- GitOps repo: `/home/sean/src/endsys-gitops`
- Cluster context: `admin@kubernetes`
- Existing Gateway API gateways:
  - `kube-system/internal` at `10.127.0.51`
  - `kube-system/external` at `10.127.0.52`
- Default storage class: `longhorn`
- Hindsight upstream chart:
  - OCI chart: `oci://ghcr.io/vectorize-io/charts/hindsight`
  - current upstream `Chart.yaml`: `version: 0.8.4`, `appVersion: 0.8.4`
  - chart values expose `api.env`, `api.secrets`, `existingSecret`, `postgresql.enabled`, `postgresql.external.*`, `tei.*`, and `api.persistence.modelCache`
- Local Ollama on Yggdrasil:
  - host IP: `10.127.0.4`
  - service bind: `OLLAMA_HOST=0.0.0.0:11434`
  - verified local API: `http://127.0.0.1:11434/api/tags`
  - current model: `gemma4:e4b`
  - context configured: `OLLAMA_CONTEXT_LENGTH=131072`
- Hindsight + Ollama docs:
  - `HINDSIGHT_API_LLM_PROVIDER=ollama`
  - `HINDSIGHT_API_LLM_BASE_URL=http://<ollama-host>:11434/v1`
  - `HINDSIGHT_API_LLM_MODEL=<model>`
  - local deployments should set `HINDSIGHT_API_LLM_MAX_CONCURRENT=1`
  - disable observations initially with `HINDSIGHT_API_ENABLE_OBSERVATIONS=false`
  - `reflect` requires an Ollama model with tool/function calling support; not all local models provide it.

## Important Constraints

1. **No live mutation without approval.** Adding this app means repo edits, Bitwarden secret creation, Flux reconciliation, new PVCs, new database, and possibly DNS/Gateway exposure. All are mutations.
2. **Repo standard says CNPG, not embedded chart PostgreSQL.** The Hindsight chart defaults to an embedded `ankane/pgvector:latest` PostgreSQL StatefulSet. Do not use that for the final deployment unless Sean explicitly accepts a quick-and-dirty MVP.
3. **The Hindsight chart has a secret-shape mismatch with CNPG.** CNPG app secrets expose `password`; the Hindsight chart expects `postgres-password` when using external PostgreSQL. Use ExternalSecret/HelmRelease `valuesFrom` or a purpose-built secret rather than putting the password in Git.
4. **Current local model may be only a bootstrap choice.** `gemma4:e4b` may be enough for retain/recall testing, but Hindsight docs recommend a tool-calling Ollama model such as `gpt-oss:20b` for `reflect`.
5. **Hermes integration is separate from app deployment.** After Hindsight is healthy, configure Hermes to use the self-hosted API URL and verify `hermes memory status` / plugin tools. Do not disable Hermes built-in memory until the new backend proves useful.

---

## Proposed Deployment Shape

### Namespace and URL

- Namespace: `hindsight`
- Internal UI hostname: `hindsight.endsys.cloud`
- Gateway: start on `internal`, not `external`
- API service path: prefer a separate internal route hostname if the chart/UI path routing proves awkward:
  - UI: `https://hindsight.endsys.cloud` → `hindsight-control-plane:3000`
  - API: `https://hindsight-api.endsys.cloud` → `hindsight-api:8888`

Reason: the upstream chart's Ingress example uses `/api`, but this repo uses HTTPRoute. A separate API hostname avoids path-prefix rewrite assumptions.

### Database

Use a CNPG cluster:

- Cluster: `hindsight-postgres`
- Database: `hindsight`
- Owner: `hindsight`
- Instances: `1` initially
- Image: `ghcr.io/tensorchord/cloudnative-vectorchord:16.9-0.4.3`
  - Note: server dry-run rejected `pgvector/pgvector:0.8.4-pg16` as an unsupported CNPG PostgreSQL image, so the implementation uses the CNPG-compatible VectorChord image instead.
  - Live verification still needs to confirm `CREATE EXTENSION vector` succeeds when the cluster initializes.
- Extension: `CREATE EXTENSION IF NOT EXISTS vector;`
- Storage: `longhorn`, 10Gi to start
- Secret wiring: use CNPG's generated `hindsight-postgres-app` secret and feed its `password` key into the HelmRelease with `valuesFrom`, avoiding committed database credentials.

### Hindsight API settings

Use the chart with external PostgreSQL and local Ollama:

```yaml
api:
  env:
    HINDSIGHT_API_LLM_PROVIDER: "ollama"
    HINDSIGHT_API_LLM_BASE_URL: "http://10.127.0.4:11434/v1"
    HINDSIGHT_API_LLM_MODEL: "gemma4:e4b"
    HINDSIGHT_API_LLM_MAX_CONCURRENT: "1"
    HINDSIGHT_API_ENABLE_OBSERVATIONS: "false"
    HINDSIGHT_API_VECTOR_EXTENSION: "pgvector"
    HINDSIGHT_API_LLM_TEMPERATURE: "none"
  persistence:
    modelCache:
      enabled: true
      storageClass: longhorn
      size: 5Gi
  resources:
    requests:
      cpu: 500m
      memory: 1Gi
    limits:
      cpu: 2000m
      memory: 4Gi

postgresql:
  enabled: false
  external:
    host: "hindsight-postgres-rw"
    port: 5432
    database: "hindsight"
    username: "hindsight"
    # password supplied by HelmRelease valuesFrom / ExternalSecret, not Git

worker:
  enabled: false

controlPlane:
  enabled: true
```

Later tuning:

- If `gemma4:e4b` fails structured extraction or `reflect`, pull and switch to `gpt-oss:20b` on Yggdrasil if memory/GPU budget allows.
- Enable `worker.enabled=true` only after the single API-pod deployment is stable.
- Re-enable observations only after local LLM latency is understood.
- Consider TEI embedding/reranker only if the built-in local model path is too slow or causes repeated model downloads despite the cache PVC.

---

## Files to Add or Modify

### 1. Add Hindsight OCI chart source

Create:

`kubernetes/flux/meta/repos/hindsight.yaml`

```yaml
---
apiVersion: source.toolkit.fluxcd.io/v1
kind: OCIRepository
metadata:
  name: hindsight
  namespace: flux-system
spec:
  interval: 5m
  layerSelector:
    mediaType: application/vnd.cncf.helm.chart.content.v1.tar+gzip
    operation: copy
  ref:
    tag: 0.8.4
  url: oci://ghcr.io/vectorize-io/charts/hindsight
```

Modify:

`kubernetes/flux/meta/repos/kustomization.yaml`

Add:

```yaml
  - ./hindsight.yaml
```

### 2. Add namespace-level app kustomization

Create:

`kubernetes/apps/hindsight/kustomization.yaml`

```yaml
---
# yaml-language-server: $schema=https://json.schemastore.org/kustomization
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: hindsight
components:
  - ../../components/common
resources:
  - ./hindsight/ks.yaml
```

Open issue: this repo currently has `cluster-apps` pointing at `./kubernetes/apps`, but `/home/sean/src/endsys-gitops/kubernetes/apps/kustomization.yaml` was not present during inspection. Before implementation, resolve how namespace-level kustomizations are currently included by Flux. If the file is genuinely absent, add a root `kubernetes/apps/kustomization.yaml` that lists all namespace kustomizations before adding `hindsight`.

### 3. Add Flux Kustomization for the app

Create:

`kubernetes/apps/hindsight/hindsight/ks.yaml`

```yaml
---
# yaml-language-server: $schema=https://raw.githubusercontent.com/fluxcd-community/flux2-schemas/main/kustomization-kustomize-v1.json
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: &app hindsight
  namespace: &namespace hindsight
spec:
  commonMetadata:
    labels:
      app.kubernetes.io/name: *app
  dependsOn:
    - name: cnpg-operator
      namespace: cnpg-system
  interval: 1h
  path: ./kubernetes/apps/hindsight/hindsight/app
  prune: true
  retryInterval: 2m
  sourceRef:
    kind: GitRepository
    name: flux-system
    namespace: flux-system
  targetNamespace: *namespace
  timeout: 10m
  wait: false
```

### 4. Add app resource kustomization

Create:

`kubernetes/apps/hindsight/hindsight/app/kustomization.yaml`

```yaml
---
# yaml-language-server: $schema=https://json.schemastore.org/kustomization
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ./postgres-cluster.yaml
  - ./helmrelease.yaml
  - ./httproute.yaml
```

### 5. Use CNPG-generated database credentials

No separate Bitwarden item or ExternalSecret is required for the initial deployment. CNPG generates the application secret for the database owner as `hindsight-postgres-app`. The HelmRelease consumes that secret with `valuesFrom`:

```yaml
valuesFrom:
  - kind: Secret
    name: hindsight-postgres-app
    valuesKey: password
    targetPath: postgresql.external.password
```

This keeps the database password out of Git while avoiding the chart's `existingSecret`/`envFrom` edge case around non-env-var keys like `postgres-password`.

### 6. Add CNPG cluster

Create:

`kubernetes/apps/hindsight/hindsight/app/postgres-cluster.yaml`

```yaml
---
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: hindsight-postgres
spec:
  instances: 1
  imageName: ghcr.io/tensorchord/cloudnative-vectorchord:16.9-0.4.3
  bootstrap:
    initdb:
      database: hindsight
      owner: hindsight
      postInitApplicationSQL:
        - CREATE EXTENSION IF NOT EXISTS vector;
  storage:
    storageClass: longhorn
    size: 10Gi
```

Implementation gate: verify that the selected image supports the `vector` extension. If not, use a known pgvector CNPG image and pin a non-`latest` tag.

### 7. Add Hindsight HelmRelease

Create:

`kubernetes/apps/hindsight/hindsight/app/helmrelease.yaml`

```yaml
---
# yaml-language-server: $schema=https://kubernetes-schemas.pages.dev/helm.toolkit.fluxcd.io/helmrelease_v2.json
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: hindsight
spec:
  interval: 1h
  chartRef:
    kind: OCIRepository
    name: hindsight
    namespace: flux-system
  install:
    remediation:
      retries: 3
  upgrade:
    cleanupOnFail: true
    remediation:
      strategy: rollback
      retries: 3
  valuesFrom:
    - kind: Secret
      name: hindsight-postgres-app
      valuesKey: password
      targetPath: postgresql.external.password
  values:
    postgresql:
      enabled: false
      external:
        host: hindsight-postgres-rw
        port: 5432
        database: hindsight
        username: hindsight

    api:
      env:
        HINDSIGHT_API_LLM_PROVIDER: "ollama"
        HINDSIGHT_API_LLM_BASE_URL: "http://10.127.0.4:11434/v1"
        HINDSIGHT_API_LLM_MODEL: "gemma4:e4b"
        HINDSIGHT_API_LLM_MAX_CONCURRENT: "1"
        HINDSIGHT_API_ENABLE_OBSERVATIONS: "false"
        HINDSIGHT_API_VECTOR_EXTENSION: "pgvector"
        HINDSIGHT_API_LLM_TEMPERATURE: "none"
      persistence:
        modelCache:
          enabled: true
          storageClass: longhorn
          size: 5Gi
      resources:
        requests:
          cpu: 500m
          memory: 1Gi
        limits:
          cpu: 2000m
          memory: 4Gi

    worker:
      enabled: false

    controlPlane:
      enabled: true
      resources:
        requests:
          cpu: 50m
          memory: 128Mi
        limits:
          memory: 512Mi
```

### 8. Add HTTPRoute

Create:

`kubernetes/apps/hindsight/hindsight/app/httproute.yaml`

Start internal-only:

```yaml
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: hindsight
  labels:
    app.kubernetes.io/name: hindsight
    app.kubernetes.io/instance: hindsight
    app.kubernetes.io/part-of: hindsight
spec:
  parentRefs:
    - name: internal
      namespace: kube-system
      sectionName: https
  hostnames:
    - hindsight.endsys.cloud
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /
      backendRefs:
        - name: hindsight-control-plane
          port: 3000
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: hindsight-api
  labels:
    app.kubernetes.io/name: hindsight
    app.kubernetes.io/instance: hindsight
    app.kubernetes.io/component: api
    app.kubernetes.io/part-of: hindsight
spec:
  parentRefs:
    - name: internal
      namespace: kube-system
      sectionName: https
  hostnames:
    - hindsight-api.endsys.cloud
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /
      backendRefs:
        - name: hindsight-api
          port: 8888
```

If DNS for those names is not automatically handled by the existing k8s-gateway/Pi-hole path, add DNS after explicit approval.

### 9. Add Velero schedule after the app proves stable

Create:

`kubernetes/apps/velero/velero/app/schedules/hindsight-schedule.yaml`

Add to:

`kubernetes/apps/velero/velero/app/kustomization.yaml`

Use existing namespace schedule patterns. Include namespace `hindsight`, PVC snapshots, and a daily cadence similar to the other app schedules.

### 10. Optional: add Gatus checks

Modify:

`kubernetes/apps/gatus/gatus/app/helmrelease.yaml`

Add checks for:

- `https://hindsight.endsys.cloud`
- `https://hindsight-api.endsys.cloud/health`

Only after internal DNS/route is working.

---

## Validation Plan

### Pre-implementation validation

Run from `/home/sean/src/endsys-gitops`:

```bash
git status --short --branch
kubectl config current-context
kubectl get nodes -o wide
kubectl get storageclass
kubectl get gateway -A
kubectl get cluster -A
kubectl -n flux-system get ocirepository,helmrepository,gitrepository
curl -fsS http://10.127.0.4:11434/api/tags | jq '.models[].name'
```

Expected:

- context is `admin@kubernetes`
- `longhorn` exists and is default
- `kube-system/internal` gateway is programmed
- Ollama returns `gemma4:e4b` or the selected model

### Local manifest validation

Run after creating files, before committing:

```bash
kubectl kustomize kubernetes/flux/meta >/tmp/meta.yaml
kubectl kustomize kubernetes/apps/hindsight >/tmp/hindsight-namespace.yaml
kubectl kustomize kubernetes/apps/hindsight/hindsight/app >/tmp/hindsight-app.yaml
kubectl apply --dry-run=server -f /tmp/meta.yaml
kubectl apply --dry-run=server -f /tmp/hindsight-namespace.yaml
kubectl apply --dry-run=server -f /tmp/hindsight-app.yaml
```

If the root `kubernetes/apps/kustomization.yaml` is restored/added:

```bash
kubectl kustomize kubernetes/apps >/tmp/apps.yaml
kubectl apply --dry-run=server -f /tmp/apps.yaml
```

Also run:

```bash
git diff --check
```

### Flux validation after approval and merge

```bash
flux get sources oci -A | grep hindsight
flux get kustomizations -A | grep hindsight
flux get helmreleases -A | grep hindsight
kubectl -n hindsight get pods,svc,pvc,httproute
kubectl -n hindsight get cluster hindsight-postgres
kubectl -n hindsight logs deploy/hindsight-api --tail=120
```

Expected:

- OCI source ready for chart tag `0.8.4`
- CNPG cluster healthy
- Hindsight API and control plane pods ready
- PVCs bound
- HTTPRoutes accepted

### API smoke test

Port-forward first to avoid DNS ambiguity:

```bash
kubectl -n hindsight port-forward svc/hindsight-api 8888:8888
curl -fsS http://127.0.0.1:8888/health
```

Then test the routed endpoint from LAN:

```bash
curl -fsS https://hindsight-api.endsys.cloud/health
```

### Memory smoke test

Use a temporary client environment rather than Hermes first:

```bash
python -m venv /tmp/hindsight-test
/tmp/hindsight-test/bin/python -m pip install hindsight-client
/tmp/hindsight-test/bin/python - <<'PY'
from hindsight_client import Hindsight

h = Hindsight(base_url="http://127.0.0.1:8888")
# TODO: adjust exact client calls to current SDK API after inspecting installed package docs.
print(h)
PY
```

If the SDK API has changed, use raw HTTP endpoints from the Hindsight API docs. The acceptance criteria are:

1. create or use a `hermes` memory bank,
2. retain one harmless test fact,
3. recall the fact,
4. optionally try reflect only if the selected Ollama model supports tool calling.

### Hermes integration validation

After Hindsight API is healthy:

1. Load the `hermes-agent` skill before changing Hermes config.
2. Configure the default Hermes profile to use Hindsight self-hosted API.
3. Prefer tools-only or hybrid with conservative recall budget initially.
4. Verify with:

```bash
hermes memory status
hermes tools
```

5. Send one test conversation through Discord and confirm the memory is retained/recalled.
6. Only then decide whether to disable the built-in local Hermes `memory` tool.

---

## Rollback Plan

If deployment fails before real use:

1. Revert the Git commit containing Hindsight manifests.
2. Let Flux prune resources.
3. If PVCs or CNPG resources remain due to finalizers/retention, inspect first:

```bash
kubectl -n hindsight get all,pvc,cluster,secrets,externalsecret,httproute
```

4. Ask Sean before deleting retained PVCs, database clusters, or Bitwarden secrets.

If Hermes integration causes poor memory injection:

1. Set Hermes memory provider back to built-in/local or disable Hindsight plugin config.
2. Keep the Hindsight app running until memory export/retention is reviewed.
3. Do not delete the database until Sean confirms no stored memory is worth preserving.

---

## Open Questions for Sean

1. Should Hindsight be **internal-only** at `hindsight.endsys.cloud` / `hindsight-api.endsys.cloud`, or public behind Cloudflare later?
2. Are you willing to pull a tool-calling Ollama model such as `gpt-oss:20b` on Yggdrasil for better Hindsight `reflect`, or should we bootstrap with existing `gemma4:e4b` first?
3. Should this become Hermes's primary memory backend immediately after smoke tests, or should it run tools-only while we compare it against built-in Hermes memory?

---

## Acceptance Criteria

- Hindsight manifests are committed in GitOps format and render cleanly.
- Flux shows the Hindsight OCI source, app Kustomization, and HelmRelease as ready.
- CNPG-backed PostgreSQL is healthy with pgvector enabled.
- Hindsight API `/health` passes through port-forward and internal Gateway route.
- Hindsight can reach Ollama at `10.127.0.4:11434` and perform at least one retain/recall cycle.
- Hermes can connect to the self-hosted Hindsight API and expose/consume the memory tools or automatic recall according to the chosen mode.

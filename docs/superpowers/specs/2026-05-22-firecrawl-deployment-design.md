# Firecrawl Deployment — Design Spec

**Date:** 2026-05-22
**Status:** Approved (pending user review of written spec)
**Author:** Brainstormed with Claude

## Summary

Deploy [Firecrawl](https://github.com/firecrawl/firecrawl) to the cluster as an internal-only web scraping / crawling API, primarily consumed by n8n workflows and other in-cluster apps. Uses the upstream Helm chart (`oci://registry-1.docker.io/winkkgmbh/firecrawl`, v0.2.0) with its bundled data dependencies (Redis, RabbitMQ, PostgreSQL). Exposed via Gateway API HTTPRoute on the `internal` gateway at `firecrawl.endsys.cloud`.

## Goals

- Expose a stable Firecrawl `/scrape`, `/crawl`, and `/map` API to in-cluster consumers (n8n, Coder workspaces).
- Follow the repo's standard app deployment structure (ks.yaml + app/ with OCIRepository for the Helm source).
- Keep the deployment minimal: no LLM/extract features, no auth, no external exposure.

## Non-goals

- LLM-backed `/extract` endpoint and structured-output features.
- API authentication / bearer tokens.
- External (Cloudflare Tunnel) exposure.
- Velero backup policy for the bundled PVCs (crawl state is transient).
- Resource tuning beyond modest defaults — tune later once real workload exists.

## Architecture

```
kubernetes/
├── flux/meta/repos/
│   └── firecrawl.yaml                 # NEW — OCIRepository
└── apps/
    └── firecrawl/                     # NEW namespace
        ├── kustomization.yaml         # references common component + ./firecrawl/ks.yaml
        └── firecrawl/
            ├── ks.yaml                # Flux Kustomization; dependsOn external-secrets-stores
            └── app/
                ├── kustomization.yaml
                ├── helmrelease.yaml   # wraps chart; overrides image, deps, ingress off
                └── httproute.yaml     # firecrawl.endsys.cloud → firecrawl-firecrawl-api:3002
```

All eight workloads (API, queue worker, Playwright service, Redis, RabbitMQ, NUQ Postgres; with `extractWorker` and `nuqPrefetchWorker` disabled) run inside the `firecrawl` namespace, managed entirely by the upstream chart.

Pattern matches `kubernetes/apps/n8n/` exactly (OCIRepository source + HelmRelease consumer + HTTPRoute), so no new conventions are introduced.

## Components

### 1. OCIRepository (`kubernetes/flux/meta/repos/firecrawl.yaml`)

```yaml
---
apiVersion: source.toolkit.fluxcd.io/v1
kind: OCIRepository
metadata:
  name: firecrawl-helm
  namespace: flux-system
spec:
  interval: 5m0s
  url: oci://registry-1.docker.io/winkkgmbh/firecrawl
  ref:
    tag: 0.2.0
```

Registered in `kubernetes/flux/meta/repos/kustomization.yaml` alongside the existing OCI sources.

### 2. Namespace kustomization (`kubernetes/apps/firecrawl/kustomization.yaml`)

```yaml
---
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: firecrawl
components:
  - ../../components/common
resources:
  - ./firecrawl/ks.yaml
```

The `common` component creates the `firecrawl` namespace.

### 3. Flux Kustomization (`kubernetes/apps/firecrawl/firecrawl/ks.yaml`)

```yaml
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: &app firecrawl
  namespace: &namespace firecrawl
spec:
  commonMetadata:
    labels:
      app.kubernetes.io/name: *app
  dependsOn:
    - name: external-secrets-stores
      namespace: external-secrets
  interval: 1h
  path: ./kubernetes/apps/firecrawl/firecrawl/app
  prune: true
  retryInterval: 2m
  sourceRef:
    kind: GitRepository
    name: flux-system
    namespace: flux-system
  targetNamespace: *namespace
  timeout: 5m
  wait: false
```

`external-secrets-stores` is kept as a soft dependency to make future secret additions (e.g. an OpenAI key) drop-in without ks.yaml edits.

### 4. HelmRelease (`kubernetes/apps/firecrawl/firecrawl/app/helmrelease.yaml`)

Overrides the chart's defaults conservatively. Final value paths must be verified against the chart's `values.yaml` before commit (see Open Implementation Questions).

```yaml
---
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: firecrawl
spec:
  interval: 1h
  chartRef:
    kind: OCIRepository
    name: firecrawl-helm
    namespace: flux-system
  install:
    remediation:
      retries: 3
  upgrade:
    cleanupOnFail: true
    remediation:
      strategy: rollback
      retries: 3
  values:
    # Pin to official GHCR x86 images (cluster is all amd64)
    image:
      api:        { repository: ghcr.io/firecrawl/firecrawl,         tag: <pinned> }
      worker:     { repository: ghcr.io/firecrawl/firecrawl,         tag: <pinned> }
      playwright: { repository: ghcr.io/firecrawl/playwright-service, tag: <pinned> }
      # Exact key shape verified during implementation (see Open Questions).

    # Auth off — internal gateway only
    secret:
      useDbAuthentication: "false"

    # No LLM
    config:
      extra: {}

    # Bundled deps (deliberate deviation — see Known Deviations)
    rabbitmq:           { enabled: true,  persistence: { enabled: true,  size: 2Gi } }
    redis:              { enabled: true,  persistence: { enabled: true,  size: 2Gi } }
    postgresql:         { enabled: true,  persistence: { enabled: true,  size: 10Gi } }
    extractWorker:      { enabled: false }    # scrape/crawl only
    nuqPrefetchWorker:  { enabled: false }    # optional perf worker; off for now

    # Use our HTTPRoute, not the chart's built-in route/ingress
    ingress: { enabled: false }
    route:   { enabled: false }

    resources:
      enabled: true     # opt in to modest requests/limits; tune later
```

### 5. HTTPRoute (`kubernetes/apps/firecrawl/firecrawl/app/httproute.yaml`)

```yaml
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: firecrawl
spec:
  parentRefs:
    - name: internal
      namespace: kube-system
      sectionName: https
  hostnames:
    - firecrawl.endsys.cloud
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /
      backendRefs:
        - name: firecrawl-firecrawl-api     # chart releases as <release>-firecrawl-api
          port: 3002
```

Service name must be verified after first install (see Open Questions).

### 6. App kustomization (`kubernetes/apps/firecrawl/firecrawl/app/kustomization.yaml`)

```yaml
---
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ./helmrelease.yaml
  - ./httproute.yaml
```

## Data flow

In-cluster consumer (preferred — zero gateway hop, no TLS overhead):

```
n8n pod
  → http://firecrawl-firecrawl-api.firecrawl.svc.cluster.local:3002/v1/scrape
    → Firecrawl API
      → publishes job to RabbitMQ
        → queue worker picks up
          → calls Playwright service for browser-based scraping
            → writes results to NUQ Postgres + Redis cache
              → API returns to caller
```

Via HTTPRoute (for ad-hoc access from inside LAN, e.g. browser/curl):

```
client (LAN) → internal Gateway (10.127.0.51:443)
            → HTTPRoute firecrawl
              → Service firecrawl-firecrawl-api:3002
                → API pod (rest as above)
```

n8n workflows should default to the cluster-DNS form to avoid the gateway round-trip.

## Known Deviations from Repo Conventions

These are deliberate trade-offs to use the upstream chart unmodified. Worth recording in `.context/debt.md` once deployed.

| Deviation | Convention violated | Justification |
|---|---|---|
| Bundled PostgreSQL (NUQ DB) | "Use CNPG Cluster CRs, don't embed databases in Helm charts" (CLAUDE.md) | Chart's NUQ schema is tightly coupled to its bundled Postgres; running CNPG would require a chart fork or extensive value/initdb overrides. NUQ data is operational/transient (crawl job state), not user-facing. |
| Bundled Redis | "Prefer Dragonfly over Redis" (`.context/cache/dragonfly.md`) | Chart wiring assumes its own Redis; switching to a sidecar Dragonfly would require value overrides for both client config and cache eviction tuning. Low ROI given Firecrawl's cache is transient. |
| Bundled RabbitMQ | No precedent (repo has no RabbitMQ deployments) | No in-repo message-broker alternative; introducing one for a single consumer is over-engineering. RabbitMQ queue state is transient. |

Mitigation: if Firecrawl becomes load-bearing or its bundled deps cause issues, revisit and migrate (one component at a time) onto CNPG + Dragonfly. Tracked as future work, not blocking.

## Error handling & resilience

- Flux `install.remediation.retries: 3` and `upgrade.remediation.strategy: rollback` — standard repo pattern, mirrors n8n.
- Bundled StatefulSets (Postgres, Redis, RabbitMQ) get PVCs from the cluster default StorageClass (matches other apps' implicit behavior).
- If Playwright service OOMs or crashes, the queue worker will retry jobs from RabbitMQ — standard Firecrawl behavior, no extra wiring needed.
- No Velero backup for the bundled PVCs: crawl state is transient and reproducible. Documented as a non-goal.

## Testing & verification

After Flux reconciles:

1. **Pods healthy:** `kubectl -n firecrawl get pods` shows API, worker(s), Playwright, Redis, RabbitMQ, Postgres all Running.
2. **API responds:** `kubectl -n firecrawl port-forward svc/firecrawl-firecrawl-api 3002:3002` then `curl localhost:3002/v0/health` (or whatever the chart's health path is — verify during impl).
3. **Through HTTPRoute:** `curl https://firecrawl.endsys.cloud/v0/health` from a LAN host resolves and returns 200.
4. **End-to-end scrape:** `curl -X POST https://firecrawl.endsys.cloud/v1/scrape -H 'Content-Type: application/json' -d '{"url":"https://example.com"}'` returns scraped content.
5. **From n8n:** point an HTTP node at `http://firecrawl-firecrawl-api.firecrawl.svc.cluster.local:3002/v1/scrape` and confirm it works without crossing the gateway.

## Open Implementation Questions

Things to verify by inspecting the actual chart during implementation (the upstream README is incomplete):

1. **Exact chart value paths** — `image.api.repository`, `image.worker.*`, persistence/storage shape, exact toggle names for `extractWorker` / `nuqPrefetchWorker`. Pull the chart locally (`helm pull oci://registry-1.docker.io/winkkgmbh/firecrawl --version 0.2.0 --untar`) and read its `values.yaml` before committing the HelmRelease.
2. **Image tag** — figure out which Firecrawl image tag corresponds to chart 0.2.0. Likely documented in `Chart.yaml`'s `appVersion` or chart README; pin explicitly (no `latest`).
3. **Service name** — `firecrawl-firecrawl-api` is my best read from the README's port-forward example, but verify after first reconcile.
4. **Health probe path** — needed for verification steps; check the chart's probe defaults.

These don't change the design; they're details to nail down when writing the actual manifests.

## Rollout plan (high-level — full plan to come from writing-plans skill)

1. Add OCIRepository to `flux/meta/repos/`.
2. Pull chart locally, audit `values.yaml`, confirm value paths.
3. Write app manifests (namespace + ks.yaml + app/).
4. Add namespace kustomization to `apps/kustomization.yaml` (or wherever the cluster-apps Kustomization picks it up).
5. Commit, push, watch Flux reconcile. DNS for `firecrawl.endsys.cloud` is created automatically by external-dns from the HTTPRoute's hostname.
6. Run the verification checklist above.
7. Update `.context/debt.md` with the three known deviations.

---
task_id: hindsight-kubernetes-ollama-20260706
title: Add Hindsight Kubernetes manifests connected to local Ollama
actor: hermes/default/gpt-5.5
runtime: Hermes
repo: /home/sean/src/endsys-gitops
branch: main
plan: .hermes/plans/2026-07-06_130333-hindsight-kubernetes-ollama-plan.md
status: complete
side_effects:
  - repo-local files written under /home/sean/src/endsys-gitops
  - commit pushed to origin/main
  - Flux reconciled cluster-meta, cluster-apps, and hindsight app Kustomization
  - live Kubernetes resources created in namespace hindsight
commands_run:
  - command: kubectl kustomize kubernetes/flux/meta
    exit_code: 0
  - command: kubectl kustomize kubernetes/apps/hindsight
    exit_code: 0
  - command: kubectl kustomize kubernetes/apps/hindsight/hindsight/app
    exit_code: 0
  - command: kubectl kustomize kubernetes/apps
    exit_code: 0
  - command: kubectl apply --dry-run=server -f /tmp/endsys-meta.yaml
    exit_code: 0
  - command: kubectl apply --dry-run=client -f /tmp/endsys-hindsight-ns.yaml
    exit_code: 0
  - command: kubectl apply --dry-run=server -n default -f /tmp/endsys-hindsight-app.yaml
    exit_code: 0
  - command: kubectl apply --dry-run=client -f /tmp/endsys-apps.yaml
    exit_code: 0
---

# Hindsight Kubernetes + Ollama Ledger

## Scope

Sean approved working out the Hindsight deployment in the GitOps repo, then approved pushing/deploying and validating it. The app was deployed through Flux from `origin/main`.

## Implementation Notes

- Added Hindsight OCI chart source pinned to `0.8.4`.
- Added root `kubernetes/apps/kustomization.yaml` because local `kubectl kustomize kubernetes/apps` failed without it while Flux points `cluster-apps` at that path.
- Added `hindsight` namespace/app Flux structure.
- Added CNPG cluster `hindsight-postgres` using `ghcr.io/tensorchord/cloudnative-vectorchord:16.9-0.4.3` after server dry-run rejected `pgvector/pgvector:0.8.4-pg16` as an unsupported CNPG PostgreSQL image.
- Wired Hindsight HelmRelease to CNPG-generated `hindsight-postgres-app` secret via `valuesFrom`, avoiding committed database credentials and avoiding a new Bitwarden secret for the initial deployment.
- Configured Hindsight API for local Ollama at `http://10.127.0.4:11434/v1`, model `gemma4:e4b`, concurrency `1`, observations disabled.
- Added internal Gateway API HTTPRoutes for `hindsight.endsys.cloud` and `hindsight-api.endsys.cloud`.

## Verification Evidence

All local render checks passed after the CNPG image correction:

```text
kubectl kustomize kubernetes/flux/meta                 # exit 0
kubectl kustomize kubernetes/apps/hindsight            # exit 0
kubectl kustomize kubernetes/apps/hindsight/hindsight/app # exit 0
kubectl kustomize kubernetes/apps                      # exit 0
```

Server/client dry-runs:

```text
kubectl apply --dry-run=server -f /tmp/endsys-meta.yaml # exit 0
kubectl apply --dry-run=client -f /tmp/endsys-hindsight-ns.yaml # exit 0
kubectl apply --dry-run=server -n default -f /tmp/endsys-hindsight-app.yaml # exit 0
kubectl apply --dry-run=client -f /tmp/endsys-apps.yaml # exit 0
```

The namespace bundle needs Flux SOPS decryption in live reconciliation; direct server dry-run rejected encrypted common-component secrets, matching existing repo behavior.

## Runtime Validation Evidence

Live deployment from commit `399e694` reached healthy state:

```text
flux reconcile source git flux-system -n flux-system      # fetched 399e694
flux reconcile kustomization cluster-meta --with-source   # ready
flux reconcile kustomization cluster-apps --with-source   # ready
flux reconcile kustomization hindsight -n hindsight --with-source # ready
kubectl -n hindsight wait cluster/hindsight-postgres --for=condition=Ready # pass
kubectl -n hindsight wait pod -l app.kubernetes.io/instance=hindsight --for=condition=Ready # pass
kubectl -n hindsight wait helmrelease/hindsight --for=condition=Ready # pass
```

Final resource state:

```text
Kustomization hindsight: Ready=True
HelmRelease hindsight: Ready=True, chart hindsight@0.8.4
CNPG cluster hindsight-postgres: 1/1 Ready, healthy
Pods: hindsight-api, hindsight-control-plane, hindsight-postgres all 1/1 Running, 0 restarts
PVCs: hindsight-api-model-cache 5Gi Bound; hindsight-postgres-1 10Gi Bound
HTTPRoutes: hindsight and hindsight-api Accepted=True, ResolvedRefs=True
```

Database extension check:

```text
pg_trgm|1.6
vector|0.8.0
```

Ollama reachability from inside the `hindsight` namespace succeeded and returned `gemma4:e4b` from `http://10.127.0.4:11434/api/tags`.

API health checks:

```text
http://hindsight-api:8888/health -> {"status":"healthy","database":"connected"}
https://hindsight-api.endsys.cloud/health via internal gateway 10.127.0.51 -> {"status":"healthy","database":"connected"}
https://hindsight.endsys.cloud via internal gateway 10.127.0.51 -> HTTP/1.1 307 Temporary Redirect to /dashboard
```

DNS checks:

```text
dig @10.127.0.50 hindsight.endsys.cloud A -> 10.127.0.51
dig @10.127.0.50 hindsight-api.endsys.cloud A -> 10.127.0.51
dig @10.127.0.3 hindsight.endsys.cloud A -> internal.endsys.cloud / 10.127.0.51
dig @10.127.0.3 hindsight-api.endsys.cloud A -> internal.endsys.cloud / 10.127.0.51
```

Hindsight retain/recall smoke test through the Python client succeeded using bank `mimir-smoke`:

```text
retain success=True, items_count=1, usage total_tokens=2174
recall returned: The validation token hugin-1783359309 belongs to the Kubernetes deployment smoke...
```

One runtime warning was found and fixed in the manifests before finalizing: `HINDSIGHT_API_WORKER_ID` was unset. The HelmRelease now sets `HINDSIGHT_API_WORKER_ID: hindsight-api`.

## Remaining Gates

- Configure Hermes to use Hindsight only after loading the `hermes-agent` skill and choosing the integration mode.
- Consider switching from `gemma4:e4b` to a tool-calling Ollama model if Hindsight `reflect` is needed.

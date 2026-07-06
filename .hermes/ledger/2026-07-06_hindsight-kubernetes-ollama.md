---
task_id: hindsight-kubernetes-ollama-20260706
title: Add Hindsight Kubernetes manifests connected to local Ollama
actor: hermes/default/gpt-5.5
runtime: Hermes
repo: /home/sean/src/endsys-gitops
branch: main
plan: .hermes/plans/2026-07-06_130333-hindsight-kubernetes-ollama-plan.md
status: in_progress
side_effects:
  - repo-local files written under /home/sean/src/endsys-gitops
  - read-only Kubernetes queries and server dry-run validation only; no live apply/reconcile/push
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

Sean approved working out the Hindsight deployment in the GitOps repo. I created repo-local manifests only. I did not push, reconcile Flux, create live namespaces, create databases, restart services, or change DNS/firewall state.

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

## Remaining Gates

- Review the diff.
- Decide whether to commit locally.
- Decide whether to push to GitHub and let Flux reconcile. Pushing/deploying is a live infrastructure mutation and needs explicit approval.
- After live deployment, verify CNPG actually initializes pgvector/vector extension and Hindsight can retain/recall through Ollama.

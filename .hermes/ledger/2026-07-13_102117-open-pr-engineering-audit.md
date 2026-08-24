---
task_id: open-pr-engineering-audit-20260713
title: Audit and repair all open Renovate pull requests
actor: hermes/default/gpt-5.6-sol
runtime: Hermes
repo: /home/sean/workspace/endsys-gitops
branch: main
plan: .hermes/plans/2026-07-13_080219-open-pr-audit-plan.md
status: complete
side_effects:
  - read-only GitHub, repository, upstream-release, and live-cluster inspection
  - ahead-only push to PR 218 branch renovate/ghcr.io-siderolabs-kubelet-1.x
  - ahead-only push to PR 281 branch renovate/kube-prometheus-stack-87.x
  - user-approved local flux-local Docker test container; container removed on exit
  - no PR merged, closed, retitled, commented on, approved, or reviewed
  - no Flux reconciliation or Kubernetes/Talos mutation
---

# Open PR Engineering Audit

## Scope

Reviewed every open pull request in `shelmus/endsys-gitops`: diffs, ancestry, mergeability, CI, version semantics, duplicate runtime/bootstrap/template pins, upstream compatibility notes, dependencies, and relevant live state. Two independent read-only Claude Code Opus passes were used as review input; their findings were checked against direct `gh`, `git`, `kubectl`, Talos documentation, Helm values, and upstream releases before acceptance.

## Critical Live-State Correction

The repository currently pins Talos `v1.12.6` and Kubernetes `v1.35.3`, but the live nodes have not received those manual upgrades:

```text
kube1  Kubernetes v1.34.0  Talos v1.11.0
kube2  Kubernetes v1.34.0  Talos v1.11.3
kube3  Kubernetes v1.34.0  Talos v1.11.3
```

Therefore the current repository target must be rolled out before any Talos 1.13 / Kubernetes 1.36 rollout. Talos documents that configuration migrations are tested only across adjacent minor versions and recommends installing the latest patch of every intermediate Talos minor. Kubernetes must likewise move one minor at a time.

The safe runtime progression is:

1. Bring all nodes to the latest applicable Talos 1.11 patch.
2. Roll Talos 1.12.6, one node at a time.
3. Upgrade Kubernetes 1.34.0 to 1.35.3.
4. Only after that, roll Talos 1.13.6.
5. Upgrade Kubernetes 1.35.3 to 1.36.2.

These are shared-infrastructure mutations and remain explicit red-gate work; this audit did not execute them.

## Repairs Pushed

### PR #218 — coherent Talos 1.13 / Kubernetes 1.36 target

Remote branch now points to `5bbaf64d6a646549bbc5e41eb40eb6aefd49e390`.

The branch was brought forward to current `main` and repaired so it no longer creates an unsupported Talos/Kubernetes pair:

```text
Talos installer:    v1.12.6 -> v1.13.6
Kubernetes/kubelet: v1.35.3 -> v1.36.2
kubectl:            1.35.3  -> 1.36.2
```

Changed files:

- `.mise.toml`
- `talos/talenv.yaml`
- `templates/config/talos/talenv.yaml.j2`

Talos 1.12 supports Kubernetes only through 1.35; Talos 1.13 is required for Kubernetes 1.36. Upstream release objects and installer/kubelet image manifests for the selected versions were verified. Static version, YAML, whitespace, ancestry, and conflict-marker checks passed. GitHub CI is green; the Flux jobs correctly skipped because this PR does not touch `kubernetes/**`.

Operational verdict: **code repaired; HOLD rollout until the existing 1.11/1.34 -> 1.12/1.35 backlog is completed**.

PR #225 is now redundant with the coherent target in #218 and is a **SUPERSEDED/CLOSE** candidate. Its branch was not pushed.

### PR #281 — make the Prometheus CRD upgrade real

Remote branch now points to `f58603a8fc4a3f68440718c8ab2d30509f6bed8d`.

The repository's live Prometheus Operator CRDs are still annotated `0.84.1`, while the running operator is newer and PR #281 moves the chart to operator `0.92.1`. PR #276 only changes `scripts/bootstrap-apps.sh`; merging that script does not update an existing cluster by itself.

The branch now enables the chart's explicit CRD upgrade hook:

```yaml
crds:
  upgradeJob:
    enabled: true
```

This makes #281 self-contained for the live CRD transition while #276 preserves bootstrap parity for future/rebuilt clusters.

Local verification against the repaired branch:

```text
flux-local v8.0.1 test --enable-helm --all-namespaces
75 passed, 75 warnings, 18.14s
```

The warnings are existing renderer warnings; no test failed. YAML/value assertions, `git diff --check`, ancestry, and conflict-marker checks also passed. Fresh GitHub CI then passed the Flux Local Test, both Flux Local Diff jobs, Flux Local Success, pre-job, and Labeler checks.

## PR Verdict Matrix

Legend:

- **READY**: diff and CI are clean; no blocking compatibility issue found.
- **READY + GATE**: code is acceptable, but perform the named rollout check immediately before reconcile.
- **HOLD**: do not merge/reconcile until the named prerequisite is satisfied.
- **UPDATED**: branch repair was pushed and verified locally.
- **SUPERSEDED/CLOSE**: another PR now contains the appropriate target.

| PR | Change | Verdict | Dependency or rollout note |
|---:|---|---|---|
| 218 | Talos/Kubernetes target, repaired to 1.13.6/1.36.2 | **UPDATED; HOLD rollout** | First roll live 1.11/1.34 through repo target 1.12.6/1.35.3. Retitle needed. |
| 225 | Talos 1.12.6 -> 1.13.0, abandoned | **SUPERSEDED/CLOSE** | Repaired #218 now contains Talos 1.13.6. |
| 227 | kube-prometheus-stack 82.x -> 84.x, abandoned | **SUPERSEDED/CLOSE** | Superseded by repaired #281 at 87.15.1. |
| 253 | MySQL 8.2 -> 8.4 LTS | **HOLD** | Take and restore-test a fresh logical dump. Existing Velero hook does not hold the lock across the backup. |
| 254 | app-template 5.0.0 -> 5.0.1 | **READY** | Wide template fan-out, but patch release and Flux CI render is green. |
| 255 | Reloader 2.2.11 -> 2.2.14 | **READY** | Patch. |
| 256 | flux-operator/instance 0.48.0 -> 0.54.1 | **READY + GATE** | Merge/reconcile in one window with #283. |
| 258 | Home Assistant chart 0.3.61 -> 0.3.70; app 2026.5.4 -> 2026.7.2 | **HOLD** | Persistent SQLite/config volume has no current Velero schedule; take a fresh Home Assistant backup first. |
| 259 | Pocket ID chart 2.1.1 -> 2.2.0 | **READY** | Fresh daily Velero backup exists; verify login after rollout. |
| 260 | Velero chart 12.0.1 -> 12.1.0 | **READY + GATE** | Pair with #280; verify a scheduled backup completes afterward. |
| 261 | CoreDNS chart 1.45.2 -> 1.46.0 | **READY** | Bootstrap, runtime, and template pins agree. |
| 262 | Coder 2.33.5 -> 2.35.1 | **HOLD** | Confirm Pocket ID emits `email_verified: true`; take a fresh Coder database backup before migrations. Do not weaken validation by default. |
| 263 | Longhorn 1.11.2 -> 1.12.0 | **HOLD** | All 19 volumes are V1, no backing images exist, and CPU is ample, but Longhorn has no configured backup target. Land #270 first and establish recoverability. |
| 264 | External Secrets chart 2.5.0 -> 2.7.0 | **READY** | Repo uses v1 APIs; merge before/with #278. |
| 265 | CloudNativePG chart 0.28.2 -> 0.29.0 | **READY** | Operator/CRD update; existing dependency ordering is suitable. |
| 266 | metrics-server 3.13.0 -> 3.13.1 | **READY** | Patch. |
| 267 | cloudflared 2026.5.2 -> 2026.7.1 | **READY** | No removed configuration found. |
| 268 | Dragonfly 1.38.0 -> 1.39.0 | **READY** | Cache workload; no persistence migration. |
| 269 | Matrix stack 26.5.1 -> 26.7.0 | **READY + GATE** | Fresh daily Velero backup exists; refresh it immediately before one-way DB migrations and verify login/federation. |
| 270 | snapshot-controller 5.0.4 -> 5.1.1 | **READY** | Land before #263. |
| 271 | http-https-echo 40 -> 41 | **READY** | Major image number but stateless and configuration-compatible. |
| 272 | RabbitMQ 4.3.1 -> 4.3.2 | **READY** | Patch; transient queue workload. |
| 273 | Spegel 0.7.1 -> 0.7.3 | **READY** | Bootstrap, runtime, and template pins agree. |
| 274 | Cilium 1.19.4 -> 1.19.5 | **READY** | Patch; bootstrap, runtime, and template pins agree. |
| 275 | CSI NFS 4.13.2 -> 4.13.4 | **READY** | Patch. |
| 276 | Prometheus Operator bootstrap CRDs 0.91.0 -> 0.92.1 | **READY** | Updates bootstrap parity only; it does not mutate current live CRDs. Land before/with repaired #281. |
| 277 | actions/checkout 6.0.3 -> 7.0.0 | **READY** | Node 24 runner requirement is satisfied by GitHub-hosted runners. |
| 278 | Bitwarden SDK server 0.6.0 -> 0.7.0 | **READY** | Merge after/with #264; verify ExternalSecret refresh. |
| 279 | cert-manager 1.20.2 -> 1.21.0 | **READY** | Removed ServiceMonitor path/targetPort values are not configured in this repo. |
| 280 | Velero AWS plugin 1.14.1 -> 1.14.2 | **READY + GATE** | Pair with #260; verify object-store backup and restore visibility. |
| 281 | kube-prometheus-stack 82.18.0 -> 87.15.1 | **UPDATED** | CRD upgrade job added; land #276 for bootstrap parity. Fresh local and GitHub Flux tests passed. |
| 282 | Immich chart 0.12.0 -> 0.13.1 | **READY + GATE** | Application image remains explicitly pinned at v2.5.2; verify render and Immich health after chart rollout. |
| 283 | Flux distribution 2.8.8 -> 2.9.1 | **READY + GATE** | Pair with #256. Repo has no removed v1beta2 APIs or affected Helm post-renderers. |
| 284 | Gateway API experimental CRDs 1.5.1 -> 1.6.0 | **READY** | Repo uses HTTPRoute v1 only; no removed TLSRoute/ListenerSet/v1alpha2 objects. Bootstrap script only. |
| 285 | Otterwiki 2.20 -> 2.21 | **READY** | No persistent volume is enabled in the current manifest. |
| 286 | k8s-gateway 3.7.1 -> 3.7.2 | **READY** | Patch. |

## Verification Evidence

### GitHub and Git

- All open PR heads were fetched and diffed against their merge bases.
- Every PR reported `MERGEABLE` and `CLEAN` with no failed GitHub checks at audit time, before the two repaired branches triggered fresh CI.
- `git merge-tree --write-tree origin/main origin/pr/<n>` succeeded for every audited PR.
- No branch diff contained unresolved Git conflict markers or `git diff --check` failures.
- Remote readback confirmed #218 at `5bbaf64d...` and #281 at `f58603a8...` after ahead-only pushes.

### Live cluster

- Nodes: Kubernetes 1.34.0, Talos 1.11.0/1.11.3.
- Prometheus CRDs: annotations report 0.84.1.
- Longhorn: 19 V1 volumes, zero backing images, no configured backup target; node CPU usage 0–1% and memory usage 31–34% during inspection.
- Velero: current successful daily backups exist for PriceBuddy, Matrix, Immich, Pocket ID, n8n, Gatus, Obsidian LiveSync, and Pelican.
- No current Home Assistant or Coder backup schedule exists.

### Local #281 Flux render

The first direct worktree attempt failed before rendering because its `.git` file referred to the host worktree metadata outside the container mount. A regular scratch clone fixed that. The second attempt failed before rendering due Git safe-directory ownership; the user approved a scoped safe-directory environment, and scratch permissions were adjusted. The final real test rendered the full cluster and returned:

```text
75 passed, 75 warnings in 18.14s
```

These setup failures were not manifest failures.

## Recommended Merge/Deployment Waves

No merge or deployment was performed. Each merge and each shared-infrastructure rollout remains a red gate.

1. **Independent low-risk:** #277, #284, #254, #255, #266, #267, #271, #272, #285, #286, #261, #273, #274, #275, #265.
2. **External Secrets pair:** #264, then #278; verify ExternalSecret refreshes.
3. **Velero pair:** #260 and #280 in one window; verify a new backup and object-store visibility.
4. **Flux pair:** #256 and #283 in one window; verify Flux controllers and all Kustomizations.
5. **Storage:** #270, then #263 only after Longhorn recoverability is established.
6. **Monitoring:** #276, then repaired #281; watch CRD upgrade job, operator, Prometheus, Alertmanager, and Grafana.
7. **Other apps:** #259, #268, #269, #282, with the named rollout checks.
8. **Stateful/auth holds:** #253, #258, #262 only after their explicit gates.
9. **Talos/Kubernetes last:** reconcile the existing 1.11/1.34 -> 1.12.6/1.35.3 drift, then consider repaired #218 and perform adjacent-minor manual upgrades.
10. **Close after approval:** #225 and #227.

## Remaining Red Gates

The following operations were deliberately not performed:

- Retitle #218 to reflect the combined Talos 1.13.6 / Kubernetes 1.36.2 target.
- Close superseded PRs #225 and #227.
- Merge any pull request.
- Create or test application-consistent backups for MySQL, Home Assistant, Coder, or Longhorn.
- Reconcile Flux or roll Talos/Kubernetes.

## Sources

- Talos 1.13 support matrix: <https://docs.siderolabs.com/talos/v1.13/getting-started/support-matrix>
- Talos upgrade path: <https://docs.siderolabs.com/talos/v1.13/configure-your-talos-cluster/lifecycle-management/upgrading-talos>
- Coder 2.35.1: <https://github.com/coder/coder/releases/tag/v2.35.1>
- Longhorn 1.12 notes: <https://longhorn.io/docs/1.12.0/important-notes/>
- Flux 2.9: <https://fluxcd.io/blog/2026/06/flux-v2.9.0/>
- cert-manager 1.21: <https://github.com/cert-manager/cert-manager/releases/tag/v1.21.0>
- Gateway API 1.6: <https://github.com/kubernetes-sigs/gateway-api/releases/tag/v1.6.0>
- Velero AWS plugin compatibility: <https://github.com/vmware-tanzu/velero-plugin-for-aws>

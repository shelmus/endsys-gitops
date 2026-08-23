# Dependency PR Rollout Verification — 2026-08-23

## Scope

Close the evidence gap for the eleven PRs Sean approved for staged merge on 2026-08-19:

- Repository-only: #291, #301
- Application/infrastructure updates: #299, #260, #280, #290, #304, #310, #305, #295, #288

This ledger records verification only. No cluster mutation, rollback, or new PR merge was performed while writing it.

## Merge record

| PR | Merge time (UTC) | Merge commit | Result |
|---|---:|---|---|
| #291 | 2026-08-20 00:08:23 | `e64d5aa76350` | Merged |
| #301 | 2026-08-20 00:09:37 | `41dbfddcbf07` | Merged |
| #299 | 2026-08-20 01:00:27 | `c6bb04d6412f` | Merged |
| #260 | 2026-08-20 01:03:00 | `4b48625183e9` | Merged |
| #280 | 2026-08-20 01:05:25 | `fae21c4d2010` | Merged |
| #290 | 2026-08-20 01:08:49 | `d3073e798565` | Merged |
| #304 | 2026-08-20 01:19:01 | `50cf9ce6478c` | Merged |
| #310 | 2026-08-20 01:29:47 | `8ae136ede48d` | Merged |
| #305 | 2026-08-20 01:32:12 | `ac03329947fc` | Merged |
| #295 | 2026-08-20 23:33:53 | `341f2944179a` | Merged |
| #288 | 2026-08-20 23:34:01 | `6f6bb1dc2d76` | Merged |

GitHub reports every scoped PR as `MERGED`. The two last merges landed together with other PRs outside this approved set; those other changes are not retrospectively attributed to this rollout.

## Current convergence evidence

Captured at `2026-08-23T00:04:57Z`:

- GitHub `main`: `dfb7ba81c254194962d5f16c2af5d0da4e68d1fa`
- Flux source artifact: `refs/heads/main@sha1:dfb7ba81c254194962d5f16c2af5d0da4e68d1fa`
- Flux Kustomizations: 45/45 Ready
- Flux HelmReleases: 36/36 Ready
- Nodes: 3/3 Ready
- ExternalSecrets: 13/13 Ready
- Certificates: 3/3 Ready
- Longhorn volumes: 23 healthy; one `unknown` volume is an unbound `20Gi` provisioning object with no PVC, node, or engine assignment—not a degraded attached volume

The live cluster therefore converged to the current `main`. Current health includes later merges and is end-to-end evidence, not proof that each individual merge caused no transient issue.

## Scoped verification

### Repository-only PRs

- **#291 Gateway API release reference:** merged into `main`; it changes bootstrap/repository input and does not mutate an already-running cluster by itself.
- **#301 action-labeler:** merged into `main`; GitHub Actions-only change, with no cluster runtime object.

### Runtime updates

- **#299 OtterWiki image:** the changed manifest now carries image `2.23`, but `kubernetes/apps/default/kustomization.yaml` has `./otterwiki/ks.yaml` commented out. There is no live OtterWiki Kustomization, HelmRelease, pod, service, or route. This PR was inert for the live cluster and cannot honestly receive an application smoke-test verdict.
- **#260 Velero chart / #280 AWS plugin:** HelmRelease Ready at chart `12.0.0`, application `1.16.2`; server and node-agent pods are Ready. The AWS plugin completed current backup activity in server logs. The read-only service account cannot list Velero Backup or BackupStorageLocation objects, so object-level success and restoreability were not independently proved here.
- **#290 Spegel:** HelmRelease Ready at chart `0.7.0`, application `0.7.0`; daemon pods are Ready on all three nodes.
- **#304 cert-manager:** HelmRelease Ready at chart/application `v1.18.3`; all three live Certificates report Ready.
- **#310 Reloader:** HelmRelease Ready at chart `2.2.3`, application `v1.4.14`; deployment pod Ready.
- **#305 Pocket-ID chart metadata:** HelmRelease Ready at chart `0.3.0`; workload remains on the explicitly pinned `ghcr.io/pocket-id/pocket-id:v2.4.0`. OIDC discovery returns HTTP 200 at `https://auth.endsys.cloud/.well-known/openid-configuration`.
- **#295 External Secrets:** HelmRelease Ready at chart `2.0.0`, application `v2.0.0`; 13/13 ExternalSecrets and the ClusterSecretStore report Ready.
- **#288 cloudflared:** tunnel deployment is Ready on `docker.io/cloudflare/cloudflared:2026.8.2`, zero restarts, with no warning/error lines in the sampled 24-hour log window.

## Functional smokes at current `main`

| Endpoint | Result |
|---|---:|
| Pocket-ID OIDC discovery | HTTP 200 |
| Element Web | HTTP 200 |
| Matrix federation version | HTTP 200 |
| n8n `/healthz` | HTTP 200 |
| Home Assistant root | HTTP 200 |
| ROMM heartbeat | HTTP 200 |
| Pricebuddy root | HTTP 302 (expected redirect) |
| Grafana health | HTTP 200 |

These are broad current-cluster checks because later merges advanced `main` beyond the eleven scoped PRs.

## Backup evidence and limits

Velero server logs show scheduled backup activity on 2026-08-22 for Home Assistant, Matrix, n8n, Pricebuddy, and ROMM, including uploader completion and `Initial backup processing complete, moving to Finalizing`. Repository-maintenance jobs also completed. The read-only identity lacks access to Velero Backup, Schedule, PodVolumeBackup, and BackupStorageLocation resources, so this ledger does **not** claim restoreability or authoritative final Backup phases.

Node-agent warning lines sampled at 02:06 UTC referenced already-expired July backup objects and missing PodVolumeBackup records during cleanup; they were not current workload-readiness failures.

## Corrections and caveats

1. A changed manifest is not necessarily reachable from an active Kustomization. #299 is the concrete example; future audits must explicitly test manifest reachability before classifying a PR as a live rollout.
2. The cluster currently contains changes from PRs merged after the approved set. Current health cannot be used to approve or excuse those unrelated merges.
3. No rollback was required for the approved set based on the evidence available to this read-only identity.

## Open dependency PR audit refresh

Captured at `2026-08-23T00:40:15Z` against `origin/main` `dfb7ba81c254194962d5f16c2af5d0da4e68d1fa`.

All sixteen listed PRs were still open. GitHub reported no incomplete or failing checks at capture. PR #218 was `DIRTY`/conflicting; the other fifteen were `CLEAN` and mergeable. A clean merge state is only mechanical evidence, not an operational approval.

| PR | Audited head | Verdict | Reason and gate |
|---|---|---|---|
| #218 | `5bbaf64d6a64` | REPLACE / CLOSE | Conflicting, stale combined Talos `1.13.6` and Kubernetes `1.36.2` work. It overlaps newer Talos inputs and should be replaced by a fresh, coordinated control-plane plan rather than repaired in place. |
| #253 | `601702ed3873` | HOLD | This is the valid first MySQL step, `8.2` to `8.4 LTS`, but Pricebuddy needs a tested logical dump/restore path. Its current Velero pre-hook releases `FLUSH TABLES WITH READ LOCK` after roughly five seconds rather than holding it across the filesystem copy. |
| #256 | `4e0f7d7b46dc` | HOLD | Flux Operator and Flux Instance must be upgraded as one self-hosting transaction with #283's bootstrap distribution pin, export/dry-run evidence, and rollback material. |
| #263 | `c665a15e521e` | HOLD | Longhorn `1.11.2` to `1.12.1` is a storage-plane maintenance change. Live volumes are V1 and no linked clones were found, but backups, node-by-node health checks, replica rebuild checks, and a maintenance window remain mandatory. |
| #276 | `3dc57699c5dc` | REPLACE / CLOSE | Its Prometheus Operator CRD pin is now incorporated into repaired #307. Merging it separately would restore a torn chart/CRD rollout. |
| #283 | `45ea123cf36b` | HOLD | Flux distribution `2.8.8` to `2.9.4` is coupled to #256 and needs a single controlled self-hosting rollout. |
| #292 | `408193d1a94d` | HOLD | Cilium `1.19.5` to `1.20.1` is a CNI dataplane change. It requires an upstream compatibility review, rendered diff, node-by-node rollout, connectivity/DNS/Gateway smokes, and a maintenance window. |
| #293 | `b36e698622ec` | HOLD | Talos installer `1.12.6` to `1.13.9` is a node OS rollout input, not a normal image bump. It needs etcd/control-plane backup evidence, a supported Kubernetes/Talos sequence, one-node-at-a-time rollout, and explicit infrastructure approval. |
| #294 | `585067c0cdcb` | HOLD | ROMM `4.9.2` to `5.2.0` crosses a major application migration. Require a current CNPG backup plus ROMM state backup, migration review, library scan/login/game launch smokes, and a demonstrated rollback boundary. |
| #306 | `9f17f628ac04` | REPLACE / CLOSE | MySQL `8.2` to `26.7` is not a supported direct jump. The required train starts with #253 (`8.2` to `8.4 LTS`), followed by later LTS steps and restore tests. |
| #307 | `a8fe552cf615` | READY WITH ROLLOUT GATE | Repaired and current-head CI green. The chart `82.18.0` to `88.5.3` update is now coupled to v0.93.1 CRDs and an explicit CRD upgrade hook. This remains a monitoring/control-plane maintenance rollout. |
| #313 | `ce04f7ec74d5` | READY WITH ROLLOUT GATE | Matrix stack `26.8.0` to `26.8.1`; the removed `keysYaml` value is not used here. Require a fresh completed backup plus login, room/message, federation, and RTC checks. |
| #314 | `811faf9f680a` | READY WITH ROLLOUT GATE | Repaired and current-head CI green. Chart `2.0.1` to `2.1.0` is decoupled from n8n 2.x; runtime is pinned to `n8nio/n8n:1.123.75`. Require a fresh completed n8n backup and workflow/webhook smoke tests. |
| #315 | `230f3a9a91a1` | READY | Bootstrap-only ExternalDNS CRD pin `v0.21.0` to `v0.22.0`. The CRD delta audited here was generator metadata only, and this source change does not mutate the running cluster by itself. Recheck the exact head and CI immediately before merge. |
| #316 | `43b08e8f8c18` | READY | metrics-server chart `3.13.1` to `3.14.0`, application `0.8.0` to `0.9.0`. Upstream documents Kubernetes `1.34` as the minimum; live client and server are both `v1.34.0`. Stage alone and verify APIService availability plus `kubectl top` after Flux converges. |
| #317 | `9f4bacc749c7` | READY WITH ROLLOUT GATE | Home Assistant chart `0.3.74` to `0.3.75`, application `2026.8.1` to `2026.8.3`. Require a fresh completed backup plus login, representative automation, and critical integration checks. |

### Dependency graph

- **#307 absorbs #276.** Merge #307 only; close #276 after explicit approval.
- **#256 and #283** form one Flux self-hosting transaction.
- **#253 precedes any later MySQL LTS step.** Do not merge #306.
- **#218 and #293** must be replaced by one fresh Talos/Kubernetes rollout plan; do not treat either as an ordinary image merge.
- **#313, #314, #317, #294, and #253** share the same unresolved backup-status limitation: the gateway read-only identity cannot list authoritative Velero Backup phases or prove restoreability.

## Repairs pushed to existing PR branches

No pull request was merged, closed, or created. Two Sean-owned feature branches were advanced by fast-forward push after local verification.

### PR #314 — decouple n8n chart and application majors

Current head: `811faf9f680ad011ba8423925806943a48bad82b`.

Changes:

- merged current `main` into the PR branch;
- retained OCI chart `2.1.0`;
- pinned runtime to `n8nio/n8n:1.123.75`;
- added Renovate metadata plus an `<2.0.0` package rule so automation does not silently reintroduce n8n 2.x.

Verification:

- YAML parsed and `git diff --check` passed;
- Renovate `44.39.2` accepted `.renovaterc.json5`;
- Helm `4.2.3` rendered the workload as `n8nio/n8n:1.123.75` with no n8n 2.x image;
- the image manifest exposes linux/amd64 and linux/arm64;
- current-head GitHub checks all passed: Flux Local Pre-Job, Test, HelmRelease diff, Kustomization diff, Success, and Labeler;
- GitHub reports `MERGEABLE` / `CLEAN`.

### PR #307 — couple Prometheus chart and CRDs

Current head: `a8fe552cf615b362bac1a455b2b182be9d30363a`.

Changes:

- merged current `main` into the PR branch;
- enabled the chart's `crds.upgradeJob` with server-side apply and `forceConflicts`;
- advanced the bootstrap Prometheus Operator CRD bundle from `v0.91.0` to `v0.93.1`, absorbing #276;
- pinned hook images to `docker.io/busybox:1.37.0` and `registry.k8s.io/kubectl:v1.34.0`, with Renovate annotations.

Verification:

- YAML parsed, `bash -n scripts/bootstrap-apps.sh` passed, and `git diff --check` passed;
- Helm `4.2.3` rendered a `pre-install,pre-upgrade,pre-rollback` CRD Job with `--server-side --force-conflicts` and the two pinned hook images;
- the target chart renders Prometheus Operator `v0.93.1`, Prometheus `v3.14.0-distroless`, Alertmanager `v0.34.0`, Grafana `13.2.0`, node-exporter `v1.12.1-distroless`, and kube-state-metrics `v2.20.0`;
- the chart's full CRD schemas match the official Prometheus Operator `v0.93.1` stripped-down schemas after removing descriptions;
- all ten target CRDs retain the live storage API versions; no stored-version conversion is introduced;
- live CRDs are materially stale: all ten carry `controller-gen.kubebuilder.io/version: v0.18.0`, and their live schemas did not match upstream `v0.89.0`, `v0.91.0`, or `v0.93.1`; this confirms that enabling the upgrade job is necessary rather than cosmetic;
- `busybox:1.37.0` is active for linux/amd64 and linux/arm64, `kubectl:v1.34.0` exists, and live Kubernetes is `v1.34.0`;
- current-head GitHub checks all passed: Flux Local Pre-Job, Test, HelmRelease diff, Kustomization diff, Success, and Labeler;
- GitHub reports `MERGEABLE` / `CLEAN`.

## Upstream evidence consulted

- Prometheus chart upgrade guide for `88.x`, including the explicit CRD-before-operator requirement and supported `crds.upgradeJob.enabled` path: <https://raw.githubusercontent.com/prometheus-community/helm-charts/kube-prometheus-stack-88.5.3/charts/kube-prometheus-stack/UPGRADE.md>
- n8n Helm chart `2.1.0` release note, which explicitly says an unpinned upgrade moves to n8n `2.35.7` and recommends `image.tag: "1.123.75"` to remain on 1.x: <https://github.com/8gears/n8n-helm-chart/releases/tag/2.1.0>
- metrics-server `v0.9.0` compatibility matrix, which lists Kubernetes `1.34+`: <https://raw.githubusercontent.com/kubernetes-sigs/metrics-server/v0.9.0/README.md>
- Oracle's MySQL `26.7` upgrade-path table, which requires stepping through successive LTS series rather than skipping them: <https://dev.mysql.com/doc/refman/26.7/en/upgrade-paths.html>

## Remaining red gates

None of the following was performed:

1. merge any PR into `main`;
2. close superseded PRs #218, #276, or #306;
3. create a pull request for this ledger branch;
4. reconcile Flux, alter Kubernetes/Talos/Longhorn/Cilium state, or restart workloads;
5. use a more privileged identity to inspect Velero Backup phases or perform restore tests.

Each requires explicit approval under the homelab trust boundary. Exact commands and post-merge checks must be refreshed from the then-current PR heads immediately before any rollout.

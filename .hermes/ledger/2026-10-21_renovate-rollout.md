# Renovate rollout: 2026-10-21

Audit of 41 open PRs against `main` @ `bad6889`; rollout 09:25–09:58 EDT. Final `main` is `9711bfe`.
Full review, sources and evidence: vault `Plan/2026-10-21_092021-endsys-gitops-open-pr-review.md`.

**Method:**
- Each merge used `merge_pr_guarded.py`: `gh pr merge --merge --match-head-commit <reviewed-oid>`.
- After each step, `flux_verify.py` waited for natural Flux convergence. No manual reconcile was run.
- Aggregate preflight: 30 heads composed onto `bad6889` with 0 conflicts. 39 files changed, 30 YAML files parsed, and `diff --check` was clean.
- Helm 4.3.0 renders, base vs merge result, for:
  - every app-template consumer (no selector, image or pod-template change);
  - kube-prometheus-stack 92 (Grafana 14 schema accepts the values, CRDs identical);
  - immich and n8n (version pins hold);
  - forgejo, coredns, ESO and the external-dns flags (all 18 present in v0.23.0).

## Branch repairs (ahead-only)

- **#424** `81f60a7`: drop `service.registry.hostPort` and `grafanaDashboard`, both removed in spegel 0.8.0. The mirror now uses NodePort 30020.
- **#294** `78f0a04`: romm `filesystem.structure` (required since 5.3), 30-min startup probe, `timeout: 40m`, and no upgrade remediation (5.4 migrations; no downgrade). **Not merged; waiting on a backup.**
- **#374** `5203165`: backup status table now lists forgejo and netbird.

## Merged

| Wave | PRs | Converged at |
|---|---|---|
| 1 | #409 #392 #410 #420 #411 #374 | 09:27 |
| 2 | #379 #413 #407 #408 #376 #380 #414 #423 → #426 → #425 | 09:31 |
| 3a | #418 → #427 → #385 | 09:35 |
| 3b | #422 | 09:37 |
| 3c | #424 | 09:39 |
| 3d | #383 → #381 | 09:42 |
| 4a | #382 → #415 → #386 | 09:48 |
| 4b | #389 | 09:50 |
| 4c | #417 #388 #384 | 09:55 |

Per-wave live checks are in the vault note: images, DNS answers, ExternalSecret refresh, WAL archiving, Prometheus targets and rules, and Discord delivery.

## Closed

- #390: superseded by #417.
- #319: superseded by #428.

## Open

- **Waiting on a database backup:** #428 hindsight, #412 coder, #377 matrix, #294 romm, #253 mysql. Plan: vault `Plan/2026-10-21_100500-endsys-database-backup-plan.md`.
- **Held:**
  - #387 Kubernetes 1.37: Cilium, Flux and Longhorn don't publish support for it yet.
  - #378 Talos 1.14.4: merge together with the manual node upgrade.
  - #416 docker 29: re-check the rebased head, then canary it.

## Notes

- The spegel pods logged a one-off libp2p "bootstrap completed but connectivity has not been reached" at simultaneous restart. It is benign: none since, and the mirror serves hits.
- `mimir-readonly` cannot use the service proxy or read `snapshot.storage.k8s.io`. Read Prometheus through `prometheus.endsys.cloud`.
- The monitoring restart wiped metric history again (emptyDir).

# Renovate rollout: 2026-09-28

The PR audit started 2026-09-27 against `main` @ `b34dac0`. The rollout ran 2026-09-28 from 05:20 to 05:40 EDT. Final `main` is `0909363`.

**Method:**
- Each PR was merged with `gh pr merge --merge --match-head-commit <reviewed-oid>`, which matches the repo's merge-commit convention.
- Each wave waited for Flux to reconcile naturally; no manual reconcile was run.
- The guards and verifiers are in the `gitops-pr-audit-workflows` skill scripts. `flux_verify` passed only when all of these held:
  - the source revision is the new `main` SHA;
  - every Kustomization is Ready at that SHA;
  - every HelmRelease is Ready;
  - the target chart versions are in HelmRelease history;
  - every non-completed pod is Ready.
- Aggregate preflight: all 15 approved heads, composed in merge order onto `b34dac0`, merged cleanly. That touched 23 files; all 15 of the changed, non-SOPS YAML files parsed, and `git diff --check` was clean.

## Merged

| Wave | PR | Change | Merge commit | Converged |
|---|---|---|---|---|
| 1 | #325 | gateway-api bootstrap URL v1.6.1 → v1.6.2 | `b508d65` | |
| 1 | #321 | otterwiki 2.23 → 2.24 (dormant app) | `fa0911f` | about 60 s |
| 2a | #360 | pocket-id chart 2.2.1 → 2.2.2 | `2f6496d` | |
| 2a | #329 | immich chart 0.13.1 → 0.13.2 | `435f6fe` | |
| 2a | #337 | rabbitmq 4.3.5 → 4.3.6 (firecrawl) | `b3aff7f` | |
| 2a | #324 | dragonfly v1.40.1 → v1.40.2 (immich, romm) | `14b0c38` | |
| 2a | #344 | http-https-echo 41 → 42 | `0f92688` | 05:25:06 |
| 2b | #341 | snapshot-controller 5.2.0 → 5.3.0 | `cf97625` | |
| 2b | #330 | reloader 2.2.16 → 2.2.17 | `bdf80c7` | |
| 2b | #316 | metrics-server 3.13.1 → 3.14.0 | `718ae96` | |
| 2b | #328 | coredns chart 1.47.0 → 1.47.1 | `27d29dd` | 05:27:09 |
| 2c | #323 | cloudflared 2026.8.2 → 2026.9.3 | `98672aa` | |
| 2c | #358 | velero-plugin-for-aws v1.14.2 → **v1.14.4** | `7c919b7` | |
| 2c | #342 | velero chart 12.1.0 → 12.2.0 | `a533a4d` | 05:30:14 |
| 3 | #338 | app-template 5.1.0 → 5.2.1 (7 HelmReleases) | `0909363` | 05:31:17 |

### Evidence per wave

- **2a:**
  - Both Dragonfly HelmReleases briefly showed an upgrade in progress, then became Ready within about 30 s.
  - The echo pod showed as Pending during its rollout.
  - Every pod is now running its new image.
  - `echo` returns HTTPS 200, and pocket-id OIDC discovery returns 200.
- **2b:**
  - `kubectl top nodes` works, so metrics-server is serving.
  - CoreDNS is 2/2, and `snapshot-controller` is 2/2.
  - Pi-hole still resolves `immich.endsys.cloud`.
- **2c:**
  - The Velero deployment now runs velero v1.18.2 with plugin v1.14.4, and its controllers started cleanly.
  - cloudflared 2026.9.3 is 1/1, and external immich returns 200.
- **3:**
  - All 7 app-template HelmReleases are at chart 5.2.1 and Ready.
  - An HTTPS probe hit all 28 live HTTPRoute hostnames, taken from `kubectl get httproutes`:
    - 200/302/307 for the apps.
    - 401 for obsidian-livesync, which is its auth gate.
    - 404 at the root for flux-webhook, hindsight-api, matrix and bare `endsys.cloud`. Those routes are path-restricted, so a root 404 is expected.
    - 503 for `octopi` (external-services). No merged PR touched it, and I have no baseline for it.

### Head changed mid-wave

The #358 head moved from `678276d` (v1.14.3) to `373c2ee` (v1.14.4) during wave 2c, and the merge guard refused it.

I re-reviewed the new head:
- The upstream compare from v1.14.3 to v1.14.4 has 2 commits, touching only `go.mod` and `go.sum` (dependency and CVE bumps).
- The plugin release notes say "Fix CVEs for 1.14.4".
- All six Flux Local checks passed on the new head.

It was then merged pinned to `373c2ee`.

## Closed

- **#307:** kube-prometheus-stack 88.x, abandoned by Renovate. Superseded by #334.
- **#276:** prometheus-operator bootstrap CRD URL. Folded into the #334 repair.
- **#306:** mysql 8.2 → 26.7, an unsupported jump. #253 (8.4 LTS) stays on hold.

## Repaired, not merged

- **#332 (external-dns 1.21.1 → 1.22.0):** pushed ahead-only as `a60bded`. The head is CLEAN and all Flux Local checks pass.
  - The repair pins `annotationPrefix: external-dns.alpha.kubernetes.io/` on both releases. v0.22 changed the default prefix with no fallback, the Gateways use the alpha prefix, and cloudflare-dns runs `policy: sync`.
  - It also removes `--pihole-api-version`, which no longer exists in v0.22.0. kingpin rejects unknown flags, so the pod would crashloop.
  - The render confirms both flags. Every rendered flag exists in the v0.22.0 source.
  - Merging it is a DNS change and needs Sean's go-ahead. #315 (bootstrap CRD URL v0.21 → v0.22) is its companion.
- **#334 (kube-prometheus-stack):** a local repair, `8b5f0f5`, exists: the CRD upgradeJob plus bootstrap CRDs v0.94.1.
  - It was built on the 91.8.0 head `8fc8264`. Renovate has since moved the PR to **91.8.1**.
  - The repair must be rebuilt and re-verified on the new head before it is pushed.
  - It needs a rollout window: the operator CRDs change, and Grafana goes to 13 with distroless images.

## Held (unchanged)

- #218, #293: Talos/Kubernetes. The upgrade is next; admin certs expired 2026-09-09 and need renewal first.
- #256 + #283: Flux operator and distribution, one transaction.
- #263: Longhorn.
- #292: Cilium.
- #253: mysql 8.4.
- #294: romm 5.x.
- Operators, one at a time, after this rollout: #331 cert-manager, #359 CNPG, #320 ESO.
- Stateful apps, each needing a backup check and smoke test: #317 HA, #314 n8n, #318 coder, #319 hindsight, #327 garage, #313 matrix, #343 dragonfly v2.

## Not verified

- **Velero:** BackupStorageLocation, BackupRepository and Schedule status. The `mimir-readonly` service account is forbidden from `velero.io` resources. Check `velero backup-location get` and the next 02:00 UTC scheduled backup.
- **octopi 503:** not confirmed as pre-existing.

## Related

- Template purge: branch `chore/purge-cluster-template` @ `45aa8c9`, pushed; no PR yet.
- The security audit is in the vault, not this public repo: `Plan/2026-09-27_221141-endsys-gitops-security-audit.md`.

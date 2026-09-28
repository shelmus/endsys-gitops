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

## Second pass (2026-09-28, 05:50–06:50 EDT; Sean: "go ahead on everything but the talos upgrade")

| PR | Change | Merge commit | Result |
|---|---|---|---|
| #332 | external-dns chart 1.21.1 → 1.22.0 (app v0.22.0) + repair `a60bded` | `54eb704` | Converged; DNS unchanged |
| #315 | bootstrap DNSEndpoint CRD URL v0.21.0 → v0.23.0 | `699de05` | Bootstrap only; no live effect |
| #334 | kube-prometheus-stack 82.18.0 → 91.8.1 + repair `385538a` | `583ff6c` | Converged; monitoring verified |

**#332:**
- Recorded a baseline first:
  - Pi-hole answers for all 28 HTTPRoute hostnames.
  - Cloudflare A records and `k8s.cname-*` ownership TXT (owner=default) for the 14 external hostnames.
- The v0.22 TXT-registry change (`a-` prefix) applies to AWS A-ALIAS only, not Cloudflare.
- After the merge:
  - Both pods run v0.22.0 with 0 restarts and carry `--annotation-prefix=external-dns.alpha.kubernetes.io/`.
  - pihole-dns no longer passes `--pihole-api-version`.
  - Both log only "All records are already up to date".
  - A re-query of all 28 Pi-hole and 14 Cloudflare answers matched the baseline exactly.
- An unrelated finding: pihole-dns has 837 lifetime restarts. The last one was 2026-09-20: `connection refused` to 10.127.0.3:80 at start-up, which means Pi-hole was down at the time. It has been stable since.

**#315:** the v0.22.0 and v0.23.0 DNSEndpoint CRDs are byte-identical, and v0.21 → v0.22 changes only the controller-gen annotation. The live CRD is v1alpha1 and was untouched, since `scripts/bootstrap-apps.sh` runs only at bootstrap.

**#334:**
- The repair was rebuilt on the 91.8.1 head. Chart 91.8.0 → 91.8.1 only adds the node-exporter `prometheusScrape: false` default. It was pushed ahead-only as `385538a`, and CI passed.
- Pre-merge evidence:
  - The render includes a pre-upgrade/pre-rollback Job that runs `kubectl apply --server-side --force-conflicts` on all 10 CRDs, with pinned busybox 1.37.0 and kubectl v1.34.0.
  - Every live `storedVersion` is still served by the target CRDs.
  - All 10 rendered images resolve in their registries.
  - `amtool` v0.34.1 (sha256-verified) accepts the rendered Alertmanager config.
  - The operator ClusterRole went from 3 wildcard-verb rules to 0.
  - Control-plane ServiceMonitors now use the chart-created `kube-prometheus-stack-prometheus-token` Secret (the 90.x change).
  - The Grafana 13 distroless image forbids `GF_*__FILE`, but this repo uses plain env from the `grafana-oauth` ExternalSecret.
- Two Renovate annotation tags were unquoted: the regex manager's `(?<currentValue>\S+)` would otherwise capture the quote marks.
- Before and after, from read-only snapshots:
  - All 10 CRDs went from `operator.prometheus.io/version` 0.84.1 to **0.94.1**, with storedVersions unchanged.
  - Pods now run operator v0.94.1, Prometheus v3.15.0-distroless, Alertmanager v0.34.1, Grafana 13.2.2-distroless, kube-state-metrics v2.20.0 and node-exporter v1.12.1-distroless. All are Ready with 0 restarts.
  - Prometheus has 37 jobs and **66/66 targets up**; 3 briefly showed `unknown` before their first scrape. 13 alert rules, none firing.
  - Config reloads succeed for both Prometheus and Alertmanager, and the operator reports 0 reconcile errors.
  - Grafana's `/api/health` reports database ok. `/login/generic_oauth` still returns a 302 to PocketID with a client_id.
  - A test alert (`MimirPostUpgradeTest`, severity warning, expires after 3 minutes) was posted at 10:46 UTC. The Discord notification counter went from 0 to 1 with 0 failures.
- Not verified: an interactive Grafana OIDC login all the way through. Sean should log in once.
- Side effect: Prometheus, Alertmanager and Grafana store data in `emptyDir`, so this restart wiped metric history, Alertmanager silences (none were active) and any dashboards created in the UI. Provisioned dashboards come back from ConfigMaps.

## PRs opened

- #361 `chore/purge-cluster-template`: template purge + README. Merged with `main` to drop the 8 `.j2` files that Renovate bumped in this rollout.

## First-pass repair notes (superseded by the second pass)

- **#332:** the repair pins `annotationPrefix: external-dns.alpha.kubernetes.io/`. v0.22 changed the default prefix with no fallback, the Gateways use the alpha prefix, and cloudflare-dns runs `policy: sync`. It also removes `--pihole-api-version`: the flag no longer exists in v0.22.0, and kingpin rejects unknown flags. Every rendered flag exists in the v0.22.0 source.
- **#334:** the first repair, `8b5f0f5`, was built on the 91.8.0 head. It was rebuilt on 91.8.1 as `385538a` and never pushed in its original form.

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

- **Velero:** the `mimir-readonly` service account can't read `velero.io` resources. Sean confirmed on 2026-09-28 that backups run to Garage on Lyris NFS. The CNPG databases still have no point-in-time backup, and no restore has been recorded.
- **octopi 503:** Sean says octopi isn't needed at the moment, so it's out of scope.
- **Grafana:** Sean confirmed on 2026-09-28 that the OIDC login works after the Grafana 13 upgrade.

## Related

- Template purge: PR #361 (`chore/purge-cluster-template` @ `077c28c`).
- The security audit is in the vault, not this public repo: `Plan/2026-09-27_221141-endsys-gitops-security-audit.md`.

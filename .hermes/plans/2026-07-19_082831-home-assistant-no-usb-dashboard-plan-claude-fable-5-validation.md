# Claude Fable 5 validation — Home Assistant no-USB dashboard plan

Generated: 2026-07-19 17:24:57 EDT
Claude result subtype: `success`
Claude session ID: `288b98a3-2c72-4526-b748-7d4cbd463ef9`
Model usage reported: `claude-haiku-4-5-20251001, claude-fable-5`

All evidence gathered. Here is the validation report.

# Home Assistant No-USB Dashboard Plan — Validation Report

## 1. Verdict

**Conditionally approved — safe to execute after two blocking amendments.** The plan's repository-side claims all check out against the actual tree: the HelmRelease matches the described state (chart 0.3.61, `privileged: true`, `kube1` pin, commented USB block, `hostNetwork: true`, Longhorn 10Gi, `configuration.enabled` with broad `trusted_proxies`), the Velero schedule pattern and file paths are correct, the sequencing (backup → proxy repair → decoupling → dashboard) is sound, PR #258 is kept properly out of scope, and removing privilege/node-pin while retaining `hostNetwork` is a genuine security improvement with no regression. However, the plan states an unverified chart behavior as fact in the one place where being wrong loses data, and the rollback plan has a recovery dead-end given the no-`kubectl exec` constraint. Fix both in the plan text before execution.

## 2. Blocking Issues

**B1. The `forceInit` "backs up and deep-merges" claim is asserted as fact but is unverified, and repository history contradicts the plan's root-cause diagnosis.** Git history shows `configuration.enabled: true` and the full `trusted_proxies` list have been in the HelmRelease since the app's *first* commit (`c6831df`, chart 0.3.48). The plan's explanation for the HTTP 400 — "config was initialized before the template would have helped, and `forceInit: false` never rewrote it" — doesn't hold from repo evidence alone: if chart 0.3.48's default template consumed `trusted_proxies` at first init, the `http:` block should already be on the PVC and proxies would be accepted. So either the chart's `trusted_proxies` plumbing does not work the way the plan assumes at these versions, or the PVC's `configuration.yaml` was created outside the chart's init path. The plan must require, as a hard PR-B pre-merge gate: render chart 0.3.61 (flux-local `v8.0.1`, already pinned in `.github/workflows/flux-local.yaml:46` and `e2e.yaml:58`) and *read the generated init-script ConfigMap* to confirm (a) whether `forceInit` merges, or overwrites-with-backup, or plain-overwrites `configuration.yaml`, and (b) whether the default `templateConfig` consumes `configuration.trusted_proxies`. If `forceInit` overwrites rather than merges, any manual YAML customizations Sean added to `configuration.yaml` would be silently dropped — the exact failure the plan's own stop condition ("configuration merge drops integrations…") is meant to catch, but with no specified detection method. The same render check also covers the currently unverified claim that chart 0.3.61 defaults `securityContext`/`nodeSelector` to empty (Phase 3's premise).

**B2. The proxy-bootstrap rollback has a recovery dead-end under the plan's own constraints.** Reverting the PR B commit restores the *pod spec*, but Helm rollback cannot undo the `configuration.yaml` rewrite the `forceInit` init container performed on the PVC. If the merged/overwritten config fails to parse, Home Assistant crashloops; restoring the downloaded backup requires a functioning Home Assistant UI, and `kubectl exec`/`cp` and ad-hoc PVC edits are all forbidden. As written, rollback steps 2–4 cannot recover from the most likely PR-B failure mode. Amend the rollback plan to add a Git-driven re-repair path: a second one-shot `forceInit` rollout with a corrected `templateConfig` (which rewrites the config file through the same supported mechanism, needing no exec), and explicitly state that Git revert does not revert PVC file contents.

## 3. Non-Blocking Improvements

- **Avoid overriding `templateConfig` if the render check shows it's unnecessary.** If chart 0.3.61's default template already renders the `http:` block when `trusted_proxies` is set, PR B may need only `forceInit: true`. A hardcoded `templateConfig` copy will silently drift from chart defaults when PR #258 lands 0.3.70 later, and copying the default while *adding* an unconditional `http:` block risks a duplicate `http:` key (HA config parse failure) if the conditional block is kept.
- **Velero schedule spec is incomplete versus the house pattern.** Existing schedules (e.g., `pocket-id-schedule.yaml`) include `schedule: "0 2 * * *"` and `includeClusterResources: true`; the plan's bullet list omits both. The `.context/backup-restore.md` table also records Cron and Retention columns, so the doc update needs the cron value anyway.
- **The `kustomize build kubernetes/apps/home-assistant` validation command builds the wrong layer.** That path is the namespace overlay (Flux `ks.yaml` + `components/common`), not the app manifests. Add `kustomize build kubernetes/apps/home-assistant/home-assistant/app` (the HelmRelease values themselves are only exercised by flux-local, which the plan correctly also requires).
- **Trusted-proxy narrowing:** `10.42.0.0/16` is corroborated by `kubernetes/apps/kube-system/cilium/app/helm/values.yaml:31` (`ipv4NativeRoutingCIDR: "10.42.0.0/16"`). Two cautions: Cilium's Gateway-API Envoy can source traffic from node IPs (host netns) rather than pod CIDR depending on configuration, so the plan's "verify from live data" step is load-bearing — keep it; and retain `127.0.0.0/8` when narrowing.
- **`.context/hardware/usb-passthrough.md:60` explicitly states "The pod must run with `securityContext.privileged: true` and a `nodeSelector`…"** — PR C's doc update should amend that sentence specifically, not just add a preamble, or the doc will directly contradict the new baseline.
- **Phase 0.1 says "preserve the existing untracked `.hermes` plan" (singular).** There are now two untracked plans (the 2026-07-13 merge-rollout plan and this one). Trivial, but the executor should not treat the second as unexpected.
- **The claim that local `main` is one commit behind `origin/main` was not verifiable this session** (git divergence commands were denied); Phase 0.1's `--ff-only` guard already handles it either way.

## 4. Specific Patch Recommendations

Edits to the plan document (not implemented, per constraints):

1. **§2.2 / "Why forceInit is one-shot":** Replace "The chart's supported force-init path backs up and deep-merges the file" with a requirement: *"Before PR B approval, extract the init-script ConfigMap from the flux-local render of chart 0.3.61 and record its exact `forceInit` semantics (merge vs. overwrite vs. overwrite-with-backup) and whether the default `templateConfig` consumes `configuration.trusted_proxies`. Choose between `forceInit`-only and `templateConfig` override based on that evidence."*
2. **§Central finding / §2.2:** Add: *"Unexplained: `trusted_proxies` and `configuration.enabled: true` have been in the HelmRelease since first deployment (`c6831df`, chart 0.3.48), yet the live instance rejects proxies. Confirm why the initial init did not apply the http block before selecting the repair mechanism."*
3. **§Rollback / Proxy bootstrap rollback:** Insert between steps 3 and 4: *"If Home Assistant fails on configuration parsing, note that Git/Helm rollback does not revert `configuration.yaml` on the PVC. Recover via a second approved one-shot `forceInit` rollout with a corrected `templateConfig` before resorting to backup restore, which requires a running Home Assistant."*
4. **§1.2:** Add `schedule: "0 2 * * *"` and `includeClusterResources: true` to the schedule spec bullets, matching `kubernetes/apps/velero/velero/app/schedules/pocket-id-schedule.yaml`.
5. **§2.3 and §3.3:** Change `kustomize build kubernetes/apps/home-assistant >/dev/null` to `kustomize build kubernetes/apps/home-assistant/home-assistant/app >/dev/null` (optionally keep the namespace-level build in addition).
6. **§3.1:** Change "Update `.context/hardware/usb-passthrough.md` to state that the document is an optional future hardware recipe" to also name line 60's privileged/nodeSelector requirement as the sentence to rewrite.
7. **§0.1:** Pluralize the untracked-plan preservation note to cover both existing `.hermes` plans.

## 5. Read-Only Evidence Checked

**Repository files read:**
- `kubernetes/apps/home-assistant/home-assistant/app/helmrelease.yaml` — confirms chart 0.3.61, privileged, `kube1` pin, commented USB block, `hostNetwork`, `forceInit: false`, broad `trusted_proxies`, service port 8080
- `kubernetes/apps/home-assistant/home-assistant/app/httproute.yaml` — internal gateway, `home-assistant.endsys.cloud`, backend port 8080
- `kubernetes/apps/home-assistant/home-assistant/ks.yaml` and both kustomization layers — SOPS decryption, `wait: false`, namespace overlay uses `components/common`
- `kubernetes/apps/velero/velero/app/kustomization.yaml` and `schedules/` listing — eight existing schedules, no Home Assistant schedule (plan claim confirmed)
- `kubernetes/apps/velero/velero/app/schedules/pocket-id-schedule.yaml` — reference shape for PR A
- `.context/backup-restore.md` (schedule table, lines 30–48) and `.context/hardware/usb-passthrough.md` (full) — doc-update targets exist; line 60 privileged/nodeSelector claim noted
- `kubernetes/apps/kube-system/cilium/app/helm/values.yaml` — `ipv4NativeRoutingCIDR: 10.42.0.0/16`, Gateway API enabled
- `.github/workflows/flux-local.yaml` and `e2e.yaml` — flux-local pinned at `v8.0.1`, matching the plan's container reference

**Git history (read-only):**
- `git log --follow` on the HelmRelease; `git show c6831df:…helmrelease.yaml` — trusted_proxies present since first commit at chart 0.3.48 (basis of B1)
- `git show 5b091a7` — USB mount commented out because `/dev/serial/by-id` was absent on `kube1` and blocked pod start (supports "stale coupling" finding)
- `git log -S trusted_proxies` — no later commit introduced the proxy list
- Session-start git snapshot — branch `main`, clean tracked tree, two untracked `.hermes` plans

**Not verifiable this session (missing evidence, not defects):** live pod/HelmRelease state, the HTTP 400 and log evidence, Velero live backups, PR #258 open/held status and its 0.3.70 target, image tag `2026.5.4`, chart 0.3.61 default values and init-script behavior (no cached chart on disk; `gh`, `kubectl`, and out-of-repo filesystem searches were all denied by the session's permission mode). Blocking issue B1 converts the most load-bearing of these into an explicit pre-merge render gate.

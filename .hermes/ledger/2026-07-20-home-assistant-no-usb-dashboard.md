# Home Assistant no-USB dashboard execution ledger

**Started:** 2026-07-20 13:52 EDT
**Plan:** `.hermes/plans/2026-07-19_082831-home-assistant-no-usb-dashboard-plan.md`
**Validation:** `.hermes/plans/2026-07-19_082831-home-assistant-no-usb-dashboard-plan-claude-fable-5-validation.md`
**Branch:** `feat/home-assistant-backup-baseline`
**Implementation base:** `2254898af78d279acb94613feb83836cee69c475`

## Status

- [x] Plan written and Claude Fable 5 validation adjudicated
- [x] Phase 0 repository synchronization
- [x] Phase 0 desired/live/user-path inventory
- [x] Direct Home Assistant access path identified
- [x] First-run onboarding state identified
- [x] Owner/core onboarding approved and completed
- [x] Fresh Home Assistant application backup downloaded and verified
- [x] PR A backup schedule implemented
- [ ] Proxy bootstrap implemented
- [ ] USB-only coupling removed
- [ ] Native household dashboard configured

## Approved action completed by Sean

At 2026-07-20 13:58 EDT, Sean approved the **minimal onboarding, then Home Assistant application backup** path:

- create the owner and complete core settings/analytics choice through the direct endpoint;
- skip every optional integration and discovered device during onboarding;
- sign in and create/download a Home Assistant application backup before any rollout.

Sean completed onboarding and downloaded the application backup on 2026-07-24.
Credentials and emergency-kit contents are not recorded in this ledger or Git.

## Phase 1 application-backup evidence — 2026-07-24

- Backup filename: `backupfor_mimir.tar`
- Home Assistant backup timestamp: `2026-07-24T09:18:55.093937-04:00`
- Home Assistant version: `2026.5.4`
- Manifest type: `partial`, containing the Home Assistant application archive
- Downloaded size: `3,174,400` bytes
- SHA-256: `b63c8e5a68dff4ac607a636e1d83358b663c68fbf6d7291a07c11d19f3362e06`
- Off-cluster location: `/home/sean/Backups/home-assistant/2026-07-24/backupfor_mimir.tar`
- Protection: parent directory mode `0700`; backup, emergency kit, and checksum file mode `0600`, owned by `sean:sean`
- Outer verification: valid POSIX tar with `backup.json` and `homeassistant.tar.gz`; no unsafe paths, duplicate names, links, or special entries
- Nested verification: gzip/tar stream fully read; 34 regular files totaling `12,865,285` bytes; configuration, `.HA_VERSION`, `.storage/core.config_entries`, and `home-assistant_v2.db` are present; no unsafe paths, duplicate names, links, or special entries
- Download behavior: manifest reports `protected: false`, consistent with Home Assistant documentation that UI downloads are decrypted on the fly

No configuration values, credentials, tokens, database contents, or emergency-kit contents were extracted into the repository.

## PR A repository implementation — 2026-07-24

Implemented on `feat/home-assistant-backup-baseline` without touching the live cluster:

- added `kubernetes/apps/velero/velero/app/schedules/home-assistant-schedule.yaml`;
- added it to the Velero app kustomization;
- documented the application-backup versus crash-consistent Velero boundary;
- reconciled the touched schedule inventory with all 10 schedule manifests, including the previously undocumented `matrix-daily` and `romm-daily` entries.

Local verification:

- `git diff --check` — passed;
- `yamllint` on the new schedule and Velero kustomization — passed;
- standalone `kustomize build` — not run because `kustomize` is absent from yggdrasil's PATH (`exit 127`);
- `kubectl kustomize` using embedded Kustomize `v5.7.1` — passed and rendered 12 documents;
- rendered `home-assistant-daily` count — exactly one;
- rendered namespace, cron, included resources, filesystem backup, storage location, TTL, cluster-resource inclusion, and owner-reference settings — all asserted;
- schedule manifest/documentation inventory — exact 10/10 match;
- secret-pattern scan across the related plan, validation, ledger, and changed files — zero recovery-key-shaped values and zero literal key-assignment labels.
- workflow-equivalent Flux Local test using pinned image `ghcr.io/allenporter/flux-local:v8.0.1@sha256:5c8cb0ff9d26a5260a47e7b3949403d80713d80037b9f0e4c02c5efca3588518` — 80/80 resources passed in 20.92 seconds, including Home Assistant and Velero.

The repository pins standalone Kustomize `5.7.0`; yggdrasil's embedded
Kustomize is `v5.7.1`. GitHub's Flux Local workflow triggers only on pull
requests. PR #296 now supplies that current-head check, which remains a
mandatory pre-merge gate.

## Commit and push evidence — 2026-07-24

- Implementation commit: `9b7d6d93b00950861727e1de43360df5dc744fd2` (`feat(velero): add Home Assistant backup schedule`)
- Verification-ledger commit before PR creation: `cf42c247e7dd341c0ea6c56503fe1c6583efebc9`
- Push: new branch `origin/feat/home-assistant-backup-baseline`, ahead-only
- Pull request: [#296](https://github.com/shelmus/endsys-gitops/pull/296), open against `main`
- Initial PR head: `cf42c247e7dd341c0ea6c56503fe1c6583efebc9`, verified equal to the local and remote branch heads at creation
- Initial GitHub state: mergeable; Flux Local pre-job and labeler passed; render test/diff jobs queued
- Local Flux Local scratch clone: exact pushed commit, regular Git clone, Garage chart `v2.3.0` fixture
- Container isolation: disposable scratch clone only; no credentials mounted; test container removed on exit; scratch directories deleted and verified absent

## Approval gates still closed

- Any storage-level pre-onboarding snapshot
- Pull request merge
- Flux reconciliation or pod restart
- Calendar/provider integration setup
- HACS installation

## Phase 0 repository evidence

- Started from local `main` at `71a8482c3c14bc56d9232f082a3d2c6887e1a582`.
- Inspected incoming paths before synchronization. The incoming work was ROMM plus CI/tooling and a shared Velero kustomization entry; it did not collide with the Home Assistant plans.
- `git pull --ff-only` fast-forwarded `main` to `2254898af78d279acb94613feb83836cee69c475`.
- Created `feat/home-assistant-backup-baseline` at that exact commit.
- Preserved all pre-existing untracked `.hermes` plans and the Fable validation artifact.
- No application manifest, Kubernetes object, Home Assistant state, backup, or external service was changed.

## Dependency classification

### Active runtime dependency: direct USB

**Absent in observed runtime.**

- Live pod volumes are the Longhorn Home Assistant PVC, two generated ConfigMaps, and the projected service-account volume.
- Home Assistant mounts only `/config` plus the projected service-account path.
- No hostPath, `/dev` mount, serial device, or USB volume is present.
- Container is nevertheless privileged and node-pinned to `kube1`; those are stale desired-state accommodations.

### Independent requirement retained

**Host networking remains justified independently of USB.**

- `hostNetwork=true` and `dnsPolicy=ClusterFirstWithHostNet` are live.
- Logs show Chromecast discovery/connection activity for two LAN devices.
- Removing host networking is outside scope.

### Independent user-path blocker

**Confirmed.**

- The HTTPRoute is Accepted and its Service reference is resolved.
- The Service exposes `8080` and targets the named port whose EndpointSlice port is `8123`.
- `https://home-assistant.endsys.cloud/` currently returns `400: Bad Request`.
- Home Assistant logs record reverse-proxy rejection from `10.42.1.240` and later `10.42.2.82`.
- The live generated `hass-configuration` ConfigMap has no `http:` mapping.
- The live generated init script has `forceInit="false"`.
- The observed proxy source has moved between node pod CIDRs, supporting a stable cluster pod-CIDR trust range rather than one ephemeral source address. Final proxy values still require render inspection.

## Live workload and storage

- HelmRelease `home-assistant` is Ready on chart `0.3.61`.
- StatefulSet is `1/1`; current and update revisions match.
- Pod `home-assistant-0` is Running with zero restarts on `kube1`.
- Image is `ghcr.io/home-assistant/home-assistant:2026.5.4`.
- Pod IP is the host-network node address `10.127.0.41`.
- Container/host port is `8123`; the direct access URL is `http://10.127.0.41:8123`.
- PVC `home-assistant-home-assistant-0` is Bound, Longhorn, RWO, 10 GiB.
- The full current container log begins with a recorder warning that the SQLite database had not previously shut down cleanly and an unfinished recorder session was closed. This reinforces that a live filesystem copy is not equivalent to an application-aware backup.

## Home Assistant onboarding and UI state — Phase 0 observation

Before Sean completed onboarding, Home Assistant's own unauthenticated
onboarding API returned:

```json
[
  {"step": "user", "done": false},
  {"step": "core_config", "done": false},
  {"step": "analytics", "done": false},
  {"step": "integration", "done": false}
]
```

Consequences at that time:

- The direct endpoint serves first-run onboarding, not an owner login.
- The normal application-backup UI is not yet available.
- Calendar, to-do, dashboard, HACS, and owner-level integration inventory cannot be completed through normal APIs before onboarding.
- Do not interpret those missing inventories as proof of a configured-but-empty dashboard; first-run setup is simply incomplete.
- Owner credentials must be chosen and entered by Sean, never through chat or browser automation.

Sean completed minimal onboarding on 2026-07-24. Post-onboarding inventory of
calendar, to-do, dashboard, HACS, and hardware-dependent integrations remains a
future approved UI phase; it was not read from the backup or inferred here.

## Other anomalies and evidence gaps

- Logs repeatedly report `Network unreachable` for `alerts.home-assistant.io:443`. This could affect upstream calendar integrations.
- Kube1 has an IPv4 default route via `10.127.0.1` and resolvers `10.127.0.3` and `10.127.0.1`.
- No standard Kubernetes NetworkPolicy exists in the Home Assistant namespace.
- The read-only identity cannot list CiliumNetworkPolicy or CiliumClusterwideNetworkPolicy.
- Hubble CLI is absent and no `hubble-relay` Service exists, so the egress failure is not root-caused.
- Cilium custom-resource reads needed for deeper source attribution are denied to `mimir-readonly`.
- Live Velero schedules/backups remain unverified because the read-only identity lacks access.
- Tablet model, OS, viewport, kiosk features, charging, and burn-in constraints remain unknown and do not block the infrastructure baseline.

## Exact next gate

The application-backup gate is closed successfully, and repository-only PR A
work is implemented, committed, pushed, and locally verified on
`feat/home-assistant-backup-baseline`.

PR #296 is open. No merge action is allowed until every check on its current
head succeeds. Once green, merge is the exact next action requiring Sean's
separate approval. Flux reconciliation and any live Home Assistant or Velero
change remain separate closed red gates. After an approved rollout, do not
report successful Velero coverage until a resulting Backup is `Completed` and
its volume-backup artifact is present.

## Verification provenance

Read-only evidence used:

- `git status`, `git log`, `git diff`, `git worktree list`, `git pull --ff-only`, branch verification
- `kubectl get` for HelmRelease, StatefulSet, pod, Service, EndpointSlice, HTTPRoute, PVC, events, ConfigMaps, node pod CIDRs, Gateway, and Cilium Envoy pods
- `kubectl logs` for the Home Assistant container and setup init container
- `talosctl get routes` and `talosctl get resolvers` on kube1
- Browser reads of the direct endpoint, `/api/onboarding`, and the Gateway hostname

All live infrastructure operations were read-only. Local mutations were the
agreed Git fast-forward/feature branch, the Sean-only recovery files, and the
repo-local plan, ledger, schedule, and documentation work recorded above.

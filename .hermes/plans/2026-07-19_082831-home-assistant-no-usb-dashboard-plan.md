# Home Assistant no-USB dashboard enablement plan

Created: 2026-07-19 08:28 EDT
Repository: `/home/sean/workspace/endsys-gitops`
Related idea: `/home/sean/Documents/cortex/Ideas/Self-Hosted Home Assistant Family Calendar.md`
Status: Validated plan; ready for Sean's staged execution approval. No execution is authorized by this document.

Execution update (2026-07-24): Sean completed minimal onboarding and produced
a verified off-cluster Home Assistant application backup. The downloaded
manifest is type `partial` and contains the Home Assistant application archive,
including configuration, `.storage`, and the SQLite database. This satisfies
the Phase 1 application-backup gate; details and checksums remain in the
execution ledger.

## Outcome

Make the existing Home Assistant instance usable as a calendar-centered household dashboard without waiting for a Z-Wave USB dongle.

The finished state is:

- Home Assistant remains available through `https://home-assistant.endsys.cloud` on the internal Gateway.
- The Home Assistant pod has no direct USB volume, no privileged container, and no `kube1` scheduling requirement.
- `hostNetwork` remains enabled for LAN auto-discovery; it is not treated as a USB setting.
- A separate, storage-mode `Household` dashboard runs first with native Home Assistant cards.
- Calendar and optional to-do/weather data come through existing Home Assistant entities.
- The existing tablet uses an ordinary non-admin Home Assistant session; no long-lived token is embedded in a dashboard.
- The future dongle is an independent project. If it is added later, prefer a network-accessible Z-Wave service rather than restoring direct USB coupling to the Home Assistant pod.

## Central finding

The dongle is not a live runtime dependency today.

The running Home Assistant pod has no USB hostPath and no USB mount. The repository already comments out the Z-Wave volume and mount. Home Assistant is nevertheless still configured with the two accommodations that direct USB would have required:

- `securityContext.privileged: true`
- `nodeSelector: kubernetes.io/hostname: kube1`

Those are stale coupling, not prerequisites for the dashboard.

A separate live blocker exists: the internal HTTPRoute currently returns HTTP 400. Home Assistant logs record:

> A request from a reverse proxy was received ... but your HTTP integration is not set-up for reverse proxies

The route must be repaired before using the tablet URL.

Exact chart evidence explains why the proxy values did not take effect. In both the first deployed chart tag (`0.3.48`) and the current tag (`0.3.61`), the default `templateConfig` emits its `http:` block only when the chart's own `ingress.enabled` or `ingress.external` value is true. This deployment uses a separate HTTPRoute and leaves both chart Ingress modes disabled. The long-standing `configuration.trusted_proxies` values were therefore inert rather than proof that the live PVC already contained an `http:` section.

The immutable `home-assistant-0.3.61` chart source at commit `1ff2e477902268c8006fe35259c6cd5e1df1a9aa` also confirms that `forceInit` first copies the existing file to `/config/configuration.yaml.<timestamp>` and then deep-merges the rendered template with `yq`. The execution phase must still inspect the Flux Local render; source inspection is not a substitute for verifying the actual Helm values and generated ConfigMaps in PR B.

## Authorization boundary

This document is a plan, not authorization to execute it.

The following are shared-infrastructure or player/user-facing mutations and require Sean's explicit approval at the named gate:

1. Creating or changing Home Assistant backups through the UI.
2. Merging any GitOps pull request and allowing Flux to reconcile it.
3. Forcing a Flux reconciliation or restarting/replacing the Home Assistant pod.
4. Adding calendar integrations, users, dashboards, cards, resources, or HACS packages in Home Assistant.
5. Running `kubectl exec`, `kubectl cp`, or any restore operation.

Feature-branch repository edits and tests may proceed after this plan is accepted. An ahead-only push to a Sean-owned feature branch may proceed after verification and must be reported. Do not merge to `main`, reconcile Flux, or mutate Home Assistant without a fresh, exact approval.

## Grounded current state

Observed during planning on 2026-07-19 and refreshed during Phase 0 on 2026-07-20:

| Item | Evidence |
|---|---|
| Home Assistant workload | HelmRelease Ready on chart `0.3.61`; image `ghcr.io/home-assistant/home-assistant:2026.5.4` |
| Pod | `home-assistant-0`, Running, zero restarts, scheduled on `kube1` |
| Storage | Bound 10 GiB Longhorn RWO PVC `home-assistant-home-assistant-0` |
| Exposure | Internal HTTPRoute for `home-assistant.endsys.cloud` exists |
| Gateway behavior | HTTPS request returned HTTP 400 |
| Proxy diagnosis | Home Assistant log explicitly rejected a reverse-proxy request |
| Direct access | `http://10.127.0.41:8123` is reachable and serves Home Assistant directly; Service port `8080` targets named container/host port `8123` |
| Onboarding | Home Assistant `/api/onboarding` reports `user`, `core_config`, `analytics`, and `integration` all `done: false`; no owner login exists yet |
| Generated config | Live `hass-configuration` ConfigMap has no `http:` block; live `init-script` has `forceInit="false"` |
| USB use | No live USB hostPath or mount in the pod |
| Residual USB coupling | Privileged container and `kube1` nodeSelector remain in Helm values |
| Discovery requirement | `hostNetwork: true`; live logs show Chromecast integrations, so retain it |
| Chart defaults | Chart `0.3.61` defaults `securityContext` and `nodeSelector` to empty; neither is required generally |
| Backup declaration | No Home Assistant Velero schedule exists in the repository |
| Backup live state | Not verified: the Mimir read-only service account cannot list Velero schedules, backups, or VolumeSnapshots |
| Existing audit | 2026-07-13 repo audit held Home Assistant PR #258 for lack of a fresh application backup |
| Pending upgrade | PR #258 updates chart `0.3.61` to `0.3.70`; it is open and deliberately excluded from this change |
| Local repo | `main` fast-forwarded to `2254898af78d279acb94613feb83836cee69c475`; implementation branch is `feat/home-assistant-backup-baseline`; all existing untracked plan/review artifacts were preserved |
| Egress anomaly | Logs repeatedly report `Network unreachable` for `alerts.home-assistant.io`; kube1 has an IPv4 default route and resolvers, but Cilium policy visibility/Hubble telemetry was unavailable, so cause is unverified |

### Facts not checked

- The contents of the PVC's `/config/configuration.yaml` were not read. The generated configuration ConfigMap was inspected, but it is not proof of later manual PVC edits.
- Active user-level Home Assistant integrations, calendar entities, to-do entities, dashboards, and HACS resources cannot be inventoried through normal APIs before owner onboarding. The onboarding API proves those first-run steps are incomplete; do not create the owner during read-only Phase 0.
- The tablet OS/model remains to be inventoried.
- The recurring outbound `Network unreachable` error was not root-caused. Standard namespace NetworkPolicy is absent; the read-only identity cannot list Cilium policies, and Hubble CLI/relay is unavailable.

## Architectural decisions

### Keep

- StatefulSet controller and existing Longhorn PVC.
- `hostNetwork: true` and `dnsPolicy: ClusterFirstWithHostNet` for LAN discovery.
- Existing internal Gateway and standalone HTTPRoute.
- Home Assistant storage-mode dashboards for the first version.
- Current chart/application versions during this work.

### Remove

- `securityContext.privileged: true`.
- The `kube1` nodeSelector.
- The commented Z-Wave USB volume and mount block from the active HelmRelease.
- Any dashboard milestone that waits for USB hardware.

### Add

- An explicit Home Assistant `http:` configuration suitable for the internal Gateway.
- A fresh, downloaded Home Assistant application backup before rollout.
- A supplemental Velero schedule for the Home Assistant namespace.
- A dedicated `Household` dashboard and non-admin display user.
- A sanitized dashboard configuration snapshot and operating note after the UI stabilizes.

### Do not combine

Do not combine this work with:

- Renovate PR #258 or any Home Assistant/chart version change.
- Talos, Cilium, Gateway, Longhorn, or Velero upgrades.
- Direct Z-Wave, Zigbee, Thread, Bluetooth, or serial hardware setup.
- A custom frontend application or custom Lovelace card.
- A forced pod move merely to prove that the nodeSelector is gone.

## Files expected to change

### GitOps repository

- `kubernetes/apps/home-assistant/home-assistant/app/helmrelease.yaml`
- `kubernetes/apps/velero/velero/app/schedules/home-assistant-schedule.yaml` — new
- `kubernetes/apps/velero/velero/app/kustomization.yaml`
- `.context/backup-restore.md`
- `.context/hardware/usb-passthrough.md`

### Home Assistant state, after explicit approval

- `/config/configuration.yaml`, indirectly through the chart's supported one-shot `configuration.forceInit` merge.
- `.storage/lovelace*`, through the Home Assistant dashboard editor.
- `.storage/auth*`, through creation of a non-admin display user.
- Calendar/to-do integration state only where Sean approves the relevant provider setup.

Do not copy credentials, auth storage, OAuth tokens, or unsanitized Home Assistant configuration into Git or the vault.

## Delivery slices

Use small pull requests and separate Flux rollouts so each failure has one likely cause.

1. **PR A — supplemental backup schedule and documentation.** No Home Assistant restart.
2. **PR B — reverse-proxy bootstrap.** One controlled Home Assistant rollout with `forceInit: true`.
3. **PR C — normalize configuration and remove USB coupling.** Set `forceInit: false`, remove privilege, node pin, and dormant USB comments; one controlled rollout.
4. **Home Assistant UI change — native dashboard.** Performed only after the infrastructure baseline is healthy.
5. **Optional UI change — HACS polish.** Separate approval and rollback from the native dashboard.

PR #258 remains separate and held until its own backup and upgrade review gate is satisfied.

## Phase 0 — execution preflight

### 0.1 Synchronize safely

Before editing:

```bash
cd /home/sean/workspace/endsys-gitops
git status --short --branch
git log --oneline --decorate main..origin/main
git switch main
git pull --ff-only
git switch -c feat/home-assistant-backup-baseline
```

Requirements:

- Preserve every existing untracked `.hermes` plan and validation artifact; do not assume a fixed count or treat another session's artifact as disposable.
- Stop if `git pull --ff-only` cannot fast-forward.
- Do not clean, stash, or delete another session's files silently.
- Record the exact `origin/main` commit used as the implementation base.

### 0.2 Inventory Home Assistant without changing it

In Home Assistant, record:

- current installation version and backup integration availability;
- active integrations that could depend on host hardware: Z-Wave JS, ZHA, Bluetooth, Thread, OTBR, serial, GPIO, and any custom component using `/dev`;
- active Chromecast/media integrations that justify retaining host networking;
- existing calendar entities and whether each source is read-only or writable;
- existing `todo.*` and weather entities;
- existing dashboards and HACS frontend resources;
- current admin access path while the Gateway route is broken.

Runtime evidence already shows no mounted host device. If the UI lists a direct-device integration, stop and determine whether it is merely unconfigured or is unexpectedly relying on another path before removing privilege.

Phase 0 found that owner onboarding is incomplete. Until Sean creates the owner account, treat calendar/to-do/dashboard/HACS inventory as **not yet configured through normal onboarding**, not as a failed discovery task. Do not add integrations during onboarding; complete the minimal owner/core setup, take the baseline backup, and inventory/add data sources only afterward.

### 0.3 Record the tablet target

Record, without guessing:

- model, OS, browser or Home Assistant Companion App version;
- landscape viewport size;
- whether guided access/kiosk/fullscreen and wake lock are available;
- charging and burn-in constraints.

This does not block the infrastructure work, but it does block final tablet acceptance.

### Exit criteria

- Clean implementation base is known.
- No active integration has an unexplained direct device dependency.
- A direct Home Assistant path is available at `http://10.127.0.41:8123`, but owner onboarding remains an explicit red gate before admin access exists.
- Calendar/to-do/weather inventory is either written down or explicitly deferred because first-run onboarding is incomplete. Phase 0 uses the latter disposition.

## Phase 1 — establish recoverability

### 1.0 Complete minimal first-run onboarding

The normal application-backup UI is unavailable until Home Assistant has an owner. Phase 0 proved all onboarding steps are incomplete.

**Red gate:** Sean must explicitly approve and personally complete the following at `http://10.127.0.41:8123`:

1. Create the owner account using credentials that never enter chat, Git, the ledger, browser automation, or command history.
2. Complete core location/unit settings and make the analytics choice.
3. Skip optional integrations and discovered devices during onboarding; calendar and other integrations come only after the baseline backup.
4. Sign in successfully through the direct endpoint.

This necessarily creates Home Assistant state before an application-native backup can exist. If Sean requires a snapshot of the untouched pre-onboarding PVC, stop and request a separate exact approval for a storage-level backup first. Do not silently substitute Velero or a Longhorn snapshot for the application backup.

### 1.1 Create a fresh Home Assistant application backup

**Red gate:** Ask Sean to approve the exact UI backup action before proceeding.

Use Home Assistant's Backup integration, which supports all Home Assistant installation types:

1. Open **Settings → System → Backups** using the working admin path.
2. Choose **Backup now → Manual backup**.
3. Create an application backup containing the Home Assistant configuration; media/share content is unnecessary for this change.
4. Download the backup to an off-cluster system before any pod rollout.
5. Download and protect the emergency kit if the backup is encrypted.
6. Record the backup timestamp, filename, size, and checksum in the execution ledger—not in persistent memory.

Offline verification:

```bash
sha256sum "$BACKUP_FILE"
tar -tf "$BACKUP_FILE" >/dev/null
```

If the downloaded format contains nested archives, list them and verify that a Home Assistant config archive exists. Do not extract secrets into the repository. Use a private temporary directory with restrictive permissions if configuration inspection is necessary.

**Hard stop:** No backup file outside the Home Assistant pod/PVC, no rollout.

### 1.2 Add a supplemental Velero schedule

Create:

`kubernetes/apps/velero/velero/app/schedules/home-assistant-schedule.yaml`

Follow the existing simple-app schedule shape:

- `kind: Schedule`
- name `home-assistant-daily`
- namespace `velero`
- `schedule: "0 2 * * *"`
- include namespace `home-assistant`
- include all namespace resources
- `defaultVolumesToFsBackup: true`
- storage location `default`
- 30-day TTL
- `includeClusterResources: true`
- normal backup labels
- `useOwnerReferencesInBackup: false`

Add the file to `kubernetes/apps/velero/velero/app/kustomization.yaml` and add Home Assistant to the schedule table in `.context/backup-restore.md`.

Caveat: this is a filesystem-level backup of a live SQLite-backed application. Treat it as supplemental disaster-recovery coverage, not proof of application consistency. The downloaded Home Assistant backup remains the rollout gate.

### 1.3 Validate PR A

```bash
git diff --check
yamllint kubernetes/apps/velero/velero/app/schedules/home-assistant-schedule.yaml \
  kubernetes/apps/velero/velero/app/kustomization.yaml
kustomize build kubernetes/apps/velero/velero/app >/dev/null
```

Also require the repository's GitHub `Flux Local` checks to pass on the feature branch/PR.

### 1.4 Roll out PR A

**Red gate:** Merge and Flux reconciliation require a separate exact approval.

After the revision reaches Flux, verify with an account authorized to read Velero CRs:

```bash
kubectl -n velero get schedule home-assistant-daily -o wide
kubectl -n velero get backup --sort-by=.metadata.creationTimestamp
```

Do not wait for this schedule to replace the downloaded backup. Do not report successful backup coverage until at least one resulting backup is `Completed` and its volume backup is present.

## Phase 2 — repair the internal Gateway path

### 2.1 Narrow the trusted proxy range

Determine the actual cluster pod CIDR and Gateway/Envoy source behavior from live read-only data. The observed proxy address was in `10.42.0.0/16`, but verify rather than copying that observation blindly.

Use the narrowest stable CIDR that covers the Gateway proxy source. Do not retain all of RFC1918 merely for convenience unless live architecture proves it necessary. Retain `127.0.0.0/8` for local proxying unless live evidence proves it is unnecessary. Cilium declares `10.42.0.0/16` as its native-routing CIDR, but Gateway Envoy may source from a node address depending on its mode; the live source check is load-bearing.

### 2.2 Add an explicit configuration template

In `kubernetes/apps/home-assistant/home-assistant/app/helmrelease.yaml`:

- retain `configuration.enabled: true`;
- set `configuration.forceInit: true` for this rollout only;
- retain or narrow `configuration.trusted_proxies` based on the previous step;
- define `configuration.templateConfig` by preserving the chart's current default content and **replacing** its Ingress-conditional `http:` block with one unconditional `http:` block with:
  - `use_x_forwarded_for: true`;
  - `trusted_proxies` rendered from the approved values list.

The template must continue to include:

- `default_config:`
- frontend themes include;
- `automation: !include automations.yaml`;
- `script: !include scripts.yaml`;
- `scene: !include scenes.yaml`.

Do not retain the original conditional block and add a second `http:` key. The rendered configuration must contain exactly one `http:` mapping.

Why `forceInit` is one-shot: the chart only copies configuration on first initialization when `forceInit` is false. The existing PVC already has a configuration file, so a template-only Git change would not repair the live instance. In chart `0.3.61`, the supported force-init path copies the current file to `/config/configuration.yaml.<timestamp>` and then runs `yq eval-all --inplace 'select(fileIndex == 0) *d select(fileIndex == 1)'` against the current and rendered files. Leaving it enabled forever would create a new backup and merge on every restart.

Before PR B approval, the Flux Local render must prove those same semantics from the generated init-script ConfigMap and must prove that the generated configuration contains the intended single `http:` block. If the rendered behavior differs from the pinned source, stop. Record any custom top-level configuration visible in the downloaded Home Assistant backup so post-rollout checks can detect loss; do not commit that configuration.

Do not remove privilege or node placement in this PR. Isolate proxy repair first.

### 2.3 Render and inspect PR B

Required checks:

```bash
git diff --check
yamllint kubernetes/apps/home-assistant/home-assistant/app/helmrelease.yaml
kustomize build kubernetes/apps/home-assistant/home-assistant/app >/dev/null
```

Run the repository's full Flux Local render either locally with the workflow-equivalent `ghcr.io/allenporter/flux-local:v8.0.1` container or through GitHub Actions. Confirm the rendered StatefulSet still has:

- the same image/chart versions;
- the same PVC claim/template;
- `hostNetwork: true`;
- the existing nodeSelector and privilege for this intermediate rollout;
- a generated configuration ConfigMap with exactly one unconditional `http:` mapping and all required include directives;
- a generated init-script ConfigMap that copies the current configuration to a timestamped backup before the exact deep merge;
- chart-default empty `securityContext` and `nodeSelector` behavior, as preparation for PR C.

Do not approve the PR from YAML syntax alone. Save the relevant rendered ConfigMap excerpts in the execution ledger without copying Home Assistant secrets.

### 2.4 Roll out and verify PR B

**Red gate:** Merge/reconcile requires exact approval and a named maintenance window.

Observe natural Flux reconciliation unless Sean explicitly approves a forced reconcile.

Verify:

```bash
kubectl -n home-assistant get helmrelease home-assistant
kubectl -n home-assistant rollout status statefulset/home-assistant --timeout=5m
kubectl -n home-assistant get pod -o wide
kubectl -n home-assistant logs home-assistant-0 -c setup-config
kubectl -n home-assistant logs home-assistant-0 --since=10m
curl -fsS -o /dev/null -w '%{http_code}\n' https://home-assistant.endsys.cloud/
```

Record the exact `/config/configuration.yaml.<timestamp>` backup filename printed by the `setup-config` init container. It is the deterministic recovery source for this rollout.

Pass conditions:

- HelmRelease and pod are Ready.
- The existing PVC is mounted and Home Assistant retains integrations/entities.
- The Gateway URL returns the Home Assistant frontend/login flow rather than HTTP 400.
- No new `reverse proxy ... not set-up` error appears.
- Existing Chromecast/media discovery remains functional.
- A fresh post-rollout Home Assistant backup can be created.

If configuration parsing or startup fails, do not assume a Git or Helm rollback reverts the PVC file; it does not. Follow **Proxy bootstrap rollback** below using the exact timestamped backup recorded from the init log.

## Phase 3 — remove USB-only coupling

### 3.1 Normalize the Helm values

Create a fresh branch from the now-current `main`.

In `kubernetes/apps/home-assistant/home-assistant/app/helmrelease.yaml`:

1. Set `configuration.forceInit: false`.
2. Remove:
   ```yaml
   securityContext:
     privileged: true
   ```
3. Remove:
   ```yaml
   nodeSelector:
     kubernetes.io/hostname: kube1
   ```
4. Delete the commented Z-Wave `additionalVolumes` and `additionalMounts` block.
5. Retain `hostNetwork: true` and `dnsPolicy: ClusterFirstWithHostNet`.
6. Do not alter the chart version, image version, controller type, PVC, service, HTTPRoute, or resources.

Update `.context/hardware/usb-passthrough.md` to state that the document is an optional future hardware recipe and that the Home Assistant dashboard does not require direct USB. Specifically rewrite the current sentence saying the pod "must" be privileged and node-pinned: describe those settings as a last-resort direct-device pattern, not the Home Assistant baseline. Do not delete the generic Talos USB knowledge.

### 3.2 Validate scheduling and port assumptions

Before merge:

- confirm every eligible target node can attach the Longhorn RWO volume;
- confirm no host-networked workload reserves Home Assistant's listening port on eligible nodes;
- confirm the rendered pod has no hostPath and no privileged context;
- confirm the rendered pod has no hostname nodeSelector;
- confirm host networking remains present.

Do not drain a node or force a reschedule for this test.

### 3.3 Validate PR C

```bash
git diff --check
yamllint kubernetes/apps/home-assistant/home-assistant/app/helmrelease.yaml
kustomize build kubernetes/apps/home-assistant/home-assistant/app >/dev/null
```

Require the full Flux Local GitHub checks to pass. Inspect the rendered diff; the only StatefulSet behavior changes should be:

- one-shot force init disabled;
- privilege removed;
- node pin removed;
- no USB comments in source.

### 3.4 Roll out and verify PR C

**Red gate:** Merge/reconcile requires a new exact approval; approval for PR B does not carry forward.

Verify:

```bash
kubectl -n home-assistant get helmrelease home-assistant
kubectl -n home-assistant rollout status statefulset/home-assistant --timeout=5m
kubectl -n home-assistant get pod -o wide
kubectl -n home-assistant get pod home-assistant-0 \
  -o jsonpath='{.spec.containers[0].securityContext}{"\n"}{.spec.nodeSelector}{"\n"}{.spec.volumes}{"\n"}'
kubectl -n home-assistant logs home-assistant-0 --since=10m
curl -fsS -o /dev/null -w '%{http_code}\n' https://home-assistant.endsys.cloud/
```

Pass conditions:

- Home Assistant is Ready with the same PVC and data.
- Container `privileged` is absent/false.
- The hostname nodeSelector is absent.
- No hostPath/USB volume is present.
- The Gateway URL still works.
- Existing calendar, media, and discovery integrations remain available.
- No new permission, raw-socket, or device-access error appears.

If a real, named integration fails because privilege was removed, stop and identify the minimum capability/device it needs. Do not reflexively restore full privilege. If the rollout itself fails, revert PR C through Git.

## Phase 4 — build the native household dashboard

### 4.1 Baseline policy

Start with built-in Home Assistant cards. Do not install HACS resources in the first pass.

Create a separate storage-mode dashboard named `Household`; do not replace or destructively rewrite the existing Overview dashboard. This gives an immediate fallback.

### 4.2 Connect only required data

Using the Phase 0 inventory:

- select the existing calendar entities to show;
- add one upstream calendar integration only if the needed calendars are not already present;
- identify which sources permit event creation;
- select an existing `todo.*` entity if one is useful;
- select one weather entity if available.

Provider OAuth, app passwords, and tokens stay in Home Assistant's integration storage. Do not place them in dashboard YAML, Git, or Obsidian.

**Red gate:** Adding or re-authenticating any integration requires explicit approval naming the provider and requested permissions.

### 4.3 Compose the first dashboard

Use a responsive Sections/Grid view for tablet landscape. The first pass should contain:

1. **Header/context section**
   - current date/time using native/template presentation;
   - current weather if an entity already exists;
   - a small unavailable/problem indicator rather than a general smart-home control panel.
2. **Primary calendar section**
   - native Calendar card;
   - seven-day/list-week default where supported;
   - only the approved family calendar entities;
   - readable titles, all-day events, and overlapping-event behavior.
3. **Companion section**
   - native To-do list card if an approved entity exists;
   - otherwise omit it rather than blocking the dashboard.
4. **Navigation/fallback**
   - direct path to the full Home Assistant Calendar panel for create/edit workflows the card cannot provide cleanly.

Keep unrelated lights, cameras, energy, and administrator controls out of this first dashboard.

### 4.4 User and session model

Create a non-admin user such as `household-display` through Home Assistant's UI. Use a normal authenticated browser or Companion App session.

Do not:

- embed a long-lived token;
- use the owner/admin account as the kiosk identity;
- expose the dashboard publicly;
- place credentials in URL parameters or YAML.

Home Assistant's standard non-admin role is not fine-grained entity authorization. Treat dashboard composition as presentation control, not a hard security boundary.

### 4.5 Tablet QA

Test on the actual existing tablet:

- portrait and landscape behavior, with landscape as the target;
- initial login and session persistence;
- refresh after Home Assistant restart;
- seven-day readability at normal viewing distance;
- all-day, timed, overlapping, empty, and unavailable calendar states;
- to-do add/complete/edit behavior if enabled;
- event create/edit path only on a proven writable calendar;
- accidental navigation and access to administrator surfaces;
- screen wake, dimming, burn-in, charging, and network recovery.

Do not buy display hardware during this phase.

### 4.6 Capture the result

After the native dashboard is accepted:

- export/copy its raw configuration through Home Assistant's dashboard editor;
- sanitize it for secrets and tokens;
- record the card/entity dependencies and restoration steps in a vault runbook under `Workflows/Home Assistant Family Dashboard/`;
- create and download a second Home Assistant backup containing the dashboard state;
- verify its checksum and archive listing.

The Home Assistant backup is the authoritative state capture. The vault copy is a readable reconstruction aid, not a credential store.

## Phase 5 — optional dashboard polish

Only enter this phase if the native dashboard passes functionally but has a named usability gap.

Possible HACS additions:

- `week-planner-card` for a denser family-oriented week layout;
- Lovelace WallPanel for browser fullscreen, wake lock, and photo screensaver behavior.

For each addition:

1. Record the exact gap the component fixes.
2. Review repository activity, release recency, Home Assistant compatibility, and open security issues.
3. Add one component at a time after explicit approval.
4. Record installed version and resource URL.
5. Retest tablet loading and fallback behavior.
6. Keep the native dashboard copy available until the custom resource survives a Home Assistant restart/update.

Do not write an original custom card unless both native and maintained HACS composition fail a documented acceptance criterion.

## Verification matrix

| Layer | Before | After | Pass condition |
|---|---|---|---|
| Backup | No repo schedule; live state unknown | Downloaded HA backup plus declared Velero schedule | Off-cluster archive verified; schedule exists; completed Velero backup verified separately |
| Gateway | HTTP 400; proxy rejection in logs | Frontend/login response through internal URL | No proxy rejection and expected HTTP response |
| Pod security | Privileged | Unprivileged/default chart context | `privileged` absent/false |
| Placement | Pinned to `kube1` | Scheduler-managed | Hostname nodeSelector absent |
| USB | No live mount; dormant comments | No USB declaration or expectation | No hostPath/device mount |
| Discovery | Host networking enabled | Host networking retained | Existing LAN media discovery remains functional |
| State | Existing Longhorn PVC | Same claim and HA configuration | Entities/integrations/dashboard persist |
| Dashboard | None dedicated | `Household` storage dashboard | Calendar loads and remains usable on actual tablet |
| Authentication | Existing admin use unknown | Non-admin display session | No embedded/admin token |
| Reproducibility | UI state only | HA backup plus sanitized runbook | Restore inputs recorded and verified |

## Rollback plan

### Proxy bootstrap rollback

1. Stop on failed readiness or configuration parsing. Read the `setup-config` init-container log and capture the exact `/config/configuration.yaml.<timestamp>` filename created before the merge.
2. Remember that reverting the proxy-bootstrap Git commit restores Kubernetes/Helm declarations but does **not** restore `configuration.yaml` on the PVC.
3. If Home Assistant still starts and the failure is limited to proxy behavior, prefer a reviewed forward fix. Do not churn the PVC merely to make the Git diff look reverted.
4. If Home Assistant cannot start because the merged file is invalid, prepare a temporary GitOps recovery change that sets `configuration.forceInit: false` and replaces `configuration.initScript` with a minimal script that copies the **exact recorded** timestamped backup over `/config/configuration.yaml` and verifies that the restored file is non-empty. Do not select "latest" or guess a filename.
5. Render that recovery change with Flux Local and obtain a fresh red-gate approval before merge/reconciliation. The existing chart init container will restore the file on the same PVC without `kubectl exec` or `kubectl cp`.
6. After Home Assistant is Ready, remove the temporary recovery script in a follow-up GitOps change, retain `forceInit: false`, and verify the route and integrations from the recovered baseline.
7. If the timestamped chart backup is absent or unusable, stop. Restoring the downloaded Home Assistant backup then requires a separately approved recovery procedure that can access the PVC; a functioning Home Assistant UI cannot be assumed during a crash loop.
8. Do not hand-edit the PVC while Flux is reconciling, and do not claim Helm rollback restored mutable application files.

### USB-decoupling rollback

1. Identify the exact integration or startup failure.
2. Revert PR C through Git.
3. Restore only the minimum required capability after root-cause analysis; do not accept full privilege as the default answer.
4. Keep direct USB out of this dashboard project even if future hardware work needs a separate service.

### Dashboard rollback

1. Switch the tablet back to the existing Overview/default dashboard.
2. Disable the new dashboard without deleting the known-good default.
3. Remove a newly added HACS resource before removing its fallback card.
4. Restore from the post-dashboard Home Assistant backup only for corrupted state, not ordinary layout mistakes.

## Stop conditions

Stop immediately if any of the following occurs:

- no downloaded, verifiable Home Assistant backup exists;
- the implementation base cannot fast-forward cleanly;
- PR #258 or another dependency changes the chart/application version in the same diff;
- Flux Local or required GitHub checks fail;
- the rendered chart does not back up before merging, contains duplicate `http:` keys, or differs materially from the inspected `0.3.61` init semantics;
- no exact timestamped configuration recovery path is available for PR B;
- rendered PVC identity/controller type changes unexpectedly;
- HelmRelease becomes NotReady or remediation loops;
- the Home Assistant pod cannot mount the existing PVC;
- the Gateway still returns 400 after proxy bootstrap;
- configuration merge drops integrations, automations, scripts, or scenes;
- removal of privilege causes an unexplained integration failure;
- Longhorn reports a degraded/faulted volume;
- calendar provider setup requests broader permissions than necessary;
- the tablet requires administrator credentials or an embedded token;
- a HACS package is needed merely for aesthetics before the native baseline works.

## Definition of done

Infrastructure:

- [x] A fresh Home Assistant application backup is downloaded off-cluster and checksum/archive verification passes.
- [ ] Home Assistant has a declared Velero schedule, and a completed backup is verified without overstating SQLite consistency.
- [ ] `https://home-assistant.endsys.cloud` serves the Home Assistant login/frontend through the internal Gateway.
- [ ] The Home Assistant container is not privileged.
- [ ] The StatefulSet has no `kube1` nodeSelector.
- [ ] No USB hostPath, device mount, or dormant USB requirement remains in the active HelmRelease.
- [ ] `hostNetwork` remains and LAN discovery smoke checks pass.
- [ ] Home Assistant still uses the same Longhorn PVC and retains existing state.
- [ ] PR #258 remains separate from this work.

Dashboard:

- [ ] A separate `Household` dashboard exists and the original Overview remains available.
- [ ] Native calendar rendering works with approved entities.
- [ ] Empty, overlapping, all-day, and unavailable states are acceptable on the actual tablet.
- [ ] To-do/weather are included only when working entities exist.
- [ ] Writable calendar actions are tested only against a disposable event.
- [ ] The tablet uses a non-admin ordinary session with no embedded token.
- [ ] A sanitized reconstruction runbook and a fresh post-dashboard backup exist.
- [ ] HACS is optional and no original frontend code is required.

## Open inputs that do not block plan approval

- Existing tablet model and OS.
- Calendar providers/entities to surface.
- Whether to-do or weather earns the companion section.
- Chosen off-cluster destination for downloaded Home Assistant backups.
- Whether the future Z-Wave stack will be hosted beside the radio or elsewhere on the LAN.

Resolve these at the relevant execution gate; do not invent answers in advance.

## Claude Fable 5 validation

Status: Completed and adjudicated on 2026-07-19.

Validation artifact:

`/home/sean/workspace/endsys-gitops/.hermes/plans/2026-07-19_082831-home-assistant-no-usb-dashboard-plan-claude-fable-5-validation.md`

Claude CLI result: `success`; session `288b98a3-2c72-4526-b748-7d4cbd463ef9`; model usage explicitly included `claude-fable-5` (and Haiku for auxiliary work).

Fable's verdict was **conditionally approved after two blocking amendments**. Adjudication:

- **Accepted:** require exact chart/render inspection rather than trusting prose; make the PVC-file rollback explicit; add Velero cron and cluster resources; correct the app-layer Kustomize path; retain loopback when narrowing proxies; rewrite the contradictory USB documentation sentence; preserve all untracked plan artifacts.
- **Corrected with stronger evidence:** the proxy values existing since the first commit do not contradict the diagnosis. Tags `0.3.48` and `0.3.61` both guard the default `http:` block on chart-managed Ingress, while this deployment uses a standalone HTTPRoute.
- **Strengthened beyond the recommendation:** a second ordinary `forceInit` merge is not a sufficient recovery guarantee if the current YAML is malformed. The rollback now restores the exact chart-created timestamped file through a temporary, rendered Git-driven init script.

With these amendments incorporated, the plan is validated for staged execution. Every named red gate still requires separate approval.

## Execution handoff prompt

```text
Implement the accepted Home Assistant no-USB dashboard enablement plan in:
/home/sean/workspace/endsys-gitops/.hermes/plans/2026-07-19_082831-home-assistant-no-usb-dashboard-plan.md

Start with Phase 0 and stop at every named red gate. Do not merge, reconcile Flux, restart Home Assistant, create backups, mutate Home Assistant UI state, install HACS, or use kubectl exec/cp without Sean's exact approval for that step.

Keep PR #258 and all version upgrades out of scope. Preserve hostNetwork for LAN discovery. The first required safety artifact is a fresh downloaded Home Assistant backup; no backup means no rollout. Use separate changes for the Velero schedule, one-shot proxy bootstrap, and USB-coupling removal. Verify every phase with real render/runtime output and update the repo-local ledger as work proceeds.
```

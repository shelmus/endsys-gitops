# ROMM Deployment Ledger

**Date:** 2026-07-14
**Plan:** `.hermes/plans/2026-07-14_190017-romm-deployment.md`
**GitOps branch:** `feat/romm`
**Ansible branch:** `feat/romm-nfs`

## Confirmed inputs

- User selected option 1: reuse `/vault/games` read/write.
- Lyris is `10.127.0.7`.
- Live `/vault/games` is approximately 355 GiB and currently exists as `root:root`, mode `0777`.
- Existing structure includes `/vault/games/roms/{n64,nes,Nintendo Gameboy,Nintendo Gameboy Advance,the-eye.eu}` and `/vault/games/roms_other`.
- Existing NFS exports do not include `/vault/games`.
- Cluster nodes are amd64; Longhorn has ample current free capacity for the planned application-state claims.
- ROMM 4.9.2 supports PostgreSQL, external Redis-compatible caches, `/romm/library`, `/romm/resources`, `/romm/assets`, and `/romm/config/config.yml`.
- ROMM's dedicated unauthenticated health endpoint is `/api/heartbeat`.

## Decisions

- Existing game bytes will not be copied, moved, renamed, scanned, or deleted by infrastructure automation.
- `/vault/games` will be exported to `10.127.0.0/24` with `root_squash`.
- ROMM is internal-only for initial deployment.
- Local setup wizard precedes optional Pocket ID OIDC.
- Velero will exclude the NFS library volume.

## Status

- [x] Discovery and storage choice
- [x] Implementation plan written
- [x] Ansible desired state implemented
- [x] GitOps manifests implemented
- [x] Static/render validation complete
- [x] Feature commits complete
- [ ] Live mutation approvals received
- [x] NFS applied and verified
- [x] Secret created and verified
- [ ] GitOps deployed and live health verified

## Approval gates still closed

- Pull request merge
- Live Flux reconciliation

## Verification evidence

GitOps checks run independently after both Claude Code workers exhausted their turn budgets:

- `kubectl kustomize kubernetes/apps/romm`: pass.
- `kubectl kustomize kubernetes/apps/velero/velero/app`: pass.
- `kubectl kustomize kubernetes/apps`: pass.
- `yamllint` across all changed manifests with only line-length disabled for schema URLs: pass.
- Helm `4.2.3` and kubeconform `0.8.0` scratch downloads: published SHA-256 checks passed.
- app-template `5.0.1` render using the exact HelmRelease values: pass; generated ServiceAccount, two retained PVCs, Service, and Deployment were inspected.
- Docker manifest inspection confirmed `rommapp/romm:4.9.2` includes `linux/amd64` and resolves to the tagged release commit `3e629ba6998ac8badf6cadd71ae8b46c9c85b17f`.
- Published-image smoke as UID/GID 1000 with all capabilities dropped and no privilege escalation: ROMM 4.9.2 initialized, accepted the read-only Git-managed config, honored external Redis, and reached PostgreSQL migrations. Exit 1 was expected because the disposable test deliberately pointed PostgreSQL at an absent loopback endpoint. A prior `/app`-path test was discarded because that source-build layout is not the published release-image layout.
- Live read-only Lyris check: `sean` is UID/GID 1000 and all known game-library directories are mode `0777`. The Ansible share item sets the export root to `1000:1000/0775`; with `fsGroupChangePolicy: OnRootMismatch`, Kubernetes can avoid a recursive ownership walk through the 355 GiB library.
- Strict kubeconform with core and CRD-catalog schemas after `SECRET_DOMAIN=example.com` substitution: 8/8 ROMM app resources valid, 1/1 Flux Kustomization valid, and 1/1 Velero Schedule valid.
- `git diff --check`: pass.
- Kubernetes server-side admission dry-run: unavailable from the gateway's intentional read-only kubeconfig. The `mimir-readonly` service account has no create permission. The repaired homelab hook allows explicit client/server dry-runs, but Mimir did not bypass the read-only identity with admin credentials.

Ansible checks in `/home/sean/workspace/endsys-ansible-romm`:

- `ansible-playbook -i inventory/hosts.yml playbooks/nas.yml --syntax-check --check`: pass.
- `yamllint inventory/host_vars/lyris/nas.yml`: pass.
- `ansible-lint playbooks/nas.yml roles/nas`: pass with zero failures and warnings.
- Local exports template render: pass, including `/vault/games    10.127.0.0/24(rw,sync,no_subtree_check,root_squash)`.
- Direct SSH and Ansible become preflight through `momo` with `/home/sean/.ssh/momo`: pass; `ping: pong` and passwordless become returned UID `0`.
- Live NFS check mode with the explicit Momo key: pass; `changed=2`, `unreachable=0`, `failed=0`. The only predicted changes are `/vault/games` root metadata (`0:0/0777` to `1000:1000/0775`) and the intended export line.
- Approved NFS apply reported `ok=32 changed=3 unreachable=0 failed=0`; the third change is the export reload handler. Backup: `/etc/exports.pre-romm-20260715T073321-0400`.
- Post-apply verification: live export is RW with `root_squash`; `/vault/games` is `1000:1000/0775`; a UID/GID 1000 create/delete NFS probe passed; no probe mounts/files remained; ZFS is healthy; idempotency check passed with `changed=0 failed=0`.

NFS live state changed only as recorded above. No Kubernetes or Flux live state has been changed. Ahead-only feature branches were pushed; no merge was performed.

## Bitwarden secret rollout

- Scratch CLI: official BWS `2.1.0`; the x86-64 GNU/Linux archive passed its published SHA-256 checksum.
- Existing `bitwarden-secretsmanager` ClusterSecretStore is Ready, has a project ID, and references `external-secrets/bitwarden-access-token` key `token`.
- With explicit approval, the cluster-held token was loaded only into process memory. Project lookup passed and the pre-create count for `romm-auth-secret-key` was `0`.
- `bws secret create ... --output none` failed with `404 Resource not found`; a post-error count confirmed the key remains absent (`0`). Sensitive variables were removed by the shell exit trap, and no value was printed or written to disk.
- Classification: the machine account has read-only project access. The error exactly matches Bitwarden SDK issue [#1287](https://github.com/bitwarden/sdk-sm/issues/1287), which documents this misleading `404` when create permission is missing.
- Sean created `romm-auth-secret-key` manually in the `endsys-gitops` project. The value was never sent through chat or read back by Mimir.
- Value-free BWS verification passed: the matching-key count is exactly `1`.

## Readiness revalidation — 2026-07-15

- Opened [shelmus/endsys-gitops#287](https://github.com/shelmus/endsys-gitops/pull/287) (`feat/romm` → `main`). PR creation was explicitly approved; merge and deployment were not.
- Branch is clean, synchronized with its remote, and not behind `origin/main`.
- Ansible syntax/lint/YAML validation and both repo diff checks passed.
- Kustomize renders passed for the ROMM app/namespace, Velero app, and root apps tree. Client dry-run creation passed for the namespace bundle, eight-resource app bundle, Velero Schedule, app-template output, and Dragonfly output.
- Strict Kubernetes 1.34/CRD schemas passed: ROMM app 8/8, Flux Kustomization 1/1, Velero Schedule 1/1, app-template output 5/5, and Dragonfly output 3/3.
- Checksum-verified Helm 4.2.3 pulled and rendered app-template 5.0.1 and Dragonfly v1.39.0 from their live OCI sources. `rommapp/romm:4.9.2` remains available for `linux/amd64`.
- All three Kubernetes nodes and every declared Flux dependency are Ready. The internal Gateway is programmed at `10.127.0.51`; the Bitwarden ClusterSecretStore is Ready.
- Longhorn is the default StorageClass; all three disks are schedulable with 619–755 GiB currently available, well above the 42 GiB requested by ROMM/CNPG/Dragonfly.
- Lyris answers NFSv4 RPC, `nfs-server` is active, and ZFS pool `vault` is ONLINE with zero known data errors.
- `pihole-dns` is Ready with no recent error/timeout log lines. Existing internal routes resolve to the internal Gateway; the ROMM record is expected only after its HTTPRoute exists.
- Velero controller logs repeatedly mark backup location `default` available; all three node agents are Ready.
- Post-merge checks remain: ExternalSecret sync, PV/PVC binding, in-pod UID/GID 1000 NFS write probe, CNPG/Dragonfly readiness, ROMM migrations and `/api/heartbeat`, HTTPRoute/DNS/TLS, a small platform scan, and proof from a real backup that volume `library` is excluded.

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
- [ ] NFS applied and verified
- [ ] Secret created and verified
- [ ] GitOps deployed and live health verified

## Approval gates still closed

- Bitwarden secret creation
- Lyris NFS apply
- Kubernetes server-side dry-run (blocked by the homelab gate)
- Pull request creation / merge
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
- Kubernetes server-side dry-run: not run; the homelab gate blocked the exact `kubectl apply --dry-run=server` commands and explicitly prohibited retrying or working around the block.

Ansible checks in `/home/sean/workspace/endsys-ansible-romm`:

- `ansible-playbook -i inventory/hosts.yml playbooks/nas.yml --syntax-check --check`: pass.
- `yamllint inventory/host_vars/lyris/nas.yml`: pass.
- `ansible-lint playbooks/nas.yml roles/nas`: pass with zero failures and warnings.
- Local exports template render: pass, including `/vault/games    10.127.0.0/24(rw,sync,no_subtree_check,root_squash)`.
- Live check mode: blocked by authentication/privilege prerequisites (`momo` key rejected; `docker_ops` has no passwordless sudo).

No NFS, Kubernetes, Bitwarden, GitHub, or Flux live state has been changed.

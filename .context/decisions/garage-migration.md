# Replace SeaweedFS with Garage

## Context

The cluster uses SeaweedFS as an S3-compatible backup target for Velero, backed by NFS at `10.127.0.5:/data/seaweedfs`. Today the namespace kustomization at `kubernetes/apps/seaweedfs/kustomization.yaml` has `resources: []`, so Flux is not reconciling SeaweedFS — Velero's S3 backup location is effectively offline.

The user has decided to switch the backup target to **Garage** (Deuxfleurs S3-compatible object store). Goals:

- Stand up Garage as the new in-cluster S3 service
- Repoint Velero at Garage; rebuild backups fresh on the existing daily schedule
- Remove SeaweedFS from the repo and `.context/` docs
- Migrate the Velero S3 credentials secret from SOPS to ExternalSecret/Bitwarden in the same change (closes part of TD-006/TD-011)

Historical Velero backups are intentionally **discarded** (per user). The cluster will re-establish its 30-day backup window from the next nightly run.

## Approach

### Garage chart sourcing

Garage publishes its Helm chart only from its source repo (no Helm registry). Use a Flux `GitRepository` source pinned to a tag, and have the HelmRelease pull the chart from `./script/helm/garage` inside that repo.

### Topology

- Single-replica StatefulSet (`replicaCount: 1`, `replicationMode: "1"`) — matches existing single-instance home cluster pattern (TD-003 territory; not in scope here).
- **Metadata** PVC: 10Gi on Longhorn (LMDB needs proper file locking; NFS is a poor fit).
- **Data** PVC: 1Ti on NFS at `10.127.0.7:/vault/k8s` (new NAS) — manually provisioned PV with `claimRef` pointing at `garage/data-garage-0`.
- Internal-only service. No HTTPRoute (Velero hits it cluster-internal at `garage-s3.garage.svc:3900`).
- Let the chart auto-generate `rpc_secret` and `admin_token` into chart-managed Secret objects — single-node rebuild can regenerate freely. Only the Velero S3 access key/secret key need to be persisted to Bitwarden.

## Files to Create

### Flux source for chart

- `kubernetes/flux/meta/repos/garage.yaml` — `GitRepository` pointed at `https://git.deuxfleurs.fr/Deuxfleurs/garage`, `ref.tag: v1.3.1` (chart 0.7.3 / appVersion v1.3.1), `ignore` rule restricting to `script/helm/garage`.
- Edit `kubernetes/flux/meta/repos/kustomization.yaml` — add `./garage.yaml`, remove `./seaweedfs.yaml`.

### Garage app

Standard app structure per `.context/architecture/app-structure.md`:

- `kubernetes/apps/garage/kustomization.yaml` — namespace `garage`, common component, `./garage/ks.yaml`.
- `kubernetes/apps/garage/garage/ks.yaml` — Flux Kustomization. `dependsOn`: `external-secrets-stores`, `csi-driver-nfs`, `longhorn` (whichever is the canonical longhorn ks name — verify against `kubernetes/apps/longhorn-system/longhorn-system/ks.yaml`).
- `kubernetes/apps/garage/garage/app/kustomization.yaml` — lists `helmrelease.yaml`, `storage-pv.yaml`, `externalsecret.yaml`.
- `kubernetes/apps/garage/garage/app/helmrelease.yaml` — references the GitRepository source; key values:
  - `garage.replicationMode: "1"`
  - `deployment.replicaCount: 1`
  - `persistence.meta.storageClass: longhorn`, `size: 10Gi`
  - `persistence.data.existingClaim: garage-data` (using the NFS PVC below)
  - `monitoring.metrics.enabled: true`, `serviceMonitor.enabled: true` (kube-prometheus-stack picks it up)
  - `service.s3.api.port: 3900`
- `kubernetes/apps/garage/garage/app/storage-pv.yaml` — manual `PersistentVolume` named `garage-data-pv` with `claimRef` → `garage/data-garage-0`, NFS at `10.127.0.7:/vault/k8s`, 1Ti, `ReadWriteOnce`, `storageClassName: ""`.
- `kubernetes/apps/garage/garage/app/externalsecret.yaml` — `external-secrets.io/v1` ExternalSecret materializing `velero-s3-credentials` in the **velero** namespace (or use a `PushSecret` / cross-namespace pattern). Cleaner: keep the secret in `velero` namespace, define ExternalSecret there (see Velero changes below).

### Bitwarden entries to create (manual, before merge)

- `velero-s3-access-key` — populated post-bootstrap with the `garage key create` output
- `velero-s3-secret-key` — populated post-bootstrap with the `garage key create` output

A `cloud` style INI-format AWS credentials blob is also needed by Velero — derive it via templating in the ExternalSecret using the two key fields above.

## Files to Modify

### Velero

- `kubernetes/apps/velero/velero/app/helmrelease.yaml`:
  - line 17–19: change `dependsOn.name` from `seaweedfs` (namespace `seaweedfs`) to `garage` (namespace `garage`).
  - line 37: change `s3Url: http://seaweedfs-s3.seaweedfs.svc:8333` to `s3Url: http://garage-s3.garage.svc:3900`.
- Replace `kubernetes/apps/velero/velero/app/secret.sops.yaml` with `kubernetes/apps/velero/velero/app/externalsecret.yaml`. Reference Bitwarden keys above; render `accessKey`, `secretKey`, and `cloud` (AWS-credentials INI templated from the two keys) via ExternalSecret `dataFrom` + `template`.
- Update `kubernetes/apps/velero/velero/app/kustomization.yaml` — swap `secret.sops.yaml` → `externalsecret.yaml`.

## Files to Delete

- `kubernetes/apps/seaweedfs/` (entire directory, including `seaweedfs/ks.yaml`, `seaweedfs/app/*`, `kustomization.yaml`)
- `kubernetes/flux/meta/repos/seaweedfs.yaml`

## Documentation Updates

- `CLAUDE.md` — stack line: replace `SeaweedFS` with `Garage`.
- `.context/substrate.md:37` — same.
- `.context/architecture/overview.md` — sections "Storage Architecture" (line 132–146), "Helm Repositories" (line 147–168), and the apps table at line 78. Replace SeaweedFS row with Garage.
- `.context/backup-restore.md` — top-level diagram (line 6–13), Components table (line 17–22), troubleshooting (line 345–356), full-cluster recovery section (line 280–292), Storage Considerations table (line 333–341). Replace SeaweedFS references with Garage; update NFS path note from `/data/seaweedfs` to `/data/garage`.
- `.context/debt.md` — remove `kubernetes/apps/seaweedfs/seaweedfs/app/secret.sops.yaml` from TD-011 (line 144), update TD-006 if velero SOPS removal completes the bullet (line 80).
- `/Users/sean/.claude/projects/-Users-sean-Documents-workspace-endsys-gitops/memory/project_architecture.md` — update if it names SeaweedFS as the backup target.

## Bootstrap Sequence (post-merge, manual)

These are one-time CLI steps. Garage needs a layout assigned before it serves traffic, and the access keys for Velero must be generated and shipped to Bitwarden.

```bash
# 1. Wait for garage-0 to be Running
kubectl -n garage rollout status statefulset/garage

# 2. Inspect node and capture its node ID
kubectl -n garage exec garage-0 -- /garage status

# 3. Assign layout (single zone, 1Ti capacity, replace <node-id>)
kubectl -n garage exec garage-0 -- /garage layout assign -z dc1 -c 1T <node-id>
kubectl -n garage exec garage-0 -- /garage layout apply --version 1

# 4. Create Velero bucket and access key
kubectl -n garage exec garage-0 -- /garage bucket create velero
kubectl -n garage exec garage-0 -- /garage key create velero-key
kubectl -n garage exec garage-0 -- /garage bucket allow --read --write --owner velero --key velero-key

# 5. Capture the printed Key ID and Secret Key. Store in Bitwarden as
#    velero-s3-access-key and velero-s3-secret-key.

# 6. Trigger ExternalSecret refresh
kubectl -n velero annotate externalsecret velero-s3-credentials force-sync=$(date +%s) --overwrite

# 7. Restart velero so it picks up the new credentials
kubectl -n velero rollout restart deployment/velero
```

## Verification

```bash
# Flux reconciliation
flux get kustomizations garage
flux get helmrelease -n garage garage

# Garage healthy
kubectl -n garage get pods
kubectl -n garage exec garage-0 -- /garage status

# Velero sees the new backup location as Available
velero backup-location get

# Smoke-test a backup against the new target
velero backup create garage-smoke-$(date +%Y%m%d) \
  --include-namespaces gatus \
  --default-volumes-to-fs-backup \
  --ttl 24h
velero backup describe garage-smoke-<date>      # Phase: Completed

# Confirm objects landed in the velero bucket
kubectl -n garage exec garage-0 -- /garage bucket info velero

# Confirm SeaweedFS is fully gone
kubectl get ns seaweedfs                         # NotFound
flux get kustomizations | grep -i seaweed        # empty
```

## Risk / Rollback

- **Risk**: chart pulled from a Forgejo (`git.deuxfleurs.fr`) instance — if that host is down at reconcile time, Flux can't fetch the chart. Mitigation: pin to a tag, accept transient unavailability (chart only re-fetched on interval).
- **Risk**: NFS-backed `/vault/k8s` doesn't exist on the new NAS (10.127.0.7) yet — must be created (`mkdir`) before HelmRelease comes up, otherwise the PVC will Bind but writes will fail.
- **Rollback**: revert the merge commit. Velero will go back to depending on SeaweedFS, which is also broken — there is no working pre-state to roll back to. The forward path is to fix the layout/key bootstrap step rather than revert.

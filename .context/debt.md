# Technical Debt Registry

Known technical debt and areas requiring attention.

## High Priority

### 2. Pricebuddy Using `latest` Image Tag

**Location**: `kubernetes/apps/pricebuddy/pricebuddy/app/deployment.yaml:40`

**Issue**:
```yaml
image: jez500/pricebuddy:latest
```

**Risk**:
- Non-reproducible deployments
- Silent breaking changes
- No rollback capability

**Recommended Fix**: Pin to specific version tag when available.

> **Note**: Pelican previously had this same issue — resolved by pinning to a release tag (currently `v1.0.0-beta38`, matched to Wings `v1.0.0-beta29`).

---

## Medium Priority

### 3. Single-Instance CNPG Clusters

**Location**: All CNPG Cluster CRs

**Issue**: All database clusters use `instances: 1`

**Risk**:
- No high availability
- Downtime during maintenance
- Single point of failure

**Recommended Fix**: Increase to 2-3 instances for production workloads.

---

### 4. Limited Velero Backup Schedules — Partial

**Status**: Partial. The earlier schedules covered n8n, immich, gatus, obsidian-livesync and pocket-id. coder, hindsight and larder were added on 2026-09-28.

**Remaining**: `taxsale-monitor` runs as a CronJob. File-system backup only captures volumes mounted by running pods, so its SQLite volume is not backed up. Either accept that the data can be regenerated, or move to CSI snapshot backups.

---

### 13. CNPG Clusters Without WAL Archiving

**Location**: All 7 CNPG `Cluster` CRs (coder, hindsight, immich, larder, matrix-mas, matrix-synapse, romm)

**Issue**: No `spec.plugins`, no `ScheduledBackup`, and no WAL archiving. Velero copies `pgdata` while Postgres is live.

**Risk**: No point-in-time recovery. A restore depends on an inconsistent daily file copy.

**Recommended Fix**: Barman Cloud plugin (`plugin-barman-cloud`) with one Garage bucket and key per cluster. Pilot on larder, then roll out one cluster per change, running a restore test for each.

---

### 14. Garage Metadata Not Protected

**Location**: `kubernetes/apps/garage/garage/app/helmrelease.yaml`

**Issue**: Garage's LMDB metadata is on the Longhorn PVC `meta-garage-0`, and `metadataAutoSnapshotInterval` is unset.

**Risk**: If the cluster or Longhorn is lost, the Velero data on NFS can't be read.

**Recommended Fix**: Enable `metadata_auto_snapshot_interval`, with `metadata_snapshots_dir` on an NFS volume on Lyris.

---

### 16. PriceBuddy MySQL Hook Does Not Hold the Lock

**Location**: `kubernetes/apps/velero/velero/app/schedules/pricebuddy-schedule.yaml`

**Issue**: The pre-hook runs `FLUSH TABLES WITH READ LOCK; SELECT SLEEP(5)` in the background and exits after `sleep 2`. The lock is released before Velero copies the volume, and a read lock doesn't make InnoDB's files consistent on disk anyway.

**Recommended Fix**: Run `mysqldump --single-transaction` into a backed-up path as the pre-hook, and back up the dump.

---

### 5. Manual PV Provisioning for Immich

**Location**: `kubernetes/apps/immich/immich/app/library-pv.yaml`

**Issue**: Immich library uses manually provisioned PV with `storageClassName: ""`.

**Risk**:
- No dynamic provisioning
- Manual intervention required for scaling
- PV deletion requires manual cleanup

**Recommended Fix**: Consider using CSI-provisioned storage or document manual process.

---

## Low Priority

### 6. ~~Velero SOPS Secret~~ — Resolved

**Status**: Resolved — `velero-s3-credentials` migrated to ExternalSecret/Bitwarden during the SeaweedFS→Garage migration.

---

### 7. n8n HTTPRoute Commented Out

**Location**: `kubernetes/apps/n8n/n8n/app/helmrelease.yaml:32-56`

**Issue**: Ingress configuration is commented out; app not publicly accessible.

**Recommended Fix**: Configure HTTPRoute or document as intentional.

---

### 8. Pricebuddy Init Container Workaround

**Location**: `kubernetes/apps/pricebuddy/pricebuddy/app/deployment.yaml`

**Issue**: Uses init container to wait for database:
```yaml
command: ['sh', '-c', 'until nc -z pricebuddy-database 3306; do sleep 1; done']
```

**Risk**: Manual ordering instead of proper dependency management.

**Recommended Fix**: Consider using CNPG with proper startup probes.

---

### 10. ~~VolSync Not Consistently Deployed~~ — Superseded

**Status**: Superseded by Velero. Its only user, otterwiki, is disabled. Remove VolSync when otterwiki is retired.

**Location**: Only `kubernetes/apps/default/otterwiki/app/volsync-backup.yaml`

**Issue**: VolSync backup only configured for otterwiki, not other stateful apps.

**Risk**:
- Immich library not replicated (relies on NFS)
- Pricebuddy data not backed up via VolSync
- No consistent backup strategy across apps

**Recommended Fix**: Add VolSync ReplicationSource for all stateful PVCs.

---

### 12. Firecrawl: Upstream Chart Limitations

**Location**: `kubernetes/apps/firecrawl/firecrawl/app/helmrelease.yaml`

**Issues** (all deliberate trade-offs from the design spec at `docs/superpowers/specs/2026-05-22-firecrawl-deployment-design.md`):

| Item | Convention violated | Why accepted |
|---|---|---|
| Bundled `nuq-postgres` (custom Postgres image) | "Use CNPG Cluster CRs" | Chart has no toggle to disable; tightly coupled. NUQ holds transient queue state, not user data. |
| Bundled Redis (instead of Dragonfly) | "Prefer Dragonfly over Redis" | Chart has no `.enabled` toggle for Redis; always deploys. Cache is transient. |
| Bundled RabbitMQ | No precedent (no other RabbitMQ in repo) | No in-repo message broker; over-engineering for a single consumer. Queue state is transient. |
| Image tag references `latest` (pinned by SHA digest) | "Never use `latest` tags" | winkkgmbh publishes only `:latest` for `firecrawl-playwright`, `nuq-postgres`. Pinned by SHA digest so the deployment is still immutable. (Firecrawl `:0.2.0` exists but is the Helm chart artifact, not a container image.) |
| `nuq-postgres` persistence disabled (emptyDir) | (data loss on pod restart) | Chart mounts PVC directly at `/var/lib/postgresql/data`; initdb refuses to start with `lost+found` present, and the chart has no `PGDATA` env override. NUQ state is transient. |

**Recommended fix paths** (if Firecrawl becomes load-bearing):
- Fork the chart to add `extraEnv` support (would fix the PGDATA issue and enable using a CNPG cluster).
- Or migrate piece-by-piece off the bundled deps via `postRenderers` Kustomize patches.

---

### 11. SOPS Secrets Still Widely Used

**Location**: 11 files across the cluster

**Files**:
- `kubernetes/components/common/sops/cluster-secrets.sops.yaml` (intentional - cluster vars)
- `kubernetes/components/common/sops/sops-age.sops.yaml` (intentional - encryption key)
- `kubernetes/apps/flux-system/flux-instance/app/secret.sops.yaml`
- `kubernetes/apps/cert-manager/cert-manager/app/secret.sops.yaml`
- `kubernetes/apps/network/cloudflare-dns/app/secret.sops.yaml`
- `kubernetes/apps/network/cloudflare-tunnel/app/secret.sops.yaml`
- `kubernetes/apps/network/pihole-dns/app/secret.sops.yaml`
- `kubernetes/apps/longhorn-system/longhorn-system/app/secret.sops.yaml`
- `kubernetes/apps/pricebuddy/pricebuddy/app/secret.sops.yaml`
- `kubernetes/apps/default/otterwiki/app/secret.sops.yaml`
- `kubernetes/apps/external-secrets/external-secrets/stores/secret.sops.yaml`

**Note**: Some SOPS usage is intentional (cluster-secrets for variable substitution).
Migration to External Secrets should focus on app-specific secrets, not cluster-wide vars.

---

## Tracking

| ID | Issue | Priority | Status |
|----|-------|----------|--------|
| TD-002 | Pricebuddy latest tag (Pelican resolved) | High | Partial |
| TD-003 | Single-instance CNPG | Medium | Open |
| TD-004 | Limited Velero schedules (taxsale-monitor remaining) | Medium | Partial |
| TD-005 | Manual Immich PV | Medium | Open |
| TD-006 | Velero SOPS secret | Low | **Resolved** |
| TD-007 | n8n HTTPRoute missing | Low | Open |
| TD-008 | Pricebuddy init workaround | Low | Open |
| TD-010 | VolSync not consistent | Medium | Superseded |
| TD-011 | SOPS still widely used | Low | Open |
| TD-012 | Firecrawl chart limitations (bundled deps, image tags, no Postgres persistence) | Low | Open |
| TD-013 | CNPG without WAL archiving | High | Open |
| TD-014 | Garage metadata unprotected | High | Open |
| TD-016 | PriceBuddy MySQL hook ineffective | Medium | Open |

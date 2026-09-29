# CNPG Backup Standard

**Rule: no PostgreSQL database is "done" until it has continuous backups, an alert, and one recorded restore.**

This applies to every CloudNativePG `Cluster` in this repo, new or existing. `scripts/cnpg-backup-scaffold.py --audit` shows which clusters meet it.

Pilot and reference implementation: `larder-postgres` (PR #372, drilled 2026-09-29).

## What every cluster gets

| Piece | Where | Value |
|---|---|---|
| Garage bucket | Garage | `cnpg-<base>` (one bucket per cluster) |
| Read-write key | Garage | `cnpg-<base>-rw`: read+write on that bucket only, cannot create buckets |
| Read-only key | Garage | `cnpg-<base>-ro`: read on that bucket only, used only by restore drills |
| Bitwarden entries | Secrets Manager, endsys-gitops project | `<base>-cnpg-s3-access-key`, `<base>-cnpg-s3-secret-key`, `<base>-cnpg-s3-ro-access-key`, `<base>-cnpg-s3-ro-secret-key` |
| ExternalSecret | app dir, `cnpg-backup-<cluster>.yaml` | `<base>-cnpg-s3` → `ACCESS_KEY_ID`, `ACCESS_SECRET_KEY`, `REGION=garage` |
| ObjectStore | same file | `<base>-objectstore` → `s3://cnpg-<base>/`, `retentionPolicy: "30d"`, gzip WAL and data, S3-compat checksum env |
| Cluster | `postgres-cluster.yaml` | `spec.plugins`: `barman-cloud.cloudnative-pg.io`, `isWALArchiver: true`, `barmanObjectName: <base>-objectstore` |
| ScheduledBackup | same file as ObjectStore | `<cluster>-daily`, `method: plugin`, daily, next free 5-minute slot from 03:15 UTC |
| Flux dependsOn | app `ks.yaml` | `plugin-barman-cloud` (cnpg-system) and `external-secrets-stores` (external-secrets) |
| Alerts | `prometheusrule-backups.yaml` (shared, nothing per cluster) | `CNPGWALArchivingFailing`, `CNPGBaseBackupFailed`, `CNPGNoRecentBaseBackup` |
| Metrics | `podmonitor-cnpg.yaml` (shared, nothing per cluster) | scrapes every CNPG instance, including the plugin's `barman_cloud_cloudnative_pg_io_*` series |

`<base>` is the cluster name without `-postgres`: `matrix-synapse-postgres` → `matrix-synapse`. Cluster names must follow `<app>-postgres`.

Why one key pair per cluster: a leaked key, or a compromised app namespace, can only read or delete that one app's backups, not Velero's or another database's.

## Onboarding a cluster (new or existing)

1. **Keys (Sean, in his own terminal).** `scripts/cnpg-backup-keys.sh <cluster>` creates the bucket and both keys and prints the four values once. Put them into Bitwarden under the printed names, then clear the terminal scrollback. The script is idempotent: existing buckets and keys are skipped and their secrets are never shown again. Run it without arguments to cover every cluster; use `--dry-run` to preview.
   Never run this script through an AI agent: the secret keys must not pass through chat or logs.
2. **Verify Bitwarden = Garage** (optional but recommended). Compare hashes, never values: a temporary ExternalSecret that templates only `sha256sum` and `len` of each Bitwarden value, against `garage key info <key> --show-secret` hashed in a pipe. Delete the ExternalSecret afterwards.
3. **Manifests.** `scripts/cnpg-backup-scaffold.py <cluster>` writes `cnpg-backup-<cluster>.yaml`, adds it to `kustomization.yaml`, adds `spec.plugins` to the Cluster and the `dependsOn` entries to `ks.yaml`. It refuses to run twice. For a brand-new app, write `postgres-cluster.yaml` first, then run the scaffold in the same PR.
4. **Before merging an existing cluster:** take a `pg_dump -Fc` to `~/backups/pg/` (mode 600) and check it with `pg_restore -l`. Adding `spec.plugins` **restarts the single instance once**, so merge at a quiet time.
5. **Merge, then take the first backup by hand.** For an existing cluster, the ScheduledBackup's `immediate: true` fires before the restarted pod has the plugin sidecar and fails with `requested plugin is not available`. Once the pod is Ready with the `plugin-barman-cloud` sidecar, create a manual backup:
   ```yaml
   apiVersion: postgresql.cnpg.io/v1
   kind: Backup
   metadata:
     name: <cluster>-first-<yyyymmdd>
     namespace: <ns>
   spec:
     cluster:
       name: <cluster>
     method: plugin
     pluginConfiguration:
       name: barman-cloud.cloudnative-pg.io
   ```
   A brand-new cluster created with `spec.plugins` from the start does not hit this.
6. **Verify** (all must hold):
   - `kubectl -n <ns> get backups.postgresql.cnpg.io`: the newest is `completed`;
   - the Cluster condition `ContinuousArchiving=True`;
   - `select archived_count, failed_count from pg_stat_archiver` on the primary: archived is rising and failed is not;
   - the ObjectStore `status.serverRecoveryWindow.<cluster>.firstRecoverabilityPoint` is set;
   - `garage bucket info cnpg-<base>` shows objects > 0.
7. **Restore drill.** `scripts/cnpg-restore-drill.py <ns> <cluster>` restores the newest backup into `<cluster>-restore-test` with the read-only key, with `archive_mode` off and no plugin, so it cannot write to the bucket. It compares the table list and per-table row counts with production, then deletes the namespace. Record the result (date, recovery point, tables/rows, time to healthy) in the backup plan note and the database's section below.
8. **Only after a passing drill:** exclude that cluster's `pgdata` from Velero (plan step 2f), so Velero stops taking inconsistent live copies.

## Restoring for real

Use the same recovery `bootstrap` as the drill script, pointed at the real namespace. With the app's Flux Kustomization suspended, delete the broken Cluster, then apply a Cluster with `bootstrap.recovery` + `externalClusters.plugin` (serverName = the original cluster name). For point-in-time recovery add `recoveryTarget.targetTime`.

The recovered cluster must write to a **new** `serverName` (or a new bucket path) once it resumes archiving, so it never overwrites the history it recovered from. Resume Flux only after the Git manifest matches.

## Alerts (already live, shared by all clusters)

| Alert | Fires when |
|---|---|
| `CNPGWALArchivingFailing` (critical) | the newest WAL archive attempt failed and nothing has archived since, for 15 m |
| `CNPGBaseBackupFailed` (critical) | the last failed base backup is newer than the last success, for 15 m |
| `CNPGNoRecentBaseBackup` (warning) | the newest base backup is older than 26 h, for 1 h |

Base-backup age uses `barman_cloud_cloudnative_pg_io_last_available_backup_timestamp`. `cnpg_collector_last_available_backup_timestamp` stays 0 for plugin-method backups.

## Status

| Cluster | Keys | Manifests | First backup | Drill |
|---|---|---|---|---|
| larder-postgres | yes | #372 | 2026-09-29 18:50 UTC | 2026-09-29: 20/20 tables, rows identical, healthy in 75-90 s |
| immich-postgres | — | — | — | — |
| romm-postgres | — | — | — | — |
| matrix-synapse-postgres | — | — | — | — |
| matrix-mas-postgres | — | — | — | — |
| hindsight-postgres | — | — | — | — |
| coder-postgres | — | — | — | — |

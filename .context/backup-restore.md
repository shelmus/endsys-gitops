# Backup and Restore

How backups work in this cluster and how to restore an application on a fresh cluster.

## Backup Architecture

```
Velero (with Kopia/Restic)
  -> Filesystem backup of PVCs + Kubernetes resources
  -> S3 API
  -> SeaweedFS (in-cluster S3)
  -> NFS (10.127.0.5:/data/seaweedfs)
```

**Components**:

| Component | Role | Location |
|-----------|------|----------|
| Velero | Backup orchestrator | `kubernetes/apps/velero/velero/` |
| SeaweedFS | S3-compatible backup target | `kubernetes/apps/seaweedfs/seaweedfs/` |
| Kopia/Restic | Filesystem-level PVC backup | Deployed as Velero node-agent |
| Snapshot Controller | VolumeSnapshot CRDs | `kubernetes/apps/kube-system/snapshot-controller/` |

### What Velero Backs Up

For each scheduled namespace, Velero captures:

1. **All Kubernetes resources** in the namespace (Deployments, Services, ConfigMaps, PVCs, etc.)
2. **PVC data** via filesystem backup (`defaultVolumesToFsBackup: true`)
3. **Cluster-scoped resources** owned by namespace resources (PVs, ClusterRoleBindings, etc.)

### Backup Schedules

Schedules live in `kubernetes/apps/velero/velero/app/schedules/` and are referenced from the Velero kustomization.

Current schedules:

| Schedule | Namespace | Cron | Retention |
|----------|-----------|------|-----------|
| `pricebuddy-daily` | pricebuddy | `0 2 * * *` (2 AM UTC) | 30 days |
| `n8n-daily` | n8n | `0 2 * * *` (2 AM UTC) | 30 days |
| `immich-daily` | immich | `0 2 * * *` (2 AM UTC) | 30 days |
| `gatus-daily` | gatus | `0 2 * * *` (2 AM UTC) | 30 days |
| `obsidian-livesync-daily` | obsidian-livesync | `0 2 * * *` (2 AM UTC) | 30 days |
| `pocket-id-daily` | pocket-id | `0 2 * * *` (2 AM UTC) | 30 days |

## Adding a Backup Schedule

### Simple App (No Database Hooks)

Create a schedule file in `kubernetes/apps/velero/velero/app/schedules/`:

```yaml
---
apiVersion: velero.io/v1
kind: Schedule
metadata:
  name: pelican-daily
  namespace: velero
  labels:
    app.kubernetes.io/name: velero
    app.kubernetes.io/component: backup-schedule
    app.kubernetes.io/part-of: pelican
spec:
  schedule: "0 2 * * *"
  template:
    includedNamespaces:
      - pelican
    includedResources:
      - '*'
    defaultVolumesToFsBackup: true
    storageLocation: default
    ttl: 720h0m0s
    includeClusterResources: true
    metadata:
      labels:
        app.kubernetes.io/name: pelican
        backup-type: scheduled
  useOwnerReferencesInBackup: false
```

Then add it to `kubernetes/apps/velero/velero/app/kustomization.yaml`:

```yaml
resources:
  - ./helmrelease.yaml
  - ./secret.sops.yaml
  - ./schedules/pricebuddy-schedule.yaml
  - ./schedules/pelican-schedule.yaml       # <-- add
```

### App with Database Hooks

If the app has an in-pod database (like pricebuddy's MySQL), add pre/post hooks to ensure consistency. See `schedules/pricebuddy-schedule.yaml` for a full example with `FLUSH TABLES WITH READ LOCK`.

Apps using CNPG do not need hooks — CNPG manages its own WAL-based consistency.

## Creating a Manual Backup

Before destructive operations or migrations, create a one-off backup:

```bash
# Backup a single namespace
velero backup create pelican-manual-$(date +%Y%m%d) \
  --include-namespaces pelican \
  --default-volumes-to-fs-backup \
  --include-cluster-resources=true \
  --ttl 720h

# Check backup status
velero backup describe pelican-manual-20260220

# List all backups
velero backup get
```

## Restoring an Application

### Scenario: Recovering Pelican on a Fresh Cluster

This walkthrough assumes:
- The cluster infrastructure is running (Flux, Cilium, storage, Velero, SeaweedFS)
- A Velero backup exists for the `pelican` namespace
- The backup target (SeaweedFS on NFS) survived or has been re-provisioned

#### Step 1: Verify Infrastructure is Ready

The Flux dependency chain must be satisfied before restoring app-level resources:

```bash
# Confirm Flux is reconciling
flux get kustomizations

# Confirm Velero is running and can see the backup location
velero backup-location get
# STATUS should be "Available"

# Confirm the backup exists
velero backup get | grep pelican
```

#### Step 2: Suspend Flux for the App

Prevent Flux from reconciling the app while you restore. If Flux tries to create resources at the same time as the restore, you'll get conflicts.

```bash
flux suspend kustomization pelican
```

If the app's Flux Kustomization doesn't exist yet (truly fresh cluster where Flux hasn't created it), you can skip this — but you should still prevent Flux from racing the restore by either:
- Temporarily removing the app's `ks.yaml` from the namespace kustomization, or
- Suspending the parent `cluster-apps` kustomization

#### Step 3: Restore from Backup

```bash
# Restore the namespace and all its resources
velero restore create pelican-restore \
  --from-backup pelican-daily-20260219020000 \
  --include-namespaces pelican \
  --restore-volumes=true

# Monitor restore progress
velero restore describe pelican-restore
velero restore logs pelican-restore
```

The restore recreates:
- The `pelican` namespace
- PVCs (`pelican-data`, `pelican-logs`) with their data
- The Deployment, Service, ConfigMap, HTTPRoute
- Any Secrets in the namespace

#### Step 4: Verify the Restore

```bash
# Check all resources are present
kubectl get all -n pelican

# Check PVCs are bound
kubectl get pvc -n pelican

# Check pods are running
kubectl get pods -n pelican

# Check logs for errors
kubectl logs -n pelican deployment/pelican-panel
```

#### Step 5: Resume Flux

Once the app is healthy, let Flux manage it again:

```bash
flux resume kustomization pelican
```

Flux will reconcile and adopt the restored resources. Since the Git manifests match what was restored, this should be a no-op.

### Scenario: CNPG Database Recovery (Immich Example)

CNPG databases are restored differently. The CNPG Cluster CR itself defines the bootstrap method.

#### Option A: Restore from Velero Backup (PVC Data)

If the Velero backup captured the CNPG PVC data:

1. Restore the namespace with Velero (same steps as above)
2. The CNPG operator will detect the existing PVC and adopt the data
3. Verify: `kubectl get cluster -n immich` shows the cluster healthy

#### Option B: Restore from CNPG Barman Backup (If Configured)

If CNPG is configured with `barmanObjectStore` backups, modify the Cluster CR to bootstrap from the backup:

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: immich-postgres
spec:
  instances: 1
  imageName: ghcr.io/tensorchord/cloudnative-vectorchord:16.9-0.4.3
  bootstrap:
    recovery:
      source: immich-postgres-backup
  externalClusters:
    - name: immich-postgres-backup
      barmanObjectStore:
        destinationPath: s3://backups/immich-postgres
        endpointURL: https://s3.example.com
        s3Credentials:
          accessKeyId:
            name: backup-creds
            key: access-key
          secretAccessKey:
            name: backup-creds
            key: secret-key
  storage:
    size: 20Gi
```

> **Note**: CNPG Barman backups are not currently configured. See `debt.md` TD-004.

#### Option C: pg_dump / pg_restore (Manual)

For manual recovery from a SQL dump:

```bash
# Take a dump from a running cluster (before disaster)
kubectl exec -n immich immich-postgres-1 -- \
  pg_dump -U immich -d immich -Fc > immich-backup.dump

# Restore into a fresh CNPG cluster (after bootstrap with initdb)
kubectl cp immich-backup.dump immich/immich-postgres-1:/tmp/
kubectl exec -n immich immich-postgres-1 -- \
  pg_restore -U immich -d immich --clean --if-exists /tmp/immich-backup.dump
```

## Full Cluster Recovery Sequence

If rebuilding the entire cluster from scratch:

### 1. Provision the Cluster

Bootstrap Talos Linux and install FluxCD. Flux will begin reconciling from Git.

### 2. Wait for Infrastructure

Flux reconciles in dependency order:

```
flux-system -> cluster-meta -> cluster-apps
  -> infrastructure (Cilium, cert-manager, CNPG operator, Longhorn, NFS CSI)
  -> configs (External Secrets stores)
  -> apps
```

### 3. Restore Backup Storage

SeaweedFS must be running and have access to the NFS path containing previous backups:

```bash
# Verify SeaweedFS is running
kubectl get pods -n seaweedfs

# Verify Velero can see the backup location
velero backup-location get
```

If the NFS server (`10.127.0.5`) retains the data under `/data/seaweedfs`, backups are automatically available once SeaweedFS starts.

### 4. Suspend and Restore Apps

For each stateful app with a backup:

```bash
# Suspend Flux for the app
flux suspend kustomization <app-name>

# Restore from the most recent backup
velero restore create <app-name>-restore \
  --from-backup <most-recent-backup-name> \
  --include-namespaces <namespace> \
  --restore-volumes=true

# Wait for restore to complete
velero restore describe <app-name>-restore

# Resume Flux
flux resume kustomization <app-name>
```

### 5. Verify Everything

```bash
# Check all Flux kustomizations are healthy
flux get kustomizations

# Check all pods are running
kubectl get pods -A | grep -v Running | grep -v Completed

# Check PVCs are bound
kubectl get pvc -A

# Check CNPG clusters (if applicable)
kubectl get cluster -A
```

## Storage Considerations

| Storage Type | Backup Method | Survives Cluster Rebuild? |
|--------------|---------------|---------------------------|
| NFS PVs (Immich library) | Data lives on NFS server | Yes, if NFS server is intact |
| Longhorn PVCs (PocketID) | Velero filesystem backup | No, must restore from backup |
| Default PVCs (Pelican, n8n) | Velero filesystem backup | No, must restore from backup |
| CNPG PVCs (Immich DB) | Velero or CNPG Barman | No, must restore from backup |
| SeaweedFS (backups themselves) | On NFS at `/data/seaweedfs` | Yes, if NFS server is intact |

The NFS server at `10.127.0.5` is the ultimate safety net. As long as it retains `/data/seaweedfs` (backup store) and `/data/photos` (Immich library), the most critical data survives a full cluster loss.

## Troubleshooting

### Velero Can't Find Backups

```bash
# Check backup storage location status
velero backup-location get

# If "Unavailable", check SeaweedFS
kubectl get pods -n seaweedfs
kubectl logs -n seaweedfs deployment/seaweedfs-master

# Check S3 credentials
kubectl get secret velero-s3-credentials -n velero
```

### Restore Stuck in "InProgress"

```bash
# Check restore logs for errors
velero restore logs <restore-name>

# Check node-agent (Restic/Kopia) pods
kubectl get pods -n velero -l name=node-agent
kubectl logs -n velero -l name=node-agent
```

### PVC Not Restored / Bound

```bash
# Check if PV was created by the restore
kubectl get pv | grep <pvc-name>

# If PV exists but PVC is Pending, check storage class
kubectl describe pvc <pvc-name> -n <namespace>
```

### Flux Conflicts After Restore

If Flux complains about resources already existing:

```bash
# Force Flux to adopt existing resources
flux reconcile kustomization <app-name> --force
```

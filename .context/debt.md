# Technical Debt Registry

Known technical debt and areas requiring attention.

## High Priority

### 1. Authentik Using Embedded Databases

**Location**: `kubernetes/apps/authentik/authentik/app/helmrelease.yaml`

**Issue**: Authentik bundles PostgreSQL and Redis as Helm subcharts instead of using CNPG and Dragonfly.

**Risk**:
- No automatic backups
- No high availability
- Inconsistent with cluster database strategy
- Comments in code acknowledge this: "For production, consider using an external database"

**Recommended Fix**:
1. Deploy CNPG Cluster for Authentik PostgreSQL
2. Deploy Dragonfly for Authentik Redis
3. Migrate data from embedded databases
4. Update HelmRelease to use external services

---

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

### 4. Limited Velero Backup Schedules

**Location**: `kubernetes/apps/velero/velero/app/schedules/`

**Issue**: Only `pricebuddy-schedule.yaml` exists.

**Risk**:
- Other apps not backed up on schedule
- Potential data loss

**Recommended Fix**: Add backup schedules for all stateful apps (immich, authentik, n8n).

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

### 6. SOPS Secrets Still Present (Deprecated)

**Location**: Various `secret.sops.yaml` files

**Issue**: Some SOPS-encrypted secrets remain despite migration to External Secrets.

**Files**:
- `kubernetes/apps/velero/velero/app/secret.sops.yaml`
- `kubernetes/apps/authentik/authentik/app/externalsecret.yaml` (references SOPS)

**Recommended Fix**: Complete migration to ExternalSecrets, remove SOPS files.

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

### 9. Authentik Blueprint Syntax (2025.x)

**Location**: `kubernetes/apps/authentik/authentik/app/blueprint-immich.yaml`

**Issue**: Blueprint syntax was outdated for Authentik 2025.x:
- `!Env [VAR]` → `!Env VAR`
- Missing `identifiers` fields
- Missing `invalidation_flow`
- `redirect_uris` as strings → objects

**Status**: Fixed 2026-02-04

**Documentation**: See [auth/oauth.md](auth/oauth.md) for correct patterns.

---

### 10. VolSync Not Consistently Deployed

**Location**: Only `kubernetes/apps/default/otterwiki/app/volsync-backup.yaml`

**Issue**: VolSync backup only configured for otterwiki, not other stateful apps.

**Risk**:
- Immich library not replicated (relies on NFS)
- Pricebuddy data not backed up via VolSync
- No consistent backup strategy across apps

**Recommended Fix**: Add VolSync ReplicationSource for all stateful PVCs.

---

### 11. SOPS Secrets Still Widely Used

**Location**: 13 files across the cluster

**Files**:
- `kubernetes/components/common/sops/cluster-secrets.sops.yaml` (intentional - cluster vars)
- `kubernetes/components/common/sops/sops-age.sops.yaml` (intentional - encryption key)
- `kubernetes/apps/flux-system/flux-instance/app/secret.sops.yaml`
- `kubernetes/apps/cert-manager/cert-manager/app/secret.sops.yaml`
- `kubernetes/apps/network/cloudflare-dns/app/secret.sops.yaml`
- `kubernetes/apps/network/cloudflare-tunnel/app/secret.sops.yaml`
- `kubernetes/apps/network/pihole-dns/app/secret.sops.yaml`
- `kubernetes/apps/longhorn-system/longhorn-system/app/secret.sops.yaml`
- `kubernetes/apps/seaweedfs/seaweedfs/app/secret.sops.yaml`
- `kubernetes/apps/velero/velero/app/secret.sops.yaml`
- `kubernetes/apps/pricebuddy/pricebuddy/app/secret.sops.yaml`
- `kubernetes/apps/default/otterwiki/app/secret.sops.yaml`
- `kubernetes/apps/external-secrets/external-secrets/stores/secret.sops.yaml`

**Note**: Some SOPS usage is intentional (cluster-secrets for variable substitution).
Migration to External Secrets should focus on app-specific secrets, not cluster-wide vars.

---

## Tracking

| ID | Issue | Priority | Status |
|----|-------|----------|--------|
| TD-001 | Authentik embedded DBs | High | Open |
| TD-002 | Pricebuddy latest tag | High | Open |
| TD-003 | Single-instance CNPG | Medium | Open |
| TD-004 | Limited Velero schedules | Medium | Open |
| TD-005 | Manual Immich PV | Medium | Open |
| TD-006 | SOPS migration incomplete | Low | In Progress |
| TD-007 | n8n HTTPRoute missing | Low | Open |
| TD-008 | Pricebuddy init workaround | Low | Open |
| TD-009 | Authentik blueprint syntax | High | **Fixed** |
| TD-010 | VolSync not consistent | Medium | Open |
| TD-011 | SOPS still widely used | Low | Open |

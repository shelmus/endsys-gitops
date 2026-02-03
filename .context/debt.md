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

## Tracking

| ID | Issue | Priority | Status |
|----|-------|----------|--------|
| TD-001 | Authentik embedded DBs | High | Open |
| TD-002 | Pricebuddy latest tag | High | Open |
| TD-003 | Single-instance CNPG | Medium | Open |
| TD-004 | Limited Velero schedules | Medium | Open |
| TD-005 | Manual Immich PV | Medium | Open |
| TD-006 | SOPS migration incomplete | Low | Open |
| TD-007 | n8n HTTPRoute missing | Low | Open |
| TD-008 | Pricebuddy init workaround | Low | Open |

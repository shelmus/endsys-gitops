# Architectural Decision Records

This directory contains key decisions made for the endsys-gitops infrastructure.

## Decision Log

| ID | Decision | Date | Status |
|----|----------|------|--------|
| ADR-001 | Use CloudNativePG over embedded databases | 2025-01 | Accepted |
| ADR-002 | Use Dragonfly instead of Redis | 2025-01 | Accepted |
| ADR-003 | Use Gateway API over Ingress | 2024 | Accepted |
| ADR-004 | Use External Secrets with Bitwarden | 2024 | Accepted |
| ADR-006 | Use PocketID for OIDC | 2026-02 | Accepted |

---

## ADR-001: CloudNativePG for PostgreSQL

**Context**: Applications needing PostgreSQL were using Helm subchart dependencies (Bitnami PostgreSQL), which bundled databases directly in app releases.

**Decision**: Migrate to CloudNativePG operator with dedicated Cluster CRs.

**Consequences**:
- (+) Proper backup/restore capabilities
- (+) Automated failover when scaled to multiple instances
- (+) Consistent database management across apps
- (+) Decoupled database lifecycle from application
- (-) Additional operator to maintain
- (-) Migration effort for existing apps

---

## ADR-002: Dragonfly over Redis

**Context**: Applications needing cache/session storage were deploying Redis instances.

**Decision**: Use Dragonfly as a Redis-compatible replacement.

**Consequences**:
- (+) 25x better performance
- (+) 80% less memory usage
- (+) Drop-in Redis protocol compatibility
- (+) Modern architecture with io_uring
- (-) Less ecosystem maturity than Redis

**Note**: Dragonfly requires tuning `--proactor_threads` on resource-constrained deployments.

---

## ADR-003: Gateway API over Ingress

**Context**: Ingress resources have limited extensibility and inconsistent implementations.

**Decision**: Use Kubernetes Gateway API with Cilium as the implementation.

**Consequences**:
- (+) Role-based resource model (Gateway, HTTPRoute)
- (+) Future-proof standard
- (+) Better multi-tenancy support
- (+) Native Cilium integration
- (-) Newer standard, less documentation available

---

## ADR-004: External Secrets with Bitwarden

**Context**: Secrets need to be managed securely without storing plaintext in Git.

**Decision**: Use External Secrets Operator syncing from Bitwarden Secrets Manager.

**Consequences**:
- (+) Centralized secret management
- (+) Audit trail in Bitwarden
- (+) No encrypted secrets in Git
- (+) Easy rotation
- (-) Dependency on external service
- (-) Requires Bitwarden SDK server component

---

## ADR-006: Use PocketID for OIDC

**Context**: The cluster needs an OIDC provider for SSO across apps (Immich, Coder, Grafana, Matrix). The provider should be lightweight and not require its own database stack.

**Decision**: Use PocketID (`anza-labs/pocket-id` Helm chart). OIDC clients are configured via PocketID's web UI.

**Consequences**:
- (+) Minimal resource usage (no PostgreSQL, no Redis — SQLite-backed)
- (+) Simple deployment and maintenance
- (+) Passkey-based authentication (more secure than passwords)
- (+) SQLite database with Longhorn PVC persistence
- (-) OIDC client configuration is manual (via UI, not GitOps)
- (-) Fewer features than full IDPs (no LDAP, SAML, etc.)

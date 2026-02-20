## Documentation Index

### Entry Point
- `.context/substrate.md` - **Start here.** Repository overview, tech stack, and AI guidelines.

### Core Context Files
| File | Purpose |
|------|---------|
| `.context/glossary.md` | Project-specific terminology (Flux, CNPG, etc.) |
| `.context/conventions.md` | Naming standards for files, resources, and secrets |
| `.context/debt.md` | Known technical debt to avoid compounding |

### Architecture
| File | Purpose |
|------|---------|
| `.context/architecture/overview.md` | System design, dependency chain, Flux patterns |
| `.context/architecture/app-structure.md` | Standard app deployment structure (ks.yaml + app/) |
| `.context/architecture/networking.md` | DNS, gateways, Cloudflare tunnel, ingress routing |

### Authentication & Secrets
| File | Purpose |
|------|---------|
| `.context/auth/secrets.md` | External Secrets + Bitwarden integration |
| `.context/auth/oauth.md` | Authentik OAuth/OIDC provider patterns |

### Database & Cache
| File | Purpose |
|------|---------|
| `.context/database/cnpg.md` | CloudNativePG cluster patterns and configuration |
| `.context/cache/dragonfly.md` | Dragonfly (Redis-compatible) cache patterns |

### Backup & Restore
| File | Purpose |
|------|---------|
| `.context/backup-restore.md` | Velero backup strategy, restore procedures, disaster recovery |

### Monitoring
| File | Purpose |
|------|---------|
| `.context/monitoring/alerting.md` | Prometheus alerts, Alertmanager, Discord notifications |

### Architecture Decision Records
| File | Purpose |
|------|---------|
| `.context/decisions/README.md` | ADR template and index |

## Instructions for Claude Code

### Before Generating Manifests
1. Read `.context/substrate.md` first for project orientation
2. Read `.context/conventions.md` for naming standards
3. Check existing apps in `kubernetes/apps/` for reference patterns

### Task-Specific Context

**Adding a new application:**
Read `.context/architecture/app-structure.md`, `.context/conventions.md`

**OAuth/SSO integration:**
Read `.context/auth/oauth.md`, `.context/auth/secrets.md`

**Secret management:**
Read `.context/auth/secrets.md`

**PostgreSQL database setup:**
Read `.context/database/cnpg.md`

**Redis/cache setup:**
Read `.context/cache/dragonfly.md`

**Understanding dependencies:**
Read `.context/architecture/overview.md`

**Networking, DNS, or ingress:**
Read `.context/architecture/networking.md`

**Monitoring or alerting:**
Read `.context/monitoring/alerting.md`

**Backup, restore, or disaster recovery:**
Read `.context/backup-restore.md`

### Code Standards
- Follow naming conventions from `.context/conventions.md`
- Use standard app structure from `.context/architecture/app-structure.md`
- Reference the `common` component for namespace creation
- Add appropriate `dependsOn` entries in Flux Kustomizations
- Use HTTPRoute (not Ingress) for exposing services
- Prefer CNPG Cluster CRs for PostgreSQL databases
- Store secrets in Bitwarden, reference via ExternalSecret

### Do Not
- Generate manifests without checking similar existing apps first
- Use Ingress resources (use HTTPRoute with Gateway API)
- Embed databases in Helm charts (use CNPG operator)
- Store secrets directly in Git (use External Secrets)
- Skip `dependsOn` for resources that need prerequisites
- Override established naming conventions without clear rationale

### When Making Changes
- Update relevant `.context/` files when adding new patterns
- Document architectural decisions in `.context/decisions/`
- Keep examples in documentation current and functional
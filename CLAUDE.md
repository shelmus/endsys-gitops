# GitOps Infrastructure Orchestrator

You are the primary orchestrator for the endsys-gitops Kubernetes infrastructure. This is a Talos Linux cluster managed via FluxCD GitOps workflows, based on the onedr0p/cluster-template.

## Repository Structure

```
kubernetes/
├── apps/           # Application HelmReleases organized by namespace
├── components/     # Shared Kustomize components
└── flux/
    ├── cluster/    # Flux bootstrapping (Kustomizations, sources)
    └── meta/       # HelmRepositories, OCIRepositories
```

## Core Stack

- **OS**: Talos Linux
- **GitOps**: FluxCD (source-controller, helm-controller, kustomize-controller)
- **CNI**: Cilium
- **Secrets**: External Secrets Operator → Bitwarden
- **Ingress**: Cloudflare Tunnels (cloudflared)
- **Certs**: cert-manager with Let's Encrypt
- **DNS**: external-dns
- **Database**: CloudNativePG (CNPG) for PostgreSQL clusters
- **Cache**: Dragonfly as Redis-compatible cache

## Your Role

1. Understand user intent and determine which subagent(s) to delegate to
2. Coordinate multi-step operations spanning multiple concerns
3. Synthesize results from subagents into coherent responses

## Available Subagents

| Agent | Purpose | When to Use |
|-------|---------|-------------|
| `@flux` | FluxCD resources, reconciliation, GitOps workflows | Kustomizations, Sources, sync issues, dependency ordering |
| `@helm` | HelmRelease authoring, values management | Creating/editing HelmReleases, chart troubleshooting, values overlays |
| `@k8s` | Raw Kubernetes resources, debugging | Manifests, kubectl commands, events, logs, stuck resources |
| `@secrets` | External Secrets + Bitwarden integration | ExternalSecret CRs, SecretStore config, rotation |
| `@talos` | Talos Linux node management | Node config, upgrades, talhelper, machine configs |
| `@docs` | Repository and application documentation | README updates, app docs, runbooks, architecture decisions |
| `@context-improver` | Agent context refinement | End of sessions, after learning new patterns |

## Delegation Patterns

### Single-concern tasks
Route directly to the appropriate subagent:
- "Add a new app" → `@helm` (then `@flux` if Kustomization needed)
- "Why isn't my release syncing?" → `@flux` first, then `@k8s` for deeper debugging
- "Create a secret for my database" → `@secrets`
- "Document this application" → `@docs`
- "Update the README" → `@docs`

### Multi-concern tasks
Coordinate across subagents:
- "Deploy a new application end-to-end" → `@secrets` (if secrets needed) → `@helm` (HelmRelease) → `@flux` (Kustomization) → `@docs` (documentation) → `@k8s` (verify)
- "Debug a failing deployment" → `@flux` (sync status) → `@helm` (release status) → `@k8s` (pod logs/events)

### Troubleshooting escalation
1. `@flux` - Check Kustomization/HelmRelease status
2. `@helm` - Check Helm release history, values
3. `@k8s` - Check pods, events, logs
4. `@talos` - Check node health if cluster-level issues

## File Conventions

### App structure (kubernetes/apps/{namespace}/{app}/)
```
app-name/
├── ks.yaml           # Kustomization pointing to ./app
├── app/
│   ├── kustomization.yaml
│   ├── helmrelease.yaml
│   ├── externalsecret.yaml  # If secrets needed
│   └── [additional resources]
```

### Naming conventions
- Namespaces: lowercase, hyphenated (e.g., `media`, `home-automation`)
- HelmReleases: match app name
- Kustomizations: `{app-name}` with `dependsOn` for ordering

## Common Commands

```bash
# Check Flux status
flux get all -A
flux get ks -A
flux get hr -A

# Force reconciliation
flux reconcile ks flux-system --with-source
flux reconcile hr {name} -n {namespace}

# Check sources
flux get sources all -A

# Talos
talosctl -n {node} health
talosctl -n {node} dmesg | tail -50
```

## Important Patterns

1. **Always use OCI sources** for Helm charts when available (ghcr.io)
2. **dependsOn chains**: infrastructure → configs → apps
3. **Secrets before apps**: ExternalSecrets must sync before HelmReleases that need them
4. **Suspend before delete**: Suspend HelmReleases before removing to avoid finalizer issues
5. **Operator before CRs**: Deploy operators (CNPG, etc.) in separate namespaces before app Kustomizations that use their CRDs
6. **External databases over subcharts**: Prefer CNPG Cluster CRs over embedded PostgreSQL subcharts for production workloads
7. **Dragonfly over Redis**: Use Dragonfly as a drop-in Redis replacement for better performance
8. **CNPG auto-secrets**: CNPG creates `{cluster-name}-app` secrets automatically with DB credentials

## Session End Protocol

Before ending any session involving new patterns, troubleshooting discoveries, or workflow improvements:
1. Invoke `@context-improver` with a summary of learnings
2. Suggest updates to agent context files if patterns should be permanent

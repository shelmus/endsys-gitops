# GitOps Agents for endsys-gitops

A Claude Code agent system for managing your Kubernetes/FluxCD/Talos infrastructure.

## Structure

```
.claude/
├── AGENT.md                    # Main orchestrator (or use as CLAUDE.md)
└── agents/
    ├── flux.md                 # FluxCD specialist
    ├── helm.md                 # HelmRelease specialist  
    ├── k8s.md                  # Kubernetes fundamentals
    ├── secrets.md              # External Secrets + Bitwarden
    ├── talos.md                # Talos Linux management
    ├── docs.md                 # Documentation management
    └── context-improver.md     # Meta-agent for improving agents
```

## Note on Original Template Documentation

The original onedr0p/cluster-template README should be retained as `cluster_template.md` for reference. The `@docs` agent will create a new `README.md` tailored to your specific cluster.

## Installation

### Option 1: As CLAUDE.md (simple)
```bash
# Copy AGENT.md to your repo root as CLAUDE.md
cp AGENT.md /path/to/endsys-gitops/CLAUDE.md

# Copy subagents to .claude/agents/
mkdir -p /path/to/endsys-gitops/.claude/agents
cp subagents/*.md /path/to/endsys-gitops/.claude/agents/
```

### Option 2: As .claude directory structure
```bash
# Copy entire structure
cp -r . /path/to/endsys-gitops/.claude/

# Rename AGENT.md
mv /path/to/endsys-gitops/.claude/AGENT.md /path/to/endsys-gitops/.claude/CLAUDE.md
```

## Usage

### Direct invocation
When working with Claude Code, reference subagents explicitly:
```
@flux why isn't my kustomization syncing?
@helm create a HelmRelease for jellyfin
@secrets set up ExternalSecret for my database credentials
@docs document the jellyfin application
@docs update the main README with current apps
```

### Via orchestrator
Just describe what you need and the orchestrator routes appropriately:
```
"Deploy a new media server application with persistent storage"
→ Orchestrator coordinates: @secrets → @helm → @flux
```

### Context improvement
At the end of productive sessions:
```
@context-improver

## Session Summary
[Describe what you accomplished]

## Key Learnings
[What did you discover?]
```

## Customization

### Add cluster-specific details

Edit `AGENT.md` to include:
- Your actual node IPs
- Namespace conventions
- Specific chart sources you use frequently
- Team conventions

### Add new subagents

Create new files in `agents/` for additional specializations:
- `@monitoring` - Prometheus/Grafana stack
- `@storage` - CSI drivers, PVC management
- `@networking` - Cilium policies, Gateway API

### Extend existing agents

Add patterns as you discover them:
```markdown
## Our Common Patterns

### Standard app deployment
[Your team's conventions]
```

## Agent Capabilities Summary

| Agent | Creates | Troubleshoots | Manages |
|-------|---------|---------------|---------|
| @flux | Kustomizations, Sources | Sync issues, dependencies | Reconciliation |
| @helm | HelmReleases | Failed releases, values | Upgrades, rollbacks |
| @k8s | Raw manifests | Pod/Node issues | Resources, cleanup |
| @secrets | ExternalSecrets | Sync failures | Rotation |
| @talos | Machine configs | Node health | Upgrades |
| @docs | READMEs, runbooks, ADRs | Documentation gaps | Repo documentation |
| @context-improver | Documentation | - | Agent knowledge |

## Tips

1. **Start with the orchestrator** for complex tasks - it will delegate appropriately
2. **Go direct to subagent** when you know exactly what you need
3. **Run @context-improver** after learning something new
4. **Keep agents lean** - only add patterns that save significant time
5. **Version control your agents** - they're part of your infrastructure

## Integration with Existing CLAUDE.md

If you already have a CLAUDE.md, you can:
1. Merge the orchestrator content into your existing file
2. Add a reference: `For infrastructure tasks, see .claude/agents/`
3. Keep them separate and context-switch as needed

# Kubernetes FluxCD Project

## Overview
This is a GitOps-managed Kubernetes cluster using FluxCD for continuous deployment. The repository contains Kubernetes manifests, Helm releases, and Flux configurations that automatically sync to the cluster.

## Project Structure
```
.
├── kubernetes/           # Cluster-specific configurations
    ├── apps/              # Application deployments
    ├── components/          # Common components
    └── flux/    
        └── cluster/      # Flux bootstrapping and configuration
        └── meta/         # Flux repos 
```

## Technology Stack
- **Kubernetes Version**: 1.34
- **FluxCD Version**: [e.g., v2.x]
- **Cluster Type**: bare-metal
- **GitOps Repo**: [this repository]
- **Container Registry**: [e.g., Docker Hub, GHCR, private registry]

## Key Components
- **Flux Controllers**: Source Controller, Kustomize Controller, Helm Controller, Notification Controller
- **Infrastructure**:
    - httproute
    - kube-system
    - longhorn-system
- **Applications**:
    - external-secrets
    - n8n
    - seaweedfs
    - velero
    - minio
    - minio-operator
    - pelican
    - openwebui

## Common Commands
NOTE: DO NOT COMMIT TO MAIN BRANCH, Flux and kubectl commands are not needed because it pulls from GitHub

### Flux Management
```bash
# Check Flux system status
flux check

# Reconcile a specific resource immediately
flux reconcile kustomization <name>
flux reconcile helmrelease <name> -n <namespace>

# Suspend/resume reconciliation
flux suspend kustomization <name>
flux resume kustomization <name>

# View logs
flux logs --level=error --all-namespaces

# Export current configuration
flux export source git flux-system
flux export kustomization flux-system
```

### Kubernetes Operations
```bash
# Apply manifests directly (testing only, not GitOps)
kubectl apply -f <file>

# Check resources
kubectl get kustomizations -A
kubectl get helmreleases -A
kubectl get gitrepositories -A

# Describe resources for debugging
kubectl describe kustomization <name> -n flux-system
kubectl describe helmrelease <name> -n <namespace>

# View events
kubectl get events -n <namespace> --sort-by='.lastTimestamp'
```

### Testing & Validation
```bash
# Validate Kubernetes manifests
kubectl apply --dry-run=client -f <file>
kubectl apply --dry-run=server -f <file>

# Validate Kustomization
kubectl kustomize <path>

# Check Helm template rendering
helm template <release-name> <chart> -f values.yaml

# Validate with kubeval (if installed)
kubeval <file>
```

## Development Workflow

### Adding a New Application
1. Create application manifests in `apps/base/<app-name>/`
2. Create Kustomization or HelmRelease resource
3. Add to appropriate environment overlay in `apps/production/`
4. Commit and push changes
5. Flux will automatically reconcile (or trigger manually)

### Updating an Application
1. Modify the relevant manifest, Kustomization, or HelmRelease
2. Update image tags or chart versions
3. Commit and push
4. Monitor reconciliation: `flux reconcile kustomization <name> --with-source`

### Managing Secrets
- **Sealed Secrets**: Encrypt secrets with `kubeseal` before committing
- **SOPS**: Use `sops` for encrypting sensitive values in Git
- **External Secrets Operator**: Sync from external secret stores

```bash
# Example: Create sealed secret
kubectl create secret generic <name> --from-literal=key=value --dry-run=client -o yaml | \
  kubeseal -o yaml > sealed-secret.yaml
```

## File Naming Conventions
- Use kebab-case for file names: `my-application.yaml`
- Kustomization files: `kustomization.yaml`
- Namespace definitions: `namespace.yaml`
- HelmRelease files: `helmrelease.yaml`
- GitRepository sources: `<release-name>.yaml`

## Code Style & Standards
- Use 2-space indentation for YAML files
- Include meaningful comments for complex configurations
- Always specify namespace explicitly in resources
- Use labels consistently:
  ```yaml
  labels:
    app.kubernetes.io/name: <app-name>
    app.kubernetes.io/instance: <instance-name>
    app.kubernetes.io/component: <component>
    app.kubernetes.io/part-of: <system>
  ```
- Pin image tags (avoid `latest`)
- Pin Helm chart versions

## System Defaults
- System uses httproute as the ingress replacement, use the following as a template for that yaml. "internal" can be switched with "external" as a choice to the user.
```
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: <app name>
spec:
  parentRefs:
  - name: internal
    namespace: kube-system
    sectionName: https
  hostnames: ["<app name>.endsys.cloud"]
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /
    - backendRefs:
        - name: <app name>
          port: 80
```
- Base kustomization.yaml also should following the following scheme, this would remove the need to create a namespace.yaml. Also allows the importing of common components.
```
---
# yaml-language-server: $schema=https://json.schemastore.org/kustomization
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: <app name>
components:
  - ../../components/common
resources:
  - ./<app name>/ks.yaml
```

## Troubleshooting

### Flux Not Reconciling
1. Check Flux system status: `flux check`
2. View resource status: `kubectl describe kustomization <name> -n flux-system`
3. Check controller logs: `flux logs --level=error`
4. Force reconciliation: `flux reconcile kustomization <name> --with-source`

### HelmRelease Failures
1. Check HelmRelease status: `kubectl describe helmrelease <name> -n <namespace>`
2. View Helm Controller logs: `kubectl logs -n flux-system deploy/helm-controller`
3. Test Helm template locally: `helm template <release> <chart> -f values.yaml`
4. Check for image pull errors: `kubectl get events -n <namespace>`

### Git Source Issues
1. Verify GitRepository status: `kubectl describe gitrepository flux-system -n flux-system`
2. Check authentication: Ensure deploy keys or tokens are valid
3. Verify repository URL and branch
4. Check network connectivity from cluster to Git provider

## Important Notes
- **Never commit unencrypted secrets** to Git
- Always test changes with `--dry-run` before applying
- Use separate branches for testing major changes
- Keep Flux components up to date
- Monitor Flux notifications for reconciliation failures
- Back up cluster state regularly with Velero or similar tools

## Resources & Documentation
- [FluxCD Documentation](https://fluxcd.io/docs/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Kustomize Documentation](https://kustomize.io/)
- [Helm Documentation](https://helm.sh/docs/)

## Environment-Specific Notes
<!-- Add specific details about your cluster environment -->
- **Cluster Name**: [your-cluster-name]
- **Cluster Provider**: [e.g., self-hosted, EKS, GKE, AKS]
- **Flux Repository URL**: [your-git-repo-url]
- **Flux Sync Interval**: [e.g., 1m, 5m]
- **Alert Channels**: [e.g., Slack, Discord, email]

## Contact & Support
- **Repository**: [link to repo]
- **Team Channel**: [e.g., #k8s-ops on Slack]
- **On-Call**: [escalation process]
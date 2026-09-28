# endsys-gitops

GitOps source for an endsys Talos Linux Kubernetes cluster. Flux, managed through the Flux Operator, reconciles the cluster from this repository; Kubernetes manifests, Talos configuration, bootstrap resources, and encrypted SOPS material are maintained directly rather than generated from templates.

## Stack

| Area | Components |
| --- | --- |
| Cluster and delivery | Talos Linux, Flux Operator / Flux, Kustomize, HelmRelease |
| Networking | Cilium, Gateway API, cert-manager, Cloudflare Tunnel |
| DNS | external-dns and k8s-gateway |
| Secrets | External Secrets Operator with Bitwarden; SOPS/age for encrypted material |
| Data | CloudNativePG, Dragonfly, Longhorn, NFS CSI, Garage |
| Protection and observability | Velero, kube-prometheus-stack, Gatus |

Talos and Kubernetes versions are declared in [`talos/talenv.yaml`](talos/talenv.yaml). Development tools are pinned in [`.mise.toml`](.mise.toml).

## Repository layout

| Path | Contents |
| --- | --- |
| [`bootstrap/`](bootstrap/) | Initial Flux and cluster bootstrap resources |
| [`kubernetes/`](kubernetes/) | Flux, shared components, infrastructure, and application manifests |
| [`talos/`](talos/) | Talos configuration, patches, and version declarations |
| [`.taskfiles/bootstrap/`](.taskfiles/bootstrap/) | Talos and application bootstrap tasks |
| [`.taskfiles/talos/`](.taskfiles/talos/) | Talos generation, apply, upgrade, and reset tasks |
| [`scripts/`](scripts/) | Bootstrap helpers |
| [`.context/`](.context/) | Architecture, conventions, operations, and decision documentation |

## Application catalog

Exposure is derived from active `HTTPRoute` resources and Helm chart route configuration. `internal` uses the private gateway; `external` uses the Cloudflare-facing gateway. `—` means no application route is declared here.

| Namespace | App | Exposure | Purpose |
| --- | --- | --- | --- |
| cert-manager | cert-manager | — | TLS certificate management |
| cnpg-system | cnpg-operator | — | PostgreSQL operator |
| coder | coder | external | Development environments |
| external-services | octopi | internal | — |
| external-services | gameserver | — | Game server monitoring target |
| external-secrets | external-secrets | — | Bitwarden secret synchronization |
| firecrawl | firecrawl | internal | Web crawling service |
| flux-system | flux-instance | external | Flux instance and GitHub webhook receiver |
| flux-system | flux-operator | — | Flux lifecycle management |
| garage | garage | — | S3-compatible object storage |
| gatus | gatus | external | Uptime monitoring |
| hindsight | hindsight | internal | — |
| home-assistant | home-assistant | internal | Home automation |
| immich | immich | external | Photo management |
| kube-prometheus-stack | kube-prometheus-stack | internal | Metrics, alerting, and dashboards |
| kube-system | cilium | — | CNI and Gateway API implementation |
| kube-system | coredns | — | Cluster DNS |
| kube-system | metrics-server | — | Resource metrics |
| kube-system | reloader | — | Workload reload controller |
| kube-system | spegel | — | Image distribution |
| kube-system | snapshot-controller | — | CSI snapshot controller |
| kube-system | csi-driver-nfs | — | NFS storage driver |
| kube-system | gpu-device-plugin | — | GPU device plugin |
| larder | larder | internal | — |
| longhorn-system | longhorn-system | internal | Distributed block storage |
| manatable | manatable | external | — |
| matrix | matrix | external | Matrix services |
| n8n | n8n | internal | Workflow automation |
| network | cloudflare-dns | — | Public DNS records |
| network | cloudflare-tunnel | — | Public ingress tunnel |
| network | k8s-gateway | — | In-cluster DNS for routed services |
| network | pihole-dns | — | Local DNS records |
| network | echo | external | HTTP connectivity test service |
| obsidian-livesync | obsidian-livesync | external | Obsidian synchronization |
| pelican | pelican | internal | Game server panel |
| pocket-id | pocket-id | external | OIDC identity provider |
| pricebuddy | pricebuddy | internal | Price tracking |
| romm | romm | internal | ROM management |
| taxsale-monitor | taxsale-monitor | — | Tax-sale monitoring |
| velero | velero | — | Cluster backup and restore |

**Dormant:** `default/otterwiki` is commented out in its namespace Kustomization and is not part of the active catalog. Its route manifest targets the internal gateway.

## How changes ship

1. Open a pull request against `main`.
2. When Kubernetes files change, the Flux Local workflow runs a rendered test and posts HelmRelease and Kustomization diffs.
3. After merge to `main`, Flux receives repository changes through its GitHub webhook receiver and reconciles the declared state.

## Renovate

[Renovate](.renovaterc.json5) runs on weekends with a dependency dashboard and branch automerge enabled. Mise tool minor and patch updates, plus GitHub Action minor, patch, and digest updates, are configured for automerge; GitHub Actions wait three days before merging.

## Operations

Run `task --list` to see the available tasks. Tools are pinned in [`.mise.toml`](.mise.toml) (`mise install`).

Tasks expect `./kubeconfig`, `./age.key`, and `talos/clusterconfig/talosconfig` at the repository root. All three are gitignored; the paths come from `Taskfile.yaml` and `.mise.toml`.

| Task | What it does |
| --- | --- |
| `task reconcile` | Force Flux to pull and reconcile `main` |
| `task debug` | Read-only `kubectl get` sweep of certificates, Flux objects, routes, nodes, and pods |
| `task talos:generate-config` | Render node configs and a fresh `talosconfig` from [`talos/talconfig.yaml`](talos/talconfig.yaml), [`talos/talenv.yaml`](talos/talenv.yaml), and the SOPS-encrypted `talos/talsecret.sops.yaml` (needs the age key) |
| `task talos:validate` | Schema-check `talconfig.yaml` |
| `task talos:apply-node IP=…` | Apply rendered config to one node |
| `task talos:upgrade-node IP=…` | Upgrade Talos on one node to `talosVersion` from `talenv.yaml` |
| `task talos:upgrade-k8s` | Upgrade Kubernetes to `kubernetesVersion` from `talenv.yaml` |
| `task bootstrap:talos` / `task bootstrap:apps` | First-time cluster and app bootstrap only |

An admin kubeconfig can be regenerated from a valid talosconfig with `talosctl kubeconfig`. The age key cannot be regenerated: it decrypts `talsecret.sops.yaml`, which holds the cluster CAs.

Start with the [context index](.context/substrate.md). Operational references include [architecture](.context/architecture/overview.md), [networking](.context/architecture/networking.md), [secrets](.context/auth/secrets.md), [backup and restore](.context/backup-restore.md), and [technical debt](.context/debt.md).

## Origins

This repository began from [onedr0p/cluster-template](https://github.com/onedr0p/cluster-template) and has since been adapted for this cluster.

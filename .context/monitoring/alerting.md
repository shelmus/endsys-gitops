# Monitoring & Alerting

Patterns for Prometheus monitoring and Alertmanager notifications.

## Overview

The `kube-prometheus-stack` Helm chart deploys Prometheus, Alertmanager, and Grafana. Custom PrometheusRule resources define alert conditions, and Alertmanager routes notifications to Discord.

```
┌──────────────┐     scrape     ┌──────────────┐
│  Prometheus  │ ◄────────────  │   Targets    │
│              │                │ (pods, nodes)│
└──────┬───────┘                └──────────────┘
       │ evaluate rules
       ▼
┌──────────────┐    webhook     ┌──────────────┐
│ Alertmanager │ ─────────────► │   Discord    │
│              │                │   Channel    │
└──────────────┘                └──────────────┘
```

## Deployment

**Location**: `kubernetes/apps/kube-prometheus-stack/kube-prometheus-stack/`

**Chart**: kube-prometheus-stack v81.0.0 from `prometheus-community.github.io/helm-charts`

**Key configuration**:
- Default rules disabled (`defaultRules.create: false`) — only custom rules are active
- Discord webhook URL injected via ExternalSecret + `valuesFrom`

## Web UIs

| Service | URL | Gateway |
|---------|-----|---------|
| Grafana | `grafana.endsys.cloud` | internal |
| Prometheus | `prometheus.endsys.cloud` | internal |
| Alertmanager | `alertmanager.endsys.cloud` | internal |

## Alertmanager Configuration

### Notification Channel

Discord webhook via ExternalSecret:
- **Bitwarden key**: `alertmanager-discord-webhook-url`
- **K8s Secret**: `alertmanager-discord` (key: `webhook-url`)
- Injected via `valuesFrom` so the URL never appears in Git

### Routing

```yaml
route:
  receiver: discord
  group_by: ['alertname', 'namespace']
  group_wait: 30s        # Wait before sending first notification
  group_interval: 5m     # Wait between notifications for same group
  repeat_interval: 4h    # Re-notify after this interval
  routes:
    - receiver: discord
      matchers:
        - severity=~"warning|critical"
```

### Message Format

Alerts display with status indicators:
- Firing: red circle + alert name + severity + description
- Resolved: green circle + same details

## Alert Rules

### App Outage Alerts (`prometheusrule-apps.yaml`)

Monitors namespaces: `immich`, `pocket-id`, `gatus`, `kube-prometheus-stack`, `n8n`, `pelican`

| Alert | Condition | Severity | For |
|-------|-----------|----------|-----|
| `AppPodNotReady` | Pod not in Ready condition | warning | 5m |
| `AppDeploymentUnavailable` | Deployment has 0 available replicas | critical | 5m |
| `AppHelmReleaseFailed` | HelmRelease Ready condition is False | critical | 5m |

### Storage Alerts (`prometheusrule-storage.yaml`)

**PVC alerts** (all namespaces):

| Alert | Condition | Severity | For |
|-------|-----------|----------|-----|
| `PVCUsageWarning` | PVC usage > 80% | warning | 5m |
| `PVCUsageCritical` | PVC usage > 90% | critical | 5m |

**Longhorn alerts** (requires Longhorn ServiceMonitor):

| Alert | Condition | Severity | For |
|-------|-----------|----------|-----|
| `LonghornVolumeDegraded` | Volume robustness is "degraded" | warning | 5m |
| `LonghornVolumeFaulted` | Volume robustness is "faulted" | critical | 1m |
| `LonghornNodeStoragePressure` | Node disk usage > 85% | warning | 5m |

## Adding a New Alert Rule

1. Add the rule to the appropriate PrometheusRule file (or create a new one)
2. Add the file to `app/kustomization.yaml`
3. Use `severity: warning` or `severity: critical` to match the Alertmanager routing
4. Include `summary` and `description` annotations

### PrometheusRule Template

```yaml
---
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: my-alerts
  labels:
    app.kubernetes.io/name: kube-prometheus-stack
    app.kubernetes.io/component: alerting
spec:
  groups:
    - name: my-alert-group
      rules:
        - alert: MyAlertName
          expr: |
            some_metric > threshold
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "Short summary with {{ $labels.instance }}"
            description: "Detailed description with {{ $value }}."
```

## Adding a New Monitored App

To include a new app namespace in the outage alerts, update the namespace regex in `prometheusrule-apps.yaml`:

```yaml
namespace=~"immich|pocket-id|gatus|kube-prometheus-stack|n8n|pelican|new-app"
```

## Dependencies

The kube-prometheus-stack Kustomization depends on:
- `external-secrets-stores` (for Discord webhook ExternalSecret)

## Troubleshooting

### Check alert status

```bash
# View firing alerts in Prometheus
kubectl port-forward -n kube-prometheus-stack svc/kube-prometheus-stack-prometheus 9090
# Then visit http://localhost:9090/alerts

# Check Alertmanager routing
kubectl port-forward -n kube-prometheus-stack svc/kube-prometheus-stack-alertmanager 9093
# Then visit http://localhost:9093/#/status
```

### Verify PrometheusRules loaded

```bash
kubectl get prometheusrules -n kube-prometheus-stack
```

### Check ExternalSecret sync

```bash
kubectl get externalsecret -n kube-prometheus-stack
```

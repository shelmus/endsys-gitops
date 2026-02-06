# Network Architecture

DNS resolution, ingress routing, and external connectivity patterns.

## Overview

Traffic reaches applications through two paths:
- **External**: Internet → Cloudflare Tunnel → `external` Gateway → HTTPRoute → Pod
- **Internal**: LAN → k8s-gateway DNS → `internal` Gateway → HTTPRoute → Pod

```
                        Internet
                            │
                            ▼
                    ┌───────────────┐
                    │   Cloudflare  │
                    │    Tunnel     │
                    └───────┬───────┘
                            │
              ┌─────────────┼─────────────┐
              ▼                           ▼
    ┌──────────────────┐        ┌──────────────────┐
    │ external Gateway │        │ internal Gateway │
    │   10.127.0.52    │        │   10.127.0.51    │
    └────────┬─────────┘        └────────┬─────────┘
             │                           │
         HTTPRoutes                  HTTPRoutes
      (public apps)             (private apps)
```

## Gateways

**Location**: `kubernetes/apps/kube-system/cilium/gateway/`

Both gateways use Cilium's Gateway API implementation with TLS certificates from cert-manager.

| Gateway | IP | Purpose | Allowed Routes |
|---------|-----|---------|---------------|
| `internal` | 10.127.0.51 | Private LAN access | All namespaces (HTTPS), Same namespace (HTTP) |
| `external` | 10.127.0.52 | Public via Cloudflare | All namespaces (HTTPS), Same namespace (HTTP) |

Both listen on `*.${SECRET_DOMAIN}` (ports 80 and 443) with TLS certificates referenced from the cert-manager-issued wildcard secret.

### HTTPRoute parentRefs

Apps reference gateways via:

```yaml
parentRefs:
  - name: internal    # or 'external'
    namespace: kube-system
    sectionName: https
```

## DNS Architecture

Three external-dns instances manage DNS records for different providers:

```
                    ┌─────────────────────┐
                    │   Gateway API       │
                    │   HTTPRoutes        │
                    └──┬──────┬──────┬────┘
                       │      │      │
          ┌────────────┘      │      └────────────┐
          ▼                   ▼                    ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│  cloudflare-dns  │ │   pihole-dns     │ │   k8s-gateway    │
│  (external-dns)  │ │  (external-dns)  │ │  (CoreDNS-based) │
└────────┬─────────┘ └────────┬─────────┘ └────────┬─────────┘
         │                    │                     │
         ▼                    ▼                     ▼
    Cloudflare API      Pi-hole API           In-cluster DNS
   (public records)   (local records)       (*.endsys.cloud)
```

### cloudflare-dns

**Location**: `kubernetes/apps/network/cloudflare-dns/`

- **Chart**: external-dns v1.20.0
- **Provider**: Cloudflare
- **Sources**: CRD (DNSEndpoint), gateway-httproute
- **Gateway filter**: `external` only
- **Policy**: `sync` (creates and deletes records)
- **Cloudflare proxy**: enabled (CDN + DDoS protection)

Creates public DNS records for apps exposed via the `external` gateway.

### pihole-dns

**Location**: `kubernetes/apps/network/pihole-dns/`

- **Chart**: external-dns v1.20.0
- **Provider**: Pi-hole (API v6)
- **Pi-hole server**: `http://10.127.0.3`
- **Sources**: gateway-httproute, service
- **Policy**: `upsert-only` (never deletes manually-created records)
- **Registry**: `noop` (Pi-hole doesn't support TXT ownership records)

Creates local DNS records on the network Pi-hole for internal resolution.

### k8s-gateway

**Location**: `kubernetes/apps/network/k8s-gateway/`

- **Chart**: k8s-gateway v3.4.1 (OCI)
- **IP**: 10.127.0.50 (LoadBalancer)
- **Port**: 53 (DNS)
- **Domain**: `${SECRET_DOMAIN}`
- **Watches**: HTTPRoute, Service
- **TTL**: 1 second

Provides in-cluster DNS resolution for `*.endsys.cloud` by watching Gateway API resources. Used by pods that need to resolve cluster services by their external hostname.

## Cloudflare Tunnel

**Location**: `kubernetes/apps/network/cloudflare-tunnel/`

Ingress path for all public-facing apps. Runs `cloudflared` connecting to Cloudflare's edge network.

- **Image**: `cloudflare/cloudflared:2025.11.1`
- **Transport**: QUIC (post-quantum encryption enabled)
- **HTTP/2 origin**: enabled
- **Metrics**: port 8080 with ServiceMonitor
- **Security**: non-root, read-only rootfs, all capabilities dropped
- **Config**: mounted from ConfigMap (`cloudflare-tunnel-configmap`)
- **Secrets**: tunnel credentials from SOPS-encrypted secret

## Echo Server

**Location**: `kubernetes/apps/network/echo/`

HTTP echo server for testing external connectivity. Exposed on the `external` gateway at `echo.endsys.cloud`.

- **Image**: `ghcr.io/mendhak/http-https-echo:39`
- **Depends on**: cloudflare-tunnel
- **Prometheus metrics**: enabled
- Monitored by Gatus as a health check target

## cert-manager

**Location**: `kubernetes/apps/cert-manager/`

Manages TLS certificates for both gateways.

- **ClusterIssuer**: `letsencrypt-production`
- **ACME solver**: DNS-01 via Cloudflare API
- Provides wildcard certificate for `*.${SECRET_DOMAIN}`
- Certificate referenced by both Gateway resources

## Adding an Externally-Accessible App

1. Create an HTTPRoute with `parentRefs` pointing to the `external` gateway
2. Cloudflare DNS will automatically create a DNS record
3. Pi-hole DNS will automatically create a local record
4. Traffic will flow: Internet → Cloudflare → Tunnel → external Gateway → your app

## Adding an Internally-Accessible App

1. Create an HTTPRoute with `parentRefs` pointing to the `internal` gateway
2. Pi-hole DNS will automatically create a local record
3. k8s-gateway provides in-cluster DNS resolution
4. Only accessible from the local network

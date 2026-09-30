# 2026-09-29 — Certificate expiry + Watchdog alerting

Branch `mimir/alerting-watchdog-cert-expiry`. Work by Mimir (Hermes, claude-opus-5-5),
authorized by Sean.

## Why

The Lyris Wings cert (`lyris.endsys.cloud`, certbot on the host) expired on
2026-09-29 at 22:21 UTC. Renewal had been failing with Cloudflare token IP
filter error 9109, and nothing alerted. `defaultRules.create: false` means
no cert rules and no Watchdog existed, and Gatus did not probe Lyris.

## Change

- `prometheusrule-certificates.yaml` (8 rules):
  - Watchdog;
  - CertManagerCertificateExpiringSoon (<14d, 1h), ExpiryCritical (<3d) and
    NotReady;
  - EndpointCertificateExpiringSoon and ExpiryCritical (Gatus);
  - TlsEndpointCheckFailing (Gatus `type="TLS"` success == 0 for 15m);
  - GatusMetricsAbsent.
- Alertmanager: a `null` receiver, and a first route sending `alertname="Watchdog"`
  to it. `discord` stays `receivers[0]` for the valuesFrom webhook path.
- Gatus: endpoint `lyris-wings-tls` = `tls://lyris.endsys.cloud:8443`, every 5m,
  with `[CONNECTED] == true` and `[CERTIFICATE_EXPIRATION] > 72h`.

## Verification

| Check | Result |
|---|---|
| `promtool check rules` (prometheus v3.7.3) | 8 rules OK |
| `promtool test rules` (3 groups: 1h-left Gatus cert, cert-manager 10d + NotReady, failing TLS vs TCP/HTTP) | pass |
| Mutations: flip the Gatus threshold; drop the `type="TLS"` scope | both caught (tests fail) |
| `amtool check-config` + `config routes test` (v0.28.1) | Watchdog → null, critical → discord |
| gatus v5.34.0 in local docker against the live expired Lyris cert | `[CONNECTED]` false, x509 expired. Only `endpoint_success{type="TLS"} 0` is emitted, with no expiry gauge. That's why TlsEndpointCheckFailing exists. |
| In-cluster DNS for lyris.endsys.cloud | CoreDNS forwards to /etc/resolv.conf. Talos nameservers are 10.127.0.3 and 10.127.0.1, and both return 10.127.0.7. |
| flux-local v8.0.1 `test --enable-helm --all-namespaces` (CI's command) | 84 passed |
| flux-local `build all --enable-helm` | renders certificate-alerts, the null route, and the Gatus endpoint |
| Live query of new exprs against current Prometheus | nothing fires today except Watchdog (all certs >57d) |

## Expected after merge

The **TlsEndpointCheckFailing critical alert will fire for lyris-wings-tls
within about 20 minutes, until the Lyris cert is renewed.** That is correct
behaviour.

## Not verified

- Live Flux reconcile and Discord delivery. These need the merge.
- The Watchdog appears in the Alertmanager UI but has no external dead-man's
  switch yet (e.g. healthchecks.io).

# Clean-Slate Wipe — Design

**Date:** 2026-04-30
**Author:** sean (with Claude)
**Status:** Approved

## Goal

Wipe data and state for all non-essential apps in the cluster, leaving `pelican` (and infrastructure) untouched. Sparing the `garage` HelmRelease/PVCs so existing Velero backups remain accessible. Disabling — not deleting — the wiped apps from Git so they can be re-enabled later.

## Scope

### Apps to wipe (data + workloads, manifests stay in Git but commented out)

- `coder`
- `home-assistant`
- `immich` (server, machine-learning, postgres, dragonfly, library NFS PV)
- `matrix` (synapse, mas, postgres clusters)
- `n8n`
- `obsidian-livesync`
- `pocket-id`
- `pricebuddy`

### Apps to spare

- `pelican` (explicit user requirement)
- `garage` (Velero backup target — recently deployed)

### Infrastructure to spare (not touched)

`flux-system`, `cilium`, `coredns`, `csi-driver-nfs`, `metrics-server`, `reloader`, `snapshot-controller`, `spegel`, `longhorn-system`, `cnpg-system`, `external-secrets`, `cert-manager`, `network/*` (cloudflare-dns, cloudflare-tunnel, echo, k8s-gateway, pihole-dns), `velero`, `kube-prometheus-stack`, `gatus`.

### Cleanup of obsolete auth stack

`authentik` and `authelia` were replaced by `pocket-id`. Remove residual references:

- Delete K8s namespaces `authentik` and `authelia` (the only live remnant is `data-authentik-postgresql-0` PVC)
- Strip authentik/authelia mentions from:
  - `CLAUDE.md`
  - `.context/auth/oauth.md`
  - `.context/debt.md`
  - `.context/decisions/README.md`

No `kubernetes/apps/authentik` or `kubernetes/apps/authelia` directories exist; no Git deletion of app manifests required.

## Phases

### Phase 0 — Pre-wipe Velero backup (safety net)

Take a full backup of every namespace about to be wiped. Stored on `garage`, retained.

```sh
velero backup create pre-clean-slate-2026-04-30 \
  --include-namespaces coder,home-assistant,immich,matrix,n8n,obsidian-livesync,pocket-id,pricebuddy \
  --wait
```

Restore command (kept here for reference):

```sh
velero restore create from-pre-clean-slate \
  --from-backup pre-clean-slate-2026-04-30 \
  --include-namespaces coder,home-assistant,immich,matrix,n8n,obsidian-livesync,pocket-id,pricebuddy
```

Verify the backup completes successfully (`velero backup describe pre-clean-slate-2026-04-30 --details`) before proceeding.

### Phase 1 — Remove residual authentik/authelia references

1. Edit out authentik/authelia mentions in:
   - `CLAUDE.md`
   - `.context/auth/oauth.md`
   - `.context/debt.md`
   - `.context/decisions/README.md`
2. Commit: `chore: remove residual authentik/authelia references`
3. Push.
4. Delete K8s namespaces `authentik` and `authelia` (PVC `data-authentik-postgresql-0` deleted with them; Longhorn volume auto-prunes).

### Phase 2 — Disable apps in Git

For each app in scope, comment the `- ./{app}/ks.yaml` line out of `kubernetes/apps/{namespace}/kustomization.yaml`. The app's directory and manifests stay intact for easy re-enable later.

Affected files:

- `kubernetes/apps/coder/kustomization.yaml`
- `kubernetes/apps/home-assistant/kustomization.yaml`
- `kubernetes/apps/immich/kustomization.yaml` (covers immich + dragonfly + postgres)
- `kubernetes/apps/matrix/kustomization.yaml`
- `kubernetes/apps/n8n/kustomization.yaml`
- `kubernetes/apps/obsidian-livesync/kustomization.yaml`
- `kubernetes/apps/pocket-id/kustomization.yaml`
- `kubernetes/apps/pricebuddy/kustomization.yaml`

Commit: `chore: disable apps for clean-slate wipe`. Push.

### Phase 3 — Let Flux prune

```sh
flux reconcile kustomization -n flux-system cluster-apps --with-source
```

Flux's `prune: true` removes the now-orphaned `Kustomization` resources, which cascades to: `HelmRelease` → `helm uninstall` → workloads/services/secrets/PVCs → Longhorn volumes (Delete policy) auto-pruned.

Verify each scope namespace is empty:

```sh
for ns in coder home-assistant immich matrix n8n obsidian-livesync pocket-id pricebuddy; do
  echo "=== $ns ==="
  kubectl get all,pvc -n $ns
done
```

If any PVC lingers (operators that don't propagate uninstall to PVCs), backstop:

```sh
kubectl delete pvc --all -n <namespace>
```

### Phase 4 — Manual cleanup outside Flux

1. Delete the manually-defined NFS PV (Retain policy):

   ```sh
   kubectl delete pv immich-library-pv
   ```

2. Wipe NFS-backed Immich data on the NAS (otherwise next deploy sees leftover content):

   ```sh
   ssh momo@10.127.0.7 "sudo rm -rf /vault/immich/*"
   ```

   **Do not touch** `/vault/k8s/garage` — that's the live Velero backup store.

### Phase 5 — Bitwarden update checklist (manual, post-wipe)

Print to user. No keys regenerate automatically.

#### Likely need new values *only if* pocket-id generates fresh OAuth client_secrets on re-registration

Alternative: when re-registering each OAuth client in pocket-id, set the client_secret to the **existing** Bitwarden value — then no update needed.

- `coder-oauth-client-id`
- `coder-oauth-client-secret`
- `immich-oauth-client-secret`
- `matrix-oauth-client-id`
- `matrix-oauth-client-secret`
- `grafana-oauth-client-id`
- `grafana-oauth-client-secret`

#### No update needed — apps initialize fresh state from these

- `pocket-id-encryption-key`
- `obsidian-livesync-couchdb-username`, `obsidian-livesync-couchdb-password`
- `pricebuddy-db-username`, `pricebuddy-db-password`, `pricebuddy-db-root-password`, `pricebuddy-admin-email`, `pricebuddy-admin-password`

#### Spared, untouched

- `pelican-app-key`
- `velero-s3-access-key`, `velero-s3-secret-key`
- `alertmanager-discord-webhook-url`

## Risks / gotchas

1. **Coder workspace home PVC** (`coder-sean-magenta-platypus-77-home`) — wiped along with the namespace. Any in-flight workspace files are lost.
2. **Matrix federation identity** — Synapse signing keys regenerate. Federated rooms will see a new server identity. Acceptable for a homelab instance.
3. **OAuth dependency on pocket-id** — Grafana (spared) authenticates against pocket-id. While pocket-id is wiped/redeploying, Grafana OAuth login fails. Until the OAuth client is re-registered in the fresh pocket-id, Grafana SSO is broken. Use a local Grafana admin to recover.
4. **NFS data on NAS persists by default** — the manual `rm -rf /vault/immich/*` step is mandatory for a true clean slate.
5. **Velero backup is single-point safety** — if the pre-wipe backup fails or is incomplete, halt before Phase 2.

## Re-enable workflow (future, out of scope here)

When the user wants an app back: uncomment its line in `kubernetes/apps/{namespace}/kustomization.yaml`, push, Flux redeploys with empty volumes. Manual steps after redeploy:

- Re-register OAuth clients in pocket-id (for coder, immich, matrix, grafana)
- Recreate users / admin accounts inside each app
- (Optional) Restore from `pre-clean-slate-2026-04-30` Velero backup if you change your mind

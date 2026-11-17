#!/usr/bin/env bash
# Create the Garage bucket and read-write / read-only keys for CNPG (Barman Cloud) backups.
#
# RUN THIS YOURSELF, in your own terminal. Do not run it through an AI agent:
# Garage prints each secret key once, at creation, and it must go straight into
# Bitwarden Secrets Manager without passing through chat, logs or Git.
#
# Usage:
#   scripts/cnpg-backup-keys.sh                 # every CNPG cluster in the live cluster
#   scripts/cnpg-backup-keys.sh romm-postgres   # one or more named clusters
#   scripts/cnpg-backup-keys.sh new-postgres    # a cluster declared in this repo but not deployed yet
#                                               # (new app: run on its PR branch BEFORE merging)
#   scripts/cnpg-backup-keys.sh --dry-run       # show what would be created, change nothing
#
# Idempotent: existing buckets and keys are left alone, never recreated or re-printed.
# Standard: .context/database/cnpg-backup-standard.md
set -Eeuo pipefail

export KUBECONFIG="${KUBECONFIG:-$HOME/kubeconfig}"
DRY_RUN=0
declare -a WANT=()
for a in "$@"; do
  case "$a" in
    --dry-run) DRY_RUN=1 ;;
    -h|--help) sed -n '2,17p' "$0"; exit 0 ;;
    *) WANT+=("$a") ;;
  esac
done

g() { kubectl -n garage exec garage-0 -c garage -- /garage "$@" 2> >(grep -v 'INFO garage_net' >&2); }
exists_bucket() { g bucket info "$1" >/dev/null 2>&1; }
exists_key() { g key info "$1" >/dev/null 2>&1; }

# Cluster list: "<namespace> <cluster-name>" from the live cluster.
mapfile -t CLUSTERS < <(kubectl get clusters.postgresql.cnpg.io -A \
  -o jsonpath='{range .items[*]}{.metadata.namespace} {.metadata.name}{"\n"}{end}')
[ "${#CLUSTERS[@]}" -gt 0 ] || { echo "No CNPG clusters found (check KUBECONFIG)"; exit 1; }

# A named cluster that isn't deployed yet (a new app's PR, keys needed BEFORE
# merging) is accepted only if a postgres-cluster.yaml in this repo declares it,
# so a typo can't create a stray bucket.
REPO_APPS="$(cd "$(dirname "$0")/.." && pwd)/kubernetes/apps"
for w in "${WANT[@]}"; do
  live=0
  for line in "${CLUSTERS[@]}"; do [ "${line#* }" = "$w" ] && live=1; done
  [ $live = 1 ] && continue
  decl=$(grep -rlx --include=postgres-cluster.yaml "  name: ${w}" "$REPO_APPS" 2>/dev/null | head -1 || true)
  [ -n "$decl" ] || { echo "Cluster '${w}' is neither live nor declared in kubernetes/apps/*/postgres-cluster.yaml"; exit 1; }
  ns=$(basename "$(dirname "$(dirname "$(dirname "$decl")")")")
  echo "Note: ${w} is not deployed yet; using its declaration in ${decl#"$REPO_APPS"/} (namespace ${ns})"
  CLUSTERS+=("${ns} ${w}")
done

declare -a PRINTED=()
for line in "${CLUSTERS[@]}"; do
  ns=${line%% *}; cluster=${line#* }
  if [ "${#WANT[@]}" -gt 0 ] && [[ ! " ${WANT[*]} " =~ " ${cluster} " ]]; then continue; fi
  base=${cluster%-postgres}               # larder-postgres -> larder
  bucket="cnpg-${base}"
  rw="cnpg-${base}-rw"; ro="cnpg-${base}-ro"

  echo
  echo "=================================================================="
  echo " ${ns}/${cluster}  ->  bucket ${bucket}"
  echo "=================================================================="

  if exists_bucket "$bucket"; then echo "  bucket ${bucket}: exists, skipped"
  elif [ $DRY_RUN = 1 ]; then echo "  bucket ${bucket}: WOULD CREATE"
  else g bucket create "$bucket" >/dev/null && echo "  bucket ${bucket}: created"; fi

  for pair in "rw:${rw}" "ro:${ro}"; do
    kind=${pair%%:*}; key=${pair#*:}
    if exists_key "$key"; then echo "  key ${key}: exists, skipped (secret not shown again)"; continue; fi
    if [ $DRY_RUN = 1 ]; then echo "  key ${key}: WOULD CREATE"; continue; fi
    out=$(g key create "$key")
    id=$(awk -F': *' '$1=="Key ID"{print $2}' <<<"$out" | tr -d '[:space:]')
    sec=$(awk -F': *' '$1=="Secret key"{print $2}' <<<"$out" | tr -d '[:space:]')
    if [ "$kind" = rw ]; then
      g bucket allow --read --write "$bucket" --key "$key" >/dev/null
      bw_id="${base}-cnpg-s3-access-key"; bw_sec="${base}-cnpg-s3-secret-key"; perm="read+write"
    else
      g bucket allow --read "$bucket" --key "$key" >/dev/null
      bw_id="${base}-cnpg-s3-ro-access-key"; bw_sec="${base}-cnpg-s3-ro-secret-key"; perm="read only"
    fi
    echo "  key ${key}: created (${perm} on ${bucket} only)"
    echo "      Bitwarden ${bw_id}  =  ${id}"
    echo "      Bitwarden ${bw_sec}  =  ${sec}"
    PRINTED+=("$bw_id" "$bw_sec")
    unset id sec out
  done

  if [ $DRY_RUN = 0 ] && exists_bucket "$bucket"; then
    echo "  permissions on ${bucket}:"
    g bucket info "$bucket" | sed -n '/KEYS FOR THIS BUCKET/,$p' | tail -n +3 | sed -E 's/^/    /; s/GK([0-9a-f]{6})[0-9a-f]+/GK\1.../'
  fi
done

echo
if [ "${#PRINTED[@]}" -gt 0 ]; then
  echo "Copy the ${#PRINTED[@]} values above into Bitwarden Secrets Manager (endsys-gitops project),"
  echo "using exactly the names shown. Garage will not show these secret keys again."
  echo "Then clear your terminal scrollback (e.g. 'clear && printf \"\\e[3J\"')."
else
  echo "Nothing new was created; no secrets printed."
fi

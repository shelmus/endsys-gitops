#!/usr/bin/env bash
# Create every secret self-hosted NetBird needs, and print each Bitwarden name next to its value.
#
# RUN THIS YOURSELF, in your own terminal. Do not run it through an AI agent:
# the values must go straight into Bitwarden Secrets Manager without passing
# through chat, logs or Git.
#
# Creates:
#   bucket cnpg-netbird   key cnpg-netbird-rw  (read+write)  -> CNPG Barman Cloud backups of netbird-postgres
#                         key cnpg-netbird-ro  (read only)   -> restore drills
#   4 random values (openssl), for netbird-server config.yaml and the Postgres owner role
#   and prints the steps for the one secret that can't be scripted: the Cloudflare DDNS token.
#
# Usage:
#   scripts/netbird-secrets.sh             # create what is missing, print new secrets once
#   scripts/netbird-secrets.sh --dry-run   # show what would be created, change nothing
#
# Garage part is idempotent: existing buckets and keys are left alone, never re-printed.
# The random values are NOT idempotent (the script can't see Bitwarden): every
# non-dry run prints fresh ones. Paste them only on the first run. If the
# Bitwarden entries already exist, ignore the printed values. Re-pasting new ones
# after NetBird is running breaks it (store key = setup keys/API tokens unreadable;
# Postgres password = server can't log in).
set -Eeuo pipefail

export KUBECONFIG="${KUBECONFIG:-$HOME/kubeconfig}"
DRY_RUN=0
for a in "$@"; do
  case "$a" in
    --dry-run) DRY_RUN=1 ;;
    -h|--help) sed -n '2,23p' "$0"; exit 0 ;;
    *) echo "unknown argument: $a" >&2; exit 2 ;;
  esac
done

command -v openssl >/dev/null || { echo "openssl not found" >&2; exit 1; }

g() { kubectl -n garage exec garage-0 -c garage -- /garage "$@" 2> >(grep -v 'INFO garage_net' >&2); }
exists_bucket() { g bucket info "$1" >/dev/null 2>&1; }
exists_key() { g key info "$1" >/dev/null 2>&1; }

declare -a PRINTED=()

ensure_bucket() {
  local bucket=$1
  if exists_bucket "$bucket"; then echo "  bucket ${bucket}: exists, skipped"
  elif [ $DRY_RUN = 1 ]; then echo "  bucket ${bucket}: WOULD CREATE"
  else g bucket create "$bucket" >/dev/null && echo "  bucket ${bucket}: created"; fi
}

# ensure_key <bucket> <key> <rw|ro> <bitwarden-id-name> <bitwarden-secret-name>
ensure_key() {
  local bucket=$1 key=$2 kind=$3 bw_id=$4 bw_sec=$5
  if exists_key "$key"; then echo "  key ${key}: exists, skipped (secret not shown again)"; return; fi
  if [ $DRY_RUN = 1 ]; then echo "  key ${key}: WOULD CREATE  (Bitwarden ${bw_id}, ${bw_sec})"; return; fi
  local out id sec perm
  out=$(g key create "$key")
  id=$(awk -F': *' '$1=="Key ID"{print $2}' <<<"$out" | tr -d '[:space:]')
  sec=$(awk -F': *' '$1=="Secret key"{print $2}' <<<"$out" | tr -d '[:space:]')
  if [ "$kind" = rw ]; then
    g bucket allow --read --write "$bucket" --key "$key" >/dev/null; perm="read+write"
  else
    g bucket allow --read "$bucket" --key "$key" >/dev/null; perm="read only"
  fi
  echo "  key ${key}: created (${perm} on ${bucket} only)"
  echo "      Bitwarden ${bw_id}  =  ${id}"
  echo "      Bitwarden ${bw_sec}  =  ${sec}"
  PRINTED+=("$bw_id" "$bw_sec")
}

show_perms() {
  local bucket=$1
  if [ $DRY_RUN = 0 ] && exists_bucket "$bucket"; then
    echo "  permissions on ${bucket}:"
    g bucket info "$bucket" | sed -n '/KEYS FOR THIS BUCKET/,$p' | tail -n +3 | sed -E 's/^/    /; s/GK([0-9a-f]{6})[0-9a-f]+/GK\1.../'
  fi
}

# gen <bitwarden-name> <openssl rand args...> <purpose>
gen() {
  local name=$1 purpose=$2; shift 2
  if [ $DRY_RUN = 1 ]; then echo "  ${name}: WOULD GENERATE  (openssl rand $*)  ${purpose}"; return; fi
  echo "  Bitwarden ${name}  =  $(openssl rand "$@")"
  echo "      (${purpose})"
  PRINTED+=("$name")
}

echo
echo "=================================================================="
echo " netbird/netbird-postgres CNPG backups  ->  bucket cnpg-netbird"
echo "=================================================================="
ensure_bucket cnpg-netbird
ensure_key cnpg-netbird cnpg-netbird-rw rw netbird-cnpg-s3-access-key netbird-cnpg-s3-secret-key
ensure_key cnpg-netbird cnpg-netbird-ro ro netbird-cnpg-s3-ro-access-key netbird-cnpg-s3-ro-secret-key
show_perms cnpg-netbird

echo
echo "=================================================================="
echo " Generated values (first run only, see header)"
echo "=================================================================="
# Hex where the value lands inside a libpq key=value DSN or plain YAML, to avoid quoting issues.
gen netbird-relay-auth-secret     "config.yaml server.authSecret: relay auth shared secret" -hex 32
gen netbird-postgres-password     "CNPG owner role 'netbird'; also used in config.yaml DSNs" -hex 24
# NetBird docs: store.encryptionKey = base64 of 32 random bytes. Losing it = re-issue all setup keys/API tokens.
gen netbird-store-encryption-key  "config.yaml server.store.encryptionKey (back this one up)" -base64 32
# NetBird docs: sessionCookieEncryptionKey = 16/24/32 raw bytes or base64 of those; base64 of 32 bytes.
gen netbird-idp-cookie-key        "config.yaml server.auth.sessionCookieEncryptionKey" -base64 32

echo
echo "=================================================================="
echo " By hand: Cloudflare API token for DDNS  ->  netbird-ddns-cloudflare-token"
echo "=================================================================="
cat <<'TXT'
  Cloudflare dashboard -> My Profile -> API Tokens -> Create Token -> "Edit zone DNS" template:
    Permissions:      Zone / DNS / Edit
    Zone Resources:   Include / Specific zone / endsys.cloud
    Client IP Filter: LEAVE EMPTY  (the home WAN IP changes; a filter breaks DDNS
                                    exactly when it's needed, as with Lyris certbot)
    TTL:              none, or a long expiry with a calendar reminder
  Copy the token once into Bitwarden as  netbird-ddns-cloudflare-token
TXT

echo
if [ $DRY_RUN = 1 ]; then
  echo "Dry run: nothing created, no secrets printed."
else
  echo "Copy the ${#PRINTED[@]} values above, plus the Cloudflare token, into Bitwarden Secrets Manager"
  echo "(endsys-gitops project), using exactly the names shown."
  echo "Then clear your terminal scrollback (e.g. 'clear && printf \"\\e[3J\"')."
fi

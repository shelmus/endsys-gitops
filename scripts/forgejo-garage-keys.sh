#!/usr/bin/env bash
# Create the Garage buckets and keys Forgejo needs, and print the Bitwarden names next to each value.
#
# RUN THIS YOURSELF, in your own terminal. Do not run it through an AI agent:
# Garage prints each secret key once, at creation, and it must go straight into
# Bitwarden Secrets Manager without passing through chat, logs or Git.
#
# Creates:
#   bucket forgejo        key forgejo-rw        (read+write)  -> Forgejo blob storage (LFS, packages, attachments, ...)
#   bucket cnpg-forgejo   key cnpg-forgejo-rw   (read+write)  -> CNPG Barman Cloud backups
#                         key cnpg-forgejo-ro   (read only)   -> restore drills
#
# Usage:
#   scripts/forgejo-garage-keys.sh             # create what is missing, print new secrets once
#   scripts/forgejo-garage-keys.sh --dry-run   # show what would be created, change nothing
#
# Idempotent: existing buckets and keys are left alone, never recreated or re-printed.
# Same mechanics as scripts/cnpg-backup-keys.sh (PR #374); that script cannot be used here
# because it lists CNPG clusters from the live cluster and forgejo-postgres does not exist yet.
set -Eeuo pipefail

export KUBECONFIG="${KUBECONFIG:-$HOME/kubeconfig}"
DRY_RUN=0
for a in "$@"; do
  case "$a" in
    --dry-run) DRY_RUN=1 ;;
    -h|--help) sed -n '2,18p' "$0"; exit 0 ;;
    *) echo "unknown argument: $a" >&2; exit 2 ;;
  esac
done

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

echo
echo "=================================================================="
echo " Forgejo blob storage  ->  bucket forgejo"
echo "=================================================================="
ensure_bucket forgejo
ensure_key forgejo forgejo-rw rw forgejo-s3-access-key forgejo-s3-secret-key
show_perms forgejo

echo
echo "=================================================================="
echo " forgejo/forgejo-postgres CNPG backups  ->  bucket cnpg-forgejo"
echo "=================================================================="
ensure_bucket cnpg-forgejo
ensure_key cnpg-forgejo cnpg-forgejo-rw rw forgejo-cnpg-s3-access-key forgejo-cnpg-s3-secret-key
ensure_key cnpg-forgejo cnpg-forgejo-ro ro forgejo-cnpg-s3-ro-access-key forgejo-cnpg-s3-ro-secret-key
show_perms cnpg-forgejo

echo
if [ "${#PRINTED[@]}" -gt 0 ]; then
  echo "Copy the ${#PRINTED[@]} values above into Bitwarden Secrets Manager (endsys-gitops project),"
  echo "using exactly the names shown. Garage will not show these secret keys again."
  echo "Then clear your terminal scrollback (e.g. 'clear && printf \"\\e[3J\"')."
else
  echo "Nothing new was created; no secrets printed."
fi

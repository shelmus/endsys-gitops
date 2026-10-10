#!/usr/bin/env python3
"""Add the standard Barman Cloud backup wiring to an existing CNPG cluster in this repo.

Usage:
  scripts/cnpg-backup-scaffold.py <cluster-name> [--time HH:MM] [--dry-run]
  scripts/cnpg-backup-scaffold.py --audit      # which clusters in Git meet the standard (exit 1 on gaps)

What it does (standard: .context/database/cnpg-backup-standard.md):
  1. writes cnpg-backup-<cluster>.yaml next to the cluster's postgres-cluster.yaml
     (ExternalSecret + ObjectStore + ScheduledBackup);
  2. lists that file in the directory's kustomization.yaml;
  3. adds spec.plugins (barman-cloud, isWALArchiver) to the Cluster;
  4. adds dependsOn plugin-barman-cloud (+ external-secrets-stores) to the Flux Kustomization.

Refuses to run if the cluster already has spec.plugins. Picks the next free 5-minute
backup slot from 03:15 UTC unless --time is given. Does not touch the live cluster.
"""
import argparse
import pathlib
import re
import sys
from typing import NoReturn

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
APPS = ROOT / "kubernetes" / "apps"
FIRST_SLOT = 3 * 60 + 15  # 03:15 UTC, after Velero's 02:00-02:50 window
PLUGIN = "barman-cloud.cloudnative-pg.io"

BACKUP_TEMPLATE = """---
# CNPG backups for {cluster}: continuous WAL archiving + daily base backup to Garage
# bucket {bucket} via the Barman Cloud plugin. Standard: .context/database/cnpg-backup-standard.md
# Required Bitwarden secrets (create with scripts/cnpg-backup-keys.sh BEFORE merging):
#   - {base}-cnpg-s3-access-key
#   - {base}-cnpg-s3-secret-key
# yaml-language-server: $schema=https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/external-secrets.io/externalsecret_v1.json
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: {base}-cnpg-s3
  labels:
    app.kubernetes.io/component: backup-storage-credentials
spec:
  refreshInterval: 1h
  secretStoreRef:
    kind: ClusterSecretStore
    name: bitwarden-secretsmanager
  target:
    name: {base}-cnpg-s3
    creationPolicy: Owner
    deletionPolicy: Retain
    template:
      engineVersion: v2
      data:
        ACCESS_KEY_ID: "{{{{ .accessKey }}}}"
        ACCESS_SECRET_KEY: "{{{{ .secretKey }}}}"
        REGION: garage
  data:
    - secretKey: accessKey
      remoteRef:
        key: {base}-cnpg-s3-access-key
    - secretKey: secretKey
      remoteRef:
        key: {base}-cnpg-s3-secret-key
---
apiVersion: barmancloud.cnpg.io/v1
kind: ObjectStore
metadata:
  name: {base}-objectstore
spec:
  retentionPolicy: "30d"
  configuration:
    destinationPath: s3://{bucket}/
    endpointURL: http://garage.garage.svc:3900
    s3Credentials:
      accessKeyId:
        name: {base}-cnpg-s3
        key: ACCESS_KEY_ID
      secretAccessKey:
        name: {base}-cnpg-s3
        key: ACCESS_SECRET_KEY
      region:
        name: {base}-cnpg-s3
        key: REGION
    wal:
      compression: gzip
    data:
      compression: gzip
  instanceSidecarConfiguration:
    env:
      # Recommended by the plugin docs for S3-compatible stores (newer boto3 checksum defaults).
      - name: AWS_REQUEST_CHECKSUM_CALCULATION
        value: when_required
      - name: AWS_RESPONSE_CHECKSUM_VALIDATION
        value: when_required
---
apiVersion: postgresql.cnpg.io/v1
kind: ScheduledBackup
metadata:
  name: {cluster}-daily
spec:
  # CNPG cron has a seconds field: {hh:02d}:{mm:02d} UTC.
  schedule: "0 {mm} {hh} * * *"
  # immediate fires before an EXISTING cluster's restarted pod has the plugin sidecar;
  # for an existing cluster, take the first backup by hand (see the standard).
  immediate: true
  backupOwnerReference: self
  cluster:
    name: {cluster}
  method: plugin
  pluginConfiguration:
    name: {plugin}
"""

PLUGINS_BLOCK = """  # WAL archiving + base backups via the Barman Cloud plugin (see cnpg-backup-{cluster}.yaml).
  plugins:
    - name: {plugin}
      isWALArchiver: true
      parameters:
        barmanObjectName: {base}-objectstore
"""


def die(msg) -> NoReturn:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def split_docs(text):
    # Split on document separators, keeping each chunk's text verbatim.
    parts = re.split(r"(?m)^---[ \t]*\n", text)
    return parts  # parts[0] is any header before the first '---'


def join_docs(parts):
    return parts[0] + "".join("---\n" + p for p in parts[1:])


def used_slots():
    slots = set()
    for f in APPS.rglob("*.yaml"):
        for doc in yaml.safe_load_all(f.read_text()):
            if isinstance(doc, dict) and doc.get("kind") == "ScheduledBackup":
                fields = str(doc["spec"]["schedule"]).split()
                if len(fields) == 6 and fields[1].isdigit() and fields[2].isdigit():
                    slots.add(int(fields[2]) * 60 + int(fields[1]))
    return slots


def audit():
    """List every CNPG Cluster in Git and whether it meets the backup standard. Exit 1 if any gap."""
    clusters, stores, sched, esecrets = {}, set(), set(), set()
    for f in sorted(APPS.rglob("*.yaml")):
        try:
            docs = list(yaml.safe_load_all(f.read_text()))
        except yaml.YAMLError:
            continue
        for d in docs:
            if not isinstance(d, dict):
                continue
            kind, name = d.get("kind"), d.get("metadata", {}).get("name")
            if kind == "Cluster" and str(d.get("apiVersion", "")).startswith("postgresql.cnpg.io/"):
                clusters[name] = (f, d)
            elif kind == "ObjectStore":
                stores.add(name)
            elif kind == "ScheduledBackup" and d.get("spec", {}).get("method") == "plugin":
                sched.add(d["spec"]["cluster"]["name"])
            elif kind == "ExternalSecret":
                esecrets.add(name)
    gaps = 0
    print(f"{'cluster':28} {'plugin':7} {'store':6} {'secret':7} {'daily':6} file")
    for name, (f, d) in sorted(clusters.items()):
        base = name.removesuffix("-postgres")
        pl = [p for p in d.get("spec", {}).get("plugins", []) or [] if p.get("name") == PLUGIN]
        wal = bool(pl and pl[0].get("isWALArchiver"))
        store = pl[0].get("parameters", {}).get("barmanObjectName") if pl else None
        row = (wal, store in stores if store else False, f"{base}-cnpg-s3" in esecrets, name in sched)
        ok = all(row)
        gaps += not ok
        print(f"{name:28} " + " ".join(f"{'yes' if v else 'NO':{w}}" for v, w in zip(row, (7, 6, 7, 6)))
              + f" {f.relative_to(ROOT)}")
    print(f"\n{len(clusters) - gaps}/{len(clusters)} clusters meet the backup standard")
    sys.exit(1 if gaps else 0)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--audit":
        audit()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cluster")
    ap.add_argument("--time", help="backup time HH:MM UTC (default: next free 5-min slot from 03:15)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    cluster = a.cluster
    if not cluster.endswith("-postgres"):
        die("cluster names follow <app>-postgres (see .context/database/cnpg.md)")
    base = cluster[: -len("-postgres")]
    bucket = f"cnpg-{base}"

    # 1. locate the Cluster manifest
    hits = []
    for f in APPS.rglob("*.yaml"):
        text = f.read_text()
        if "kind: Cluster" not in text:
            continue
        for doc in yaml.safe_load_all(text):
            if isinstance(doc, dict) and doc.get("kind") == "Cluster" and doc.get("apiVersion", "").startswith("postgresql.cnpg.io/") \
                    and doc.get("metadata", {}).get("name") == cluster:
                hits.append((f, doc))
    if len(hits) != 1:
        die(f"expected exactly one Cluster named {cluster}, found {len(hits)}")
    cfile, cdoc = hits[0]
    if cdoc.get("spec", {}).get("plugins"):
        die(f"{cluster} already has spec.plugins; nothing to do")
    adir = cfile.parent
    out = adir / f"cnpg-backup-{cluster}.yaml"
    if out.exists():
        die(f"{out.relative_to(ROOT)} already exists")

    # 2. schedule slot
    if a.time:
        hh, mm = (int(x) for x in a.time.split(":"))
    else:
        taken = used_slots()
        slot = FIRST_SLOT
        while slot in taken:
            slot += 5
        hh, mm = divmod(slot, 60)

    backup_yaml = BACKUP_TEMPLATE.format(cluster=cluster, base=base, bucket=bucket, hh=hh, mm=mm, plugin=PLUGIN)

    # 3. Cluster: append plugins under spec (spec must be the last top-level key of that document)
    parts = split_docs(cfile.read_text())
    done = False
    for i, p in enumerate(parts):
        d = yaml.safe_load(p) if p.strip() else None
        if isinstance(d, dict) and d.get("kind") == "Cluster" and d.get("metadata", {}).get("name") == cluster:
            if list(d.keys())[-1] != "spec":
                die(f"{cfile.relative_to(ROOT)}: 'spec' is not the last key of the {cluster} document; edit by hand")
            parts[i] = p.rstrip("\n") + "\n" + PLUGINS_BLOCK.format(cluster=cluster, base=base, plugin=PLUGIN)
            done = True
    if not done:
        die("could not locate the Cluster document text")
    new_cluster = join_docs(parts)

    # 4. kustomization.yaml resources
    kfile = adir / "kustomization.yaml"
    ktext = kfile.read_text()
    m = re.search(r"(?m)^([ \t]*)- \./" + re.escape(cfile.name) + r"[ \t]*$", ktext)
    if not m:
        die(f"{kfile.relative_to(ROOT)} does not list ./{cfile.name}")
    entry = f"{m.group(1)}- ./{out.name}"
    new_k = ktext[: m.end()] + "\n" + entry + ktext[m.end():]
    if not new_k.endswith("\n"):
        new_k += "\n"

    # 5. Flux Kustomization dependsOn
    ks = adir.parent / "ks.yaml"
    rel = "./" + str(adir.relative_to(ROOT))
    kparts = split_docs(ks.read_text())
    kdone = False
    for i, p in enumerate(kparts):
        d = yaml.safe_load(p) if p.strip() else None
        if not (isinstance(d, dict) and d.get("kind") == "Kustomization" and d.get("spec", {}).get("path") == rel):
            continue
        deps = {(x["name"], x.get("namespace")) for x in d["spec"].get("dependsOn", [])}
        add = []
        for name, ns in (("external-secrets-stores", "external-secrets"), ("plugin-barman-cloud", "cnpg-system")):
            if (name, ns) not in deps:
                add.append(f"    - name: {name}\n      namespace: {ns}\n")
        if add:
            lines = p.splitlines(keepends=True)
            idx = next((j for j, ln in enumerate(lines) if ln.rstrip("\n") == "  dependsOn:"), None)
            if idx is not None:
                # the dependsOn list runs while lines are indented deeper than 2 spaces
                end = idx + 1
                while end < len(lines) and (lines[end].startswith("    ") or not lines[end].strip()):
                    end += 1
                lines[end:end] = add
            else:
                sidx = next((j for j, ln in enumerate(lines) if ln.rstrip("\n") == "spec:"), None)
                if sidx is None:
                    die(f"{ks.relative_to(ROOT)}: no top-level spec:; edit by hand")
                lines[sidx + 1:sidx + 1] = ["  dependsOn:\n"] + add
            p = "".join(lines)
            kparts[i] = p
        kdone = True
    if not kdone:
        die(f"no Flux Kustomization in {ks.relative_to(ROOT)} has path {rel}")
    new_ks = join_docs(kparts)

    # validate everything parses before writing
    for label, text in ((out.name, backup_yaml), (cfile.name, new_cluster), (kfile.name, new_k), (ks.name, new_ks)):
        try:
            list(yaml.safe_load_all(text))
        except yaml.YAMLError as e:
            die(f"generated {label} does not parse: {e}")

    print(f"cluster   {cluster}  (base '{base}', bucket {bucket})")
    print(f"schedule  {hh:02d}:{mm:02d} UTC")
    print(f"write     {out.relative_to(ROOT)}")
    print(f"edit      {cfile.relative_to(ROOT)}  (+spec.plugins)")
    print(f"edit      {kfile.relative_to(ROOT)}  (+{out.name})")
    print(f"edit      {ks.relative_to(ROOT)}  (dependsOn)")
    print(f"bitwarden {base}-cnpg-s3-access-key, {base}-cnpg-s3-secret-key, "
          f"{base}-cnpg-s3-ro-access-key, {base}-cnpg-s3-ro-secret-key")
    if a.dry_run:
        print("dry run: nothing written")
        return
    out.write_text(backup_yaml)
    cfile.write_text(new_cluster)
    kfile.write_text(new_k)
    ks.write_text(new_ks)


if __name__ == "__main__":
    main()

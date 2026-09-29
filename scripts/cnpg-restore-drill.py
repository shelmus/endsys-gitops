#!/usr/bin/env python3
"""Restore drill for a CNPG cluster backed up with the Barman Cloud plugin.

Usage:
  scripts/cnpg-restore-drill.py <namespace> <cluster-name> [--keep] [--dry-run]

Creates namespace <cluster>-restore-test containing:
  - an ExternalSecret for the READ-ONLY Garage key (<base>-cnpg-s3-ro-*),
  - an ObjectStore pointing at the production bucket with that key,
  - a Cluster that recovers from the newest base backup + archived WAL.
The restored cluster copies the production image, postgresql settings and storage size,
has no spec.plugins and archive_mode off, so it cannot write to the backup bucket.

It then compares the table list and per-table row counts (numbers only, no row data)
between production and the restore, prints the result, and deletes the namespace
unless --keep is given. Red tier: creates and deletes a namespace. Needs admin kubeconfig.
Standard: .context/database/cnpg-backup-standard.md
"""
import argparse
import json
import os
import subprocess
import sys
import time

KUBECONFIG = os.environ.get("KUBECONFIG", os.path.expanduser("~/kubeconfig"))
PLUGIN = "barman-cloud.cloudnative-pg.io"
COUNT_SQL = (
    "select string_agg(format('select %L as t, count(*) as n from %I.%I', "
    "table_schema||'.'||table_name, table_schema, table_name), ' union all ' "
    "order by table_schema, table_name) from information_schema.tables "
    "where table_schema not in ('pg_catalog','information_schema') and table_type='BASE TABLE'"
)


def k(*args, input=None, check=True):
    r = subprocess.run(["kubectl", "--kubeconfig", KUBECONFIG, *args], input=input,
                       capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.exit(f"kubectl {' '.join(args[:3])} failed: {r.stderr.strip()}")
    return r.stdout


def psql(ns, pod, db, sql):
    return k("-n", ns, "exec", pod, "-c", "postgres", "--", "psql", "-d", db, "-At", "-F", " ", "-c", sql)


def counts(ns, pod, db):
    q = psql(ns, pod, db, COUNT_SQL).strip()
    if not q:
        return {}
    out = psql(ns, pod, db, q + " order by 1")
    return dict(line.rsplit(" ", 1) for line in out.splitlines() if line.strip())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("namespace")
    ap.add_argument("cluster")
    ap.add_argument("--keep", action="store_true", help="leave the restore namespace for inspection")
    ap.add_argument("--dry-run", action="store_true", help="print the manifests only")
    a = ap.parse_args()
    ns, cluster = a.namespace, a.cluster
    base = cluster.removesuffix("-postgres")
    rns = f"{cluster}-restore-test"[:63]

    src = json.loads(k("-n", ns, "get", "clusters.postgresql.cnpg.io", cluster, "-o", "json"))
    spec = src["spec"]
    plugins = [p for p in spec.get("plugins", []) if p.get("name") == PLUGIN]
    if not plugins:
        sys.exit(f"{ns}/{cluster} has no {PLUGIN} plugin; nothing to restore from")
    store = plugins[0]["parameters"]["barmanObjectName"]
    ostore = json.loads(k("-n", ns, "get", "objectstores.barmancloud.cnpg.io", store, "-o", "json"))
    rw = ostore.get("status", {}).get("serverRecoveryWindow", {}).get(cluster, {})
    if not rw.get("lastSuccessfulBackupTime"):
        sys.exit(f"{store} reports no successful base backup for {cluster} yet")
    initdb = spec.get("bootstrap", {}).get("initdb", {})
    db, owner = initdb.get("database", "app"), initdb.get("owner", "app")

    pg = dict(spec.get("postgresql") or {})
    params = dict(pg.get("parameters") or {})
    params["archive_mode"] = "off"      # the restore must never archive anywhere
    pg["parameters"] = params

    storage = {"size": spec["storage"]["size"]}
    if spec["storage"].get("storageClass"):
        storage["storageClass"] = spec["storage"]["storageClass"]

    cfg = json.loads(json.dumps(ostore["spec"]["configuration"]))
    for f in ("accessKeyId", "secretAccessKey", "region"):
        cfg["s3Credentials"][f]["name"] = f"{base}-cnpg-s3-ro"

    docs = [
        {"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": rns}},
        {"apiVersion": "external-secrets.io/v1", "kind": "ExternalSecret",
         "metadata": {"name": f"{base}-cnpg-s3-ro", "namespace": rns},
         "spec": {"refreshInterval": "0",
                  "secretStoreRef": {"kind": "ClusterSecretStore", "name": "bitwarden-secretsmanager"},
                  "target": {"name": f"{base}-cnpg-s3-ro", "creationPolicy": "Owner", "deletionPolicy": "Delete",
                             "template": {"engineVersion": "v2", "data": {
                                 "ACCESS_KEY_ID": "{{ .accessKey }}", "ACCESS_SECRET_KEY": "{{ .secretKey }}",
                                 "REGION": "garage"}}},
                  "data": [{"secretKey": "accessKey", "remoteRef": {"key": f"{base}-cnpg-s3-ro-access-key"}},
                           {"secretKey": "secretKey", "remoteRef": {"key": f"{base}-cnpg-s3-ro-secret-key"}}]}},
        {"apiVersion": "barmancloud.cnpg.io/v1", "kind": "ObjectStore",
         "metadata": {"name": f"{store}-ro", "namespace": rns},
         "spec": {"configuration": cfg,
                  **({"instanceSidecarConfiguration": ostore["spec"]["instanceSidecarConfiguration"]}
                     if ostore["spec"].get("instanceSidecarConfiguration") else {})}},
        {"apiVersion": "postgresql.cnpg.io/v1", "kind": "Cluster",
         "metadata": {"name": f"{cluster}-restore", "namespace": rns},
         "spec": {"instances": 1,
                  **({"imageName": spec["imageName"]} if spec.get("imageName") else {}),
                  "postgresql": pg, "storage": storage,
                  "bootstrap": {"recovery": {"source": "origin", "database": db, "owner": owner}},
                  "externalClusters": [{"name": "origin", "plugin": {
                      "name": PLUGIN, "parameters": {"barmanObjectName": f"{store}-ro", "serverName": cluster}}}]}},
    ]
    manifest = "\n".join(json.dumps(d) for d in docs)
    if a.dry_run:
        print(json.dumps(docs, indent=2))
        return

    if k("get", "ns", rns, check=False).strip():
        sys.exit(f"namespace {rns} already exists; delete it first")
    print(f"drill     {ns}/{cluster} -> {rns} (store {store}, last backup {rw['lastSuccessfulBackupTime']})")
    t0 = time.time()
    k("apply", "-f", "-", input=manifest)
    try:
        phase = ""
        for _ in range(80):   # up to 20 min
            phase = k("-n", rns, "get", "clusters.postgresql.cnpg.io", f"{cluster}-restore",
                      "-o", "jsonpath={.status.phase}", check=False)
            if phase == "Cluster in healthy state":
                break
            time.sleep(15)
        took = int(time.time() - t0)
        if phase != "Cluster in healthy state":
            print(f"FAIL      restore not healthy after {took}s (phase: {phase or 'none'})")
            print(k("-n", rns, "get", "pods", check=False))
            sys.exit(2)
        print(f"restored  healthy in {took}s")

        prod = counts(ns, f"{cluster}-1", db)
        rest = counts(rns, f"{cluster}-restore-1", db)
        diff = {t: (prod.get(t, "MISSING"), rest.get(t, "MISSING"))
                for t in sorted(set(prod) | set(rest)) if prod.get(t) != rest.get(t)}
        print(f"tables    prod={len(prod)} restore={len(rest)}")
        print(f"rows      prod={sum(int(v) for v in prod.values())} restore={sum(int(v) for v in rest.values())}")
        if diff:
            print("DIFF      table: prod / restore  (differences after the recovery point are expected on a busy DB)")
            for t, (p, r) in diff.items():
                print(f"          {t}: {p} / {r}")
        else:
            print("MATCH     identical table list and row counts")
        size = psql(rns, f"{cluster}-restore-1", db,
                    f"select pg_size_pretty(pg_database_size('{db}'))").strip()
        print(f"size      restore={size}")
    finally:
        if a.keep:
            print(f"kept      namespace {rns} (delete with: kubectl delete ns {rns})")
        else:
            k("delete", "ns", rns, "--wait=true", "--timeout=300s", check=False)
            print(f"cleanup   namespace {rns} deleted")


if __name__ == "__main__":
    main()

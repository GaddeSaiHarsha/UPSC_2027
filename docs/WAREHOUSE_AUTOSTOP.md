# Databricks SQL Warehouse Auto-Stop

## Why it matters

When the morning pipeline (NB6 → NB9) finishes, the SQL Warehouse idles but keeps
billing DBUs until it auto-stops.  Setting auto-stop to **5 minutes** cuts idle
cost to essentially zero.

## One-command fix (REST API via curl)

```bash
export DATABRICKS_HOST="https://adb-7405615460529826.6.azuredatabricks.net"
export DATABRICKS_TOKEN="<your PAT>"
export WAREHOUSE_ID="589dccbdf8c6e4c9"   # your SQL warehouse ID

curl -s -X POST \
  "${DATABRICKS_HOST}/api/2.0/sql/warehouses/${WAREHOUSE_ID}/edit" \
  -H "Authorization: Bearer ${DATABRICKS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"auto_stop_mins": 5}'
```

A successful response is an empty JSON object `{}`.

## Python script

A ready-to-run script lives at `scripts/set_warehouse_autostop.py`:

```bash
export DATABRICKS_HOST="https://adb-7405615460529826.6.azuredatabricks.net"
export DATABRICKS_TOKEN="<your PAT>"
python3 scripts/set_warehouse_autostop.py
```

Options:
```
--warehouse-id  ID    Override warehouse ID (default: 589dccbdf8c6e4c9)
--minutes       N     Auto-stop timeout (default: 5)
--dry-run             Print current config, make no changes
```

## Verify via Databricks UI

1. Databricks → **SQL Warehouses** → select your warehouse
2. **Edit** → **Auto-stop** → confirm it shows **5 minutes**

## Recommended: run once after initial setup

You only need to run this once.  The setting persists across warehouse restarts.
It does **not** affect query performance — the warehouse starts back up
automatically when NB6 fires at 7 AM IST.

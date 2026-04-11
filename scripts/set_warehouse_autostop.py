#!/usr/bin/env python3
"""
set_warehouse_autostop.py
=========================
Sets the Databricks SQL Warehouse auto-stop to 5 minutes to avoid
idle DBU charges.

Usage:
    export DATABRICKS_HOST=https://adb-7405615460529826.6.azuredatabricks.net
    export DATABRICKS_TOKEN=<your PAT>
    python3 scripts/set_warehouse_autostop.py

    # Or pass a custom warehouse ID:
    python3 scripts/set_warehouse_autostop.py --warehouse-id <id>

    # Dry run (just prints the current config):
    python3 scripts/set_warehouse_autostop.py --dry-run
"""

import argparse
import json
import os
import sys

import requests

# ── Defaults ──────────────────────────────────────────────────────────────
DEFAULT_WAREHOUSE_ID = "589dccbdf8c6e4c9"
AUTO_STOP_MINS = 5


def get_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def get_warehouse(host: str, token: str, warehouse_id: str) -> dict:
    url = f"{host}/api/2.0/sql/warehouses/{warehouse_id}"
    resp = requests.get(url, headers=get_headers(token), timeout=30)
    resp.raise_for_status()
    return resp.json()


def set_autostop(host: str, token: str, warehouse_id: str, minutes: int) -> dict:
    url = f"{host}/api/2.0/sql/warehouses/{warehouse_id}/edit"
    payload = {"auto_stop_mins": minutes}
    resp = requests.post(url, headers=get_headers(token), json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def main() -> int:
    parser = argparse.ArgumentParser(description="Set Databricks SQL Warehouse auto-stop")
    parser.add_argument("--warehouse-id", default=DEFAULT_WAREHOUSE_ID,
                        help="Warehouse ID (default: %(default)s)")
    parser.add_argument("--minutes", type=int, default=AUTO_STOP_MINS,
                        help="Auto-stop timeout in minutes (default: %(default)s)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print current config without making changes")
    args = parser.parse_args()

    host = os.environ.get("DATABRICKS_HOST", "").rstrip("/")
    token = os.environ.get("DATABRICKS_TOKEN", "")

    if not host or not token:
        print("❌  DATABRICKS_HOST and DATABRICKS_TOKEN must be set as environment variables.")
        return 1

    print(f"Warehouse ID : {args.warehouse_id}")
    print(f"Host         : {host}")

    try:
        info = get_warehouse(host, token, args.warehouse_id)
    except requests.HTTPError as exc:
        print(f"❌  Failed to fetch warehouse info: {exc}")
        return 1

    current = info.get("auto_stop_mins", "unknown")
    print(f"Current auto-stop : {current} minutes")

    if args.dry_run:
        print("Dry-run mode — no changes made.")
        return 0

    if current == args.minutes:
        print(f"✅  Already set to {args.minutes} minutes — nothing to do.")
        return 0

    print(f"Setting auto-stop to {args.minutes} minutes …")
    try:
        set_autostop(host, token, args.warehouse_id, args.minutes)
    except requests.HTTPError as exc:
        print(f"❌  Failed to update warehouse: {exc}")
        return 1

    print(f"✅  Auto-stop set to {args.minutes} minutes.")
    print("    The warehouse will now stop after 5 minutes of inactivity,")
    print("    saving DBUs when the morning pipeline finishes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

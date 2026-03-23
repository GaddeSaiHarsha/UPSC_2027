#!/usr/bin/env python3
"""
UPSC Obsidian Vault Sync — Databricks Volume → Local Mac
=========================================================
Syncs the entire UPSC_2026 vault from Databricks Volumes to local Obsidian.
Uses Databricks CLI v2. Runs via launchd at 8:15 AM IST daily.

Usage:
  python3 sync_from_databricks.py              # full sync
  python3 sync_from_databricks.py --ca-only     # only today's CA notes
  python3 sync_from_databricks.py --dry-run     # preview without copying
"""

import json, os, subprocess, sys, logging
from pathlib import Path
from datetime import date, datetime

# ── Config ──
CONFIG_PATH = Path(__file__).parent / "sync_config.json"
with open(CONFIG_PATH) as f:
    config = json.load(f)

LOCAL_VAULT = Path(config["local_vault_path"]).expanduser()
VOLUME_BASE = "dbfs:" + config["volume_ca_path"] + "/UPSC_2026"
HOST = config["databricks_host"]
LOG_FILE = LOCAL_VAULT / "07_Sync" / "sync.log"

# ── Logging ──
LOCAL_VAULT.mkdir(parents=True, exist_ok=True)
(LOCAL_VAULT / "07_Sync").mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, mode="a"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("upsc_sync")

# ── CLI Helper ──
def run_cli(args, timeout=120):
    """Run a Databricks CLI command and return (success, stdout, stderr)."""
    cmd = ["databricks"] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0, result.stdout, result.stderr
    except FileNotFoundError:
        return False, "", "Databricks CLI not found. Run: brew install databricks/tap/databricks"
    except subprocess.TimeoutExpired:
        return False, "", f"Timeout after {timeout}s"

def sync_folder(remote_path, local_path, dry_run=False):
    """Sync a remote Volume folder to local using CLI v2."""
    local_path.mkdir(parents=True, exist_ok=True)
    
    if dry_run:
        log.info(f"  [DRY RUN] Would sync: {remote_path} -> {local_path}")
        return True
    
    # Use 'databricks fs cp -r' for recursive copy
    ok, out, err = run_cli(
        ["fs", "cp", "-r", "--overwrite", remote_path, str(local_path)],
        timeout=300
    )
    if ok:
        log.info(f"  Synced: {remote_path}")
        return True
    else:
        log.error(f"  Failed: {remote_path} -> {err.strip()}")
        return False

def main():
    ca_only = "--ca-only" in sys.argv
    dry_run = "--dry-run" in sys.argv
    today = date.today()
    month_folder = today.strftime("%m-%B")
    
    log.info("=" * 60)
    log.info(f"UPSC Vault Sync | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info(f"Mode: {'CA-only' if ca_only else 'Full vault'} | {'DRY RUN' if dry_run else 'LIVE'}")
    log.info(f"Remote: {VOLUME_BASE}")
    log.info(f"Local:  {LOCAL_VAULT}")
    log.info("=" * 60)
    
    # Test CLI connectivity
    ok, out, err = run_cli(["auth", "env"])
    if not ok:
        log.error(f"CLI auth failed: {err.strip()}")
        log.error("Run: databricks configure --profile upsc")
        sys.exit(1)
    
    success_count = 0
    fail_count = 0
    
    if ca_only:
        # Sync only today's CA folder
        folders = [
            (f"{VOLUME_BASE}/01_Current_Affairs/2026/{month_folder}",
             LOCAL_VAULT / "01_Current_Affairs" / "2026" / month_folder),
        ]
    else:
        # Full vault sync — all content folders
        folders = [
            # Dashboard & config
            (f"{VOLUME_BASE}/.obsidian", LOCAL_VAULT / ".obsidian"),
            (f"{VOLUME_BASE}/.claude", LOCAL_VAULT / ".claude"),
            (f"{VOLUME_BASE}/00_Dashboard", LOCAL_VAULT / "00_Dashboard"),
            # Current Affairs (full tree)
            (f"{VOLUME_BASE}/01_Current_Affairs", LOCAL_VAULT / "01_Current_Affairs"),
            # Subject notes
            (f"{VOLUME_BASE}/02_Subjects", LOCAL_VAULT / "02_Subjects"),
            # PYQs
            (f"{VOLUME_BASE}/03_PYQs", LOCAL_VAULT / "03_PYQs"),
            # Traps (refreshed daily by NB6)
            (f"{VOLUME_BASE}/04_Traps", LOCAL_VAULT / "04_Traps"),
            # Revision schedule
            (f"{VOLUME_BASE}/05_Revision", LOCAL_VAULT / "05_Revision"),
            # Answer practice (populated by NB7 Practice Generator)
            (f"{VOLUME_BASE}/06_Answer_Practice", LOCAL_VAULT / "06_Answer_Practice"),
            # Sync config + templates
            (f"{VOLUME_BASE}/07_Sync", LOCAL_VAULT / "07_Sync"),
            (f"{VOLUME_BASE}/Templates", LOCAL_VAULT / "Templates"),
        ]
    
    for remote, local in folders:
        ok = sync_folder(remote, local, dry_run)
        if ok:
            success_count += 1
        else:
            fail_count += 1
    
    # Summary
    log.info("-" * 40)
    log.info(f"Done: {success_count} synced, {fail_count} failed")
    
    if fail_count == 0:
        log.info("Vault ready in Obsidian!")
    else:
        log.warning(f"{fail_count} folders failed — check sync.log")

if __name__ == "__main__":
    main()

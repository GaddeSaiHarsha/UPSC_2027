#!/usr/bin/env python3
"""
hermes_healthcheck.py — Non-destructive Hermes bot health checker
==================================================================
Validates that hermes_full.py is importable, required environment
variables are present, and key bot components are reachable.

Does NOT start the Telegram bot or make any real API calls.
Safe to run in CI and in cron environments.

Exit codes:
  0 — all checks passed (or only optional checks failed)
  1 — one or more required checks failed
"""

import ast
import importlib.util
import os
import sys
from pathlib import Path

# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #
PASS = "✅"
FAIL = "❌"
WARN = "⚠️ "

_failures: list[str] = []
_warnings: list[str] = []


def check(label: str, ok: bool, msg: str = "", required: bool = True) -> bool:
    status = PASS if ok else (FAIL if required else WARN)
    detail = f" — {msg}" if msg else ""
    print(f"  {status} {label}{detail}")
    if not ok:
        if required:
            _failures.append(label)
        else:
            _warnings.append(label)
    return ok


# ------------------------------------------------------------------ #
# 1. File existence checks
# ------------------------------------------------------------------ #
def check_files() -> None:
    print("\n[1] File existence checks")
    repo_root = Path(__file__).resolve().parent.parent
    check("bot_code/hermes_full.py exists", (repo_root / "bot_code" / "hermes_full.py").is_file())
    check("scripts/hermes_healthcheck.py exists", (repo_root / "scripts" / "hermes_healthcheck.py").is_file())
    check(
        ".github/workflows/hermes-ci.yml exists",
        (repo_root / ".github" / "workflows" / "hermes-ci.yml").is_file(),
    )
    check(
        ".github/workflows/hermes-scheduled-health.yml exists",
        (repo_root / ".github" / "workflows" / "hermes-scheduled-health.yml").is_file(),
    )


# ------------------------------------------------------------------ #
# 2. Syntax / compile check
# ------------------------------------------------------------------ #
def check_syntax() -> None:
    print("\n[2] Syntax / compile checks")
    repo_root = Path(__file__).resolve().parent.parent
    bot_file = repo_root / "bot_code" / "hermes_full.py"
    if not bot_file.is_file():
        check("hermes_full.py syntax", False, "file missing — skipping")
        return
    try:
        source = bot_file.read_text(encoding="utf-8")
        ast.parse(source, filename=str(bot_file))
        check("hermes_full.py syntax (AST parse)", True)
    except SyntaxError as exc:
        check("hermes_full.py syntax (AST parse)", False, str(exc))


# ------------------------------------------------------------------ #
# 3. Required imports available
# ------------------------------------------------------------------ #
def check_imports() -> None:
    print("\n[3] Required Python package checks")
    packages = {
        "groq": True,        # required
        "telegram": True,    # required (python-telegram-bot)
        "requests": True,    # required
        "sqlite3": True,     # stdlib — always present
        "asyncio": True,     # stdlib
    }
    for pkg, required in packages.items():
        spec = importlib.util.find_spec(pkg)
        check(f"import {pkg}", spec is not None, required=required)


# ------------------------------------------------------------------ #
# 4. Environment variable checks
# ------------------------------------------------------------------ #
def check_env_vars() -> None:
    print("\n[4] Environment variable checks")

    required_vars = ["HERMES_BOT_TOKEN", "GROQ_API_KEY"]
    optional_vars = [
        "TELEGRAM_USER_ID",
        "DATABRICKS_HOST",
        "DATABRICKS_TOKEN",
        "DATABRICKS_SQL_WAREHOUSE_ID",
        "VAULT_PATH",
        "HERMES_DB",
    ]

    for var in required_vars:
        val = os.environ.get(var, "")
        check(f"{var} is set", bool(val), required=True)

    for var in optional_vars:
        val = os.environ.get(var, "")
        check(f"{var} is set", bool(val), required=False)


# ------------------------------------------------------------------ #
# 5. Bot token format check (no live API call)
# ------------------------------------------------------------------ #
def check_token_format() -> None:
    print("\n[5] Bot token format check (offline)")
    token = os.environ.get("HERMES_BOT_TOKEN", "")
    if not token:
        print(f"  {WARN} HERMES_BOT_TOKEN format — not set, skipping format check")
        return
    # Telegram bot tokens are always: <digits>:<alphanumeric_and_underscores>
    import re
    ok = bool(re.match(r"^\d+:[A-Za-z0-9_-]{35,}$", token))
    check("HERMES_BOT_TOKEN format looks valid", ok,
          "expected format: <bot_id>:<secret>" if not ok else "")


# ------------------------------------------------------------------ #
# Main
# ------------------------------------------------------------------ #
def main() -> int:
    print("=" * 60)
    print("Hermes Health Check")
    print("=" * 60)

    check_files()
    check_syntax()
    check_imports()
    check_env_vars()
    check_token_format()

    print("\n" + "=" * 60)
    if _failures:
        print(f"{FAIL} Health check FAILED — {len(_failures)} required check(s) failed:")
        for f in _failures:
            print(f"   • {f}")
        if _warnings:
            print(f"\n{WARN} {len(_warnings)} optional check(s) also failed (non-blocking):")
            for w in _warnings:
                print(f"   • {w}")
        print("=" * 60)
        return 1

    if _warnings:
        print(f"✅ Health check PASSED (with {len(_warnings)} optional warning(s))")
        for w in _warnings:
            print(f"   {WARN} {w}")
    else:
        print("✅ Health check PASSED — all checks green")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())

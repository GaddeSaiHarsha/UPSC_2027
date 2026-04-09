# Hermes GitHub Actions Guide

Step-by-step instructions for secrets setup, manual workflow runs, and interpreting smoke/health run results.

---

## 1. Where to Add GitHub Actions Secrets

Secrets are encrypted variables that GitHub Actions workflows read at runtime.  
**Never put real tokens in `.yml` files or source code.**

### Step-by-step

1. Go to your repository on GitHub:  
   `https://github.com/GaddeSaiHarsha/UPSC_2027`

2. Click **Settings** (top tab of the repo, not your profile settings).

3. In the left sidebar, click **Secrets and variables → Actions**.

4. Click **New repository secret**.

5. Add each secret below one at a time — paste the name exactly, then paste the value.

---

### Required Secrets (workflows will fail without these)

| Secret Name | Where to get it | Example format |
|---|---|---|
| `HERMES_BOT_TOKEN` | BotFather on Telegram → `/mybots` → select bot → API Token | `7123456789:AAFxyz...` |
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) → API Keys | `gsk_...` |

### Optional Secrets (enable Databricks + heartbeat features)

| Secret Name | Where to get it | Notes |
|---|---|---|
| `TELEGRAM_USER_ID` | Your numeric Telegram user ID (use [@userinfobot](https://t.me/userinfobot)) | Needed for Telegram heartbeat messages |
| `DATABRICKS_HOST` | Databricks workspace URL | `https://adb-7405615460529826.6.azuredatabricks.net` |
| `DATABRICKS_TOKEN` | Databricks → User Settings → Developer → Access Tokens | `dapi...` |
| `DATABRICKS_SQL_WAREHOUSE_ID` | Databricks → SQL Warehouses → your warehouse → Connection Details | `589dccbdf8c6e4c9` |

> **Tip:** If you only want CI smoke tests (no live bot), you only need `HERMES_BOT_TOKEN` and `GROQ_API_KEY`.

---

## 2. How to Manually Run Workflows (workflow_dispatch)

Both workflows support **manual triggering** from the GitHub Actions tab, no code push required.

### Steps

1. Go to your repository on GitHub.

2. Click the **Actions** tab (top navigation bar).

3. In the left sidebar, click the workflow you want to run:
   - **"Hermes CI"** — syntax check + smoke test
   - **"Hermes Scheduled Health Check"** — full secret/environment health check

4. On the right side, click **"Run workflow"** (a dropdown button).

5. Choose the branch (default is `main`).

6. Fill in any optional inputs:
   - **Hermes CI** → `run_smoke_test`: choose `true` (default) or `false`
   - **Hermes Scheduled Health Check** → `send_telegram_heartbeat`: choose `true` to receive a Telegram message on success, `false` (default) to skip

7. Click the green **"Run workflow"** button.

8. Refresh the page — a new run will appear in the list. Click it to watch logs in real time.

---

## 3. What to Expect from a Smoke Run / Health Run

### Hermes CI (smoke test)

This workflow runs on every push/PR to `bot_code/`, `scripts/`, or `.github/workflows/`, and can also be triggered manually.

**Steps it runs:**

| Step | What it checks | Expected result |
|---|---|---|
| Checkout | Clones repo | Always passes |
| Set up Python | Installs Python 3.11 | Always passes |
| Install dependencies | `pip install groq python-telegram-bot requests` | ✅ Pass if PyPI is reachable |
| Syntax check — hermes_full.py | `python -m py_compile` | ✅ Pass if no syntax errors |
| Syntax check — health script | `python -m py_compile` | ✅ Pass always |
| Smoke test — import and static checks | Runs `scripts/hermes_healthcheck.py` | See outcome table below |

**Smoke test outcome table:**

| Secrets configured? | Expected outcome |
|---|---|
| `HERMES_BOT_TOKEN` + `GROQ_API_KEY` set | ✅ All required checks pass |
| Missing `HERMES_BOT_TOKEN` or `GROQ_API_KEY` | ❌ Fails with "required check(s) failed" |
| Only optional secrets missing | ✅ Passes with warnings (non-blocking) |
| Syntax error introduced in `hermes_full.py` | ❌ Fails at "Syntax check" step |

**Typical successful smoke run output:**
```
============================================================
Hermes Health Check
============================================================

[1] File existence checks
  ✅ bot_code/hermes_full.py exists
  ✅ scripts/hermes_healthcheck.py exists
  ✅ .github/workflows/hermes-ci.yml exists
  ✅ .github/workflows/hermes-scheduled-health.yml exists

[2] Syntax / compile checks
  ✅ hermes_full.py syntax (AST parse)

[3] Required Python package checks
  ✅ import groq
  ✅ import telegram
  ✅ import requests
  ✅ import sqlite3
  ✅ import asyncio

[4] Environment variable checks
  ✅ HERMES_BOT_TOKEN is set
  ✅ GROQ_API_KEY is set
  ⚠️  TELEGRAM_USER_ID is set  ← warning (optional)
  ⚠️  DATABRICKS_HOST is set   ← warning (optional)
  ...

[5] Bot token format check (offline)
  ✅ HERMES_BOT_TOKEN format looks valid

============================================================
✅ Health check PASSED (with N optional warning(s))
============================================================
```

---

### Hermes Scheduled Health Check

Runs automatically every day at **09:00 IST (03:30 UTC)** after the Databricks NB9 backup job completes.  
Can also be triggered manually (see Section 2 above).

**Steps it runs:**

| Step | What it checks | Expected result |
|---|---|---|
| Verify required secrets | Checks `HERMES_BOT_TOKEN` and `GROQ_API_KEY` env vars | ✅ Pass if both are set |
| Run health check script | Full `hermes_healthcheck.py` run | ✅ Pass if bot code is healthy |
| Send Telegram heartbeat | Sends a Telegram message to your user ID | ✅ Pass if enabled and secrets set; skipped if disabled |

**Telegram heartbeat message (when enabled):**
```
✅ Hermes Health Check Passed
Time: 2026-04-09 03:30 UTC
Bot code: syntax OK, imports OK
Status: all checks green 🟢
```

**Common failure scenarios and fixes:**

| Failure message | Cause | Fix |
|---|---|---|
| `❌ HERMES_BOT_TOKEN is not set` | Secret not added to repo | Add it in Settings → Secrets → Actions |
| `❌ GROQ_API_KEY is not set` | Secret not added to repo | Add it in Settings → Secrets → Actions |
| `❌ hermes_full.py syntax (AST parse)` | Syntax error in bot code | Fix the syntax error in `bot_code/hermes_full.py` |
| `❌ import groq` | Package not installable | Check PyPI availability; usually a transient failure |
| `⚠️ Telegram heartbeat send failed: 401` | Bot token is wrong or revoked | Re-generate token via BotFather, update secret |

---

## 4. Important Notes

- **GitHub Actions cannot host a 24/7 Telegram bot.** Workflow runners terminate after the job finishes. Use a persistent runtime (Fly.io, Render, Railway, Azure VM, etc.) to run `hermes_full.py` long-term.
- The smoke test and health check are **non-destructive** — they never start the Telegram polling loop or make live API calls to Groq/Databricks.
- The scheduled health check runs at 03:30 UTC (09:00 IST) daily to align with the Databricks NB9 backup job schedule.
- Workflow logs are retained for 90 days by default. You can view them in the **Actions** tab.

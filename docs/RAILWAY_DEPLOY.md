# Hermes Bot — Railway Deploy (5-min setup)

## Step 1 — Create Railway project
1. Go to [railway.app](https://railway.app) → New Project → **Deploy from GitHub repo**
2. Select `GaddeSaiHarsha/UPSC_2027`
3. Railway auto-detects `railway.toml` → click **Deploy**

## Step 2 — Set environment variables
In Railway → your service → **Variables** tab, add these 5:

| Variable | Value |
|---|---|
| `HERMES_BOT_TOKEN` | Token from BotFather (create new bot or use existing) |
| `GROQ_API_KEY` | From [console.groq.com](https://console.groq.com) — free tier |
| `TELEGRAM_USER_ID` | Your numeric Telegram ID (get from [@userinfobot](https://t.me/userinfobot)) |
| `DATABRICKS_HOST` | `https://adb-7405615460529826.6.azuredatabricks.net` |
| `DATABRICKS_TOKEN` | Your Databricks PAT (from Databricks → User Settings → Tokens) |

Optional (has defaults):
| Variable | Default | Override if needed |
|---|---|---|
| `DATABRICKS_SQL_WAREHOUSE_ID` | `589dccbdf8c6e4c9` | Only if warehouse changed |
| `VAULT_PATH` | `~/UPSC_2026` | Not needed on Railway |

## Step 3 — Redeploy
Railway → your service → **Redeploy** (or it auto-deploys on env var save)

## Step 4 — Sanity check via Telegram
Send these to your Hermes bot in order:

```
/start          → should greet you as Gad
/stats          → shows session stats (DB working)
/teach Article 356    → short AI response (Groq working)
/quiz polity 1        → 1 MCQ (stateful session working)
```

If `/teach` replies in ~3-5 seconds → **all systems go**.

## Logs
Railway → your service → **Logs** tab — live tail.

Look for:
```
Hermes V1.8 starting...
Bot polling started
```

## Cost
- Railway free tier: 500 hrs/month (enough for 24/7 if only 1 service)
- Groq: free tier (~14,400 req/day) — sufficient
- Total: **$0/month**

## Quick local test (before Railway deploy)
```bash
cd /workspaces/UPSC_2027
export HERMES_BOT_TOKEN=your_token
export GROQ_API_KEY=your_key
export TELEGRAM_USER_ID=your_id
pip install -r bot_code/requirements.txt
python bot_code/hermes_full.py
```

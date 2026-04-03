# Databricks notebook source
import requests

TOKEN = "8788057001:AAEFvfaypZfw18wPJN94K2YPCbMpP6ttAWA"
BASE = f"https://api.telegram.org/bot{TOKEN}"

# Check bot identity
me = requests.get(f"{BASE}/getMe").json()
print("Bot:", me.get("result", {}).get("username"), "- OK" if me.get("ok") else "- ERROR")

# Check for queued (unprocessed) updates
updates = requests.get(f"{BASE}/getUpdates", params={"limit": 10, "timeout": 1}).json()
pending = updates.get("result", [])
print(f"\nPending unprocessed messages: {len(pending)}")
for u in pending[-5:]:
    msg = u.get("message", {})
    text = msg.get("text", "")
    dt = msg.get("date", 0)
    from datetime import datetime
    ts = datetime.utcfromtimestamp(dt).strftime("%H:%M:%S UTC") if dt else "?"
    print(f"  [{ts}] {text}")

# COMMAND ----------

# DBTITLE 1,Clear stale Telegram pending messages
import requests

TOKEN = "8788057001:AAEFvfaypZfw18wPJN94K2YPCbMpP6ttAWA"
BASE = f"https://api.telegram.org/bot{TOKEN}"

# Get pending updates
updates = requests.get(f"{BASE}/getUpdates", params={"limit": 100, "timeout": 1}).json()
pending = updates.get("result", [])
print(f"Pending messages: {len(pending)}")

if pending:
    last_id = pending[-1]["update_id"]
    print(f"Last update_id: {last_id}")
    # Clear by acknowledging all
    clear = requests.get(f"{BASE}/getUpdates", params={"offset": last_id + 1, "timeout": 1}).json()
    print(f"Cleared. Remaining: {len(clear.get('result', []))}")
else:
    print("No pending messages to clear")

# COMMAND ----------

# DBTITLE 1,VM Deployment Guide
# MAGIC %md
# MAGIC # Deploy UPSC Telegram Bot to Azure VM — Always-On
# MAGIC
# MAGIC ## Prerequisites
# MAGIC * Your existing Azure VM (SSH access)
# MAGIC * Databricks PAT token (for agent + SQL warehouse calls)
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Step 1: SSH into your VM
# MAGIC ```bash
# MAGIC ssh <your-user>@<your-vm-ip>
# MAGIC ```
# MAGIC
# MAGIC ## Step 2: Install Python + dependencies
# MAGIC ```bash
# MAGIC sudo apt update && sudo apt install -y python3 python3-pip
# MAGIC pip3 install python-telegram-bot requests
# MAGIC ```
# MAGIC
# MAGIC ## Step 3: Create bot directory
# MAGIC ```bash
# MAGIC mkdir -p ~/upsc_bot
# MAGIC cd ~/upsc_bot
# MAGIC ```
# MAGIC
# MAGIC ## Step 4: Download bot from Databricks workspace
# MAGIC Run this on the VM (replace `<YOUR_PAT>` with your Databricks PAT):
# MAGIC ```bash
# MAGIC curl -s -H "Authorization: Bearer <YOUR_PAT>" \
# MAGIC   "https://adb-7405615460529826.6.azuredatabricks.net/api/2.0/workspace/export?path=/Users/admin@mngenvmcap915189.onmicrosoft.com/upsc_telegram_bot_v23.py&format=SOURCE" \
# MAGIC   | python3 -c "import sys,json,base64; print(base64.b64decode(json.load(sys.stdin)['content']).decode())" \
# MAGIC   > upsc_telegram_bot.py
# MAGIC ```
# MAGIC
# MAGIC ## Step 5: Create environment file
# MAGIC ```bash
# MAGIC cat > ~/upsc_bot/.env << 'EOF'
# MAGIC export TELEGRAM_BOT_TOKEN="8788057001:AAEFvfaypZfw18wPJN94K2YPCbMpP6ttAWA"
# MAGIC export DATABRICKS_HOST="https://adb-7405615460529826.6.azuredatabricks.net"
# MAGIC export DATABRICKS_TOKEN="<YOUR_DATABRICKS_PAT>"
# MAGIC export TELEGRAM_USER_ID="2022402970"
# MAGIC export DATABRICKS_SQL_WAREHOUSE_ID="589dccbdf8c6e4c9"
# MAGIC export VAULT_PATH="/home/$USER/upsc_bot/vault"
# MAGIC export MEMORY_DB="/home/$USER/upsc_bot/upsc_memory.db"
# MAGIC EOF
# MAGIC
# MAGIC mkdir -p ~/upsc_bot/vault
# MAGIC chmod 600 ~/upsc_bot/.env
# MAGIC ```
# MAGIC
# MAGIC ## Step 6: Create systemd service (auto-restart on crash/reboot)
# MAGIC ```bash
# MAGIC sudo tee /etc/systemd/system/upsc-bot.service << EOF
# MAGIC [Unit]
# MAGIC Description=UPSC Telegram Bot v2.4
# MAGIC After=network-online.target
# MAGIC Wants=network-online.target
# MAGIC
# MAGIC [Service]
# MAGIC Type=simple
# MAGIC User=$USER
# MAGIC WorkingDirectory=/home/$USER/upsc_bot
# MAGIC EnvironmentFile=/home/$USER/upsc_bot/.env
# MAGIC ExecStart=/usr/bin/python3 /home/$USER/upsc_bot/upsc_telegram_bot.py
# MAGIC Restart=always
# MAGIC RestartSec=10
# MAGIC StartLimitIntervalSec=60
# MAGIC StartLimitBurst=3
# MAGIC
# MAGIC [Install]
# MAGIC WantedBy=multi-user.target
# MAGIC EOF
# MAGIC ```
# MAGIC
# MAGIC ## Step 7: Start the bot
# MAGIC ```bash
# MAGIC sudo systemctl daemon-reload
# MAGIC sudo systemctl enable upsc-bot
# MAGIC sudo systemctl start upsc-bot
# MAGIC ```
# MAGIC
# MAGIC ## Step 8: Verify
# MAGIC ```bash
# MAGIC sudo systemctl status upsc-bot    # Should show "active (running)"
# MAGIC journalctl -u upsc-bot -f          # Live logs (Ctrl+C to exit)
# MAGIC ```
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Useful commands
# MAGIC ```bash
# MAGIC sudo systemctl restart upsc-bot    # Restart after code update
# MAGIC sudo systemctl stop upsc-bot       # Stop bot
# MAGIC journalctl -u upsc-bot --since "1 hour ago"  # Recent logs
# MAGIC ```
# MAGIC
# MAGIC ## Later: Upload v2.4 from Mac
# MAGIC When you're home, upload v2.4 to workspace, then on VM:
# MAGIC ```bash
# MAGIC curl -s -H "Authorization: Bearer <PAT>" \
# MAGIC   "https://adb-7405615460529826.6.azuredatabricks.net/api/2.0/workspace/export?path=/Users/admin@mngenvmcap915189.onmicrosoft.com/upsc_telegram_bot_v24.py&format=SOURCE" \
# MAGIC   | python3 -c "import sys,json,base64; print(base64.b64decode(json.load(sys.stdin)['content']).decode())" \
# MAGIC   > upsc_telegram_bot.py
# MAGIC sudo systemctl restart upsc-bot
# MAGIC ```

# COMMAND ----------

# DBTITLE 1,Quick Reference — Copy-paste commands
# MAGIC %md
# MAGIC ## Quick Reference — One-shot deploy (copy-paste all at once)
# MAGIC
# MAGIC After SSH into your VM, paste this **entire block** (replace `<YOUR_PAT>` first):
# MAGIC
# MAGIC ```bash
# MAGIC # === ONE-SHOT DEPLOY ===
# MAGIC sudo apt update && sudo apt install -y python3 python3-pip
# MAGIC pip3 install python-telegram-bot requests
# MAGIC
# MAGIC mkdir -p ~/upsc_bot/vault && cd ~/upsc_bot
# MAGIC
# MAGIC # Download bot from Databricks
# MAGIC curl -s -H "Authorization: Bearer <YOUR_PAT>" \
# MAGIC   "https://adb-7405615460529826.6.azuredatabricks.net/api/2.0/workspace/export?path=/Users/admin@mngenvmcap915189.onmicrosoft.com/upsc_telegram_bot_v23.py&format=SOURCE" \
# MAGIC   | python3 -c "import sys,json,base64; print(base64.b64decode(json.load(sys.stdin)['content']).decode())" \
# MAGIC   > upsc_telegram_bot.py
# MAGIC
# MAGIC # Create env file
# MAGIC cat > .env << 'EOF'
# MAGIC export TELEGRAM_BOT_TOKEN="8788057001:AAEFvfaypZfw18wPJN94K2YPCbMpP6ttAWA"
# MAGIC export DATABRICKS_HOST="https://adb-7405615460529826.6.azuredatabricks.net"
# MAGIC export DATABRICKS_TOKEN="<YOUR_PAT>"
# MAGIC export TELEGRAM_USER_ID="2022402970"
# MAGIC export DATABRICKS_SQL_WAREHOUSE_ID="589dccbdf8c6e4c9"
# MAGIC export VAULT_PATH="/home/$USER/upsc_bot/vault"
# MAGIC export MEMORY_DB="/home/$USER/upsc_bot/upsc_memory.db"
# MAGIC EOF
# MAGIC chmod 600 .env
# MAGIC
# MAGIC # Create systemd service
# MAGIC sudo tee /etc/systemd/system/upsc-bot.service << SVCEOF
# MAGIC [Unit]
# MAGIC Description=UPSC Telegram Bot
# MAGIC After=network-online.target
# MAGIC Wants=network-online.target
# MAGIC
# MAGIC [Service]
# MAGIC Type=simple
# MAGIC User=$USER
# MAGIC WorkingDirectory=/home/$USER/upsc_bot
# MAGIC EnvironmentFile=/home/$USER/upsc_bot/.env
# MAGIC ExecStart=/usr/bin/python3 /home/$USER/upsc_bot/upsc_telegram_bot.py
# MAGIC Restart=always
# MAGIC RestartSec=10
# MAGIC
# MAGIC [Install]
# MAGIC WantedBy=multi-user.target
# MAGIC SVCEOF
# MAGIC
# MAGIC # Start!
# MAGIC sudo systemctl daemon-reload
# MAGIC sudo systemctl enable upsc-bot
# MAGIC sudo systemctl start upsc-bot
# MAGIC
# MAGIC # Verify
# MAGIC sleep 3 && sudo systemctl status upsc-bot
# MAGIC ```
# MAGIC
# MAGIC ## ⚠️ Important Notes
# MAGIC 1. Replace `<YOUR_PAT>` in **two places** (curl command + .env file)
# MAGIC 2. Generate a new PAT: Workspace → User Settings → Developer → Access Tokens → Generate New
# MAGIC 3. This deploys **v2.3** from workspace. When home, upload v2.4 to workspace and re-download
# MAGIC 4. The `systemd` service auto-restarts on crash AND on VM reboot — truly always-on
# MAGIC 5. SQLite DB is created fresh on VM (your Mac DB history won't carry over unless you copy it)
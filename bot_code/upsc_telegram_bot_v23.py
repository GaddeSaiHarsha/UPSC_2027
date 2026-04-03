#!/usr/bin/env python3
"""
UPSC 2027 AIR 1-75 MEGA-BOT v2.3
================================
Databricks Agent (Llama 3.3 70B + 80,800 FAISS vectors)
+ SQLite Spaced Repetition Memory
+ 10 Active Learning Frameworks
+ Stage-specific UPSC Modules
+ Claude Code Bridge
+ Knowledge Graph (GraphRAG) Entity Relationships
+ Daily Practice Mobile Access (NEW in v2.3)
+ AI Playground / Tool-Calling Functions (NEW in v2.3)

v2.3 Changes:
  + /practice /podcast /insights /phone /files /raw
    (reads NB7+NB8 outputs from Delta + Volume -> sends to phone)
  + AI Playground tool_call() — use from Playground or any OpenAI-compatible client
  + Retry logic for agent cold starts
  + SQL Statement API for Delta queries (no Spark needed)
v2.2: + /graphrag (Knowledge Graph entity relationships via agent tool)

30 Commands:
  Core:     /start /teach /log /eod /daily /dump /stats /weak
  Prelims:  /quiz /trap /drill
  Mains:    /evaluate /model
  Active:   /socratic /feynman /why /visual /recall /simplify /progress
  Interview:/daf
  GraphRAG: /graphrag
  Mobile:   /practice /podcast /insights /phone /files /raw
  System:   /sync /help

=== SETUP (Windows / Mac / Linux) ===
  1. pip install python-telegram-bot requests
  2. Get a Telegram bot token: @BotFather -> /newbot
  3. Get your Telegram user ID: @userinfobot
  4. Get a Databricks PAT: Workspace -> User Settings -> Developer -> Access Tokens
  5. Set env vars:
       TELEGRAM_BOT_TOKEN=<token>
       DATABRICKS_TOKEN=<pat>
       TELEGRAM_USER_ID=<your_id>       (optional, locks bot to you)
       DATABRICKS_HOST=https://adb-7405615460529826.6.azuredatabricks.net
       DATABRICKS_SQL_WAREHOUSE_ID=589dccbdf8c6e4c9
       VAULT_PATH=C:\\UPSC_2026          (or ~/UPSC_2026 on Mac)
  6. python upsc_telegram_bot_v23.py

=== AI PLAYGROUND / TOOL CALLING ===
  The bot's core functions are also exposed as plain Python callables
  (Section 9) so you can register them as UC functions or use them
  in the AI Playground's function-calling mode with any served LLM.
  See: tool_definitions() for OpenAI-compatible tool schemas.
"""

import os, sqlite3, logging, requests, re, subprocess, glob, json, time
from datetime import datetime, date
from pathlib import Path
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ===============================================================
# CONFIG
# ===============================================================
BOT_TOKEN        = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
DATABRICKS_HOST  = os.environ.get("DATABRICKS_HOST", "https://adb-7405615460529826.6.azuredatabricks.net")
DATABRICKS_TOKEN = os.environ.get("DATABRICKS_TOKEN", "YOUR_PAT_HERE")
AGENT_ENDPOINT   = "agents_upsc_catalog-rag-upsc_tutor_agent"
VAULT_PATH       = os.environ.get("VAULT_PATH", r"C:\UPSC_2026")
DB_PATH          = os.environ.get("MEMORY_DB", r"C:\UPSC_2026\07_Sync\upsc_memory.db")
ALLOWED_USER_ID  = os.environ.get("TELEGRAM_USER_ID", "")
CLAUDE_MD_PATH   = os.environ.get("CLAUDE_MD", r"C:\UPSC_2026\.claude\CLAUDE.md")
DBR_CLI_PROFILE  = os.environ.get("DATABRICKS_CLI_PROFILE", "upsc")
SQL_WAREHOUSE_ID = os.environ.get("DATABRICKS_SQL_WAREHOUSE_ID", "589dccbdf8c6e4c9")

DAF_PROFILE = (
    "Candidate: Data Engineer based in Calgary, Alberta, Canada (Permanent Resident). "
    "Optional Subject: Telugu Literature. Background in Databricks, Azure, AI/ML pipelines. "
    "Migrated from India, understands both Canadian governance and Indian administration."
)

# v2.3: Volume path for Daily Practice files
VOLUME_BASE = "/Volumes/upsc_catalog/rag/obsidian_ca/Daily_Practice"

# v2.3: Text dividers (avoids f-string backslash issues on Python < 3.12)
DIVIDER = "\u2500" * 30
DIVIDER_WIDE = "=" * 40
DIVIDER_NARROW = "=" * 35

# v2.3: Retry config for agent cold starts
AGENT_RETRIES = 2
AGENT_RETRY_DELAY = 5  # seconds

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)
log = logging.getLogger("upsc_mega_bot")


# ===============================================================
# 1. SQLITE BRAIN
# ===============================================================

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS interactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT DEFAULT (datetime('now')),
        command TEXT, user_message TEXT, bot_response TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS weak_topics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject TEXT NOT NULL, topic TEXT NOT NULL,
        miss_count INTEGER DEFAULT 1, hit_count INTEGER DEFAULT 0,
        last_reviewed TEXT, source TEXT DEFAULT 'quiz',
        UNIQUE(subject, topic))""")
    c.execute("""CREATE TABLE IF NOT EXISTS quiz_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT DEFAULT (datetime('now')),
        subject TEXT, question TEXT, user_answer TEXT,
        was_correct INTEGER, score REAL, topic TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS daily_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL, content TEXT NOT NULL, file_path TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS concepts_taught (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT DEFAULT (datetime('now')),
        concept TEXT NOT NULL UNIQUE, revision_count INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS prelims_traps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic TEXT, trap_type TEXT, trap_description TEXT,
        date_logged TEXT DEFAULT (datetime('now')))""")
    c.execute("""CREATE TABLE IF NOT EXISTS mains_flaws (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        flaw_type TEXT NOT NULL, frequency INTEGER DEFAULT 1,
        last_seen TEXT DEFAULT (datetime('now')),
        UNIQUE(flaw_type))""")
    c.execute("""CREATE TABLE IF NOT EXISTS socratic_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT DEFAULT (datetime('now')),
        topic TEXT, depth_reached INTEGER DEFAULT 0)""")
    conn.commit()
    conn.close()
    log.info(f"Mega-Memory DB ready: {DB_PATH}")


def get_user_context():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    parts = []
    c.execute("""SELECT subject, topic, miss_count, last_reviewed
        FROM weak_topics ORDER BY miss_count DESC, last_reviewed ASC LIMIT 5""")
    weak = c.fetchall()
    if weak:
        parts.append("WEAK TOPICS:")
        for s, t, m, lr in weak:
            parts.append(f"  - {s}/{t}: missed {m}x, last: {lr or 'never'}")
    c.execute("SELECT trap_description FROM prelims_traps ORDER BY id DESC LIMIT 3")
    traps = c.fetchall()
    if traps:
        parts.append("KNOWN TRAPS:")
        for (trap,) in traps:
            parts.append(f"  - {trap[:100]}")
    c.execute("SELECT flaw_type, frequency FROM mains_flaws ORDER BY frequency DESC LIMIT 3")
    flaws = c.fetchall()
    if flaws:
        parts.append("MAINS FLAWS:")
        for f, n in flaws:
            parts.append(f"  - {f} ({n}x)")
    c.execute("""SELECT subject,
        ROUND(AVG(CASE WHEN was_correct=1 THEN 100.0 ELSE 0.0 END), 0) as pct,
        COUNT(*) as n
        FROM quiz_history WHERE timestamp >= date('now', '-7 days')
        GROUP BY subject ORDER BY pct ASC""")
    for s, p, n in c.fetchall():
        parts.append(f"Quiz 7d: {s} {p:.0f}% ({n} Qs)")
    c.execute("SELECT content FROM daily_logs WHERE date = date('now')")
    logs = c.fetchall()
    if logs:
        parts.append(f"TODAY'S LOG ({len(logs)} entries):")
        for (ct,) in logs:
            parts.append(f"  - {ct[:120]}")
    c.execute("SELECT COUNT(*) FROM interactions WHERE date(timestamp) = date('now')")
    parts.append(f"Interactions today: {c.fetchone()[0]}")
    conn.close()
    return "\n".join(parts) if parts else "First session."


def log_interaction(cmd, msg, resp):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO interactions(command,user_message,bot_response) VALUES(?,?,?)",
                 (cmd, msg, resp[:3000]))
    conn.commit()
    conn.close()

def log_concept(concept):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""INSERT INTO concepts_taught(concept) VALUES(?)
        ON CONFLICT(concept) DO UPDATE SET
        revision_count=revision_count+1, timestamp=datetime('now')""", (concept,))
    conn.commit()
    conn.close()

def log_weakness(subject, topic, source="quiz"):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""INSERT INTO weak_topics(subject,topic,miss_count,last_reviewed,source)
        VALUES(?,?,1,datetime('now'),?)
        ON CONFLICT(subject,topic) DO UPDATE SET
        miss_count=miss_count+1, last_reviewed=datetime('now')""",
                 (subject, topic, source))
    conn.commit()
    conn.close()

def log_mains_flaw(flaw_type):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""INSERT INTO mains_flaws(flaw_type) VALUES(?)
        ON CONFLICT(flaw_type) DO UPDATE SET
        frequency=frequency+1, last_seen=datetime('now')""", (flaw_type,))
    conn.commit()
    conn.close()


# ===============================================================
# 1b. CLAUDE.MD BRIDGE
# ===============================================================

def sync_claude_md():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    weak = c.execute("SELECT subject,topic,miss_count,last_reviewed FROM weak_topics ORDER BY miss_count DESC LIMIT 10").fetchall()
    traps = c.execute("SELECT trap_description,date_logged FROM prelims_traps WHERE date_logged>=date('now','-60 days') ORDER BY id DESC LIMIT 10").fetchall()
    flaws = c.execute("SELECT flaw_type,frequency FROM mains_flaws ORDER BY frequency DESC LIMIT 5").fetchall()
    quiz = c.execute("SELECT subject,ROUND(AVG(CASE WHEN was_correct=1 THEN 100.0 ELSE 0 END),0),COUNT(*) FROM quiz_history WHERE timestamp>=date('now','-7 days') GROUP BY subject ORDER BY 2 ASC").fetchall()
    concepts = c.execute("SELECT concept,revision_count FROM concepts_taught ORDER BY revision_count DESC LIMIT 15").fetchall()
    logs = c.execute("SELECT date,content FROM daily_logs WHERE date>=date('now','-3 days') ORDER BY date DESC LIMIT 20").fetchall()
    conn.close()
    lines = ["# UPSC 2027 \u2014 Claude Code Context", f"_Auto-generated {date.today().isoformat()}_", ""]
    if weak:
        lines += ["## Weak Topics"]
        for s,t,m,lr in weak: lines.append(f"- [{s}] {t} \u2014 missed {m}x, last: {lr or 'never'}")
        lines.append("")
    if quiz:
        lines += ["## 7-Day Quiz Accuracy"]
        for s,p,n in quiz: lines.append(f"- {s}: {p:.0f}% ({n} Qs)")
        lines.append("")
    if traps:
        lines += ["## Recent Traps"]
        for desc,logged in traps: lines.append(f"- [{(logged or '?')[:10]}] {desc[:120]}")
        lines.append("")
    if flaws:
        lines += ["## Mains Flaws"]
        for f,n in flaws: lines.append(f"- {f} ({n}x)")
        lines.append("")
    if concepts:
        lines += ["## Concepts Taught"]
        lines.append(", ".join(f"{c} (x{r})" for c,r in concepts))
        lines.append("")
    if logs:
        lines += ["## Recent Logs (3d)"]
        for d,content in logs: lines.append(f"- [{d}] {content[:150]}")
        lines.append("")
    p = Path(CLAUDE_MD_PATH); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"CLAUDE.md synced: {len(lines)} lines")
    return len(lines)


# ===============================================================
# 1c. CA NOTE FETCHER
# ===============================================================

def get_todays_ca_note():
    """Read today's CA note. Try local vault first, then download from Databricks Volume."""
    today = date.today()
    month_folder = today.strftime("%m-%B")
    local_path = Path(VAULT_PATH) / "01_Current_Affairs" / str(today.year) / month_folder / f"CA_{today.isoformat()}.md"

    if local_path.exists():
        log.info(f"CA note found locally: {local_path}")
        return local_path.read_text(encoding="utf-8")[:6000]

    remote = f"dbfs:/Volumes/upsc_catalog/rag/obsidian_ca/UPSC_2026/01_Current_Affairs/{today.year}/{month_folder}/CA_{today.isoformat()}.md"
    local_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(
            ["databricks", "fs", "cp", remote, str(local_path), "--profile", DBR_CLI_PROFILE],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and local_path.exists():
            log.info(f"CA note downloaded from Volume: {local_path}")
            return local_path.read_text(encoding="utf-8")[:6000]
        else:
            log.warning(f"CA download failed: {result.stderr[:200]}")
    except Exception as e:
        log.warning(f"CA download error: {e}")
    return None


# ===============================================================
# 1d. DATABRICKS SQL STATEMENT API (v2.3)
# Queries Delta tables directly -- no CLI/Spark dependency
# ===============================================================

def run_databricks_sql(query, max_wait=60):
    """Execute SQL via Databricks SQL Statement API. Returns list of dicts."""
    url = f"{DATABRICKS_HOST}/api/2.0/sql/statements/"
    headers = {"Authorization": f"Bearer {DATABRICKS_TOKEN}", "Content-Type": "application/json"}
    payload = {"statement": query, "wait_timeout": "30s", "warehouse_id": SQL_WAREHOUSE_ID}

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=max_wait)
        resp.raise_for_status()
        data = resp.json()

        statement_id = data.get("statement_id")
        status = data.get("status", {}).get("state", "")
        poll_count = 0
        while status in ("PENDING", "RUNNING") and poll_count < 10:
            time.sleep(3)
            poll_resp = requests.get(f"{url}{statement_id}", headers=headers, timeout=30)
            poll_resp.raise_for_status()
            data = poll_resp.json()
            status = data.get("status", {}).get("state", "")
            poll_count += 1

        if status != "SUCCEEDED":
            error_msg = data.get("status", {}).get("error", {}).get("message", status)
            log.error(f"SQL failed: {error_msg}")
            return None

        manifest = data.get("manifest", {})
        columns = [col["name"] for col in manifest.get("schema", {}).get("columns", [])]
        rows = []
        for chunk in data.get("result", {}).get("data_array", []):
            rows.append(dict(zip(columns, chunk)))
        return rows

    except Exception as e:
        log.error(f"SQL Statement API error: {e}")
        return None


def fetch_volume_file_via_api(volume_path):
    """Read a file from Databricks Volume via Files API."""
    url = f"{DATABRICKS_HOST}/api/2.0/fs/files{volume_path}"
    headers = {"Authorization": f"Bearer {DATABRICKS_TOKEN}"}
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.text
    except requests.exceptions.HTTPError as e:
        log.warning(f"Volume file not found: {volume_path} ({e.response.status_code})")
        return None
    except Exception as e:
        log.error(f"Volume fetch error: {e}")
        return None


def list_volume_files(dir_path):
    """List files in a Volume directory via Files API."""
    url = f"{DATABRICKS_HOST}/api/2.0/fs/directories{dir_path}"
    headers = {"Authorization": f"Bearer {DATABRICKS_TOKEN}"}
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        entries = resp.json().get("contents", [])
        return [e for e in entries if not e.get("is_directory", False)]
    except Exception as e:
        log.error(f"Volume list error: {e}")
        return []


# ===============================================================
# 2. DATABRICKS AGENT ENGINE (with retry)
# ===============================================================

def clean_response(text):
    """Remove hallucinated tool call syntax from Llama 3.3 responses."""
    text = re.sub(r'<function=[^>]*>\{[^}]*\}</function>', '', text)
    text = re.sub(r'<function=[^>]*>[^<]*</function>', '', text)
    text = re.sub(r'<function=[^>]*>', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def call_agent(user_message, memory_context=""):
    """Call the UPSC tutor agent with automatic retry on cold-start timeouts."""
    url = f"{DATABRICKS_HOST}/serving-endpoints/{AGENT_ENDPOINT}/invocations"
    headers = {"Authorization": f"Bearer {DATABRICKS_TOKEN}", "Content-Type": "application/json"}
    enhanced = user_message
    if memory_context:
        enhanced = f"[STUDENT PROFILE]\n{memory_context}\n\n[INSTRUCTION]\n{user_message}"
    payload = {"dataframe_records": [{"input": [{"role": "user", "content": enhanced}],
               "custom_inputs": {"session_id": f"tg-{date.today().isoformat()}"}}]}

    last_error = None
    for attempt in range(1, AGENT_RETRIES + 1):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=180)
            resp.raise_for_status()
            pred = resp.json().get("predictions", {})
            if isinstance(pred, dict):
                for item in pred.get("output", []):
                    if isinstance(item, dict) and item.get("type") == "message":
                        texts = [c.get("text", "") for c in item.get("content", [])
                                 if isinstance(c, dict) and c.get("type") == "output_text"]
                        if texts:
                            return clean_response("\n".join(texts))
            raw = str(pred)[:4000] if pred else "No response from agent."
            return clean_response(raw)
        except requests.exceptions.Timeout:
            last_error = "timeout"
            if attempt < AGENT_RETRIES:
                log.warning(f"Agent timeout (attempt {attempt}/{AGENT_RETRIES}), retrying in {AGENT_RETRY_DELAY}s...")
                time.sleep(AGENT_RETRY_DELAY)
                continue
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else 0
            if status_code in (503, 429) and attempt < AGENT_RETRIES:
                log.warning(f"Agent {status_code} (attempt {attempt}), retrying...")
                time.sleep(AGENT_RETRY_DELAY)
                continue
            log.error(f"API error: {e}")
            return f"Agent error ({status_code}). Retry shortly."
        except Exception as e:
            log.error(f"Error: {e}")
            return f"Error: {str(e)[:300]}"

    return "Agent cold-starting (~30s). Send your message again in a moment."


async def send_long(update, text):
    """Send text in 4000-char chunks (Telegram limit)."""
    if not text:
        text = "(empty response)"
    for i in range(0, len(text), 4000):
        await update.message.reply_text(text[i:i+4000])

def check_auth(update):
    if not ALLOWED_USER_ID:
        return True
    return str(update.effective_user.id) == ALLOWED_USER_ID


# ===============================================================
# 3. CORE COMMANDS
# ===============================================================

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    await update.message.reply_text(
        "\U0001f3db UPSC 2027 MEGA-TUTOR v2.3\n"
        "80,800+ chunks + Llama 3.3 70B + Knowledge Graph\n\n"
        "CORE:\n"
        "  /teach <concept> \u2014 Memory Hooks + Linkages\n"
        "  /log <text> \u2014 Save to vault + SQLite\n"
        "  /eod \u2014 End-of-day summary\n"
        "  /daily \u2014 Today's CA briefing\n"
        "  /dump <article> \u2014 Structure for UPSC\n"
        "  /stats \u2014 Statistics\n"
        "  /weak \u2014 Weakest topics\n\n"
        "PRELIMS:\n"
        "  /quiz [subject] \u2014 MCQ\n"
        "  /trap <failed Q> \u2014 Options Autopsy\n"
        "  /drill \u2014 Interleaved practice\n\n"
        "MAINS:\n"
        "  /evaluate <answer> \u2014 Grade answer\n"
        "  /model <topic> \u2014 Mental Model\n\n"
        "ACTIVE LEARNING:\n"
        "  /socratic /feynman /why /visual\n"
        "  /recall /simplify /progress\n\n"
        "KNOWLEDGE GRAPH:\n"
        "  /graphrag <entity> \u2014 Entity Relationships\n\n"
        "\U0001f4f1 MOBILE PRACTICE (v2.3):\n"
        "  /phone \u2014 2-min quick summary\n"
        "  /practice \u2014 Tutor brief + key insights\n"
        "  /podcast \u2014 Full podcast transcript\n"
        "  /insights \u2014 Top 5 exam-critical facts\n"
        "  /files \u2014 List all today's files\n"
        "  /raw <filename> \u2014 Fetch any file\n\n"
        "INTERVIEW & SYSTEM:\n"
        "  /daf \u2014 Mock Interview\n"
        "  /sync \u2014 Sync to CLAUDE.md\n"
        "  /help \u2014 This menu\n\n"
        "Or just send any question!"
    )

cmd_help = cmd_start

async def cmd_teach(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    concept = " ".join(ctx.args) if ctx.args else ""
    if not concept:
        await update.message.reply_text("Usage: /teach <concept>")
        return
    await update.message.reply_text(f"\U0001f50d Querying KB for: {concept}...")
    prompt = (f"TEACH ME: {concept}\n\nStructure as:\n"
              "1. SIMPLE EXPLANATION\n2. MEMORY HOOK\n3. ANALOGY\n"
              "4. UPSC LINKAGES (GS1-4)\n5. WAY FORWARD\n6. TRAP ALERT")
    resp = call_agent(prompt, get_user_context())
    log_interaction("/teach", concept, resp)
    log_concept(concept)
    await send_long(update, resp)

async def cmd_log(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    text = " ".join(ctx.args) if ctx.args else ""
    if not text:
        await update.message.reply_text("Usage: /log <what you learned>")
        return
    today_str = date.today().isoformat()
    filename = f"Daily_Log_{today_str}.md"
    filepath = Path(VAULT_PATH) / "00_Dashboard" / filename
    filepath.parent.mkdir(parents=True, exist_ok=True)
    now_t = datetime.now().strftime("%H:%M")
    if filepath.exists():
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(f"\n\n## Update ({now_t})\n{text}\n")
    else:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"---\ndate: {today_str}\ntype: daily-log\n---\n\n# Daily Log \u2014 {today_str}\n\n## Learned\n{text}\n\n---\n*Logged via Telegram at {now_t}*\n")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO daily_logs(date,content,file_path) VALUES(?,?,?)",
                 (today_str, text, str(filepath)))
    conn.commit(); conn.close()
    log_interaction("/log", text, f"Saved to {filepath}")
    await update.message.reply_text(f"\u2705 Logged to {filename}")

async def cmd_eod(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    await update.message.reply_text("\U0001f305 Generating EOD summary...")
    prompt = ("END OF DAY SUMMARY. Based on my profile:\n"
              "1. Encouraging summary\n2. Most important concept\n"
              "3. 1 active-recall question\n4. Tomorrow's focus\n5. Intensity: Light/Medium/Heavy")
    resp = call_agent(prompt, get_user_context())
    log_interaction("/eod", "end-of-day", resp)
    try:
        n = sync_claude_md()
        await send_long(update, resp)
        await update.message.reply_text(f"\u2705 CLAUDE.md auto-synced ({n} lines).")
    except Exception:
        await send_long(update, resp)

async def cmd_daily(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    await update.message.reply_text("\U0001f4f0 Fetching today's CA briefing...")
    ca_content = get_todays_ca_note()
    if ca_content:
        prompt = (
            f"Here is today's ({date.today().isoformat()}) UPSC Current Affairs note. "
            "Analyze it and provide a study briefing. For each story:\n"
            "- Title\n- 2-line summary\n- GS paper relevance\n- 1 Prelims trap to avoid\n- 1 Mains angle\n\n"
            f"CA NOTE:\n{ca_content}"
        )
    else:
        prompt = (
            f"Search the knowledge base for Current Affairs from {date.today().isoformat()}. "
            f"Look for CA notes with filename CA_{date.today().isoformat()}.md. "
            "For each story: title, 2-line summary, GS paper, 1 trap, 1 Mains angle."
        )
    resp = call_agent(prompt, get_user_context())
    log_interaction("/daily", "daily-ca", resp)
    await send_long(update, resp)

async def cmd_dump(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    text = " ".join(ctx.args) if ctx.args else ""
    if len(text) < 50:
        await update.message.reply_text("Usage: /dump <paste long article>")
        return
    await update.message.reply_text("Processing article...")
    prompt = (f"STRUCTURE FOR UPSC:\n\n{text[:6000]}\n\n"
              "1. KEY FACTS\n2. GS PAPER MAP\n3. MAINS ANGLE\n4. PRELIMS TRAPS\n5. LINKAGES")
    resp = call_agent(prompt, get_user_context())
    slug = re.sub(r'[^a-z0-9]+', '_', text[:30].lower())[:20]
    filename = f"Dump_{date.today().isoformat()}_{slug}.md"
    filepath = Path(VAULT_PATH) / "00_Dashboard" / filename
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"---\ndate: {date.today().isoformat()}\ntype: dump\n---\n\n{resp}\n")
    log_interaction("/dump", text[:200], resp)
    await send_long(update, resp)
    await update.message.reply_text(f"\u2705 Saved: {filename}")

async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    total = c.execute("SELECT COUNT(*) FROM interactions").fetchone()[0]
    today = c.execute("SELECT COUNT(*) FROM interactions WHERE date(timestamp)=date('now')").fetchone()[0]
    qt, qa = c.execute("SELECT COUNT(*),COALESCE(AVG(CASE WHEN was_correct=1 THEN 100.0 ELSE 0.0 END),0) FROM quiz_history").fetchone()
    wk = c.execute("SELECT COUNT(*) FROM weak_topics").fetchone()[0]
    ct = c.execute("SELECT COUNT(*) FROM concepts_taught").fetchone()[0]
    ld = c.execute("SELECT COUNT(DISTINCT date) FROM daily_logs").fetchone()[0]
    traps = c.execute("SELECT COUNT(*) FROM prelims_traps").fetchone()[0]
    flaws = c.execute("SELECT COUNT(*) FROM mains_flaws").fetchone()[0]
    active = c.execute("SELECT COUNT(DISTINCT date(timestamp)) FROM interactions WHERE timestamp>=date('now','-30 days')").fetchone()[0]
    conn.close()
    await update.message.reply_text(
        f"\U0001f4ca UPSC Stats\n{DIVIDER}\n"
        f"Total: {total} | Today: {today}\n"
        f"Concepts: {ct} | Quizzes: {qt} | Accuracy: {qa:.0f}%\n"
        f"Weak topics: {wk} | Traps: {traps} | Flaws: {flaws}\n"
        f"Days logged: {ld} | Active 30d: {active}/30")

async def cmd_weak(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    conn = sqlite3.connect(DB_PATH)
    topics = conn.execute("SELECT subject,topic,miss_count,last_reviewed FROM weak_topics ORDER BY miss_count DESC LIMIT 10").fetchall()
    conn.close()
    if not topics:
        await update.message.reply_text("No weak topics yet. Use /quiz!")
        return
    msg = "\u26a0\ufe0f Weakest Topics\n" + DIVIDER + "\n\n"
    for i,(s,t,m,lr) in enumerate(topics,1):
        msg += f"{i}. [{s}] {t} \u2014 missed {m}x (last: {lr or 'never'})\n"
    await update.message.reply_text(msg)


# ===============================================================
# 4. PRELIMS MODULE
# ===============================================================

async def cmd_quiz(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    subject = " ".join(ctx.args) if ctx.args else ""
    memory = get_user_context()
    if subject:
        prompt = f"QUIZ ME on {subject}. 1 UPSC Prelims MCQ, 4 options, subtle trap from my trap log. Do NOT reveal answer."
    else:
        prompt = "QUIZ ME on my weakest topic. 1 MCQ, 4 options, trap from my log. Do NOT reveal answer."
    await update.message.reply_text("\U0001f9e0 Generating quiz...")
    resp = call_agent(prompt, memory)
    log_interaction("/quiz", subject or "auto", resp)
    await send_long(update, resp)

async def cmd_trap(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    text = " ".join(ctx.args) if ctx.args else ""
    if not text:
        await update.message.reply_text("Usage: /trap <paste failed PYQ + why you got it wrong>")
        return
    await update.message.reply_text("\U0001f52c Options Autopsy...")
    prompt = (f"OPTIONS AUTOPSY:\n\n{text}\n\n"
              "1. EXACT trap\n2. Psychological bias\n3. Correct reasoning\n"
              "4. One-line RULE. Under 200 words.")
    resp = call_agent(prompt, get_user_context())
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO prelims_traps(topic,trap_type,trap_description) VALUES(?,?,?)",
                 ("General", "autopsy", resp[:300]))
    conn.commit(); conn.close()
    log_interaction("/trap", text[:200], resp)
    await send_long(update, resp)
    await update.message.reply_text("\U0001f6a8 Trap memorized.")

async def cmd_drill(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    await update.message.reply_text("\U0001f32a Interleaved Drill...")
    prompt = ("INTERLEAVED practice. Mix 3 different concepts from my weak topics. "
              "3 rapid-fire UPSC MCQs, different subjects. Do NOT reveal answers.")
    resp = call_agent(prompt, get_user_context())
    log_interaction("/drill", "interleaved", resp)
    await send_long(update, resp)


# ===============================================================
# 5. MAINS MODULE
# ===============================================================

async def cmd_evaluate(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    text = " ".join(ctx.args) if ctx.args else ""
    if len(text) < 50:
        await update.message.reply_text("Usage: /evaluate <paste full Mains answer>")
        return
    await update.message.reply_text("\U0001f4dd Grading...")
    prompt = (f"EVALUATE strictly:\n\n{text[:5000]}\n\n"
              "1. SCORE X/10\n2. STRUCTURE critique\n3. Missing articles/judgments\n"
              "4. GS LINKAGES\n5. Top 3 FLAWS\n6. Model intro (3 sentences)\n"
              "Check my known mains_flaws \u2014 am I repeating?")
    resp = call_agent(prompt, get_user_context())
    log_interaction("/evaluate", text[:200], resp)
    await send_long(update, resp)

async def cmd_model(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    topic = " ".join(ctx.args) if ctx.args else ""
    if not topic:
        await update.message.reply_text("Usage: /model <topic>")
        return
    await update.message.reply_text(f"\U0001f528 Forging model for: {topic}...")
    prompt = (f"MENTAL MODEL for: {topic}\n\n"
              "1. CORE PRINCIPLES\n2. RULES & MECHANISMS\n3. EXCEPTIONS\n"
              "4. EXAMPLES (2 current + 2 historical)\n5. GS PAPER MAP\n"
              "6. QUICK-DRAW FRAMEWORK (5-line skeleton, 1 min under pressure)")
    resp = call_agent(prompt, get_user_context())
    log_interaction("/model", topic, resp)
    log_concept(topic)
    await send_long(update, resp)


# ===============================================================
# 6. ACTIVE LEARNING
# ===============================================================

async def cmd_socratic(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    topic = " ".join(ctx.args) if ctx.args else ""
    if not topic:
        await update.message.reply_text("Usage: /socratic <topic>")
        return
    await update.message.reply_text(f"\U0001f9d0 Socratic mode: {topic}...")
    prompt = (f"SOCRATIC COACH for: {topic}\n\n"
              "Do NOT give answers. Ask ONE smart question to test what I know.\n"
              "Push toward UPSC depth (articles, judgments). Wait for my reply.")
    resp = call_agent(prompt, get_user_context())
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO socratic_sessions(topic) VALUES(?)", (topic,))
    conn.commit(); conn.close()
    log_interaction("/socratic", topic, resp)
    await send_long(update, resp)

async def cmd_feynman(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    text = " ".join(ctx.args) if ctx.args else ""
    if ":" not in text:
        await update.message.reply_text("Usage: /feynman <topic>: <your explanation>")
        return
    topic, explanation = text.split(":", 1)
    await update.message.reply_text(f"\U0001f9d0 Auditing: {topic.strip()}...")
    prompt = (f"FEYNMAN AUDIT\nTopic: {topic.strip()}\nExplanation: {explanation.strip()}\n\n"
              "1. ACCURACY\n2. COMPLETENESS\n3. DEPTH\n4. SCORE X/10\n5. CORRECTED VERSION (3 sentences)")
    resp = call_agent(prompt, get_user_context())
    log_interaction("/feynman", text[:200], resp)
    log_concept(topic.strip())
    await send_long(update, resp)

async def cmd_why(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    fact = " ".join(ctx.args) if ctx.args else ""
    if not fact:
        await update.message.reply_text("Usage: /why <state a fact>")
        return
    await update.message.reply_text(f"\U0001f525 Stress-testing: {fact}...")
    prompt = (f"WHY-HOW INTERROGATION\nStudent states: \"{fact}\"\n\n"
              "1. WHY true?\n2. HOW in practice?\n3. WHAT breaks it?\n4. WHO said it?\n\n"
              "Start with WHY only. Wait for my answer.")
    resp = call_agent(prompt, get_user_context())
    log_interaction("/why", fact, resp)
    await send_long(update, resp)

async def cmd_visual(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    topic = " ".join(ctx.args) if ctx.args else ""
    if not topic:
        await update.message.reply_text("Usage: /visual <topic>")
        return
    await update.message.reply_text(f"\U0001f3a8 Dual-coding: {topic}...")
    prompt = (f"DUAL-CODING for: {topic}\n\n"
              "Per concept: WORDS (2-3 sentences) + VISUAL (ASCII diagram/table/flowchart).\n"
              "Then: 2 examples, 3 test questions, 1 mnemonic.")
    resp = call_agent(prompt, get_user_context())
    log_interaction("/visual", topic, resp)
    log_concept(topic)
    await send_long(update, resp)

async def cmd_recall(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    topic = " ".join(ctx.args) if ctx.args else ""
    if not topic:
        await update.message.reply_text("Usage: /recall <topic>")
        return
    await update.message.reply_text(f"\U0001f4a1 Active Recall: {topic}...")
    prompt = (f"ACTIVE RECALL for: {topic}\nDo NOT explain. Make ME produce.\n\n"
              "Step 1: Write 3-sentence summary from memory.\n"
              "Start Step 1 only. Adapt difficulty based on my answers.")
    resp = call_agent(prompt, get_user_context())
    log_interaction("/recall", topic, resp)
    await send_long(update, resp)

async def cmd_simplify(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    topic = " ".join(ctx.args) if ctx.args else ""
    if not topic:
        await update.message.reply_text("Usage: /simplify <topic>")
        return
    await update.message.reply_text(f"\U0001f476 Simplifying: {topic}...")
    prompt = (f"SIMPLIFIED LEARNING: {topic}\n\n4 layers:\n"
              "1. ELI12\n2. ELI-GRADUATE\n3. ELI-UPSC\n4. ELI-TOPPER")
    resp = call_agent(prompt, get_user_context())
    log_interaction("/simplify", topic, resp)
    log_concept(topic)
    await send_long(update, resp)

async def cmd_progress(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    topic = " ".join(ctx.args) if ctx.args else ""
    if not topic:
        await update.message.reply_text("Usage: /progress <topic>")
        return
    await update.message.reply_text(f"\U0001f4c8 Progressive Recall: {topic}...")
    prompt = (f"PROGRESSIVE RECALL for: {topic}\nDo NOT give answers.\n\n"
              "L1-RECALL, L2-UNDERSTAND, L3-APPLY, L4-ANALYZE, L5-EVALUATE.\n"
              "Start L1 only. Move up on accuracy. Stay if wrong.")
    resp = call_agent(prompt, get_user_context())
    log_interaction("/progress", topic, resp)
    await send_long(update, resp)


# ===============================================================
# 6b. KNOWLEDGE GRAPH (GraphRAG)
# ===============================================================

async def cmd_graphrag(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    entity = " ".join(ctx.args) if ctx.args else ""
    if not entity:
        await update.message.reply_text(
            "Usage: /graphrag <entity>\n\n"
            "Examples:\n"
            "  /graphrag Article 356\n"
            "  /graphrag Finance Commission\n"
            "  /graphrag S.R. Bommai Case"
        )
        return
    await update.message.reply_text(f"\U0001f578 Querying Knowledge Graph for: {entity}...")
    prompt = (
        f"Use the knowledge graph search tool (search_knowledge_graph) to find all relationships "
        f"for the entity: \"{entity}\".\n\n"
        "Then combine with vector search to provide:\n"
        "1. ENTITY RELATIONSHIP MAP\n2. KEY CONNECTIONS\n3. UPSC RELEVANCE\n4. RELATED TOPICS\n\n"
        "If the knowledge graph returns empty, fall back to vector search."
    )
    resp = call_agent(prompt, get_user_context())
    log_interaction("/graphrag", entity, resp)
    log_concept(entity)
    await send_long(update, resp)


# ===============================================================
# 6c. DAILY PRACTICE MOBILE ACCESS (v2.3)
# Reads NB7+NB8 outputs from Delta queue table or Volume files
# and sends directly to Telegram for phone-friendly consumption
# ===============================================================

def _get_target_date(args):
    """Parse optional date arg or default to today."""
    if args:
        d = " ".join(args).strip()
        if re.match(r'^\d{4}-\d{2}-\d{2}$', d):
            return d
    return date.today().isoformat()


def _get_practice_from_queue(target_date):
    """Fetch practice content from daily_practice_queue Delta table."""
    rows = run_databricks_sql(
        f"SELECT * FROM upsc_catalog.rag.daily_practice_queue "
        f"WHERE ca_date = '{target_date}' LIMIT 1"
    )
    if rows and len(rows) > 0:
        return rows[0]
    return None


async def cmd_phone(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Send Mode 8 phone summary -- 2-min scannable read."""
    if not check_auth(update): return
    target = _get_target_date(ctx.args)
    await update.message.reply_text(f"\U0001f4f1 Fetching phone summary for {target}...")

    queue = _get_practice_from_queue(target)
    if queue and queue.get("mode8_phone_summary"):
        msg = f"\U0001f4f1 QUICK SUMMARY \u2014 {target}\n{DIVIDER_NARROW}\n\n{queue['mode8_phone_summary']}"
        log_interaction("/phone", target, msg[:500])
        await send_long(update, msg)
        return

    content = fetch_volume_file_via_api(f"{VOLUME_BASE}/{target}/08_Phone_Summary.md")
    if content:
        msg = f"\U0001f4f1 QUICK SUMMARY \u2014 {target}\n{DIVIDER_NARROW}\n\n{content}"
        log_interaction("/phone", target, msg[:500])
        await send_long(update, msg)
        return

    await update.message.reply_text(
        f"\u274c No phone summary for {target}.\nTry /daily for a live CA briefing."
    )


async def cmd_practice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Send combined practice package: tutor brief + key insights (~5 min)."""
    if not check_auth(update): return
    target = _get_target_date(ctx.args)
    await update.message.reply_text(f"\U0001f4da Loading practice package for {target}...")

    queue = _get_practice_from_queue(target)
    parts = []

    # Part 1: Tutor Brief (Mode 7)
    tutor = (queue or {}).get("mode7_tutor_brief", "")
    if not tutor:
        tutor = fetch_volume_file_via_api(f"{VOLUME_BASE}/{target}/07_AI_Tutor_Brief.md") or ""
    if tutor:
        parts.append(f"\U0001f9d1\u200d\U0001f3eb TUTOR BRIEF\n{DIVIDER}\n{tutor}")

    # Part 2: Key Insights (from NB8)
    insights = fetch_volume_file_via_api(f"{VOLUME_BASE}/{target}/key_insights.md") or ""
    if insights:
        parts.append(f"\n\U0001f4a1 KEY INSIGHTS\n{DIVIDER}\n{insights}")

    # Part 3: Phone summary as a quick closer
    phone = (queue or {}).get("mode8_phone_summary", "")
    if phone:
        parts.append(f"\n\U0001f4f1 QUICK SUMMARY\n{DIVIDER}\n{phone}")

    if parts:
        msg = f"\U0001f4da PRACTICE PACKAGE \u2014 {target}\n{DIVIDER_WIDE}\n\n" + "\n\n".join(parts)
        log_interaction("/practice", target, msg[:500])
        await send_long(update, msg)
    else:
        await update.message.reply_text(
            f"\u274c No practice content for {target}.\n"
            "Try: /daily (live CA) or /phone (quick summary)"
        )


async def cmd_podcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Send the full podcast transcript from NB8 (~14 min read)."""
    if not check_auth(update): return
    target = _get_target_date(ctx.args)
    await update.message.reply_text(f"\U0001f399 Fetching podcast transcript for {target}...")

    content = fetch_volume_file_via_api(f"{VOLUME_BASE}/{target}/podcast_transcript.md")
    if content:
        msg = f"\U0001f399 PODCAST TRANSCRIPT \u2014 {target}\n{DIVIDER_WIDE}\n\n{content}"
        log_interaction("/podcast", target, f"Sent {len(content)} chars")
        await send_long(update, msg)
        return

    queue = _get_practice_from_queue(target)
    if queue and queue.get("audio_script"):
        msg = f"\U0001f399 AUDIO SCRIPT \u2014 {target}\n{DIVIDER_WIDE}\n\n{queue['audio_script']}"
        log_interaction("/podcast", target, "Sent queue audio_script")
        await send_long(update, msg)
    else:
        await update.message.reply_text(
            f"\u274c No podcast for {target}. Try /practice instead."
        )


async def cmd_insights(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Send key insights summary -- top 5 exam-critical facts."""
    if not check_auth(update): return
    target = _get_target_date(ctx.args)
    await update.message.reply_text(f"\U0001f4a1 Fetching key insights for {target}...")

    content = fetch_volume_file_via_api(f"{VOLUME_BASE}/{target}/key_insights.md")
    if content:
        msg = f"\U0001f4a1 KEY INSIGHTS \u2014 {target}\n{DIVIDER_WIDE}\n\n{content}"
        log_interaction("/insights", target, msg[:500])
        await send_long(update, msg)
        return

    queue = _get_practice_from_queue(target)
    if queue and queue.get("mode1_practice_answer"):
        hook = queue.get("memory_hook", "N/A")
        msg = (f"\U0001f4a1 KEY TAKEAWAYS \u2014 {target}\n{DIVIDER_WIDE}\n\n"
               f"\U0001f4dd Practice Answer:\n{queue['mode1_practice_answer']}\n\n"
               f"\U0001f9e0 Memory Hook:\n{hook}")
        log_interaction("/insights", target, msg[:500])
        await send_long(update, msg)
    else:
        await update.message.reply_text(f"\u274c No insights for {target}. Try /daily.")


async def cmd_raw(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Fetch any raw file by name from today's Daily Practice folder.
    Usage: /raw key_insights.md  or  /raw 2026-03-29 podcast_transcript.md
    """
    if not check_auth(update): return
    args = ctx.args or []
    if not args:
        await update.message.reply_text(
            "Usage: /raw <filename>\n"
            "  or:  /raw <date> <filename>\n\n"
            "Examples:\n"
            "  /raw key_insights.md\n"
            "  /raw 2026-03-29 podcast_transcript.md\n\n"
            "Use /files to see available filenames."
        )
        return

    # Parse date + filename
    if len(args) >= 2 and re.match(r'^\d{4}-\d{2}-\d{2}$', args[0]):
        target = args[0]
        filename = " ".join(args[1:])
    else:
        target = date.today().isoformat()
        filename = " ".join(args)

    await update.message.reply_text(f"\U0001f4e5 Fetching {filename} for {target}...")
    content = fetch_volume_file_via_api(f"{VOLUME_BASE}/{target}/{filename}")
    if content:
        msg = f"\U0001f4c4 {filename} \u2014 {target}\n{DIVIDER_WIDE}\n\n{content}"
        log_interaction("/raw", f"{target}/{filename}", f"Sent {len(content)} chars")
        await send_long(update, msg)
    else:
        await update.message.reply_text(
            f"\u274c File not found: {filename}\nUse /files to list available files."
        )


async def cmd_files(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """List all available practice files for today (or specified date)."""
    if not check_auth(update): return
    target = _get_target_date(ctx.args)
    await update.message.reply_text(f"\U0001f4c2 Checking files for {target}...")

    files = list_volume_files(f"{VOLUME_BASE}/{target}")

    if files:
        msg = f"\U0001f4c2 DAILY FILES \u2014 {target}\n{DIVIDER_NARROW}\n\n"
        total_bytes = 0
        emoji_map = {
            "phone": "\U0001f4f1", "quick": "\U0001f4f1",
            "podcast": "\U0001f399", "transcript": "\U0001f399",
            "insight": "\U0001f4a1", "tutor": "\U0001f9d1\u200d\U0001f3eb",
            "mcq": "\U0001f9e0", "prelims": "\U0001f9e0",
            "ethics": "\u2696\ufe0f", "mains": "\u270d\ufe0f", "model": "\u270d\ufe0f",
            "telugu": "\U0001f4d6", "karl": "\U0001f4cb",
            "knowledge": "\U0001f4d3", "qa": "\U0001f4d3",
        }
        for f in sorted(files, key=lambda x: x.get("name", "")):
            name = f.get("name", "?")
            size = f.get("file_size", 0) or 0
            total_bytes += size
            name_lower = name.lower()
            emoji = "\U0001f4c4"
            for key, em in emoji_map.items():
                if key in name_lower:
                    emoji = em
                    break
            msg += f"{emoji} {name} ({size:,}B)\n"

        msg += (f"\n{DIVIDER}\n{len(files)} files | {total_bytes:,} bytes\n\n"
                "\U0001f449 Quick access:\n"
                "  /phone  /practice  /podcast  /insights\n"
                "  /raw <filename> \u2014 fetch any file above")
        log_interaction("/files", target, f"{len(files)} files")
        await update.message.reply_text(msg)
    else:
        queue = _get_practice_from_queue(target)
        if queue:
            await update.message.reply_text(
                f"\u26a0\ufe0f Queue entry exists for {target} but Volume files not ready.\n"
                "NB8 may still be running.\n\n"
                "\U0001f449 Content available from Delta:\n"
                "  /phone  /practice"
            )
        else:
            await update.message.reply_text(
                f"\u274c No files for {target}.\n\n"
                "Pipeline schedule:\n"
                "  7:00 AM IST \u2014 NB6 fetches CA\n"
                "  8:00 AM IST \u2014 NB7 generates practice\n"
                "  8:30 AM IST \u2014 NB8 generates audio + files\n\n"
                "Try: /files 2026-03-29"
            )


# ===============================================================
# 7. DAF & SYSTEM
# ===============================================================

async def cmd_daf(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    await update.message.reply_text("\U0001f454 Entering Interview Room...")
    prompt = (f"UPSC INTERVIEW BOARD CHAIRMAN.\nDAF: {DAF_PROFILE}\n\n"
              "Ask ONE high-pressure question connecting my Data Engineering/Canada "
              "background to Indian governance. Stay in character. After I answer: feedback + score/10.")
    resp = call_agent(prompt, get_user_context())
    log_interaction("/daf", "interview", resp)
    await send_long(update, resp)

async def cmd_sync(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    try:
        n = sync_claude_md()
        vault = Path(VAULT_PATH)
        for cmd in [
            ["git", "-C", str(vault), "add", ".claude/CLAUDE.md"],
            ["git", "-C", str(vault), "commit", "-m", f"sync: CLAUDE.md {date.today().isoformat()}"],
            ["git", "-C", str(vault), "push"],
        ]:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0 and "nothing to commit" not in result.stdout:
                await update.message.reply_text(f"\u26a0\ufe0f Git: {result.stderr[:200]}")
                return
        await update.message.reply_text(f"\u2705 CLAUDE.md synced ({n} lines) + pushed to GitHub.\nPull on Mac: git pull")
    except Exception as e:
        await update.message.reply_text(f"\u26a0\ufe0f Sync failed: {str(e)[:300]}")


# ===============================================================
# 8. MAIN
# ===============================================================

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    user_msg = update.message.text
    if not user_msg: return
    await update.message.reply_text("\U0001f50d Thinking...")
    resp = call_agent(user_msg, get_user_context())
    log_interaction("direct", user_msg, resp)
    await send_long(update, resp)

def main():
    init_db()
    if "YOUR_" in BOT_TOKEN:
        print("Set TELEGRAM_BOT_TOKEN! @BotFather -> /newbot"); return
    if "YOUR_" in DATABRICKS_TOKEN:
        print("Set DATABRICKS_TOKEN!"); return
    app = Application.builder().token(BOT_TOKEN).build()
    commands = [
        ("start", cmd_start), ("help", cmd_help), ("teach", cmd_teach),
        ("log", cmd_log), ("eod", cmd_eod), ("daily", cmd_daily),
        ("dump", cmd_dump), ("stats", cmd_stats), ("weak", cmd_weak),
        ("quiz", cmd_quiz), ("trap", cmd_trap), ("drill", cmd_drill),
        ("evaluate", cmd_evaluate), ("model", cmd_model),
        ("socratic", cmd_socratic), ("feynman", cmd_feynman),
        ("why", cmd_why), ("visual", cmd_visual), ("recall", cmd_recall),
        ("simplify", cmd_simplify), ("progress", cmd_progress),
        ("graphrag", cmd_graphrag),
        # v2.3: Mobile Practice commands
        ("phone", cmd_phone), ("practice", cmd_practice),
        ("podcast", cmd_podcast), ("insights", cmd_insights),
        ("files", cmd_files), ("raw", cmd_raw),
        # System
        ("daf", cmd_daf), ("sync", cmd_sync),
    ]
    for cmd_name, handler in commands:
        app.add_handler(CommandHandler(cmd_name, handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    log.info("\U0001f680 UPSC MEGA-BOT v2.3 STARTING...")
    log.info(f"{len(commands)} commands | Agent: {AGENT_ENDPOINT}")
    log.info(f"Memory: {DB_PATH} | Vault: {VAULT_PATH}")
    log.info(f"SQL Warehouse: {SQL_WAREHOUSE_ID}")
    app.run_polling(drop_pending_updates=True)


# ===============================================================
# 9. AI PLAYGROUND / TOOL CALLING (v2.3)
# Plain Python functions usable as UC functions or in Playground
# with any served model (Claude, Llama, DBRX, etc.)
# ===============================================================

def tool_get_phone_summary(target_date: str = "") -> str:
    """Get today's 2-min phone-optimized UPSC CA summary.
    Args: target_date (str): ISO date like '2026-03-30'. Defaults to today.
    Returns: Phone summary text or error message.
    """
    target = target_date or date.today().isoformat()
    queue = _get_practice_from_queue(target)
    if queue and queue.get("mode8_phone_summary"):
        return queue["mode8_phone_summary"]
    content = fetch_volume_file_via_api(f"{VOLUME_BASE}/{target}/08_Phone_Summary.md")
    return content or f"No phone summary for {target}."


def tool_get_practice_package(target_date: str = "") -> str:
    """Get the full practice package (tutor brief + insights + phone summary).
    Args: target_date (str): ISO date. Defaults to today.
    Returns: Combined practice content.
    """
    target = target_date or date.today().isoformat()
    queue = _get_practice_from_queue(target)
    parts = []
    tutor = (queue or {}).get("mode7_tutor_brief", "")
    if not tutor:
        tutor = fetch_volume_file_via_api(f"{VOLUME_BASE}/{target}/07_AI_Tutor_Brief.md") or ""
    if tutor:
        parts.append(f"TUTOR BRIEF:\n{tutor}")
    insights = fetch_volume_file_via_api(f"{VOLUME_BASE}/{target}/key_insights.md") or ""
    if insights:
        parts.append(f"KEY INSIGHTS:\n{insights}")
    phone = (queue or {}).get("mode8_phone_summary", "")
    if phone:
        parts.append(f"QUICK SUMMARY:\n{phone}")
    return "\n\n".join(parts) if parts else f"No practice content for {target}."


def tool_get_podcast_transcript(target_date: str = "") -> str:
    """Get the full podcast transcript for the given date.
    Args: target_date (str): ISO date. Defaults to today.
    Returns: Podcast transcript text.
    """
    target = target_date or date.today().isoformat()
    content = fetch_volume_file_via_api(f"{VOLUME_BASE}/{target}/podcast_transcript.md")
    if content:
        return content
    queue = _get_practice_from_queue(target)
    if queue and queue.get("audio_script"):
        return queue["audio_script"]
    return f"No podcast transcript for {target}."


def tool_get_key_insights(target_date: str = "") -> str:
    """Get exam-critical key insights for the given date.
    Args: target_date (str): ISO date. Defaults to today.
    Returns: Key insights text.
    """
    target = target_date or date.today().isoformat()
    content = fetch_volume_file_via_api(f"{VOLUME_BASE}/{target}/key_insights.md")
    if content:
        return content
    queue = _get_practice_from_queue(target)
    if queue and queue.get("mode1_practice_answer"):
        return f"Practice Answer:\n{queue['mode1_practice_answer']}\n\nMemory Hook:\n{queue.get('memory_hook', 'N/A')}"
    return f"No insights for {target}."


def tool_list_daily_files(target_date: str = "") -> str:
    """List all generated practice files for a date.
    Args: target_date (str): ISO date. Defaults to today.
    Returns: File listing with names and sizes.
    """
    target = target_date or date.today().isoformat()
    files = list_volume_files(f"{VOLUME_BASE}/{target}")
    if not files:
        return f"No files for {target}."
    lines = [f"Files for {target}:"]
    for f in sorted(files, key=lambda x: x.get("name", "")):
        lines.append(f"  {f.get('name', '?')} ({f.get('file_size', 0):,} bytes)")
    return "\n".join(lines)


def tool_fetch_file(filename: str, target_date: str = "") -> str:
    """Fetch any raw file from the Daily Practice folder.
    Args: filename (str): e.g. 'key_insights.md', 'podcast_transcript.md'
          target_date (str): ISO date. Defaults to today.
    Returns: File content.
    """
    target = target_date or date.today().isoformat()
    content = fetch_volume_file_via_api(f"{VOLUME_BASE}/{target}/{filename}")
    return content or f"File not found: {filename} for {target}."


def tool_ask_agent(question: str) -> str:
    """Ask the UPSC tutor agent any question. Uses 80,800 vector chunks.
    Args: question (str): Your UPSC-related question.
    Returns: Agent response.
    """
    return call_agent(question)


def tool_query_delta(sql_query: str) -> str:
    """Run a SQL query against the UPSC Delta tables.
    Args: sql_query (str): SQL statement (SELECT only).
    Returns: JSON array of results.
    """
    if not sql_query.strip().upper().startswith("SELECT"):
        return "Only SELECT queries are allowed."
    rows = run_databricks_sql(sql_query)
    if rows is None:
        return "Query failed. Check SQL syntax."
    return json.dumps(rows[:20], indent=2, default=str)


def tool_definitions():
    """Return OpenAI-compatible tool definitions for AI Playground.
    Paste these into the Playground's 'Tools' panel or use with any
    OpenAI-compatible client (Cursor, Claude, etc.).
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "get_phone_summary",
                "description": "Get today's 2-min phone-optimized UPSC CA summary",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_date": {"type": "string", "description": "ISO date (YYYY-MM-DD). Defaults to today."}
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_practice_package",
                "description": "Get full practice package: tutor brief + insights + phone summary",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_date": {"type": "string", "description": "ISO date. Defaults to today."}
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_podcast_transcript",
                "description": "Get full 14-min podcast transcript for UPSC CA",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_date": {"type": "string", "description": "ISO date. Defaults to today."}
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_key_insights",
                "description": "Get top 5 exam-critical UPSC CA insights",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_date": {"type": "string", "description": "ISO date. Defaults to today."}
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "list_daily_files",
                "description": "List all generated practice files for a date",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_date": {"type": "string", "description": "ISO date. Defaults to today."}
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "fetch_file",
                "description": "Fetch any raw file from Daily Practice folder",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {"type": "string", "description": "Filename like 'key_insights.md'"},
                        "target_date": {"type": "string", "description": "ISO date. Defaults to today."}
                    },
                    "required": ["filename"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "ask_agent",
                "description": "Ask the UPSC tutor agent any question (80,800 vector chunks)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string", "description": "Your UPSC question"}
                    },
                    "required": ["question"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "query_delta",
                "description": "Run SQL SELECT against UPSC Delta tables (stories, traps, chunks, etc.)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sql_query": {"type": "string", "description": "SQL SELECT statement"}
                    },
                    "required": ["sql_query"]
                }
            }
        }
    ]


# Map tool names -> functions for easy dispatch
TOOL_DISPATCH = {
    "get_phone_summary": tool_get_phone_summary,
    "get_practice_package": tool_get_practice_package,
    "get_podcast_transcript": tool_get_podcast_transcript,
    "get_key_insights": tool_get_key_insights,
    "list_daily_files": tool_list_daily_files,
    "fetch_file": tool_fetch_file,
    "ask_agent": tool_ask_agent,
    "query_delta": tool_query_delta,
}


def handle_tool_call(tool_name: str, arguments: dict) -> str:
    """Dispatch a tool call from AI Playground or any OpenAI-compatible client.
    Usage:
        result = handle_tool_call("get_phone_summary", {"target_date": "2026-03-30"})
    """
    fn = TOOL_DISPATCH.get(tool_name)
    if not fn:
        return f"Unknown tool: {tool_name}. Available: {list(TOOL_DISPATCH.keys())}"
    try:
        return fn(**arguments)
    except Exception as e:
        return f"Tool error: {str(e)[:500]}"


if __name__ == "__main__":
    main()

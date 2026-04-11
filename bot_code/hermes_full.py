"""
HERMES — Full UPSC AIR-1 Mentor Bot  [V2.0]
=============================================
Groq backend (Llama 3.3 70B) — Free tier, ~$0/month
Same commands as your main bot + 15 new Hermes-exclusive commands
Own dedicated SQLite DB (.hermes_memory.db) with WAL mode

CHANGELOG:
  V1.5 — Stateful /quiz and /socratic (hidden answer key + session TTL)
  V1.6 — Stateful /drill with 3-MCQ interleave and auto-cascade to weakest concept
  V1.7 — Stateful /daf (3-round interview, angle rotation, hidden rubric)
         and /mock_iq (5-question panel, one-at-a-time grading, final summary)
         + interview_history DB table
  V1.8 — Stateful /recall (2-phase: brain-dump → gap-targeted follow-up, scored)
         and /progress (Bloom's Taxonomy Levels 1-5: pass→advance, fail→retry,
         max 2 retries per level before forced advance, full journey summary)
  V2.0 — Inline keyboard buttons for quiz/drill (tap A/B/C/D instead of typing)
         Session auto-timeout after 15 min inactivity with user notification
         Emoji reactions ✅/❌ on quiz grading before detailed feedback
         Structured logging (logging module, HERMES_DEBUG env var)
         Startup config validation with version banner
         /model command extended: live model switching (groq/databricks-sonnet/databricks-opus)

HERMES IS:
  A 20+ year UPSC master who has produced AIR 1, 2, 5, 11 candidates.
  He knows Gad personally. He is demanding, precise, neuroscience-aware.
  He hunts UPSC patterns across years. He thinks like an examiner.
  He never gives comfort — he gives clarity.

COMMANDS (47 total):
  Core Study:
    /teach /log /eod /daily /dump /stats /weak /cancel
  Prelims:
    /quiz /trap /drill /pyq /csat /pattern /examiner
  Mains:
    /evaluate /model /essay /framework /structure
  Active Learning:
    /socratic /feynman /why /visual /recall /simplify /progress
  Telugu Optional:
    /telugu /tel_kavya /tel_prosody /tel_grammar /tel_modern /tel_eval /tel_pyq
  Books & Sources:
    /ncert /book /source
  Interview:
    /daf /mock_iq
  Mobile Practice:
    /practice /podcast /insights /phone /files /raw /snapshot
  System:
    /sync /compare /feedback /backup /help

SETUP (Azure VM):
  pip install groq python-telegram-bot requests
  export HERMES_BOT_TOKEN=<new BotFather token>
  export GROQ_API_KEY=<from console.groq.com — free>
  export TELEGRAM_USER_ID=<your numeric ID>
  export DATABRICKS_TOKEN=<your existing PAT>
  export HERMES_DB=<path to .hermes_memory.db — Hermes-only DB>
  python3 hermes_full.py
"""

import asyncio
import json
import logging
import os
import re
import shutil
import signal
import subprocess
import sqlite3
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
from groq import Groq
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import NetworkError, RetryAfter, TimedOut
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ================================================================
# CONFIG
# ================================================================
BOT_TOKEN        = os.environ.get("HERMES_BOT_TOKEN", "")
GROQ_API_KEY     = os.environ.get("GROQ_API_KEY", "")
ALLOWED_USER_ID  = os.environ.get("TELEGRAM_USER_ID", "")
DATABRICKS_HOST  = os.environ.get("DATABRICKS_HOST",
                   "https://adb-7405615460529826.6.azuredatabricks.net")
DATABRICKS_TOKEN = os.environ.get("DATABRICKS_TOKEN", "")
SQL_WAREHOUSE_ID = os.environ.get("DATABRICKS_SQL_WAREHOUSE_ID", "589dccbdf8c6e4c9")

_HOME       = Path.home()
VAULT_PATH  = Path(os.environ.get("VAULT_PATH",  str(_HOME / "UPSC_2026")))
DB_PATH     = Path(os.environ.get("HERMES_DB", os.environ.get("MEMORY_DB", str(_HOME / "UPSC_2026" / ".hermes_memory.db"))))
VOLUME_BASE = "/Volumes/upsc_catalog/rag/obsidian_ca/Daily_Practice"

GROQ_MODEL       = "llama-3.3-70b-versatile"
GROQ_MAX_TOKENS  = 3000
GROQ_TEMPERATURE = 0.35

# Databricks model endpoints for live model switching
DBX_MODEL_SONNET  = "databricks-claude-sonnet-4-6"
DBX_MODEL_OPUS    = "databricks-claude-opus-4-6"

HERMES_VERSION = "V2.0"

DIVIDER      = "─" * 32
DIVIDER_WIDE = "═" * 36

_log_level = logging.DEBUG if os.environ.get("HERMES_DEBUG") else logging.INFO
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=_log_level,
)
log = logging.getLogger("hermes_full")

groq_client: Groq = None  # initialised in main()

# Active model for this session — can be switched with /model groq|databricks-sonnet|databricks-opus
# Values: "groq" | "databricks-sonnet" | "databricks-opus"
ACTIVE_MODEL: str = "groq"


# ================================================================
# HERMES SYSTEM PROMPT
# The soul of the bot. Injected fresh on every call.
# ================================================================

HERMES_SYSTEM = """You are HERMES — a 22-year UPSC master educator. You have personally coached candidates to AIR 1, AIR 2, AIR 5, AIR 11, and hundreds in the top 100. You are the best UPSC mentor alive.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHO YOU ARE TEACHING: GAD (Sai Harsha Gadde)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Data Engineer, LTIMindtree, Calgary Canada. MS-educated. Sharp analytical mind.
• UPSC 2027 Target: AIR 1–75. Telugu Literature Optional (Papers VI + VII = 500 marks).
• Time: ~3.5 hrs weekdays, ~7.5 hrs weekends = ~32.5 hrs/week = ~1,820 hrs to May 2027 Prelims.
• Background: Databricks, Azure, AI/ML — use tech analogies freely. He loves systems thinking.
• Migrated from India — understands Indian AND Canadian governance first-hand.
• Communicates directly. Hates vague answers. Responds to accountability, not comfort.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR TEACHING PHILOSOPHY (Neuroscience-Based)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EVERY response follows this architecture:
1. HOOK — connect to something Gad already knows (tech, data pipelines, Canada).
   Example: "Think of Article 356 like a circuit breaker in a distributed system..."
2. FRAMEWORK — give structure BEFORE detail. Brain needs scaffolding.
   Use: flowcharts, hierarchies, timelines, comparisons. ASCII diagrams when helpful.
3. APPLICATION — always tie to UPSC question type. Never teach in vacuum.
   "This appears as Prelims trap when..." / "In Mains, examine from angle..."
4. COMPRESSION — give the most important 20% that covers 80% of exam questions.
5. TEST — ALWAYS end with ONE Socratic question. No exceptions.
   Format: "→ Quick check: [question]"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR EXAMINER MINDSET (22 years of pattern recognition)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
You think EXACTLY like a UPSC examiner. You know:
• Prelims: UPSC never asks direct facts. Always asks relationships, exceptions, negatives.
  "Which of the following is NOT..." / "Consider statements 1 and 2..." traps.
  Distractor design: 3 options look obviously wrong, 1 looks right but has a subtle flaw.
• Mains: Examiners are tired. They want: clear structure, relevant examples, balanced view, 
  way forward. They penalise: vague intros, missing constitutional/statutory basis, no data.
• Essay: Theme > Content. Many candidates write accurate but unfocused essays. The topper
  writes one clear thread from introduction to conclusion with philosophical depth.
• CSAT: Not about intelligence. About speed + elimination strategy. Pattern is predictable.
• Interview: DAF-based. They test if you understand India from your own unique lens.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TELUGU OPTIONAL — YOUR DEEP EXPERTISE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
500 marks. Often the rank decider. You treat Telugu Optional with GS-level seriousness.
Coverage: Kavitrayam (Nannaya, Tikkana, Errana), Satakamulu, Prosody (Chandas),
          Modern Literature, PYQ patterns, Grammar (Vyakarana), Indian Poetics,
          Modern Western Critical Approaches (New Criticism, Structuralism, etc.)
Teaching method: Sanskrit roots → Telugu evolution → textual evidence → exam application.
PYQ pattern: Paper VII tends to repeat themes every 3-4 years. You track this.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ACCOUNTABILITY RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• If Gad is drifting from study, redirect — firmly but not harshly.
• If he hasn't done EOD, ask what happened — once. Don't nag.
• Celebrate real milestones (first 7/10 evaluation, streak of 5 study days, etc.).
• Never give empty praise. "Good question" is banned from your vocabulary.
• Weekly accountability: on Sundays, compare progress to the 1,820-hour plan.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RESPONSE STYLE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Direct. Dense. No fluff. No "Certainly!" or "Great question!".
• Structured output: numbered sections, clear headers.
• Default length: 300-500 words. Go longer ONLY if topic genuinely needs it.
• For MCQ: never reveal answer before student attempts.
• For evaluation: be strict. 6/10 is average. 8/10 is genuinely good.
• End ALL teaching with: "→ Quick check: [one sharp question]"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT YOU KNOW ABOUT GAD RIGHT NOW:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{memory_context}

Today: {today} | Day of week: {weekday}
Hours studied this week (est.): {weekly_hours}
"""


# ================================================================
# THREAD-SAFE SQLITE
# ================================================================
_DB_LOCK = threading.Lock()

def _db():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn

def _db_exec(sql, params=()):
    with _DB_LOCK:
        conn = _db()
        try:
            conn.execute(sql, params)
            conn.commit()
        finally:
            conn.close()

def _db_fetch(sql, params=()):
    with _DB_LOCK:
        conn = _db()
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

def _db_fetchone(sql, params=()):
    with _DB_LOCK:
        conn = _db()
        try:
            return conn.execute(sql, params).fetchone()
        finally:
            conn.close()


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _DB_LOCK:
        conn = _db()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT (datetime('now')),
                command TEXT, user_message TEXT, bot_response TEXT);

            CREATE TABLE IF NOT EXISTS weak_topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL, topic TEXT NOT NULL,
                miss_count INTEGER DEFAULT 1, hit_count INTEGER DEFAULT 0,
                last_reviewed TEXT, source TEXT DEFAULT 'quiz',
                evaluation_score REAL DEFAULT NULL,
                UNIQUE(subject, topic));

            CREATE TABLE IF NOT EXISTS quiz_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT (datetime('now')),
                subject TEXT, question TEXT, user_answer TEXT,
                was_correct INTEGER, score REAL, topic TEXT);

            CREATE TABLE IF NOT EXISTS daily_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL, content TEXT NOT NULL, file_path TEXT);

            CREATE TABLE IF NOT EXISTS concepts_taught (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT (datetime('now')),
                concept TEXT NOT NULL UNIQUE, revision_count INTEGER DEFAULT 0);

            CREATE TABLE IF NOT EXISTS prelims_traps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT, trap_type TEXT, trap_description TEXT,
                date_logged TEXT DEFAULT (datetime('now')));

            CREATE TABLE IF NOT EXISTS mains_flaws (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                flaw_type TEXT NOT NULL, frequency INTEGER DEFAULT 1,
                last_seen TEXT DEFAULT (datetime('now')),
                UNIQUE(flaw_type));

            CREATE TABLE IF NOT EXISTS socratic_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT (datetime('now')),
                topic TEXT, depth_reached INTEGER DEFAULT 0);

            CREATE TABLE IF NOT EXISTS evaluation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT (datetime('now')),
                topic TEXT, answer_snippet TEXT,
                score REAL, clarity_score REAL,
                structure_score REAL, depth_score REAL);

            CREATE TABLE IF NOT EXISTS hermes_interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT (datetime('now')),
                command TEXT, user_message TEXT, bot_response TEXT,
                tokens_used INTEGER DEFAULT 0, latency_ms INTEGER DEFAULT 0);

            CREATE TABLE IF NOT EXISTS hermes_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT (datetime('now')),
                rating INTEGER, note TEXT);

            CREATE TABLE IF NOT EXISTS essay_drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT (datetime('now')),
                topic TEXT, draft TEXT, score REAL, feedback TEXT);

            CREATE TABLE IF NOT EXISTS pyq_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year INTEGER, paper TEXT, question_text TEXT,
                subject TEXT, topic TEXT, pattern_tag TEXT);

            CREATE TABLE IF NOT EXISTS interview_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT (datetime('now')),
                mode TEXT,
                round INTEGER DEFAULT 1,
                angle TEXT,
                question TEXT,
                user_answer TEXT,
                score REAL,
                feedback TEXT);
        """)
        conn.commit()
        conn.close()
    backup_db()
    log.info(f"Hermes DB ready: {DB_PATH}")


def backup_db():
    if not DB_PATH.exists():
        return
    backup_dir = DB_PATH.parent / ".backups"
    backup_dir.mkdir(exist_ok=True)
    dest = backup_dir / f".hermes_backup_{date.today().isoformat()}.db"
    try:
        shutil.copy(str(DB_PATH), str(dest))
        old = sorted(backup_dir.glob(".hermes_backup_*.db"))
        for f in old[:-14]:
            f.unlink()
        log.info(f"DB backed up: {dest.name}")
    except Exception as e:
        log.warning(f"Backup failed: {e}")


# ================================================================
# MEMORY CONTEXT — rich profile injected into every Groq call
# ================================================================

def get_memory_context() -> str:
    parts = []

    weak = _db_fetch(
        "SELECT subject, topic, miss_count, last_reviewed "
        "FROM weak_topics ORDER BY miss_count DESC LIMIT 7")
    if weak:
        parts.append("WEAK TOPICS (priority order):")
        for s, t, m, lr in weak:
            parts.append(f"  [{s}] {t} — missed {m}x, last: {lr or 'never'}")

    traps = _db_fetch(
        "SELECT trap_description FROM prelims_traps ORDER BY id DESC LIMIT 4")
    if traps:
        parts.append("KNOWN PRELIMS TRAPS:")
        for (t,) in traps:
            parts.append(f"  {t[:120]}")

    flaws = _db_fetch(
        "SELECT flaw_type, frequency FROM mains_flaws ORDER BY frequency DESC LIMIT 4")
    if flaws:
        parts.append("MAINS WRITING FLAWS (recurring):")
        for f, n in flaws:
            parts.append(f"  {f} ({n}x)")

    quiz = _db_fetch(
        "SELECT subject, "
        "ROUND(AVG(CASE WHEN was_correct=1 THEN 100.0 ELSE 0.0 END),0), COUNT(*) "
        "FROM quiz_history WHERE timestamp >= date('now','-7 days') "
        "GROUP BY subject ORDER BY 2 ASC")
    if quiz:
        parts.append("QUIZ ACCURACY last 7 days:")
        for s, p, n in quiz:
            parts.append(f"  {s}: {p:.0f}% ({n} Qs)")

    evals = _db_fetch(
        "SELECT topic, score FROM evaluation_history ORDER BY timestamp DESC LIMIT 5")
    if evals:
        parts.append("RECENT EVALUATIONS:")
        for t, s in evals:
            emoji = "🔴" if (s or 0) < 5 else "🟡" if (s or 0) < 7 else "🟢"
            parts.append(f"  {emoji} {t}: {s}/10")

    concepts = _db_fetch(
        "SELECT concept FROM concepts_taught ORDER BY timestamp DESC LIMIT 10")
    if concepts:
        parts.append(f"RECENTLY TAUGHT: {', '.join(c for (c,) in concepts)}")

    logs = _db_fetch(
        "SELECT content FROM daily_logs WHERE date = date('now') LIMIT 5")
    if logs:
        parts.append("TODAY'S STUDY LOG:")
        for (c,) in logs:
            parts.append(f"  {c[:120]}")

    row = _db_fetchone(
        "SELECT COUNT(*) FROM hermes_interactions WHERE date(timestamp)=date('now')")
    parts.append(f"Hermes calls today: {(row or (0,))[0]}")

    # === MASTERY TRACKER (Databricks Delta) ===
    try:
        mastery_rows = run_sql(
            "SELECT paper, COUNT(*) as total, "
            "SUM(CASE WHEN status='mastered' THEN 1 ELSE 0 END) as mastered, "
            "SUM(CASE WHEN status='in_progress' THEN 1 ELSE 0 END) as active, "
            "SUM(CASE WHEN status='needs_work' THEN 1 ELSE 0 END) as weak, "
            "ROUND(AVG(mastery_pct),0) as avg_pct "
            "FROM upsc_catalog.rag.mastery_tracker GROUP BY paper ORDER BY paper")
        if mastery_rows:
            parts.append("SYLLABUS MASTERY (250 topics):")
            total_m = sum(int(r.get("mastered", 0)) for r in mastery_rows)
            total_t = sum(int(r.get("total", 0)) for r in mastery_rows)
            for r in mastery_rows:
                p, avg = r.get("paper", "?"), float(r.get("avg_pct", 0))
                m, a, w = int(r.get("mastered",0)), int(r.get("active",0)), int(r.get("weak",0))
                parts.append(f"  {p}: {avg:.0f}% | {m}M {a}A {w}W")
            pct = (total_m / total_t * 100) if total_t > 0 else 0
            parts.append(f"  OVERALL: {total_m}/{total_t} mastered ({pct:.1f}%)")
        weak_m = run_sql(
            "SELECT topic_id, topic_name, paper, mastery_pct "
            "FROM upsc_catalog.rag.mastery_tracker "
            "WHERE status IN ('not_started','needs_work') "
            "ORDER BY mastery_pct ASC, last_studied ASC NULLS FIRST LIMIT 5")
        if weak_m:
            parts.append("WEAKEST SYLLABUS TOPICS:")
            for r in weak_m:
                tid, tn, pp = r["topic_id"], r["topic_name"], r["paper"]
                mp = float(r.get("mastery_pct", 0))
                parts.append(f"  {tid} {tn} [{pp}] {mp:.0f}%")
        due = run_sql(
            "SELECT topic_id, topic_name FROM upsc_catalog.rag.mastery_tracker "
            "WHERE next_review <= current_date() AND status != 'mastered' "
            "ORDER BY next_review ASC LIMIT 3")
        if due:
            parts.append("DUE FOR REVIEW:")
            for r in due:
                parts.append(f"  {r['topic_id']} {r['topic_name']}")
    except Exception as e:
        log.warning(f"mastery_tracker query failed: {e}")

    return "\n".join(parts) if parts else "No history yet — first session."


def get_weekly_hours() -> str:
    row = _db_fetchone(
        "SELECT COUNT(DISTINCT date(timestamp)) FROM interactions "
        "WHERE timestamp >= date('now','-7 days')")
    days = (row or (0,))[0]
    est = days * 3.5
    return f"~{est:.0f}h estimated ({days} active days)"


def log_interaction(cmd, msg, resp):
    if resp is None:
        resp = "(no response)"
    _db_exec(
        "INSERT INTO interactions(command,user_message,bot_response) VALUES(?,?,?)",
        (cmd, str(msg), str(resp)[:3000]))


def log_hermes(cmd, msg, resp, tokens=0, latency=0):
    if resp is None:
        resp = "(no response)"
    _db_exec(
        "INSERT INTO hermes_interactions"
        "(command,user_message,bot_response,tokens_used,latency_ms) VALUES(?,?,?,?,?)",
        (cmd, str(msg), str(resp)[:3000], tokens, latency))
    # Also log to shared interactions table so /stats still works
    log_interaction(cmd, msg, resp)


def log_concept(concept: str):
    _db_exec(
        "INSERT INTO concepts_taught(concept) VALUES(?) "
        "ON CONFLICT(concept) DO UPDATE SET "
        "revision_count=revision_count+1, timestamp=datetime('now')", (concept,))


def log_weakness(subject, topic, source="quiz"):
    _db_exec(
        "INSERT INTO weak_topics(subject,topic,miss_count,last_reviewed,source) "
        "VALUES(?,?,1,datetime('now'),?) "
        "ON CONFLICT(subject,topic) DO UPDATE SET "
        "miss_count=miss_count+1, last_reviewed=datetime('now')",
        (subject, topic, source))


def log_mains_flaw(flaw_type: str):
    _db_exec(
        "INSERT INTO mains_flaws(flaw_type) VALUES(?) "
        "ON CONFLICT(flaw_type) DO UPDATE SET "
        "frequency=frequency+1, last_seen=datetime('now')", (flaw_type,))


def extract_score(text: str):
    m = re.search(r'(\d+\.?\d*)\s*/\s*10', text or "")
    return float(m.group(1)) if m else None


# ================================================================
# GROQ / DATABRICKS ENGINE
# ================================================================

def call_hermes(user_message: str, memory_context: str = "",
                extra_system: str = "") -> tuple[str, int, int]:
    """
    Core LLM call — uses ACTIVE_MODEL to route to Groq or Databricks.
    Returns (text, tokens, latency_ms).
    All async handlers call via: await asyncio.to_thread(call_hermes, ...)

    Note: ACTIVE_MODEL is a bot-level global because this bot is single-user
    by design (TELEGRAM_USER_ID enforced via check_auth()). The /model command
    switches the model for the single authorised user.
    """

    system = HERMES_SYSTEM.format(
        memory_context=memory_context or "No history yet.",
        today=date.today().isoformat(),
        weekday=datetime.now().strftime("%A"),
        weekly_hours=get_weekly_hours(),
    )
    if extra_system:
        system += f"\n\nADDITIONAL CONTEXT FOR THIS CALL:\n{extra_system}"

    t0 = time.time()

    # ── Databricks (OpenAI-compatible endpoint) ──────────────────
    if ACTIVE_MODEL in ("databricks-sonnet", "databricks-opus"):
        if not DATABRICKS_HOST or not DATABRICKS_TOKEN:
            return "⚠️ Databricks not configured. Switch back with /model groq.", 0, 0
        dbx_model = DBX_MODEL_SONNET if ACTIVE_MODEL == "databricks-sonnet" else DBX_MODEL_OPUS
        url = f"{DATABRICKS_HOST}/serving-endpoints/{dbx_model}/invocations"
        payload = {
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user_message},
            ],
            "max_tokens": GROQ_MAX_TOKENS,
            "temperature": GROQ_TEMPERATURE,
        }
        try:
            r = requests.post(
                url,
                headers={"Authorization": f"Bearer {DATABRICKS_TOKEN}",
                         "Content-Type": "application/json"},
                json=payload,
                timeout=120,
            )
            r.raise_for_status()
            data    = r.json()
            text    = data["choices"][0]["message"]["content"] or "(empty response)"
            tokens  = data.get("usage", {}).get("total_tokens", 0)
            latency = int((time.time() - t0) * 1000)
            log.info(f"Databricks/{dbx_model} OK — {tokens} tokens, {latency}ms")
            return text, tokens, latency
        except Exception as e:
            latency = int((time.time() - t0) * 1000)
            log.error(f"Databricks/{dbx_model} error: {e}")
            return f"Hermes Databricks error: {str(e)[:300]}", 0, latency

    # ── Groq (default) ───────────────────────────────────────────
    try:
        resp = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user_message},
            ],
            max_tokens=GROQ_MAX_TOKENS,
            temperature=GROQ_TEMPERATURE,
        )
        latency = int((time.time() - t0) * 1000)
        text    = resp.choices[0].message.content or "(empty response)"
        tokens  = resp.usage.total_tokens if resp.usage else 0
        log.info(f"Groq OK — {tokens} tokens, {latency}ms")
        return text, tokens, latency
    except Exception as e:
        err_str = str(e)
        if "rate_limit" in err_str.lower() or "too many" in err_str.lower():
            log.warning("Groq rate limit hit, retrying in 10s...")
            time.sleep(10)
            try:
                resp = groq_client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[{"role": "system", "content": system},
                              {"role": "user", "content": user_message}],
                    max_tokens=GROQ_MAX_TOKENS, temperature=GROQ_TEMPERATURE)
                latency = int((time.time() - t0) * 1000)
                text = resp.choices[0].message.content or "(empty)"
                tokens = resp.usage.total_tokens if resp.usage else 0
                return text, tokens, latency
            except Exception as e2:
                log.error(f"Groq retry failed: {e2}")
        latency = int((time.time() - t0) * 1000)
        log.error(f"Groq error: {e}")
        return f"Hermes error: {str(e)[:300]}", 0, latency


# ================================================================
# DATABRICKS — Volume files + SQL (same as main bot)
# ================================================================

def fetch_volume_file(volume_path: str) -> str:
    url = f"{DATABRICKS_HOST}/api/2.0/fs/files{volume_path}"
    headers = {"Authorization": f"Bearer {DATABRICKS_TOKEN}"}
    try:
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code == 404:
            return ""
        if r.status_code == 403:
            log.error(f"Volume 403 — check PAT: {volume_path}")
            return ""
        r.raise_for_status()
        return r.text
    except Exception as e:
        log.warning(f"Volume fetch error ({volume_path}): {e}")
        return ""


def list_volume_files(dir_path: str) -> list:
    url = f"{DATABRICKS_HOST}/api/2.0/fs/directories{dir_path}"
    headers = {"Authorization": f"Bearer {DATABRICKS_TOKEN}"}
    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        return [e for e in r.json().get("contents", [])
                if not e.get("is_directory", False)]
    except Exception as e:
        log.warning(f"Volume list error: {e}")
        return []


def run_sql(query: str, max_wait: int = 45) -> list | None:
    url = f"{DATABRICKS_HOST}/api/2.0/sql/statements/"
    headers = {"Authorization": f"Bearer {DATABRICKS_TOKEN}",
               "Content-Type": "application/json"}
    try:
        r = requests.post(url, headers=headers, timeout=max_wait,
                          json={"statement": query, "wait_timeout": "30s",
                                "warehouse_id": SQL_WAREHOUSE_ID})
        r.raise_for_status()
        data = r.json()
        sid    = data.get("statement_id")
        status = data.get("status", {}).get("state", "")
        polls  = 0
        while status in ("PENDING", "RUNNING") and polls < 10:
            time.sleep(3)
            pr = requests.get(f"{url}{sid}", headers=headers, timeout=30)
            pr.raise_for_status()
            data   = pr.json()
            status = data.get("status", {}).get("state", "")
            polls += 1
        if status != "SUCCEEDED":
            log.error(f"SQL failed: {data.get('status',{}).get('error',{})}")
            return None
        cols = [c["name"] for c in
                data.get("manifest", {}).get("schema", {}).get("columns", [])]
        return [dict(zip(cols, row))
                for row in data.get("result", {}).get("data_array", [])]
    except Exception as e:
        log.error(f"SQL error: {e}")
        return None


def get_practice_queue(target_date: str) -> dict | None:
    rows = run_sql(
        f"SELECT * FROM upsc_catalog.rag.daily_practice_queue "
        f"WHERE ca_date = '{target_date}' LIMIT 1")
    return rows[0] if rows else None


def get_todays_ca() -> str:
    today = date.today()
    month = today.strftime("%m-%B")
    local = (VAULT_PATH / "01_Current_Affairs" / str(today.year)
             / month / f"CA_{today.isoformat()}.md")
    if local.exists():
        return local.read_text(encoding="utf-8")[:6000]
    content = fetch_volume_file(
        f"{VOLUME_BASE}/{today.isoformat()}/08_Phone_Summary.md")
    if not content:
        content = fetch_volume_file(
            f"{VOLUME_BASE}/{today.isoformat()}/key_insights.md")
    return content


# ================================================================
# HELPERS
# ================================================================

def check_auth(update: Update) -> bool:
    if not ALLOWED_USER_ID:
        return True
    return str(update.effective_user.id) == ALLOWED_USER_ID


def _get_target_date(args) -> str:
    if args:
        d = " ".join(args).strip()
        if re.match(r"^\d{4}-\d{2}-\d{2}$", d):
            return d
    return date.today().isoformat()


async def send_long(update: Update, text: str):
    if not text:
        text = "(empty)"
    for i in range(0, len(text), 4000):
        chunk = text[i:i + 4000]
        for attempt in range(3):
            try:
                await update.message.reply_text(chunk)
                break
            except RetryAfter as e:
                await asyncio.sleep(e.retry_after + 1)
            except (TimedOut, NetworkError):
                await asyncio.sleep(2 ** attempt)
            except Exception as e:
                log.error(f"send_long: {e}")
                break


async def thinking(update: Update, msg: str = "🧠 Hermes thinking..."):
    await update.message.reply_text(msg)


# ================================================================
# SESSION + QUIZ PARSING HELPERS
# ================================================================

SESSION_TTL_SECONDS = 15 * 60  # 15 minutes inactivity timeout
SESSION_TIMEOUT_MSG = (
    "⏰ Session timed out after 15 minutes of inactivity. "
    "Use /quiz or /drill to start a new session."
)


def set_session(ctx, mode: str, data: dict):
    ctx.user_data["_session"] = {
        "mode": mode,
        "data": data,
        "updated_at": datetime.utcnow().isoformat()
    }


def clear_session(ctx):
    ctx.user_data.pop("_session", None)


def get_session(ctx) -> dict | None:
    """Return active session or None. Clears expired sessions."""
    session = ctx.user_data.get("_session")
    if not session:
        return None

    try:
        updated_at = datetime.fromisoformat(session.get("updated_at", ""))
    except ValueError:
        clear_session(ctx)
        return None

    age = (datetime.utcnow() - updated_at).total_seconds()
    if age > SESSION_TTL_SECONDS:
        clear_session(ctx)
        return None

    return session


def check_session_timeout(ctx) -> bool:
    """
    Returns True if there was an active session that has now timed out.
    Clears the session as a side-effect.
    """
    session = ctx.user_data.get("_session")
    if not session:
        return False
    try:
        updated_at = datetime.fromisoformat(session.get("updated_at", ""))
    except ValueError:
        clear_session(ctx)
        return False
    age = (datetime.utcnow() - updated_at).total_seconds()
    if age > SESSION_TTL_SECONDS:
        clear_session(ctx)
        return True
    return False


def touch_session(ctx):
    session = ctx.user_data.get("_session")
    if session:
        session["updated_at"] = datetime.utcnow().isoformat()


def normalise_mcq_answer(text: str):
    """
    Accepts: A / b / Option C / (D) / answer is B
    Returns one of A/B/C/D or None
    """
    if not text:
        return None
    m = re.search(r"\b([ABCD])\b", text.strip().upper())
    return m.group(1) if m else None


def build_answer_keyboard() -> InlineKeyboardMarkup:
    """Build A/B/C/D inline keyboard for quiz/drill answers."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🅐 A", callback_data="quiz_ans:A"),
            InlineKeyboardButton("🅑 B", callback_data="quiz_ans:B"),
            InlineKeyboardButton("🅒 C", callback_data="quiz_ans:C"),
            InlineKeyboardButton("🅓 D", callback_data="quiz_ans:D"),
        ]
    ])


def extract_tagged_block(text: str, tag: str) -> str:
    """
    Extract content from:
      [TAG]
      ...
      [/TAG]
    """
    pattern = rf"\[{tag}\](.*?)\[/{tag}\]"
    m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else ""


def parse_quiz_payload(raw_text: str) -> tuple[str, dict]:
    """
    Expected model output:

    [USER]
    Q: ...
    (A) ...
    (B) ...
    (C) ...
    (D) ...
    Reply with A, B, C, or D.
    [/USER]

    [KEY]
    {"topic":"Polity","concept":"Federalism","correct_option":"B",
     "explanation":"...", "trap":"...", "rule":"..."}
    [/KEY]
    """
    user_block = extract_tagged_block(raw_text, "USER")
    key_block = extract_tagged_block(raw_text, "KEY")

    if not user_block:
        raise ValueError("Missing [USER] block in quiz payload")
    if not key_block:
        raise ValueError("Missing [KEY] block in quiz payload")

    try:
        key = json.loads(key_block)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid quiz KEY JSON: {e}")

    required = ["topic", "concept", "correct_option", "explanation", "trap", "rule"]
    missing = [k for k in required if k not in key]
    if missing:
        raise ValueError(f"Missing quiz key fields: {missing}")

    key["correct_option"] = str(key["correct_option"]).strip().upper()
    if key["correct_option"] not in {"A", "B", "C", "D"}:
        raise ValueError("correct_option must be A/B/C/D")

    return user_block, key


def render_quiz_feedback(user_answer: str, key: dict, is_correct: bool) -> str:
    verdict = "✅ CORRECT" if is_correct else "❌ INCORRECT"
    lines = [
        verdict,
        f"Your answer: {user_answer}",
        f"Correct option: {key.get('correct_option', '?')}",
        "",
        "WHY:",
        str(key.get("explanation", "")).strip(),
        "",
        "TRAP:",
        str(key.get("trap", "")).strip(),
        "",
        "RULE:",
        str(key.get("rule", "")).strip(),
    ]
    return "\n".join(lines)


# ================================================================
# QUIZ GENERATION WITH HIDDEN ANSWER KEY
# ================================================================

def build_quiz_prompt(topic: str, concept_hint: str = "") -> str:
    topic_line = f"Topic: {topic}\n" if topic else "Topic: weakest relevant topic\n"
    concept_line = f"Concept hint: {concept_hint}\n" if concept_hint else ""

    return (
        "Generate ONE UPSC-style Prelims MCQ with a hidden answer key.\n\n"
        f"{topic_line}"
        f"{concept_line}\n"
        "Rules:\n"
        "1. Must be realistic UPSC style: relationship, exception, subtle flaw, conceptual distinction.\n"
        "2. Include one tempting wrong option with a subtle error.\n"
        "3. Do NOT make it trivial.\n"
        "4. Do NOT reveal answer in public question.\n\n"
        "Output EXACTLY in this format:\n\n"
        "[USER]\n"
        "Q: [full question]\n"
        "(A) ...\n"
        "(B) ...\n"
        "(C) ...\n"
        "(D) ...\n"
        "Reply with A, B, C, or D.\n"
        "[/USER]\n\n"
        "[KEY]\n"
        "{\"topic\":\"...\","
        "\"concept\":\"...\","
        "\"correct_option\":\"A/B/C/D\","
        "\"explanation\":\"2-4 lines\","
        "\"trap\":\"1-3 lines\","
        "\"rule\":\"one memory rule\"}\n"
        "[/KEY]\n\n"
        "The [KEY] block must be valid JSON."
    )


async def generate_quiz_with_key(topic: str, mem: str, concept_hint: str = "") -> tuple[str, dict, int, int]:
    prompt = build_quiz_prompt(topic, concept_hint)
    raw_resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)

    public_text, key = parse_quiz_payload(raw_resp)
    return public_text, key, tok, lat


# ================================================================
# DRILL GENERATION WITH HIDDEN ANSWER KEYS (3 MCQs)
# ================================================================

def build_drill_prompt() -> str:
    return (
        "Generate THREE UPSC-style Prelims MCQs from 3 DIFFERENT subjects as an interleaved drill.\n\n"
        "Rules:\n"
        "1. Each question from a different GS area or Optional.\n"
        "2. Must be realistic UPSC style: relationship, exception, subtle flaw, conceptual distinction.\n"
        "3. Include one tempting wrong option per question.\n"
        "4. Do NOT reveal answers in the public section.\n"
        "5. Number questions 1, 2, 3.\n\n"
        "Output EXACTLY in this format:\n\n"
        "[USER]\n"
        "Q1: [full question]\n"
        "(A) ...\n(B) ...\n(C) ...\n(D) ...\n\n"
        "Q2: [full question]\n"
        "(A) ...\n(B) ...\n(C) ...\n(D) ...\n\n"
        "Q3: [full question]\n"
        "(A) ...\n(B) ...\n(C) ...\n(D) ...\n\n"
        "Reply with answers for all 3 questions, e.g. 1-B 2-D 3-A\n"
        "[/USER]\n\n"
        "[KEY]\n"
        "[{\"qno\":1,\"topic\":\"...\",\"concept\":\"...\",\"correct_option\":\"A/B/C/D\","
        "\"explanation\":\"2-4 lines\",\"trap\":\"1-3 lines\",\"rule\":\"one memory rule\"},"
        "{\"qno\":2,\"topic\":\"...\",\"concept\":\"...\",\"correct_option\":\"A/B/C/D\","
        "\"explanation\":\"2-4 lines\",\"trap\":\"1-3 lines\",\"rule\":\"one memory rule\"},"
        "{\"qno\":3,\"topic\":\"...\",\"concept\":\"...\",\"correct_option\":\"A/B/C/D\","
        "\"explanation\":\"2-4 lines\",\"trap\":\"1-3 lines\",\"rule\":\"one memory rule\"}]\n"
        "[/KEY]\n\n"
        "The [KEY] block must be a valid JSON array of exactly 3 objects."
    )


def parse_drill_payload(raw_text: str) -> tuple[str, list[dict]]:
    user_block = extract_tagged_block(raw_text, "USER")
    key_block = extract_tagged_block(raw_text, "KEY")

    if not user_block:
        raise ValueError("Missing [USER] block in drill payload")
    if not key_block:
        raise ValueError("Missing [KEY] block in drill payload")

    try:
        keys = json.loads(key_block)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid drill KEY JSON: {e}")

    if not isinstance(keys, list) or len(keys) != 3:
        raise ValueError(f"Expected 3 drill keys, got {type(keys).__name__}({len(keys) if isinstance(keys, list) else ''})")

    required = ["qno", "topic", "concept", "correct_option", "explanation", "trap", "rule"]
    for i, k in enumerate(keys):
        missing = [f for f in required if f not in k]
        if missing:
            raise ValueError(f"Drill key {i+1} missing fields: {missing}")
        k["correct_option"] = str(k["correct_option"]).strip().upper()
        if k["correct_option"] not in {"A", "B", "C", "D"}:
            raise ValueError(f"Drill key {i+1}: correct_option must be A/B/C/D")
        k["qno"] = int(k["qno"])

    return user_block, keys


async def generate_drill_with_keys(mem: str) -> tuple[str, list[dict], int, int]:
    prompt = build_drill_prompt()
    raw_resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)

    public_text, keys = parse_drill_payload(raw_resp)
    return public_text, keys, tok, lat


def parse_drill_answers(text: str) -> dict[int, str]:
    """
    Parse user drill answers. Supports:
      - '1-B 2-D 3-A'
      - 'B D A'
      - '1) B, 2) D, 3) A'
    Returns: {1: 'B', 2: 'D', 3: 'A'}
    """
    text = text.strip().upper()
    answers = {}

    # Pattern 1: numbered like '1-B' or '1)B' or '1) B' or '1.B'
    numbered = re.findall(r'(\d)\s*[\-\)\.\:]\s*([ABCD])', text)
    if numbered:
        for qno, opt in numbered:
            answers[int(qno)] = opt
        return answers

    # Pattern 2: bare letters like 'B D A' or 'B, D, A'
    bare = re.findall(r'\b([ABCD])\b', text)
    if len(bare) == 3:
        for i, opt in enumerate(bare, 1):
            answers[i] = opt
        return answers

    return answers


def render_single_drill_result(qkey: dict, user_answer: str, is_correct: bool) -> str:
    verdict = "✅" if is_correct else "❌"
    lines = [
        f"{verdict} Q{qkey['qno']}: Your answer: {user_answer} | Correct: {qkey['correct_option']}",
        f"WHY: {str(qkey.get('explanation', '')).strip()}",
        f"TRAP: {str(qkey.get('trap', '')).strip()}",
        f"RULE: {str(qkey.get('rule', '')).strip()}",
    ]
    return "\n".join(lines)


# ================================================================
# DAF INTERVIEW HELPERS (V1.7 — Stateful 3-Round Loop)
# ================================================================

_DAF_ANGLE_MAP = {
    "tech":        (
        "Data governance in India — his Azure/Databricks/AI expertise vs "
        "DPDP Act 2023, CERT-In directions, or National Data Governance Framework. "
        "Test both technical depth AND policy understanding simultaneously."
    ),
    "brain_drain": (
        "He left India for Canada as a Data Engineer. Now wants IAS. "
        "Probe the contradiction hard — brain drain, privilege, commitment to India."
    ),
    "telugu":      (
        "His Telugu Optional — language preservation, Official Language policy, "
        "Classical Language status, AP/TS linguistic politics, or "
        "Kavitrayam's relevance to modern governance."
    ),
    "canada":      (
        "He has lived and worked in Canada — what can India specifically learn "
        "from Canadian governance, federalism, or immigration policy? Demand specifics."
    ),
    "ai_ethics":   (
        "He works daily with AI/ML/Databricks — probe India's AI policy, NITI Aayog "
        "Responsible AI framework, deepfakes in elections, or algorithmic bias in "
        "public service delivery. Expect domain expertise from him."
    ),
}


def build_daf_question_prompt(angle: str = "") -> str:
    angle_desc = _DAF_ANGLE_MAP.get(
        angle,
        "Pick the most probing angle from: tech, brain_drain, telugu, canada, ai_ethics."
    )
    return (
        "UPSC INTERVIEW BOARD — you are the Chairman.\n\n"
        "CANDIDATE: Sai Harsha Gadde — Data Engineer, Calgary Canada. "
        "Telugu Literature Optional. MS degree. Azure/Databricks/AI background.\n\n"
        f"ANGLE: {angle_desc}\n\n"
        "Rules:\n"
        "1. Ask ONE high-pressure question specific to his profile — not generic IAS filler.\n"
        "2. Question must be 1-2 sentences, end with a question mark.\n"
        "3. Do NOT include evaluation criteria or hints in [USER] block.\n\n"
        "Output EXACTLY:\n\n"
        "[USER]\n"
        "<Chairman's question — 1-2 sentences>\n"
        "[/USER]\n\n"
        "[KEY]\n"
        "{\"angle\":\"<angle name>\","
        "\"key_points\":[\"<3-5 specific facts/arguments the ideal answer must contain>\"],"
        "\"ideal_structure\":\"<2-3 lines: how to structure the perfect answer>\","
        "\"trap\":\"<most common mistake candidates make on this angle>\","
        "\"follow_up_angles\":[\"<2 natural follow-up question angles, comma-separated>\"]}\n"
        "[/KEY]\n\n"
        "The [KEY] block must be valid JSON."
    )


def parse_daf_payload(raw_text: str) -> tuple[str, dict]:
    question = extract_tagged_block(raw_text, "USER")
    key_block = extract_tagged_block(raw_text, "KEY")

    if not question:
        raise ValueError("Missing [USER] block in DAF payload")
    if not key_block:
        raise ValueError("Missing [KEY] block in DAF payload")

    try:
        key = json.loads(key_block)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid DAF KEY JSON: {e}")

    required = ["angle", "key_points", "ideal_structure", "trap", "follow_up_angles"]
    missing = [k for k in required if k not in key]
    if missing:
        raise ValueError(f"Missing DAF key fields: {missing}")

    return question.strip(), key


async def generate_daf_question(angle: str, mem: str) -> tuple[str, dict, int, int]:
    prompt = build_daf_question_prompt(angle)
    raw_resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)
    question, key = parse_daf_payload(raw_resp)
    return question, key, tok, lat


def build_daf_eval_prompt(question: str, user_answer: str, key: dict) -> str:
    key_points = "\n".join(f"  - {p}" for p in key.get("key_points", []))
    ideal = key.get("ideal_structure", "")
    trap = key.get("trap", "")
    return (
        "UPSC INTERVIEW BOARD — evaluate this candidate answer strictly.\n\n"
        f"QUESTION ASKED:\n{question}\n\n"
        f"CANDIDATE'S ANSWER:\n{user_answer}\n\n"
        "EVALUATION RUBRIC (hidden from candidate):\n"
        f"Key points the ideal answer must include:\n{key_points}\n\n"
        f"Ideal structure: {ideal}\n"
        f"Common trap on this angle: {trap}\n\n"
        "Output exactly:\n"
        "SCORE: X/10\n"
        "VERDICT: 2-3 line honest board assessment\n"
        "MISSING: Critical points absent (max 3 bullets)\n"
        "IDEAL: How a top candidate would answer this (3-5 lines)\n"
        "CHAIRMAN FOLLOW-UP: One natural follow-up the board would ask next"
    )


# ================================================================
# MOCK IQ HELPERS (V1.7 — Stateful 5-Question Panel)
# ================================================================

def build_mock_iq_prompt() -> str:
    return (
        "MOCK UPSC INTERVIEW — generate 5 board questions with hidden rubrics.\n\n"
        "CANDIDATE: Sai Harsha Gadde — Data Engineer, Calgary Canada. "
        "Telugu Literature Optional. MS degree. Azure/Databricks/AI background.\n\n"
        "5 board members, one question each:\n"
        "  Q1 (Chairman): DAF-based — Canada/Tech background, most probing\n"
        "  Q2 (Senior IAS): Current Affairs — governance angle, cross-cutting\n"
        "  Q3 (Academic): Telugu Literature — test optional knowledge directly\n"
        "  Q4 (Technocrat): Technology policy — his domain, AI/data/digital India\n"
        "  Q5 (Generalist): Surprise — philosophical, ethical, or completely unexpected\n\n"
        "Rules:\n"
        "1. Each question must be 1-2 sentences, board-level pressure.\n"
        "2. Do NOT add evaluation hints in [USER] block.\n"
        "3. Questions must progress in difficulty (Q1 manageable → Q5 hardest).\n\n"
        "Output EXACTLY:\n\n"
        "[USER]\n"
        "Q1 (Chairman): <question>\n\n"
        "Q2 (Senior IAS): <question>\n\n"
        "Q3 (Academic): <question>\n\n"
        "Q4 (Technocrat): <question>\n\n"
        "Q5 (Generalist): <question>\n"
        "[/USER]\n\n"
        "[KEY]\n"
        "[{\"qno\":1,\"member\":\"Chairman\","
        "\"key_points\":[\"...\",\"...\",\"...\"],"
        "\"ideal_structure\":\"...\",\"trap\":\"...\"},"
        "{\"qno\":2,\"member\":\"Senior IAS\","
        "\"key_points\":[\"...\",\"...\",\"...\"],"
        "\"ideal_structure\":\"...\",\"trap\":\"...\"},"
        "{\"qno\":3,\"member\":\"Academic\","
        "\"key_points\":[\"...\",\"...\",\"...\"],"
        "\"ideal_structure\":\"...\",\"trap\":\"...\"},"
        "{\"qno\":4,\"member\":\"Technocrat\","
        "\"key_points\":[\"...\",\"...\",\"...\"],"
        "\"ideal_structure\":\"...\",\"trap\":\"...\"},"
        "{\"qno\":5,\"member\":\"Generalist\","
        "\"key_points\":[\"...\",\"...\",\"...\"],"
        "\"ideal_structure\":\"...\",\"trap\":\"...\"}]\n"
        "[/KEY]\n\n"
        "The [KEY] block must be a valid JSON array of exactly 5 objects."
    )


def parse_mock_iq_payload(raw_text: str) -> tuple[list, list]:
    """
    Returns:
        questions: list of 5 question strings (with member label)
        keys: list of 5 key dicts
    """
    user_block = extract_tagged_block(raw_text, "USER")
    key_block  = extract_tagged_block(raw_text, "KEY")

    if not user_block:
        raise ValueError("Missing [USER] block in mock_iq payload")
    if not key_block:
        raise ValueError("Missing [KEY] block in mock_iq payload")

    questions = []
    for m in re.finditer(
        r'Q(\d)\s*\(([^)]+)\)\s*:\s*(.+?)(?=\nQ\d|\Z)',
        user_block, re.DOTALL
    ):
        qno_str  = m.group(1)
        member   = m.group(2).strip()
        text     = m.group(3).strip()
        questions.append(f"Q{qno_str} ({member}): {text}")

    if len(questions) != 5:
        raise ValueError(f"Expected 5 mock_iq questions, parsed {len(questions)}")

    try:
        keys = json.loads(key_block)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid mock_iq KEY JSON: {e}")

    if not isinstance(keys, list) or len(keys) != 5:
        n = len(keys) if isinstance(keys, list) else "?"
        raise ValueError(f"Expected 5 mock_iq keys, got {n}")

    required = ["qno", "member", "key_points", "ideal_structure", "trap"]
    for i, k in enumerate(keys):
        missing = [f for f in required if f not in k]
        if missing:
            raise ValueError(f"Mock IQ key {i+1} missing fields: {missing}")
        k["qno"] = int(k["qno"])

    return questions, keys


async def generate_mock_iq_questions(mem: str) -> tuple[list, list, int, int]:
    prompt = build_mock_iq_prompt()
    raw_resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)
    questions, keys = parse_mock_iq_payload(raw_resp)
    return questions, keys, tok, lat


def build_interview_eval_prompt(question: str, member: str, user_answer: str, key: dict) -> str:
    key_points = "\n".join(f"  - {p}" for p in key.get("key_points", []))
    ideal = key.get("ideal_structure", "")
    trap  = key.get("trap", "")
    return (
        f"UPSC INTERVIEW BOARD — {member} evaluates candidate answer.\n\n"
        f"QUESTION:\n{question}\n\n"
        f"CANDIDATE'S ANSWER:\n{user_answer}\n\n"
        "EVALUATION RUBRIC (hidden from candidate):\n"
        f"Key points required:\n{key_points}\n"
        f"Ideal structure: {ideal}\n"
        f"Common trap: {trap}\n\n"
        "Evaluate strictly (board standard). Output:\n"
        "SCORE: X/10\n"
        "VERDICT: 2-3 lines honest assessment\n"
        "MISSING: Critical gaps (max 3 bullets)\n"
        "IDEAL: How a top candidate would answer this (3-4 lines)"
    )


# ================================================================
# RECALL HELPERS (V1.8 — Stateful 2-Phase Active Recall)
# ================================================================

def build_recall_question_prompt(topic: str) -> str:
    """Phase 1: Ask the student to do a brain dump. Returns [USER]+[KEY] tagged output."""
    return (
        f"ACTIVE RECALL SESSION — Topic: {topic}\n\n"
        "You are Hermes. Do NOT teach. Your job is to test.\n\n"
        "Generate a structured recall challenge.\n\n"
        "FORMAT YOUR RESPONSE AS EXACTLY TWO TAGGED BLOCKS:\n\n"
        "[USER]\n"
        f"Write everything you know about **{topic}** in 3-4 sentences.\n"
        "No notes. No looking up. Pure memory.\n"
        "[/USER]\n\n"
        "[KEY]\n"
        "{\n"
        f'  "topic": "{topic}",\n'
        '  "expected_points": ["point 1", "point 2", "point 3", "point 4", "point 5"],\n'
        '  "trap_points": ["common wrong belief 1", "common wrong belief 2"],\n'
        '  "follow_up_gap": "the single most important gap to probe in phase 2"\n'
        "}\n"
        "[/KEY]\n\n"
        "The KEY must be valid JSON. expected_points = 5 most important facts a UPSC topper must know."
    )


def parse_recall_payload(raw_text: str) -> tuple[str, dict]:
    """Split [USER] shown text from [KEY] rubric dict."""
    user_block = extract_tagged_block(raw_text, "USER") or raw_text
    key_block  = extract_tagged_block(raw_text, "KEY")  or "{}"
    try:
        key = json.loads(key_block)
    except json.JSONDecodeError:
        key = {"topic": "", "expected_points": [], "trap_points": [], "follow_up_gap": ""}
    return user_block.strip(), key


async def generate_recall_question(topic: str, mem: str) -> tuple[str, dict, int, int]:
    """Call Groq, return (public_question, key_dict, tokens, latency_ms)."""
    prompt = build_recall_question_prompt(topic)
    raw, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)
    public_q, key = parse_recall_payload(raw)
    return public_q, key, tok, lat


def build_recall_eval_prompt(topic: str, expected_points: list, trap_points: list,
                              follow_up_gap: str, user_dump: str) -> str:
    """Phase 2 eval prompt: grade the brain dump and ask a targeted follow-up."""
    pts = "\n".join(f"  - {p}" for p in expected_points)
    traps = "\n".join(f"  - {t}" for t in trap_points) if trap_points else "  (none)"
    return (
        f"RECALL EVALUATION — Topic: {topic}\n\n"
        f"EXPECTED POINTS:\n{pts}\n\n"
        f"COMMON TRAPS:\n{traps}\n\n"
        f"STUDENT DUMP:\n{user_dump}\n\n"
        "YOUR TASK:\n"
        "1. WHAT YOU GOT RIGHT — list specific hits (be generous but accurate)\n"
        "2. WHAT YOU MISSED — list what was absent from their dump\n"
        "3. CONFIDENCE vs ACCURACY — did they seem confident but miss key things?\n"
        f"4. SCORE: X/10 (strict — 10/10 only if all expected points covered)\n"
        f"5. FOLLOW-UP QUESTION targeting this gap: {follow_up_gap}\n\n"
        "Be direct. No padding. The follow-up question must end with a '?'."
    )


# ================================================================
# PROGRESS HELPERS (V1.8 — Stateful Bloom's Taxonomy Levels 1-5)
# ================================================================

_BLOOM_LEVEL_NAMES = {
    1: "RECALL",
    2: "UNDERSTAND",
    3: "APPLY",
    4: "ANALYSE",
    5: "EVALUATE",
}

_BLOOM_LEVEL_DESCS = {
    1: "List 3-4 key facts.",
    2: "Explain WHY this matters for India/UPSC.",
    3: "Give a real example where this principle worked or failed.",
    4: "Compare with a closely related concept.",
    5: "Critically examine from 3 different perspectives (policy / society / economy).",
}


def build_progress_question_prompt(topic: str, level: int) -> str:
    """Build a Bloom's level question with [USER]+[KEY] blocks."""
    lvl_name = _BLOOM_LEVEL_NAMES[level]
    lvl_desc = _BLOOM_LEVEL_DESCS[level]
    return (
        f"PROGRESSIVE RECALL — Topic: {topic} | Bloom's Level {level}: {lvl_name}\n\n"
        "You are Hermes. Generate ONE question at the specified Bloom's level.\n\n"
        "FORMAT AS EXACTLY TWO TAGGED BLOCKS:\n\n"
        "[USER]\n"
        f"📊 LEVEL {level}/5 — {lvl_name}\n\n"
        f"**{topic}** — {lvl_desc}\n\n"
        "(Answer in 3-5 sentences. /cancel to exit.)\n"
        "[/USER]\n\n"
        "[KEY]\n"
        "{\n"
        f'  "topic": "{topic}",\n'
        f'  "level": {level},\n'
        '  "key_points": ["point 1", "point 2", "point 3"],\n'
        '  "pass_threshold": 6,\n'
        '  "examiner_note": "what distinguishes a pass from a fail at this level"\n'
        "}\n"
        "[/KEY]\n\n"
        "key_points = 3 specific facts/ideas the student MUST cover to pass this level."
    )


def parse_progress_payload(raw_text: str) -> tuple[str, dict]:
    """Split [USER] shown question from [KEY] rubric dict."""
    user_block = extract_tagged_block(raw_text, "USER") or raw_text
    key_block  = extract_tagged_block(raw_text, "KEY")  or "{}"
    try:
        key = json.loads(key_block)
    except json.JSONDecodeError:
        key = {"topic": "", "level": 1, "key_points": [], "pass_threshold": 6, "examiner_note": ""}
    return user_block.strip(), key


async def generate_progress_question(topic: str, level: int, mem: str) -> tuple[str, dict, int, int]:
    """Call Groq, return (public_question, key_dict, tokens, latency_ms)."""
    prompt = build_progress_question_prompt(topic, level)
    raw, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)
    public_q, key = parse_progress_payload(raw)
    return public_q, key, tok, lat


def build_progress_eval_prompt(topic: str, level: int, question: str,
                                user_answer: str, key: dict) -> str:
    """Evaluate a Bloom's level answer. Decides pass/fail."""
    pts = "\n".join(f"  - {p}" for p in key.get("key_points", []))
    threshold = key.get("pass_threshold", 6)
    examiner_note = key.get("examiner_note", "")
    lvl_name = _BLOOM_LEVEL_NAMES.get(level, f"Level {level}")
    return (
        f"PROGRESSIVE RECALL EVALUATION\n"
        f"Topic: {topic} | Level {level}: {lvl_name}\n\n"
        f"QUESTION:\n{question}\n\n"
        f"KEY POINTS REQUIRED:\n{pts}\n\n"
        f"EXAMINER NOTE: {examiner_note}\n"
        f"PASS THRESHOLD: {threshold}/10\n\n"
        f"STUDENT ANSWER:\n{user_answer}\n\n"
        "YOUR TASK:\n"
        "1. HITS — which key points did they cover? (specific)\n"
        "2. MISSES — which key points did they skip?\n"
        f"3. SCORE: X/10 (strict — use {threshold}/10 as the pass line)\n"
        "4. VERDICT — exactly one of: PASS (advance to next level) or RETRY (repeat this level)\n"
        "5. ONE LINE of feedback (brutal honesty — no softening)\n\n"
        "Format: end with SCORE: X/10 and VERDICT: PASS or VERDICT: RETRY on separate lines."
    )


# ================================================================
# SECTION 1 — CORE COMMANDS
# ================================================================

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    await update.message.reply_text(
        "🧠 HERMES — AIR-1 UPSC Mentor\n"
        f"{DIVIDER_WIDE}\n"
        "22 years. Produced AIR 1, 2, 5, 11.\n"
        "Groq-powered. Free. Always on.\n\n"
        "CORE STUDY:\n"
        "  /teach /log /eod /daily /dump /stats /weak\n\n"
        "PRELIMS:\n"
        "  /quiz /trap /drill /pyq /csat /pattern /examiner\n\n"
        "MAINS:\n"
        "  /evaluate /model /essay /framework /structure\n\n"
        "ACTIVE LEARNING:\n"
        "  /socratic /feynman /why /visual /recall /simplify /progress\n\n"
        "TELUGU OPTIONAL (500 marks):\n"
        "  /telugu /tel_kavya /tel_prosody /tel_grammar\n"
        "  /tel_modern /tel_eval /tel_pyq\n\n"
        "BOOKS & SOURCES:\n"
        "  /ncert /book /source\n\n"
        "MOBILE PRACTICE:\n"
        "  /practice /podcast /insights /phone /files /raw /snapshot\n\n"
        "INTERVIEW:\n"
        "  /daf /mock_iq\n\n"
        "SYSTEM:\n"
        "  /sync /compare /feedback /backup /cancel /help\n\n"
        "Or just TYPE anything — Hermes responds directly.\n"
        f"{DIVIDER_WIDE}\n"
        "Start: /daily for today's CA or /teach <concept>"
    )

cmd_help = cmd_start


async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update):
        return
    clear_session(ctx)
    await update.message.reply_text("✅ Active session cleared. What next?")


async def cmd_teach(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    concept = " ".join(ctx.args) if ctx.args else ""
    if not concept:
        await update.message.reply_text("Usage: /teach <concept>"); return
    await thinking(update, f"📖 Teaching: {concept}...")
    prompt = (
        f"TEACH ME: {concept}\n\n"
        "Use your full neuroscience framework:\n"
        "1. HOOK — connect to my tech/data/Canada background\n"
        "2. CORE FRAMEWORK — diagram or hierarchy first, then detail\n"
        "3. CONSTITUTIONAL/STATUTORY BASIS — articles, acts, bodies\n"
        "4. UPSC ANGLES:\n"
        "   Prelims: key facts + common trap on this topic\n"
        "   Mains: GS paper, likely question framing, ideal structure\n"
        "5. STANDARD BOOK REFERENCE — which chapter of which book covers this best\n"
        "6. MEMORY ANCHOR — one mnemonic or vivid image\n"
        "End with: → Quick check: [one question]"
    )
    mem = get_memory_context()
    resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)
    log_hermes("/teach", concept, resp, tok, lat)
    log_concept(concept)
    await send_long(update, resp)


async def cmd_log(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    text = " ".join(ctx.args) if ctx.args else ""
    if not text:
        await update.message.reply_text("Usage: /log <what you studied/learned>"); return
    today_str = date.today().isoformat()
    if VAULT_PATH.exists():
        fp = VAULT_PATH / "00_Dashboard" / f"Daily_Log_{today_str}.md"
        fp.parent.mkdir(parents=True, exist_ok=True)
        now_t = datetime.now().strftime("%H:%M")
        with open(fp, "a", encoding="utf-8") as f:
            f.write(f"\n## {now_t}\n{text}\n")
    _db_exec("INSERT INTO daily_logs(date,content,file_path) VALUES(?,?,?)",
             (today_str, text, ""))
    log_hermes("/log", text, "logged")
    await update.message.reply_text(f"✅ Logged. Keep going.")


async def cmd_eod(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update):
        return

    await thinking(update, "🌅 Hermes EOD review...")
    weekly_hours = get_weekly_hours()

    prompt = (
        "END OF DAY REVIEW — be honest, not gentle.\n\n"
        "1. WHAT WORKED TODAY — specific, not vague\n"
        "2. WHAT DIDN'T — name it directly\n"
        "3. RETENTION CHECK — pick the most important concept from today's log and ask one question now\n"
        "4. TOMORROW'S PRIORITY — one subject, one topic, reason\n"
        "5. PACE CHECK — am I on track for 1,820 hours by May 2027?\n"
        f"   Estimate: {weekly_hours} this week. Is this enough?\n"
        "6. INTENSITY VERDICT: Light / On-Track / Heavy"
    )
    mem = get_memory_context()
    resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)
    log_hermes("/eod", "eod", resp, tok, lat)
    await send_long(update, resp)


async def cmd_daily(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    await thinking(update, "📰 Fetching CA...")
    ca = get_todays_ca()
    if ca:
        prompt = (
            f"Today is {date.today().isoformat()}. Here is today's CA:\n\n{ca[:5000]}\n\n"
            "As Hermes, give me a study briefing. For EACH story:\n"
            "1. HEADLINE + 2-line factual summary\n"
            "2. GS PAPER + section (e.g. GS2 > Governance > RTI)\n"
            "3. PRELIMS TRAP — exactly what UPSC might ask + what trips candidates\n"
            "4. MAINS ANGLE — frame a 10-mark or 15-mark question from this\n"
            "5. LINKAGE — connect to any other topic in syllabus\n\n"
            "End with: TOP STORY TO MASTER TODAY and why."
        )
    else:
        prompt = (
            f"Today is {date.today().isoformat()}. No CA file found.\n"
            "From your knowledge, give me the 3 most UPSC-critical current developments "
            "in India this week across: Economy, Governance, Environment, IR.\n"
            "For each: 2-line summary, GS paper, Prelims trap, Mains angle."
        )
    mem = get_memory_context()
    resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)
    log_hermes("/daily", "daily-ca", resp, tok, lat)
    await send_long(update, resp)


async def cmd_dump(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    text = " ".join(ctx.args) if ctx.args else ""
    if len(text) < 50:
        await update.message.reply_text("Usage: /dump <paste article text>"); return
    await thinking(update, "🔍 Structuring for UPSC...")
    prompt = (
        f"STRUCTURE THIS FOR UPSC:\n\n{text[:6000]}\n\n"
        "1. KEY FACTS (bullet — what UPSC would actually test)\n"
        "2. GS PAPER MAP (which papers, which sections, why)\n"
        "3. MAINS ANGLES (2-3 specific question framings)\n"
        "4. PRELIMS TRAPS (what's dangerous here)\n"
        "5. LINKAGES (connect to 2-3 other syllabus topics)\n"
        "6. STANDARD BOOK CONTEXT (does any standard book cover this?)"
    )
    mem = get_memory_context()
    resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)
    log_hermes("/dump", text[:200], resp, tok, lat)
    await send_long(update, resp)


async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    total   = (_db_fetchone("SELECT COUNT(*) FROM interactions") or (0,))[0]
    today_n = (_db_fetchone("SELECT COUNT(*) FROM interactions WHERE date(timestamp)=date('now')") or (0,))[0]
    qt, qa  = _db_fetchone("SELECT COUNT(*),COALESCE(AVG(CASE WHEN was_correct=1 THEN 100.0 ELSE 0.0 END),0) FROM quiz_history") or (0, 0)
    wk      = (_db_fetchone("SELECT COUNT(*) FROM weak_topics") or (0,))[0]
    ct      = (_db_fetchone("SELECT COUNT(*) FROM concepts_taught") or (0,))[0]
    ld      = (_db_fetchone("SELECT COUNT(DISTINCT date) FROM daily_logs") or (0,))[0]
    traps   = (_db_fetchone("SELECT COUNT(*) FROM prelims_traps") or (0,))[0]
    flaws   = (_db_fetchone("SELECT COUNT(*) FROM mains_flaws") or (0,))[0]
    active  = (_db_fetchone("SELECT COUNT(DISTINCT date(timestamp)) FROM interactions WHERE timestamp>=date('now','-30 days')") or (0,))[0]
    h_tok   = (_db_fetchone("SELECT COALESCE(SUM(tokens_used),0) FROM hermes_interactions WHERE timestamp>=date('now','-7 days')") or (0,))[0]
    h_lat   = (_db_fetchone("SELECT COALESCE(AVG(latency_ms),0) FROM hermes_interactions WHERE latency_ms>0") or (0,))[0]
    await update.message.reply_text(
        f"📊 HERMES Stats\n{DIVIDER}\n"
        f"Interactions: {total} total | {today_n} today\n"
        f"Concepts taught: {ct} | Quizzes: {qt} | Accuracy: {qa:.0f}%\n"
        f"Weak topics: {wk} | Traps logged: {traps} | Mains flaws: {flaws}\n"
        f"Days logged: {ld} | Active 30d: {active}/30\n"
        f"{DIVIDER}\n"
        f"Groq this week: {h_tok:,} tokens | Avg latency: {h_lat:.0f}ms\n"
        f"Est. cost: $0.00 (free tier)"
    )


async def cmd_weak(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    topics = _db_fetch(
        "SELECT subject,topic,miss_count,last_reviewed "
        "FROM weak_topics ORDER BY miss_count DESC LIMIT 10")
    if not topics:
        await update.message.reply_text("No weak topics yet. Use /quiz!"); return
    topic_list = "\n".join(f"  [{s}] {t} — missed {m}x" for s,t,m,_ in topics)
    prompt = (
        f"My weakest topics:\n{topic_list}\n\n"
        "As Hermes:\n"
        "1. Which ONE do I tackle today? (give clear reason)\n"
        "2. Exact 20-minute revision plan for it\n"
        "3. One Prelims Q and one Mains Q from this topic\n"
        "4. Root cause: WHY am I repeatedly missing this?"
    )
    await thinking(update, "⚠️ Hermes analyzing weak topics...")
    mem = get_memory_context()
    resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)
    log_hermes("/weak", "weak-analysis", resp, tok, lat)
    raw = f"⚠️ Weak Topics\n{DIVIDER}\n{topic_list}"
    await send_long(update, raw)
    await send_long(update, f"🧠 Hermes Study Plan:\n\n{resp}")


# ================================================================
# SECTION 2 — PRELIMS
# ================================================================

async def cmd_quiz(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update):
        return

    subject = " ".join(ctx.args) if ctx.args else ""
    await thinking(update, "🎯 Generating Prelims MCQ...")

    mem = get_memory_context()

    try:
        public_text, key, tok, lat = await generate_quiz_with_key(subject or "General Studies", mem)
    except Exception as e:
        log.error(f"/quiz parse failure: {e}")
        await update.message.reply_text("⚠️ Quiz generation failed. Try /quiz again.")
        return

    log_hermes("/quiz", subject or "auto", public_text, tok, lat)

    set_session(ctx, "quiz", {
        "topic": key.get("topic", subject or "General Studies"),
        "concept": key.get("concept", subject or "General"),
        "question_text": public_text,
        "answer_key": key,
        "attempts": 0,
        "started_at": datetime.utcnow().isoformat()
    })

    await update.message.reply_text(public_text, reply_markup=build_answer_keyboard())


async def cmd_trap(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    text = " ".join(ctx.args) if ctx.args else ""
    if not text:
        await update.message.reply_text(
            "Usage: /trap <paste the question you got wrong + which option you chose>"); return
    await thinking(update, "🔬 Options Autopsy...")
    prompt = (
        f"OPTIONS AUTOPSY on this question I got wrong:\n\n{text}\n\n"
        "1. EXACT TRAP — name the specific distractor technique used\n"
        "2. PSYCHOLOGICAL BIAS — why human brain picks the wrong option\n"
        "3. CORRECT REASONING — step-by-step logic to right answer\n"
        "4. THE RULE — one line I must memorise to never miss this type again\n"
        "5. SIMILAR PYQs — name 1-2 past year questions with same trap pattern\n"
        "Under 250 words. Dense, not padded."
    )
    mem = get_memory_context()
    resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)
    _db_exec("INSERT INTO prelims_traps(topic,trap_type,trap_description) VALUES(?,?,?)",
             ("General", "autopsy", str(resp)[:300]))
    log_hermes("/trap", text[:200], resp, tok, lat)
    await send_long(update, resp)
    await update.message.reply_text("🚨 Trap logged to memory.")


async def cmd_drill(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update):
        return

    await thinking(update, "🌪️ Interleaved Drill...")
    mem = get_memory_context()

    try:
        public_text, keys, tok, lat = await generate_drill_with_keys(mem)
    except Exception as e:
        log.error(f"/drill parse failure: {e}")
        await update.message.reply_text("⚠️ Drill generation failed. Try /drill again.")
        return

    log_hermes("/drill", "interleaved", public_text, tok, lat)

    set_session(ctx, "drill", {
        "questions_text": public_text,
        "drill_keys": keys,
        "attempts": 0,
        "started_at": datetime.utcnow().isoformat()
    })

    await update.message.reply_text(public_text, reply_markup=build_answer_keyboard())


async def cmd_pyq(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """PYQ pattern analysis — examiner mindset."""
    if not check_auth(update): return
    topic = " ".join(ctx.args) if ctx.args else ""
    if not topic:
        await update.message.reply_text(
            "Usage: /pyq <topic>\nExample: /pyq federalism\nExample: /pyq environment Prelims"); return
    await thinking(update, f"📜 PYQ Pattern for: {topic}...")
    prompt = (
        f"PYQ ANALYSIS: {topic}\n\n"
        "As a 22-year UPSC expert who has memorised every PYQ:\n"
        "1. FREQUENCY — how many times has this appeared? (Prelims vs Mains)\n"
        "2. YEAR-WISE PATTERN — list actual years and what aspect was tested\n"
        "3. QUESTION EVOLUTION — how has the framing changed over decades?\n"
        "4. EXAMINER'S FAVOURITE ANGLE — what specific aspect do they love to test?\n"
        "5. PREDICTION — based on pattern, what's likely in 2025-2027?\n"
        "6. GAPS — what aspect of this topic has NEVER been asked but should be?\n\n"
        "Be specific. Year + paper + actual question theme where possible."
    )
    mem = get_memory_context()
    resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)
    log_hermes("/pyq", topic, resp, tok, lat)
    log_concept(f"PYQ:{topic}")
    await send_long(update, resp)


async def cmd_csat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """CSAT practice with strategy."""
    if not check_auth(update): return
    topic = " ".join(ctx.args) if ctx.args else "mixed"
    await thinking(update, "📐 CSAT Practice...")
    prompt = (
        f"CSAT PRACTICE — topic: {topic}\n\n"
        "Give me 3 CSAT questions:\n"
        "  1. Reading comprehension (short passage + 2 questions)\n"
        "  2. Logical reasoning / analytical (clear, no ambiguity)\n"
        "  3. Basic numeracy (keep calculation under 60 seconds)\n\n"
        "After each question, include:\n"
        "STRATEGY TIP: how to eliminate wrong options quickly.\n"
        "TIME TARGET: how many seconds to spend on this type.\n\n"
        "Do NOT reveal answers yet."
    )
    mem = get_memory_context()
    resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)
    log_hermes("/csat", topic, resp, tok, lat)
    await send_long(update, resp)


async def cmd_pattern(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Identify question patterns across years for a subject."""
    if not check_auth(update): return
    subject = " ".join(ctx.args) if ctx.args else ""
    if not subject:
        await update.message.reply_text(
            "Usage: /pattern <subject>\nExamples: /pattern Polity  /pattern Economy  /pattern Environment"); return
    await thinking(update, f"🔍 Pattern analysis: {subject}...")
    prompt = (
        f"PRELIMS PATTERN ANALYSIS: {subject}\n\n"
        "Analyse the last 10 years of UPSC Prelims for this subject:\n"
        "1. TOPIC DISTRIBUTION — which subtopics get maximum questions?\n"
        "2. YEARLY TREND — is frequency increasing, decreasing, stable?\n"
        "3. QUESTION TYPES — factual vs conceptual vs application ratio?\n"
        "4. DISTRACTOR PATTERNS — what traps does UPSC repeatedly use here?\n"
        "5. HIGH-YIELD ZONES — top 5 subtopics to master for max ROI\n"
        "6. NEGLECTED ZONES — subtopics in syllabus that rarely appear\n"
        "7. 2027 PREDICTION — what should I focus on given current trends?\n\n"
        "Give actual numbers and years where possible."
    )
    mem = get_memory_context()
    resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)
    log_hermes("/pattern", subject, resp, tok, lat)
    await send_long(update, resp)


async def cmd_examiner(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Think like the examiner — deconstruct any question."""
    if not check_auth(update): return
    question = " ".join(ctx.args) if ctx.args else ""
    if not question:
        await update.message.reply_text(
            "Usage: /examiner <paste any UPSC question>\n"
            "Hermes deconstructs it from the examiner's perspective."); return
    await thinking(update, "🧐 Examiner mindset...")
    prompt = (
        f"EXAMINER DECONSTRUCTION:\n\n\"{question}\"\n\n"
        "Step into the mind of the UPSC examiner who designed this question:\n"
        "1. WHY THIS QUESTION — what gap in understanding is being tested?\n"
        "2. INTENDED WRONG ANSWER — which option is the trap and why?\n"
        "3. DISCRIMINATOR — what separates top 1% from top 10% here?\n"
        "4. CORRECT ANSWER + REASONING — full logical path\n"
        "5. STANDARD BOOK SOURCE — where exactly is this answer?\n"
        "6. SIMILAR QUESTIONS TO PRACTISE — 2 questions with same design"
    )
    mem = get_memory_context()
    resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)
    log_hermes("/examiner", question[:200], resp, tok, lat)
    await send_long(update, resp)


# ================================================================
# SECTION 3 — MAINS
# ================================================================

async def cmd_evaluate(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    text = " ".join(ctx.args) if ctx.args else ""
    if len(text) < 50:
        await update.message.reply_text("Usage: /evaluate <paste your Mains answer>"); return
    await thinking(update, "📝 Hermes grading...")
    prompt = (
        f"EVALUATE THIS MAINS ANSWER — be a strict UPSC examiner:\n\n{text[:5000]}\n\n"
        "1. SCORE X/10 — be honest. Average is 5.5. Good is 7+. Excellent is 8.5+.\n"
        "2. STRUCTURE AUDIT — intro/body/conclusion: tight or loose?\n"
        "3. CONTENT GAPS — missing: articles? judgments? schemes? data? examples?\n"
        "4. GS LINKAGES — what other GS areas could have been woven in?\n"
        "5. TOP 3 FLAWS — state them bluntly. Check if I'm repeating known flaws.\n"
        "6. TOPPER DIFFERENCE — what would an AIR-5 answer have that mine doesn't?\n"
        "7. MODEL INTRO — rewrite my introduction in 3 sentences the way a topper would.\n\n"
        "Do not soften. A 6/10 with sharp feedback is worth more than 8/10 with vague praise."
    )
    mem = get_memory_context()
    resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)
    score = extract_score(resp)
    topic = (" ".join(text.split()[:4]))
    if score:
        _db_exec(
            "INSERT INTO evaluation_history(topic,answer_snippet,score) VALUES(?,?,?)",
            (topic, text[:100], score))
        if score < 6.0:
            log_weakness("Mains", topic, "evaluate")
    log_hermes("/evaluate", text[:200], resp, tok, lat)
    await send_long(update, resp)


async def cmd_model(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    Dual-purpose command:
      /model groq               — switch to Groq/Llama 3.3 70B (default, free)
      /model databricks-sonnet  — switch to Claude Sonnet 4.6 via Databricks (costs DBUs)
      /model databricks-opus    — switch to Claude Opus 4.6 via Databricks (costs more DBUs)
      /model                    — show current model
      /model <topic>            — build a mental model for a UPSC topic (original behaviour)
    """
    global ACTIVE_MODEL
    if not check_auth(update): return
    arg = " ".join(ctx.args).strip() if ctx.args else ""

    # ── Live model switching ──────────────────────────────────────
    _switch_map = {
        "groq": "groq",
        "databricks-sonnet": "databricks-sonnet",
        "databricks-opus": "databricks-opus",
    }
    if not arg:
        model_label = {
            "groq": f"Groq / {GROQ_MODEL} (free)",
            "databricks-sonnet": f"Databricks / {DBX_MODEL_SONNET} (DBU cost)",
            "databricks-opus":   f"Databricks / {DBX_MODEL_OPUS} (DBU cost)",
        }.get(ACTIVE_MODEL, ACTIVE_MODEL)
        await update.message.reply_text(
            f"🤖 Current model: {model_label}\n\n"
            "Switch with:\n"
            "  /model groq                — Llama 3.3 70B (free)\n"
            "  /model databricks-sonnet   — Claude Sonnet 4.6 (DBU)\n"
            "  /model databricks-opus     — Claude Opus 4.6 (DBU)\n\n"
            "Or build a mental model: /model <UPSC topic>"
        )
        return

    if arg.lower() in _switch_map:
        new_model = _switch_map[arg.lower()]
        ACTIVE_MODEL = new_model
        dbx_warn = ""
        if new_model.startswith("databricks") and (not DATABRICKS_HOST or not DATABRICKS_TOKEN):
            dbx_warn = "\n\n⚠️ Warning: DATABRICKS_HOST or DATABRICKS_TOKEN not set — calls will fail."
        label = {
            "groq": f"Groq / {GROQ_MODEL}",
            "databricks-sonnet": f"Databricks / {DBX_MODEL_SONNET}",
            "databricks-opus":   f"Databricks / {DBX_MODEL_OPUS}",
        }[new_model]
        log.info(f"Model switched to {new_model} by user")
        await update.message.reply_text(f"✅ Model switched to: {label}{dbx_warn}")
        return

    # ── Mental model builder (original behaviour) ─────────────────
    topic = arg
    await thinking(update, f"🔨 Building mental model: {topic}...")
    prompt = (
        f"MENTAL MODEL: {topic}\n\n"
        "1. CORE PRINCIPLE — one sentence that explains everything\n"
        "2. MECHANISM — how it actually works (5 steps max, use flowchart if helpful)\n"
        "3. CONSTITUTIONAL/LEGAL BASIS — articles, acts, rules\n"
        "4. EXCEPTIONS AND EDGE CASES — where the model breaks\n"
        "5. EXAMPLES:\n"
        "   Historical (pre-2000): 1 case\n"
        "   Recent (post-2015): 1 case\n"
        "   Comparative (another country): 1 case\n"
        "6. GS MAP — Prelims + Mains + Essay angle\n"
        "7. 90-SECOND ANSWER SKELETON — if this appears in Mains, what's my structure?"
    )
    mem = get_memory_context()
    resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)
    log_hermes("/model", topic, resp, tok, lat)
    log_concept(topic)
    await send_long(update, resp)


async def cmd_essay(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Essay writing — the most neglected part of UPSC."""
    if not check_auth(update): return
    topic = " ".join(ctx.args) if ctx.args else ""
    if not topic:
        await update.message.reply_text(
            "Usage: /essay <topic>\n"
            "Example: /essay 'Technology is the new religion'\n"
            "Example: /essay evaluate <paste your essay draft>"); return

    # If user pastes a draft (long text), evaluate it
    if len(topic) > 200:
        await thinking(update, "📜 Evaluating essay draft...")
        prompt = (
            f"EVALUATE THIS UPSC ESSAY:\n\n{topic[:8000]}\n\n"
            "1. THEME COHERENCE — is there one clear thread? Score /10\n"
            "2. INTRODUCTION — does it set the philosophical context? Score /10\n"
            "3. STRUCTURE — logical flow, transitions, balance? Score /10\n"
            "4. CONTENT DEPTH — examples, data, multidimensional? Score /10\n"
            "5. CONCLUSION — does it land powerfully? Score /10\n"
            "6. OVERALL /10\n"
            "7. THE ONE THING that would most improve this essay\n"
            "8. REWRITE the introduction paragraph the way a topper would."
        )
    else:
        await thinking(update, f"📜 Essay framework: {topic}...")
        prompt = (
            f"ESSAY FRAMEWORK: '{topic}'\n\n"
            "As a 22-year UPSC essay specialist:\n"
            "1. THEME IDENTIFICATION — what is this essay REALLY about? (1 sentence)\n"
            "2. PHILOSOPHICAL HOOK — what quote or idea opens powerfully?\n"
            "3. STRUCTURE (1800 words target):\n"
            "   INTRO (200w): hook → context → thesis\n"
            "   BODY 1 (400w): [aspect 1 + example + analysis]\n"
            "   BODY 2 (400w): [aspect 2 + example + analysis]\n"
            "   BODY 3 (400w): [counterargument + rebuttal]\n"
            "   BODY 4 (200w): [way forward / solution]\n"
            "   CONCLUSION (200w): [synthesis + vision]\n"
            "4. TOP 5 EXAMPLES to use — specific, dateable, diverse\n"
            "5. VOCABULARY — 5 power phrases for this theme\n"
            "6. TRAPS — what do mediocre candidates write that examiners hate?\n"
            "7. AIR-1 DIFFERENTIATOR — what makes the topper essay on this topic unforgettable?"
        )
    mem = get_memory_context()
    resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)
    log_hermes("/essay", topic[:200], resp, tok, lat)
    await send_long(update, resp)


async def cmd_framework(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Quick answer frameworks for common Mains question types."""
    if not check_auth(update): return
    qtype = " ".join(ctx.args) if ctx.args else ""
    if not qtype:
        await update.message.reply_text(
            "Usage: /framework <question type or topic>\n"
            "Examples:\n"
            "  /framework critically examine\n"
            "  /framework discuss implications\n"
            "  /framework governance reforms\n"
            "  /framework environment vs development"); return
    await thinking(update, f"⚙️ Framework for: {qtype}...")
    prompt = (
        f"MAINS ANSWER FRAMEWORK: '{qtype}'\n\n"
        "1. QUESTION TYPE DECODE — what exactly is this asking?\n"
        "2. INSTANT STRUCTURE — 5-point skeleton I can use in 2 minutes\n"
        "3. OPENING LINE FORMULA — how to start without wasting 30 seconds\n"
        "4. MANDATORY ELEMENTS — what an examiner ALWAYS expects here\n"
        "5. COMMON MISTAKES — what average candidates write\n"
        "6. SAMPLE ANSWER SKELETON — fill in the blanks style, 150 words\n"
        "7. TIME ALLOCATION — how to split 7-8 minutes across sections"
    )
    mem = get_memory_context()
    resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)
    log_hermes("/framework", qtype, resp, tok, lat)
    await send_long(update, resp)


async def cmd_structure(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Paste a question, get a full answer structure back."""
    if not check_auth(update): return
    question = " ".join(ctx.args) if ctx.args else ""
    if not question:
        await update.message.reply_text(
            "Usage: /structure <paste any Mains question>\n"
            "Hermes gives you a ready-to-write answer structure."); return
    await thinking(update, "📋 Structuring answer...")
    prompt = (
        f"ANSWER STRUCTURE for:\n\"{question}\"\n\n"
        "Give me a ready-to-write answer plan:\n"
        "1. WORD LIMIT STRATEGY — 150 or 250 words? How to split?\n"
        "2. INTRODUCTION (2-3 lines) — exact approach\n"
        "3. BODY POINTS (numbered) — exactly what each paragraph covers\n"
        "4. MUST-INCLUDE — specific articles / data / schemes / judgments\n"
        "5. CONCLUSION (2 lines) — way forward or balanced statement\n"
        "6. DIAGRAM/TABLE? — would a flowchart or table add marks here?\n"
        "7. TIME: X minutes — how to use them\n\n"
        "Be specific. No vague advice."
    )
    mem = get_memory_context()
    resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)
    log_hermes("/structure", question[:200], resp, tok, lat)
    await send_long(update, resp)


# ================================================================
# SECTION 4 — ACTIVE LEARNING
# ================================================================

async def cmd_socratic(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update):
        return

    topic = " ".join(ctx.args) if ctx.args else ""
    if not topic:
        await update.message.reply_text("Usage: /socratic <topic>")
        return

    await thinking(update, f"🤔 Socratic session: {topic}...")

    prompt = (
        f"SOCRATIC SESSION: {topic}\n\n"
        "Ask EXACTLY ONE foundational question.\n"
        "Do NOT explain the topic.\n"
        "Do NOT ask multiple questions.\n"
        "The question must test first-principles understanding.\n"
        "End only with the question."
    )

    _db_exec("INSERT INTO socratic_sessions(topic) VALUES(?)", (topic,))
    mem = get_memory_context()
    resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)

    log_hermes("/socratic", topic, resp, tok, lat)

    set_session(ctx, "socratic", {
        "topic": topic,
        "last_prompt": resp,
        "depth": 1,
        "started_at": datetime.utcnow().isoformat()
    })

    await send_long(update, resp)


async def cmd_feynman(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    text = " ".join(ctx.args) if ctx.args else ""
    if ":" not in text:
        await update.message.reply_text("Usage: /feynman <topic>: <your explanation>"); return
    topic, explanation = text.split(":", 1)
    await thinking(update, f"🔬 Feynman audit: {topic.strip()}...")
    prompt = (
        f"FEYNMAN AUDIT\n"
        f"Topic: {topic.strip()}\n"
        f"My explanation: {explanation.strip()}\n\n"
        "1. ACCURACY — what's correct in my explanation?\n"
        "2. ERRORS — what's wrong or misleading? Be specific.\n"
        "3. GAPS — what important aspect did I miss entirely?\n"
        "4. DEPTH — is this exam-level or surface level?\n"
        "5. SCORE X/10\n"
        "6. THE CORRECT EXPLANATION — rewrite it in 5 sentences the way I should say it in Mains\n"
        "7. MEMORY ANCHOR — one way to never forget this again"
    )
    mem = get_memory_context()
    resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)
    log_hermes("/feynman", text[:200], resp, tok, lat)
    log_concept(topic.strip())
    await send_long(update, resp)


async def cmd_why(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    fact = " ".join(ctx.args) if ctx.args else ""
    if not fact:
        await update.message.reply_text("Usage: /why <state a fact>"); return
    await thinking(update, f"🔥 WHY interrogation...")
    prompt = (
        f"WHY-HOW INTERROGATION\nGad states: \"{fact}\"\n\n"
        "Don't explain. Ask ONE sharp 'Why?' that reveals whether he truly understands.\n"
        "Not a surface why — a foundational why.\n"
        "After he answers:\n"
        "  If correct → go one level deeper with another Why\n"
        "  If wrong → correct precisely, then ask again\n"
        "Keep going until we hit bedrock understanding.\n"
        "Maximum 4 levels deep."
    )
    mem = get_memory_context()
    resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)
    log_hermes("/why", fact, resp, tok, lat)
    await send_long(update, resp)


async def cmd_visual(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    topic = " ".join(ctx.args) if ctx.args else ""
    if not topic:
        await update.message.reply_text("Usage: /visual <topic>"); return
    await thinking(update, f"🎨 Dual-coding: {topic}...")
    prompt = (
        f"DUAL-CODING for: {topic}\n\n"
        "For each key concept:\n"
        "  WORDS: 2-3 sentence precise definition\n"
        "  VISUAL: ASCII diagram, flowchart, or comparison table\n\n"
        "Then:\n"
        "HIERARCHY MAP — show relationships between sub-concepts using indentation\n"
        "TIMELINE (if applicable) — key dates in chronological structure\n"
        "MEMORY TRICK — one vivid image that encodes the whole concept\n"
        "2 EXAM QUESTIONS — one Prelims, one Mains"
    )
    mem = get_memory_context()
    resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)
    log_hermes("/visual", topic, resp, tok, lat)
    log_concept(topic)
    await send_long(update, resp)


async def cmd_recall(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Stateful active recall — Phase 1: brain dump. Phase 2: gap-targeted follow-up."""
    if not check_auth(update): return
    topic = " ".join(ctx.args) if ctx.args else ""
    if not topic:
        await update.message.reply_text("Usage: /recall <topic>"); return
    clear_session(ctx)
    await thinking(update, f"💡 Active Recall: {topic}...")
    mem = get_memory_context()
    question, key, tok, lat = await generate_recall_question(topic, mem)
    log_hermes("/recall", topic, question, tok, lat)
    set_session(ctx, "recall", {
        "topic": topic,
        "question": question,
        "answer_key": key,
        "phase": "dump",            # "dump" → eval+followup → "followup" → final
        "scores": [],
        "started_at": datetime.utcnow().isoformat(),
    })
    await send_long(update, f"💡 ACTIVE RECALL — {topic.upper()}\n{DIVIDER}\n\n{question}")


async def cmd_simplify(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    topic = " ".join(ctx.args) if ctx.args else ""
    if not topic:
        await update.message.reply_text("Usage: /simplify <topic>"); return
    await thinking(update, f"🧒 Simplifying: {topic}...")
    prompt = (
        f"SIMPLIFY: {topic}\n\n"
        "4 layers — each builds on the previous:\n"
        "LAYER 1 — ELI-12: explain as if to a smart 12-year-old. No jargon.\n"
        "LAYER 2 — ELI-GRAD: explain to a well-educated adult. Some technical terms ok.\n"
        "LAYER 3 — ELI-UPSC: explain at Mains answer quality. All technical aspects.\n"
        "LAYER 4 — ELI-TOPPER: add the nuance, exceptions, and linkages that "
        "separate AIR 1-50 from AIR 200-500.\n\n"
        "Keep each layer DISTINCT. Don't just add words — add a new dimension each time."
    )
    mem = get_memory_context()
    resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)
    log_hermes("/simplify", topic, resp, tok, lat)
    log_concept(topic)
    await send_long(update, resp)


async def cmd_progress(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Stateful Bloom's Taxonomy Levels 1-5 — advance on pass, retry on fail."""
    if not check_auth(update): return
    topic = " ".join(ctx.args) if ctx.args else ""
    if not topic:
        await update.message.reply_text("Usage: /progress <topic>"); return
    clear_session(ctx)
    await thinking(update, f"📈 Progressive Recall: {topic}...")
    mem = get_memory_context()
    question, key, tok, lat = await generate_progress_question(topic, 1, mem)
    log_hermes("/progress", topic, question, tok, lat)
    set_session(ctx, "progress", {
        "topic": topic,
        "level": 1,
        "question": question,
        "answer_key": key,
        "level_scores": [],         # one entry per level attempted
        "retries": 0,               # retries on current level
        "started_at": datetime.utcnow().isoformat(),
    })
    await send_long(update, f"📈 PROGRESSIVE RECALL — {topic.upper()}\n{DIVIDER}\n\n{question}")


# ================================================================
# SECTION 5 — TELUGU OPTIONAL (500 marks — treated seriously)
# ================================================================

async def cmd_telugu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Daily Telugu Optional — reads Volume file first, then Hermes analysis."""
    if not check_auth(update): return
    topic = " ".join(ctx.args) if ctx.args else ""
    await thinking(update, "📚 Telugu Optional...")
    today = date.today().isoformat()
    content = fetch_volume_file(f"{VOLUME_BASE}/{today}/06_Telugu_Optional.md")
    if content:
        prompt = (
            f"Today's Telugu Optional content:\n{content[:4000]}\n\n"
            "1. CORE LITERARY CONCEPT — explain in simple Telugu + English\n"
            "2. PAPER MAPPING — Paper VI or VII? Which section?\n"
            "3. EXAM QUESTIONS — 2 likely questions from this passage\n"
            "4. TEXTUAL EVIDENCE — key quotes or references to memorise\n"
            "5. MEMORY HOOK — one vivid way to remember this\n"
            "→ Quick check: [one question on this passage]"
        )
    elif topic:
        prompt = (
            f"TELUGU OPTIONAL: {topic}\n\n"
            "Paper VI/VII — treat with full GS rigor:\n"
            "1. LITERARY/LINGUISTIC CONCEPT — precise definition with Sanskrit roots\n"
            "2. HISTORICAL CONTEXT — period, tradition, major works\n"
            "3. KEY AUTHORS & TEXTS — who, when, what contribution\n"
            "4. PAPER SECTION MAPPING — exact syllabus location\n"
            "5. PYQ PATTERN — has this been asked before? When?\n"
            "6. MODEL ANSWER SKELETON — how to structure if this appears\n"
            "7. MEMORY TECHNIQUE — mnemonic or story\n"
            "→ Quick check: [one question]"
        )
    else:
        prompt = (
            f"Today is {today}. Give me today's Telugu Optional focus.\n\n"
            "Pick the highest-yield topic from my weak list or syllabus gaps.\n"
            "Give a focused 15-minute revision capsule:\n"
            "  Topic name + Paper/Section\n"
            "  Core concept (5 lines)\n"
            "  3 key points to memorise\n"
            "  1 likely exam question\n"
            "  1 memory hook"
        )
    mem = get_memory_context()
    resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)
    log_hermes("/telugu", topic or today, resp, tok, lat)
    log_concept(f"Telugu:{topic or 'daily'}")
    await send_long(update, resp)


async def cmd_tel_kavya(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Kavitrayam — Nannaya, Tikkana, Errana deep dive."""
    if not check_auth(update): return
    focus = " ".join(ctx.args) if ctx.args else ""
    await thinking(update, "📖 Kavitrayam...")
    prompt = (
        f"KAVITRAYAM DEEP DIVE{' — ' + focus if focus else ''}\n\n"
        "The three pillars of Telugu literature: Nannaya, Tikkana, Errana.\n\n"
        "Cover:\n"
        "1. NANNAYA — Adi Kavi, Andhra Mahabharatamu, his unique contributions, "
        "Gramya vs. Sahitya debate, chandas used\n"
        "2. TIKKANA — Style contrast with Nannaya, Nirvachana Uttara Ramayanamu, "
        "Sabha Parva contribution, philosophical depth\n"
        "3. ERRANA — Completion of Mahabharatamu, Ramayanamu, his critical reception\n"
        "4. COMPARATIVE TABLE — style, period, works, unique feature each\n"
        "5. PYQ PATTERN — which aspects are examined most?\n"
        "6. MODEL ANSWER — if asked 'Compare the three poets of Kavitrayam' (400 words)\n"
        f"{'Focus specifically on: ' + focus if focus else ''}\n"
        "→ Quick check: [one question]"
    )
    mem = get_memory_context()
    resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)
    log_hermes("/tel_kavya", focus or "general", resp, tok, lat)
    log_concept("Kavitrayam")
    await send_long(update, resp)


async def cmd_tel_prosody(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Telugu Prosody (Chandas) — Vrittalu, Padyalu, metres."""
    if not check_auth(update): return
    topic = " ".join(ctx.args) if ctx.args else ""
    await thinking(update, "🎵 Telugu Prosody...")
    prompt = (
        f"TELUGU PROSODY (CHANDAS){' — ' + topic if topic else ''}\n\n"
        "1. METRE SYSTEM — Aksara Gana, Matra Gana, Laghu-Guru basics\n"
        "2. MAJOR METRES — Uttara Ramachandra Vrittam, Champakamala, Sisa Vrittam: "
        "structure + example line from actual text\n"
        "3. PADYA TYPES — Shatpadi, Sangatya, Dwipada: definition + example\n"
        "4. SANGAM INFLUENCE vs SANSKRIT INFLUENCE — how Telugu prosody evolved\n"
        "5. EXAM ANGLE — typically Paper VI or VII? What exact questions appear?\n"
        "6. IDENTIFICATION EXERCISE — give me one padya and ask me to identify the metre\n"
        "→ Quick check: [identification question]"
    )
    mem = get_memory_context()
    resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)
    log_hermes("/tel_prosody", topic or "general", resp, tok, lat)
    log_concept("Telugu Prosody")
    await send_long(update, resp)


async def cmd_tel_grammar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Telugu Grammar (Vyakarana) — Bala Vyakaranamu etc."""
    if not check_auth(update): return
    topic = " ".join(ctx.args) if ctx.args else ""
    await thinking(update, "📝 Telugu Grammar...")
    prompt = (
        f"TELUGU GRAMMAR (VYAKARANA){' — ' + topic if topic else ''}\n\n"
        "1. MAJOR GRAMMARS — Nannaya's grammar, Bala Vyakaranamu, Andhra Shabda Chintamani: "
        "author, period, contribution\n"
        "2. SANDHI RULES — with Telugu examples (not just theory)\n"
        "3. SAMASA TYPES — Dwandwa, Tatpurusha, Bahuvrihi in Telugu with examples\n"
        "4. VIBHAKTI SYSTEM — case endings, comparison with Sanskrit\n"
        "5. DIALECT vs STANDARD — Gramya bhasha vs Grandhika bhasha debate\n"
        "6. EXAM QUESTIONS — typical grammar questions in Paper VII\n"
        "7. PRACTICE — give me one sandhi/samasa to identify\n"
        "→ Quick check: [grammar identification]"
    )
    mem = get_memory_context()
    resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)
    log_hermes("/tel_grammar", topic or "general", resp, tok, lat)
    log_concept("Telugu Grammar")
    await send_long(update, resp)


async def cmd_tel_modern(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Modern Telugu Literature + Western Critical Theory."""
    if not check_auth(update): return
    topic = " ".join(ctx.args) if ctx.args else ""
    await thinking(update, "🖊️ Modern Telugu + Critical Theory...")
    prompt = (
        f"MODERN TELUGU LITERATURE & WESTERN CRITICAL APPROACHES"
        f"{' — ' + topic if topic else ''}\n\n"
        "PART A — MODERN TELUGU:\n"
        "1. REFORMATION ERA — Kandukuri Veeresalingam, Gurajada Apparao: their revolt against tradition\n"
        "2. VIRASAM / DIGAMBARA KAVITVA — revolutionary poetry movement: key poets, themes\n"
        "3. FEMINIST VOICES — major women writers and their contribution\n"
        "4. SHORT STORY TRADITION — Chalam, Sripada Subrahmanya Sastry: style + themes\n\n"
        "PART B — WESTERN CRITICAL APPROACHES:\n"
        "5. NEW CRITICISM — close reading, intentional fallacy, affective fallacy\n"
        "6. STRUCTURALISM — Saussure's signifier/signified applied to Telugu texts\n"
        "7. POST-COLONIALISM — applying to Telugu literature's British-era transformation\n"
        "8. PAPER MAPPING — which theory is tested more in Paper VII?\n"
        "→ Quick check: [one theory application question]"
    )
    mem = get_memory_context()
    resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)
    log_hermes("/tel_modern", topic or "general", resp, tok, lat)
    log_concept("Modern Telugu Literature")
    await send_long(update, resp)


async def cmd_tel_eval(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Evaluate a Telugu Optional answer."""
    if not check_auth(update): return
    text = " ".join(ctx.args) if ctx.args else ""
    if len(text) < 30:
        await update.message.reply_text(
            "Usage: /tel_eval <paste your Telugu Optional answer>"); return
    await thinking(update, "📊 Evaluating Telugu answer...")
    prompt = (
        f"EVALUATE THIS TELUGU OPTIONAL ANSWER:\n\n{text[:4000]}\n\n"
        "Evaluate as a Telugu literature examiner:\n"
        "1. SCORE X/10\n"
        "2. TEXTUAL ACCURACY — are facts, dates, author names correct?\n"
        "3. CRITICAL DEPTH — does the answer show understanding beyond surface?\n"
        "4. LITERARY TERMINOLOGY — correct use of chandas, alankara, rasa terms?\n"
        "5. COMPARATIVE ANALYSIS — did it compare adequately (if required)?\n"
        "6. LANGUAGE QUALITY — Telugu/English mix appropriate?\n"
        "7. TOPPER DIFFERENCE — what would an AIR-5 Telugu Optional answer include?\n"
        "8. REWRITE the weakest paragraph correctly."
    )
    mem = get_memory_context()
    resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)
    score = extract_score(resp)
    if score:
        _db_exec(
            "INSERT INTO evaluation_history(topic,answer_snippet,score) VALUES(?,?,?)",
            ("Telugu Optional", text[:100], score))
    log_hermes("/tel_eval", text[:200], resp, tok, lat)
    await send_long(update, resp)


async def cmd_tel_pyq(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Telugu Optional PYQ pattern analysis."""
    if not check_auth(update): return
    paper = " ".join(ctx.args) if ctx.args else ""
    await thinking(update, "📜 Telugu Optional PYQ analysis...")
    prompt = (
        f"TELUGU OPTIONAL PYQ ANALYSIS{' — ' + paper if paper else ' (both papers)'}\n\n"
        "As someone who has analysed 20 years of Telugu Optional papers:\n"
        "1. PAPER VI PATTERN — which topics repeat? Frequency?\n"
        "2. PAPER VII PATTERN — grammar vs literature ratio? Trend?\n"
        "3. HIGH-YIELD TOPICS — what 20% of syllabus gives 80% of marks?\n"
        "4. QUESTION DESIGN — essay type vs short answer ratio?\n"
        "5. YEAR-WISE SHIFT — has the paper become easier/harder/more theoretical?\n"
        "6. SAFE BETS FOR 2027 — topics almost certain to appear based on gap analysis\n"
        "7. PREPARATION PRIORITY for Gad — given his background, what to master first?"
    )
    mem = get_memory_context()
    resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)
    log_hermes("/tel_pyq", paper or "both", resp, tok, lat)
    await send_long(update, resp)


# ================================================================
# SECTION 6 — BOOKS & SOURCES
# ================================================================

async def cmd_ncert(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """NCERT-level grounding for any topic."""
    if not check_auth(update): return
    topic = " ".join(ctx.args) if ctx.args else ""
    if not topic:
        await update.message.reply_text(
            "Usage: /ncert <topic>\nExample: /ncert federalism\nExample: /ncert cell biology"); return
    await thinking(update, f"📗 NCERT foundation: {topic}...")
    prompt = (
        f"NCERT FOUNDATION: {topic}\n\n"
        "1. WHICH NCERT — exact book (class + subject + chapter) covering this\n"
        "2. CORE CONCEPT as NCERT explains it — simple, precise\n"
        "3. KEY DIAGRAMS/MAPS from NCERT if applicable\n"
        "4. BEYOND NCERT — what NCERT misses that UPSC actually tests\n"
        "5. NCERT → UPSC BRIDGE — how this NCERT concept connects to actual PYQs\n"
        "6. SUPPLEMENTARY SOURCE — which standard book to read AFTER NCERT for this\n"
        "→ Quick check: [NCERT-level question]"
    )
    mem = get_memory_context()
    resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)
    log_hermes("/ncert", topic, resp, tok, lat)
    log_concept(f"NCERT:{topic}")
    await send_long(update, resp)


async def cmd_book(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Standard book guidance — what to read, how much, which edition."""
    if not check_auth(update): return
    query = " ".join(ctx.args) if ctx.args else ""
    if not query:
        await update.message.reply_text(
            "Usage: /book <topic or book name>\n"
            "Examples:\n"
            "  /book polity\n"
            "  /book Laxmikanth which chapters\n"
            "  /book economy standard books\n"
            "  /book environment best source"); return
    await thinking(update, f"📚 Book guidance: {query}...")
    prompt = (
        f"STANDARD BOOK GUIDANCE: {query}\n\n"
        "As Hermes with 22 years of UPSC coaching:\n"
        "1. RECOMMENDED BOOKS — title, author, edition (be specific)\n"
        "2. HOW MUCH TO READ — full book? Specific chapters? First reading vs revision?\n"
        "3. READING STRATEGY — what to annotate, what to skim, what to skip\n"
        "4. EDITION TRAP — is the latest edition always better? Any specific edition recommended?\n"
        "5. TIME INVESTMENT — realistic hours to complete this source\n"
        "6. INTEGRATION — how does this source connect with other books?\n"
        "7. FOR GAD SPECIFICALLY — given his 1,820 hours, how to prioritise this source"
    )
    mem = get_memory_context()
    resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)
    log_hermes("/book", query, resp, tok, lat)
    await send_long(update, resp)


async def cmd_source(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Find the best source for any specific UPSC topic."""
    if not check_auth(update): return
    topic = " ".join(ctx.args) if ctx.args else ""
    if not topic:
        await update.message.reply_text("Usage: /source <topic>"); return
    await thinking(update, f"🔍 Best source for: {topic}...")
    prompt = (
        f"BEST SOURCE FOR: {topic}\n\n"
        "Give me the fastest path to mastery:\n"
        "1. PRIMARY SOURCE — the one book/document every topper reads for this\n"
        "2. GOVERNMENT SOURCE — any official report, committee, ministry document\n"
        "3. NEWSPAPER SOURCE — Hindu editorial, EPW, PIB — is this a CA topic?\n"
        "4. ONLINE SOURCE — any reliable website, Shodhganga, PRS India, etc.\n"
        "5. WHAT TO IGNORE — popular but useless sources for this topic\n"
        "6. TIME vs VALUE — is this topic worth deep reading or surface coverage?\n"
        "7. ONE-PAGE SUMMARY — if you had to give me this topic in 100 words, what are they?"
    )
    mem = get_memory_context()
    resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)
    log_hermes("/source", topic, resp, tok, lat)
    await send_long(update, resp)


# ================================================================
# SECTION 7 — INTERVIEW
# ================================================================

async def cmd_daf(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Stateful DAF interview — 3 rounds, hidden rubric, auto-advance angle."""
    if not check_auth(update): return
    clear_session(ctx)

    # Optional angle arg: /daf tech | /daf brain_drain | /daf telugu | /daf canada | /daf ai
    _alias = {"brain": "brain_drain", "ai": "ai_ethics", "drain": "brain_drain"}
    raw_angle = (ctx.args[0].lower() if ctx.args else "")
    angle = _alias.get(raw_angle, raw_angle) if raw_angle in {*_DAF_ANGLE_MAP, *_alias} else ""

    await thinking(update, "🎙️ Interview board loading...")
    mem = get_memory_context()

    try:
        question, key, tok, lat = await generate_daf_question(angle, mem)
    except Exception as e:
        log.error(f"DAF question generation failed: {e}")
        await update.message.reply_text("⚠️ Board room unavailable. Try again.")
        return

    set_session(ctx, "daf", {
        "question":   question,
        "answer_key": key,
        "angle":      key.get("angle", angle or "mixed"),
        "round":      1,
        "scores":     [],
        "started_at": datetime.utcnow().isoformat(),
    })

    log_hermes("/daf", angle or "auto", question, tok, lat)
    await send_long(update,
        f"🎙️ INTERVIEW BOARD — Round 1/3\n{DIVIDER}\n\n"
        f"{question}\n\n"
        f"(Type your answer. /cancel to exit.)"
    )


async def cmd_mock_iq(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Stateful 5-question mock panel — answer one at a time, graded per question."""
    if not check_auth(update): return
    clear_session(ctx)

    await thinking(update, "🎙️ Generating 5-member panel questions...")
    mem = get_memory_context()

    try:
        questions, keys, tok, lat = await generate_mock_iq_questions(mem)
    except Exception as e:
        log.error(f"Mock IQ generation failed: {e}")
        await update.message.reply_text("⚠️ Panel generation failed. Try again.")
        return

    set_session(ctx, "mock_iq", {
        "questions":  questions,
        "keys":       keys,
        "current_q":  0,
        "scores":     [],
        "started_at": datetime.utcnow().isoformat(),
    })

    log_hermes("/mock_iq", "5q-start", questions[0], tok, lat)
    await send_long(update,
        f"🎙️ MOCK INTERVIEW — 5 Questions\n{DIVIDER}\n\n"
        f"Answer each question individually. Panel will evaluate each one.\n\n"
        f"{questions[0]}\n\n"
        f"(Q1/5 — Type your answer. /cancel to exit.)"
    )


# ================================================================
# SECTION 8 — MOBILE PRACTICE (Databricks Volume)
# ================================================================

async def cmd_phone(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    target = _get_target_date(ctx.args)
    await thinking(update, f"📱 Quick summary: {target}...")
    queue = get_practice_queue(target)
    if queue and queue.get("mode8_phone_summary"):
        await send_long(update,
            f"📱 QUICK SUMMARY — {target}\n{DIVIDER}\n\n{queue['mode8_phone_summary']}")
        return
    content = fetch_volume_file(f"{VOLUME_BASE}/{target}/08_Phone_Summary.md")
    if content:
        await send_long(update, f"📱 QUICK SUMMARY — {target}\n{DIVIDER}\n\n{content}")
        return
    await update.message.reply_text(f"❌ No phone summary for {target}. Try /daily.")


async def cmd_practice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    target = _get_target_date(ctx.args)
    await thinking(update, f"📚 Practice package: {target}...")
    queue = get_practice_queue(target)
    parts = []
    tutor = (queue or {}).get("mode7_tutor_brief", "") or \
            fetch_volume_file(f"{VOLUME_BASE}/{target}/07_AI_Tutor_Brief.md") or ""
    if tutor:
        parts.append(f"🧑‍🏫 TUTOR BRIEF\n{DIVIDER}\n{tutor}")
    insights = fetch_volume_file(f"{VOLUME_BASE}/{target}/key_insights.md") or ""
    if insights:
        parts.append(f"💡 KEY INSIGHTS\n{DIVIDER}\n{insights}")
    phone = (queue or {}).get("mode8_phone_summary", "")
    if phone:
        parts.append(f"📱 QUICK SUMMARY\n{DIVIDER}\n{phone}")
    if parts:
        await send_long(update,
            f"📚 PRACTICE PACKAGE — {target}\n{DIVIDER_WIDE}\n\n" + "\n\n".join(parts))
    else:
        await update.message.reply_text(f"❌ No practice content for {target}. Try /daily.")


async def cmd_podcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    target = _get_target_date(ctx.args)
    await thinking(update, f"🎙️ Podcast: {target}...")
    content = fetch_volume_file(f"{VOLUME_BASE}/{target}/podcast_transcript.md")
    if content:
        await send_long(update, f"🎙️ PODCAST — {target}\n{DIVIDER_WIDE}\n\n{content}"); return
    queue = get_practice_queue(target)
    if queue and queue.get("audio_script"):
        await send_long(update,
            f"🎙️ AUDIO SCRIPT — {target}\n{DIVIDER_WIDE}\n\n{queue['audio_script']}")
    else:
        await update.message.reply_text(f"❌ No podcast for {target}. Try /practice.")


async def cmd_insights(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    target = _get_target_date(ctx.args)
    await thinking(update, f"💡 Key insights: {target}...")
    content = fetch_volume_file(f"{VOLUME_BASE}/{target}/key_insights.md")
    if content:
        await send_long(update,
            f"💡 KEY INSIGHTS — {target}\n{DIVIDER_WIDE}\n\n{content}"); return
    queue = get_practice_queue(target)
    if queue and queue.get("mode1_practice_answer"):
        await send_long(update,
            f"💡 KEY TAKEAWAYS — {target}\n{DIVIDER_WIDE}\n\n"
            f"Practice Answer:\n{queue['mode1_practice_answer']}\n\n"
            f"Memory Hook:\n{queue.get('memory_hook','N/A')}")
    else:
        await update.message.reply_text(f"❌ No insights for {target}. Try /daily.")


async def cmd_raw(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    args = ctx.args or []
    if not args:
        await update.message.reply_text(
            "Usage: /raw <filename>  or  /raw <date> <filename>"); return
    if len(args) >= 2 and re.match(r"^\d{4}-\d{2}-\d{2}$", args[0]):
        target, filename = args[0], " ".join(args[1:])
    else:
        target, filename = date.today().isoformat(), " ".join(args)
    content = fetch_volume_file(f"{VOLUME_BASE}/{target}/{filename}")
    if content:
        await send_long(update, f"📄 {filename} — {target}\n{DIVIDER_WIDE}\n\n{content}")
    else:
        await update.message.reply_text(f"❌ Not found: {filename}. Use /files.")


async def cmd_files(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    target = _get_target_date(ctx.args)
    await update.message.reply_text(f"📂 Checking files: {target}...")
    files = list_volume_files(f"{VOLUME_BASE}/{target}")
    if files:
        emoji_map = {"phone":"📱","quick":"📱","podcast":"🎙️","transcript":"🎙️",
                     "insight":"💡","tutor":"🧑‍🏫","mcq":"🧠","prelims":"🧠",
                     "ethics":"⚖️","mains":"✍️","model":"✍️",
                     "telugu":"📖","karl":"📋","knowledge":"📓","qa":"📓"}
        msg = f"📂 FILES — {target}\n{DIVIDER}\n\n"
        total = 0
        for f in sorted(files, key=lambda x: x.get("name", "")):
            name = f.get("name", "?")
            size = f.get("file_size", 0) or 0
            total += size
            em = next((v for k,v in emoji_map.items() if k in name.lower()), "📄")
            msg += f"{em} {name} ({size:,}B)\n"
        msg += f"\n{DIVIDER}\n{len(files)} files | {total:,} bytes"
        await update.message.reply_text(msg)
    else:
        await update.message.reply_text(
            f"❌ No files for {target}.\n"
            "Pipeline: 7AM IST NB6 → 8AM NB7 → 8:30AM NB8\n"
            "Try: /files 2026-03-29")


async def cmd_snapshot(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Combined daily snapshot — Hermes analysed."""
    if not check_auth(update): return
    await thinking(update, "📸 Building snapshot...")
    today = date.today().isoformat()
    content = fetch_volume_file(f"{VOLUME_BASE}/{today}/00_Daily_Snapshot.md")
    if not content:
        daily  = fetch_volume_file(f"{VOLUME_BASE}/{today}/08_Phone_Summary.md") or ""
        insigh = fetch_volume_file(f"{VOLUME_BASE}/{today}/key_insights.md") or ""
        content = f"{daily}\n\n{insigh}".strip()
    if content:
        prompt = (
            f"Today's snapshot content:\n{content[:4000]}\n\n"
            "As Hermes:\n"
            "1. TOP STORY — most UPSC-critical item today\n"
            "2. MUST-REMEMBER FACT — one thing I cannot forget from today\n"
            "3. MAINS QUESTION — frame one question from today's content\n"
            "4. STUDY PRIORITY — given my weak topics, what should I focus on today?\n"
            "5. MOTIVATION CHECK — am I on pace for AIR 1-75?"
        )
        mem = get_memory_context()
        resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)
        log_hermes("/snapshot", today, resp, tok, lat)
        await send_long(update, resp)
    else:
        await update.message.reply_text("❌ No snapshot yet. Try /daily.")


# ================================================================
# SECTION 9 — SYSTEM
# ================================================================

async def cmd_sync(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    try:
        if not VAULT_PATH.exists():
            await update.message.reply_text("⚠️ VAULT_PATH not found. Skipping git sync."); return
        CLAUDE_MD = VAULT_PATH / ".claude" / "CLAUDE.md"
        CLAUDE_MD.parent.mkdir(parents=True, exist_ok=True)
        weak     = _db_fetch("SELECT subject,topic,miss_count FROM weak_topics ORDER BY miss_count DESC LIMIT 10")
        concepts = _db_fetch("SELECT concept FROM concepts_taught ORDER BY timestamp DESC LIMIT 20")
        flaws    = _db_fetch("SELECT flaw_type,frequency FROM mains_flaws ORDER BY frequency DESC LIMIT 5")
        lines = [f"# HERMES Context — {date.today().isoformat()}", ""]
        if weak:
            lines += ["## Weak Topics"] + [f"- [{s}] {t} ({m}x)" for s,t,m in weak] + [""]
        if flaws:
            lines += ["## Mains Flaws"] + [f"- {f} ({n}x)" for f,n in flaws] + [""]
        if concepts:
            lines += ["## Concepts Taught", ", ".join(c for (c,) in concepts), ""]
        CLAUDE_MD.write_text("\n".join(lines), encoding="utf-8")
        try:
            for cmd in [
                ["git","-C",str(VAULT_PATH),"add",".claude/CLAUDE.md"],
                ["git","-C",str(VAULT_PATH),"commit","-m",f"hermes sync {date.today()}"],
                ["git","-C",str(VAULT_PATH),"push"],
            ]:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if r.returncode != 0 and "nothing to commit" not in r.stdout:
                    await update.message.reply_text(f"⚠️ Git: {r.stderr[:200]}"); return
            await update.message.reply_text(f"✅ Synced + pushed ({len(lines)} lines).")
        except FileNotFoundError:
            await update.message.reply_text(f"✅ CLAUDE.md written ({len(lines)} lines). git not found — not pushed.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Sync failed: {str(e)[:300]}")


async def cmd_compare(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Week comparison stats — Hermes vs main bot."""
    if not check_auth(update): return
    h_total = (_db_fetchone("SELECT COUNT(*) FROM hermes_interactions") or (0,))[0]
    h_week  = (_db_fetchone("SELECT COUNT(*) FROM hermes_interactions WHERE timestamp>=date('now','-7 days')") or (0,))[0]
    h_tok   = (_db_fetchone("SELECT COALESCE(SUM(tokens_used),0) FROM hermes_interactions WHERE timestamp>=date('now','-7 days')") or (0,))[0]
    h_lat   = (_db_fetchone("SELECT COALESCE(AVG(latency_ms),0) FROM hermes_interactions WHERE latency_ms>0") or (0,))[0]
    m_total = (_db_fetchone("SELECT COUNT(*) FROM interactions") or (0,))[0]
    m_week  = (_db_fetchone("SELECT COUNT(*) FROM interactions WHERE timestamp>=date('now','-7 days')") or (0,))[0]
    ratings = _db_fetch("SELECT AVG(rating), COUNT(*) FROM hermes_feedback WHERE timestamp>=date('now','-7 days')")
    avg_r, r_count = ratings[0] if ratings else (None, 0)
    await update.message.reply_text(
        f"📊 WEEK COMPARISON\n{DIVIDER_WIDE}\n\n"
        f"MAIN BOT (Databricks Llama):\n"
        f"  Total: {m_total} | This week: {m_week}\n"
        f"  Latency: ~10-30s | Cost: Databricks compute\n\n"
        f"HERMES (Groq Llama — same model):\n"
        f"  Total: {h_total} | This week: {h_week}\n"
        f"  Tokens this week: {h_tok:,}\n"
        f"  Avg latency: {h_lat:.0f}ms\n"
        f"  Est. cost: $0.00\n"
        f"  User rating: {f'{avg_r:.1f}/5 ({r_count} ratings)' if avg_r else 'Not rated yet'}\n\n"
        f"{DIVIDER}\n"
        f"Rate Hermes: /feedback <1-5> <note>\n"
        f"Decide after 7 days — keep both, merge, or dissolve."
    )


async def cmd_feedback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    args = ctx.args or []
    if not args:
        await update.message.reply_text("Usage: /feedback <1-5> <note>"); return
    try:
        rating = int(args[0])
        note   = " ".join(args[1:]) if len(args) > 1 else ""
        _db_exec("INSERT INTO hermes_feedback(rating,note) VALUES(?,?)", (rating, note))
        await update.message.reply_text(f"✅ Feedback: {rating}/5. Noted.")
    except ValueError:
        await update.message.reply_text("Usage: /feedback <1-5> <note>")


async def cmd_backup(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    backup_db()
    backup_dir = DB_PATH.parent / ".backups"
    backups = sorted(backup_dir.glob("*.db")) if backup_dir.exists() else []
    msg = f"✅ Backup complete.\nTotal backups: {len(backups)} (keeping 14 days)"
    if backups:
        latest = backups[-1]
        msg += f"\nLatest: {latest.name} ({latest.stat().st_size/1024:.1f} KB)"
    await update.message.reply_text(msg)


async def cmd_eval_log(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    history = _db_fetch(
        "SELECT timestamp, topic, score FROM evaluation_history "
        "ORDER BY timestamp DESC LIMIT 10")
    if not history:
        await update.message.reply_text("No evaluations yet. Use /evaluate."); return
    report = f"📊 Evaluation History\n{DIVIDER}\n\n"
    for ts, topic, score in history:
        emoji = "🔴" if (score or 0) < 5 else "🟡" if (score or 0) < 7 else "🟢"
        report += f"{emoji} {(topic or 'Unknown')[:30]:30} {score or 0:.1f}/10  {(ts or '')[:10]}\n"
    report += "\n💡 Red (<5) → auto-added to /weak"
    await update.message.reply_text(report)


# ================================================================
# INLINE KEYBOARD CALLBACK HANDLER (quiz/drill button answers)
# ================================================================

async def handle_quiz_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle A/B/C/D button taps from InlineKeyboardMarkup."""
    query = update.callback_query
    await query.answer()  # acknowledge the tap immediately

    if not check_auth(update):
        return

    data = query.data or ""
    if not data.startswith("quiz_ans:"):
        return

    answer = data.split(":", 1)[1].upper()
    if answer not in {"A", "B", "C", "D"}:
        return

    # Disable the keyboard so the user can't tap again
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass

    session = get_session(ctx)
    if not session:
        await query.message.reply_text("No active quiz session. Use /quiz to start.")
        return

    mode = session.get("mode")

    if mode == "quiz":
        topic   = session["data"].get("topic", "Prelims")
        concept = session["data"].get("concept", topic)
        key     = session["data"].get("answer_key", {})
        attempts = int(session["data"].get("attempts", 0)) + 1
        session["data"]["attempts"] = attempts
        touch_session(ctx)

        correct_option = str(key.get("correct_option", "")).upper()
        is_correct = (answer == correct_option)

        # Emoji reaction for instant feedback
        await query.message.reply_text("✅ Correct!" if is_correct else "❌ Wrong!")

        feedback = render_quiz_feedback(answer, key, is_correct)
        _db_exec(
            "INSERT INTO quiz_history(subject,question,user_answer,was_correct,score,topic) "
            "VALUES(?,?,?,?,?,?)",
            (topic, session["data"].get("question_text", "")[:1000], answer,
             1 if is_correct else 0, 1.0 if is_correct else 0.0, concept)
        )
        if not is_correct:
            log_weakness("Prelims", concept, "quiz")

        mem = get_memory_context()
        try:
            followup_public, followup_key, tok, lat = await generate_quiz_with_key(
                topic, mem, concept_hint=concept)
            log_hermes("quiz_followup_btn", f"{concept}|{answer}", followup_public, tok, lat)
        except Exception as e:
            log.error(f"quiz button follow-up failed: {e}")
            clear_session(ctx)
            await query.message.reply_text(
                feedback + "\n\n⚠️ Follow-up generation failed. Start again with /quiz.")
            return

        session["data"]["question_text"] = followup_public
        session["data"]["answer_key"]    = followup_key
        session["data"]["concept"]       = followup_key.get("concept", concept)
        touch_session(ctx)

        await query.message.reply_text(
            feedback + "\n\nFOLLOW-UP:\n" + followup_public,
            reply_markup=build_answer_keyboard()
        )

    elif mode == "drill":
        # For drill: accumulate answers in session, grade when all 3 received
        answers = session["data"].get("button_answers", {})
        answered_count = len(answers)
        next_q = answered_count + 1
        if next_q > 3:
            await query.message.reply_text("All 3 drill questions already answered.")
            return

        answers[next_q] = answer
        session["data"]["button_answers"] = answers
        touch_session(ctx)

        if len(answers) < 3:
            await query.message.reply_text(
                f"✓ Q{next_q} answered: {answer}. Reply for Q{next_q + 1} or tap a button.",
                reply_markup=build_answer_keyboard()
            )
        else:
            # All 3 answers received — grade the drill
            await query.message.reply_text("🧠 Grading drill...", reply_markup=None)
            drill_keys = session["data"].get("drill_keys", [])
            session["data"]["attempts"] = int(session["data"].get("attempts", 0)) + 1
            touch_session(ctx)

            total_correct = 0
            result_blocks = []
            incorrect_concepts = []

            for qkey in drill_keys:
                qno = qkey["qno"]
                user_answer = answers.get(qno, "?")
                correct_option = qkey["correct_option"]
                is_correct_q = (user_answer == correct_option)
                if is_correct_q:
                    total_correct += 1
                else:
                    incorrect_concepts.append({"topic": qkey.get("topic", "Prelims"),
                                               "concept": qkey.get("concept", "General")})
                _db_exec(
                    "INSERT INTO quiz_history(subject,question,user_answer,was_correct,score,topic) "
                    "VALUES(?,?,?,?,?,?)",
                    (qkey.get("topic", "Prelims"),
                     f"Drill Q{qno}: {session['data'].get('questions_text', '')[:900]}",
                     user_answer, 1 if is_correct_q else 0,
                     1.0 if is_correct_q else 0.0,
                     qkey.get("concept", qkey.get("topic", "General")))
                )
                result_blocks.append(render_single_drill_result(qkey, user_answer, is_correct_q))
                if not is_correct_q:
                    log_weakness("Prelims", qkey.get("concept", qkey.get("topic", "General")), "drill")

            summary = (f"🌪️ DRILL RESULT\n{DIVIDER}\nScore: {total_correct}/3\n\n"
                       + "\n\n".join(result_blocks))

            weakest_concept = incorrect_concepts[0]["concept"] if incorrect_concepts else None
            if weakest_concept:
                summary += f"\n\nWEAKEST CONCEPT TO REVISE NEXT:\n{weakest_concept}"
                mem = get_memory_context()
                try:
                    followup_pub, followup_key, tok, lat = await generate_quiz_with_key(
                        "Prelims", mem, concept_hint=weakest_concept)
                    log_hermes("drill_followup_btn", weakest_concept, followup_pub, tok, lat)
                    set_session(ctx, "quiz", {
                        "topic": followup_key.get("topic", "Prelims"),
                        "concept": followup_key.get("concept", weakest_concept),
                        "question_text": followup_pub, "answer_key": followup_key,
                        "attempts": 0, "started_at": datetime.utcnow().isoformat()
                    })
                    await query.message.reply_text(
                        summary + "\n\nFOLLOW-UP MCQ ON YOUR WEAKEST CONCEPT:\n" + followup_pub,
                        reply_markup=build_answer_keyboard()
                    )
                    return
                except Exception as e:
                    log.error(f"Drill button follow-up failed: {e}")

            clear_session(ctx)
            await query.message.reply_text(summary + "\n\n✅ Drill session complete.")


# ================================================================
# FREE TEXT HANDLER — the main differentiator
# Just type anything. Hermes responds with full context.
# ================================================================

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update):
        return

    user_msg = update.message.text
    if not user_msg:
        return

    # ── Session inactivity timeout check ─────────────────────────
    if check_session_timeout(ctx):
        await update.message.reply_text(SESSION_TIMEOUT_MSG)
        # Fall through to handle as free-text (no active session)

    session = get_session(ctx)

    # ============================================================
    # QUIZ SESSION CONTINUATION (DETERMINISTIC)
    # ============================================================
    if session and session.get("mode") == "quiz":
        await thinking(update, "🧠 Evaluating quiz answer...")

        answer = normalise_mcq_answer(user_msg)
        if answer not in {"A", "B", "C", "D"}:
            await update.message.reply_text("Reply with A, B, C, or D.")
            return

        topic = session["data"].get("topic", "Prelims")
        concept = session["data"].get("concept", topic)
        key = session["data"].get("answer_key", {})
        attempts = int(session["data"].get("attempts", 0)) + 1
        session["data"]["attempts"] = attempts
        touch_session(ctx)

        correct_option = str(key.get("correct_option", "")).upper()
        is_correct = (answer == correct_option)

        # Emoji reaction for instant feedback before detailed explanation
        await update.message.reply_text("✅ Correct!" if is_correct else "❌ Wrong!")

        feedback = render_quiz_feedback(answer, key, is_correct)

        _db_exec(
            "INSERT INTO quiz_history(subject,question,user_answer,was_correct,score,topic) "
            "VALUES(?,?,?,?,?,?)",
            (
                topic,
                session["data"].get("question_text", "")[:1000],
                answer,
                1 if is_correct else 0,
                1.0 if is_correct else 0.0,
                concept
            )
        )

        if not is_correct:
            log_weakness("Prelims", concept, "quiz")

        # Generate follow-up on same concept
        mem = get_memory_context()
        try:
            followup_public, followup_key, tok, lat = await generate_quiz_with_key(topic, mem, concept_hint=concept)
            log_hermes("quiz_followup", f"{concept} | {answer}", followup_public, tok, lat)
        except Exception as e:
            log.error(f"quiz follow-up generation failed: {e}")
            clear_session(ctx)
            await send_long(update, feedback + "\n\n⚠️ Follow-up generation failed. Start again with /quiz.")
            return

        session["data"]["question_text"] = followup_public
        session["data"]["answer_key"] = followup_key
        session["data"]["concept"] = followup_key.get("concept", concept)
        touch_session(ctx)

        await update.message.reply_text(
            feedback + "\n\nFOLLOW-UP:\n" + followup_public,
            reply_markup=build_answer_keyboard()
        )
        return

    # ============================================================
    # DRILL SESSION CONTINUATION (DETERMINISTIC)
    # ============================================================
    if session and session.get("mode") == "drill":
        await thinking(update, "🧠 Grading drill...")

        answers = parse_drill_answers(user_msg)
        if set(answers.keys()) != {1, 2, 3}:
            await update.message.reply_text(
                "Reply with all 3 answers in one line.\n"
                "Examples:\n"
                "1-B 2-D 3-A\n"
                "B D A\n"
                "1) B, 2) D, 3) A"
            )
            return

        drill_keys = session["data"].get("drill_keys", [])
        session["data"]["attempts"] = int(session["data"].get("attempts", 0)) + 1
        touch_session(ctx)

        total_correct = 0
        result_blocks = []
        incorrect_concepts = []

        for qkey in drill_keys:
            qno = qkey["qno"]
            user_answer = answers.get(qno, "?")
            correct_option = qkey["correct_option"]
            is_correct = (user_answer == correct_option)

            if is_correct:
                total_correct += 1
            else:
                incorrect_concepts.append({
                    "topic": qkey.get("topic", "Prelims"),
                    "concept": qkey.get("concept", qkey.get("topic", "General"))
                })
                log_weakness("Prelims", qkey.get("concept", qkey.get("topic", "General")), "drill")

            _db_exec(
                "INSERT INTO quiz_history(subject,question,user_answer,was_correct,score,topic) "
                "VALUES(?,?,?,?,?,?)",
                (
                    qkey.get("topic", "Prelims"),
                    f"Drill Q{qno}: {session['data'].get('questions_text', '')[:900]}",
                    user_answer,
                    1 if is_correct else 0,
                    1.0 if is_correct else 0.0,
                    qkey.get("concept", qkey.get("topic", "General"))
                )
            )

            result_blocks.append(render_single_drill_result(qkey, user_answer, is_correct))

        weakest_concept = None
        if incorrect_concepts:
            weakest_concept = incorrect_concepts[0]["concept"]

        summary = (
            f"🌪️ DRILL RESULT\n{DIVIDER}\n"
            f"Score: {total_correct}/3\n\n"
            + "\n\n".join(result_blocks)
        )

        if weakest_concept:
            summary += (
                f"\n\nWEAKEST CONCEPT TO REVISE NEXT:\n"
                f"{weakest_concept}"
            )

            # Follow-up: auto-switch into quiz mode on weakest concept
            mem = get_memory_context()
            try:
                followup_public, followup_key, tok, lat = await generate_quiz_with_key(
                    "Prelims",
                    mem,
                    concept_hint=weakest_concept
                )
                log_hermes("drill_followup", weakest_concept, followup_public, tok, lat)

                set_session(ctx, "quiz", {
                    "topic": followup_key.get("topic", "Prelims"),
                    "concept": followup_key.get("concept", weakest_concept),
                    "question_text": followup_public,
                    "answer_key": followup_key,
                    "attempts": 0,
                    "started_at": datetime.utcnow().isoformat()
                })

                await send_long(
                    update,
                    summary + "\n\nFOLLOW-UP MCQ ON YOUR WEAKEST CONCEPT:\n" + followup_public
                )
                return

            except Exception as e:
                log.error(f"Drill follow-up quiz generation failed: {e}")
                clear_session(ctx)
                await send_long(update, summary + "\n\n⚠️ Follow-up generation failed. Start again with /quiz or /drill.")
                return

        clear_session(ctx)
        await send_long(update, summary + "\n\n✅ Drill session complete.")
        return

    # ============================================================
    # DAF SESSION CONTINUATION (STATEFUL 3-ROUND INTERVIEW)
    # ============================================================
    if session and session.get("mode") == "daf":
        await thinking(update, "🎙️ Board evaluating...")

        question      = session["data"].get("question", "")
        key           = session["data"].get("answer_key", {})
        current_round = int(session["data"].get("round", 1))
        scores        = list(session["data"].get("scores", []))

        mem         = get_memory_context()
        eval_prompt = build_daf_eval_prompt(question, user_msg, key)
        eval_resp, tok, lat = await asyncio.to_thread(call_hermes, eval_prompt, mem)
        log_hermes("daf_eval", user_msg[:200], eval_resp, tok, lat)

        score_match = re.search(r'SCORE:\s*(\d+(?:\.\d+)?)\s*/\s*10', eval_resp, re.IGNORECASE)
        score = float(score_match.group(1)) if score_match else 5.0
        scores.append(score)

        _db_exec(
            "INSERT INTO interview_history(mode,round,angle,question,user_answer,score,feedback) "
            "VALUES(?,?,?,?,?,?,?)",
            ("daf", current_round, session["data"].get("angle", ""),
             question[:1000], user_msg[:1000], score, eval_resp[:2000])
        )

        if current_round >= 3:
            avg = sum(scores) / len(scores) if scores else 0
            score_summary = " | ".join(f"R{i+1}: {s:.1f}/10" for i, s in enumerate(scores))
            clear_session(ctx)
            await send_long(update,
                f"ROUND {current_round} EVALUATION:\n{eval_resp}\n\n"
                f"{DIVIDER_WIDE}\n\n"
                f"🎙️ INTERVIEW COMPLETE\n"
                f"Scores: {score_summary}\n"
                f"Average: {avg:.1f}/10\n\n"
                f"Use /daf [angle] for a focused session or /mock_iq for a full panel."
            )
            return

        # Auto-advance to next angle using follow_up_angles from the key
        follow_ups = key.get("follow_up_angles", [])
        next_angle_raw = follow_ups[0].lower() if follow_ups else ""
        _fw_alias = {
            "tech": "tech", "data": "tech", "governance": "tech",
            "brain": "brain_drain", "drain": "brain_drain",
            "telugu": "telugu", "language": "telugu", "linguistics": "telugu",
            "canada": "canada", "canadian": "canada", "federalism": "canada",
            "ai": "ai_ethics", "ethics": "ai_ethics", "artificial": "ai_ethics",
        }
        next_angle = ""
        for word in next_angle_raw.split():
            if word in _fw_alias:
                next_angle = _fw_alias[word]
                break

        try:
            next_q, next_key, tok2, lat2 = await generate_daf_question(next_angle, mem)
            log_hermes("daf_next", next_angle or "auto", next_q, tok2, lat2)

            session["data"]["question"]   = next_q
            session["data"]["answer_key"] = next_key
            session["data"]["angle"]      = next_key.get("angle", next_angle or "mixed")
            session["data"]["round"]      = current_round + 1
            session["data"]["scores"]     = scores
            touch_session(ctx)

            await send_long(update,
                f"ROUND {current_round} EVALUATION:\n{eval_resp}\n\n"
                f"{DIVIDER}\n\n"
                f"🎙️ ROUND {current_round + 1}/3 — New angle:\n\n"
                f"{next_q}\n\n"
                f"(Type your answer.)"
            )
        except Exception as e:
            log.error(f"DAF next question generation failed: {e}")
            clear_session(ctx)
            await send_long(update,
                f"ROUND {current_round} EVALUATION:\n{eval_resp}\n\n"
                f"⚠️ Next round generation failed. Start fresh with /daf."
            )
        return

    # ============================================================
    # MOCK IQ SESSION CONTINUATION (STATEFUL 5-QUESTION PANEL)
    # ============================================================
    if session and session.get("mode") == "mock_iq":
        await thinking(update, "🎙️ Panel evaluating...")

        questions    = session["data"].get("questions", [])
        keys         = session["data"].get("keys", [])
        current_q    = int(session["data"].get("current_q", 0))
        scores       = list(session["data"].get("scores", []))

        if current_q >= len(questions):
            clear_session(ctx)
            await update.message.reply_text("✅ Mock interview already complete.")
            return

        question = questions[current_q]
        key      = keys[current_q] if current_q < len(keys) else {}
        member   = key.get("member", f"Member {current_q + 1}")

        mem         = get_memory_context()
        eval_prompt = build_interview_eval_prompt(question, member, user_msg, key)
        eval_resp, tok, lat = await asyncio.to_thread(call_hermes, eval_prompt, mem)
        log_hermes("mock_iq_eval", user_msg[:200], eval_resp, tok, lat)

        score_match = re.search(r'SCORE:\s*(\d+(?:\.\d+)?)\s*/\s*10', eval_resp, re.IGNORECASE)
        score = float(score_match.group(1)) if score_match else 5.0
        scores.append({"qno": current_q + 1, "member": member, "score": score})

        _db_exec(
            "INSERT INTO interview_history(mode,round,angle,question,user_answer,score,feedback) "
            "VALUES(?,?,?,?,?,?,?)",
            ("mock_iq", current_q + 1, member,
             question[:1000], user_msg[:1000], score, eval_resp[:2000])
        )

        next_q = current_q + 1

        if next_q >= len(questions):
            avg = sum(s["score"] for s in scores) / len(scores) if scores else 0
            score_lines = " | ".join(
                f"Q{s['qno']}({s['member'][:4]}): {s['score']:.1f}" for s in scores
            )
            clear_session(ctx)
            await send_long(update,
                f"EVALUATION — {member}:\n{eval_resp}\n\n"
                f"{DIVIDER_WIDE}\n\n"
                f"🎙️ MOCK INTERVIEW COMPLETE\n"
                f"Scores: {score_lines}\n"
                f"Average: {avg:.1f}/10\n\n"
                f"Use /daf to deep-dive any angle, or /weak to see patterns."
            )
            return

        session["data"]["current_q"] = next_q
        session["data"]["scores"]    = scores
        touch_session(ctx)

        next_question = questions[next_q]
        await send_long(update,
            f"EVALUATION — {member}:\n{eval_resp}\n\n"
            f"{DIVIDER}\n\n"
            f"{next_question}\n\n"
            f"(Q{next_q + 1}/5 — Type your answer.)"
        )
        return

    # ============================================================
    # RECALL SESSION CONTINUATION (V1.8)
    # ============================================================
    if session and session.get("mode") == "recall":
        await thinking(update, "💡 Grading your recall...")

        topic       = session["data"].get("topic", "")
        phase       = session["data"].get("phase", "dump")
        key         = session["data"].get("answer_key", {})
        scores      = session["data"].get("scores", [])

        mem = get_memory_context()

        if phase == "dump":
            # ── Phase 1: grade the brain dump, ask targeted follow-up
            eval_prompt = build_recall_eval_prompt(
                topic,
                key.get("expected_points", []),
                key.get("trap_points", []),
                key.get("follow_up_gap", "core mechanism"),
                user_msg,
            )
            eval_resp, tok, lat = await asyncio.to_thread(call_hermes, eval_prompt, mem)
            log_hermes("recall_eval", user_msg, eval_resp, tok, lat)

            score_match = re.search(r'SCORE:\s*(\d+(?:\.\d+)?)\s*/\s*10', eval_resp, re.IGNORECASE)
            score = float(score_match.group(1)) if score_match else 0.0
            scores.append(score)

            session["data"]["phase"] = "followup"
            session["data"]["followup_eval"] = eval_resp
            session["data"]["scores"] = scores
            touch_session(ctx)

            await send_long(update, eval_resp)
            return

        else:
            # ── Phase 2: final evaluation of follow-up answer → close session
            followup_prompt = (
                f"RECALL SESSION FINAL — Topic: {topic}\n\n"
                f"The student just answered the follow-up question.\n\n"
                f"STUDENT ANSWER:\n{user_msg}\n\n"
                "TASK:\n"
                "1. Did they close the gap? (1-3 lines)\n"
                "2. FINAL SCORE: X/10 (cumulative judgment)\n"
                "3. ONE strong revision tip for this topic\n"
                "4. End with: 'Session complete. /recall again or /progress for deeper drill.'"
            )
            final_resp, tok, lat = await asyncio.to_thread(call_hermes, followup_prompt, mem)
            log_hermes("recall_final", user_msg, final_resp, tok, lat)

            final_score_match = re.search(r'FINAL SCORE:\s*(\d+(?:\.\d+)?)\s*/\s*10',
                                          final_resp, re.IGNORECASE)
            final_score = float(final_score_match.group(1)) if final_score_match else 0.0
            scores.append(final_score)

            avg = sum(scores) / len(scores) if scores else 0.0
            summary = f"\n\n📊 Recall avg: {avg:.1f}/10"
            clear_session(ctx)
            await send_long(update, final_resp + summary)
            return

    # ============================================================
    # PROGRESS SESSION CONTINUATION (V1.8 — Bloom's Levels)
    # ============================================================
    if session and session.get("mode") == "progress":
        await thinking(update, "📈 Evaluating...")

        topic        = session["data"].get("topic", "")
        level        = int(session["data"].get("level", 1))
        question     = session["data"].get("question", "")
        key          = session["data"].get("answer_key", {})
        level_scores = session["data"].get("level_scores", [])
        retries      = int(session["data"].get("retries", 0))

        mem = get_memory_context()

        eval_prompt = build_progress_eval_prompt(topic, level, question, user_msg, key)
        eval_resp, tok, lat = await asyncio.to_thread(call_hermes, eval_prompt, mem)
        log_hermes("progress_eval", user_msg, eval_resp, tok, lat)

        score_match = re.search(r'SCORE:\s*(\d+(?:\.\d+)?)\s*/\s*10', eval_resp, re.IGNORECASE)
        score = float(score_match.group(1)) if score_match else 0.0

        verdict_pass = bool(re.search(r'VERDICT:\s*PASS', eval_resp, re.IGNORECASE))
        threshold    = int(key.get("pass_threshold", 6))
        passed       = verdict_pass or score >= threshold

        level_scores.append({"level": level, "score": score, "passed": passed})

        lvl_name = _BLOOM_LEVEL_NAMES.get(level, f"Level {level}")

        if passed and level >= 5:
            # ── Completed all 5 levels
            journey = " → ".join(
                f"L{e['level']}({e['score']:.0f})" for e in level_scores
            )
            summary = (
                f"\n\n{'='*40}\n"
                f"🏆 BLOOM'S COMPLETE — {topic.upper()}\n"
                f"Journey: {journey}\n"
                f"Final: {score:.1f}/10 at Level 5 (EVALUATE)\n"
                f"{'='*40}\n"
                f"Use /recall {topic} for another brain-dump session."
            )
            clear_session(ctx)
            await send_long(update, eval_resp + summary)
            return

        if passed:
            # ── Advance to next level
            next_level = level + 1
            next_q, next_key, tok2, lat2 = await generate_progress_question(topic, next_level, mem)
            log_hermes("progress_advance", topic, next_q, tok2, lat2)

            session["data"].update({
                "level": next_level,
                "question": next_q,
                "answer_key": next_key,
                "level_scores": level_scores,
                "retries": 0,
            })
            touch_session(ctx)

            next_name = _BLOOM_LEVEL_NAMES.get(next_level, f"Level {next_level}")
            await send_long(
                update,
                eval_resp
                + f"\n\n✅ PASS — advancing to Level {next_level}: {next_name}\n{DIVIDER}\n\n"
                + next_q
            )
        else:
            # ── Stay on same level (max 2 retries before forcing advance)
            if retries >= 2:
                if level < 5:
                    next_level = level + 1
                    next_q, next_key, tok2, lat2 = await generate_progress_question(topic, next_level, mem)
                    log_hermes("progress_forced_advance", topic, next_q, tok2, lat2)
                    session["data"].update({
                        "level": next_level,
                        "question": next_q,
                        "answer_key": next_key,
                        "level_scores": level_scores,
                        "retries": 0,
                    })
                    touch_session(ctx)
                    await send_long(
                        update,
                        eval_resp
                        + f"\n\n⚡ 3 attempts at Level {level} — moving forward.\n{DIVIDER}\n\n"
                        + next_q
                    )
                else:
                    # forced finish
                    clear_session(ctx)
                    await send_long(update, eval_resp + "\n\nSession ended. Use /recall to consolidate.")
            else:
                # retry same level
                retry_q, retry_key, tok2, lat2 = await generate_progress_question(topic, level, mem)
                log_hermes("progress_retry", topic, retry_q, tok2, lat2)
                session["data"].update({
                    "question": retry_q,
                    "answer_key": retry_key,
                    "level_scores": level_scores,
                    "retries": retries + 1,
                })
                touch_session(ctx)
                await send_long(
                    update,
                    eval_resp
                    + f"\n\n🔁 RETRY — Level {level}: {lvl_name} (attempt {retries + 2}/3)\n{DIVIDER}\n\n"
                    + retry_q
                )
        return

    # ============================================================
    # SOCRATIC SESSION CONTINUATION
    # ============================================================
    if session and session.get("mode") == "socratic":
        await thinking(update, "🤔 Going deeper...")

        topic = session["data"].get("topic", "General")
        last_prompt = session["data"].get("last_prompt", "")
        depth = int(session["data"].get("depth", 1))

        if depth >= 4:
            prompt = (
                "Conclude this Socratic mentoring session.\n\n"
                f"Topic: {topic}\n"
                f"Previous question:\n{last_prompt}\n\n"
                f"Student answer:\n{user_msg}\n\n"
                "Do this:\n"
                "1) Assess understanding in 3-5 lines\n"
                "2) Identify single biggest gap (if any)\n"
                "3) Give 5-line synthesis\n"
                "4) End with exactly one → Quick check question"
            )

            mem = get_memory_context()
            resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)
            log_hermes("socratic_final", user_msg, resp, tok, lat)
            clear_session(ctx)
            await send_long(update, resp)
            return

        prompt = (
            "Continue active Socratic session.\n\n"
            f"Topic: {topic}\n"
            f"Previous question:\n{last_prompt}\n\n"
            f"Student answer:\n{user_msg}\n\n"
            "Rules:\n"
            "1) Assess answer in 2-4 lines\n"
            "2) If sound → ask ONE deeper question\n"
            "3) If weak → correct in 2-4 lines and ask ONE simpler reformulated question\n"
            "4) No lecture. One question only. End with the question."
        )

        mem = get_memory_context()
        resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)
        log_hermes("socratic_followup", user_msg, resp, tok, lat)

        session["data"]["last_prompt"] = resp
        session["data"]["depth"] = depth + 1
        touch_session(ctx)

        await send_long(update, resp)
        return

    # ============================================================
    # DEFAULT FREE CHAT
    # ============================================================
    await thinking(update)
    mem = get_memory_context()
    resp, tok, lat = await asyncio.to_thread(call_hermes, user_msg, mem)
    log_hermes("direct", user_msg, resp, tok, lat)
    await send_long(update, resp)


# ================================================================
# MAIN

# ================================================================
# SECTION 10 — MASTERY TRACKER (Databricks Delta table)
# ================================================================

async def cmd_mastery(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show mastery dashboard from Databricks Delta table."""
    if not check_auth(update): return
    await thinking(update, "\U0001f4ca Querying mastery tracker...")
    summary = run_sql(
        "SELECT paper, COUNT(*) as total, "
        "SUM(CASE WHEN status='mastered' THEN 1 ELSE 0 END) as mastered, "
        "SUM(CASE WHEN status='in_progress' THEN 1 ELSE 0 END) as active, "
        "SUM(CASE WHEN status='needs_work' THEN 1 ELSE 0 END) as weak, "
        "SUM(CASE WHEN status='not_started' THEN 1 ELSE 0 END) as not_started, "
        "ROUND(AVG(mastery_pct),1) as avg_pct "
        "FROM upsc_catalog.rag.mastery_tracker GROUP BY paper ORDER BY paper")
    if not summary:
        await update.message.reply_text("\u274c Could not query mastery_tracker.")
        return
    msg = "\U0001f4ca MASTERY DASHBOARD\n" + DIVIDER_WIDE + "\n\n"
    grand_total = 0
    grand_mastered = 0
    for r in summary:
        p = r.get("paper", "?")
        t = int(r.get("total", 0))
        m = int(r.get("mastered", 0))
        a = int(r.get("active", 0))
        w = int(r.get("weak", 0))
        ns = int(r.get("not_started", 0))
        avg = float(r.get("avg_pct", 0))
        grand_total += t
        grand_mastered += m
        msg += f"{p}: {avg:.0f}% avg\n"
        msg += f"  \U0001f7e2{m} \U0001f7e1{a} \U0001f534{w} \u26aa{ns} / {t}\n\n"
    pct = (grand_mastered / grand_total * 100) if grand_total > 0 else 0
    msg += DIVIDER + "\n"
    msg += f"OVERALL: {grand_mastered}/{grand_total} mastered ({pct:.1f}%)\n"
    hy = run_sql(
        "SELECT topic_id, topic_name, paper FROM upsc_catalog.rag.mastery_tracker "
        "WHERE priority='HIGH_YIELD' AND status='not_started' "
        "ORDER BY paper, topic_id LIMIT 10")
    if hy:
        msg += "\n\U0001f525 HIGH-YIELD NOT STARTED:\n"
        for r in hy:
            msg += f"  {r['topic_id']} {r['topic_name']} [{r['paper']}]\n"
    due = run_sql(
        "SELECT topic_id, topic_name, next_review FROM upsc_catalog.rag.mastery_tracker "
        "WHERE next_review <= current_date() AND status != 'mastered' "
        "ORDER BY next_review LIMIT 5")
    if due:
        msg += "\n\u23f0 DUE FOR REVIEW:\n"
        for r in due:
            msg += f"  {r['topic_id']} {r['topic_name']} \u2014 due {r['next_review']}\n"
    await send_long(update, msg)


async def cmd_mastery_update(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Update mastery for a topic. Usage: /mastery_update GS1-001 45"""
    if not check_auth(update): return
    args = ctx.args or []
    if len(args) < 2:
        await update.message.reply_text(
            "Usage: /mastery_update <topic_id> <mastery_pct> [status]\n"
            "Example: /mastery_update GS1-001 45 in_progress\n"
            "Status auto-set: <40=needs_work, 40-79=in_progress, 80+=mastered")
        return
    topic_id = args[0].upper()
    try:
        pct = float(args[1])
    except ValueError:
        await update.message.reply_text("\u274c mastery_pct must be a number 0-100")
        return
    if len(args) > 2:
        status = args[2]
    elif pct >= 80:
        status = "mastered"
    elif pct >= 40:
        status = "in_progress"
    elif pct > 0:
        status = "needs_work"
    else:
        status = "not_started"
    result = run_sql(
        f"UPDATE upsc_catalog.rag.mastery_tracker SET "
        f"mastery_pct = {pct}, status = '{status}', "
        f"last_studied = current_date(), study_count = study_count + 1, "
        f"next_review = CASE "
        f"WHEN study_count = 0 THEN date_add(current_date(), 7) "
        f"WHEN study_count = 1 THEN date_add(current_date(), 15) "
        f"WHEN study_count = 2 THEN date_add(current_date(), 30) "
        f"WHEN study_count >= 3 THEN date_add(current_date(), 60) "
        f"ELSE date_add(current_date(), 7) END, "
        f"updated_at = current_timestamp() "
        f"WHERE topic_id = '{topic_id}'")
    if result is not None:
        await update.message.reply_text(
            f"\u2705 Updated {topic_id}: {pct}% | {status}\n"
            f"Spaced review scheduled.")
        log_hermes("/mastery_update", f"{topic_id} {pct}% {status}", "updated")
    else:
        await update.message.reply_text(f"\u274c Failed. Check topic_id: {topic_id}")


# ================================================================

def main():
    global groq_client

    # ── Startup config validation ─────────────────────────────────
    errors   = []
    warnings = []

    if not BOT_TOKEN:
        errors.append("HERMES_BOT_TOKEN (or TELEGRAM_TOKEN) is not set")
    if not GROQ_API_KEY:
        errors.append("GROQ_API_KEY is not set — free at console.groq.com")
    if not ALLOWED_USER_ID:
        warnings.append("TELEGRAM_USER_ID not set — bot is open to everyone!")
    if not DATABRICKS_HOST:
        warnings.append("DATABRICKS_HOST not set — Databricks models unavailable")
    if not DATABRICKS_TOKEN:
        warnings.append("DATABRICKS_TOKEN not set — Databricks models unavailable")

    # Print startup banner
    log.info("=" * 60)
    log.info(f"  HERMES {HERMES_VERSION} — UPSC AIR-1 Mentor Bot")
    log.info(f"  Groq backend  : {GROQ_MODEL}")
    log.info(f"  DBX Sonnet    : {DBX_MODEL_SONNET}")
    log.info(f"  DBX Opus      : {DBX_MODEL_OPUS}")
    log.info(f"  Session TTL   : {SESSION_TTL_SECONDS // 60} min")
    log.info(f"  DB path       : {DB_PATH}")
    log.info(f"  Vault         : {VAULT_PATH} ({'✓' if VAULT_PATH.exists() else '✗ not found'})")
    log.info(f"  Auth user     : {ALLOWED_USER_ID or 'OPEN (all users)!'}")
    for w in warnings:
        log.warning(f"  ⚠  {w}")
    log.info("=" * 60)

    if errors:
        for err in errors:
            log.error(f"STARTUP ERROR: {err}")
        return

    groq_client = Groq(api_key=GROQ_API_KEY)
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    commands = [
        # Core
        ("start",      cmd_start),     ("help",       cmd_help),
        ("cancel",     cmd_cancel),    ("teach",      cmd_teach),
        ("log",        cmd_log),       ("eod",        cmd_eod),
        ("daily",      cmd_daily),     ("dump",       cmd_dump),
        ("stats",      cmd_stats),     ("weak",       cmd_weak),
        # Prelims
        ("quiz",       cmd_quiz),      ("trap",       cmd_trap),
        ("drill",      cmd_drill),     ("pyq",        cmd_pyq),
        ("csat",       cmd_csat),      ("pattern",    cmd_pattern),
        ("examiner",   cmd_examiner),
        # Mains
        ("evaluate",   cmd_evaluate),  ("model",      cmd_model),
        ("essay",      cmd_essay),     ("framework",  cmd_framework),
        ("structure",  cmd_structure),
        # Active Learning
        ("socratic",   cmd_socratic),  ("feynman",    cmd_feynman),
        ("why",        cmd_why),       ("visual",     cmd_visual),
        ("recall",     cmd_recall),    ("simplify",   cmd_simplify),
        ("progress",   cmd_progress),
        # Telugu Optional
        ("telugu",     cmd_telugu),    ("tel_kavya",  cmd_tel_kavya),
        ("tel_prosody",cmd_tel_prosody),("tel_grammar",cmd_tel_grammar),
        ("tel_modern", cmd_tel_modern),("tel_eval",   cmd_tel_eval),
        ("tel_pyq",    cmd_tel_pyq),
        # Books
        ("ncert",      cmd_ncert),     ("book",       cmd_book),
        ("source",     cmd_source),
        # Interview
        ("daf",        cmd_daf),       ("mock_iq",    cmd_mock_iq),
        # Mobile
        ("practice",   cmd_practice),  ("podcast",    cmd_podcast),
        ("insights",   cmd_insights),  ("phone",      cmd_phone),
        ("files",      cmd_files),     ("raw",        cmd_raw),
        ("snapshot",   cmd_snapshot),
        # System
        ("sync",       cmd_sync),      ("compare",    cmd_compare),
        ("feedback",   cmd_feedback),  ("backup",     cmd_backup),
        ("eval_log",   cmd_eval_log),
        ("mastery",    cmd_mastery),  ("mastery_update", cmd_mastery_update),
    ]

    for name, handler in commands:
        app.add_handler(CommandHandler(name, handler))
    app.add_handler(CallbackQueryHandler(handle_quiz_callback, pattern=r"^quiz_ans:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    def _shutdown(sig, frame):
        log.info(f"Signal {sig} — shutting down.")
        app.stop_running()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT,  _shutdown)

    log.info(f"🧠 HERMES {HERMES_VERSION} — {len(commands)} commands — polling started")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()


# ================================================================
# SYSTEMD SERVICE — /etc/systemd/system/hermes-bot.service
# ================================================================
# [Unit]
# Description=Hermes UPSC Full Bot (Groq — Free)
# After=network-online.target
# Wants=network-online.target
#
# [Service]
# Type=simple
# User=YOUR_USERNAME
# WorkingDirectory=/home/YOUR_USERNAME/bots
# EnvironmentFile=/home/YOUR_USERNAME/bots/.env_hermes
# ExecStart=/usr/bin/python3 /home/YOUR_USERNAME/bots/hermes_full.py
# Restart=always
# RestartSec=10
# StandardOutput=journal
# StandardError=journal
#
# [Install]
# WantedBy=multi-user.target
# ================================================================


**Workaround:** I’m giving you a **repo‑ready document** + a **recommended repo structure** + **exact code blocks** to paste into `hermes_full.py`.

---

# ✅ COPY‑PASTE DOC (Put this in your repo)

> Save as: `docs/HERMES_V1_5_ROCK_SOLID_PLAN.md` (or just `HERMES_V1_5_ROCK_SOLID_PLAN.md`)

```md
# HERMES V1.5 — Rock‑Solid Stateful Mentor Upgrade
Author: Gad (Sai Harsha Gadde) + Copilot
Goal: Upgrade Hermes from “one‑shot tutor” → “true multi‑turn mentor loop”.

---

## 0) What This Upgrade Fixes (Non‑Negotiable)

### Before
Hermes asked MCQ → you reply “B” → free‑text handler treats it like normal chat.
Result: fragile behaviour, inconsistent grading, “theatre” multi‑turn flows.

### After (V1.5)
Hermes asks MCQ with **hidden answer key stored in session**.
You reply “B” → Hermes grades **deterministically** (no guessing), logs result, explains trap, generates follow‑up MCQ on same concept.

✅ Adds real state for:
- `/quiz` (deterministic grading)
- `/socratic` (depth tracking and continuation)

---

## 1) Installation / Ops Notes (Do this now)

### 1.1 Add to `.gitignore`
Never commit secrets or DB backups:
```
.env*
*.db
.backups/
__pycache__/
*.pyc
```

### 1.2 Use `.env_hermes`
Keep tokens out of shell history:
```
HERMES_BOT_TOKEN=...
GROQ_API_KEY=...
TELEGRAM_USER_ID=...
DATABRICKS_HOST=...
DATABRICKS_TOKEN=...
DATABRICKS_SQL_WAREHOUSE_ID=...
HERMES_DB=/home/<user>/UPSC_2026/.hermes_memory.db
```

---

## 2) Rock‑Solid Design (How Hermes will behave)

### 2.1 Session State Model
Stored in `ctx.user_data["_session"]`:
- mode: `quiz` or `socratic`
- data: question text, hidden answer key, concept, attempts, timestamps

Sessions auto‑expire after 45 min (TTL).

### 2.2 Deterministic Quiz Grading
Quiz generation returns:
- `[USER]` block → shown to Telegram
- `[KEY]` JSON → stored in session only

Grading compares your answer against `KEY.correct_option` directly.

---

## 3) CODE PATCH — Paste These Blocks

> You will paste 6 blocks into `hermes_full.py`:
1) Session + parsing helpers  
2) Quiz generation helper (hidden key)  
3) Replace `cmd_quiz()`  
4) Replace `cmd_socratic()`  
5) Replace `handle_message()`  
6) Fix known interpolation bugs + safer cancel

---

# 3.1 BLOCK 1 — Session + Quiz Parsing Helpers
Paste below your HELPERS section (after `thinking()`), before commands.

```python
# ================================================================
# SESSION + QUIZ PARSING HELPERS
# ================================================================

SESSION_TTL_SECONDS = 45 * 60  # 45 minutes


def set_session(ctx, mode: str, data: dict):
    ctx.user_data["_session"] = {
        "mode": mode,
        "data": data,
        "updated_at": datetime.utcnow().isoformat()
    }


def clear_session(ctx):
    ctx.user_data.pop("_session", None)


def get_session(ctx):
    session = ctx.user_data.get("_session")
    if not session:
        return None

    try:
        updated_at = datetime.fromisoformat(session.get("updated_at", ""))
    except Exception:
        clear_session(ctx)
        return None

    age = (datetime.utcnow() - updated_at).total_seconds()
    if age > SESSION_TTL_SECONDS:
        clear_session(ctx)
        return None

    return session


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


def extract_tagged_block(text: str, tag: str) -> str:
    """
    Extract content from:
      [TAG]
      ...
      [/TAG]
    """
    pattern = rf"\.*?\[/{tag}\]"
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
    except Exception as e:
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
```

---

# 3.2 BLOCK 2 — Quiz Generator with Hidden Key
Paste below Block 1.

```python
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
```

---

# 3.3 BLOCK 3 — Replace cmd_quiz()
Replace your existing `cmd_quiz()` with:

```python
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
        "concept": key.get("concept", subject or subject or "General"),
        "question_text": public_text,
        "answer_key": key,
        "attempts": 0,
        "started_at": datetime.utcnow().isoformat()
    })

    await send_long(update, public_text)
```

---

# 3.4 BLOCK 4 — Replace cmd_socratic()
Replace your existing `cmd_socratic()` with:

```python
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
```

---

# 3.5 BLOCK 5 — Replace handle_message()
Replace your existing `handle_message()` with:

```python
async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update):
        return

    user_msg = update.message.text
    if not user_msg:
        return

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

        await send_long(update, feedback + "\n\nFOLLOW-UP:\n" + followup_public)
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
```

---

# 3.6 BLOCK 6 — Fix Interpolation Bugs + Safer Cancel

## 6.1 Replace cmd_cancel()
```python
async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update):
        return
    clear_session(ctx)
    await update.message.reply_text("✅ Active session cleared. What next?")
```

## 6.2 Fix cmd_eod() bug (weekly_hours)
```python
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
```

## 6.3 Fix cmd_recall() and cmd_progress() {topic} literals
Inside each prompt, ensure f-strings are used for lines containing {topic}.
Example for recall:
```python
prompt = (
    f"ACTIVE RECALL: {topic}\n\n"
    "Do NOT teach. Make Gad produce.\n\n"
    f"Step 1: Ask him to write everything he knows about {topic} in 3 sentences.\n"
    "Tell him: 'Don't look anything up. Write from memory.'\n"
    "Then grade and ask ONE follow-up."
)
```

Example for progress:
```python
prompt = (
    f"PROGRESSIVE RECALL: {topic}\n\n"
    "Start ONLY with Level 1.\n"
    f"LEVEL 1 — List 3 facts about {topic}.\n"
    "..."
)
```

---

## 4) Smoke Test Checklist (Run after patch)

1) `/quiz polity` → Hermes sends MCQ  
2) Reply `B` → Hermes grades (correct/incorrect), explains trap, gives rule, sends follow‑up MCQ  
3) Reply `A` → repeats reliably  
4) `/socratic federalism` → Hermes asks ONE question  
5) Answer → Hermes evaluates and asks ONE deeper or simpler question  
6) `/cancel` → session clears  
7) Free typing works as normal Hermes

---

## 5) Next Upgrades (V1.6 Roadmap)

Apply the same “hidden key + session” pattern to:
- `/drill` (3 questions + per-question key + graded after 3 replies)
- `/daf` (store question, then evaluate when you answer)
- `/mock_iq` (store 5 questions, then grade sequentially)
- `/recall` and `/progress` (multi-step rubric state machine)

---

# END
```

---

# ✅ Repo integration recommendations (even without browsing your repo)

Since I can’t open the repo content from here, here’s the **best-practice structure** for an UPSC + bot repo:

```
UPSC_2027/
  bots/
    hermes_full.py
    requirements.txt
    systemd/
      hermes-bot.service
  docs/
    HERMES_V1_5_ROCK_SOLID_PLAN.md
    STUDY_OS_PLAYBOOK.md
  upsc/
    syllabus/
    gs/
    optional_telugu/
    pyq/
    notes/
  data/
    (keep empty; ignore in git)
  .gitignore
  README.md
```

---

# ✅ Now the “edge among others”: what you should do next (study + practice system)

You asked for the real “brownie marks” edge — here is the **exact operating system** to beat average aspirants:

## 1) Your weekly loop (non-negotiable)
### **Mon–Fri (3.5h/day)**
- **60 min**: GS core concept (Laxmikanth/Spectrum/Geo/Eco)
- **45 min**: CA integration (your Databricks CA pipeline + `/daily` or `/snapshot`)
- **45 min**: Prelims MCQ loop (**Hermes `/quiz` session: 10 questions/day**)  
- **30 min**: Mains answer writing (**1 answer/day, `/evaluate`**)  
- **30 min**: Telugu optional (alternating Paper VI/VII)

### **Sat (7.5h)**
- **3h**: Full-length sectional test (Prelims or Mains)
- **2h**: Review mistakes → log into Hermes (`/trap`, `/weak`)
- **1.5h**: Telugu optional writing practice
- **1h**: Essay framework or ethics caselets

### **Sun (7.5h)**
- **2h**: Weekly consolidation notes (1-page per topic)
- **2h**: PYQ mapping: topic → how UPSC frames it
- **2h**: Mock interview / DAF style Qs
- **1.5h**: “Weak topics only” targeted revision

**Edge:** Most people “study”. You will **close loops**: test → error → log → fix → retest.

---

## 2) The “3 dashboards” that create rank jumps

### Dashboard A — **Weakness Heatmap**
From Hermes DB:
- top 10 weak topics
- miss count trend
- trap categories

**Rule:** If something stays in top 5 for >2 weeks → you’re not revising correctly.

### Dashboard B — **Answer Writing Score Trend**
From `/evaluate` history:
- average score per week
- repeated flaws

**Rule:** Fix ONE writing flaw per week (not ten).

### Dashboard C — **Mastery Tracker**
From your Databricks mastery table:
- due reviews
- not started high yield topics

**Rule:** every Sunday: clear due reviews first.

---

## 3) The “Topper behaviour” edge (what others don’t do)
### A) Turn every mistake into an asset
Each wrong MCQ → you should log:
- trap type
- why you chose wrong
- one-line rule

Hermes already supports this. Your new session quiz makes it *automatic and consistent*.

### B) 2-layer notes only
- **Layer 1**: 1-page revision capsule per topic
- **Layer 2**: PYQ framing patterns + examples

No long notes. UPSC punishes bulk, rewards recall and structure.

### C) 15-mark answer templates
For GS2, GS3, Ethics:
- intro formula
- 5 body points
- 2 examples
- conclusion formula

Do it once → reuse forever.

---

## 4) How to use Hermes to dominate (practical command plan)

### Daily minimum commands
- `/log <what you studied>` (forces accountability)
- `/quiz <topic>` × 10 (session loop)
- `/trap <wrong question>` (only on wrong)
- `/evaluate <1 mains answer>`
- `/telugu <topic or daily>`

### Weekly commands
- `/weak` on Sunday
- `/compare` if you use both bots
- `/snapshot` daily CA at least 4×/week

---

# If you want the next best “V1.6 edge” patch
I can produce the same **hidden-key + session** upgrade for:
- `/drill` (3 MCQs stored, then grade after 3 answers)
- `/daf` (store chairman question → grade your response)
- `/mock_iq` (store 5 questions → grade one by one)

That would make Hermes a **full coaching loop**, not just quiz/socratic.

---

## One quick question (only if you want repo-specific tailoring)
Since I can’t access the repo contents here:  
**Which file is the main entrypoint in your repo right now — is it `bots/hermes_full.py` or something else?**ADME.md
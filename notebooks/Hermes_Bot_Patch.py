# Databricks notebook source
# Read the full file
with open("/Workspace/Users/admin@mngenvmcap915189.onmicrosoft.com/Drafts/hermes_full.py", "r") as f:
    content = f.read()

lines = content.split("\n")
print(f"Total lines: {len(lines)}")

# Find key line numbers for surgical patching
for i, line in enumerate(lines, 1):
    if "import signal" in line and "from" not in line:
        print(f"Line {i}: {line}")
    if "GROQ_TEMPERATURE" in line:
        print(f"Line {i}: {line}")
    if "def get_memory_context" in line:
        print(f"Line {i}: {line}")
    if "return .\\n..join(parts)" in line or ('return "\\n".join(parts)' in line):
        print(f"Line {i}: {line}")
    if "def cmd_weak" in line:
        print(f"Line {i}: {line}")
    if "def cmd_stats" in line:
        print(f"Line {i}: {line}")
    if '"eval_log"' in line:
        print(f"Line {i}: {line}")
    if "except Exception as e:" in line and i > 470 and i < 478:
        print(f"Line {i}: {line}")

# COMMAND ----------

# DBTITLE 1,Patch hermes_full.py — bugs + mastery_tracker
file_path = "/Workspace/Users/admin@mngenvmcap915189.onmicrosoft.com/Drafts/hermes_full.py"

with open(file_path, "r") as f:
    lines = f.readlines()

print(f"Original: {len(lines)} lines")
changes = []

# ============================================================
# FIX 1: Add 'import subprocess' after 'import signal'
# ============================================================
for i in range(len(lines)):
    if lines[i].strip() == 'import signal':
        lines.insert(i + 1, 'import subprocess\n')
        changes.append(f"FIX 1: import subprocess after line {i+1}")
        break

# ============================================================
# FIX 2: Temperature 0.65 -> 0.35
# ============================================================
for i in range(len(lines)):
    if 'GROQ_TEMPERATURE' in lines[i] and '0.65' in lines[i]:
        lines[i] = lines[i].replace('0.65', '0.35')
        changes.append(f"FIX 2: temp 0.65->0.35 at line {i+1}")
        break

# ============================================================
# FIX 3: Groq rate limit retry
# Find 'except Exception as e:' near call_hermes (around line 472)
# ============================================================
for i in range(len(lines)):
    if 'except Exception as e:' in lines[i] and i > 460 and i < 500:
        # Check next line has 'latency'
        if i + 1 < len(lines) and 'latency' in lines[i + 1]:
            # Replace 3 lines (except + latency + log.error + return)
            old_end = i + 4  # approximate end of block
            for j in range(i + 1, min(i + 6, len(lines))):
                if 'return f' in lines[j] and 'Hermes error' in lines[j]:
                    old_end = j + 1
                    break
            retry_block = [
                '    except Exception as e:\n',
                '        err_str = str(e)\n',
                '        if "rate_limit" in err_str.lower() or "too many" in err_str.lower():\n',
                '            log.warning("Groq rate limit hit, retrying in 10s...")\n',
                '            time.sleep(10)\n',
                '            try:\n',
                '                resp = groq_client.chat.completions.create(\n',
                '                    model=GROQ_MODEL,\n',
                '                    messages=[{"role": "system", "content": system},\n',
                '                              {"role": "user", "content": user_message}],\n',
                '                    max_tokens=GROQ_MAX_TOKENS, temperature=GROQ_TEMPERATURE)\n',
                '                latency = int((time.time() - t0) * 1000)\n',
                '                text = resp.choices[0].message.content or "(empty)"\n',
                '                tokens = resp.usage.total_tokens if resp.usage else 0\n',
                '                return text, tokens, latency\n',
                '            except Exception as e2:\n',
                '                log.error(f"Groq retry failed: {e2}")\n',
                '        latency = int((time.time() - t0) * 1000)\n',
                '        log.error(f"Groq error: {e}")\n',
                '        return f"Hermes error: {str(e)[:300]}", 0, latency\n',
            ]
            lines[i:old_end] = retry_block
            changes.append(f"FIX 3: rate limit retry at line {i+1}")
        break

# ============================================================
# FIX 4: Add mastery_tracker to get_memory_context()
# Find the return line inside get_memory_context
# ============================================================
for i in range(len(lines)):
    if 'join(parts)' in lines[i] and 'first session' in lines[i]:
        mastery_lines = [
            '    # === MASTERY TRACKER (Databricks Delta) ===\n',
            '    try:\n',
            '        mastery_rows = run_sql(\n',
            '            "SELECT paper, COUNT(*) as total, "\n',
            '            "SUM(CASE WHEN status=\'mastered\' THEN 1 ELSE 0 END) as mastered, "\n',
            '            "SUM(CASE WHEN status=\'in_progress\' THEN 1 ELSE 0 END) as active, "\n',
            '            "SUM(CASE WHEN status=\'needs_work\' THEN 1 ELSE 0 END) as weak, "\n',
            '            "ROUND(AVG(mastery_pct),0) as avg_pct "\n',
            '            "FROM upsc_catalog.rag.mastery_tracker GROUP BY paper ORDER BY paper")\n',
            '        if mastery_rows:\n',
            '            parts.append("SYLLABUS MASTERY (250 topics):")\n',
            '            total_m = sum(int(r.get("mastered", 0)) for r in mastery_rows)\n',
            '            total_t = sum(int(r.get("total", 0)) for r in mastery_rows)\n',
            '            for r in mastery_rows:\n',
            '                p, avg = r.get("paper", "?"), float(r.get("avg_pct", 0))\n',
            '                m, a, w = int(r.get("mastered",0)), int(r.get("active",0)), int(r.get("weak",0))\n',
            '                parts.append(f"  {p}: {avg:.0f}% | {m}M {a}A {w}W")\n',
            '            pct = (total_m / total_t * 100) if total_t > 0 else 0\n',
            '            parts.append(f"  OVERALL: {total_m}/{total_t} mastered ({pct:.1f}%)")\n',
            '        weak_m = run_sql(\n',
            '            "SELECT topic_id, topic_name, paper, mastery_pct "\n',
            '            "FROM upsc_catalog.rag.mastery_tracker "\n',
            '            "WHERE status IN (\'not_started\',\'needs_work\') "\n',
            '            "ORDER BY mastery_pct ASC, last_studied ASC NULLS FIRST LIMIT 5")\n',
            '        if weak_m:\n',
            '            parts.append("WEAKEST SYLLABUS TOPICS:")\n',
            '            for r in weak_m:\n',
            '                tid, tn, pp = r["topic_id"], r["topic_name"], r["paper"]\n',
            '                mp = float(r.get("mastery_pct", 0))\n',
            '                parts.append(f"  {tid} {tn} [{pp}] {mp:.0f}%")\n',
            '        due = run_sql(\n',
            '            "SELECT topic_id, topic_name FROM upsc_catalog.rag.mastery_tracker "\n',
            '            "WHERE next_review <= current_date() AND status != \'mastered\' "\n',
            '            "ORDER BY next_review ASC LIMIT 3")\n',
            '        if due:\n',
            '            parts.append("DUE FOR REVIEW:")\n',
            '            for r in due:\n',
            '                parts.append(f"  {r[\'topic_id\']} {r[\'topic_name\']}")\n',
            '    except Exception as e:\n',
            '        log.warning(f"mastery_tracker query failed: {e}")\n',
            '\n',
        ]
        for idx, ml in enumerate(mastery_lines):
            lines.insert(i + idx, ml)
        changes.append(f"FIX 4: mastery_tracker in get_memory_context() at line {i+1}")
        break

print(f"After fixes 1-4: {len(lines)} lines")
for c in changes:
    print(f"  {c}")

with open(file_path, "w") as f:
    f.writelines(lines)
print("\nFile saved. Fixes 1-4 applied.")
print("\nFix 5 (mastery commands) and Fix 6 (registration) will be in next cell.")

# COMMAND ----------

# DBTITLE 1,Fix 5-6: Add /mastery + /mastery_update commands
file_path = "/Workspace/Users/admin@mngenvmcap915189.onmicrosoft.com/Drafts/hermes_full.py"

with open(file_path, "r") as f:
    lines = f.readlines()

print(f"Starting: {len(lines)} lines")

# ============================================================
# FIX 5: Add /mastery and /mastery_update commands
# Insert before the MAIN section (look for '# MAIN' with ====)
# ============================================================

# Write mastery commands to a temp file first, then read as lines
mastery_code = r'''
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

'''

# Find the MAIN section
insert_at = None
for i in range(len(lines)):
    if '# MAIN' in lines[i] and '====' in lines[i] and i > 1900:
        insert_at = i
        break

if insert_at is None:
    # Fallback: find 'def main():'
    for i in range(len(lines)):
        if lines[i].strip() == 'def main():':
            insert_at = i - 2  # go above the def
            break

if insert_at:
    mastery_lines = mastery_code.split('\n')
    new_lines = [ml + '\n' for ml in mastery_lines]
    lines[insert_at:insert_at] = new_lines
    print(f"FIX 5: Added /mastery + /mastery_update ({len(new_lines)} lines) before line {insert_at+1}")
else:
    print("FIX 5: ERROR - could not find insertion point")

# ============================================================
# FIX 6: Register commands in the commands list
# Find 'eval_log' registration line
# ============================================================
for i in range(len(lines)):
    if '"eval_log"' in lines[i] and 'cmd_eval_log' in lines[i]:
        lines.insert(i + 1, '        ("mastery",    cmd_mastery),  ("mastery_update", cmd_mastery_update),\n')
        print(f"FIX 6: Registered /mastery + /mastery_update at line {i+2}")
        break

# ============================================================
# WRITE
# ============================================================
with open(file_path, "w") as f:
    f.writelines(lines)

print(f"\nFinal: {len(lines)} lines")

# Verify all patches
with open(file_path, "r") as f:
    final = f.read()

checks = [
    ("import subprocess", "import subprocess"),
    ("GROQ_TEMPERATURE = 0.35", "temperature 0.35"),
    ("rate_limit", "rate limit retry"),
    ("SYLLABUS MASTERY", "mastery_tracker in memory context"),
    ("cmd_mastery", "/mastery command defined"),
    ("cmd_mastery_update", "/mastery_update command defined"),
    ('"mastery"', "/mastery registered"),
]

print("\n--- VERIFICATION ---")
for pattern, label in checks:
    found = pattern in final
    print(f"  {'\u2705' if found else '\u274c'} {label}")

# Count total commands registered
import re
cmd_count = len(re.findall(r'CommandHandler\(', final))
print(f"\n  Total commands registered: {cmd_count}")
print(f"  Total file size: {len(final):,} chars")

# COMMAND ----------

# DBTITLE 1,Verify syntax + command count
import re
file_path = "/Workspace/Users/admin@mngenvmcap915189.onmicrosoft.com/Drafts/hermes_full.py"

with open(file_path, "r") as f:
    content = f.read()
    lines = content.split('\n')

# Syntax check
try:
    compile(content, file_path, "exec")
    print("\u2705 Python syntax OK")
except SyntaxError as e:
    print(f"\u274c Syntax error at line {e.lineno}: {e.msg}")
    if e.lineno:
        start = max(0, e.lineno - 3)
        for j in range(start, min(e.lineno + 2, len(lines))):
            marker = ">>>" if j == e.lineno - 1 else "   "
            print(f"  {marker} {j+1}: {lines[j]}")

# Count command tuples
cmd_count = len(re.findall(r'\("\w+"\s*,\s*cmd_\w+\)', content))
print(f"\nRegistered commands: {cmd_count}")

# Check mastery entries
for i, line in enumerate(lines):
    if '"mastery"' in line and 'cmd_mastery' in line:
        print(f"  Line {i+1}: {line.strip()}")

# COMMAND ----------

with open("/Workspace/Users/admin@mngenvmcap915189.onmicrosoft.com/Drafts/hermes_full.py", "r") as f:
    content = f.read()

# ============================================================
# FIX 1: Add import subprocess after import signal (line 50)
# ============================================================
content = content.replace(
    "import signal\nimport sqlite3",
    "import signal\nimport subprocess\nimport sqlite3"
)

# ============================================================
# FIX 2: Temperature 0.65 → 0.35 for factual accuracy
# ============================================================
content = content.replace(
    "GROQ_TEMPERATURE = 0.65",
    "GROQ_TEMPERATURE = 0.35"
)

# ============================================================
# FIX 3: Add Groq rate limit retry in call_hermes()
# ============================================================
old_call = '''    t0 = time.time()
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
        latency = int((time.time() - t0) * 1000)
        log.error(f"Groq error: {e}")
        return f"Hermes error: {str(e)[:300]}", 0, latency'''

new_call = '''    t0 = time.time()
    last_err = None
    for attempt in range(3):
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
            last_err = e
            err_str = str(e).lower()
            if "rate_limit" in err_str or "429" in err_str:
                wait = (attempt + 1) * 5
                log.warning(f"Groq rate limit — retry {attempt+1}/3 in {wait}s")
                time.sleep(wait)
                continue
            latency = int((time.time() - t0) * 1000)
            log.error(f"Groq error: {e}")
            return f"Hermes error: {str(e)[:300]}", 0, latency
    latency = int((time.time() - t0) * 1000)
    log.error(f"Groq failed after 3 retries: {last_err}")
    return f"Hermes rate limited — try again in 30s. Error: {str(last_err)[:200]}", 0, latency'''

content = content.replace(old_call, new_call)

# ============================================================
# FIX 4: Add mastery_tracker to get_memory_context()
# ============================================================
old_memory_end = '''    row = _db_fetchone(
        "SELECT COUNT(*) FROM hermes_interactions WHERE date(timestamp)=date('now')")
    parts.append(f"Hermes calls today: {(row or (0,))[0]}")

    return "\\n".join(parts) if parts else "No history yet — first session."'''

new_memory_end = '''    row = _db_fetchone(
        "SELECT COUNT(*) FROM hermes_interactions WHERE date(timestamp)=date('now')")
    parts.append(f"Hermes calls today: {(row or (0,))[0]}")

    # Mastery tracker from Databricks Delta table
    mastery = run_sql(
        "SELECT paper, COUNT(*) as total, "
        "SUM(CASE WHEN status='mastered' THEN 1 ELSE 0 END) as mastered, "
        "ROUND(AVG(mastery_pct),0) as avg "
        "FROM upsc_catalog.rag.mastery_tracker GROUP BY paper ORDER BY paper")
    if mastery:
        parts.append("MASTERY TRACKER (Databricks):")
        for row in mastery:
            parts.append(f"  {row['paper']}: {row['avg']}% avg ({row['mastered']}/{row['total']} mastered)")

    due_reviews = run_sql(
        "SELECT topic_id, topic_name, mastery_pct FROM upsc_catalog.rag.mastery_tracker "
        "WHERE next_review <= current_date() AND status != 'mastered' "
        "ORDER BY mastery_pct ASC LIMIT 5")
    if due_reviews:
        parts.append("DUE FOR REVIEW TODAY:")
        for r in due_reviews:
            parts.append(f"  {r['topic_id']} {r['topic_name']} ({r['mastery_pct']}%)")

    return "\\n".join(parts) if parts else "No history yet — first session."'''

content = content.replace(old_memory_end, new_memory_end)

# ============================================================
# FIX 5: Enhanced /weak command with mastery_tracker
# ============================================================
old_weak = '''async def cmd_weak(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    topics = _db_fetch(
        "SELECT subject,topic,miss_count,last_reviewed "
        "FROM weak_topics ORDER BY miss_count DESC LIMIT 10")
    if not topics:
        await update.message.reply_text("No weak topics yet. Use /quiz!"); return
    topic_list = "\\n".join(f"  [{s}] {t} — missed {m}x" for s,t,m,_ in topics)
    prompt = (
        f"My weakest topics:\\n{topic_list}\\n\\n"
        "As Hermes:\\n"
        "1. Which ONE do I tackle today? (give clear reason)\\n"
        "2. Exact 20-minute revision plan for it\\n"
        "3. One Prelims Q and one Mains Q from this topic\\n"
        "4. Root cause: WHY am I repeatedly missing this?"
    )
    await thinking(update, "⚠️ Hermes analyzing weak topics...")
    mem = get_memory_context()
    resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)
    log_hermes("/weak", "weak-analysis", resp, tok, lat)
    raw = f"⚠️ Weak Topics\\n{DIVIDER}\\n{topic_list}"
    await send_long(update, raw)
    await send_long(update, f"🧠 Hermes Study Plan:\\n\\n{resp}")'''

new_weak = '''async def cmd_weak(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update): return
    # Local SQLite weak topics
    topics = _db_fetch(
        "SELECT subject,topic,miss_count,last_reviewed "
        "FROM weak_topics ORDER BY miss_count DESC LIMIT 10")
    topic_list = "\\n".join(f"  [{s}] {t} — missed {m}x" for s,t,m,_ in topics) if topics else ""

    # Databricks mastery_tracker weak topics
    mastery_weak = run_sql(
        "SELECT topic_id, topic_name, paper, mastery_pct, last_studied "
        "FROM upsc_catalog.rag.mastery_tracker "
        "WHERE status IN ('needs_work', 'not_started') "
        "OR (status = 'in_progress' AND next_review <= current_date()) "
        "ORDER BY mastery_pct ASC, last_studied ASC NULLS FIRST LIMIT 10")
    mastery_list = ""
    if mastery_weak:
        mastery_list = "\\n".join(
            f"  {r['topic_id']} [{r['paper']}] {r['topic_name']} — {r['mastery_pct']}%"
            f" (last: {r['last_studied'] or 'never'})"
            for r in mastery_weak)

    if not topics and not mastery_weak:
        await update.message.reply_text("No weak topics yet. Use /quiz!"); return

    combined = ""
    if topic_list:
        combined += f"SQLite (quiz/eval misses):\\n{topic_list}\\n\\n"
    if mastery_list:
        combined += f"Mastery Tracker (syllabus progress):\\n{mastery_list}"

    prompt = (
        f"My weakest topics:\\n{combined}\\n\\n"
        "As Hermes:\\n"
        "1. Which ONE do I tackle today? (give clear reason)\\n"
        "2. Exact 20-minute revision plan for it\\n"
        "3. One Prelims Q and one Mains Q from this topic\\n"
        "4. Root cause: WHY am I repeatedly missing this?"
    )
    await thinking(update, "⚠️ Hermes analyzing weak topics...")
    mem = get_memory_context()
    resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)
    log_hermes("/weak", "weak-analysis", resp, tok, lat)
    raw = f"⚠️ Weak Topics\\n{DIVIDER}\\n{combined}"
    await send_long(update, raw)
    await send_long(update, f"🧠 Hermes Study Plan:\\n\\n{resp}")'''

content = content.replace(old_weak, new_weak)

# ============================================================
# FIX 6: Add /mastery command before FREE TEXT HANDLER
# ============================================================
mastery_cmd = '''

async def cmd_mastery(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show mastery dashboard from Databricks Delta table."""
    if not check_auth(update): return
    await thinking(update, "📊 Querying mastery tracker...")
    paper_filter = " ".join(ctx.args).upper() if ctx.args else ""

    # Overall stats
    summary = run_sql(
        "SELECT paper, COUNT(*) as total, "
        "SUM(CASE WHEN status='mastered' THEN 1 ELSE 0 END) as mastered, "
        "SUM(CASE WHEN status='in_progress' THEN 1 ELSE 0 END) as active, "
        "SUM(CASE WHEN status='needs_work' THEN 1 ELSE 0 END) as needs_work, "
        "SUM(CASE WHEN status='not_started' THEN 1 ELSE 0 END) as not_started, "
        "ROUND(AVG(mastery_pct),0) as avg_mastery "
        "FROM upsc_catalog.rag.mastery_tracker GROUP BY paper ORDER BY paper")

    if not summary:
        await update.message.reply_text("❌ Could not query mastery_tracker. Check SQL warehouse."); return

    msg = f"📊 MASTERY DASHBOARD\\n{DIVIDER_WIDE}\\n\\n"
    total_topics = 0
    total_mastered = 0
    for r in summary:
        total_topics += int(r['total'])
        total_mastered += int(r['mastered'])
        emoji = "🟢" if float(r['avg_mastery']) >= 70 else "🟡" if float(r['avg_mastery']) >= 30 else "🔴"
        msg += (f"{emoji} {r['paper']:10} | {r['avg_mastery']}% avg | "
                f"✅{r['mastered']} 🔵{r['active']} 🔴{r['needs_work']} ⚪{r['not_started']}\\n")

    pct_done = round(total_mastered / total_topics * 100, 1) if total_topics else 0
    msg += f"\\n{DIVIDER}\\n"
    msg += f"Total: {total_mastered}/{total_topics} mastered ({pct_done}%)\\n"

    # Due for review
    due = run_sql(
        "SELECT topic_id, topic_name, mastery_pct FROM upsc_catalog.rag.mastery_tracker "
        "WHERE next_review <= current_date() AND status != 'mastered' "
        "ORDER BY mastery_pct ASC LIMIT 5")
    if due:
        msg += f"\\n📅 DUE FOR REVIEW:\\n"
        for r in due:
            msg += f"  {r['topic_id']} {r['topic_name']} ({r['mastery_pct']}%)\\n"

    # Paper detail if requested
    if paper_filter:
        detail = run_sql(
            f"SELECT topic_id, topic_name, mastery_pct, status, priority "
            f"FROM upsc_catalog.rag.mastery_tracker "
            f"WHERE paper = '{paper_filter}' ORDER BY mastery_pct DESC")
        if detail:
            msg += f"\\n📋 {paper_filter} DETAIL:\\n"
            for r in detail:
                s = {"mastered":"✅","in_progress":"🔵","needs_work":"🔴","not_started":"⚪"}.get(r['status'],"?")
                hy = " ⭐" if r.get('priority') == 'HIGH_YIELD' else ""
                msg += f"  {s} {r['topic_id']} {r['topic_name']} — {r['mastery_pct']}%{hy}\\n"

    await send_long(update, msg)
    log_hermes("/mastery", paper_filter or "overview", msg[:200])


'''

# Insert before the FREE TEXT HANDLER section
content = content.replace(
    "# ================================================================\n# FREE TEXT HANDLER",
    mastery_cmd + "# ================================================================\n# FREE TEXT HANDLER"
)

# ============================================================
# FIX 7: Register /mastery in command list
# ============================================================
content = content.replace(
    '        ("eval_log",   cmd_eval_log),\n    ]',
    '        ("eval_log",   cmd_eval_log),\n        ("mastery",    cmd_mastery),\n    ]'
)

# ============================================================
# FIX 8: Add /mastery to /start help text
# ============================================================
content = content.replace(
    '        "SYSTEM:\\n"\n        "  /sync /compare /feedback /backup /cancel /help\\n\\n"',
    '        "MASTERY TRACKER:\\n"\n        "  /mastery [paper] — syllabus progress from Databricks\\n\\n"\n        "SYSTEM:\\n"\n        "  /sync /compare /feedback /backup /cancel /help\\n\\n"'
)

# Write back
with open("/Workspace/Users/admin@mngenvmcap915189.onmicrosoft.com/Drafts/hermes_full.py", "w") as f:
    f.write(content)

# Verify
lines = content.split("\n")
print(f"✅ File written: {len(lines)} lines, {len(content)} chars")

# Verify patches applied
checks = [
    ("import subprocess", "subprocess import"),
    ("GROQ_TEMPERATURE = 0.35", "temperature fix"),
    ("rate_limit", "rate limit retry"),
    ("mastery_tracker", "mastery_tracker integration"),
    ("cmd_mastery", "/mastery command"),
    ("MASTERY TRACKER:", "/mastery in help"),
]
for pattern, name in checks:
    if pattern in content:
        print(f"  ✅ {name}")
    else:
        print(f"  ❌ {name} — NOT FOUND")

# COMMAND ----------

file_path = "/Workspace/Users/admin@mngenvmcap915189.onmicrosoft.com/Drafts/hermes_full.py"

with open(file_path, "r") as f:
    lines = f.readlines()

# Count command registrations (tuples in commands list)
import re
cmd_tuples = 0
in_commands_list = False
for line in lines:
    if 'commands = [' in line:
        in_commands_list = True
    if in_commands_list:
        cmd_tuples += len(re.findall(r'\("(\w+)"', line))
        if ']' in line and 'commands' not in line:
            in_commands_list = False

print(f"Total command registrations: {cmd_tuples}")
print(f"Total lines: {len(lines)}")

# Verify mastery commands are in the list
for i, line in enumerate(lines):
    if '"mastery"' in line:
        print(f"\nLine {i+1}: {line.rstrip()}")
    if '"mastery_update"' in line:
        print(f"Line {i+1}: {line.rstrip()}")

# Verify no syntax issues in key new functions
print("\n--- Key function definitions ---")
for i, line in enumerate(lines):
    if 'async def cmd_mastery' in line:
        print(f"Line {i+1}: {line.rstrip()}")
    if 'SECTION 10' in line:
        print(f"Line {i+1}: {line.rstrip()}")
    if 'SYLLABUS MASTERY' in line:
        print(f"Line {i+1}: {line.rstrip()}")

# Quick syntax check
print("\n--- Syntax check ---")
try:
    compile(open(file_path).read(), file_path, "exec")
    print("✅ Python syntax OK")
except SyntaxError as e:
    print(f"❌ Syntax error: {e}")

# COMMAND ----------

# Create secrets scope and store credentials
try:
    dbutils.secrets.createScope("upsc-bot-secrets")
    print("✅ Created scope: upsc-bot-secrets")
except Exception as e:
    if "already exists" in str(e).lower():
        print("ℹ️ Scope upsc-bot-secrets already exists")
    else:
        print(f"⚠️ Scope creation: {e}")

# Store Hermes bot credentials
secrets = {
    "hermes-bot-token": "8520202994:AAEoNCngmi7LdrMARnVLj6MkcVEd7cuERus",
    "groq-api-key": "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",
    "main-bot-token": "8788057001:AAEFvfaypZfw18wPJN94K2YPCbMpP6ttAWA",
    "telegram-user-id": "2022402970",
}

for key, val in secrets.items():
    try:
        dbutils.secrets.put("upsc-bot-secrets", key, val)
        print(f"✅ Stored: {key}")
    except Exception as e:
        print(f"⚠️ {key}: {e}")

# Verify
print("\n--- Verification ---")
for key in secrets:
    try:
        v = dbutils.secrets.get("upsc-bot-secrets", key)
        print(f"✅ {key}: {len(v)} chars (redacted)")
    except:
        print(f"❌ {key}: not found")

# COMMAND ----------

# DBTITLE 1,Store secrets via REST API
import requests, os

host = spark.conf.get("spark.databricks.workspaceUrl", "")
if not host.startswith("http"):
    host = f"https://{host}"
token = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# Create scope
r = requests.post(f"{host}/api/2.0/secrets/scopes/create", headers=headers,
                  json={"scope": "upsc-bot-secrets"})
if r.status_code == 200:
    print("\u2705 Created scope: upsc-bot-secrets")
elif "RESOURCE_ALREADY_EXISTS" in r.text:
    print("\u2139\ufe0f Scope already exists")
else:
    print(f"\u26a0\ufe0f Scope: {r.status_code} {r.text[:200]}")

# Store secrets
secrets = {
    "hermes-bot-token": "8520202994:AAEoNCngmi7LdrMARnVLj6MkcVEd7cuERus",
    "groq-api-key": "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",
    "main-bot-token": "8788057001:AAEFvfaypZfw18wPJN94K2YPCbMpP6ttAWA",
    "telegram-user-id": "2022402970",
}
for key, val in secrets.items():
    r = requests.post(f"{host}/api/2.0/secrets/put", headers=headers,
                      json={"scope": "upsc-bot-secrets", "key": key, "string_value": val})
    print(f"  {'\u2705' if r.status_code == 200 else '\u274c'} {key}: {r.status_code}")

# Verify
r = requests.get(f"{host}/api/2.0/secrets/list", headers=headers,
                 params={"scope": "upsc-bot-secrets"})
if r.status_code == 200:
    keys = [s["key"] for s in r.json().get("secrets", [])]
    print(f"\n\u2705 Stored {len(keys)} secrets: {', '.join(keys)}")

# COMMAND ----------

# DBTITLE 1,Test Groq API + Hermes bot token (no VM needed)
import requests, time

# === TEST 1: Groq API Key ===
print("=== TEST 1: Groq API ===")
GROQ_KEY = "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"

t0 = time.time()
r = requests.post(
    "https://api.groq.com/openai/v1/chat/completions",
    headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
    json={
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": "You are HERMES, a UPSC mentor. Be concise."},
            {"role": "user", "content": "In 3 bullet points, what are the key features of Article 21?"}
        ],
        "max_tokens": 300,
        "temperature": 0.35
    }
)
latency = time.time() - t0

if r.status_code == 200:
    data = r.json()
    text = data["choices"][0]["message"]["content"]
    tokens = data.get("usage", {}).get("total_tokens", 0)
    print(f"\u2705 Groq OK | {latency:.1f}s | {tokens} tokens")
    print(f"\nHermes says:\n{text}\n")
else:
    print(f"\u274c Groq failed: {r.status_code} {r.text[:300]}")

# === TEST 2: Hermes Telegram Bot Token ===
print("\n=== TEST 2: Hermes Bot ===")
HERMES_TOKEN = "8520202994:AAEoNCngmi7LdrMARnVLj6MkcVEd7cuERus"
me = requests.get(f"https://api.telegram.org/bot{HERMES_TOKEN}/getMe").json()
if me.get("ok"):
    bot = me["result"]
    print(f"\u2705 Bot: @{bot['username']} (ID: {bot['id']})")
else:
    print(f"\u274c Bot token invalid: {me}")

# === TEST 3: Mastery Tracker accessible ===
print("\n=== TEST 3: Mastery Tracker ===")
try:
    df = spark.sql("SELECT paper, COUNT(*) as cnt, ROUND(AVG(mastery_pct),1) as avg FROM upsc_catalog.rag.mastery_tracker GROUP BY paper ORDER BY paper")
    rows = df.collect()
    total = sum(r['cnt'] for r in rows)
    print(f"\u2705 mastery_tracker: {total} topics across {len(rows)} papers")
    for r in rows:
        print(f"  {r['paper']}: {r['cnt']} topics, {r['avg']}% avg")
except Exception as e:
    print(f"\u274c mastery_tracker: {e}")

print("\n=== ALL TESTS COMPLETE ===")

# COMMAND ----------

# DBTITLE 1,Force delete agent endpoint + model versions
import requests

host = f"https://{spark.conf.get('spark.databricks.workspaceUrl')}"
token = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# 1) DELETE serving endpoint
ep_name = "agents_upsc_catalog-rag-upsc_tutor_agent"
r = requests.delete(f"{host}/api/2.0/serving-endpoints/{ep_name}", headers=headers)
if r.status_code == 200:
    print(f"\u2705 Deleted endpoint: {ep_name}")
elif r.status_code == 404:
    print(f"\u2139\ufe0f Endpoint already deleted: {ep_name}")
else:
    print(f"\u26a0\ufe0f Endpoint delete: {r.status_code} {r.text[:200]}")

# 2) DELETE all 10 model versions
model_name = "upsc_catalog.rag.upsc_tutor_agent"
for v in range(1, 11):
    r = requests.post(f"{host}/api/2.0/mlflow/model-versions/delete", headers=headers,
                      json={"name": model_name, "version": str(v)})
    status = "\u2705" if r.status_code == 200 else "\u26a0\ufe0f" if r.status_code == 404 else "\u274c"
    print(f"  {status} Version {v}: {r.status_code}")

# 3) DELETE registered model
r = requests.post(f"{host}/api/2.0/mlflow/registered-models/delete", headers=headers,
                  json={"name": model_name})
if r.status_code == 200:
    print(f"\n\u2705 Deleted registered model: {model_name}")
elif r.status_code == 404:
    print(f"\n\u2139\ufe0f Model already deleted: {model_name}")
else:
    print(f"\n\u26a0\ufe0f Model delete: {r.status_code} {r.text[:200]}")

print("\n--- Done. Monthly savings: ~$55 ---")
# UPSC_2027 — Complete Deployment Guide
## Hermes V1.8: Stateful `/recall` and `/progress` ✅

> **Date:** 2026-04-09
> **Branch:** `copilot/update-documentation-for-project`
> **Status:** Ready to deploy — `hermes_full.py` updated

---

## 📋 SUMMARY OF CHANGES (V1.8)

### `bot_code/hermes_full.py` — Stateful `/recall` and `/progress`

**What changed:**
- `/recall <topic>` is now a **stateful 2-phase active recall loop**
  - Phase 1 (dump): Bot asks "write everything you know" — hidden `[KEY]` has 5 expected points + traps
  - User answers → graded (hits/misses/confidence gap/score) → targeted follow-up question on biggest gap
  - Phase 2 (followup): User answers follow-up → final score + revision tip → session clears
  - Session mode: `recall` | Phases: `dump` → `followup`
- `/progress <topic>` is now a **stateful Bloom's Taxonomy Levels 1-5 drill**
  - Level 1 (RECALL) → Level 2 (UNDERSTAND) → Level 3 (APPLY) → Level 4 (ANALYSE) → Level 5 (EVALUATE)
  - Each level generated with hidden `[KEY]` (key_points + pass_threshold)
  - Score ≥ threshold (default 6/10) → **PASS**, advance to next level
  - Score < threshold → **RETRY** (max 2 retries per level, then forced advance)
  - After Level 5: full journey summary `L1(8) → L2(7) → L3(9) → L4(7) → L5(8)` → session clears
  - Session mode: `progress`
- New helper functions:
  - `build_recall_question_prompt()` / `parse_recall_payload()` / `generate_recall_question()`
  - `build_recall_eval_prompt()` — grades brain dump, surfaces targeted follow-up
  - `build_progress_question_prompt()` / `parse_progress_payload()` / `generate_progress_question()`
  - `build_progress_eval_prompt()` — scores Bloom's level answer, emits VERDICT: PASS/RETRY
  - `_BLOOM_LEVEL_NAMES` / `_BLOOM_LEVEL_DESCS` — level metadata dicts
  - `build_interview_eval_prompt()` — per-question evaluation

**No other commands changed.**

---

## 🔧 DEPLOY STEPS

No Databricks changes required. Only `bot_code/hermes_full.py` changed.

On your Azure VM running Hermes:

```bash
# 1. Pull latest
cd ~/bots
git pull origin main

# 2. Restart Hermes (new DB table created automatically on startup)
sudo systemctl restart hermes-bot

# 3. Verify startup
sudo journalctl -u hermes-bot -n 30 --no-pager
# Should see: "Hermes DB ready" and "15 tables" (new: interview_history)
```

**Smoke test:**
```
/daf                         → board question appears (auto-angle)
/daf tech                    → board question, tech angle
<type answer>                → evaluation + Round 2 question appears
<type answer>                → evaluation + Round 3 question appears
<type answer>                → Round 3 evaluation + cumulative scores + session clears

/mock_iq                     → Q1 (Chairman) appears
<type answer>                → Q1 evaluation + Q2 (Senior IAS) appears
...                          → continues through Q5
<type answer for Q5>         → Q5 evaluation + final panel summary + session clears

/cancel                      → clears any running session mid-way
```

---

## Hermes Stateful Command Summary (as of V1.8)

| Command | Mode | Rounds | Auto-advance |
|---------|------|--------|--------------|
| `/quiz [topic]` | `quiz` | Infinite follow-up | Same concept follow-up MCQ |
| `/drill` | `drill` | 1 (3 MCQs) | Auto-cascade to weakest concept quiz |
| `/socratic [topic]` | `socratic` | Up to 4 depths | Deeper/simpler follow-up → conclusion |
| `/daf [angle]` | `daf` | 3 rounds | Next angle from `follow_up_angles` key |
| `/mock_iq` | `mock_iq` | 5 questions | Sequential Q1→Q5 with per-question grading |
| `/recall <topic>` | `recall` | 2 phases | Phase 1: dump → eval+follow-up → Phase 2: final |
| `/progress <topic>` | `progress` | Up to 5 levels | PASS→advance, RETRY (max 2)→forced advance |

### Smoke Tests — `/recall`
```
1. /recall Article 356
2. [Type a 3-sentence brain dump]
   → Expect: hits/misses breakdown, SCORE: X/10, follow-up question
3. [Answer the follow-up]
   → Expect: FINAL SCORE: X/10, revision tip, "Session complete."
```

### Smoke Tests — `/progress`
```
1. /progress Preamble of the Constitution
2. [Answer Level 1 correctly]
   → Expect: "✅ PASS — advancing to Level 2: UNDERSTAND"
3. [Answer Level 2 poorly]
   → Expect: "🔁 RETRY — Level 2: UNDERSTAND (attempt 2/3)"
4. [Fail again] → "🔁 RETRY (attempt 3/3)"
5. [Fail third time] → "⚡ 3 attempts at Level 2 — moving forward."
6. [Continue to Level 5 and pass]
   → Expect: "🏆 BLOOM'S COMPLETE" with journey summary
```

---

## Previous Deployment History

---

### PR #7 — Hermes V1.6: Stateful /drill (2026-04-08)
- Stateful `/drill`: 3 interleaved MCQs → grade all → auto-cascade to weakest concept quiz
- PR merged to `main`

### PR #3 — NB6/NB9/hermes fixes (2026-04-07)
> **PR:** [#3 Fix NB6 duplicate header, NB9 snapshot bloat, hermes SQL injection](https://github.com/GaddeSaiHarsha/UPSC_2027/pull/3)
> **Status:** Merged to `main` ✅

---

## 📋 PREVIOUS CHANGES (PR #3 — 3 Files)

### 1. `NB6_CA_Orchestrator.py` — Gemini cleanup
- Removed duplicate 37-line markdown header (copy-paste artifact)
- Removed dead `PERPLEXITY_API_KEY` loading code (was reading from wrong `azure-ocr` scope)
- Updated header to v3.3 reflecting Gemini 2.5 Flash
- Cleaned all stale "Perplexity sonar-pro" references
- **No logic changes** — Gemini API calls, parsing, dedup all untouched

### 2. `NB9_Backup_Sync.py` — Diff-based snapshot push
- Added `hashlib` and `timedelta` imports at top
- Before pushing each table JSON to GitHub, compares MD5 hash against yesterday's snapshot
- Skips unchanged tables (eliminates daily identical `mastery_tracker.json` push — was 83KB/day of waste)
- Adds "skipped" count to summary output
- **No behavioral changes** — still pushes all changed tables normally

### 3. `bot_code/hermes_full.py` — SQL injection fix
- `/mastery_update` command now validates:
  - `topic_id` against regex `^[A-Z0-9]+-\d{3}$`
  - `pct` range 0–100
  - `status` against whitelist `{mastered, in_progress, needs_work, not_started}`
- **No other commands changed**

---

## 🔧 STEP-BY-STEP DATABRICKS DEPLOYMENT

### Method 1: Use Genie/Assistant — Copy-Paste Prompts

Open your Databricks **Assistant** (or Genie Code) and paste these prompts one at a time:

---

#### PROMPT 1: Update NB6 CA Orchestrator

```
Open the notebook "NB6 CA Orchestrator Pipeline" in my workspace.

I need to apply these changes from the GitHub PR that was merged:

1. The header markdown cell (first cell) should be REPLACED with this content — there was a duplicate header that needs removing. The header should start with:
   "# NB6: Current Affairs Orchestrator Pipeline v3.3"
   and the subtitle should say:
   "### Gemini 2.5 Flash → Two-Pass Analysis → Delta → RAG Pipeline → FAISS → Obsidian"

2. In the Configuration cell (Cell 2), REMOVE the entire Perplexity API key loading block. Look for these lines and DELETE them:
   ```
   PERPLEXITY_API_KEY = ""
   try:
       _widget_key = dbutils.widgets.get("perplexity_api_key")
       ...
   ```
   Delete from `PERPLEXITY_API_KEY = ""` through the `print("   Get your key: ...")` line (approximately 20 lines).

3. Replace any comment mentioning "Perplexity" with "Gemini 2.5 Flash" in the Configuration cell. The API key comment should reference `gemini_api_key` widget and `upsc-bot-secrets/google-ai-api-key`.

4. The cost line in the header should read:
   "**Cost:** ~$0/day with Google AI credits ($400 balance); Gemini 2.5 Flash + BGE embeddings"

These are ONLY cleanup changes — do NOT modify any Gemini API call logic, parsing, or Delta table operations.
```

---

#### PROMPT 2: Update NB9 Backup Sync

```
Open the notebook "NB9 UPSC Backup and GitHub Sync" in my workspace.

I need to add diff-based snapshot skipping to avoid pushing identical table data to GitHub every day. Here are the exact changes:

1. In Cell 1 (Configuration), add these imports at the top with the other imports:
   ```python
   import hashlib as _hashlib
   from datetime import date, datetime, timedelta
   ```
   (If `timedelta` is already imported, just add `hashlib as _hashlib`)

2. In Cell 4 (Push to GitHub), find the section "Push critical table data as JSON". 
   BEFORE the `for table_name in CRITICAL_TABLES:` loop, add this function:
   ```python
   def _get_prev_snapshot_hash(table_name):
       """Get md5 hash of yesterday's snapshot for diff-based skip."""
       yesterday = (date.today() - timedelta(days=1)).isoformat()
       prev_path = f"data_snapshots/{yesterday}/{table_name}.json"
       try:
           r = gh_api("get", prev_path)
           if r.status_code == 200:
               content = base64.b64decode(r.json().get("content", ""))
               return _hashlib.md5(content).hexdigest()
       except Exception:
           pass
       return None
   ```

3. Inside the `for table_name in CRITICAL_TABLES:` loop, AFTER the line:
   `content_bytes = json_str.encode('utf-8')`
   
   ADD these lines BEFORE `gh_path = f"data_snapshots/{TODAY}/...`:
   ```python
   # Diff check: skip if content identical to yesterday's snapshot
   new_hash = _hashlib.md5(content_bytes).hexdigest()
   prev_hash = _get_prev_snapshot_hash(table_name)
   if prev_hash and new_hash == prev_hash:
       skipped_unchanged += 1
       print(f"   ⏭️  {table_name:<45} unchanged — skipped")
       continue
   ```

4. Before the for loop, add: `skipped_unchanged = 0`

5. In the Summary section at the end of Cell 4, after the "Pushed:" line, add:
   ```python
   if skipped_unchanged > 0:
       print(f"   Skipped: {skipped_unchanged} unchanged table snapshots (diff-based)")
   ```

This will skip pushing mastery_tracker.json (83KB) when it hasn't changed, saving ~33MB/year of GitHub bloat.
```

---

#### PROMPT 3: Update hermes_full.py (Bot Code)

```
Open the file "hermes_full.py" in my workspace.

Find the function `cmd_mastery_update`. I need to add input validation to prevent SQL injection. Here are the exact changes:

After `topic_id = args[0].upper()`, ADD:
```python
# Validate topic_id format to prevent SQL injection (e.g. GS1-001, GS2-045)
if not re.match(r'^[A-Z0-9]+-\d{3}$', topic_id):
    await update.message.reply_text("❌ topic_id must be like GS1-001, GS2-045, etc.")
    return
```

After `pct = float(args[1])` / the try/except block, ADD:
```python
if not (0 <= pct <= 100):
    await update.message.reply_text("❌ mastery_pct must be between 0 and 100")
    return
```

Replace the status assignment block with:
```python
VALID_STATUSES = {"mastered", "in_progress", "needs_work", "not_started"}
if len(args) > 2:
    status = args[2]
    if status not in VALID_STATUSES:
        await update.message.reply_text(
            f"❌ status must be one of: {', '.join(sorted(VALID_STATUSES))}")
        return
elif pct >= 80:
    status = "mastered"
elif pct >= 40:
    status = "in_progress"
elif pct > 0:
    status = "needs_work"
else:
    status = "not_started"
```

Make sure `import re` is at the top of the file (it should already be there).

No other commands need changing — only `/mastery_update`.
```

---

### Method 2: Direct File Replace (Download & Import)

The `notebooks/` and `bot_code/` folders in this package contain the exact merged files from GitHub `main` branch. You can:

1. **NB6**: Download `notebooks/NB6_CA_Orchestrator.py` → In Databricks, go to your workspace → right-click "NB6 CA Orchestrator Pipeline" → Import → choose the `.py` file → Confirm overwrite

2. **NB9**: Download `notebooks/NB9_Backup_Sync.py` → Same import process for "NB9 UPSC Backup and GitHub Sync"

3. **hermes_full.py**: Download `bot_code/hermes_full.py` → Upload to your VM's bot directory

---

## 🤖 HERMES BOT REDEPLOYMENT

The **only change** to `hermes_full.py` is input validation in `/mastery_update`. No new dependencies, no config changes.

### If running on Azure VM:

```bash
# SSH into your VM
ssh your-vm

# Navigate to bot directory
cd /path/to/hermes

# Backup current file
cp hermes_full.py hermes_full.py.bak.$(date +%Y%m%d)

# Upload new file (use scp, wget from GitHub, or paste)
# Option A: Download from GitHub directly
wget -O hermes_full.py "https://raw.githubusercontent.com/GaddeSaiHarsha/UPSC_2027/main/bot_code/hermes_full.py"

# Option B: Or use the file from this package
scp hermes_full.py your-vm:/path/to/hermes/

# Restart the bot
# If using systemd:
sudo systemctl restart hermes-bot

# If using screen/tmux:
# Kill the old process, then:
python3 hermes_full.py

# If using nohup:
kill $(pgrep -f hermes_full)
nohup python3 hermes_full.py &
```

### If running in Databricks:
The `hermes_full.py` file is already in your workspace. The next NB9 run will push it to GitHub, but you need to update the workspace copy manually since the bot runs from the workspace file.

### Verify the fix:
Send `/mastery_update test 50` to the bot — it should now reject "test" as an invalid topic_id format.

---

## 📅 DATABRICKS JOB MODIFICATIONS

### No job schedule changes needed!

The existing jobs are fine:
| Job | Schedule | Notebook | Status |
|-----|----------|----------|--------|
| UPSC Daily CA Orchestrator | 7:00 AM IST | NB6 | ✅ No job change needed |
| Daily CA Practice Generator | 8:00 AM IST | NB7 | ✅ Untouched |
| NB8 Audio Generator | 8:30 AM IST | NB8 | ✅ Untouched |
| NB9 UPSC Backup and GitHub Sync | 9:00 AM IST | NB9 | ✅ No job change needed |

**Only the notebook CODE changed, not the job configuration.** Since jobs reference notebooks by path, updating the notebook content is sufficient.

---

## 📂 OBSIDIAN VAULT SETUP

### Fresh Install (Mac/Windows/Linux):

1. Download and install [Obsidian](https://obsidian.md)
2. Extract `obsidian_vault/` from this package to `~/Desktop/UPSC_2027/`
3. Open Obsidian → "Open folder as vault" → select `~/Desktop/UPSC_2027/`
4. It will auto-detect the `.obsidian` config with these pre-installed plugins:
   - ✅ Calendar
   - ✅ Dataview
   - ✅ Excalidraw
   - ✅ Heatmap Calendar
   - ✅ Kanban
   - ✅ Spaced Repetition
   - ✅ Style Settings
   - ✅ Omnisearch
   - ✅ Templater
   - ✅ Minimal theme

### Pre-built Data Included:
- `01_Current_Affairs/2026/03-March/` — 4 CA notes (Mar 20-23)
- `Daily_Practice/2026-04-03..07/` — 5 days of practice content (QA, MCQs, Ethics, Telugu, etc.)
- `04_Traps/seed_traps.csv` — 15 hand-curated traps
- `04_Traps/Trap_Index.md` — Trap database index
- `Templates/` — 4 templates (Topic Note, Answer Practice, PYQ Extract, Weekly Review)
- `00_Dashboard/Home.md` — Command center with daily routine

### Daily Sync from Databricks:
```bash
# Run this daily after 9:30 AM IST (after NB9 completes)
cd ~/Desktop/UPSC_2027
git pull origin main
```

Or use the auto-sync script:
```bash
cd ~/Desktop/UPSC_2027/07_Sync
python3 sync_from_databricks.py
```

### Vault Structure:
```
UPSC_2027/
├── .obsidian/              ← Pre-configured plugins + Minimal theme
├── .claude/CLAUDE.md       ← Claude Code project instructions
├── 00_Dashboard/           ← Home MOC + Weekly Review
├── 01_Current_Affairs/     ← Daily CA notes from NB6 (auto-generated)
│   └── 2026/
│       ├── 03-March/       ← 4 pre-built notes
│       ├── 04-April/       ← Ready for new notes
│       └── ...
├── 02_Subjects/            ← Manual study notes
│   ├── Polity/Topics/
│   ├── Economy/Topics/
│   ├── Geography/Topics/
│   ├── History/Topics/
│   ├── Environment/Topics/
│   ├── Science_Tech/Topics/
│   ├── IR/Topics/
│   ├── Ethics/Topics/
│   └── Telugu_Optional/Topics/
├── 03_PYQs/                ← PYQ extraction + tracking
│   ├── By_Year/
│   ├── By_Subject/
│   └── My_Performance/
├── 04_Traps/               ← Trap database (synced from Delta)
├── 05_Revision/            ← Spaced repetition (Dataview-powered)
├── 06_Answer_Practice/     ← Mains answer writing
│   ├── GS1/ GS2/ GS3/ GS4/ Essay/
│   └── KARL_Scores.md
├── 07_Sync/                ← Databricks ↔ Obsidian bridge scripts
├── Daily_Practice/         ← 8 practice modes from NB7
│   └── 2026-04-07/         ← Latest: QA, KARL, MCQs, Ethics, Mains, Telugu, Tutor, Phone
├── Templates/              ← 4 templates for consistency
└── UPSC_SYSTEM_GUIDE.md    ← Complete system documentation
```

---

## ✅ VERIFICATION CHECKLIST

After deploying, verify:

- [ ] **NB6**: Run Cell 1 (Header) — should show v3.3, no "Perplexity" mentions
- [ ] **NB6**: Run Cell 2 (Config) — should NOT try to load `PERPLEXITY_API_KEY`
- [ ] **NB6**: Run Step 2 — should call Gemini (check: `Calling Gemini 2.5 Flash...`)
- [ ] **NB9**: Run Cell 1 — should show `hashlib` imported without error
- [ ] **NB9**: Run Cell 4 — when mastery_tracker is unchanged, should print `⏭️ mastery_tracker unchanged — skipped`
- [ ] **Hermes Bot**: Send `/mastery_update INVALID 50` — should reject
- [ ] **Hermes Bot**: Send `/mastery_update GS1-001 50` — should succeed
- [ ] **Obsidian**: Open vault → Home.md loads → Dataview plugin active → Calendar plugin shows dates

---

## ⚠️ IMPORTANT NOTES

1. **NB6 Gemini API Key**: Make sure `google-ai-api-key` is in your `upsc-bot-secrets` Databricks secret scope. The code tries:
   - Widget `gemini_api_key` first
   - Then `dbutils.secrets.get("upsc-bot-secrets", "google-ai-api-key")`
   
   For scheduled jobs (no UI), the secret is required. Verify:
   ```python
   dbutils.secrets.get("upsc-bot-secrets", "google-ai-api-key")
   ```

2. **The previous research analysis identified a potential secret name mismatch**: the code uses `google-ai-api-key` but stored memories reference `google-ai-key`. Please verify which name your secret is actually stored under:
   ```python
   # Try both:
   try: print("Found:", dbutils.secrets.get("upsc-bot-secrets", "google-ai-api-key")[:5])
   except: print("NOT FOUND: google-ai-api-key")
   try: print("Found:", dbutils.secrets.get("upsc-bot-secrets", "google-ai-key")[:5])
   except: print("NOT FOUND: google-ai-key")
   ```
   If only `google-ai-key` works, update NB6 line 605 to use that name.

3. **No changes to NB7, NB8, or other notebooks** — they are untouched.

# UPSC 2027 AI System — Production Master Guide
> **Last updated:** 2026-04-09 | **Status:** Production-Ready ✅
> **Target:** UPSC CSE 2027 (Prelims May 2027 · Mains Sep 2027) | Telugu Optional (500 marks)

---

## QUICK REFERENCE — WHAT'S BUILT AND WHERE

| Layer | What | Where | Status |
|---|---|---|---|
| Databricks Cloud | NB6 CA Pipeline (7 AM) | Workspace NB `3121042200670064` | ✅ Runs daily |
| Databricks Cloud | NB7 Practice Generator (8 AM) | Workspace NB `3121042200670073` | ✅ Runs daily |
| Databricks Cloud | Knowledge Base (80,800 chunks) | `upsc_catalog.rag.*` | ✅ Live |
| Databricks Cloud | Vector Search | `upsc_catalog.rag.upsc_knowledge_index` | ✅ Live |
| Databricks Cloud | Knowledge Graph | `kg_entities` + `kg_relationships` | ✅ Live |
| Telegram Bot | Hermes V1.8 mentor bot | `bot_code/hermes_full.py` | ✅ Built |
| Mac | Obsidian vault (syncs 8:15 AM) | `~/Desktop/UPSC_2026` | ✅ Auto-sync |
| Mac | Obsidian Copilot | Plugin: Copilot by Logan Yang | ⬜ Install once |
| Claude Code | MCP Study Tools (6 tools) | `.claude/settings.local.json` | ✅ Configured |
| Claude Code | Native Databricks MCP | `databricks mcp start` | ⬜ CLI install |

---

## PART 1 — CREDENTIALS & CONFIG (LOCKED)

> **NEVER commit actual tokens to git.** Use environment variables or `~/.databrickscfg`.

### Databricks
```
Host:         https://adb-7405615460529826.6.azuredatabricks.net
CLI Profile:  upsc  (stored in ~/.databrickscfg on Mac)
Warehouse ID: 589dccbdf8c6e4c9
Catalog:      upsc_catalog
Schema:       rag
Volume:       /Volumes/upsc_catalog/rag/obsidian_ca/UPSC_2026/
```

### Telegram Bot (Hermes)
```
Telegram User ID:  2022402970  (only you can talk to Hermes)
Memory DB:         /home/$USER/UPSC_2026/.upsc_memory.db  (SQLite, WAL mode)
Groq Backend:      Llama 3.3 70B (free tier, ~$0/month)
```

### Vault Paths
```
Mac (Obsidian):    ~/Desktop/UPSC_2026
Linux/Codespace:   /home/$USER/UPSC_2026
Git repo:          github.com/GaddeSaiHarsha/UPSC_2027
Current branch:    copilot/update-documentation-for-project
```

### AI Models
```
NB6 CA Pipeline:   databricks-claude-opus-4-6
NB7 + Notebooks:   databricks-claude-sonnet-4-6
Obsidian Copilot:  databricks-claude-opus-4-6 (deep) / sonnet (daily)
Hermes Bot:        Llama 3.3 70B via Groq (free)
Embeddings:        Qwen3 0.6B (1024-dim)
```

---

## PART 2 — SYSTEM ARCHITECTURE (END TO END)

```
╔══════════════════════════════════════════════════════════════════╗
║                     DATABRICKS CLOUD                             ║
║                                                                  ║
║  07:00 AM IST ────────────────────────────────────────────────  ║
║  NB6 CA Orchestrator (NB ID: 3121042200670064)                  ║
║    Perplexity sonar-pro API → 4-6 CA stories                    ║
║    → upsc_catalog.rag.stories          (title, priority, GS)    ║
║    → upsc_catalog.rag.story_traps      (wrong/correct beliefs)  ║
║    → upsc_catalog.rag.deep_analysis    (PYQ, skeleton, links)   ║
║    → upsc_catalog.rag.geography_context (location analysis)     ║
║    → upsc_catalog.rag.essay_threads    (recurring themes)       ║
║    → Volume: CA_2026-MM-DD.md          (Obsidian note)          ║
║    Model: Claude Opus 4.6 (deep 2-pass reasoning)               ║
║                                                                  ║
║  08:00 AM IST ────────────────────────────────────────────────  ║
║  NB7 Practice Generator (NB ID: 3121042200670073)               ║
║    Mode 1: Knowledge Q&A (15-mark Mains + Article citations)    ║
║    Mode 2: KARL Evaluation (question → answer → score)          ║
║    Mode 3: Prelims MCQs (5 trap-based MCQs)                     ║
║    Mode 4: Ethics Case Study (GS4 stakeholder map)              ║
║    Mode 5: Mains Model Answers (cross-subject, deep)            ║
║    Mode 6: Telugu Optional (P1+P2 PYQ model answers)            ║
║    Model: Claude Sonnet 4.6 (all 6 modes)                       ║
║                                                                  ║
║  On-demand ────────────────────────────────────────────────     ║
║  NB4 Examiner Agent      → KARL-pattern answer grading          ║
║  NB5 Weakness Tracker    → subject gaps + study plan            ║
║  NB1-3 RAG Pipeline      → PDF ingest → chunk → embed           ║
║  Morning Dashboard       → 14-cell visual summary               ║
║  Telugu Study System     → OCR + dedicated Telugu AI            ║
║                                                                  ║
║  DATA (upsc_catalog.rag.*)                                       ║
║  ├── contextual_chunks   80,800 rows — textbook/PYQ knowledge   ║
║  ├── embedded_chunks     80,800 rows — Qwen3 embeddings         ║
║  ├── stories             Daily CA (title, priority, GS papers)  ║
║  ├── story_traps         UPSC exam traps per story              ║
║  ├── deep_analysis       PYQ patterns + mains skeletons         ║
║  ├── geography_context   Location analysis for CA stories       ║
║  ├── essay_threads       Recurring 30-day CA themes             ║
║  ├── ca_runs             Pipeline run metadata                  ║
║  ├── kg_entities         Knowledge Graph entities               ║
║  └── kg_relationships    KG directed relationships              ║
║                                                                  ║
║  Vector Search: upsc_knowledge_index (Qwen3 1024-dim)           ║
╚══════════════════════════════════════════════════════════════════╝
                              │
                        8:15 AM IST
                     Databricks CLI v2
                    dbfs: Volume → Mac
                              ▼
╔══════════════════════════════════════════════════════════════════╗
║                     MAC (OBSIDIAN)                               ║
║  ~/Desktop/UPSC_2026/                                            ║
║  ├── 01_Current_Affairs/  ← NB6 daily CA notes (auto-synced)    ║
║  ├── 02_Subjects/         ← 9 subject folders                   ║
║  ├── 03_PYQs/             ← By_Subject, By_Year, Performance    ║
║  ├── 04_Traps/            ← Trap_Index.md                       ║
║  ├── 05_Revision/         ← Due_Today.md (spaced rep)           ║
║  ├── 06_Answer_Practice/  ← GS1-4 + Essay + KARL_Scores         ║
║  ├── 07_Sync/             ← All scripts in this section         ║
║  └── .claude/CLAUDE.md    ← AI context (this file)             ║
║                                                                  ║
║  Obsidian Copilot:                                               ║
║    Claude Opus 4.6 via Databricks endpoint                       ║
║    Cmd+Shift+C → chat with open note                            ║
╚══════════════════════════════════════════════════════════════════╝
                              │
                     Claude Code (this)
                     + Hermes Telegram Bot
                              ▼
╔══════════════════════════════════════════════════════════════════╗
║             STUDY SESSION (You, 8:30 AM onwards)                 ║
║                                                                  ║
║  Option A — Obsidian:                                            ║
║    Open CA note → Cmd+Shift+C → ask Copilot anything            ║
║                                                                  ║
║  Option B — Claude Code (here):                                  ║
║    MCP tools auto-connected → ask: "what are today's stories?"   ║
║    → get_daily_summary, get_today_stories, get_traps             ║
║    → get_deep_analysis, search_chunks, search_knowledge_graph    ║
║                                                                  ║
║  Option C — Telegram (Hermes bot):                               ║
║    /quiz /drill /socratic /recall /progress (stateful sessions)  ║
║    /daf /mock_iq (interview practice)                            ║
║    /evaluate /model /essay /telugu (answer writing)              ║
╚══════════════════════════════════════════════════════════════════╝
```

---

## PART 3 — HERMES BOT V1.8 — COMPLETE COMMAND REFERENCE

### Stateful Commands (session persists until /cancel or completion)

| Command | Session Mode | How it works | Ends when |
|---|---|---|---|
| `/quiz [topic]` | `quiz` | MCQ with hidden key → grade → follow-up MCQ on same concept | `/cancel` |
| `/drill` | `drill` | 3 interleaved MCQs → grade all → auto-cascade to weakest concept quiz | After 3 MCQs + summary |
| `/socratic [topic]` | `socratic` | Depth 1-4: probe → deeper/simpler → conclude | After depth 4 |
| `/recall <topic>` | `recall` | Phase 1: brain dump → grade (hits/misses/score) → targeted follow-up | After Phase 2 |
| `/progress <topic>` | `progress` | Bloom L1→L5: RECALL→UNDERSTAND→APPLY→ANALYSE→EVALUATE. PASS=advance, FAIL=retry (max 2) | After L5 PASS or forced |
| `/daf [angle]` | `daf` | 3-round interview board: tech/brain_drain/telugu/canada/ai_ethics, hidden rubric | After Round 3 |
| `/mock_iq` | `mock_iq` | 5-member panel (Chairman/Sr.IAS/Academic/Technocrat/Generalist), one Q at a time | After Q5 |

### Instant Commands (no session — immediate response)

| Category | Commands |
|---|---|
| **Core Study** | `/teach <topic>` `/log <note>` `/eod` `/daily` `/dump` `/stats` `/weak` |
| **Prelims** | `/quiz [topic]` `/trap [topic]` `/drill` `/pyq [subject]` `/csat` `/pattern` `/examiner` |
| **Mains** | `/evaluate` `/model <topic>` `/essay <title>` `/framework <topic>` `/structure` |
| **Active Learning** | `/socratic [topic]` `/feynman <topic>` `/why <thing>` `/visual <topic>` `/recall <topic>` `/simplify <topic>` `/progress <topic>` |
| **Telugu Optional** | `/telugu [topic]` `/tel_kavya` `/tel_prosody` `/tel_grammar` |
| **Interview** | `/daf [angle]` `/mock_iq` |

### Database Tables (SQLite — `.hermes_memory.db`)

| Table | Purpose |
|---|---|
| `interactions` | Every message: command, input, response, tokens, latency |
| `concepts` | Topics studied (log_concept on each /teach, /simplify) |
| `quiz_sessions` | Quiz history: topic, question, answer, score |
| `weaknesses` | Subject + topic weak areas (auto-tagged from wrong quiz answers) |
| `interview_history` | DAF + mock_iq sessions: round, angle, question, score, feedback |

### Hidden Key Pattern (how evaluation works)
```
LLM output → [USER] block shown to user
           → [KEY] block = JSON rubric (hidden)
User answers → eval prompt uses [KEY] to grade
           → SCORE: X/10 extracted via regex
           → session advances or retries
```

---

## PART 4 — DELTA TABLES SCHEMA (upsc_catalog.rag.*)

### stories
```sql
date STRING, story_id STRING, slug STRING, title STRING,
priority STRING,        -- CRITICAL | HIGH | MEDIUM | LOW
gs_papers STRING,       -- JSON array e.g. ["GS2", "GS3"]
topic_cluster STRING,   -- e.g. "Economy|IR"
keywords STRING         -- JSON array
```

### story_traps
```sql
trap_id STRING, story_slug STRING, subject STRING,
trap_type STRING,       -- FACTUAL_CONFUSION | DATE_ERROR | CONFLATION | PARTIAL_FACT | SCOPE_ERROR
wrong_belief STRING, correct_belief STRING,
severity STRING,        -- HIGH | MEDIUM | LOW
reinforces_trap_id STRING, created_date STRING
```

### deep_analysis
```sql
story_id STRING, date STRING,
pyq_patterns STRING,    -- JSON: [{year, paper, theme, connection}]
traps_detailed STRING,  -- JSON: [{trap, why_students_fall, exam_risk}]
mains_skeleton STRING,  -- JSON: {question, directive, intro, body_points[], conclusion}
static_links STRING,    -- JSON: [{book, topic, why_read}]
created_date STRING
```

### geography_context
```sql
story_id STRING, date STRING, location_name STRING,
map_description STRING, surrounding_context STRING,
strategic_importance STRING, created_date STRING
```

### contextual_chunks (80,800 rows)
```sql
chunk_id STRING, source_file STRING, subject STRING,
page_number INT, chunk_index INT,
text STRING,            -- WITH context header prepended
raw_text STRING, context_header STRING,
token_count INT, ingested_at TIMESTAMP,
doc_type STRING,        -- textbook | PYQ | CA | topper
exam_stage STRING       -- Prelims | Mains | Both
```

### kg_entities
```sql
entity_id STRING, entity_name STRING, entity_type STRING,
description STRING, source_chunks STRING  -- JSON array of chunk_ids
```

### kg_relationships
```sql
relationship_id STRING, source_entity_id STRING, target_entity_id STRING,
relationship_type STRING, context STRING, strength FLOAT
```

### Vector Search Index
```
Name:     upsc_catalog.rag.upsc_knowledge_index
Model:    Qwen3 0.6B embeddings (1024-dim)
Columns:  chunk_id, text, subject, source_file
Query:    POST /api/2.0/vector-search/indexes/upsc_catalog.rag.upsc_knowledge_index/query
          body: {"query_text": "...", "num_results": 5, "columns": ["chunk_id","text","subject","source_file"]}
```

---

## PART 5 — MCP TOOLS IN CLAUDE CODE

When you open Claude Code in this folder, **2 MCP servers** auto-start and give you **6 tools**:

### Tool Reference

| Tool | Call example | What you get |
|---|---|---|
| `get_daily_summary` | `get_daily_summary()` | Did NB6 run? Stories/traps/analysis counts, total KB size |
| `get_today_stories` | `get_today_stories("2026-04-09")` | All stories: priority, GS papers, keywords, story_id |
| `get_traps` | `get_traps(topic="Article 356")` | Trap list: wrong belief → correct belief, severity |
| `get_deep_analysis` | `get_deep_analysis("story_1")` | Mains skeleton + PYQ patterns + static textbook links |
| `search_chunks` | `search_chunks("Bommai judgment", subject="Polity")` | Top matching KB passages with source + page |
| `search_knowledge_graph` | `search_knowledge_graph("Article 21")` | Entity + all connections across GS papers |

### MCP Server 1 — Databricks Native (`upsc-databricks-native`)
```json
Command: databricks mcp start --profile upsc
Provides: SQL execution, Unity Catalog, Vector Search, MLflow
```

### MCP Server 2 — Custom Study Tools (`upsc-databricks-study`)
```json
Command: python3 07_Sync/mcp_databricks_server.py
Config:  07_Sync/sync_config.json (warehouse ID: 589dccbdf8c6e4c9 — already set)
Auth:    ~/.databrickscfg [upsc] profile token
```

### Morning Workflow with MCP (8:30 AM)
```
1. Open Claude Code in UPSC_2027 folder
2. Ask: "Give me today's daily summary"
   → get_daily_summary() tells you if NB6 ran
3. Ask: "What are today's top priority stories?"
   → get_today_stories() returns all stories ranked
4. Ask: "Get deep analysis for story_1"
   → get_deep_analysis() gives mains skeleton + PYQ patterns
5. Ask: "What are today's HIGH severity traps?"
   → get_traps() returns traps to memorize
6. Ask: "Search chunks for Article 356 Bommai"
   → search_chunks() pulls textbook passages
7. Write answer → paste in Claude Code for evaluation
```

---

## PART 6 — OBSIDIAN COPILOT SETUP (ONE-TIME, ON MAC)

### Install Steps
1. Obsidian → Settings → Community Plugins → turn off Restricted Mode
2. Browse → search **"Copilot"** → install **Copilot by Logan Yang** → Enable
3. Settings → Copilot → Add Custom Model:

```
Display Name:  Claude Opus 4.6 (UPSC)
Provider:      OpenAI-compatible
Base URL:      https://adb-7405615460529826.6.azuredatabricks.net/serving-endpoints
API Key:       dapi-... (your Databricks PAT — NOT committed to git)
Model Name:    databricks-claude-opus-4-6
```

4. Add second model (for daily use):
```
Display Name:  Claude Sonnet 4.6 (Fast)
Model Name:    databricks-claude-sonnet-4-6
(rest same as above)
```

5. Settings:
```
Default Model:              Claude Opus 4.6 (UPSC)
Temperature:                0.3
Max Tokens:                 2000
Use Active Note as Context: ON
Auto-complete:              OFF (costs DBUs per keystroke)
System Prompt:              "You are a UPSC CSE 2027 expert tutor. Be precise,
                             cite Article numbers, case laws, and specific facts.
                             Format for exam answers."
```

6. Keyboard shortcut: `Cmd+Shift+C` → opens Copilot chat panel

### Ready-to-Use Prompts (paste in Copilot with CA note open)
```
Summarize this CA note for GS2 Mains in 150 words
What Prelims MCQs can be framed from this note? Give 3.
Create 5 flashcards in #card format for spaced repetition
Frame a GS4 Ethics case study from this story
Write a 250-word model answer on the main theme of this note
What are the 3 traps students most likely make on this topic?
Connect this to PYQs from the last 5 years
What would Ambedkar, Gandhi, and Kalam say about this issue?
```

---

## PART 7 — DAILY STUDY WORKFLOW (PRODUCTION)

```
07:00 AM  NB6 runs automatically on Databricks
           → 4-6 CA stories + traps + deep analysis + geo context
           → CA_2026-MM-DD.md written to Databricks Volume

08:00 AM  NB7 runs automatically on Databricks
           → 6 AI practice outputs (Q&A, KARL, MCQ, Ethics, Model Answers, Telugu)
           → outputs stored in Delta tables + printed to NB7 output

08:15 AM  launchd on Mac runs sync_from_databricks.py
           → downloads entire vault from Databricks Volume to ~/Desktop/UPSC_2026
           → Obsidian auto-detects new files

08:30 AM  YOUR MORNING ROUTINE:

  STEP 1 — Open Claude Code in UPSC_2027 folder
           Ask: "Daily summary for today"
           → Confirms NB6 ran, shows story/trap counts

  STEP 2 — Open Obsidian
           → New CA note is in 01_Current_Affairs/2026/04-April/
           → Cmd+Shift+C → Copilot: "Summarize for GS Mains"
           → Cmd+Shift+C → Copilot: "What are 3 MCQs from this?"

  STEP 3 — Review traps (in Claude Code or Copilot)
           Ask: "Get today's HIGH severity traps"
           → Memorize wrong→correct, note the mnemonics

  STEP 4 — Write 1 answer in 06_Answer_Practice/
           Choose a story from today's deep_analysis mains skeleton
           Write 250 words (15 min, timed)
           Send to Hermes: /evaluate [paste answer]
           OR paste in Claude Code for evaluation

  STEP 5 — Hermes session (Telegram)
           /quiz Economy   → MCQ drill
           /recall Article 356  → brain dump test
           /socratic federalism → Socratic depth drill
           OR: /daf tech → interview practice

  STEP 6 — Log the session
           /log [what you studied today]
           /eod → end of day summary in Hermes

WEEKLY (Sunday evening):
  /stats → see performance trends
  /weak  → identify weakest subjects
  Run NB5 Weakness Tracker for full analysis
```

---

## PART 8 — ACTIONS REQUIRED FROM YOU (CHECKLIST)

### One-Time Setup (Mac)

- [ ] **Run setup script**: `bash ~/Desktop/UPSC_2026/07_Sync/setup_mac.sh`
  - Installs Databricks CLI, Obsidian, configures launchd auto-sync
  - Runs initial full vault sync from Databricks Volume

- [ ] **Install MCP dependencies**:
  ```bash
  pip install -r ~/Desktop/UPSC_2026/07_Sync/mcp_requirements.txt
  ```

- [ ] **Verify Databricks CLI auth**:
  ```bash
  databricks auth token --profile upsc
  # Should return your dapi-... token
  ```

- [ ] **Install Obsidian Copilot plugin** (see Part 6 above)
  - Add Claude Opus 4.6 + Sonnet 4.6 custom models
  - Test connection

- [ ] **Deploy Hermes bot** (if not running):
  ```bash
  # On your server/Mac in background:
  cd ~/Desktop/UPSC_2026/bot_code
  # Set env vars (do NOT commit to git):
  export TELEGRAM_TOKEN=your_bot_token
  export TELEGRAM_USER_ID=2022402970
  export GROQ_API_KEY=your_groq_key
  python3 hermes_full.py
  ```

- [ ] **Add shell aliases** to `~/.zshrc`:
  ```bash
  # Quick Sonnet query from terminal
  alias upsc='f(){ databricks serving-endpoints query --profile upsc \
    --name databricks-claude-sonnet-4-6 \
    --input "{\"messages\":[{\"role\":\"system\",\"content\":\"UPSC expert\"},{\"role\":\"user\",\"content\":\"$*\"}],\"max_tokens\":2000}"; }; f'
  alias upsc-deep='f(){ databricks serving-endpoints query --profile upsc \
    --name databricks-claude-opus-4-6 \
    --input "{\"messages\":[{\"role\":\"user\",\"content\":\"$*\"}],\"max_tokens\":3000}"; }; f'
  source ~/.zshrc
  ```

### Ongoing Weekly Actions

- [ ] Sunday: run `/stats` and `/weak` in Hermes → identify gaps
- [ ] Update CLAUDE.md "My current weak areas" section weekly
- [ ] Upload new PDFs to Databricks Volume → run NB1-3 to ingest

### Remaining Knowledge Base Gaps

| Subject | Chunks | Gap | Action |
|---|---|---|---|
| Internal Security | 45 | Need Ashok Kumar textbook | Upload PDF → NB1-3 |
| Agriculture | 1,077 | Need dedicated textbook | Upload Mrunal/Shankar IAS |
| Disaster Management | 218 | Need NDMA guidelines | Upload NDMA doc |
| Telugu Paper 2 | Limited | More prescribed text editions | Upload specific texts |

---

## PART 9 — FILE STRUCTURE (THIS REPO)

```
UPSC_2027/
├── .claude/
│   ├── CLAUDE.md              ← AI context (updated 2026-04-09)
│   └── settings.local.json    ← MCP server config (both servers wired)
│
├── 07_Sync/
│   ├── sync_config.json       ← ALL config (warehouse 589dccbdf8c6e4c9 locked in)
│   ├── sync_from_databricks.py ← Databricks Volume → Mac sync script
│   ├── mcp_databricks_server.py ← Custom MCP server (6 study tools)
│   ├── mcp_requirements.txt   ← mcp + databricks-sql-connector
│   ├── setup_mac.sh           ← One-time Mac setup (CLI + Obsidian + launchd)
│   ├── com.upsc.obsidian-sync.plist ← launchd: 8:15 AM IST auto-sync
│   └── setup_git.sh           ← Git remote setup (one-time)
│
├── bot_code/
│   └── hermes_full.py         ← Hermes V1.8 (3,498 lines, all stateful commands)
│
├── PRODUCTION_MASTER.md       ← THIS FILE — complete system documentation
├── DEPLOYMENT_GUIDE.md        ← V1.8 deployment + smoke tests
├── CLAUDE.md (symlink context)
│
├── 00_Dashboard/              → Home.md (command center)
├── 01_Current_Affairs/        → NB6 daily CA notes (auto-synced)
├── 02_Subjects/               → 9 subject folders
├── 03_PYQs/                   → By_Subject + By_Year + Performance
├── 04_Traps/                  → Trap_Index.md
├── 05_Revision/               → Due_Today.md (spaced repetition)
├── 06_Answer_Practice/        → GS1-4 + Essay + KARL_Scores.md
└── Templates/                 → 4 note templates
```

---

## PART 10 — QUICK TROUBLESHOOTING

| Problem | Fix |
|---|---|
| NB6 didn't run | Check Databricks Jobs → NB6 schedule → trigger manually |
| Vault not syncing at 8:15 AM | `launchctl list \| grep upsc` → reload: `launchctl load ~/Library/LaunchAgents/com.upsc.obsidian-sync.plist` |
| MCP tools not showing in Claude Code | Restart Claude Code → check `settings.local.json` is valid JSON |
| `get_daily_summary` returns error | Verify `~/.databrickscfg` has `[upsc]` profile with valid token |
| Hermes not responding | Check Groq API key + `TELEGRAM_USER_ID=2022402970` is set |
| `/quiz` session stuck | Send `/cancel` to clear session, then restart |
| Obsidian Copilot "connection failed" | PAT expired → generate new token at Databricks → Settings → Access Tokens |
| Chunks not found for subject | Run NB1-3 RAG Pipeline after uploading new PDFs to Volume |

---

## PART 11 — MODEL COST REFERENCE

| Component | Model | Est. DBU/session | Monthly (30 days) |
|---|---|---|---|
| NB6 CA Pipeline (daily) | Opus 4.6 | ~5 DBU | ~150 DBU |
| NB7 Practice Gen (daily) | Sonnet 4.6 | ~2 DBU | ~60 DBU |
| Obsidian Copilot (deep) | Opus 4.6 | ~5 DBU | ~150 DBU |
| Obsidian Copilot (daily) | Sonnet 4.6 | ~1 DBU | ~30 DBU |
| CLI ad-hoc queries | Sonnet 4.6 | ~0.5 DBU | ~15 DBU |
| Hermes bot | Llama 3.3 70B | $0 (Groq free) | $0 |
| Claude Code | Sonnet 4.6 (Pro) | Included | $20/mo |
| **Recommended mix** | Sonnet daily + Opus weekly review | ~3 DBU avg | ~**90 DBU/mo** |

---

## PART 12 — EXAM TIMELINE & STRATEGY

```
TODAY: 2026-04-09
├── Prelims: ~May 2027 (13 months)
│   Focus: BREADTH — cover all subjects
│   Target: 120+ score on 200-question paper
│   Tool: /quiz /drill /trap daily in Hermes
│   Gaps to fix: Agriculture (1,077 chunks), Internal Security (45 chunks)
│
├── Mains: ~Sep 2027 (17 months)
│   Focus: ANSWER WRITING quality
│   Target: 10+ evaluated answers (activate NB5 Weakness Tracker)
│   Tool: /evaluate /model /essay in Hermes + NB4 Examiner
│   Practice: 1 answer/day in 06_Answer_Practice/
│
└── Telugu Optional: ~Sep 2027 (Paper 1 + Paper 2 = 500 marks)
    Coverage: 8,518 chunks — EXCELLENT
    Tool: /telugu /tel_kavya /tel_prosody + NB7 Mode 6
    Gaps: Paper 2 prescribed text editions
```

---

*This document is the single source of truth for the UPSC 2027 AI system.
Update Part 8 checklist as items are completed. Update "My current weak areas" in CLAUDE.md weekly.*
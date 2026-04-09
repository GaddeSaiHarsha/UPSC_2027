# UPSC 2027 AI Study System — Complete Guide
# ═══════════════════════════════════════════════════════════
# Share this file with any AI assistant for full system context.
# Last updated: 2026-04-09
# ═══════════════════════════════════════════════════════════

## WHO I AM
- **UPSC CSE 2027** aspirant | **Telugu Optional** (500 marks)
- MacBook Air (Apple Silicon) | Obsidian vault synced via GitHub
- Full AI-powered study pipeline on **Databricks** (Azure)
- Daily routine: 4 hours morning (7-11 AM IST)
- **Telegram bots**: Hermes (47 commands, Groq/Llama 3.3 70B) + Main Bot v2.3 (30 commands, Databricks Agent)

## THE SYSTEM ARCHITECTURE

```
┌─────────────────────── DATABRICKS CLOUD ──────────────────────────┐
│                                                                    │
│  7:00 AM ─── NB6 CA Orchestrator v3.2 ────────────────────┐      │
│              │ Gemini 2.5 Flash + google_search grounding  │      │
│              │ → stories, story_traps                      │      │
│              │ → deep_analysis, geography_context           │      │
│              │ → contextual_chunks (CA daily)               │      │
│              │ → FAISS rebuild (80,854+ vectors)            │      │
│              │ → Obsidian CA note (.md on Volume)           │      │
│              └─────────────────────────────────────────────┘      │
│                                                                    │
│  8:00 AM ─── NB7 Practice Generator ──────────────────────┐      │
│              │ 8 AI modes via ai_query (Claude Sonnet 4)   │      │
│              │ → Mains Q&A, KARL eval, MCQs                │      │
│              │ → Ethics case study, Model answers           │      │
│              │ → Telugu Optional, AI Tutor, Phone Summary   │      │
│              └─────────────────────────────────────────────┘      │
│                                                                    │
│  8:30 AM ─── NB8 Audio Generator ─────────────────────────┐      │
│              │ NotebookLM + Google Cloud TTS (WaveNet)      │      │
│              │ → Daily CA Podcast (15-20 min)               │      │
│              │ → Strategic Deep-Dive (2x/week, 20-30 min)   │      │
│              │ → Quick Revision Brief (daily, 5 min)        │      │
│              └─────────────────────────────────────────────┘      │
│                                                                    │
│  9:00 AM ─── NB9 Backup & GitHub Sync ────────────────────┐      │
│              │ Delta tables → JSON/Parquet → GitHub         │      │
│              │ Notebooks, bot code, FAISS, Obsidian vault   │      │
│              │ Diff-based skip (MD5 hash vs yesterday)      │      │
│              └─────────────────────────────────────────────┘      │
│                                                                    │
│  On-demand ── NB4 Examiner Agent (KARL pattern)                   │
│               NB5 Weakness Tracker                                 │
│               NB1-3 RAG Pipeline (ingest/embed/query)             │
│               Morning Dashboard (14 cells + 4 AI cells)            │
│               Telugu Optional Study System (OCR + AI)              │
│                                                                    │
│  Data ─────── 80,854+ chunks in Delta tables                      │
│               FAISS IndexFlatIP (Qwen3 1024-dim)                   │
│               10+ Delta tables in upsc_catalog.rag                 │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
                          │
              9:00 AM NB9 pushes to GitHub
                          │
                          ▼
┌─────────────── GITHUB (GaddeSaiHarsha/UPSC_2027) ───────┐
│  Obsidian vault, notebooks, bot code, data_snapshots     │
│  Daily_Practice/, 01_Current_Affairs/, FAISS index       │
└──────────────────────────────────────────────────────────┘
                          │
                    git pull (manual or auto)
                          ▼
┌─────────────── MAC (OBSIDIAN VAULT) ────────────────────┐
│                                                          │
│  ~/Desktop/UPSC_2027/                                    │
│  ├── .obsidian/          (config + 9 plugins + theme)    │
│  ├── .claude/            (CLAUDE.md — AI context)        │
│  ├── 00_Dashboard/       (Home.md, Weekly_Review.md)     │
│  ├── 01_Current_Affairs/ (daily CA notes from NB6)       │
│  ├── 02_Subjects/        (9 subject folders)             │
│  ├── 03_PYQs/            (By_Subject, By_Year, Perf)     │
│  ├── 04_Traps/           (Trap_Index, seed_traps.csv)    │
│  ├── 05_Revision/        (Due_Today.md, spaced rep)      │
│  ├── 06_Answer_Practice/ (GS1-4, Essay, KARL_Scores)     │
│  ├── 07_Sync/            (sync script, launchd plist)    │
│  ├── Daily_Practice/     (8 modes output per day)        │
│  ├── data_snapshots/     (daily Delta table JSON dumps)  │
│  └── Templates/          (4 templates for notes)         │
│                                                          │
│  Plugins: Dataview, Calendar, Spaced Repetition,         │
│           Templater, Kanban, Heatmap Calendar,            │
│           Style Settings, Omnisearch, Excalidraw          │
│  Theme:   Minimal (dark)                                 │
│                                                          │
└──────────────────────────────────────────────────────────┘
                          │
              Telegram bots (Azure VM)
                          ▼
┌─────────────── TELEGRAM BOTS ───────────────────────────┐
│                                                          │
│  Hermes Bot (hermes_full.py) — 47 commands               │
│    Groq (Llama 3.3 70B) | SQLite memory | ~$0/month     │
│    Core, Prelims, Mains, Active Learning, Telugu,        │
│    Books, Interview, Mobile Practice, System             │
│                                                          │
│  Main Bot v2.3 (upsc_telegram_bot_v23.py) — 30 commands  │
│    Databricks Agent (Llama 3.3 70B + FAISS)              │
│    + GraphRAG + Spaced Repetition + AI Playground        │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

## DATABRICKS NOTEBOOKS (10 total)

| ID | Name | Schedule | Purpose |
|----|------|----------|---------|
| 4264351243244281 | NB1-3 RAG Pipeline | On-demand | PDF ingest → chunking → embedding → FAISS index |
| 2480902325137437 | NB4 Examiner Agent v2 | On-demand | KARL-pattern answer evaluation (weighted nuggets) |
| 2480902325137438 | NB5 Weakness Tracker | On-demand | Subject performance, missed nuggets, study plan |
| 3121042200670064 | NB6 CA Orchestrator v3.2 | 7 AM IST daily | Gemini 2.5 Flash → stories → traps → deep analysis → FAISS → Obsidian |
| 3121042200670073 | NB7 Practice Generator | 8 AM IST daily | 8 AI practice modes (Q&A, KARL, MCQ, Ethics, Model Answers, Telugu, Tutor, Phone) |
| — | NB8 Audio Generator | 8:30 AM IST daily | NotebookLM + Google Cloud TTS → podcasts + revision briefs |
| — | NB9 Backup & GitHub Sync | 9:00 AM IST daily | Delta tables + notebooks + bot code → GitHub (diff-based skip) |
| 3121042200670066 | Morning Dashboard | On-demand | 14-cell visual summary of pipeline + 4 AI cells |
| 138096049883218 | Telugu Optional Study System | On-demand | OCR pipeline + AI study cells for Telugu literature |
| — | Hermes Bot Patch | On-demand | Bot deployment and patching utilities |

## DELTA TABLES (upsc_catalog.rag.*)

### stories
Daily CA stories from Gemini 2.5 Flash (with google_search grounding).
```
date STRING, story_id STRING, slug STRING, title STRING,
priority STRING (CRITICAL/HIGH/MEDIUM/LOW),
gs_papers STRING (JSON array), topic_cluster STRING,
keywords STRING (JSON array)
```

### story_traps
UPSC exam traps per story — wrong beliefs students commonly hold.
```
trap_id STRING, story_slug STRING, subject STRING,
trap_type STRING (FACTUAL_CONFUSION/DATE_ERROR/CONFLATION/PARTIAL_FACT/SCOPE_ERROR),
wrong_belief STRING, correct_belief STRING,
severity STRING, reinforces_trap_id STRING, created_date STRING
```

### deep_analysis
Second-pass analysis with PYQ patterns, mains skeletons, textbook links.
```
story_id STRING, date STRING,
pyq_patterns STRING (JSON), traps_detailed STRING (JSON),
mains_skeleton STRING (JSON), static_links STRING (JSON),
created_date STRING
```

### geography_context
Geographic enrichment for stories with location relevance.
```
story_id STRING, date STRING, location_name STRING,
map_description STRING, surrounding_context STRING,
strategic_importance STRING, created_date STRING
```

### ca_runs
Pipeline run metadata — one row per daily NB6 execution.
```
run_date STRING, generated_at STRING, raw_output STRING,
parsed_json STRING, story_count INT, schema_version STRING
```

### contextual_chunks (80,854+ rows)
The knowledge base — all textbook/PYQ/CA content chunked and contextualized.
```
chunk_id STRING, source_file STRING, subject STRING,
page_number INT, chunk_index INT,
text STRING (with context header), raw_text STRING,
context_header STRING, token_count INT,
ingested_at TIMESTAMP, doc_type STRING, exam_stage STRING
```

### embedded_chunks (80,854+ rows)
Same chunks with Qwen3 embeddings for FAISS vector search.
```
chunk_id STRING, text STRING, subject STRING,
source_file STRING, page_number INT, token_count INT,
embedding ARRAY<DOUBLE> (1024-dim Qwen3)
```

### essay_threads
Recurring themes across 30 days of CA for essay preparation.
```
theme STRING, frequency INT, story_ids STRING,
essay_title STRING, week_date STRING
```

### mastery_tracker
Per-topic mastery scores (updated via Hermes `/mastery_update` command).
```
topic_id STRING (e.g. GS1-001), mastery_pct FLOAT,
status STRING (mastered/in_progress/needs_work/not_started),
updated_at TIMESTAMP
```

### daily_practice_queue
Queue of daily practice items for mobile access.
```
date STRING, mode INT, content STRING, status STRING
```

## KNOWLEDGE BASE — 80,854+ CHUNKS

| Subject | Chunks | Sources |
|---------|--------|---------|
| History | 14,636 | Spectrum, PMFIAS Ancient Medieval, NCERTs, Bipan Chandra, Makkhan Lal, Arjun Dev, Norman |
| PYQ | 10,328 | Mains GS1-4, Prelims 2011-2025, CSAT, Toppers Handwritten GS1-4, MAX IAS 6-Year Solved |
| Telugu Optional | 8,518 | 84+ files, MemoryLines.md, Kavitrayam, Satakamulu, Prosody, Modern, PYQs, sahityam |
| Economy | 8,052 | Ramesh Singh, Economy PT 365 2026, GS3 notes, Economic Survey, Budget |
| Geography | 7,888 | GC Leong, PMFIAS (Physical + Human + Mineral + Industrial), NCERTs, Maps PYQs |
| Environment | 7,578 | Shankar IAS 8e, Blue Book, ForumIAS MCQs, Renewable Energy P1+P2, Pollution notes |
| Polity | 6,716 | Laxmikant 8e, Polity Governance CA, NCERTs, Ruhani Rank-5, Toppers Constitution |
| Science & Tech | 5,068 | Blue Book S&T, ASO S&T, Redbook, Sunya IAS, ForumIAS, S&T 2025, PT 365 |
| General Studies | 3,445 | Prelims Made Easy V1-V3, Lucent GK, Highlighted L-23, Infographics |
| Art & Culture | 2,580 | Nitin Singhania, AnC.pdf, Redbook Art & Culture, Neeraj Rao, NCERT |
| Ethics | 1,111 | 24 files: Rank-4/17/25/27/70/194 toppers, Redbook, mindmaps, case studies, applied ethics |
| Agriculture | 1,077 | Agriculture Prelims PYQs, Major Crops CSN, Major-Crops-PMF |
| International Relations | 997 | Redbook IR, IR Mind Maps, Prelims Magnum IR Places-in-News, NCERT |
| Society | 940 | Redbook Society, Health/Education/HR, PYQ answers, NCERTs |
| Current Affairs | 768+ | Indian Express x4, Dec2025 NewsClips, NB6 daily notes (growing daily) |
| Strategy | 525 | Anudeep Durishetty AIR 1 writing strategies |
| Disaster Management | 218 | Disaster.pdf, Redbook Disaster Management |
| Syllabus | 175 | UPSC syllabus docs |
| Internal Security | 45 | X-Factor Border Security + Defence Industry |

### REMAINING GAPS (upload PDFs to Volume, then ingest)
1. **Agriculture** — Need dedicated textbook (Shankar IAS Agriculture or Mrunal) for depth
2. **Internal Security** — Need Ashok Kumar for comprehensive coverage (only 45 chunks)
3. **Disaster Management** — Could add NDMA guidelines for more depth

### TELUGU OPTIONAL — 8,518 CHUNKS (EXCELLENT COVERAGE)

| Syllabus Area | Status | Details |
|---------------|--------|---------|
| కవిత్రయం (Nannaya/Tikkana/Errana) | ✅ Excellent | Multiple texts + MemoryLines fresh 2026 Tikkana Udyoga Parvam |
| ప్రబంధ యుగం (Srinatha/Peddana) | ✅ Good | Gunanidi Srinathudu, Sarada Lekhalu, కర్పూర వసంతరాయలు |
| ఆధునిక సాహిత్యం (Modern) | ✅ Good | మహాప్రస్థానం (Sri Sri), గబ్బిలం, అల్పజీవి, MemoryLines Jashuva/Devulapalli/Atreya |
| వ్యాకరణం & ఛందస్సు (Prosody) | ✅ Filled | 5 chunks from MemoryLines (Kanda Padyamu, Meters, Sabdalamkara) |
| భాషా చరిత్ర (Language History) | ✅ Excellent | 5 different histories (పింగళి, వెలమల x2, దివాకర్ల, భద్రిరాజు) |
| సాహిత్య చరిత్ర (Literary History) | ✅ Excellent | Andhra Kavula Charitramu (576 chunks), multiple histories |
| శతకములు (Satakamulu) | ✅ Good | MemoryLines Sumati, Dasarathi, Choudappa, Bhaskara |
| గాథా సప్తశతి | ✅ Good | 5 gems with analysis from MemoryLines |
| PYQ model answers | ✅ Good | 736+ chunks |
| Paper 2 prescribed texts | ⚠️ Could improve | Need more actual prescribed text editions |

## 8 PRACTICE MODES (NB7 — Daily 8 AM IST)

| # | Mode | Input | Output |
|---|------|-------|--------|
| 1 | **Knowledge Q&A** | Top CA story + 80K+ textbook chunks (keyword match) | 15-mark Mains answer with Article citations, source files |
| 2 | **KARL Answer Evaluation** | Today's CA chunks | Auto question → sample answer → strict scoring (Critical 60% / Important 30% / Optional 10%) → model answer |
| 3 | **Prelims MCQs** | Stories + NB6 `story_traps` | 5 MCQs with trap-based wrong options, trap_type classification |
| 4 | **Ethics Case Study (GS4)** | CA stories + Ethics 1,111 chunks | Stakeholder map → thinkers (Kant/Gandhi/Kautilya) → dilemma → model answer |
| 5 | **Mains Model Answers + Interlinking** | `deep_analysis` + `geography_context` + `story_traps` | Cross-subject map (GS1-4 + Essay) → structured answers → textbook anchors → PYQ connections |
| 6 | **Telugu Optional (P1 & P2)** | 8,518 Telugu chunks (PYQ + textbooks) | 5 PYQ model answers → approach + తెలుగు సాహిత్య పదాలు + scoring tips |
| 7 | **AI Tutor Brief** | Stories + traps + deep_analysis | 5-min tutor session: practice answer + model answer + memory hooks + revision plan |
| 8 | **Phone Summary** | Modes 1, 5, 7 outputs | 2-3 min emoji-formatted quick read → saved to Obsidian vault |

## OBSIDIAN VAULT STRUCTURE

```
~/Desktop/UPSC_2027/  (also GitHub: GaddeSaiHarsha/UPSC_2027)
├── .obsidian/                    # Vault config + plugins
│   ├── plugins/                  # 9 community plugins
│   │   ├── dataview/             # Query notes like SQL
│   │   ├── calendar/             # Sidebar calendar
│   │   ├── obsidian-spaced-repetition/  # Flashcard SM-2
│   │   ├── templater-obsidian/   # Dynamic templates
│   │   ├── obsidian-kanban/      # Study tracking boards
│   │   ├── obsidian-heatmap-calendar/   # Streak tracker
│   │   ├── obsidian-style-settings/     # Theme customization
│   │   ├── omnisearch/           # Full-text search
│   │   └── obsidian-excalidraw-plugin/  # Diagrams
│   └── themes/Minimal/          # Clean dark theme
│
├── .claude/CLAUDE.md             # AI context for Claude Code
│
├── 00_Dashboard/
│   ├── Home.md                   # Command center (80,854+ chunks, pipeline status)
│   └── Weekly_Review.md          # Weekly stats template
│
├── 01_Current_Affairs/
│   ├── CA_Master_Index.md        # Index of all CA notes
│   └── 2026/
│       ├── 03-March/             # CA_2026-03-20..23.md
│       └── 04-April/             # Growing daily from NB6
│
├── 02_Subjects/                  # One folder per subject
│   ├── Economy/ Environment/ Ethics/ Geography/
│   ├── History/ IR/ Polity/ Science_Tech/
│   └── Telugu_Optional/
│
├── 03_PYQs/
│   ├── By_Subject/               # PYQs organized by subject
│   ├── By_Year/                  # PYQs organized by year
│   ├── My_Performance/
│   │   └── Accuracy_Tracker.md   # PYQ score tracking
│   └── _SOURCE/                  # Raw PYQ data
│
├── 04_Traps/
│   ├── Trap_Index.md             # All traps (from story_traps table)
│   └── seed_traps.csv            # Initial trap data
│
├── 05_Revision/
│   └── Due_Today.md              # Spaced repetition due items
│
├── 06_Answer_Practice/
│   ├── GS1/ GS2/ GS3/ GS4/      # Practice answers by paper
│   ├── Essay/
│   └── KARL_Scores.md            # Answer evaluation history
│
├── 07_Sync/
│   ├── sync_from_databricks.py   # CLI v2 sync script
│   ├── sync_config.json          # Databricks connection config
│   └── com.upsc.obsidian-sync.plist  # launchd auto-sync
│
├── Daily_Practice/               # 8 modes output per day (from NB7)
│   └── YYYY-MM-DD/
│       ├── 01_Knowledge_QA.md
│       ├── 02_KARL_Evaluation.md
│       ├── 03_Prelims_MCQs.md
│       ├── 04_Ethics_Case_Study.md
│       ├── 05_Mains_Model_Answers.md
│       ├── 06_Telugu_Optional.md
│       ├── 07_AI_Tutor_Brief.md
│       ├── 08_Phone_Summary.md
│       ├── podcast_transcript.md
│       └── key_insights.md
│
├── data_snapshots/               # Daily Delta table JSON backups (from NB9)
│   └── YYYY-MM-DD/
│       ├── stories.json
│       ├── story_traps.json
│       ├── ca_runs.json
│       ├── mastery_tracker.json
│       └── daily_practice_queue.json
│
├── Templates/
│   ├── Topic_Note.md             # For new subject notes
│   ├── Answer_Practice.md        # For answer writing practice
│   ├── PYQ_Extract.md            # For PYQ analysis
│   └── Weekly_Review.md          # For weekly reviews
│
├── notebooks/                    # Databricks notebook source (.py)
│   ├── NB6_CA_Orchestrator.py
│   ├── NB7_Daily_CA_Practice.py
│   ├── NB8_Audio_Generator.py
│   ├── NB9_Backup_Sync.py
│   ├── UPSC_Examiner_Agent_v2.py
│   ├── UPSC_Mass_Ingestion.py
│   ├── UPSC_Weakness_Tracker.py
│   ├── Telugu_ReOCR.py
│   ├── Hermes_Bot_Patch.py
│   └── VM_Deploy_Guide.py
│
├── bot_code/                     # Telegram bot source
│   ├── hermes_full.py            # Hermes bot (47 commands, Groq/Llama 3.3 70B)
│   └── upsc_telegram_bot_v23.py  # Main bot v2.3 (30 commands, Databricks Agent)
│
├── UPSC_SYSTEM_GUIDE.md          # THIS FILE — complete system documentation
├── DEPLOYMENT_GUIDE.md           # PR #3 deployment instructions
└── README.md                     # Repository overview
```

## INSTALLED PLUGINS — HOW TO USE EACH

### 1. Dataview (query notes like SQL)
```dataview
// List all CA notes this month
LIST FROM "01_Current_Affairs/2026"
WHERE file.cday >= date(2026-04-01)
SORT file.name DESC
```

### 2. Calendar — click sidebar icon, days with CA notes show dots
### 3. Spaced Repetition — `#card` tag, review via `Cmd+P` → SM-2 scheduling
### 4. Templater — `<% tp.date.now("YYYY-MM-DD") %>`, insert via `Cmd+P`
### 5. Kanban — columns: Not Started | Reading | Revising | Mastered
### 6. Heatmap Calendar — GitHub-style streak tracker
### 7. Style Settings — Minimal theme customization
### 8. Omnisearch — `Cmd+Shift+O` — full-text search across vault
### 9. Excalidraw — diagrams and concept maps

## TELEGRAM BOTS

### Hermes Bot (`bot_code/hermes_full.py`) — 47 commands
- **Backend**: Groq (Llama 3.3 70B) — free tier, ~$0/month
- **Memory**: Own SQLite DB (`.hermes_memory.db`) with WAL mode
- **Personality**: Demanding UPSC mentor (20+ year veteran, produced AIR 1/2/5/11)
- **Commands**: Core (8) + Prelims (7) + Mains (5) + Active Learning (7) + Telugu (7) + Books (3) + Interview (2) + Mobile (7) + System (4)
- **Input validation**: `/mastery_update` validates topic_id format, pct range, status whitelist (SQL injection prevention)
- **Setup**: `pip install groq python-telegram-bot requests` + env vars

### Main Bot v2.3 (`bot_code/upsc_telegram_bot_v23.py`) — 30 commands
- **Backend**: Databricks Agent (Llama 3.3 70B + 80K FAISS vectors)
- **Features**: GraphRAG entity relationships, spaced repetition memory, AI Playground tool-calling
- **Commands**: Core (8) + Prelims (3) + Mains (2) + Active Learning (7) + Interview (1) + GraphRAG (1) + Mobile (6) + System (2)

## NB6 CA ORCHESTRATOR — TECHNICAL DETAILS

**Current API**: Gemini 2.5 Flash via `generativelanguage.googleapis.com` with `google_search` grounding tool
- **Fallbacks**: `gemini-2.5-flash-lite` → `gemini-1.5-flash`
- **API Key**: Widget `gemini_api_key` or secret `upsc-bot-secrets/google-ai-api-key`
- **Cost**: ~$0/day with $400 Google AI credit balance

**12-Step Pipeline:**
1. Memory Injection — reads recent stories, groups by topic_cluster+keywords
2. Pass 1: Broad Fetch — Gemini + google_search → 3-5 diverse CA stories
3. Post-Fetch Dedup — 3-check: cluster diversity → keyword overlap → title-keyword cross-check
4. Dual-Output Parse — human brief + structured JSON (schema v1.0.0)
5. Delta Writes — `ca_runs`, `stories` (UPSERT on date+slug), `story_traps`
6. Pass 2: Deep Analysis — top 3 stories → PYQ patterns, mains skeletons, textbook links
7. Geography Enrichment — auto-detects geo stories → map, strategic importance
8. RAG Ingest — contextual chunks MERGEd into `contextual_chunks`
9. Embedding — `databricks-qwen3-embedding-0-6b` for new CA chunks
10. FAISS Rebuild — `IndexFlatIP` from ALL 80,854+ embedded_chunks → Volume
11. Obsidian Export — enhanced markdown with Deep Analysis + Geography + PYQ Match

## THE 5 TRAP TYPES (v2 Taxonomy)

| Type | Description | Example |
|------|-------------|---------|
| FACTUAL_CONFUSION | Mixing similar schemes/articles | Confusing Article 356 with 365 |
| DATE_ERROR | Wrong year for event/judgment | Sarkaria Commission: 1983 not 1988 |
| CONFLATION | Treating distinct things as same | Mixing NAM with Panchsheel |
| PARTIAL_FACT | Knowing part, missing caveat | Art 356 without Bommai safeguards |
| SCOPE_ERROR | Overstating/understating reach | Assuming GST covers petroleum |

## AI TOOLS FOR TELUGU UPSC LEARNING

| Tool | Best For | Notes |
|------|----------|-------|
| **Google Gemini** | Telugu poetry analysis, అలంకారాలు | Best multilingual model for Telugu; also powers NB6 CA |
| **Claude Sonnet 4** | Practice generation, answer evaluation | Powers NB7 8 practice modes via ai_query |
| **Sarvam AI** | Telugu translation, summarization | Indian AI, Telugu-first models |
| **Bhashini** | Govt translation platform | English ↔ Telugu |
| **Google Lens** | Scanning handwritten Telugu notes | Best Telugu OCR |
| **NotebookLM** | Upload Telugu PDFs, get audio summaries | Powers NB8 podcast generation |

## DAILY PIPELINE TIMELINE

```
07:00 IST  NB6 runs → Gemini 2.5 Flash + google_search → 3-5 stories
07:01      stories, story_traps, deep_analysis, geography_context updated
07:05      CA note written to Volume: CA_YYYY-MM-DD.md
07:06      contextual_chunks: CA text chunked + embedded
07:08      FAISS rebuild: IndexFlatIP from 80,854+ vectors
           ──────────────────────────────────
08:00 IST  NB7 runs → ai_query (Claude Sonnet 4) → 8 modes
08:01-05   Modes 1-5: Q&A, KARL, MCQs, Ethics, Model Answers
08:06      Mode 6: Telugu Optional model answers
08:07      Mode 7: AI Tutor Brief (practice + memory hooks)
08:08      Mode 8: Phone Summary (emoji-formatted quick read)
           ──────────────────────────────────
08:30 IST  NB8 runs → NotebookLM/TTS → podcast + revision brief
08:45      Audio files written to Volume
           ──────────────────────────────────
09:00 IST  NB9 runs → GitHub sync
09:01      Notebooks, bot code, Obsidian vault pushed
09:02      Delta table snapshots (JSON) → diff-based skip for unchanged
09:05      Summary: pushed X files, skipped Y unchanged
           ──────────────────────────────────
09:30+     YOU: Open Obsidian → read CA → review traps → practice
           Listen to podcast, review phone summary
           Use Hermes bot for quick practice
```

## DATABRICKS SECRETS (upsc-bot-secrets scope)

All secrets stored in scope `upsc-bot-secrets` (15 total):
- **Google**: google-ai-key, google-oauth-client-id, google-oauth-client-secret, google-access-token, google-refresh-token
- **YouTube**: yt-oauth-client-id, yt-oauth-client-secret, yt-client-secret-json
- **Other**: gcloud-tts-key, notebooklm-storage-state, groq-api-key, github-pat, hermes-bot-token, main-bot-token, telegram-user-id

> **Note**: NB6 code references `google-ai-api-key` but the actual secret may be stored as `google-ai-key`. Verify with `dbutils.secrets.get("upsc-bot-secrets", "google-ai-key")`.

## RULES FOR AI ASSISTANTS
1. NEVER delete files without asking
2. NEVER modify CLAUDE.md without permission
3. NEVER create notes outside the vault structure
4. Always use Templates/ for new notes
5. Always update Accuracy_Tracker after PYQ sessions
6. Always cite specific Articles, Acts, and committee names
7. Be STRICT in evaluations — max ~65% (9.5/15) is excellent
8. Use the 5 trap types consistently
9. Cross-reference with static anchors (textbook chapters)
10. Prioritize remaining gaps: Agriculture depth, Internal Security, Disaster Management

## HOW TO HELP ME STUDY

### When I paste a question, do this:
1. Check if a relevant note exists in 02_Subjects/ or 03_PYQs/
2. Give a structured answer (Intro | Framework | Key points | Way forward)
3. Flag any traps from 04_Traps/Trap_Index.md that apply
4. Tell me which textbook chapter this connects to

### My current weak areas (update weekly):
- Agriculture — light coverage (1,077 chunks), need dedicated textbook
- Internal Security — minimal (45 chunks), need Ashok Kumar
- Disaster Management — could add NDMA guidelines
- Telugu Paper 2 prescribed texts — could use more dedicated text editions
- Answer writing — need more evaluations to activate Weakness Tracker

### Daily routine:
- 7 AM: NB6 runs (CA note appears in 01_Current_Affairs/)
- 8 AM: NB7 runs (8 practice modes including Telugu Optional)
- 8:30 AM: NB8 runs (podcast + audio briefs)
- 9 AM: NB9 runs (GitHub sync — vault auto-updates)
- 9:30 AM: Open Obsidian → read CA → review traps → practice → listen to podcast
- Then: write 1 answer in 06_Answer_Practice/, evaluate in NB4

### Current Exam Timeline:
- Target: UPSC CSE 2027
- Prelims: ~May 2027 (~13 months away) → focus breadth
- Mains: ~Sep 2027 (~17 months) → start answer writing now
- Optional: Telugu Literature (500 marks) → 8,518 chunks ready

## TUTOR MODE — HOW TO TEACH ME

### My Learning Style
- Explain like I'm 16 first, then layer UPSC depth on top
- Use STORIES and ANALOGIES — not bullet dumps
- Give me a MEMORY HOOK for every concept (one sticky image/phrase)
- After explaining, quiz me — don't wait for me to ask
- Connect EVERYTHING to: a current affair + a PYQ + a trap

### Story Format Template (use this every time)
1. THE STORY — real-world analogy or historical drama (3-5 lines)
2. THE CONCEPT — what it actually means, simply
3. THE UPSC LAYER — articles, cases, committees
4. THE TRAP — what most students get wrong
5. THE HOOK — one line I'll remember at 2 AM before exam
6. QUIZ ME — 2 questions, one easy, one MCQ-hard

### Session Format When I Say "Teaching Mode: [Topic]"
- Ask me: "What do you already know?" first
- Teach in 3 chunks max, then quiz before continuing
- If I get something wrong — don't just correct, re-story it
- Track what I struggled with → append to 02_Subjects/[subject]/_Session_Log.md

### First 3 Commands to Try
```
> List all files in 02_Subjects/ and tell me which subject folders have no notes yet
> Read today's CA note and give me: 3 flashcard Q&As, the most important mains angle, and any trap alerts
> Using the Answer_Practice template, create a new file in 06_Answer_Practice/GS2/ for "Finance Commission and Fiscal Federalism"
```

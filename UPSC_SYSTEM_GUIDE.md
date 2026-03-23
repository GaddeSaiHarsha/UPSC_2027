# CLAUDE.md — UPSC 2026 AI Study System (Complete Context)
# ═══════════════════════════════════════════════════════════
# Share this file with Claude Code, Claude API, or any AI assistant
# to give full context about the UPSC preparation system.
# Last updated: 2026-03-21 (Session 2)
# ═══════════════════════════════════════════════════════════

## WHO I AM
- **UPSC CSE 2027** aspirant | **Telugu Optional** (500 marks)
- MacBook Air (Apple Silicon) | Obsidian vault at `~/Desktop/UPSC_2026`
- Full AI-powered study pipeline on **Databricks** (Azure)
- Daily routine: 4 hours morning (7-11 AM IST)

## THE SYSTEM ARCHITECTURE

```
┌─────────────────── DATABRICKS CLOUD ────────────────────┐
│                                                          │
│  7:00 AM ─── NB6 CA Orchestrator v3.0 ────────────┐    │
│              │ Perplexity sonar-pro API             │    │
│              │ → stories, story_traps               │    │
│              │ → deep_analysis, geography_context    │    │
│              │ → contextual_chunks (CA daily)        │    │
│              │ → Obsidian CA note (.md on Volume)    │    │
│              └──────────────────────────────────────┘    │
│                                                          │
│  8:00 AM ─── NB7 Practice Generator ───────────────┐    │
│              │ 6 AI modes via ai_query (Llama 70B)  │    │
│              │ → Mains Q&A, KARL eval, MCQs         │    │
│              │ → Ethics case study, Model answers    │    │
│              │ → Telugu Optional model answers       │    │
│              └──────────────────────────────────────┘    │
│                                                          │
│  On-demand ── NB4 Examiner Agent (KARL pattern)         │
│               NB5 Weakness Tracker                       │
│               NB1-3 RAG Pipeline (ingest/embed/query)   │
│               Morning Dashboard (14 cells)               │
│                                                          │
│  Data ─────── 65,833 chunks in Delta tables             │
│               Vector Search index (Qwen3 1024-dim)      │
│               8 Delta tables in upsc_catalog.rag        │
│                                                          │
└──────────────────────────────────────────────────────────┘
                          │
                    8:15 AM sync
                    (Databricks CLI v2)
                          ▼
┌─────────────── MAC (OBSIDIAN VAULT) ────────────────────┐
│                                                          │
│  ~/Desktop/UPSC_2026/                                    │
│  ├── .obsidian/          (config + 9 plugins + theme)    │
│  ├── .claude/            (THIS FILE — AI context)        │
│  ├── 00_Dashboard/       (Home.md, Weekly_Review.md)     │
│  ├── 01_Current_Affairs/ (daily CA notes from NB6)       │
│  ├── 02_Subjects/        (9 subject folders)             │
│  ├── 03_PYQs/            (By_Subject, By_Year, Perf)     │
│  ├── 04_Traps/           (Trap_Index, seed_traps.csv)    │
│  ├── 05_Revision/        (Due_Today.md, spaced rep)      │
│  ├── 06_Answer_Practice/ (GS1-4, Essay, KARL_Scores)     │
│  ├── 07_Sync/            (sync script, launchd plist)    │
│  └── Templates/          (4 templates for notes)         │
│                                                          │
│  Plugins: Dataview, Calendar, Spaced Repetition,         │
│           Templater, Kanban, Heatmap Calendar,            │
│           Style Settings, Omnisearch, Excalidraw          │
│  Theme:   Minimal (dark)                                 │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

## DATABRICKS NOTEBOOKS (7 total)

| ID | Name | Schedule | Purpose |
|----|------|----------|---------|
| 4264351243244281 | NB1-3 RAG Pipeline | On-demand | PDF ingest → chunking → embedding → VS index |
| 2480902325137437 | NB4 Examiner Agent v2 | On-demand | KARL-pattern answer evaluation (weighted nuggets) |
| 2480902325137438 | NB5 Weakness Tracker | On-demand | Subject performance, missed nuggets, study plan |
| 3121042200670064 | NB6 CA Orchestrator v3.0 | 7 AM IST daily | Perplexity → stories → traps → deep analysis → Obsidian |
| 3121042200670073 | NB7 Practice Generator | 8 AM IST daily | 6 AI practice modes (Q&A, KARL, MCQ, Ethics, Model Answers, Telugu) |
| 3121042200670066 | Morning Dashboard | On-demand | 14-cell visual summary of pipeline + 4 AI cells |

## DELTA TABLES (upsc_catalog.rag.*)

### stories
Daily CA stories from Perplexity.
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

### contextual_chunks (65,833 rows)
The knowledge base — all textbook/PYQ/CA content chunked and contextualized.
```
chunk_id STRING, source_file STRING, subject STRING,
page_number INT, chunk_index INT,
text STRING (with context header), raw_text STRING,
context_header STRING, token_count INT,
ingested_at TIMESTAMP, doc_type STRING, exam_stage STRING
```

### embedded_chunks (65,833 rows)
Same chunks with Qwen3 embeddings for vector search.
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

## KNOWLEDGE BASE — 65,833 CHUNKS

| Subject | Chunks | Sources |
|---------|--------|---------|
| History | 13,924 | Spectrum, NCERTs, Bipan Chandra, Makkhan Lal, PYQs |
| PYQ | 9,866 | Mains GS1-4, Prelims 2011-2025, CSAT |
| Economy | 7,771 | Ramesh Singh, Economic Survey 2025-26, Budget |
| Geography | 7,441 | NCERTs, PMF Human + Physical Geography |
| Environment | 7,352 | Shankar IAS 8th ed, ForumIAS 1,488 MCQs, NCERTs |
| Polity | 6,461 | Laxmikanth 8th edition, NCERTs |
| Science & Tech | 4,515 | S&T 2025 textbook, ForumIAS 1,140 MCQs, PYQs, notes |
| Telugu Optional | 3,671 | Lakshmi Kanth (455), ఆంధ్ర మహాభారతం (792), Lit P1+P2 (329), PYQs (736), System guide (89) |
| Art & Culture | 1,432 | PYQs + 1 NCERT (gap — need Nitin Singhania) |
| Agriculture | 999 | PYQs only (gap — need textbook) |
| Current Affairs | 768 | Indian Express x4, NB6 daily notes |
| Strategy | 525 | Anudeep Durishetty AIR 1 strategies |
| Society | 524 | 2 NCERTs |
| IR | 223 | 1 NCERT (gap — need Pavneet Singh) |
| General Studies | 186 | Infographics |
| Syllabus | 175 | UPSC syllabus docs |

### GAPS TO FILL (upload PDFs to Volume, then ingest)
1. **Science & Tech** — Shankar IAS S&T (have overview + MCQs, need depth)
2. **Ethics (GS4)** — Lexicon Ethics 6th edition
3. **Art & Culture** — Nitin Singhania
4. **IR** — Pavneet Singh International Relations
5. **Internal Security** — Ashok Kumar
6. **Agriculture** — Shankar IAS Agriculture or Mrunal
7. **Society** — Ram Ahuja Indian Society

### TELUGU OPTIONAL — DETAILED GAP ANALYSIS
**Current: 3,671 chunks (Textbook:2,913 + PYQ:736 + System:89)**

| Syllabus Area | Status | What's Missing |
|---------------|--------|----------------|
| కవిత్రయం (Nannaya/Tikkana/Errana) | ✅ Good | Errana ఆరణ్యపర్వం analysis |
| ప్రబంధ యుగం (Srinatha/Pothana/Vemana) | ⚠️ Partial | Pothana భాగవతం, Vemana శతకం dedicated texts |
| ఆధునిక సాహిత్యం (Modern) | ❌ Weak | Kanyasulkam, Maha Prasthanam, modern anthology |
| వ్యాకరణం & ఛందస్సు (Grammar/Prosody) | ❌ Zero | అప్పకవీయం, ఛందోదర్పణం, బాలవ్యాకరణం |
| అలంకార శాస్త్రం (Rhetoric) | ❌ Zero | అప్పకవీయం alankara section |
| Paper 2 prescribed texts | ⚠️ Partial | Need actual prescribed text editions |
| PYQ model answers | ✅ Good | 736 chunks, keep adding yearly |

**Top 10 Telugu Resources Needed:**
1. అప్పకవీయం (Appakaviyam) — grammar+prosody bible
2. పోతన భాగవతం (Pothana Bhagavatam) — prescribed text
3. వేమన శతకం with commentary — social criticism
4. కన్యాశుల్కం by Gurajada — modern drama
5. మహాప్రస్థానం by Sri Sri — revolutionary poetry
6. తెలుగు సాహిత్య చరిత్ర by Arudra — best literature history
7. ఛందోదర్పణం — prosody reference
8. అల్లసాని పెద్దన మనుచరిత్ర — first ప్రబంధం
9. Telugu Academy BA/MA textbook — full syllabus coverage
10. బాలవ్యాకరణం — grammar reference

## 6 PRACTICE MODES (NB7 — Daily 8 AM IST)

| # | Mode | Input | Output |
|---|------|-------|--------|
| 1 | **Knowledge Q&A** | Top CA story + 65K textbook chunks | 15-mark Mains answer with Article citations |
| 2 | **KARL Answer Evaluation** | Today's CA chunks | Auto question → sample answer → strict scoring → model answer |
| 3 | **Prelims MCQs** | Stories + story_traps | 5 MCQs with trap-based wrong options |
| 4 | **Ethics Case Study (GS4)** | CA stories + Ethics PYQs | Stakeholder map → thinkers → dilemma → model answer |
| 5 | **Mains Model Answers** | deep_analysis + geography + traps | Cross-subject map → structured answers → textbook anchors |
| 6 | **Telugu Optional (P1 & P2)** | 3,671 Telugu chunks (PYQ + textbooks) | 5 PYQ model answers → approach + తెలుగు సాహిత్య పదాలు + scoring tips |

## OBSIDIAN VAULT STRUCTURE

```
~/Desktop/UPSC_2026/
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
├── .claude/CLAUDE.md             # THIS FILE (AI context)
│
├── 00_Dashboard/
│   ├── Home.md                   # Command center (65,833 chunks, pipeline status)
│   └── Weekly_Review.md          # Weekly stats template
│
├── 01_Current_Affairs/
│   ├── CA_Master_Index.md        # Index of all CA notes
│   └── 2026/
│       └── 03-March/
│           ├── CA_2026-03-20.md  # Auto-generated by NB6
│           └── CA_2026-03-21.md  # Latest CA
│
├── 02_Subjects/                  # One folder per subject
│   ├── Economy/
│   ├── Environment/
│   ├── Ethics/
│   ├── Geography/
│   ├── History/
│   ├── IR/
│   ├── Polity/
│   ├── Science_Tech/
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
└── Templates/
    ├── Topic_Note.md             # For new subject notes
    ├── Answer_Practice.md        # For answer writing practice
    ├── PYQ_Extract.md            # For PYQ analysis
    └── Weekly_Review.md          # For weekly reviews
```

## INSTALLED PLUGINS — HOW TO USE EACH

### 1. Dataview (query notes like SQL)
```dataview
// List all CA notes this month
LIST FROM "01_Current_Affairs/2026"
WHERE file.cday >= date(2026-03-01)
SORT file.name DESC
```
```dataview
// Count notes by folder
TABLE length(rows) AS Count
FROM ""
GROUP BY file.folder
```

### 2. Calendar (sidebar calendar)
- Click calendar icon in right sidebar
- Days with CA notes show dots
- Click any day → opens/creates that day's CA note

### 3. Spaced Repetition (flashcards)
```
#card
Q: What is Article 356?
A: President's Rule — allows Centre to assume state government functions
on grounds of constitutional breakdown (Sarkaria Commission cautions
against misuse; S.R. Bommai judgment mandates floor test)
```
- Review: `Cmd+P` → "Spaced Repetition: Review flashcards"
- Cards auto-schedule using SM-2 algorithm (like Anki)

### 4. Templater (dynamic templates)
- `<% tp.date.now("YYYY-MM-DD") %>` — today's date
- `<% tp.file.title %>` — current file name
- Insert: `Cmd+P` → "Templater: Insert template"

### 5. Kanban (study tracking boards)
- `Cmd+P` → "Kanban: New board"
- Columns: Not Started | Reading | Revising | Mastered

### 6. Heatmap Calendar — GitHub-style streak tracker
### 7. Style Settings — theme customization via Minimal
### 8. Omnisearch — `Cmd+Shift+O` — full-text search across vault
### 9. Excalidraw — `Cmd+P` → "Excalidraw: Create new drawing" — diagrams

## CLAUDE CODE COMMANDS (use in terminal)

### `/daily`
Open today's CA note, summarize stories, quiz on traps, suggest static anchors

### `/pyq quiz [SUBJECT] [N]`
Select N random PYQs, ask one-by-one, evaluate, update Accuracy_Tracker

### `/revision due`
Find all notes with `next_review` ≤ today, list by priority

### `/weekly`
Count stories/traps/PYQs this week, generate summary, set focus areas

### `Create note on [TOPIC]`
Use Topic_Note template, check Trap_Index, create in correct subject folder

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
| **Google Gemini** | Telugu poetry analysis, అలంకారాలు | Best multilingual model for Telugu |
| **Claude Code** | Study planning, answer evaluation | Already installed on Mac |
| **Sarvam AI** | Telugu translation, summarization | Indian AI, Telugu-first models |
| **Bhashini** | Govt translation platform | English ↔ Telugu |
| **Google Lens** | Scanning handwritten Telugu notes | Best Telugu OCR |
| **NotebookLM** | Upload Telugu PDFs, get audio summaries | Supports multilingual |

## DATABRICKS CONNECTION

- **Host**: https://adb-7405615460529826.6.azuredatabricks.net
- **CLI Profile**: `upsc` (Databricks CLI v2 via Homebrew)
- **Volume**: `dbfs:/Volumes/upsc_catalog/rag/obsidian_ca/UPSC_2026/`
- **IMPORTANT**: CLI needs `dbfs:` prefix for Volume paths
- **Sync**: `databricks --profile upsc fs cp -r dbfs:/Volumes/upsc_catalog/rag/obsidian_ca/UPSC_2026/ ~/Desktop/UPSC_2026/ --overwrite`

## DAILY PIPELINE TIMELINE

```
07:00 IST  NB6 runs → Perplexity API → 4-6 stories
07:01      stories, story_traps, deep_analysis, geography_context updated
07:05      CA note written to Volume: CA_YYYY-MM-DD.md
07:06      contextual_chunks: CA text chunked + embedded
           ──────────────────────────────────
08:00 IST  NB7 runs → ai_query (Llama 70B) → 6 modes
08:01-05   Modes 1-5: Q&A, KARL, MCQs, Ethics, Model Answers
08:06      Mode 6: Telugu Optional model answers
           ──────────────────────────────────
08:15 IST  launchd syncs vault to Mac
08:16      Obsidian auto-refreshes (new CA note appears)
           ──────────────────────────────────
08:30      YOU: Open Obsidian → read CA → review traps → practice
```

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
10. Prioritize gaps: Ethics, Art & Culture, IR, Telugu Grammar


## HOW TO HELP ME STUDY

### When I paste a question, do this:
1. Check if a relevant note exists in 02_Subjects/ or 03_PYQs/
2. Give a structured answer (Intro | Framework | Key points | Way forward)
3. Flag any traps from 04_Traps/Trap_Index.md that apply
4. Tell me which textbook chapter this connects to

### My current weak areas (update weekly):
- Ethics — zero notes yet (need Lexicon Ethics textbook)
- Art & Culture — thin coverage (need Nitin Singhania)
- Telugu Grammar & Prosody — CRITICAL gap (need అప్పకవీయం)
- Answer writing — started, 1 evaluation so far

### Daily routine:
- 7 AM: NB6 runs (CA note appears in 01_Current_Affairs/)
- 8 AM: NB7 runs (6 practice modes + Telugu Optional)
- 8:15 AM: Vault auto-syncs to Mac
- 8:30 AM: I open Claude Code here and review the note
- Then: write 1 answer in 06_Answer_Practice/, evaluate in NB4

### Current Exam Timeline:
- Target: UPSC CSE 2027
- Prelims: ~May 2027 (14 months away) → focus breadth
- Mains: ~Sep 2027 (18 months) → start answer writing now
- Optional: Telugu Literature (500 marks) → dedicated notebook ready

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

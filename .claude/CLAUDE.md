# CLAUDE.md — UPSC 2026 AI Study System (Complete Context)
# ═══════════════════════════════════════════════════════════
# Share this file with Claude Code, Claude API, or any AI assistant
# to give full context about the UPSC preparation system.
# Last updated: 2026-03-21 (Session 5 — Post Full Gap-Fill)
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
│  Data ─────── 80,800 chunks in Delta tables             │
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
| 138096049883218 | Telugu Optional Study System | On-demand | OCR pipeline + AI study cells |

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

### contextual_chunks (80,800 rows)
The knowledge base — all textbook/PYQ/CA content chunked and contextualized.
```
chunk_id STRING, source_file STRING, subject STRING,
page_number INT, chunk_index INT,
text STRING (with context header), raw_text STRING,
context_header STRING, token_count INT,
ingested_at TIMESTAMP, doc_type STRING, exam_stage STRING
```

### embedded_chunks (80,800 rows)
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

## KNOWLEDGE BASE — 80,800 CHUNKS

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
| Current Affairs | 768 | Indian Express x4, Dec2025 NewsClips, NB6 daily notes |
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

## 6 PRACTICE MODES (NB7 — Daily 8 AM IST)

| # | Mode | Input | Output |
|---|------|-------|--------|
| 1 | **Knowledge Q&A** | Top CA story + 80K textbook chunks | 15-mark Mains answer with Article citations |
| 2 | **KARL Answer Evaluation** | Today's CA chunks | Auto question → sample answer → strict scoring → model answer |
| 3 | **Prelims MCQs** | Stories + story_traps | 5 MCQs with trap-based wrong options |
| 4 | **Ethics Case Study (GS4)** | CA stories + Ethics 1,111 chunks | Stakeholder map → thinkers → dilemma → model answer |
| 5 | **Mains Model Answers** | deep_analysis + geography + traps | Cross-subject map → structured answers → textbook anchors |
| 6 | **Telugu Optional (P1 & P2)** | 8,518 Telugu chunks (PYQ + textbooks) | 5 PYQ model answers → approach + తెలుగు సాహిత్య పదాలు + scoring tips |

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
│   ├── Home.md                   # Command center (80,800 chunks, pipeline status)
│   └── Weekly_Review.md          # Weekly stats template
│
├── 01_Current_Affairs/
│   ├── CA_Master_Index.md        # Index of all CA notes
│   └── 2026/03-March/            # Auto-generated by NB6
│
├── 02_Subjects/                  # One folder per subject
│   ├── Economy/ Environment/ Ethics/ Geography/
│   ├── History/ IR/ Polity/ Science_Tech/
│   └── Telugu_Optional/
│
├── 03_PYQs/                      # By_Subject, By_Year, My_Performance
├── 04_Traps/                     # Trap_Index.md + seed_traps.csv
├── 05_Revision/                  # Due_Today.md (spaced repetition)
├── 06_Answer_Practice/           # GS1-4, Essay, KARL_Scores.md
├── 07_Sync/                      # sync script + launchd plist
└── Templates/                    # 4 templates
```

## INSTALLED PLUGINS — HOW TO USE EACH

### 1. Dataview (query notes like SQL)
```dataview
LIST FROM "01_Current_Affairs/2026" WHERE file.cday >= date(2026-03-01) SORT file.name DESC
```

### 2. Calendar — click sidebar icon, days with CA notes show dots
### 3. Spaced Repetition — `#card` tag, review via `Cmd+P` → SM-2 scheduling
### 4. Templater — `<% tp.date.now("YYYY-MM-DD") %>`, insert via `Cmd+P`
### 5. Kanban — columns: Not Started | Reading | Revising | Mastered
### 6. Heatmap Calendar — GitHub-style streak tracker
### 7. Style Settings — Minimal theme customization
### 8. Omnisearch — `Cmd+Shift+O` — full-text search across vault
### 9. Excalidraw — diagrams and concept maps

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
10. Prioritize remaining gaps: Agriculture depth, Internal Security

## HOW TO HELP ME STUDY

### When I paste a question, do this:
1. Check if a relevant note exists in 02_Subjects/ or 03_PYQs/
2. Give a structured answer (Intro | Framework | Key points | Way forward)
3. Flag any traps from 04_Traps/Trap_Index.md that apply
4. Tell me which textbook chapter this connects to

### My current weak areas (update weekly):
- Agriculture — light coverage, need textbook depth
- Internal Security — minimal (45 chunks), need Ashok Kumar
- Answer writing — started, need 10+ evaluations to activate Weakness Tracker
- Telugu Paper 2 prescribed texts — could use more dedicated text editions

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

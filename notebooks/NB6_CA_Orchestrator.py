# Databricks notebook source
# DBTITLE 1,NB6 CA Orchestrator — Header
# MAGIC %md
# MAGIC # NB6: Current Affairs Orchestrator Pipeline v3.2
# MAGIC ### Perplexity sonar-pro → Two-Pass Analysis → Delta → RAG Pipeline → FAISS → Obsidian
# MAGIC
# MAGIC **v3.2 Changes (2026-04-04): Inclusion-Based Steering + Cluster Diversity Fix**
# MAGIC - **Root Cause**: v3.1's "ABSOLUTE PROHIBITION" approach failed because (a) word-overlap grouping was too fragile, (b) LLMs ignore exclusion lists, (c) `search_recency_filter=day` always returns trending topics.
# MAGIC - **Fix 1 — DO-Cover-Y Prompt**: Replaced "DON'T cover X" with "DO cover Y". Prompt now leads with PRIORITY AREAS (under-covered GS topics) to steer Perplexity toward fresh domains.
# MAGIC - **Fix 2 — Topic-Cluster Grouping**: Memory injection now groups by `topic_cluster` field + keyword-set overlap (>40%) instead of fragile 40%-word-overlap on first-6-title-words.
# MAGIC - **Fix 3 — Cluster Diversity Enforcement**: System prompt and post-fetch dedup both enforce unique `topic_cluster` per story per day. No two stories can share the same cluster.
# MAGIC - **Fix 4 — Keyword-Set Dedup**: Post-fetch dedup now uses story's `keywords` JSON array (not title words) for overlap scoring. Three-check pipeline: cluster diversity → keyword overlap → title-keyword cross-check.
# MAGIC - **Fix 5 — MERGE Key Fix**: Stories MERGE changed from `(date, story_id)` to `(date, slug)` with UPSERT. Prevents duplicate story_1 entries on re-runs.
# MAGIC
# MAGIC **v3.1 Changes (2026-03-30): 3-Layer Deduplication Fix** *(superseded by v3.2)*
# MAGIC - ~~Layer 1 — Topic-Grouped Memory Injection~~
# MAGIC - ~~Layer 2 — Prompt Hard-Block Language~~
# MAGIC - ~~Layer 3 — Post-Fetch Python Dedup~~
# MAGIC
# MAGIC **Pipeline Steps (end-to-end):**
# MAGIC 1. **Memory Injection** — Reads recent stories, groups by topic_cluster+keywords, builds BLOCK list + SUGGESTED AREAS
# MAGIC 2. **Pass 1: Broad Fetch** — Perplexity `sonar-pro` fetches 3–5 DIVERSE CA stories (`recency=day`), steered toward under-covered areas
# MAGIC 3. **Post-Fetch Dedup** — 3-check pipeline: cluster diversity → keyword-set overlap → title-keyword cross-check (fallback to `week` if <2 survive)
# MAGIC 4. **Dual-Output Parse** — Splits response into human brief + structured JSON (schema v1.0.0)
# MAGIC 5. **Delta Writes** — `ca_runs`, `stories` (UPSERT on date+slug), `story_traps` tables with MERGE idempotency
# MAGIC 6. **Pass 2: Deep Analysis** — Top 3 stories → sonar-pro again for PYQ patterns, prelims traps, mains skeletons, textbook links
# MAGIC 7. **Geography Enrichment** — Auto-detects geo stories → map locations, strategic importance
# MAGIC 8. **RAG Ingest** — Creates contextual chunks and MERGEs into `contextual_chunks`
# MAGIC 9. **Embedding** — Calls `databricks-qwen3-embedding-0-6b` for new CA chunks
# MAGIC 10. ~~**VS Index Sync**~~ — *DEPRECATED 2026-03-23: replaced by FAISS rebuild in Step 10*
# MAGIC 11. **FAISS Rebuild** — Rebuilds `IndexFlatIP` from ALL 80,808 embedded_chunks → Volume
# MAGIC 12. **Obsidian Export** — Enhanced markdown with Deep Analysis + Geography callouts + PYQ Match
# MAGIC
# MAGIC **Schedule:** Daily at 7 AM IST via [UPSC Daily CA Orchestrator](#job-1121120519823159)
# MAGIC
# MAGIC **Cost:** \~$0.01–0.03/day (3–4 sonar-pro calls + Qwen3 embeddings)

# COMMAND ----------

# DBTITLE 1,NB6 CA Orchestrator — Header
# MAGIC %md
# MAGIC # NB6: Current Affairs Orchestrator Pipeline v3.2
# MAGIC ### Perplexity sonar-pro → Two-Pass Analysis → Delta → RAG Pipeline → FAISS → Obsidian
# MAGIC
# MAGIC **v3.2 Changes (2026-04-04): Inclusion-Based Steering + Cluster Diversity Fix**
# MAGIC - **Root Cause**: v3.1's "ABSOLUTE PROHIBITION" approach failed because (a) word-overlap grouping was too fragile, (b) LLMs ignore exclusion lists, (c) `search_recency_filter=day` always returns trending topics.
# MAGIC - **Fix 1 — DO-Cover-Y Prompt**: Replaced "DON'T cover X" with "DO cover Y". Prompt now leads with PRIORITY AREAS (under-covered GS topics) to steer Perplexity toward fresh domains.
# MAGIC - **Fix 2 — Topic-Cluster Grouping**: Memory injection now groups by `topic_cluster` field + keyword-set overlap (>40%) instead of fragile 40%-word-overlap on first-6-title-words.
# MAGIC - **Fix 3 — Cluster Diversity Enforcement**: System prompt and post-fetch dedup both enforce unique `topic_cluster` per story per day. No two stories can share the same cluster.
# MAGIC - **Fix 4 — Keyword-Set Dedup**: Post-fetch dedup now uses story's `keywords` JSON array (not title words) for overlap scoring. Three-check pipeline: cluster diversity → keyword overlap → title-keyword cross-check.
# MAGIC - **Fix 5 — MERGE Key Fix**: Stories MERGE changed from `(date, story_id)` to `(date, slug)` with UPSERT. Prevents duplicate story_1 entries on re-runs.
# MAGIC
# MAGIC **v3.1 Changes (2026-03-30): 3-Layer Deduplication Fix** *(superseded by v3.2)*
# MAGIC - ~~Layer 1 — Topic-Grouped Memory Injection~~
# MAGIC - ~~Layer 2 — Prompt Hard-Block Language~~
# MAGIC - ~~Layer 3 — Post-Fetch Python Dedup~~
# MAGIC
# MAGIC **Pipeline Steps (end-to-end):**
# MAGIC 1. **Memory Injection** — Reads recent stories, groups by topic_cluster+keywords, builds BLOCK list + SUGGESTED AREAS
# MAGIC 2. **Pass 1: Broad Fetch** — Perplexity `sonar-pro` fetches 3–5 DIVERSE CA stories (`recency=day`), steered toward under-covered areas
# MAGIC 3. **Post-Fetch Dedup** — 3-check pipeline: cluster diversity → keyword-set overlap → title-keyword cross-check (fallback to `week` if <2 survive)
# MAGIC 4. **Dual-Output Parse** — Splits response into human brief + structured JSON (schema v1.0.0)
# MAGIC 5. **Delta Writes** — `ca_runs`, `stories` (UPSERT on date+slug), `story_traps` tables with MERGE idempotency
# MAGIC 6. **Pass 2: Deep Analysis** — Top 3 stories → sonar-pro again for PYQ patterns, prelims traps, mains skeletons, textbook links
# MAGIC 7. **Geography Enrichment** — Auto-detects geo stories → map locations, strategic importance
# MAGIC 8. **RAG Ingest** — Creates contextual chunks and MERGEs into `contextual_chunks`
# MAGIC 9. **Embedding** — Calls `databricks-qwen3-embedding-0-6b` for new CA chunks
# MAGIC 10. ~~**VS Index Sync**~~ — *DEPRECATED 2026-03-23: replaced by FAISS rebuild in Step 10*
# MAGIC 11. **FAISS Rebuild** — Rebuilds `IndexFlatIP` from ALL 80,808 embedded_chunks → Volume
# MAGIC 12. **Obsidian Export** — Enhanced markdown with Deep Analysis + Geography callouts + PYQ Match
# MAGIC
# MAGIC **Schedule:** Daily at 7 AM IST via [UPSC Daily CA Orchestrator](#job-1121120519823159)
# MAGIC
# MAGIC **Cost:** \~$0.01–0.03/day (3–4 sonar-pro calls + Qwen3 embeddings)

# COMMAND ----------

# DBTITLE 1,Configuration
# -- CONFIGURATION -------------------------------------------------------------------------------
import json, requests, time, re
from datetime import date, timedelta, datetime, timezone
from pyspark.sql import functions as F, Row
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, TimestampType, ArrayType, FloatType

# -- Perplexity API Key (widget first, then Secrets fallback) --
# Widget key takes priority so you can paste a fresh key without updating Secrets
PERPLEXITY_API_KEY = ""
try:
    _widget_key = dbutils.widgets.get("perplexity_api_key")
    if _widget_key and _widget_key.startswith("pplx-"):
        PERPLEXITY_API_KEY = _widget_key
        print("\u2705 Perplexity API key loaded from widget")
except Exception:
    pass

if not PERPLEXITY_API_KEY:
    try:
        PERPLEXITY_API_KEY = dbutils.secrets.get("azure-ocr", "perplexity-api-key")
        print("\u2705 Perplexity API key loaded from Databricks Secrets")
    except Exception:
        pass

if not PERPLEXITY_API_KEY:
    print("\u26a0\ufe0f  Perplexity API key not found!")
    print("   Option 1: Paste your key into the 'perplexity_api_key' widget at the top of this notebook")
    print("   Option 2: Add to Secrets (for scheduled runs):")
    print('            databricks secrets put-secret azure-ocr perplexity-api-key --string-value "pplx-xxxx"')
    print("\n   Get your key: https://www.perplexity.ai/settings/api")

# Catalog / Schema (matches RAG Pipeline NB1-3)
CATALOG         = "upsc_catalog"
SCHEMA          = "rag"

# Tables
CA_RUNS_TABLE   = f"{CATALOG}.{SCHEMA}.ca_runs"
STORIES_TABLE   = f"{CATALOG}.{SCHEMA}.stories"
TRAPS_TABLE     = f"{CATALOG}.{SCHEMA}.story_traps"
CHUNKS_TABLE    = f"{CATALOG}.{SCHEMA}.contextual_chunks"
EMBED_TABLE     = f"{CATALOG}.{SCHEMA}.embedded_chunks"

# Volumes
OBSIDIAN_VOLUME = f"/Volumes/{CATALOG}/{SCHEMA}/obsidian_ca"
DOCS_VOLUME     = f"/Volumes/{CATALOG}/{SCHEMA}/documents"

# Embedding (same model as RAG Pipeline Phase 2)
EMBEDDING_MODEL = "databricks-qwen3-embedding-0-6b"
EMBEDDING_DIM   = 1024

# FAISS Index (rebuilt daily in Step 9, replaces VS Classic as of 2026-03-23)
FAISS_INDEX_PATH = f"{DOCS_VOLUME}/upsc_faiss.index"
FAISS_META_PATH  = f"{DOCS_VOLUME}/upsc_faiss_meta.pkl"

# Parameters
TODAY              = date.today().isoformat()
LOOKBACK_DAYS      = 7
TRAP_LOOKBACK_DAYS = 60

print(f"\u2705 Config loaded | Date: {TODAY} | Catalog: {CATALOG}.{SCHEMA}")
print(f"   Tables: ca_runs, stories, story_traps, contextual_chunks, embedded_chunks")
print(f"   Embedding: {EMBEDDING_MODEL} ({EMBEDDING_DIM}-dim)")
print(f"   FAISS Index: {FAISS_INDEX_PATH}")

# COMMAND ----------

# DBTITLE 1,Setup: Create CA Tables If Not Exist
# MAGIC %sql
# MAGIC -- Create CA-specific tables (idempotent)
# MAGIC -- contextual_chunks and embedded_chunks already exist from RAG Pipeline
# MAGIC
# MAGIC CREATE TABLE IF NOT EXISTS upsc_catalog.rag.ca_runs (
# MAGIC   run_date        STRING     COMMENT 'ISO date of the CA run',
# MAGIC   generated_at    STRING     COMMENT 'UTC timestamp of generation',
# MAGIC   raw_output      STRING     COMMENT 'Full Perplexity response text',
# MAGIC   parsed_json     STRING     COMMENT 'Extracted JSON block as string',
# MAGIC   story_count     INT        COMMENT 'Number of stories extracted',
# MAGIC   schema_version  STRING     COMMENT 'Dual-output contract version'
# MAGIC ) USING DELTA
# MAGIC COMMENT 'Raw CA orchestrator run logs';
# MAGIC
# MAGIC CREATE TABLE IF NOT EXISTS upsc_catalog.rag.stories (
# MAGIC   date            STRING     COMMENT 'ISO date of the story',
# MAGIC   story_id        STRING     COMMENT 'story_1, story_2 etc.',
# MAGIC   slug            STRING     COMMENT 'Kebab-case short title',
# MAGIC   title           STRING     COMMENT 'Full story title',
# MAGIC   priority        STRING     COMMENT 'HIGH / MEDIUM / LOW',
# MAGIC   gs_papers       STRING     COMMENT 'JSON array of GS paper tags',
# MAGIC   topic_cluster   STRING     COMMENT 'Governance|Economy|Environment|IR|S&T|Society|Security|Ethics',
# MAGIC   keywords        STRING     COMMENT 'JSON array of keywords'
# MAGIC ) USING DELTA
# MAGIC COMMENT 'Structured CA stories for dedup and analytics';
# MAGIC
# MAGIC CREATE TABLE IF NOT EXISTS upsc_catalog.rag.story_traps (
# MAGIC   trap_id              STRING  COMMENT 'T001, T002 etc.',
# MAGIC   story_slug           STRING  COMMENT 'Links to stories.slug',
# MAGIC   subject              STRING  COMMENT 'Topic cluster',
# MAGIC   trap_type            STRING  COMMENT 'FACTUAL_CONFUSION|DATE_ERROR|CONFLATION|PARTIAL_FACT|SCOPE_ERROR',
# MAGIC   wrong_belief         STRING  COMMENT 'What students wrongly believe',
# MAGIC   correct_belief       STRING  COMMENT 'What is actually correct',
# MAGIC   severity             STRING  COMMENT 'HIGH / MEDIUM / LOW',
# MAGIC   reinforces_trap_id   STRING  COMMENT 'Links to a prior trap if reinforcing',
# MAGIC   created_date         STRING  COMMENT 'ISO date trap was created'
# MAGIC ) USING DELTA
# MAGIC COMMENT 'UPSC exam traps — wrong beliefs students carry';

# COMMAND ----------

# DBTITLE 1,Setup: Create Pass 2 Tables (v3.0)
# MAGIC %sql
# MAGIC -- v3.0 tables for two-pass CA synthesis + geography enrichment
# MAGIC
# MAGIC CREATE TABLE IF NOT EXISTS upsc_catalog.rag.deep_analysis (
# MAGIC   story_id          STRING  COMMENT 'FK to stories.story_id (e.g. story_1)',
# MAGIC   date              STRING  COMMENT 'ISO date of analysis',
# MAGIC   pyq_patterns      STRING  COMMENT 'JSON: PYQ patterns from 2013-2024 matching this story',
# MAGIC   traps_detailed    STRING  COMMENT 'JSON: detailed prelims traps (look-correct-but-wrong statements)',
# MAGIC   mains_skeleton    STRING  COMMENT 'JSON: complete 10-marker skeleton with intro/body/conclusion',
# MAGIC   static_links      STRING  COMMENT 'JSON: textbook chapter connections (Laxmikanth, Ramesh Singh, etc.)',
# MAGIC   created_date      STRING  COMMENT 'ISO date record was created'
# MAGIC ) USING DELTA
# MAGIC COMMENT 'Pass 2 deep analysis for top 3 CA stories per day';
# MAGIC
# MAGIC CREATE TABLE IF NOT EXISTS upsc_catalog.rag.geography_context (
# MAGIC   story_id              STRING  COMMENT 'FK to stories.story_id',
# MAGIC   date                  STRING  COMMENT 'ISO date',
# MAGIC   location_name         STRING  COMMENT 'Primary geographic feature name',
# MAGIC   map_description       STRING  COMMENT 'Exact location description for map marking',
# MAGIC   surrounding_context   STRING  COMMENT 'Surrounding countries/states/features',
# MAGIC   strategic_importance  STRING  COMMENT 'Why this location matters for India',
# MAGIC   created_date          STRING  COMMENT 'ISO date record was created'
# MAGIC ) USING DELTA
# MAGIC COMMENT 'Geography enrichment for CA stories with spatial relevance';

# COMMAND ----------

# DBTITLE 1,Setup: Ensure Obsidian Volume Exists
# Ensure the Obsidian CA output volume exists
import os

try:
    spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{SCHEMA}.obsidian_ca")
    print(f"\u2705 Volume ready: {OBSIDIAN_VOLUME}")
except Exception as e:
    print(f"\u26a0\ufe0f Volume creation skipped (may already exist): {e}")

# Verify write access
test_path = f"{OBSIDIAN_VOLUME}/.test_write"
try:
    with open(test_path, "w") as f:
        f.write("ok")
    os.remove(test_path)
    print("\u2705 Volume write access confirmed")
except Exception as e:
    print(f"\u274c Cannot write to {OBSIDIAN_VOLUME}: {e}")
    print("   Falling back to documents volume for Obsidian output")
    OBSIDIAN_VOLUME = DOCS_VOLUME

# COMMAND ----------

# DBTITLE 1,Prompt Engineering: System + User Prompt Builders
# ══════════════════════════════════════════════════════════════════════════
# PROMPT ENGINEERING — System prompt + dynamic user prompt builder
# v3.2: Inclusion-based steering + topic-cluster diversity enforcement
# ══════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are a UPSC Current Affairs Intelligence Officer with deep expertise in 
the UPSC Civil Services Examination pattern (Prelims + Mains GS Papers 1-4, Essay).

## YOUR EXPERTISE
- You know which current affairs become UPSC questions (policy implementation gaps, 
  constitutional tensions, governance failures, India's international positioning, 
  science with policy implications, environment-economy conflicts)
- You distinguish between noise (celebrity politics, pure sports) and signal (structural 
  economic shifts, new legislation, landmark judgments, India's treaty obligations)
- You know the UPSC examiner's preference: static anchors dressed in current clothing -- 
  every story should connect to syllabus topics the student must know permanently.

## DIVERSITY RULE (MOST IMPORTANT)
Your output is part of a DAILY series. The user will tell you which topics were already 
covered this week and which GS areas are UNDER-COVERED.

**Your #1 job is TOPIC DIVERSITY across the week.**
- PRIORITIZE the suggested under-covered areas — these are gaps in the student's weekly brief.
- If a topic was already covered (listed as "already covered"), SKIP IT entirely unless 
  there is a genuinely new development (new law passed, verdict delivered, war started/ended).
  A "new article about the same event" does NOT count.
- If you cannot find stories in the suggested areas, look for niche/emerging topics: 
  committee reports, statistical releases, regulatory changes, judicial appointments, 
  environmental clearances, tribal welfare updates, education policy changes.
- NEVER return more than 1 story from the same topic_cluster in a single day.
- If you can only find 3 genuinely diverse stories, return 3. Quality > quantity.

## TRAP GENERATION PRINCIPLES
Traps are not trivia -- they are specific wrong beliefs that cost marks:
- FACTUAL_CONFUSION: mixing up two similar schemes, articles, or committees
- DATE_ERROR: wrong year for a judgment, treaty, or policy launch
- CONFLATION: treating two distinct things as the same (e.g., NAC vs NITI Aayog)
- PARTIAL_FACT: knowing part of a provision but not the critical caveat
- SCOPE_ERROR: overstating or understating the reach of a law/policy

Severity guidance:
- HIGH: appears in Prelims MCQ distractors or Mains Part B answers
- MEDIUM: shows up in answer quality gaps
- LOW: minor nuance, worth knowing but not mark-critical

## OUTPUT DISCIPLINE
- Human brief comes FIRST -- flowing narrative, no bullet points, ~400 words
- JSON block comes LAST -- single fenced block, no text after it
- JSON must be valid -- no trailing commas, no comments inside the block
- story IDs must be sequential: "story_1", "story_2" etc.
- slug must be kebab-case, max 5 words.
- Every fact must be independently verifiable -- no hallucinated statistics.
- If unsure of a specific number/date, omit it rather than guess.
- Each story MUST have a DIFFERENT topic_cluster value from every other story in the output.

## RELEVANCE FILTER
Include a story only if it maps to at least one of:
GS1 (Indian History/Society/Geography), GS2 (Governance/Polity/IR), 
GS3 (Economy/Environment/S&T/Security), GS4 (Ethics), or Essay themes.
Exclude pure state politics, sports scores, and sub-national news with no policy implications."""


# JSON template as a static string (not inside the f-string) to avoid brace escaping hell
_JSON_TEMPLATE = """```json
{
  "schema_version": "1.0.0",
  "date": "DATE_PLACEHOLDER",
  "stories": [
    {
      "id": "story_1",
      "slug": "kebab-case-title",
      "title": "Full Story Title",
      "date": "DATE_PLACEHOLDER",
      "priority": "HIGH|MEDIUM|LOW",
      "relevance": "1-2 sentences on why this matters for UPSC",
      "gs_papers": ["GS2", "GS3"],
      "topic_cluster": "Governance|Economy|Environment|IR|S&T|Society|Security|Ethics",
      "keywords": ["keyword1", "keyword2"],
      "memory_hook": "One punchy sentence to remember this story",
      "facts": [
        {"statement": "Specific verifiable fact with numbers/names/dates", "source": "source name"}
      ],
      "static_anchors": ["Article 21", "Sarkaria Commission", "PMGSY"],
      "answer_skeleton": {
        "intro": "1-2 sentence intro framing the issue",
        "body_points": [
          "Point 1: ...",
          "Point 2: ...",
          "Point 3: ..."
        ],
        "conclusion_direction": "Forward-looking conclusion hint"
      },
      "traps": [
        {
          "trap_id": "TRAP_ID_PLACEHOLDER",
          "trap_type": "FACTUAL_CONFUSION|DATE_ERROR|CONFLATION|PARTIAL_FACT|SCOPE_ERROR",
          "wrong_belief": "What students wrongly believe",
          "correct_belief": "What is actually correct",
          "severity": "HIGH|MEDIUM|LOW",
          "reinforces_trap_id": null
        }
      ]
    }
  ]
}
```"""

# Fallback strings (kept outside f-string to avoid backslash-in-expression errors on Python 3.10)
_NO_STORIES_YET = "(none -- first run)"
_NO_TRAPS_YET = "(none yet)"


def build_user_prompt(today, recent_slugs_text, suggested_areas_text, traps_text, next_trap_num):
    """Build the dynamic user prompt with inclusion-based topic steering (v3.2)."""
    start_trap_id = f"T{next_trap_num:03d}"
    json_example = _JSON_TEMPLATE.replace("DATE_PLACEHOLDER", today).replace("TRAP_ID_PLACEHOLDER", start_trap_id)
    stories_memory = recent_slugs_text if recent_slugs_text else _NO_STORIES_YET
    traps_memory = traps_text if traps_text else _NO_TRAPS_YET
    suggested = suggested_areas_text if suggested_areas_text else "(Cover any UPSC-relevant area)"
    
    return f"""DATE: {today} (IST)

## YOUR PRIMARY MISSION: FILL THESE GAPS
{suggested}

These GS areas have NOT been covered this week. Your primary task is to find 
UPSC-relevant stories in these specific domains. Search for news in these areas FIRST.

## Already Covered This Week (skip these topics)
{stories_memory}

Stories matching already-covered topics will be auto-removed by our validation pipeline.
Do not waste tokens on them — they will be discarded.

## MEMORY: Active traps (T001 onward, last 60 days)
{traps_memory}
Next trap ID to assign: {start_trap_id}

## YOUR TASK
Find 3-5 DIVERSE stories for today's UPSC Current Affairs brief.

STEP 1: Search for stories in the PRIORITY AREAS listed above
STEP 2: If you found <3 stories from priority areas, broaden to other GS topics
STEP 3: Verify NONE of your stories overlap with the "Already Covered" list
STEP 4: Verify each story has a UNIQUE topic_cluster (no duplicates)

For each story (3-5 stories, each with a DIFFERENT topic_cluster):
- Map to GS Papers (GS1 / GS2 / GS3 / GS4 / Essay)
- Identify 1-3 static anchors (constitutional articles, committees, landmark judgments)
- Assign priority: HIGH / MEDIUM / LOW based on UPSC exam relevance
- Generate 1-2 TRAPS — common wrong beliefs students carry into this topic
- Write a memory hook (one punchy sentence)
- Write an answer skeleton (intro + 3-5 body points + conclusion direction)

## OUTPUT FORMAT (STRICT)
Output TWO sections in this exact order:

### SECTION 1 -- HUMAN BRIEF (plain text, ~400 words)
Write a clean daily brief for a UPSC aspirant. Narrative style. 
Cover each story in 2-3 sentences. End with a "Today's Static Angle" note.

### SECTION 2 -- JSON BLOCK
Immediately after the human brief, output a single JSON block (no other text after):

{json_example}
"""

print("\u2705 Prompt builders loaded (v3.2 — inclusion-based steering + cluster diversity)")
print("   Changes: DO-cover-Y replaces DON'T-cover-X, unique topic_cluster enforced, suggested areas injected")

# COMMAND ----------

# DBTITLE 1,Step 1: Memory Injection — Load Recent Stories + Traps
# ══════════════════════════════════════════════════════════════════════════
# STEP 1: MEMORY INJECTION (v3.2 — Topic-Cluster + Keyword-Set Dedup)
# Groups recent stories by topic_cluster field (deterministic, not fuzzy title words).
# Builds: (1) covered_topics block list, (2) suggested_areas for prompt steering
# Also builds keyword sets for post-fetch Python dedup in Step 2.
# ══════════════════════════════════════════════════════════════════════════

from collections import defaultdict

# All GS topic areas the pipeline should cover across a week
# Used to detect under-covered areas and steer Perplexity toward them
ALL_TOPIC_AREAS = [
    "Governance|Polity", "Economy", "Environment|Ecology", "IR",
    "S&T", "Society", "Security|Defence", "Ethics",
    "History|Culture", "Geography", "Education|NEP",
    "Health|Epidemics", "Agriculture|Food Security",
    "Judiciary|Legal", "Tribal|Welfare", "Digital|Cyber",
    "Space|ISRO", "Energy|Climate", "Labour|Employment",
    "Disaster Management"
]

# 1a. Recent stories (last 7 days) — grouped by topic_cluster + keywords
cutoff = (date.today() - timedelta(days=LOOKBACK_DAYS)).isoformat()
try:
    recent_stories_df = spark.sql(f"""
        SELECT date, slug, title, priority, topic_cluster, keywords
        FROM {STORIES_TABLE} 
        WHERE date >= '{cutoff}' 
        ORDER BY date DESC 
    """)
    rows = recent_stories_df.collect()
    
    # ── Group by normalized topic_cluster (primary) + keyword overlap (secondary) ──
    topic_groups = defaultdict(lambda: {"titles": [], "dates": set(), "keywords": set(), "slugs": set()})
    
    for r in rows:
        # Primary grouping key: normalize topic_cluster (sort pipe-separated values)
        cluster = r.topic_cluster or "Unknown"
        cluster_key = "|".join(sorted(set(c.strip() for c in cluster.split("|"))))
        
        # Parse keywords for this story
        story_keywords = set()
        try:
            kw_list = json.loads(r.keywords) if r.keywords else []
            story_keywords = {kw.lower().strip() for kw in kw_list if isinstance(kw, str) and len(kw) > 2}
        except: pass
        
        # Try to match to an existing group: same cluster OR >40% keyword overlap
        matched_key = None
        for existing_key, grp in topic_groups.items():
            existing_cluster = existing_key.split("::")[0]
            # Match 1: Same normalized cluster AND any keyword overlap
            if cluster_key == existing_cluster and grp["keywords"] and story_keywords & grp["keywords"]:
                matched_key = existing_key
                break
            # Match 2: Different cluster but >40% keyword overlap (cross-cluster duplication)
            if grp["keywords"] and story_keywords:
                overlap = len(story_keywords & grp["keywords"]) / max(len(story_keywords), 1)
                if overlap > 0.4:
                    matched_key = existing_key
                    break
        
        if matched_key:
            topic_groups[matched_key]["titles"].append(r.title)
            topic_groups[matched_key]["dates"].add(r.date)
            topic_groups[matched_key]["keywords"].update(story_keywords)
            topic_groups[matched_key]["slugs"].add(r.slug)
        else:
            # New group: cluster_key::first_slug
            group_key = f"{cluster_key}::{r.slug}"
            topic_groups[group_key]["titles"].append(r.title)
            topic_groups[group_key]["dates"].add(r.date)
            topic_groups[group_key]["keywords"].update(story_keywords)
            topic_groups[group_key]["slugs"].add(r.slug)
    
    # ── Build BLOCKED TOPICS (covered >= 2 days) with short canonical labels ──
    blocked_topics = []
    blocked_keywords_all = set()
    covered_cluster_keys = set()
    
    for key, grp in topic_groups.items():
        days_count = len(grp["dates"])
        cluster_part = key.split("::")[0]
        covered_cluster_keys.add(cluster_part)
        
        if days_count >= 2:  # Covered 2+ days = BLOCKED
            # Use SHORT canonical label, not full title
            short_label = grp["titles"][0][:80]
            top_keywords = sorted(grp["keywords"])[:5]
            blocked_topics.append(
                f"  - {short_label} [{cluster_part}] (covered {days_count}d, keywords: {', '.join(top_keywords)})"
            )
            blocked_keywords_all.update(grp["keywords"])
    
    # Remove overly common words from blocked keywords
    stop_words = {"india", "indian", "government", "policy", "state", "under", "from", "with", 
                  "that", "this", "into", "after", "near", "over", "about", "their", "also",
                  "upsc", "mains", "prelims", "exam", "new", "amid", "says", "india's",
                  "minister", "ministry", "national", "will", "year", "report", "data"}
    blocked_keywords_all -= stop_words
    
    # ── Build SUGGESTED AREAS (under-covered in last 7 days) ──
    suggested_areas = []
    for area in ALL_TOPIC_AREAS:
        area_parts = set(a.strip().lower() for a in area.split("|"))
        # Check if any covered cluster overlaps with this area
        is_covered = False
        for ck in covered_cluster_keys:
            ck_parts = set(c.strip().lower() for c in ck.split("|"))
            if area_parts & ck_parts:
                is_covered = True
                break
        if not is_covered:
            suggested_areas.append(area)
    
    # Build memory text for prompt (ASCII-safe, no surrogate emojis)
    if blocked_topics:
        recent_slugs_text = "Topics already covered (skip unless MAJOR new development):\n"
        recent_slugs_text += "\n".join(blocked_topics)
    else:
        recent_slugs_text = "(No stale topics -- all clear)"
    
    if suggested_areas:
        suggested_areas_text = ">>> PRIORITY AREAS (under-covered this week -- search for these):\n"
        suggested_areas_text += "\n".join(f"  [+] {area}" for area in suggested_areas[:8])
    else:
        suggested_areas_text = "(Good coverage across all areas this week -- find any genuinely new story)"
    
    print(f"\u2705 Memory: {len(rows)} recent stories -> {len(topic_groups)} unique topic groups")
    print(f"   [X] {len(blocked_topics)} topics BLOCKED (covered 2+ days)")
    print(f"   [K] {len(blocked_keywords_all)} blocked keywords for post-fetch dedup")
    print(f"   [>] {len(suggested_areas)} under-covered areas to suggest")
    for area in suggested_areas[:8]:
        print(f"      -> {area}")
    
except Exception as e:
    recent_slugs_text = "(No prior stories -- first run)"
    suggested_areas_text = "(First run -- cover any UPSC-relevant area)"
    blocked_keywords_all = set()
    topic_groups = {}
    print(f"\u26a0\ufe0f Stories table empty or missing (first run): {e}")

# 1b. Recent traps (last 60 days) for context
trap_cutoff = (date.today() - timedelta(days=TRAP_LOOKBACK_DAYS)).isoformat()
try:
    traps_df = spark.sql(f"""
        SELECT DISTINCT trap_id, subject, trap_type, wrong_belief, correct_belief, severity 
        FROM {TRAPS_TABLE} 
        WHERE created_date >= '{trap_cutoff}' 
        ORDER BY trap_id
    """)
    trap_rows = traps_df.collect()
    traps_text = "\n".join([
        f"- {r.trap_id} | {r.subject} | {r.trap_type} | WRONG: \"{r.wrong_belief}\" -> RIGHT: \"{r.correct_belief}\" | {r.severity}" 
        for r in trap_rows
    ])
    print(f"\u2705 Memory: {len(trap_rows)} active traps loaded (last {TRAP_LOOKBACK_DAYS} days)")
except Exception as e:
    traps_text = "(No traps yet)"
    print(f"\u26a0\ufe0f Traps table empty or missing (first run): {e}")

# 1c. Get next trap ID (prevents ID collisions across runs)
try:
    max_trap = spark.sql(f"SELECT MAX(trap_id) as max_id FROM {TRAPS_TABLE}").collect()[0][0]
    next_trap_num = int(max_trap.replace("T", "")) + 1 if max_trap else 1
except Exception:
    next_trap_num = 1  # First run ever

print(f"\u2705 Next trap ID: T{next_trap_num:03d}")

# COMMAND ----------

# DBTITLE 1,Step 2: Call Perplexity API (sonar-pro with web search)
# ======================================================================
# STEP 2: GEMINI API CALL (v3.9 -- maxOutputTokens 65536 for thinking headroom)
# Uses Gemini 2.5 Flash via generativelanguage.googleapis.com
# Auth: API key from notebook widget (same pattern as Perplexity key)
# Search: google_search tool (replaces deprecated googleSearchRetrieval)
# Note: Gemini 2.5 Flash uses thinking tokens from the output budget.
#   maxOutputTokens=65536 gives enough room for thinking + full JSON output.
# After fetch: Python dedup uses keyword arrays + topic_cluster matching
# ======================================================================

def _get_gemini_api_key():
    """Get Google AI API key: widget first, then Databricks Secrets fallback."""
    try:
        wk = dbutils.widgets.get("gemini_api_key")
        if wk and len(wk) > 10:
            return wk
    except Exception:
        pass
    try:
        return dbutils.secrets.get("upsc-bot-secrets", "google-ai-api-key")
    except Exception:
        pass
    raise ValueError(
        "Gemini API key not found!\n"
        "   Option 1: Paste key into 'gemini_api_key' widget at top of notebook\n"
        "   Option 2: Store in Secrets: upsc-bot-secrets/google-ai-api-key\n"
        "   Get your key: https://aistudio.google.com/apikey"
    )


def call_gemini(system_prompt, user_prompt, max_retries=3, use_search=True):
    """Call Gemini via Generative Language API with Google Search grounding."""
    api_key = _get_gemini_api_key()
    model = "gemini-2.5-flash"
    fallbacks = ["gemini-2.5-flash-lite", "gemini-1.5-flash"]
    
    headers = {"Content-Type": "application/json"}
    
    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": user_prompt}]}
        ],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 65536
        }
    }
    
    if use_search:
        payload["tools"] = [{"google_search": {}}]
    
    for attempt in range(max_retries):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        try:
            print(f"   Attempt {attempt+1}: {model} via Generative Language API (API key)")
            response = requests.post(url, headers=headers, json=payload, timeout=180)
            response.raise_for_status()
            result = response.json()
            # Gemini 2.5 may return multi-part responses: thought parts + output parts
            # Concatenate all non-thought text parts to get the full response
            parts = result["candidates"][0]["content"]["parts"]
            content = "".join(p["text"] for p in parts if "text" in p and not p.get("thought", False))
            if not content:
                content = "".join(p["text"] for p in parts if "text" in p)
            return content
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429:
                wait = 30 * (attempt + 1)
                print(f"   [!] Rate limited -- waiting {wait}s")
                time.sleep(wait)
            elif response.status_code == 404:
                if fallbacks:
                    next_model = fallbacks.pop(0)
                    print(f"   [!] 404: {model} not found. Falling back to {next_model}...")
                    model = next_model
                    continue
                else:
                    print(f"   [!] 404: {model} not found and no fallbacks left.")
                    raise
            elif response.status_code == 403:
                print(f"   [!] 403 Forbidden: {response.text[:400]}")
                raise
            else:
                print(f"   [!] HTTP {response.status_code}: {response.text[:300]}")
                raise
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                print(f"   [!] Timeout -- retrying")
                time.sleep(10)
            else:
                raise
        except (KeyError, IndexError) as e:
            print(f"   [!] Unexpected response format: {e}")
            print(f"       Response: {json.dumps(response.json(), indent=2)[:500]}")
            raise
    raise RuntimeError(f"Gemini failed after {max_retries} attempts (last model: {model})")


def parse_dual_output(raw_text):
    """Split response into human brief + structured JSON."""
    json_match = re.search(r'```(?:json|JSON)?\s*([\s\S]*?)\s*```', raw_text)
    if not json_match:
        json_match = re.search(r'(\{[\s\S]*"stories"[\s\S]*\})', raw_text)
    if not json_match:
        # Fallback: try parsing entire response as JSON (responseMimeType case)
        try:
            parsed = json.loads(raw_text)
            if "stories" in parsed:
                return "", parsed
        except (json.JSONDecodeError, TypeError):
            pass
        debug_path = f"{DOCS_VOLUME}/ca_debug_{TODAY}.txt"
        with open(debug_path, "w") as f:
            f.write(raw_text)
        raise ValueError(f"No JSON block found in response. Raw saved to {debug_path}")
    json_str = json_match.group(1).strip()
    parsed   = json.loads(json_str)
    human    = raw_text[:json_match.start()].strip()
    return human, parsed


def dedup_stories(stories, blocked_keywords, topic_groups):
    """
    Post-fetch deduplication v3.2: uses topic_cluster + keyword-set overlap.
    Returns (kept_stories, removed_stories).
    """
    if not blocked_keywords and not topic_groups:
        return stories, []
    blocked_groups = []
    for key, grp in topic_groups.items():
        if len(grp["dates"]) >= 2:
            cluster_part = key.split("::")[0]
            blocked_groups.append({"cluster": cluster_part, "keywords": grp["keywords"], "titles": grp["titles"]})
    kept, removed, seen_clusters = [], [], set()
    for story in stories:
        title = story.get("title", "")
        raw_cluster = story.get("topic_cluster", "Unknown")
        story_cluster = "|".join(sorted(set(c.strip() for c in raw_cluster.split("|"))))
        story_kws = {kw.lower().strip() for kw in story.get("keywords", []) if isinstance(kw, str)}
        if story_cluster in seen_clusters:
            removed.append(story)
            print(f"   [X] CLUSTER DUP: \"{title}\"")
            continue
        is_blocked = False
        for bg in blocked_groups:
            if bg["keywords"] and story_kws:
                overlap = len(story_kws & bg["keywords"]) / max(len(story_kws), 1)
                if overlap > 0.5:
                    is_blocked = True; print(f"   [X] KW BLOCKED: \"{title}\" ({overlap:.0%})"); break
            if story_cluster == bg["cluster"] and story_kws and bg["keywords"] and (story_kws & bg["keywords"]):
                is_blocked = True; print(f"   [X] CLUSTER+KW BLOCKED: \"{title}\""); break
        if is_blocked:
            removed.append(story); continue
        title_words = set(w.lower() for w in title.split() if len(w) > 3)
        if blocked_keywords:
            t_overlap = len(title_words & blocked_keywords) / max(len(title_words), 1)
            if t_overlap > 0.5:
                removed.append(story); print(f"   [X] TITLE-KW BLOCKED: \"{title}\""); continue
        kept.append(story); seen_clusters.add(story_cluster)
        print(f"   [+] NEW: \"{title}\" (cluster: {story_cluster})")
    return kept, removed


# -- PASS 1: Call Gemini with Google Search grounding --
user_prompt = build_user_prompt(TODAY, recent_slugs_text, suggested_areas_text, traps_text, next_trap_num)
print("[>>] Calling Gemini 2.5 Flash via Generative Language API (API key auth)...")
raw_output = call_gemini(SYSTEM_PROMPT, user_prompt, use_search=True)
print(f"\u2705 Response received: {len(raw_output):,} chars")

human_brief, ca_json = parse_dual_output(raw_output)
stories_raw = ca_json.get("stories", [])
if not isinstance(stories_raw, list) or len(stories_raw) == 0:
    raise ValueError(f"LLM returned no valid stories. Keys: {list(ca_json.keys())}")
print(f"\n[?] Gemini returned {len(stories_raw)} stories. Running post-fetch dedup...")

stories, removed_stories = dedup_stories(stories_raw, blocked_keywords_all, topic_groups)
print(f"\n[=] Dedup result: {len(stories)} kept, {len(removed_stories)} removed")

if len(stories) < 2:
    print(f"\n[!] Only {len(stories)} new stories. Making fallback call...")
    fallback_prompt = user_prompt + """\n\n## CRITICAL: YOUR FIRST ATTEMPT FAILED
All your stories were duplicates of previously covered topics.
You MUST find COMPLETELY DIFFERENT topics this time.
Search specifically for: committee reports, statistical releases, WHO/UNEP/IMF reports,
judicial appointments, environmental clearances, agricultural policy, defence exercises."""
    raw_output_2 = call_gemini(SYSTEM_PROMPT, fallback_prompt, use_search=True)
    _, ca_json_2 = parse_dual_output(raw_output_2)
    stories_2, _ = dedup_stories(ca_json_2.get("stories", []), blocked_keywords_all, topic_groups)
    existing_slugs = {s["slug"] for s in stories}
    for s in stories_2:
        if s["slug"] not in existing_slugs:
            stories.append(s); existing_slugs.add(s["slug"])
    raw_output = raw_output + "\n\n=== FALLBACK CALL ===\n" + raw_output_2
    print(f"\u2705 After fallback: {len(stories)} total new stories")

ca_json["stories"] = stories
if len(stories) == 0:
    raise ValueError("No new stories after deduplication.")

print(f"\n\u2705 Final: {len(stories)} stories | Schema: {ca_json.get('schema_version', 'unknown')}")
for s in stories:
    tc = len(s.get('traps', []))
    print(f"   * [{s['priority']}] {s['title']} ({tc} traps, cluster: {s.get('topic_cluster', '?')})")

# COMMAND ----------

# DBTITLE 1,Step 3: Write to Delta — ca_runs, stories, story_traps
# ══════════════════════════════════════════════════════════════════════════
# STEP 3: DELTA TABLE WRITES (MERGE for idempotency)
# v3.2: Stories MERGE key changed to (date, slug) + UPSERT support
# Safe to re-run — won't duplicate on same date/slug/trap_id
# ══════════════════════════════════════════════════════════════════════════

now_utc = datetime.now(timezone.utc)
now_utc_str = now_utc.isoformat()

# 3a. Write ca_runs (raw run log) — MERGE on run_date for idempotency on re-runs
run_row = {
    "run_date":       TODAY,
    "generated_at":   now_utc_str,
    "raw_output":     raw_output,
    "parsed_json":    json.dumps(ca_json),
    "story_count":    int(len(stories)),
    "schema_version": ca_json.get("schema_version", "1.0.0")
}
run_df = spark.createDataFrame([run_row])
run_df = run_df.withColumn("story_count", F.col("story_count").cast("int"))
run_df.createOrReplaceTempView("new_ca_run")
spark.sql(f"""
    MERGE INTO {CA_RUNS_TABLE} t
    USING new_ca_run n
    ON t.run_date = n.run_date
    WHEN MATCHED THEN UPDATE SET *
    WHEN NOT MATCHED THEN INSERT *
""")
print(f"\u2705 ca_runs: 1 row merged (run_date={TODAY})")

# 3b. Write stories — v3.2: MERGE on (date, slug) instead of (date, story_id)
# slug is the natural key (content-derived); story_id changes across re-runs
# Added WHEN MATCHED THEN UPDATE to handle re-runs properly
if stories:
    stories_rows = [{
        "date":          TODAY,
        "story_id":      s["id"],
        "slug":          s["slug"],
        "title":         s["title"],
        "priority":      s["priority"],
        "gs_papers":     json.dumps(s.get("gs_papers", [])),
        "topic_cluster": s.get("topic_cluster", ""),
        "keywords":      json.dumps(s.get("keywords", []))
    } for s in stories]

    spark.createDataFrame(stories_rows).createOrReplaceTempView("new_stories")
    spark.sql(f"""
        MERGE INTO {STORIES_TABLE} t 
        USING new_stories n 
        ON t.date = n.date AND t.slug = n.slug
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
    """)
    print(f"\u2705 stories: {len(stories_rows)} rows merged (key: date+slug)")

# 3c. Write story_traps (MERGE on trap_id)
all_traps = []
for s in stories:
    for t in s.get("traps", []):
        all_traps.append({
            "trap_id":           t["trap_id"],
            "story_slug":        s["slug"],
            "subject":           s.get("topic_cluster", ""),
            "trap_type":         t["trap_type"],
            "wrong_belief":      t["wrong_belief"],
            "correct_belief":    t.get("correct_belief", t.get("correct_fact", "")),
            "severity":          t["severity"],
            "reinforces_trap_id": t.get("reinforces_trap_id") or "",
            "created_date":      TODAY
        })

if all_traps:
    spark.createDataFrame(all_traps).createOrReplaceTempView("new_traps")
    spark.sql(f"""
        MERGE INTO {TRAPS_TABLE} t 
        USING new_traps n 
        ON t.trap_id = n.trap_id 
        WHEN NOT MATCHED THEN INSERT *
    """)
    print(f"\u2705 story_traps: {len(all_traps)} traps merged")
else:
    print("\u26a0\ufe0f No traps in today's stories")

# 3d. Retention cleanup (only run once per day, early morning)
if now_utc.hour < 8:
    deleted = spark.sql(f"DELETE FROM {CA_RUNS_TABLE} WHERE run_date < date_sub(current_date(), 90)")
    print("Retention: ca_runs older than 90 days cleaned")

# COMMAND ----------

# DBTITLE 1,Step 3B: Pass 2 — Deep Analysis (Top 3 Stories)
# ══════════════════════════════════════════════════════════════════════════
# STEP 3B: TWO-PASS CA SYNTHESIS (v3.1 — Gemini 2.5 Flash)
# Pass 1 already fetched 5-7 stories. Now Pass 2 takes the top 3
# and calls Gemini again (no search grounding) for deep UPSC analysis:
#   - PYQ patterns (2013-2024)
#   - Detailed prelims traps
#   - Complete 10-marker mains skeleton
#   - Static textbook chapter links
# ══════════════════════════════════════════════════════════════════════════

DEEP_ANALYSIS_TABLE = f"{CATALOG}.{SCHEMA}.deep_analysis"

DEEP_ANALYSIS_SYSTEM = """You are a UPSC exam pattern analyst. Given a current affairs story,
provide deep exam-focused analysis. Output ONLY valid JSON, no other text."""

def build_deep_prompt(story):
    """Build focused prompt for Pass 2 deep analysis of a single story."""
    return f"""Analyze this UPSC Current Affairs story for exam preparation:

STORY: {story['title']}
GS PAPERS: {', '.join(story.get('gs_papers', []))}
CLUSTER: {story.get('topic_cluster', '')}
RELEVANCE: {story.get('relevance', '')}
STATIC ANCHORS: {', '.join(story.get('static_anchors', []))}

Provide a JSON response with EXACTLY these 4 fields:

```json
{{
  "pyq_patterns": [
    {{
      "year": 2023,
      "paper": "GS2",
      "question_theme": "Brief description of the PYQ theme",
      "how_it_connects": "How this story connects to that PYQ pattern"
    }}
  ],
  "traps_detailed": [
    {{
      "statement": "A statement that LOOKS correct but is WRONG",
      "why_wrong": "Why students fall for this",
      "correct_version": "The accurate statement",
      "exam_risk": "HIGH/MEDIUM/LOW"
    }}
  ],
  "mains_skeleton": {{
    "question": "A likely 10-mark mains question on this topic",
    "directive": "Discuss/Analyze/Critically examine/etc.",
    "intro": "2-3 sentence intro with definition + context",
    "body": [
      "Point 1: [heading] — [2 sentences with fact/example]",
      "Point 2: [heading] — [2 sentences with fact/example]",
      "Point 3: [heading] — [2 sentences with fact/example]",
      "Point 4: [heading] — [2 sentences with fact/example]",
      "Point 5: [heading] — [2 sentences with fact/example]"
    ],
    "conclusion": "Forward-looking conclusion with reform suggestion"
  }},
  "static_links": [
    {{
      "book": "Laxmikanth/Ramesh Singh/Spectrum/NCERT",
      "chapter": "Chapter name or number",
      "topic": "Specific topic within the chapter",
      "why_read": "What static knowledge this story tests"
    }}
  ]
}}
```

Rules:
- PYQ patterns: Find 3-5 actual patterns from 2013-2024 prelims/mains
- Traps: 3-5 statements that could appear as MCQ distractors
- Mains skeleton: Must be answerable in 150 words (10-marker)
- Static links: 2-4 textbook references from standard UPSC books
- Output ONLY the JSON block, nothing else"""


# Select top 3 stories by priority
priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
top_3 = sorted(stories, key=lambda s: priority_order.get(s.get("priority", "LOW"), 2))[:3]

print(f"\U0001f50d Pass 2: Deep analysis for top {len(top_3)} stories...")

deep_results = []
for i, story in enumerate(top_3):
    print(f"   [{i+1}/{len(top_3)}] {story['title']}...")
    try:
        raw = call_gemini(DEEP_ANALYSIS_SYSTEM, build_deep_prompt(story), use_search=False)
        # Extract JSON from response (may have markdown fencing)
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', raw)
        if json_match:
            parsed = json.loads(json_match.group(1).strip())
        else:
            parsed = json.loads(raw.strip())
        
        deep_results.append({
            "story_id":       story["id"],
            "date":           TODAY,
            "pyq_patterns":   json.dumps(parsed.get("pyq_patterns", [])),
            "traps_detailed": json.dumps(parsed.get("traps_detailed", [])),
            "mains_skeleton": json.dumps(parsed.get("mains_skeleton", {})),
            "static_links":   json.dumps(parsed.get("static_links", [])),
            "created_date":   TODAY
        })
        print(f"         \u2705 {len(parsed.get('pyq_patterns',[]))} PYQ patterns, {len(parsed.get('traps_detailed',[]))} traps")
    except Exception as e:
        print(f"         \u26a0\ufe0f Failed: {e}")
        continue
    time.sleep(2)  # Rate limit courtesy

# Write to Delta with MERGE
# FIX: Use explicit column names instead of SET * / INSERT *
# The deep_analysis table has an extra column (dimension_labels) that
# doesn't exist in deep_results, causing MERGE ... SET * to fail with
# DELTA_MERGE_UNRESOLVED_EXPRESSION. Explicit columns avoid this.
DEEP_COLS = ["story_id", "date", "pyq_patterns", "traps_detailed", "mains_skeleton", "static_links", "created_date"]
if deep_results:
    # ── Dedup: keep last entry per story_id (in case of retry duplicates) ──
    seen = {}
    for dr in deep_results:
        seen[dr["story_id"]] = dr
    deep_results_deduped = list(seen.values())
    dupes_removed = len(deep_results) - len(deep_results_deduped)
    if dupes_removed > 0:
        print(f"   \u26a0\ufe0f Dedup: removed {dupes_removed} duplicate story_id entries from deep_results")
    
    spark.createDataFrame(deep_results_deduped).select(*DEEP_COLS).createOrReplaceTempView("new_deep_raw")
    # SQL safety net: ROW_NUMBER dedup in case DataFrame still has dupes
    spark.sql("""
        CREATE OR REPLACE TEMP VIEW new_deep AS
        SELECT story_id, date, pyq_patterns, traps_detailed, mains_skeleton, static_links, created_date
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY story_id, date ORDER BY created_date DESC) AS rn
            FROM new_deep_raw
        )
        WHERE rn = 1
    """)
    spark.sql(f"""
        MERGE INTO {DEEP_ANALYSIS_TABLE} t
        USING new_deep n
        ON t.story_id = n.story_id AND t.date = n.date
        WHEN MATCHED THEN UPDATE SET
            t.pyq_patterns   = n.pyq_patterns,
            t.traps_detailed = n.traps_detailed,
            t.mains_skeleton = n.mains_skeleton,
            t.static_links   = n.static_links,
            t.created_date   = n.created_date
        WHEN NOT MATCHED THEN INSERT
            (story_id, date, pyq_patterns, traps_detailed, mains_skeleton, static_links, created_date)
            VALUES (n.story_id, n.date, n.pyq_patterns, n.traps_detailed, n.mains_skeleton, n.static_links, n.created_date)
    """)
    print(f"\u2705 Deep analysis: {len(deep_results_deduped)} rows merged into {DEEP_ANALYSIS_TABLE}")
else:
    print("\u26a0\ufe0f No deep analysis results to write")

# COMMAND ----------

# DBTITLE 1,Step 3C: Geography Enrichment (Auto-Detect)
# ══════════════════════════════════════════════════════════════════════════
# STEP 3C: GEOGRAPHY FLAG + ENRICHMENT (v3.1 — Gemini 2.5 Flash)
# Auto-detects geography stories by subject or keyword scan
# Calls Gemini (no search grounding) for map location, context, strategic importance
# ══════════════════════════════════════════════════════════════════════════

GEO_TABLE = f"{CATALOG}.{SCHEMA}.geography_context"

GEO_KEYWORDS = {
    "strait", "river", "pass", "plateau", "delta", "basin",
    "peninsula", "chokepoint", "sea", "ocean", "mountain",
    "island", "gulf", "canal", "border", "glacier", "lake"
}

GEO_SYSTEM = """You are a UPSC Geography specialist. Given a current affairs story with
geographic relevance, provide precise location intelligence for map-based questions.
Output ONLY valid JSON, no other text."""

def is_geography_story(story):
    """Check if a story has geography relevance."""
    # Check topic cluster
    if story.get("topic_cluster", "").lower() in ["geography", "environment"]:
        return True
    # Check subject in GS papers
    if "GS1" in story.get("gs_papers", []):
        return True
    # Keyword scan across title, relevance, keywords
    text_to_scan = " ".join([
        story.get("title", ""),
        story.get("relevance", ""),
        " ".join(story.get("keywords", [])),
        " ".join(story.get("static_anchors", []))
    ]).lower()
    return bool(GEO_KEYWORDS & set(text_to_scan.split()))


def build_geo_prompt(story):
    return f"""Analyze the geographic dimension of this UPSC Current Affairs story:

STORY: {story['title']}
KEYWORDS: {', '.join(story.get('keywords', []))}
STATIC ANCHORS: {', '.join(story.get('static_anchors', []))}
RELEVANCE: {story.get('relevance', '')}

Provide a JSON response:

```json
{{
  "location_name": "Primary geographic feature/place name",
  "map_description": "Exact location for map marking: latitude/longitude range, which state/country, relative position (e.g., 'on the western coast of India, between Mumbai and Goa')",
  "surrounding_context": "Neighboring countries, states, water bodies, or geographic features within 500km",
  "strategic_importance": "Why this location matters for India: trade routes, defense, resources, climate, or geopolitical significance. Connect to UPSC syllabus."
}}
```

Rules:
- Be geographically precise — this should help mark the location on a blank map
- Include cardinal directions and relative distances
- Connect to India's strategic/economic interests
- Output ONLY the JSON block"""


# Detect geography stories
geo_stories = [s for s in stories if is_geography_story(s)]
print(f"\U0001f30d Geography scan: {len(geo_stories)}/{len(stories)} stories have geographic relevance")

geo_results = []
for i, story in enumerate(geo_stories):
    print(f"   [{i+1}/{len(geo_stories)}] {story['title']}...")
    try:
        raw = call_gemini(GEO_SYSTEM, build_geo_prompt(story), use_search=False)
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', raw)
        if json_match:
            parsed = json.loads(json_match.group(1).strip())
        else:
            parsed = json.loads(raw.strip())
        
        geo_results.append({
            "story_id":             story["id"],
            "date":                 TODAY,
            "location_name":        parsed.get("location_name", ""),
            "map_description":      parsed.get("map_description", ""),
            "surrounding_context":  parsed.get("surrounding_context", ""),
            "strategic_importance":  parsed.get("strategic_importance", ""),
            "created_date":         TODAY
        })
        print(f"         \u2705 {parsed.get('location_name', 'Unknown')}")
    except Exception as e:
        print(f"         \u26a0\ufe0f Failed: {e}")
        continue
    time.sleep(2)

# Write to Delta with MERGE
# FIX: Explicitly select only the 7 valid columns to avoid Spark Connect phantom columns
GEO_COLS = ["story_id", "date", "location_name", "map_description", "surrounding_context", "strategic_importance", "created_date"]
if geo_results:
    spark.createDataFrame(geo_results).select(*GEO_COLS).createOrReplaceTempView("new_geo")
    spark.sql(f"""
        MERGE INTO {GEO_TABLE} t
        USING new_geo n
        ON t.story_id = n.story_id AND t.date = n.date
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
    """)
    print(f"\u2705 Geography context: {len(geo_results)} rows merged into {GEO_TABLE}")
else:
    print("\U0001f30d No geography stories detected today (normal for non-geo news days)")

# COMMAND ----------

# DBTITLE 1,Step 4: RAG Ingest — Create Contextual Chunks from CA Stories
# ══════════════════════════════════════════════════════════════════════════
# STEP 4: RAG PIPELINE INGEST
# Creates contextual chunks from each CA story and MERGEs into
# the main contextual_chunks table (same table as NB1-3 pipeline)
# ══════════════════════════════════════════════════════════════════════════

ca_chunks = []
for idx, story in enumerate(stories):
    # Build rich text from story components
    facts_text = " | ".join([f["statement"] for f in story.get("facts", [])])
    body_points = "\n".join(story.get("answer_skeleton", {}).get("body_points", []))
    anchors = ", ".join(story.get("static_anchors", []))
    gs_papers = ", ".join(story.get("gs_papers", []))
    
    # Raw text (the actual content)
    chunk_text = f"""{story['title']} | {story.get('date', TODAY)}

{story.get('relevance', '')}

MEMORY HOOK: {story.get('memory_hook', '')}

Key facts: {facts_text}

Answer skeleton: {story.get('answer_skeleton', {}).get('intro', '')}
{body_points}

Static anchors: {anchors}""".strip()

    # Context header (same pattern as NB1 contextual retrieval)
    ctx_header = f"Current Affairs {TODAY}: {story['title']} — {gs_papers}"
    enriched = f"[Context: {ctx_header}]\n\n{chunk_text}"
    
    # Robust chunk indexing
    try:
        chunk_index = int(story['id'].split('_')[1])
    except (IndexError, ValueError):
        chunk_index = idx

    ca_chunks.append({
        "chunk_id":       f"ca_{TODAY}_{story['slug']}",
        "source_file":    f"CA_{TODAY}.md",
        "subject":        "Current Affairs",
        "page_number":    1,
        "chunk_index":    chunk_index,
        "text":           enriched,
        "raw_text":       chunk_text,
        "context_header": ctx_header,
        "token_count":    len(enriched.split()),
        "ingested_at":    now_utc,
        "doc_type":       "CurrentAffairs",
        "exam_stage":     "Both",
    })

if ca_chunks:
    ca_df = spark.createDataFrame([Row(**c) for c in ca_chunks])
    ca_df.createOrReplaceTempView("ca_today")
    spark.sql(f"""
        MERGE INTO {CHUNKS_TABLE} t 
        USING ca_today s 
        ON t.chunk_id = s.chunk_id 
        WHEN MATCHED THEN UPDATE SET * 
        WHEN NOT MATCHED THEN INSERT *
    """)
    print(f"\u2705 RAG Ingest: {len(ca_chunks)} CA chunks \u2192 {CHUNKS_TABLE}")
else:
    print("\u26a0\ufe0f No chunks to ingest")

# COMMAND ----------

# DBTITLE 1,Step 5: Embed CA Chunks (NEW — Missing from v1!)
# ══════════════════════════════════════════════════════════════════════════
# STEP 5: EMBEDDING (v2.1 — switched to databricks-bge-large-en)
# Original model databricks-qwen3-embedding-0-6b was retired (404).
# databricks-bge-large-en also produces 1024-dim embeddings.
# Uses Volume parquet workaround for serverless Spark Connect RPC limits
# ══════════════════════════════════════════════════════════════════════════
import pandas as pd

# Override model name — original endpoint was removed
EMBEDDING_MODEL = "databricks-bge-large-en"

host = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiUrl().getOrElse(None)
token = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().getOrElse(None)

def embed_batch(texts, batch_size=20):
    """Call Databricks embedding API for a batch of texts."""
    url = f"{host}/serving-endpoints/{EMBEDDING_MODEL}/invocations"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        payload = {"input": batch}
        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        batch_embeds = [item["embedding"] for item in resp.json()["data"]]
        all_embeddings.extend(batch_embeds)
        if len(texts) > batch_size:
            print(f"   Embedded {min(i+batch_size, len(texts))}/{len(texts)}")
    return all_embeddings

# Get texts to embed
ca_texts = [c["text"] for c in ca_chunks]
ca_ids   = [c["chunk_id"] for c in ca_chunks]

print(f"\U0001f9e0 Embedding {len(ca_texts)} CA chunks with {EMBEDDING_MODEL}...")
embeddings = embed_batch(ca_texts)
print(f"\u2705 Generated {len(embeddings)} embeddings ({EMBEDDING_DIM}-dim each)")

# Build pandas DataFrame with ALL columns matching embedded_chunks schema
# Columns: chunk_id, text, subject, source_file, page_number, token_count, embedding
chunks_by_id = {c["chunk_id"]: c for c in ca_chunks}

embed_records = []
for chunk_id, text, embedding in zip(ca_ids, ca_texts, embeddings):
    chunk_meta = chunks_by_id.get(chunk_id, {})
    embed_records.append({
        "chunk_id":    chunk_id,
        "text":        text,
        "subject":     chunk_meta.get("subject", "CurrentAffairs"),
        "source_file": chunk_meta.get("source_file", f"ca_{TODAY}"),
        "page_number": int(chunk_meta.get("page_number", 0)),
        "token_count": int(chunk_meta.get("token_count", 0)),
        "embedding":   embedding
    })

embed_pdf = pd.DataFrame(embed_records)

# Serverless workaround: save to Volume parquet, then read back with Spark
parquet_path = f"{DOCS_VOLUME}/ca_embeddings_{TODAY}.parquet"
embed_pdf.to_parquet(parquet_path, index=False)
print(f"\u2705 Saved to {parquet_path}")

# Read back and MERGE into embedded_chunks
embed_spark_df = spark.read.parquet(parquet_path)
# Cast int columns to match table schema (parquet may infer as bigint)
embed_spark_df = embed_spark_df.withColumn("page_number", F.col("page_number").cast("int")) \
                               .withColumn("token_count", F.col("token_count").cast("int"))
embed_spark_df.createOrReplaceTempView("ca_embeddings")

spark.sql(f"""
    MERGE INTO {EMBED_TABLE} t
    USING ca_embeddings s
    ON t.chunk_id = s.chunk_id
    WHEN MATCHED THEN UPDATE SET
        t.text = s.text, t.embedding = s.embedding,
        t.subject = s.subject, t.source_file = s.source_file,
        t.page_number = s.page_number, t.token_count = s.token_count
    WHEN NOT MATCHED THEN INSERT *
""")

print(f"\u2705 Embeddings merged into {EMBED_TABLE}")

# Cleanup temp parquet
import os
try:
    os.remove(parquet_path)
except:
    pass

# COMMAND ----------

# DBTITLE 1,Step 6: Trigger Vector Search Index Sync
# ══════════════════════════════════════════════════════════════
# STEP 6: VECTOR SEARCH SYNC — DEPRECATED 2026-03-23
# VS Classic replaced by FAISS index (rebuilt daily in Step 9)
# Step 9 overwrites /Volumes/upsc_catalog/rag/documents/upsc_faiss.index every morning
# Agent downloads fresh FAISS at container boot — always current
# ══════════════════════════════════════════════════════════════
print("✅ Step 6: VS sync deprecated — FAISS rebuild handled in Step 9")
print("   FAISS index path: /Volumes/upsc_catalog/rag/documents/upsc_faiss.index")
print("   Rebuilt daily at ~7:05 AM IST after CA embeddings are merged")

# COMMAND ----------

# DBTITLE 1,Step 7: Generate Obsidian Note to Volume
# ══════════════════════════════════════════════════════════════════════════
# STEP 7: OBSIDIAN NOTE GENERATION (v3.1 -- Fixed JSON parsing)
# FIX: isinstance guards on pyq_data, traps_data, mains_data, static_data
#      Perplexity sometimes returns lists of strings instead of dicts
# ══════════════════════════════════════════════════════════════════════════
from datetime import date as _date
import os as _os

# Build lookup dicts from Pass 2 + Geography results
deep_by_story = {d["story_id"]: d for d in deep_results} if deep_results else {}
geo_by_story = {g["story_id"]: g for g in geo_results} if geo_results else {}

# Indicator symbols (extracted as variables to avoid backslash-in-fstring issues on Python 3.10)
_DEEP_CHECK = "\u2705"   # checkmark
_GEO_GLOBE = "\U0001f30d"  # globe
_DASH = "\u2014"  # em-dash
_CROSS = "\u274c"  # cross mark
_CHECK = "\u2705"  # checkmark
_BULB = "\U0001f4a1"  # lightbulb
_ENDASH = "\u2013"  # en-dash


def _safe_json_load(raw, fallback):
    """Safely parse JSON string, returning fallback on failure."""
    if not raw:
        return fallback
    try:
        parsed = json.loads(raw)
        return parsed if parsed is not None else fallback
    except (json.JSONDecodeError, TypeError):
        return fallback


def build_obsidian_note_v3(today, human_brief, ca_json, generated_at, deep_map, geo_map):
    """Build enhanced Obsidian note with Deep Analysis + Geography sections."""
    stories = ca_json.get("stories", [])
    
    gs_papers_all = sorted(set(p for s in stories for p in s.get("gs_papers", [])))
    topic_clusters = sorted(set(s.get("topic_cluster", "") for s in stories))
    has_deep = len(deep_map) > 0
    has_geo = len(geo_map) > 0
    tags = ["current-affairs", today[:7]] + [tc.lower().replace(" ", "-") for tc in topic_clusters if tc]
    if has_geo:
        tags.append("geography")
    
    gs_joined = ", ".join(gs_papers_all)
    topics_joined = ", ".join(topic_clusters)
    tags_joined = ", ".join(tags)
    frontmatter = f"""---
date: {today}
generated_at: {generated_at}
story_count: {len(stories)}
deep_analysis_count: {len(deep_map)}
geography_stories: {len(geo_map)}
gs_papers: [{gs_joined}]
topics: [{topics_joined}]
tags: [{tags_joined}]
type: daily-brief
version: "3.1"
---"""

    # Story index table — build rows without backslashes in f-string expressions
    story_row_lines = []
    for s in stories:
        gs_str = ", ".join(s.get("gs_papers", []))
        deep_ind = _DEEP_CHECK if s["id"] in deep_map else ""
        geo_ind = _GEO_GLOBE if s["id"] in geo_map else ""
        story_row_lines.append(
            f"| {s['id']} | {s['priority']} | [[#{s['slug']}|{s['title']}]] | {gs_str} | {deep_ind} | {geo_ind} |"
        )
    story_rows = "\n".join(story_row_lines)
    story_table = f"| ID | Priority | Story | GS Papers | Deep | Geo |\n|---|---|---|---|---|---|\n{story_rows}"

    # Build each story section
    story_sections = []
    for s in stories:
        facts_md = "\n".join([f"- {f['statement']}" if isinstance(f, dict) else f"- {f}" for f in s.get("facts", [])])
        anchors = ", ".join([f"`{a}`" for a in s.get("static_anchors", [])])
        body_md = "\n".join([f"- {p}" for p in s.get("answer_skeleton", {}).get("body_points", [])])
        
        trap_blocks = []
        for t in s.get("traps", []):
            if isinstance(t, dict):
                correct = t.get("correct_belief", t.get("correct_fact", ""))
                trap_blocks.append(
                    f"> [!warning] {t.get('trap_id', '?')} {_DASH} {t.get('trap_type', '?')} ({t.get('severity', '?')})\n"
                    f"> {_CROSS} **Wrong:** {t.get('wrong_belief', '')}\n"
                    f"> {_CHECK} **Right:** {correct}"
                )
            else:
                trap_blocks.append(f"> [!warning] {t}")
        traps_md = "\n".join(trap_blocks)

        # Geography Context callout (if applicable)
        geo_section = ""
        if s["id"] in geo_map:
            g = geo_map[s["id"]]
            if isinstance(g, dict):
                loc = g.get("location_name", "")
                mapdesc = g.get("map_description", "")
                surr = g.get("surrounding_context", "")
                strat = g.get("strategic_importance", "")
                geo_section = f"""\n### {_GEO_GLOBE} Geography Context\n> [!info] Map Location: {loc}\n> **Where:** {mapdesc}\n> **Surrounding:** {surr}\n> **Strategic Importance:** {strat}\n"""

        # Deep Analysis section (if applicable)
        deep_section = ""
        if s["id"] in deep_map:
            d = deep_map[s["id"]]
            pyq_data = _safe_json_load(d.get("pyq_patterns", "[]"), [])
            traps_data = _safe_json_load(d.get("traps_detailed", "[]"), [])
            mains_data = _safe_json_load(d.get("mains_skeleton", "{}"), {})
            static_data = _safe_json_load(d.get("static_links", "[]"), [])
            
            # FIX: Handle both dict and string items in pyq_data
            pyq_lines = []
            if isinstance(pyq_data, list):
                for p in pyq_data:
                    if isinstance(p, dict):
                        yr = p.get("year", "?")
                        paper = p.get("paper", "")
                        theme = p.get("question_theme", "")
                        conn = p.get("how_it_connects", "")
                        pyq_lines.append(f"- **{yr} {paper}**: {theme} -> {conn}")
                    elif isinstance(p, str):
                        pyq_lines.append(f"- {p}")
            elif isinstance(pyq_data, str):
                pyq_lines.append(f"- {pyq_data}")
            pyq_md = "\n".join(pyq_lines) if pyq_lines else "- No direct PYQ matches found"
            
            # FIX: Handle both dict and string items in traps_data
            dtrap_blocks = []
            if isinstance(traps_data, list):
                for t in traps_data:
                    if isinstance(t, dict):
                        risk = t.get("exam_risk", "MEDIUM")
                        stmt = t.get("statement", "")
                        why = t.get("why_wrong", "")
                        corr = t.get("correct_version", "")
                        dtrap_blocks.append(
                            f"> [!danger] Prelims Trap ({risk})\n"
                            f"> **Statement:** {stmt}\n"
                            f"> **Why wrong:** {why}\n"
                            f"> **Correct:** {corr}"
                        )
                    elif isinstance(t, str):
                        dtrap_blocks.append(f"> [!danger] {t}")
            dtraps_md = "\n".join(dtrap_blocks) if dtrap_blocks else ""
            
            # FIX: Handle mains_skeleton as string or dict
            if isinstance(mains_data, str):
                mains_q = mains_data
                mains_dir = ""
                mains_intro = ""
                mains_body = ""
                mains_concl = ""
            elif isinstance(mains_data, dict):
                mains_q = mains_data.get("question", "")
                mains_dir = mains_data.get("directive", "")
                mains_intro = mains_data.get("intro", "")
                mains_body = "\n".join([f"- {p}" if isinstance(p, str) else f"- {p}" for p in mains_data.get("body", [])])
                mains_concl = mains_data.get("conclusion", "")
            else:
                mains_q = mains_dir = mains_intro = mains_body = mains_concl = ""
            
            # FIX: Handle both dict and string items in static_data
            static_lines = []
            if isinstance(static_data, list):
                for l in static_data:
                    if isinstance(l, dict):
                        bk = l.get("book", "")
                        ch = l.get("chapter", "")
                        tp = l.get("topic", "")
                        wr = l.get("why_read", "")
                        static_lines.append(f"- **{bk}** -> {ch}: {tp} ({wr})")
                    elif isinstance(l, str):
                        static_lines.append(f"- {l}")
            elif isinstance(static_data, str):
                static_lines.append(f"- {static_data}")
            static_md = "\n".join(static_lines) if static_lines else "- Check standard references"
            
            deep_section = f"""\n### Deep Analysis (Pass 2)\n\n#### PYQ Patterns (2013{_ENDASH}2024)\n{pyq_md}\n\n#### Detailed Prelims Traps\n{dtraps_md}\n\n#### Mains Answer Skeleton (10 marks)\n> **Q:** {mains_q}\n> *Directive: {mains_dir}*\n\n**Intro:** {mains_intro}\n\n{mains_body}\n\n**Conclusion:** {mains_concl}\n\n#### Static Reading Links\n{static_md}\n"""

        memo = s.get("memory_hook", "")
        relev = s.get("relevance", "")
        gs_papers_str = ", ".join(s.get("gs_papers", []))
        cluster = s.get("topic_cluster", "")
        intro = s.get("answer_skeleton", {}).get("intro", "")
        concl_dir = s.get("answer_skeleton", {}).get("conclusion_direction", "")
        story_sections.append(f"""\n## {s['title']} {{#{s['slug']}}}\n**Priority:** `{s['priority']}` | **Papers:** {gs_papers_str} | **Cluster:** {cluster}\n\n> {_BULB} **Memory Hook:** {memo}\n\n{relev}\n\n### Key Facts\n{facts_md}\n\n### Static Anchors\n{anchors}\n\n### Answer Skeleton\n**Intro:** {intro}\n\n{body_md}\n\n**Conclusion direction:** {concl_dir}\n\n### Traps\n{traps_md}\n{geo_section}{deep_section}""")

    return f"{frontmatter}\n\n# CA Brief {_DASH} {today}\n\n{human_brief}\n\n---\n\n## Story Index\n{story_table}\n\n---\n{''.join(story_sections)}---\n*Generated: {generated_at} | NB6 v3.1 (Databricks)*"


# Generate and save
obsidian_note = build_obsidian_note_v3(TODAY, human_brief, ca_json, now_utc_str, deep_by_story, geo_by_story)

today_date = _date.fromisoformat(TODAY)
month_folder = today_date.strftime("%m-%B")
vault_ca_dir = f"{OBSIDIAN_VOLUME}/UPSC_2026/01_Current_Affairs/2026/{month_folder}"
_os.makedirs(vault_ca_dir, exist_ok=True)

note_path = f"{vault_ca_dir}/CA_{TODAY}.md"
with open(note_path, "w", encoding="utf-8") as f:
    f.write(obsidian_note)

print(f"\u2705 Obsidian note saved: {note_path}")
print(f"   Size: {len(obsidian_note):,} chars")
print(f"   Deep Analysis sections: {len(deep_by_story)}")
print(f"   Geography callouts: {len(geo_by_story)}")

# COMMAND ----------

# DBTITLE 1,Step 8: Pipeline Summary + Verification
# ══════════════════════════════════════════════════════════════════════════
# PIPELINE SUMMARY (v3.0)
# ══════════════════════════════════════════════════════════════════════════

DEEP_ANALYSIS_TABLE = f"{CATALOG}.{SCHEMA}.deep_analysis"
GEO_TABLE = f"{CATALOG}.{SCHEMA}.geography_context"

# Verify counts across all tables
total_chunks = spark.sql(f"SELECT COUNT(*) as cnt FROM {CHUNKS_TABLE}").collect()[0][0]
ca_chunks_count = spark.sql(f"SELECT COUNT(*) as cnt FROM {CHUNKS_TABLE} WHERE doc_type = 'CurrentAffairs'").collect()[0][0]
total_embeds = spark.sql(f"SELECT COUNT(*) as cnt FROM {EMBED_TABLE}").collect()[0][0]
total_stories = spark.sql(f"SELECT COUNT(*) as cnt FROM {STORIES_TABLE}").collect()[0][0]
total_traps = spark.sql(f"SELECT COUNT(*) as cnt FROM {TRAPS_TABLE}").collect()[0][0]
total_deep = spark.sql(f"SELECT COUNT(*) as cnt FROM {DEEP_ANALYSIS_TABLE}").collect()[0][0]
total_geo = spark.sql(f"SELECT COUNT(*) as cnt FROM {GEO_TABLE}").collect()[0][0]

# Today's run stats
deep_count = len(deep_results) if deep_results else 0
geo_count = len(geo_results) if geo_results else 0

sep = "\u2550" * 60
dash = "\u2014"
print(f"\n{sep}")
print(f"  NB6 CA Orchestrator v3.0 {dash} {TODAY} {dash} COMPLETE")
print(sep)
print(f"")
print(f"  Pass 1 (Broad Fetch):")
print(f"    Stories fetched  : {len(stories)}")
print(f"    Traps generated  : {len(all_traps)}")
print(f"    Chunks created   : {len(ca_chunks)}")
print(f"    Embeddings       : {len(embeddings)}")
print(f"")
print(f"  Pass 2 (Deep Analysis):")
print(f"    Stories analyzed : {deep_count}")
print(f"    Geography enriched: {geo_count}")
print(f"")
print(f"  Cumulative Totals:")
print(f"    Total chunks     : {total_chunks:,} ({ca_chunks_count} CA)")
print(f"    Total embeddings : {total_embeds:,}")
print(f"    Total stories    : {total_stories}")
print(f"    Total traps      : {total_traps}")
print(f"    Deep analyses    : {total_deep}")
print(f"    Geo contexts     : {total_geo}")
print(f"")
print(f"  Outputs:")
print(f"    Delta tables     : ca_runs, stories, story_traps, deep_analysis, geography_context,")
print(f"                       contextual_chunks, embedded_chunks")
print(f"    Obsidian note    : {note_path}")
print(f"    FAISS index      : /Volumes/upsc_catalog/rag/documents/upsc_faiss.index (rebuilt in Step 9)")
print(sep)

# COMMAND ----------

# DBTITLE 1,Step 9 Header: FAISS Rebuild
# MAGIC %md
# MAGIC ## Step 9: Rebuild FAISS Index (Daily)
# MAGIC Re-exports **entire** `embedded_chunks` table to FAISS `IndexFlatIP` with L2 normalisation.
# MAGIC Overwrites Volume files so the AI Tutor agent picks up today's CA when it boots.

# COMMAND ----------

# DBTITLE 1,Step 9 Prereq: Install faiss-cpu
# MAGIC %pip install faiss-cpu "numpy<2" -q

# COMMAND ----------

# DBTITLE 1,Step 9: Rebuild FAISS Index from ALL embedded_chunks
# ══════════════════════════════════════════════════════════════════════════
# STEP 9: REBUILD FAISS INDEX FROM ALL EMBEDDED_CHUNKS
# Ensures today's CA chunks are in the FAISS index by ~7:05 AM
# The AI Tutor Agent downloads these files at container boot time
#
# NOTE: %pip install (previous cell) restarts the kernel, so we must
# re-define config variables that were originally set in Cell 2.
# ══════════════════════════════════════════════════════════════════════════
import faiss
import numpy as np
import pickle
import time as _time
import os as _os
from datetime import datetime, timezone

# ── Re-define config (kernel was restarted by %pip install) ──
CATALOG = "upsc_catalog"
SCHEMA = "rag"
EMBED_TABLE = f"{CATALOG}.{SCHEMA}.embedded_chunks"
DOCS_VOLUME = f"/Volumes/{CATALOG}/{SCHEMA}/documents"
FAISS_INDEX_PATH = f"{DOCS_VOLUME}/upsc_faiss.index"
FAISS_META_PATH  = f"{DOCS_VOLUME}/upsc_faiss_meta.pkl"
EMBED_DIM = 1024

print(f"\u2550" * 60)
print(f"  STEP 9: FAISS Index Rebuild")
print(f"\u2550" * 60)

faiss_start = _time.time()

# 1. Load ALL vectors from embedded_chunks
print("Loading all vectors from embedded_chunks...")
all_rows = spark.table(EMBED_TABLE) \
    .select("chunk_id", "text", "subject", "source_file", "embedding") \
    .collect()
print(f"  Loaded {len(all_rows):,} rows in {_time.time()-faiss_start:.1f}s")

# 2. Extract vectors + metadata
vectors = np.zeros((len(all_rows), EMBED_DIM), dtype=np.float32)
metadata = []
skipped = 0

for i, row in enumerate(all_rows):
    emb = row["embedding"]
    if emb is not None and len(emb) == EMBED_DIM:
        vectors[i] = np.array(emb, dtype=np.float32)
    else:
        skipped += 1
    metadata.append({
        "chunk_id":    row["chunk_id"],
        "text":        row["text"],
        "subject":     row["subject"],
        "source_file": row["source_file"],
    })

if skipped > 0:
    print(f"  \u26a0\ufe0f Skipped {skipped} rows with invalid embeddings")

# 3. L2 normalize ALL vectors for cosine similarity via inner product
faiss.normalize_L2(vectors)

# 4. Build fresh IndexFlatIP
index = faiss.IndexFlatIP(EMBED_DIM)
index.add(vectors)
print(f"  FAISS index built: {index.ntotal:,} vectors")

# 5. Overwrite Volume files
faiss.write_index(index, FAISS_INDEX_PATH)
with open(FAISS_META_PATH, "wb") as f:
    pickle.dump(metadata, f)

# 6. Report
idx_size = _os.path.getsize(FAISS_INDEX_PATH) / (1024*1024)
meta_size = _os.path.getsize(FAISS_META_PATH) / (1024*1024)
faiss_elapsed = _time.time() - faiss_start
rebuild_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

print(f"\n{'='*60}")
print(f"\u2705 FAISS INDEX REBUILD COMPLETE")
print(f"{'='*60}")
print(f"  Vectors in index:   {index.ntotal:,}")
print(f"  Index file size:    {idx_size:.1f} MB")
print(f"  Metadata file size: {meta_size:.1f} MB")
print(f"  Rebuild time:       {faiss_elapsed:.1f}s")
print(f"  Timestamp:          {rebuild_ts}")
print(f"  Index path:         {FAISS_INDEX_PATH}")
print(f"  Meta path:          {FAISS_META_PATH}")
print(f"{'='*60}")

# COMMAND ----------

# DBTITLE 1,Preview: Today's Human Brief
# Display today's human brief for quick review
# NOTE: After %pip install kernel restart, these variables may not exist.
# This cell is informational only — all data is already in Delta tables.
try:
    print("\U0001f4f0 TODAY'S UPSC CA BRIEF")
    print("=" * 60)
    print(human_brief[:2000])  # First 2000 chars
    if len(human_brief) > 2000:
        print(f"\n... [{len(human_brief) - 2000} more chars]")
    print("\n" + "=" * 60)
    print(f"\n\U0001f50d Stories: {', '.join(s['slug'] for s in stories)}")
except NameError:
    print("\u26a0\ufe0f Preview skipped (kernel restarted after pip install).")
    print("   Data is safely in Delta tables — check: SELECT * FROM upsc_catalog.rag.stories WHERE date = current_date()")

# COMMAND ----------

# DBTITLE 1,Obsidian Vault Blueprint
# MAGIC %md
# MAGIC ---
# MAGIC # Appendix A: Obsidian Vault Blueprint
# MAGIC ### `UPSC_2026/` — Designed to sync with this Databricks pipeline
# MAGIC
# MAGIC ```
# MAGIC UPSC_2026/
# MAGIC ├── .claude/
# MAGIC │   └── CLAUDE.md                    ← Claude Code project instructions
# MAGIC │
# MAGIC ├── 00_Dashboard/
# MAGIC │   ├── Home.md                      ← MOC (Map of Content) — daily landing page
# MAGIC │   ├── Weekly_Review.md             ← Auto-template: 7 stories, traps, accuracy
# MAGIC │   └── Exam_Countdown.md            ← Days left, syllabus coverage tracker
# MAGIC │
# MAGIC ├── 01_Current_Affairs/              ← NB6 writes here daily
# MAGIC │   ├── 2026/
# MAGIC │   │   ├── 03-March/
# MAGIC │   │   │   ├── CA_2026-03-20.md     ← Auto-generated by Step 7 of this notebook
# MAGIC │   │   │   └── ...
# MAGIC │   │   ├── 04-April/
# MAGIC │   │   └── ...
# MAGIC │   └── CA_Master_Index.md           ← All stories indexed by GS paper + cluster
# MAGIC │
# MAGIC ├── 02_Subjects/                     ← Manual study notes (template-driven)
# MAGIC │   ├── Polity/
# MAGIC │   │   └── Topics/                  ← Topic_Template.md-based notes
# MAGIC │   ├── Economy/
# MAGIC │   │   └── Topics/
# MAGIC │   ├── Geography/
# MAGIC │   │   └── Topics/
# MAGIC │   ├── History/
# MAGIC │   │   └── Topics/
# MAGIC │   ├── Environment/
# MAGIC │   │   └── Topics/
# MAGIC │   ├── Science_Tech/
# MAGIC │   │   └── Topics/
# MAGIC │   ├── IR/
# MAGIC │   │   └── Topics/
# MAGIC │   ├── Ethics/
# MAGIC │   │   └── Topics/
# MAGIC │   └── Telugu_Optional/
# MAGIC │       └── Topics/
# MAGIC │
# MAGIC ├── 03_PYQs/                         ← PYQ extraction + quiz tracking
# MAGIC │   ├── _SOURCE/
# MAGIC │   │   └── PYQ_GS_English_2013-25.pdf
# MAGIC │   ├── By_Year/
# MAGIC │   │   ├── 2013.md ... 2025.md
# MAGIC │   ├── By_Subject/
# MAGIC │   │   ├── Polity.md ... Economy.md
# MAGIC │   └── My_Performance/
# MAGIC │       └── Accuracy_Tracker.md
# MAGIC │
# MAGIC ├── 04_Traps/                        ← Synced from story_traps Delta table
# MAGIC │   ├── Trap_Index.md                ← All traps grouped by type + severity
# MAGIC │   ├── seed_traps.csv               ← Original 15 hand-curated traps
# MAGIC │   └── My_Weak_Traps.md             ← Traps I keep falling for
# MAGIC │
# MAGIC ├── 05_Revision/                     ← Spaced repetition
# MAGIC │   ├── Due_Today.md                 ← Notes with next_review <= today
# MAGIC │   └── Revision_Schedule.md         ← SM-2 intervals: 1d, 3d, 7d, 14d, 30d
# MAGIC │
# MAGIC ├── 06_Answer_Practice/              ← Mains answer writing
# MAGIC │   ├── GS1/ GS2/ GS3/ GS4/ Essay/
# MAGIC │   └── KARL_Scores.md               ← Links to Databricks answer_evaluations
# MAGIC │
# MAGIC ├── 07_Sync/                         ← Databricks ↔ Obsidian bridge
# MAGIC │   ├── sync_from_databricks.py      ← Pull CA notes from Volume to local vault
# MAGIC │   ├── sync_traps.py                ← Pull trap analytics from Delta
# MAGIC │   └── sync_config.json             ← Workspace URL, volume paths
# MAGIC │
# MAGIC └── Templates/                       ← Consistency enforcement
# MAGIC     ├── Daily_CA.md                  ← (Auto-generated, reference only)
# MAGIC     ├── Topic_Note.md                ← For manual study notes
# MAGIC     ├── PYQ_Extract.md               ← For /pyq extract command
# MAGIC     ├── Answer_Practice.md           ← For Mains answer writing
# MAGIC     └── Weekly_Review.md             ← For weekly self-assessment
# MAGIC ```
# MAGIC
# MAGIC ### Mapping: Databricks Tables → Obsidian Folders
# MAGIC
# MAGIC | Databricks Source | Obsidian Destination | Sync Method |
# MAGIC | --- | --- | --- |
# MAGIC | `ca_runs` + `stories` | `01_Current_Affairs/YYYY/MM-Month/` | **Auto** (NB6 Step 7 writes .md) |
# MAGIC | `story_traps` | `04_Traps/Trap_Index.md` | `sync_traps.py` (manual/cron) |
# MAGIC | `contextual_chunks` (doc_type=PYQ) | `03_PYQs/By_Subject/` | Manual extraction |
# MAGIC | `answer_evaluations` | `06_Answer_Practice/KARL_Scores.md` | `sync_from_databricks.py` |
# MAGIC | Topic notes (user-written) | `02_Subjects/*/Topics/` | **Local only** (not synced back) |

# COMMAND ----------

# DBTITLE 1,Appendix B: One-Click Vault Setup Script
# ══════════════════════════════════════════════════════════════════════════
# ONE-CLICK OBSIDIAN VAULT SETUP
# Creates the entire vault structure on the Databricks Volume
# Download this folder to your local machine and open as Obsidian vault
# ══════════════════════════════════════════════════════════════════════════
import os, json, csv
from datetime import date

VAULT_ROOT = "/Volumes/upsc_catalog/rag/obsidian_ca/UPSC_2026"
SEP_LINE = "\u2550" * 60

# ── 1. FOLDER STRUCTURE ───────────────────────────────────────────────────
folders = [
    ".claude",
    "00_Dashboard",
    "01_Current_Affairs/2026/03-March", "01_Current_Affairs/2026/04-April",
    "01_Current_Affairs/2026/05-May", "01_Current_Affairs/2026/06-June",
    "02_Subjects/Polity/Topics", "02_Subjects/Economy/Topics",
    "02_Subjects/Geography/Topics", "02_Subjects/History/Topics",
    "02_Subjects/Environment/Topics", "02_Subjects/Science_Tech/Topics",
    "02_Subjects/IR/Topics", "02_Subjects/Ethics/Topics",
    "02_Subjects/Telugu_Optional/Topics",
    "03_PYQs/_SOURCE", "03_PYQs/By_Year", "03_PYQs/By_Subject", "03_PYQs/My_Performance",
    "04_Traps",
    "05_Revision",
    "06_Answer_Practice/GS1", "06_Answer_Practice/GS2",
    "06_Answer_Practice/GS3", "06_Answer_Practice/GS4", "06_Answer_Practice/Essay",
    "07_Sync",
    "Templates",
]

for folder in folders:
    path = f"{VAULT_ROOT}/{folder}"
    os.makedirs(path, exist_ok=True)
print(f"\u2705 Created {len(folders)} folders")

# ── 2. CLAUDE.md ──────────────────────────────────────────────────────────
claude_md = """# CLAUDE.md \u2014 UPSC 2026 Master Brain (v2.0 Databricks-Integrated)

## MY IDENTITY
- UPSC CSE 2027 aspirant (Telugu Optional)
- Target: 110+ marks in Prelims
- System: Databricks RAG + Obsidian vault + Claude Code

## YOUR ROLE
You are my AI study partner. You:
1. Read daily CA notes from `01_Current_Affairs/` (auto-generated by Databricks NB6)
2. Detect traps using `04_Traps/` (synced from `story_traps` Delta table)
3. Create topic notes using `Templates/Topic_Note.md`
4. Quiz me from `03_PYQs/`
5. Track my revision schedule in `05_Revision/`

## THE 5 TRAP TYPES (v2 Taxonomy)
- FACTUAL_CONFUSION: mixing up similar schemes, articles, committees
- DATE_ERROR: wrong year for judgment, treaty, policy launch
- CONFLATION: treating two distinct things as same
- PARTIAL_FACT: knowing part of a provision but missing the caveat
- SCOPE_ERROR: overstating/understating reach of a law/policy

## WHEN I SAY "/daily"
1. Open today's CA note from `01_Current_Affairs/2026/[Month]/CA_YYYY-MM-DD.md`
2. Summarize the top stories
3. Quiz me on the traps listed in the note
4. Suggest static anchors to revise

## WHEN I SAY "Create note on [TOPIC]"
1. Read `Templates/Topic_Note.md`
2. Check `04_Traps/Trap_Index.md` for related traps
3. Create note in `02_Subjects/[Subject]/Topics/[Topic].md`

## WHEN I SAY "/pyq quiz [TOPIC] N"
1. Read `03_PYQs/By_Subject/[Topic].md`
2. Select N random questions
3. Ask one by one, track answers
4. Update `03_PYQs/My_Performance/Accuracy_Tracker.md`

## WHEN I SAY "/revision due"
1. Search all notes for `next_review: YYYY-MM-DD`
2. Find dates <= today
3. List topics sorted by priority

## WHEN I SAY "/weekly"
1. Read `00_Dashboard/Weekly_Review.md`
2. Count: stories read, traps logged, PYQs attempted
3. Generate weekly summary + next week's focus areas

## NEVER DO
- Delete files without asking
- Modify CLAUDE.md without permission
- Create notes outside the vault structure
"""
with open(f"{VAULT_ROOT}/.claude/CLAUDE.md", "w") as f:
    f.write(claude_md)
print("\u2705 CLAUDE.md written")

# ── 3. TEMPLATES ──────────────────────────────────────────────────────────
templates = {
    "Topic_Note.md": """---
subject: {{subject}}
topic: {{topic}}
date_created: {{date}}
next_review: {{date}}
confidence: 0
tags: [study-note, {{subject|lower}}]
---

# {{topic}}

## Definition & Constitutional Framework
- 

## Key Points
1. 
2. 
3. 

## Trap Alerts
> [!warning] Trap 1
> Wrong: 
> Right: 

## Current Affairs Connection (2024\u20132026)
- 

## PYQ References
- See [[03_PYQs/By_Subject/{{subject}}]]

## Quick Revision
- 3 lines max for last-minute recall

## Static Anchors
- Articles: 
- Committees: 
- Landmark Cases: 
""",
    "Answer_Practice.md": """---
date: {{date}}
gs_paper: {{paper}}
topic: {{topic}}
marks: 15
time_taken_min: 0
karl_score: 0
tags: [answer-practice, {{paper|lower}}]
---

# {{topic}} ({{marks}} marks)

## Question


## My Answer


## KARL Evaluation
*Run through Databricks NB4 Examiner Agent*
- Nuggets Hit: /
- Critical Missed: 
- Score: /10

## Model Answer Points
1. 
2. 
3. 
""",
    "Weekly_Review.md": """---
week_of: {{date}}
tags: [weekly-review]
---

# Weekly Review \u2014 {{date}}

## This Week's Numbers
| Metric | Target | Actual |
|---|---|---|
| CA stories read | 35 | |
| New traps logged | 10 | |
| PYQs attempted | 50 | |
| PYQ accuracy | 75% | |
| Notes created | 5 | |
| Answers practiced | 3 | |

## Top 3 Weak Areas
1. 
2. 
3. 

## Next Week's Focus
- [ ] 
- [ ] 
- [ ] 

## Reflection

""",
    "PYQ_Extract.md": """---
topic: {{topic}}
subject: {{subject}}
total_questions: 0
extraction_status: pending
tags: [pyq, {{subject|lower}}]
---

# PYQs: {{topic}}

### Q1 (UPSC YYYY)
**Question:** 
a) 
b) 
c) 
d) 

**Answer:** ()
**Trap Type:** 
**Explanation:** 
"""
}

for name, content in templates.items():
    with open(f"{VAULT_ROOT}/Templates/{name}", "w") as f:
        f.write(content)
print(f"\u2705 {len(templates)} templates written")

# ── 4. DASHBOARD ──────────────────────────────────────────────────────────
home_md = f"""---
tags: [dashboard, moc]
---

# UPSC 2026 \u2014 Command Center

> *Last updated: {date.today().isoformat()}*

## Quick Links
- [[01_Current_Affairs/CA_Master_Index|Today's CA]]
- [[04_Traps/Trap_Index|Trap Database]]
- [[05_Revision/Due_Today|Revision Due]]
- [[03_PYQs/My_Performance/Accuracy_Tracker|PYQ Stats]]
- [[06_Answer_Practice/KARL_Scores|KARL Scores]]

## Daily Routine (4 hours)
| Time | Activity | Tool |
|---|---|---|
| 7:00 AM | Read today's CA note | Obsidian (auto-generated) |
| 7:30 AM | Review traps from CA note | Obsidian |
| 8:00 AM | Study 1 topic (create note) | Obsidian + Claude |
| 9:00 AM | PYQ quiz (25 questions) | Claude `/pyq quiz` |
| 10:00 AM | Answer writing (1 question) | NB4 Examiner Agent |
| 10:30 AM | Review revision-due topics | `/revision due` |

## Databricks Pipeline Status
- RAG chunks: [[Check in Databricks|51,468+]]
- VS Index: `upsc_knowledge_index` (auto-sync)
- CA Orchestrator: NB6 runs daily at 7 AM IST
- Examiner Agent: NB4 (on-demand)
- Weakness Tracker: NB5 (needs 10+ evaluations)

## This Week
![[00_Dashboard/Weekly_Review]]
"""
with open(f"{VAULT_ROOT}/00_Dashboard/Home.md", "w") as f:
    f.write(home_md)
print("\u2705 Dashboard Home.md written")

# ── 5. CA MASTER INDEX ────────────────────────────────────────────────────
ca_index = """---
tags: [current-affairs, index]
---

# Current Affairs Master Index

*Auto-updated: Notes are generated daily by NB6 CA Orchestrator*

## How to Use
1. New notes appear in `01_Current_Affairs/2026/[Month]/`
2. Each note has: human brief, story index, trap callouts, answer skeletons
3. Use `/daily` in Claude to get a quiz on today's note

## By Month
- [[01_Current_Affairs/2026/03-March/|March 2026]]
- [[01_Current_Affairs/2026/04-April/|April 2026]]
- [[01_Current_Affairs/2026/05-May/|May 2026]]
- [[01_Current_Affairs/2026/06-June/|June 2026]]

## By GS Paper
### GS1 (History / Society / Geography)
*Search: `gs_papers: [GS1]` in frontmatter*

### GS2 (Governance / Polity / IR)
*Search: `gs_papers: [GS2]` in frontmatter*

### GS3 (Economy / Environment / S&T)
*Search: `gs_papers: [GS3]` in frontmatter*

### GS4 (Ethics)
*Search: `gs_papers: [GS4]` in frontmatter*
"""
with open(f"{VAULT_ROOT}/01_Current_Affairs/CA_Master_Index.md", "w") as f:
    f.write(ca_index)
print("\u2705 CA Master Index written")

# ── 6. TRAP INDEX ─────────────────────────────────────────────────────────
trap_index = """---
tags: [traps, index]
---

# Trap Database Index

*Source: `upsc_catalog.rag.story_traps` (auto-populated by NB6)*
*Sync: Run `07_Sync/sync_traps.py` to refresh*

## By Type
### FACTUAL_CONFUSION
*Mixing up two similar schemes, articles, or committees*

### DATE_ERROR
*Wrong year for a judgment, treaty, or policy launch*

### CONFLATION
*Treating two distinct things as the same*

### PARTIAL_FACT
*Knowing part of a provision but missing the critical caveat*

### SCOPE_ERROR
*Overstating or understating the reach of a law/policy*

## By Severity
### HIGH (Prelims MCQ killers)

### MEDIUM (Mains quality gaps)

### LOW (Minor nuance)

## Seed Traps (Original 15)
| Keyword | Trap Type | Target | Priority |
|---|---|---|---|
| fiscal deficit | Definition Distortion | FRBM Act 2003 | 10 |
| digital rupee | Definition Distortion | RBI liability vs Asset | 10 |
| governor | Authority Confusion | Article 163/200 | 10 |
| basic structure | Chronology Confusion | Kesavananda 1973 | 10 |
| joint sitting | Procedure vs Power | NOT for Money Bills | 9 |
| vote on account | Procedure vs Power | Article 116 vs 114 | 9 |
| lithium | CA Overlay | Critical vs Atomic minerals | 10 |
| pm surya ghar | CA Overlay | 1 crore by 2027 not 2025 | 10 |
| green hydrogen | CA Overlay | 5 MMT by 2030 | 9 |
| net zero | CA Overlay | 2070 target COP26 | 9 |
| aif | Definition Distortion | Hedge Funds YES, Bonds NO | 9 |
| article 356 | Authority Confusion | President proclaims | 9 |
| delimitation | Authority Confusion | Freeze till 2026 | 8 |
| repo rate | CA Overlay | 6.5% as of Dec 2024 | 8 |
| msp | Extreme Statement | 23 crops not all crops | 8 |
"""
with open(f"{VAULT_ROOT}/04_Traps/Trap_Index.md", "w") as f:
    f.write(trap_index)
print("\u2705 Trap Index written")

# ── 7. SEED TRAP CSV ──────────────────────────────────────────────────────
seed_traps = [
    ["fiscal deficit","Economy","Fiscal Policy","FRBM Act 2003 & NK Singh Committee Targets","NCERT Macro","Definition Distortion","10"],
    ["digital rupee","Economy","Banking","RBI liability vs Asset (Common trap)","Economic Survey","Definition Distortion","10"],
    ["governor","Polity","State Executive","Article 163 (Discretion) & Article 200 (Bills)","Laxmikanth","Authority Confusion","10"],
    ["basic structure","Polity","Constitution","Kesavananda 1973 not Golaknath","Laxmikanth","Chronology Confusion","10"],
    ["joint sitting","Polity","Parliament","NOT available for Money Bills (Article 108)","Laxmikanth","Procedure vs Power","9"],
    ["vote on account","Polity","Budget","Article 116 vs Article 114 (Appropriation)","Laxmikanth","Procedure vs Power","9"],
    ["lithium","Geography","Resources","Mines Act (Critical vs Atomic minerals)","PMF IAS","Current Affairs Overlay","10"],
    ["pm surya ghar","Environment","Energy","1 crore by 2027 not 2025","Budget 2025","Current Affairs Overlay","10"],
    ["green hydrogen","Environment","Energy","5 MMT by 2030 National Mission","Economic Survey","Current Affairs Overlay","9"],
    ["net zero","Environment","Climate","2070 target announced COP26","PIB","Current Affairs Overlay","9"],
    ["aif","Economy","Financial Markets","Hedge Funds YES | Bonds NO","SEBI Guidelines","Definition Distortion","9"],
    ["article 356","Polity","Emergency","President proclaims Cabinet advises","Laxmikanth","Authority Confusion","9"],
    ["delimitation","Polity","Elections","Article 82 & 84th Amendment (Freeze till 2026)","Laxmikanth","Authority Confusion","8"],
    ["repo rate","Economy","Monetary Policy","6.5% as of Dec 2024","RBI Website","Current Affairs Overlay","8"],
    ["msp","Economy","Agriculture","23 crops not all crops","Budget 2025","Extreme Statement Trap","8"],
]
csv_path = f"{VAULT_ROOT}/04_Traps/seed_traps.csv"
with open(csv_path, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Keyword","Subject","Theme","Static_Target","Source","Trap_Type","Priority"])
    w.writerows(seed_traps)
print("\u2705 Seed traps CSV written (15 traps)")

# ── 8. SYNC SCRIPTS ───────────────────────────────────────────────────────
sync_config = {
    "databricks_host": "https://adb-7405615460529826.6.azuredatabricks.net",
    "volume_ca_path": "/Volumes/upsc_catalog/rag/obsidian_ca",
    "volume_docs_path": "/Volumes/upsc_catalog/rag/documents",
    "catalog": "upsc_catalog",
    "schema": "rag",
    "tables": {
        "stories": "upsc_catalog.rag.stories",
        "traps": "upsc_catalog.rag.story_traps",
        "chunks": "upsc_catalog.rag.contextual_chunks",
        "evaluations": "upsc_catalog.rag.answer_evaluations"
    },
    "local_vault_path": "~/Desktop/UPSC_2026",
    "sync_direction": "databricks_to_local"
}
with open(f"{VAULT_ROOT}/07_Sync/sync_config.json", "w") as f:
    json.dump(sync_config, f, indent=2)

sync_ca_script = '''#!/usr/bin/env python3
"""Sync CA notes from Databricks Volume to local Obsidian vault.
Usage: python sync_from_databricks.py
"""
import json, os, subprocess
from pathlib import Path
from datetime import date

config_path = Path(__file__).parent / "sync_config.json"
with open(config_path) as f:
    config = json.load(f)

LOCAL_VAULT = Path(config["local_vault_path"]).expanduser()
MONTH = date.today().strftime("%m-%B")
LOCAL_CA_DIR = LOCAL_VAULT / "01_Current_Affairs" / "2026" / MONTH
LOCAL_CA_DIR.mkdir(parents=True, exist_ok=True)

VOLUME_PATH = config["volume_ca_path"] + "/UPSC_2026/01_Current_Affairs/2026/" + MONTH

print(f"Syncing from: {VOLUME_PATH}")
print(f"        to:   {LOCAL_CA_DIR}")

try:
    result = subprocess.run(
        ["databricks", "fs", "cp", "-r", f"dbfs:{VOLUME_PATH}/", str(LOCAL_CA_DIR) + "/"],
        capture_output=True, text=True, timeout=60
    )
    if result.returncode == 0:
        print("Synced successfully!")
    else:
        print(f"CLI sync failed: {result.stderr}")
        print("Tip: Run `databricks configure` first.")
except FileNotFoundError:
    print("Databricks CLI not found. Install: pip install databricks-cli")
    print("Then run: databricks configure --token")
'''
with open(f"{VAULT_ROOT}/07_Sync/sync_from_databricks.py", "w") as f:
    f.write(sync_ca_script)
print("\u2705 Sync config + scripts written")

# ── 9. REVISION + PERFORMANCE TRACKERS ──────────────────────────────────
due_today = """---
tags: [revision, due]
---

# Revision Due Today

*Auto-populated: search vault for `next_review` <= today's date*

## How Spaced Repetition Works
1. After creating a topic note, `next_review` = tomorrow
2. If you remember it during quiz: interval doubles (1d > 3d > 7d > 14d > 30d > 60d)
3. If you forget: interval resets to 1d
4. Use Obsidian Dataview plugin to auto-list due notes:

```dataview
TABLE subject, confidence, next_review
FROM "02_Subjects"
WHERE next_review <= date(today)
SORT next_review ASC
```

## Due Now
*(Use the Dataview query above)*
"""
with open(f"{VAULT_ROOT}/05_Revision/Due_Today.md", "w") as f:
    f.write(due_today)

accuracy_tracker = """---
tags: [pyq, performance]
---

# PYQ Accuracy Tracker

| Date | Subject | Attempted | Correct | Accuracy | Weak Topics |
|---|---|---|---|---|---|
| | | | | | |

## Subject-wise Summary
| Subject | Total Qs | Correct | Accuracy |
|---|---|---|---|
| Polity | 0 | 0 | 0% |
| Economy | 0 | 0 | 0% |
| Geography | 0 | 0 | 0% |
| History | 0 | 0 | 0% |
| Environment | 0 | 0 | 0% |
| Science & Tech | 0 | 0 | 0% |
"""
with open(f"{VAULT_ROOT}/03_PYQs/My_Performance/Accuracy_Tracker.md", "w") as f:
    f.write(accuracy_tracker)
print("\u2705 Revision + Performance trackers written")

# ── SUMMARY ───────────────────────────────────────────────────────────────
total_files = sum([len(files) for _, _, files in os.walk(VAULT_ROOT)])
total_dirs = sum([len(dirs) for _, dirs, _ in os.walk(VAULT_ROOT)])
print(f"\n{SEP_LINE}")
print(f"  VAULT SETUP COMPLETE")
print(f"  Location: {VAULT_ROOT}")
print(f"  Folders:  {total_dirs}")
print(f"  Files:    {total_files}")
print(SEP_LINE)
print("\n  Next: Download this folder to your Mac and open in Obsidian")

# COMMAND ----------

# DBTITLE 1,Recovery: Backfill Missing Dates (Mar 22-23)
# ══════════════════════════════════════════════════════════════════════════
# RECOVERY: Backfill stories + traps from saved ca_runs data
# ca_runs has parsed_json for Mar 22-29 but stories table is missing them.
# This cell re-extracts stories/traps from saved data — NO API calls needed.
# For Apr 2-4 (no ca_runs data), calls Gemini to generate fresh stories.
# ══════════════════════════════════════════════════════════════════════════
import json

# ── 1. Find dates with ca_runs data but missing/incomplete stories ──
existing_stories = spark.sql(f"""
    SELECT date, COUNT(*) as cnt FROM {CATALOG}.{SCHEMA}.stories GROUP BY date
""").collect()
existing_map = {r["date"]: r["cnt"] for r in existing_stories}

ca_runs_dates = spark.sql(f"""
    SELECT run_date, story_count, parsed_json FROM {CATALOG}.{SCHEMA}.ca_runs ORDER BY run_date
""").collect()

print("\u2550" * 60)
print("  BACKFILL ASSESSMENT")
print("\u2550" * 60)
recoverable = []
for r in ca_runs_dates:
    d = r["run_date"]
    ca_count = r["story_count"]
    stories_count = existing_map.get(d, 0)
    if stories_count < ca_count:
        gap = ca_count - stories_count
        print(f"  {d}: ca_runs={ca_count}, stories={stories_count} -> RECOVER {gap} stories")
        recoverable.append((d, r["parsed_json"]))
    elif stories_count == 0:
        print(f"  {d}: ca_runs={ca_count}, stories=0 -> RECOVER ALL")
        recoverable.append((d, r["parsed_json"]))
    else:
        print(f"  {d}: ca_runs={ca_count}, stories={stories_count} -> OK")

print(f"\n  Total dates to recover: {len(recoverable)}")

# ── 2. Re-extract stories + traps from saved parsed_json ──
all_stories_rows = []
all_traps_rows = []

for recover_date, parsed_json_str in recoverable:
    try:
        ca_json = json.loads(parsed_json_str)
        stories_list = ca_json.get("stories", [])
        if not stories_list:
            print(f"  \u26a0\ufe0f {recover_date}: parsed_json has no stories")
            continue
        
        for s in stories_list:
            all_stories_rows.append({
                "date":          recover_date,
                "story_id":      s.get("id", ""),
                "slug":          s.get("slug", ""),
                "title":         s.get("title", ""),
                "priority":      s.get("priority", "MEDIUM"),
                "gs_papers":     json.dumps(s.get("gs_papers", [])),
                "topic_cluster": s.get("topic_cluster", ""),
                "keywords":      json.dumps(s.get("keywords", []))
            })
            for t in s.get("traps", []):
                all_traps_rows.append({
                    "trap_id":            t.get("trap_id", ""),
                    "story_slug":         s.get("slug", ""),
                    "subject":            s.get("topic_cluster", ""),
                    "trap_type":          t.get("trap_type", ""),
                    "wrong_belief":       t.get("wrong_belief", ""),
                    "correct_belief":     t.get("correct_belief", t.get("correct_fact", "")),
                    "severity":           t.get("severity", ""),
                    "reinforces_trap_id": t.get("reinforces_trap_id") or "",
                    "created_date":       recover_date
                })
        print(f"  \u2705 {recover_date}: extracted {len(stories_list)} stories, {sum(len(s.get('traps',[])) for s in stories_list)} traps")
    except Exception as e:
        print(f"  \u274c {recover_date}: parse error: {e}")

# ── 3. Write recovered stories to Delta ──
if all_stories_rows:
    spark.createDataFrame(all_stories_rows).createOrReplaceTempView("backfill_stories")
    result = spark.sql(f"""
        MERGE INTO {CATALOG}.{SCHEMA}.stories t
        USING backfill_stories n
        ON t.date = n.date AND t.slug = n.slug
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
    """)
    print(f"\n\u2705 Stories: {len(all_stories_rows)} rows merged into stories table")
else:
    print("\n\u26a0\ufe0f No stories to recover")

# ── 4. Write recovered traps to Delta ──
if all_traps_rows:
    spark.createDataFrame(all_traps_rows).createOrReplaceTempView("backfill_traps")
    result = spark.sql(f"""
        MERGE INTO {CATALOG}.{SCHEMA}.story_traps t
        USING backfill_traps n
        ON t.trap_id = n.trap_id
        WHEN NOT MATCHED THEN INSERT *
    """)
    print(f"\u2705 Traps: {len(all_traps_rows)} rows merged into story_traps table")
else:
    print("\u26a0\ufe0f No traps to recover")

# ── 5. Final verification ──
final_counts = spark.sql(f"""
    SELECT date, COUNT(*) as stories FROM {CATALOG}.{SCHEMA}.stories GROUP BY date ORDER BY date
""").collect()
_sep_heavy = "\u2550" * 60
_sep_light = "\u2500" * 30
print("\n" + _sep_heavy)
print("  FINAL STORY COUNTS BY DATE")
print(_sep_heavy)
total = 0
for r in final_counts:
    total += r["stories"]
    print(f"  {r['date']}: {r['stories']} stories")
print(f"  {_sep_light}")
print(f"  TOTAL: {total} stories across {len(final_counts)} days")

# COMMAND ----------

# DBTITLE 1,Appendix C: Complete Usage Guide
# MAGIC %md
# MAGIC ---
# MAGIC # Appendix C: System Usage Guide
# MAGIC
# MAGIC ## One-Time Setup (You Do This Once)
# MAGIC
# MAGIC ### Step 1: Perplexity API Key (5 min)
# MAGIC 1. Get your key from [Perplexity API Console](https://www.perplexity.ai/settings/api)
# MAGIC 2. Add to Databricks Secrets (run in any notebook):
# MAGIC ```python
# MAGIC # Option A: Via Databricks CLI (recommended)
# MAGIC # databricks secrets put-secret azure-ocr perplexity-api-key --string-value "pplx-xxxx"
# MAGIC
# MAGIC # Option B: Via Databricks REST API (if CLI not available)
# MAGIC import requests
# MAGIC host = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiUrl().getOrElse(None)
# MAGIC token = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().getOrElse(None)
# MAGIC requests.post(f"{host}/api/2.0/secrets/put",
# MAGIC     headers={"Authorization": f"Bearer {token}"},
# MAGIC     json={"scope": "azure-ocr", "key": "perplexity-api-key", "string_value": "YOUR_KEY_HERE"})
# MAGIC ```
# MAGIC
# MAGIC ### Step 2: Run Vault Setup (2 min)
# MAGIC Run the cell above ("One-Click Vault Setup Script") to create the full Obsidian structure on the Volume.
# MAGIC
# MAGIC ### Step 3: Download Vault to Local Mac (5 min)
# MAGIC ```bash
# MAGIC # Install Databricks CLI if not already
# MAGIC pip install databricks-cli
# MAGIC databricks configure --token
# MAGIC # Host: https://adb-7405615460529826.6.azuredatabricks.net
# MAGIC # Token: your personal access token
# MAGIC
# MAGIC # Download the vault
# MAGIC mkdir -p ~/Desktop/UPSC_2026
# MAGIC databricks fs cp -r dbfs:/Volumes/upsc_catalog/rag/obsidian_ca/UPSC_2026/ ~/Desktop/UPSC_2026/
# MAGIC ```
# MAGIC
# MAGIC ### Step 4: Open in Obsidian
# MAGIC 1. Open Obsidian \u2192 "Open folder as vault" \u2192 select `~/Desktop/UPSC_2026`
# MAGIC 2. Install recommended plugins: **Dataview**, **Calendar**, **Templater**
# MAGIC 3. Set `00_Dashboard/Home.md` as your startup note
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Daily Workflow (Automated + Manual)
# MAGIC
# MAGIC ### What Happens Automatically (7 AM IST)
# MAGIC The scheduled job [UPSC Daily CA Orchestrator](#job-1121120519823159) runs NB6:
# MAGIC 1. Fetches 5\u20137 UPSC-relevant stories from Perplexity (web search)
# MAGIC 2. Generates traps per story
# MAGIC 3. Writes to Delta tables (`stories`, `story_traps`, `ca_runs`)
# MAGIC 4. Creates contextual chunks \u2192 embeds with Qwen3 \u2192 syncs VS index
# MAGIC 5. Exports `CA_2026-MM-DD.md` to Volume
# MAGIC
# MAGIC ### What You Do (7:30 AM onward)
# MAGIC
# MAGIC | Time | Action | Where |
# MAGIC | --- | --- | --- |
# MAGIC | 7:30 | Sync today's CA note to local vault | `python 07_Sync/sync_from_databricks.py` |
# MAGIC | 7:35 | Read the CA brief in Obsidian | `01_Current_Affairs/2026/[Month]/CA_today.md` |
# MAGIC | 7:45 | Review traps (callout blocks in the note) | Same note, scroll to "Traps" sections |
# MAGIC | 8:00 | Claude: `/daily` \u2192 quiz on today's traps | Claude Code in vault terminal |
# MAGIC | 8:30 | Create 1 topic note using template | Claude: `Create note on [TOPIC]` |
# MAGIC | 9:30 | PYQ practice (25 questions) | Claude: `/pyq quiz Polity 25` |
# MAGIC | 10:30 | Answer writing (1 Mains question) | Databricks NB4 Examiner Agent |
# MAGIC | 11:00 | Check revision due | Claude: `/revision due` |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Weekly Workflow (Every Sunday)
# MAGIC
# MAGIC 1. **Review the week**: Claude \u2192 `/weekly`
# MAGIC 2. **Check trap analytics**: Look at `04_Traps/Trap_Index.md` for patterns
# MAGIC 3. **Update PYQ tracker**: `03_PYQs/My_Performance/Accuracy_Tracker.md`
# MAGIC 4. **Create weekly review note**: Use `Templates/Weekly_Review.md`
# MAGIC 5. **Identify weak areas**: Focus next week on subjects below 70% accuracy
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Slash Commands Reference (Claude Code in Vault)
# MAGIC
# MAGIC | Command | What It Does |
# MAGIC | --- | --- |
# MAGIC | `/daily` | Opens today's CA note, quizzes on traps |
# MAGIC | `Create note on [TOPIC]` | Creates structured topic note from template |
# MAGIC | `/pyq quiz [TOPIC] N` | N random PYQs with instant feedback |
# MAGIC | `/pyq stats` | Subject-wise accuracy + weak areas |
# MAGIC | `/revision due` | Lists notes with `next_review` \u2264 today |
# MAGIC | `/weekly` | Generates weekly summary + next week plan |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Sync Architecture
# MAGIC
# MAGIC ```
# MAGIC   DATABRICKS (Cloud)                          LOCAL MAC
# MAGIC   \u250c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510              \u250c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510
# MAGIC   \u2502 NB6 runs daily at 7AM   \u2502              \u2502 Obsidian vault           \u2502
# MAGIC   \u2502 Perplexity \u2192 Delta     \u2502              \u2502 ~/Desktop/UPSC_2026     \u2502
# MAGIC   \u2502 \u2192 Embed \u2192 VS Index   \u2502              \u2502                         \u2502
# MAGIC   \u2502                         \u2502  sync_ca.py  \u2502 01_Current_Affairs/     \u2502
# MAGIC   \u2502 /Volumes/.../obsidian_ca \u2502 \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u25b6 \u2502   CA_2026-03-20.md      \u2502
# MAGIC   \u2502   CA_2026-03-20.md      \u2502              \u2502                         \u2502
# MAGIC   \u2502                         \u2502              \u2502 Claude Code terminal    \u2502
# MAGIC   \u2502 AI Tutor Agent (NB6)    \u2502 \u25c0\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500 \u2502   /daily, /pyq quiz     \u2502
# MAGIC   \u2502 answers via VS Index    \u2502  REST API    \u2502                         \u2502
# MAGIC   \u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518              \u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518
# MAGIC ```
# MAGIC
# MAGIC **Direction:** One-way: Databricks \u2192 Local. Your manual study notes stay local.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Cost Control
# MAGIC * NB6 daily job: \~$0.15/day (serverless compute \u223c 2 min + Perplexity \u223c $0.05)
# MAGIC * Embeddings: \u223c $0.001 per run (5\u20137 chunks \u00d7 free Qwen3)
# MAGIC * VS Index: \u223c $0.07/hour ONLY when endpoint is running
# MAGIC * **Monthly estimate: \u223c $5\u201310** (CA pipeline + occasional tutor queries)
# MAGIC * **Always ensure VS endpoint teardown** when not studying (NB1-3 has teardown cell)
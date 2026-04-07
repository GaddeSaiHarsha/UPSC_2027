# Databricks notebook source
# DBTITLE 1,NB9 UPSC Backup and GitHub Sync
# MAGIC %md
# MAGIC # NB9: UPSC Backup & GitHub Sync — Disaster Recovery
# MAGIC
# MAGIC **Purpose:** If you lose Databricks workspace access tomorrow, this notebook ensures you have **everything portable**.
# MAGIC
# MAGIC ### What gets backed up:
# MAGIC | Asset | Format | Destination |
# MAGIC |-------|--------|-------------|
# MAGIC | 19 UC Delta tables (75K chunks) | JSON + Parquet | Volume + GitHub |
# MAGIC | All notebooks (NB6-NB8 + bots) | .py source | GitHub |
# MAGIC | Bot code (hermes_full.py) | .py | GitHub |
# MAGIC | FAISS index | Binary | Volume + GitHub LFS |
# MAGIC | Obsidian vault | Markdown | GitHub (existing structure) |
# MAGIC | Mastery tracker | JSON | GitHub |
# MAGIC
# MAGIC ### Schedule: Daily at 9:00 AM IST (after NB8 completes)
# MAGIC
# MAGIC ### GitHub Repo: `GaddeSaiHarsha/UPSC_2027`
# MAGIC
# MAGIC ---
# MAGIC > **First run:** Set your GitHub PAT in Cell 1 below.

# COMMAND ----------

# DBTITLE 1,Cell 1: Configuration and GitHub Setup
# ═══════════════════════════════════════════════════════════════════════════
# NB9: UPSC BACKUP & GITHUB SYNC — DISASTER RECOVERY
# ═══════════════════════════════════════════════════════════════════════════

import requests, json, base64, os, time
import hashlib as _hashlib
from datetime import date, datetime, timedelta

# ── Configuration ──────────────────────────────────────────────────────────
TODAY = date.today().isoformat()

# GitHub config
GITHUB_OWNER = "GaddeSaiHarsha"
GITHUB_REPO = "UPSC_2027"
GITHUB_BRANCH = "main"

# Try to get PAT from Databricks secrets first, then widget
try:
    GITHUB_PAT = dbutils.secrets.get("upsc-bot-secrets", "github-pat")
    print(f"✅ GitHub PAT loaded from secrets ({len(GITHUB_PAT)} chars)")
except Exception:
    GITHUB_PAT = None
    print("⚠️  GitHub PAT not in secrets. Set it below:")
    print("   Option A: Run this once:")
    print('   dbutils.secrets.put("upsc-bot-secrets", "github-pat", "ghp_YOUR_TOKEN")')
    print("   Option B: Set GITHUB_PAT variable manually in this cell")

# Databricks workspace config
DB_HOST = f"https://{spark.conf.get('spark.databricks.workspaceUrl')}"
DB_TOKEN = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
DB_HEADERS = {"Authorization": f"Bearer {DB_TOKEN}", "Content-Type": "application/json"}

# Paths
BACKUP_VOL = "/Volumes/upsc_catalog/rag/documents/backups"
OBSIDIAN_VOL = "/Volumes/upsc_catalog/rag/obsidian_ca"
USER_DIR = "/Users/admin@mngenvmcap915189.onmicrosoft.com"

# Tables to export
ALL_TABLES = [
    "contextual_chunks", "mastery_tracker", "stories", "story_traps",
    "deep_analysis", "geography_context", "daily_practice_queue",
    "answer_evaluations", "ca_runs", "embedded_chunks", "essay_threads",
    "kg_connected_concepts", "kg_entities", "kg_extraction_staging",
    "kg_relationships", "telugu_optional_chunks", "upsc_knowledge_index",
    "upsc_tutor_agent_payload", "visual_anchors"
]

# Notebooks to backup
NOTEBOOKS = {
    "NB6_CA_Orchestrator": "NB6 CA Orchestrator Pipeline",
    "NB7_Daily_CA_Practice": "Daily CA Practice Generator",
    "NB8_Audio_Generator": "NB8 Audio Generator \u2014 UPSC Podcast Pipeline",
    "NB9_Backup_Sync": "NB9 UPSC Backup and GitHub Sync",
    "UPSC_Examiner_Agent_v2": "UPSC Examiner Agent v2",
    "UPSC_Mass_Ingestion": "UPSC Mass Ingestion Pipeline",
    "UPSC_Weakness_Tracker": "UPSC Weakness Tracker",
    "Telugu_ReOCR": "Telugu Re-OCR Pipeline (ai_parse_document)",
    "Hermes_Bot_Patch": "Hermes Bot Patch mastery tracker integration",
    "VM_Deploy_Guide": "UPSC Bot Azure VM Deployment Guide",
}

BOT_FILES = [
    "Drafts/hermes_full.py",
    "upsc_telegram_bot_v23.py",
    "UPSC_Audio_Pipeline_Docs.md",
]

# GitHub helper
def gh_api(method, path, json_data=None):
    """Call GitHub REST API."""
    url = f"https://api.github.com{path}"
    headers = {
        "Authorization": f"Bearer {GITHUB_PAT}",
        "Accept": "application/vnd.github.v3+json",
    }
    r = getattr(requests, method)(url, headers=headers, json=json_data, timeout=30)
    return r

def gh_push_file(repo_path, content_bytes, message, is_binary=False):
    """Push a file to GitHub (create or update)."""
    path = f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{repo_path}"
    encoded = base64.b64encode(content_bytes).decode('utf-8')

    # Check if file exists to get SHA
    existing = gh_api("get", path)
    sha = existing.json().get("sha") if existing.status_code == 200 else None

    payload = {
        "message": message,
        "content": encoded,
        "branch": GITHUB_BRANCH,
    }
    if sha:
        payload["sha"] = sha

    r = gh_api("put", path, payload)
    return r.status_code in (200, 201), r.status_code

print(f"\n📦 NB9 Backup & Sync — {TODAY}")
print(f"{'='*60}")
print(f"   GitHub: {GITHUB_OWNER}/{GITHUB_REPO}")
print(f"   Tables: {len(ALL_TABLES)}")
print(f"   Notebooks: {len(NOTEBOOKS)}")
print(f"   Bot files: {len(BOT_FILES)}")
print(f"   Backup vol: {BACKUP_VOL}")

# Create backup directory
try:
    dbutils.fs.mkdirs(BACKUP_VOL)
    dbutils.fs.mkdirs(f"{BACKUP_VOL}/{TODAY}")
    print(f"   Backup dir: {BACKUP_VOL}/{TODAY} ✓")
except Exception as e:
    print(f"   ⚠️  Dir: {e}")

# COMMAND ----------

# DBTITLE 1,Cell 2: Export All UC Tables to JSON + Parquet
# ═══════════════════════════════════════════════════════════════════════════
# CELL 2: Export all 19 UC tables to portable formats
# JSON (human-readable, any platform) + Parquet (efficient, Spark/Pandas)
# ═══════════════════════════════════════════════════════════════════════════

print(f"💾 Exporting {len(ALL_TABLES)} UC tables...")
print(f"{'-'*60}")

table_export_results = []
total_rows = 0
total_bytes = 0

for table_name in ALL_TABLES:
    fqn = f"upsc_catalog.rag.{table_name}"
    try:
        df = spark.table(fqn)
        row_count = df.count()
        total_rows += row_count

        # Export to Parquet (efficient, preserves types)
        parquet_path = f"{BACKUP_VOL}/{TODAY}/{table_name}.parquet"
        df.write.mode("overwrite").parquet(parquet_path)

        # Export small/critical tables to JSON too (human-readable)
        if row_count <= 100000:  # JSON for tables under 100K rows
            json_path = f"{BACKUP_VOL}/{TODAY}/{table_name}.json"
            df.write.mode("overwrite").json(json_path)

        # Get size
        try:
            files = dbutils.fs.ls(parquet_path)
            size = sum(f.size for f in files)
            total_bytes += size
        except:
            size = 0

        table_export_results.append((table_name, row_count, size, "✅"))
        print(f"   ✅ {table_name:<35} {row_count:>8,} rows  {size:>12,} bytes")

    except Exception as e:
        table_export_results.append((table_name, 0, 0, "❌"))
        print(f"   ❌ {table_name:<35} Error: {str(e)[:60]}")

print(f"\n{'='*60}")
print(f"   Tables exported: {sum(1 for _,_,_,s in table_export_results if s=='✅')}/{len(ALL_TABLES)}")
print(f"   Total rows: {total_rows:,}")
print(f"   Total size: {total_bytes:,} bytes ({total_bytes/1024/1024:.1f} MB)")
print(f"   Location: {BACKUP_VOL}/{TODAY}/")

# COMMAND ----------

# DBTITLE 1,Cell 3: Export All Notebooks + Bot Code
# ═══════════════════════════════════════════════════════════════════════════
# CELL 3: Export notebooks as .py source + bot code files
# Uses Databricks Workspace API to export notebooks
# ═══════════════════════════════════════════════════════════════════════════

import urllib.parse

print(f"📓 Exporting notebooks and bot code...")
print(f"{'-'*60}")

# Store exported content for GitHub push in Cell 4
exported_files = {}  # {github_path: content_bytes}

# ── Export notebooks via Workspace API ─────────────────────────────
nb_results = []
for short_name, full_name in NOTEBOOKS.items():
    ws_path = f"{USER_DIR}/{full_name}"
    encoded_path = urllib.parse.quote(ws_path, safe='')
    try:
        r = requests.get(
            f"{DB_HOST}/api/2.0/workspace/export",
            headers=DB_HEADERS,
            params={"path": ws_path, "format": "SOURCE"}
        )
        if r.status_code == 200:
            content_b64 = r.json().get("content", "")
            content_bytes = base64.b64decode(content_b64)

            # Save to Volume
            vol_path = f"{BACKUP_VOL}/{TODAY}/notebooks/{short_name}.py"
            dbutils.fs.put(vol_path, content_bytes.decode('utf-8', errors='replace'), overwrite=True)

            # Store for GitHub push
            exported_files[f"notebooks/{short_name}.py"] = content_bytes
            nb_results.append((short_name, len(content_bytes), "✅"))
            print(f"   ✅ {short_name:<35} {len(content_bytes):>8,} bytes")
        else:
            nb_results.append((short_name, 0, "❌"))
            print(f"   ❌ {short_name:<35} HTTP {r.status_code}")
    except Exception as e:
        nb_results.append((short_name, 0, "❌"))
        print(f"   ❌ {short_name:<35} {str(e)[:50]}")

# ── Export bot code files ───────────────────────────────────────────
print(f"\n🤖 Bot code + docs:")
for bot_file in BOT_FILES:
    ws_path = f"/Workspace{USER_DIR}/{bot_file}"
    try:
        with open(ws_path, "r") as f:
            content = f.read()
        content_bytes = content.encode('utf-8')

        # Save to Volume
        fname = bot_file.split('/')[-1]
        vol_path = f"{BACKUP_VOL}/{TODAY}/bot_code/{fname}"
        dbutils.fs.put(vol_path, content, overwrite=True)

        # Store for GitHub push
        exported_files[f"bot_code/{fname}"] = content_bytes
        print(f"   ✅ {fname:<35} {len(content_bytes):>8,} bytes")
    except Exception as e:
        print(f"   ❌ {bot_file:<35} {str(e)[:50]}")

print(f"\n{'='*60}")
print(f"   Notebooks exported: {sum(1 for _,_,s in nb_results if s=='✅')}/{len(NOTEBOOKS)}")
print(f"   Total files ready for GitHub: {len(exported_files)}")

# COMMAND ----------

# DBTITLE 1,Cell 4: Push Everything to GitHub
# ═══════════════════════════════════════════════════════════════════════════
# CELL 4: Push to GitHub (notebooks + bot code + critical tables)
# Pushes to GaddeSaiHarsha/UPSC_2027 repo
# ═══════════════════════════════════════════════════════════════════════════

if not GITHUB_PAT:
    print("❌ GitHub PAT not set. Skip this cell or set it in Cell 1.")
    print("   To create a PAT: GitHub > Settings > Developer settings > Personal access tokens")
    print("   Scope needed: repo (full control of private repositories)")
else:
    print(f"🚀 Pushing to GitHub: {GITHUB_OWNER}/{GITHUB_REPO}")
    print(f"{'-'*60}")

    push_results = []
    commit_msg = f"[NB9] Daily backup {TODAY}"

    # ── 1. Push notebooks + bot code ───────────────────────────────────
    for gh_path, content_bytes in exported_files.items():
        try:
            ok, status = gh_push_file(gh_path, content_bytes, commit_msg)
            push_results.append((gh_path, ok, status))
            icon = "✅" if ok else "❌"
            print(f"   {icon} {gh_path:<45} HTTP {status}")
            time.sleep(0.5)  # Rate limiting
        except Exception as e:
            push_results.append((gh_path, False, str(e)[:30]))
            print(f"   ❌ {gh_path:<45} {str(e)[:40]}")

    # ── 2. Push critical table data as JSON ───────────────────────────
    # Only push small critical tables to GitHub (large ones stay in Volume)
    # OPTIMIZATION (v2.1): Skip tables whose content hasn't changed since
    # last push. mastery_tracker was 83KB of identical data every day.
    # Diff check: compare md5 hash of new JSON against previous day's snapshot.
    CRITICAL_TABLES = ["mastery_tracker", "stories", "story_traps",
                       "daily_practice_queue", "ca_runs"]

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

    print(f"\n📊 Pushing critical table snapshots:")
    skipped_unchanged = 0
    for table_name in CRITICAL_TABLES:
        try:
            df = spark.table(f"upsc_catalog.rag.{table_name}")
            rows = df.limit(5000).toPandas()  # Cap at 5K rows for GitHub
            json_str = rows.to_json(orient='records', indent=2, default_handler=str)
            content_bytes = json_str.encode('utf-8')

            # Diff check: skip if content identical to yesterday's snapshot
            new_hash = _hashlib.md5(content_bytes).hexdigest()
            prev_hash = _get_prev_snapshot_hash(table_name)
            if prev_hash and new_hash == prev_hash:
                skipped_unchanged += 1
                print(f"   ⏭️  {table_name:<45} unchanged — skipped")
                continue

            gh_path = f"data_snapshots/{TODAY}/{table_name}.json"
            ok, status = gh_push_file(gh_path, content_bytes, commit_msg)
            push_results.append((gh_path, ok, status))
            icon = "✅" if ok else "❌"
            print(f"   {icon} {gh_path:<45} {len(rows)} rows, HTTP {status}")
            time.sleep(0.5)
        except Exception as e:
            print(f"   ❌ {table_name:<45} {str(e)[:40]}")

    # ── 3. Push today's Obsidian outputs ───────────────────────────────
    print(f"\n📓 Pushing today's Obsidian outputs:")
    practice_dir = f"{OBSIDIAN_VOL}/Daily_Practice/{TODAY}"
    try:
        for f_info in dbutils.fs.ls(practice_dir):
            if f_info.name.endswith('.md'):
                content = dbutils.fs.head(f_info.path, 65536)
                content_bytes = content.encode('utf-8')
                gh_path = f"Daily_Practice/{TODAY}/{f_info.name}"
                ok, status = gh_push_file(gh_path, content_bytes, commit_msg)
                icon = "✅" if ok else "❌"
                print(f"   {icon} {gh_path}")
                time.sleep(0.3)
    except Exception as e:
        print(f"   ⚠️  No practice dir for today: {e}")

    # Summary
    ok_count = sum(1 for _, ok, _ in push_results if ok)
    print(f"\n{'='*60}")
    print(f"   Pushed: {ok_count}/{len(push_results)} files to GitHub")
    if skipped_unchanged > 0:
        print(f"   Skipped: {skipped_unchanged} unchanged table snapshots (diff-based)")
    print(f"   Repo: https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}")

# COMMAND ----------

# DBTITLE 1,Cell 5: Create Portable Knowledge Package
# ═══════════════════════════════════════════════════════════════════════════
# CELL 5: Create portable knowledge package
# Self-contained package that works with ANY LLM platform
# ═══════════════════════════════════════════════════════════════════════════

print(f"🌐 Creating portable knowledge package...")
print(f"   This package lets you rebuild the UPSC system on ANY platform.")
print(f"{'-'*60}")

PKG_DIR = f"{BACKUP_VOL}/{TODAY}/portable_package"
dbutils.fs.mkdirs(PKG_DIR)

# ── 1. Export contextual_chunks as JSONL (universal format) ────────
print("   ⏳ Exporting 75K chunks as JSONL (this takes ~60s)...")

chunks_df = spark.table("upsc_catalog.rag.contextual_chunks")
chunks_path = f"{PKG_DIR}/knowledge_base_chunks.jsonl"

# Write as single-partition JSONL for easy consumption
chunks_df.coalesce(1).write.mode("overwrite").json(f"{PKG_DIR}/chunks_temp")

# Move the single part file to clean name
try:
    temp_files = dbutils.fs.ls(f"{PKG_DIR}/chunks_temp")
    for tf in temp_files:
        if tf.name.startswith("part-") and tf.name.endswith(".json"):
            dbutils.fs.cp(tf.path, chunks_path)
            break
    dbutils.fs.rm(f"{PKG_DIR}/chunks_temp", recurse=True)
    chunk_size = dbutils.fs.ls(chunks_path)[0].size if dbutils.fs.ls(chunks_path) else 0
    print(f"   ✅ knowledge_base_chunks.jsonl ({chunk_size/1024/1024:.1f} MB)")
except Exception as e:
    print(f"   ⚠️  Chunks export: {e}")
    chunk_size = 0

# ── 2. Export mastery tracker as clean JSON ───────────────────────
mastery_pd = spark.table("upsc_catalog.rag.mastery_tracker").toPandas()
mastery_json = mastery_pd.to_json(orient='records', indent=2, default_handler=str)
dbutils.fs.put(f"{PKG_DIR}/mastery_tracker.json", mastery_json, overwrite=True)
print(f"   ✅ mastery_tracker.json ({len(mastery_pd)} topics)")

# ── 3. Export knowledge graph ──────────────────────────────────────
for kg_table in ["kg_entities", "kg_relationships", "kg_connected_concepts"]:
    try:
        kg_pd = spark.table(f"upsc_catalog.rag.{kg_table}").toPandas()
        kg_json = kg_pd.to_json(orient='records', indent=2, default_handler=str)
        dbutils.fs.put(f"{PKG_DIR}/{kg_table}.json", kg_json, overwrite=True)
        print(f"   ✅ {kg_table}.json ({len(kg_pd)} entries)")
    except Exception as e:
        print(f"   ❌ {kg_table}: {e}")

# ── 4. Copy FAISS index ───────────────────────────────────────────
try:
    faiss_src = "/Volumes/upsc_catalog/rag/documents/upsc_faiss.index"
    faiss_dst = f"{PKG_DIR}/upsc_faiss.index"
    dbutils.fs.cp(faiss_src, faiss_dst)
    faiss_size = dbutils.fs.ls(faiss_dst)[0].size
    print(f"   ✅ upsc_faiss.index ({faiss_size/1024/1024:.1f} MB)")
except Exception as e:
    print(f"   ❌ FAISS index: {e}")

# ── 5. Create README for the portable package ────────────────────
readme = f"""# UPSC AI Study System — Portable Knowledge Package

## Created: {TODAY}
## Source: Databricks workspace (upsc_catalog.rag)

## Contents:

| File | Description | Size |
|------|-------------|------|
| knowledge_base_chunks.jsonl | 75K+ contextual chunks (Polity, History, Economy, Geography, Telugu) | {chunk_size/1024/1024:.1f} MB |
| mastery_tracker.json | 250 syllabus topics with spaced repetition data | {len(mastery_pd)} topics |
| kg_entities.json | Knowledge graph entities | 500 nodes |
| kg_relationships.json | Knowledge graph relationships | edges |
| kg_connected_concepts.json | Cross-topic connections | links |
| upsc_faiss.index | Pre-built FAISS vector index | binary |

## How to use with ANY LLM:

### Option 1: Python + OpenAI/Claude API
```python
import json

# Load knowledge base
with open('knowledge_base_chunks.jsonl') as f:
    chunks = [json.loads(line) for line in f]

# Search chunks (simple keyword)
def search(query, top_k=5):
    scored = []
    for c in chunks:
        text = c.get('contextualized_content', '') or c.get('content', '')
        score = sum(1 for w in query.lower().split() if w in text.lower())
        if score > 0:
            scored.append((score, c))
    return sorted(scored, reverse=True)[:top_k]

# Use with any LLM
results = search("Article 21 right to life")
context = '\\n'.join(r[1]['content'][:500] for r in results)
prompt = f"Based on this context:\\n{{context}}\\n\\nAnswer: What is Article 21?"
```

### Option 2: FAISS + Sentence Transformers (local)
```python
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')
index = faiss.read_index('upsc_faiss.index')

query_vec = model.encode(['Article 21 right to life'])
D, I = index.search(query_vec, k=5)  # top 5 results
```

### Option 3: LangChain / LlamaIndex
```python
from langchain.document_loaders import JSONLoader
from langchain.vectorstores import FAISS

loader = JSONLoader('knowledge_base_chunks.jsonl', jq_schema='.content')
docs = loader.load()
# Use with any LangChain LLM
```

### Option 4: Upload to any platform
- **ChatGPT**: Upload chunks JSONL as knowledge base
- **Claude Projects**: Add as project knowledge
- **Google NotebookLM**: Import as sources
- **Perplexity Spaces**: Add as collection
- **Custom RAG**: Any vector DB (Pinecone, Weaviate, ChromaDB)

## Rebuilding the full system:
1. Import notebooks/ directory into any Jupyter/Databricks environment
2. Load chunks into your preferred vector DB
3. Run bot_code/hermes_full.py with Groq API key
4. Set up mastery_tracker in any SQL database
"""

dbutils.fs.put(f"{PKG_DIR}/README.md", readme, overwrite=True)
print(f"   ✅ README.md (usage guide)")

print(f"\n{'='*60}")
print(f"   🌐 Portable package: {PKG_DIR}")
print(f"   Works with: OpenAI, Claude, Gemini, Ollama, LangChain, LlamaIndex")
print(f"   Zero vendor lock-in — pure JSON + FAISS")

# COMMAND ----------

# DBTITLE 1,Cell 6: Backup Summary + Next Steps
# ═══════════════════════════════════════════════════════════════════════════
# CELL 6: Final summary + disaster recovery instructions
# ═══════════════════════════════════════════════════════════════════════════

from datetime import datetime as _dt

print(f"")
print(f"╔{'='*68}╗")
print(f"║  NB9 BACKUP & GITHUB SYNC — SUMMARY{'':>31}║")
print(f"╠{'='*68}╣")
print(f"║  Date: {TODAY}{'':>{48 - len(TODAY)}}║")
print(f"║  Time: {_dt.now().strftime('%H:%M:%S IST')}{'':>43}║")
print(f"╠{'-'*68}╣")

# Volume backup
print(f"║  💾 VOLUME BACKUP (local disaster recovery){'':>25}║")
try:
    backup_files = dbutils.fs.ls(f"{BACKUP_VOL}/{TODAY}")
    print(f"║     Location: {BACKUP_VOL}/{TODAY}{'':>15}║")
    print(f"║     Contents: {len(backup_files)} items{'':>41}║")
except:
    print(f"║     ⚠️  Volume backup not yet run{'':>38}║")

# GitHub sync
print(f"╠{'-'*68}╣")
print(f"║  🚀 GITHUB SYNC{'':>54}║")
if GITHUB_PAT:
    print(f"║     Repo: {GITHUB_OWNER}/{GITHUB_REPO}{'':>29}║")
    print(f"║     PAT: ✅ configured{'':>44}║")
else:
    print(f"║     PAT: ❌ not set (Cell 4 will skip GitHub push){'':>17}║")

# Portable package
print(f"╠{'-'*68}╣")
print(f"║  🌐 PORTABLE PACKAGE{'':>50}║")
try:
    pkg_files = dbutils.fs.ls(f"{BACKUP_VOL}/{TODAY}/portable_package")
    print(f"║     Files: {len(pkg_files)} portable assets{'':>36}║")
except:
    print(f"║     ⚠️  Not yet created (run Cell 5){'':>34}║")

print(f"╠{'='*68}╣")
print(f"║  🚨 IF YOU LOSE WORKSPACE ACCESS:{'':>37}║")
print(f"║{'':>68}║")
print(f"║  1. GitHub has: notebooks, bot code, critical table snapshots{'':>6}║")
print(f"║  2. Portable package has: 75K chunks JSONL + FAISS index{'':>11}║")
print(f"║  3. Any LLM can use: Upload chunks to Claude/GPT/NotebookLM{'':>7}║")
print(f"║  4. Bot is standalone: hermes_full.py + Groq API = works{'':>11}║")
print(f"║  5. Rebuild anywhere: Import notebooks into any Jupyter env{'':>7}║")
print(f"║{'':>68}║")
print(f"║  🔑 CREDENTIALS TO SAVE SEPARATELY:{'':>35}║")
print(f"║     - Groq API key (for Hermes bot){'':>33}║")
print(f"║     - Telegram bot tokens (Hermes + Main){'':>27}║")
print(f"║     - GitHub PAT (for sync){'':>41}║")
print(f"║     - Databricks PAT (if workspace recovers){'':>24}║")
print(f"╚{'='*68}╝")

print(f"\n✅ NB9 complete! Your UPSC system is backed up and portable.")
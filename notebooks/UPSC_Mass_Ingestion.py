# Databricks notebook source
# DBTITLE 0,Mass Ingestion Overview
# MAGIC %md
# MAGIC # UPSC Mass Ingestion Pipeline
# MAGIC ### Process all 32 text-extractable PDFs + 14 Markdown files → `upsc_catalog.rag.contextual_chunks`
# MAGIC
# MAGIC | Source | Files | Est. Pages | Content |
# MAGIC |--------|-------|-----------|--------|
# MAGIC | **NCERTs** | 20 PDFs | ~3,500 | Polity, History, Geography, Economy, Society, Art, Biology |
# MAGIC | **Standard Textbooks** | 6 PDFs | ~2,700 | Spectrum, Makkhan, Norman, Polity Notes |
# MAGIC | **PYQ Text** | 4 PDFs | ~1,000 | GS English 2013-25, IAS Hub Toppers, Mains GS-II |
# MAGIC | **Current Affairs** | 9 MDs | ~1,500 pts | March 2025 – January 2026 |
# MAGIC | **Strategy Docs** | 5 MDs | ~100K chars | Golden Rules, Trap Analysis, Value Addition |
# MAGIC
# MAGIC **Mode:** Rule-based context headers (fast, free). Set `USE_LLM_CONTEXT = True` for LLM headers (~$10, hours).
# MAGIC
# MAGIC > 19 scanned PDFs (Laxmikanth, Ramesh Singh, Prelims PYQs, Toppers) are **skipped** — re-upload a clean digital Laxmikanth and use OCR for the rest.

# COMMAND ----------

# DBTITLE 0,Install dependencies
# MAGIC %pip install pypdf langchain-text-splitters tiktoken typing_extensions --upgrade -q
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# DBTITLE 0,Configuration
# ── CONFIGURATION ─────────────────────────────────────────────────────────
CATALOG        = "upsc_catalog"
SCHEMA         = "rag"
VOLUME_PATH    = f"/Volumes/{CATALOG}/{SCHEMA}/documents"
OUTPUT_TABLE   = f"{CATALOG}.{SCHEMA}.contextual_chunks"

# Context generation: True = LLM headers (~$10, hours) | False = rule-based (free, minutes)
CONTEXT_MODEL  = "databricks-meta-llama-3-3-70b-instruct"
USE_LLM_CONTEXT = False

CHUNK_SIZE     = 512
CHUNK_OVERLAP  = 64

# ── 19 scanned/image-heavy PDFs — skip until OCR pipeline is ready ─────────
SKIP_FILES = {
    "IndianEconomy_RameshSingh.pdf",
    "MLaxmikant(8e).pdf",                        # scanned — re-upload clean digital copy
    "Science & Technology (Prelims PYQs).pdf",
    "Modern History (Prelims PYQs).pdf",
    "Polity (Prelims PYQs).pdf",
    "Maps (Prelims PYQs).pdf",
    "Environment (Prelims PYQs).pdf",
    "Economy (Prelims PYQs).pdf",
    "Geography (Prelims PYQs).pdf",
    "Agriculture (Prelims PYQs).pdf",
    "GS4_TOPPERS_HANDWRITTEN_UPSC_PYQ_ANS_TILL 2022RP.pdf",
    "GS1_TOPPERS_HANDWRITTEN_UPSC_PYQ_ANS_TILL 2022RP.pdf",
    "GS2_TOPPERS_HANDWRITTEN_UPSC_PYQ_ANS_TILL 2022RP.pdf",
    "GS3_TOPPERS_HANDWRITTEN_UPSC_PYQ_ANS_TILL 2022RP.pdf",
    "Arjun-Dev-Part-1-2-The_Story_of_Civilization.pdf",
    "Modern _ India-Bipan Chandra.pdf",
    "AncientHistory-Old_NCERT.pdf",
    "Medieval India- Satish Chandra.pdf",
    "Copy of Untitled document.pdf",
}

# Non-document files to skip
SKIP_NON_DOCS = {
    "V2-mocks.py", "upsc_trap_detector_v2.py",
    "interactive_trap_detector.jsx", "interactive_trap_detector-1.jsx",
    "systemlogic-and-design.docx", "cc_obsidian.docx",
    "upsc_bible_master.zip", "upsc_bible_master.numbers",
    "upsc_bible_master.xlsx", "upsc_bible_master.csv",
    "final_questions_master_v3.csv", "final_questions_with_themes.csv",
    "final_questions_with_traps.csv", "grand_test_2_75.csv",
    "mock_grand_test_1_75_75Q.csv", "mock_history_high_trap_15_14Q.csv",
    "mock_mixed_trap_25_25Q.csv", "Theme_Summary-Table 1.csv",
    "upsc_master_enhanced.csv", "upsc_v2_analysis_output.xlsx",
    "upsc_v2_notes_plan.xlsx", "upsc_v3_pattern_engine.xlsx",
    "upsc_v4_revision_engine.xlsx", "upsc_v5_prediction_engine.xlsx",
    "HighYielders_upsc.xlsx", "demofile.PDF",
}

print(f"✅ Config ready: {OUTPUT_TABLE}")
print(f"   Chunk: {CHUNK_SIZE} tokens, overlap {CHUNK_OVERLAP}")
print(f"   Context: {'LLM' if USE_LLM_CONTEXT else 'Rule-based (fast)'}")
print(f"   Skipping {len(SKIP_FILES)} scanned PDFs + {len(SKIP_NON_DOCS)} non-doc files")

# COMMAND ----------

# DBTITLE 0,Setup helpers: extraction, cleaning, chunking
import os
import re
import requests
import json
from pathlib import Path
from datetime import datetime, timezone
from pypdf import PdfReader
import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pyspark.sql import Row
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, TimestampType

# API credentials
token = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
host  = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiUrl().get()

# Tokenizer & splitter
enc = tiktoken.get_encoding("cl100k_base")
def count_tokens(text):
    return len(enc.encode(text))

splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP,
    length_function=count_tokens,
    separators=["\n\n", "\n", "। ", ". ", " ", ""]
)

# ── Enhanced subject detection ────────────────────────────────────
def detect_subject(filename):
    fl = filename.lower()
    if any(k in fl for k in ['polity', 'constitution', 'laxmikant', 'political', 'politics-in-india']): return 'Polity'
    if any(k in fl for k in ['history', 'makkhan', 'spectrum', 'bipan', 'satish', 'norman', 'civilization', 'ancient', 'medieval', 'modern_india', 'modern ']): return 'History'
    if any(k in fl for k in ['geography', 'physical-geo', 'human-geo', 'people-and-economy', 'physical-environment']): return 'Geography'
    if any(k in fl for k in ['economy', 'economic', 'macroeconomic', 'ramesh']): return 'Economy'
    if any(k in fl for k in ['environment', 'ecology', 'biology']): return 'Environment'
    if any(k in fl for k in ['ethics', 'integrity']): return 'Ethics'
    if any(k in fl for k in ['sociology', 'social_change', 'society', 'indian_society']): return 'Society'
    if any(k in fl for k in ['art', 'culture']): return 'Art & Culture'
    if any(k in fl for k in ['science', 'technology']): return 'Science & Tech'
    if any(k in fl for k in ['ca_', 'current_affairs', 'current-affairs']): return 'Current Affairs'
    if any(k in fl for k in ['trap', 'golden_rule', 'cheat_sheet', 'value_addition', 'quick_reference']): return 'Strategy'
    if any(k in fl for k in ['pyq', 'toppers', 'ias_hub', 'ias hub', 'mains pyq']): return 'PYQ'
    if any(k in fl for k in ['syllabus']): return 'Syllabus'
    if any(k in fl for k in ['world', 'international', 'contemporary-world']): return 'International Relations'
    return 'General Studies'

# ── Text extraction ───────────────────────────────────────────────
def extract_text_from_pdf(local_path):
    try:
        reader = PdfReader(local_path)
        pages = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if len(text.strip()) > 50:
                pages.append({"page": i + 1, "text": text})
        return pages
    except Exception as e:
        print(f"  ⚠️ PDF error: {e}")
        return []

def extract_text_from_markdown(file_path):
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    if content.startswith('---'):
        end = content.find('---', 3)
        if end > 0:
            content = content[end + 3:]
    return [{"page": 1, "text": content.strip()}] if len(content.strip()) > 50 else []

def clean_text(text):
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\x00-\x7F\u0900-\u097F]+', ' ', text)
    return text.strip()

# ── Context header generation ────────────────────────────────────
def generate_context_header(chunk_text, doc_title, subject, use_llm=False):
    if use_llm:
        prompt = f"""You are a UPSC Study Planner. Book: {doc_title}, Subject: {subject}.
Content: {chunk_text[:300]}...
Write ONE LINE explaining what this chunk discusses and its UPSC relevance. Only the one line."""
        url = f"{host}/serving-endpoints/{CONTEXT_MODEL}/invocations"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        try:
            resp = requests.post(url, headers=headers, json={"messages": [{"role": "user", "content": prompt}]}, timeout=30)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        except:
            pass
    first_line = chunk_text.split('.')[0].strip()[:150]
    return f"Segment from {doc_title} ({subject}): {first_line}"

print("✅ All helpers ready.")

# COMMAND ----------

# DBTITLE 0,Discover files and process all documents
# ── DISCOVER ALL FILES (recursive, including Standard_resources/) ───────
def discover_files(base_path):
    found = []
    for root, dirs, files_list in os.walk(base_path):
        for fname in files_list:
            ext = Path(fname).suffix.lower()
            if ext not in ('.pdf', '.md', '.txt'):
                continue
            if fname in SKIP_FILES or fname in SKIP_NON_DOCS:
                continue
            if fname.startswith('.'):
                continue
            found.append(os.path.join(root, fname))
    return sorted(found)

all_files = discover_files(VOLUME_PATH)
print(f"📄 Found {len(all_files)} files to process:")
for f in all_files:
    fname = os.path.basename(f)
    ext = Path(fname).suffix.lower()
    subj = detect_subject(fname)
    size_kb = os.path.getsize(f) / 1024
    icon = '📕' if ext == '.pdf' else '📝'
    print(f"  {icon} {fname[:58]:<58} {subj:<20} {size_kb:>8.0f} KB")

# ── PROCESS ALL FILES ─────────────────────────────────────────────
all_chunks = []
ingestion_time = datetime.now(timezone.utc)
total_pages = 0
failed_files = []

for file_idx, filepath in enumerate(all_files, 1):
    fname = os.path.basename(filepath)
    ext = Path(fname).suffix.lower()
    subject = detect_subject(fname)

    print(f"\n[{file_idx}/{len(all_files)}] 📖 {fname[:55]} ({subject})")

    if ext == '.pdf':
        pages = extract_text_from_pdf(filepath)
    elif ext in ('.md', '.txt'):
        pages = extract_text_from_markdown(filepath)
    else:
        continue

    if not pages:
        print(f"   ⚠️ No text extracted — skipping")
        failed_files.append(fname)
        continue

    total_pages += len(pages)
    file_chunks = 0

    for page_info in pages:
        raw_text = clean_text(page_info["text"])
        if len(raw_text) < 50:
            continue

        chunks = splitter.split_text(raw_text)

        for chunk_idx, chunk in enumerate(chunks):
            context_header = generate_context_header(chunk, fname, subject, use_llm=USE_LLM_CONTEXT)
            enriched_text = f"[Context: {context_header}]\n\n{chunk}"

            all_chunks.append({
                "chunk_id": f"{fname}__p{page_info['page']}__c{chunk_idx}",
                "source_file": fname,
                "subject": subject,
                "page_number": page_info["page"],
                "chunk_index": chunk_idx,
                "text": enriched_text,
                "raw_text": chunk,
                "context_header": context_header,
                "token_count": count_tokens(enriched_text),
                "ingested_at": ingestion_time,
            })
            file_chunks += 1

    print(f"   ✅ {len(pages)} pages → {file_chunks} chunks")

print(f"\n{'='*60}")
print(f"📊 PROCESSING COMPLETE")
print(f"   Files processed: {len(all_files) - len(failed_files)}/{len(all_files)}")
print(f"   Pages extracted: {total_pages:,}")
print(f"   Chunks created:  {len(all_chunks):,}")
if failed_files:
    print(f"   ⚠️ Failed: {failed_files}")

# COMMAND ----------

# DBTITLE 0,Save to Delta table
# ── SAVE TO DELTA TABLE ─────────────────────────────────────────────
print(f"\n💾 Saving {len(all_chunks):,} chunks to {OUTPUT_TABLE}...")

schema = StructType([
    StructField("chunk_id", StringType(), False),
    StructField("source_file", StringType(), True),
    StructField("subject", StringType(), True),
    StructField("page_number", IntegerType(), True),
    StructField("chunk_index", IntegerType(), True),
    StructField("text", StringType(), True),
    StructField("raw_text", StringType(), True),
    StructField("context_header", StringType(), True),
    StructField("token_count", IntegerType(), True),
    StructField("ingested_at", TimestampType(), True),
])

rows = [Row(**c) for c in all_chunks]
df = spark.createDataFrame(rows, schema=schema)
df.write.format("delta").mode("overwrite").option("mergeSchema", "true").saveAsTable(OUTPUT_TABLE)

print(f"✅ Saved to {OUTPUT_TABLE}")

# ── VALIDATION ────────────────────────────────────────────────────
result_df = spark.table(OUTPUT_TABLE)
total_rows = result_df.count()
print(f"\n📊 Validation: {total_rows:,} chunks in table")
display(
    result_df.groupBy("subject")
    .agg(
        {"chunk_id": "count", "token_count": "avg", "source_file": "approx_count_distinct"}
    )
    .withColumnRenamed("count(chunk_id)", "chunks")
    .withColumnRenamed("avg(token_count)", "avg_tokens")
    .withColumnRenamed("approx_count_distinct(source_file)", "files")
    .orderBy("chunks", ascending=False)
)

# COMMAND ----------

# DBTITLE 0,Sample output verification
# MAGIC %sql
# MAGIC -- Quick sample: verify enriched chunks from different subjects
# MAGIC SELECT subject, source_file, context_header, LEFT(raw_text, 200) AS text_preview
# MAGIC FROM upsc_catalog.rag.contextual_chunks
# MAGIC WHERE subject IN ('Polity', 'History', 'Geography', 'Current Affairs', 'Economy')
# MAGIC ORDER BY subject, source_file
# MAGIC LIMIT 15
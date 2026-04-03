# Databricks notebook source
# DBTITLE 1,Telugu Re-OCR Pipeline
# MAGIC %md
# MAGIC # Telugu Re-OCR Pipeline — `ai_parse_document()`
# MAGIC
# MAGIC ### Why re-OCR?
# MAGIC The original Azure Document Intelligence OCR **garbled Telugu script into Tamil** for 7,917 out of 8,425 chunks.
# MAGIC PYQ answer PDFs, textbooks, and study materials are unreadable — rendering the entire Telugu Optional knowledge base unreliable.
# MAGIC
# MAGIC **`ai_parse_document()`** (Databricks native) produces **correct Telugu script** — verified on Vachana gabbilam (465 elements, proper తెలుగు లిపి).
# MAGIC
# MAGIC ### Pipeline Steps
# MAGIC | Step | Cell | Action |
# MAGIC |------|------|--------|
# MAGIC | 1 | Config | Set paths, skip list, parameters |
# MAGIC | 2 | Delete | Remove 7,917 garbled chunks + orphan embeddings |
# MAGIC | 3 | List | Discover PDFs to re-OCR, show sizes |
# MAGIC | 4 | Re-OCR | `ai_parse_document()` on all Telugu PDFs via `READ_FILES` |
# MAGIC | 5 | Chunk | Split re-OCR’d text into ~500-token chunks → MERGE into `contextual_chunks` |
# MAGIC | 6 | Embed | Generate 1024-dim vectors → MERGE into `embedded_chunks` |
# MAGIC | 7 | FAISS | Rebuild FAISS index with all 80K+ vectors |
# MAGIC | 8 | Verify | Count checks + sample Telugu text from previously-garbled sources |
# MAGIC
# MAGIC **Estimated runtime:** 30–60 min for all files (large PDFs handled by `ai_parse_document` internal batching).

# COMMAND ----------

# DBTITLE 1,Cell 1: Configuration
# ══════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════

CATALOG = "upsc_catalog"
SCHEMA = "rag"
CHUNKS_TABLE = f"{CATALOG}.{SCHEMA}.contextual_chunks"
EMBED_TABLE = f"{CATALOG}.{SCHEMA}.embedded_chunks"
TELUGU_DIR = "/Volumes/upsc_catalog/rag/documents/Telugu_Optional/TeluguOptional"
DOCS_VOLUME = f"/Volumes/{CATALOG}/{SCHEMA}/documents"
EMBEDDING_MODEL = "databricks-qwen3-embedding-0-6b"
EMBEDDING_DIM = 1024
CHUNK_SIZE = 500  # tokens per chunk
SUBJECT = "Telugu Optional"

# Files to SKIP — these are already clean (non-OCR or correctly processed)
SKIP_FILES = [
    "MemoryLines_Telugu_Complete_UPSC.md",
    "History-of-Telugu-Literature.pdf",
    "TELUGU_LITERATURE_COMPLETE_SYSTEM.pdf",
    "Make_It_Telugu_Legitimizing_Author_Patro.pdf",
    "telugu lit paper1+paper2_compressed.pdf",
    "Gunanidhi-2.pdf",
    "\u0c06\u0c23\u0c3f\u0c2e\u0c41\u0c24\u0c4d\u0c2f\u0c3e\u0c32\u0c41_compressed.pdf",
    "telugu optionalpaper I 2025.pdf",
    "Schedule- Daily Answer Writing - Telugu Lit- Pioneer.pdf",
    "I am sharing 'Schedule- Daily Answer Writing - Telugu Lit- Pioneer (1)' with you.pdf",
]

print(f"\u2705 Config loaded")
print(f"   Catalog: {CATALOG}.{SCHEMA}")
print(f"   Telugu dir: {TELUGU_DIR}")
print(f"   Skip files: {len(SKIP_FILES)}")
print(f"   Chunk size: {CHUNK_SIZE} tokens")
print(f"   Embedding: {EMBEDDING_MODEL} ({EMBEDDING_DIM}-dim)")

# COMMAND ----------

# DBTITLE 1,Cell 2: Delete Garbled Chunks + Orphan Embeddings
# MAGIC %sql
# MAGIC -- ══════════════════════════════════════════════════════════════════════
# MAGIC -- DELETE garbled Telugu chunks (Azure DI OCR → Tamil/garbage)
# MAGIC -- Keeps: MemoryLines, History-of-Telugu, COMPLETE_SYSTEM, and other clean files
# MAGIC -- ══════════════════════════════════════════════════════════════════════
# MAGIC
# MAGIC -- Step 1: Count what we're about to delete
# MAGIC WITH bad_chunks AS (
# MAGIC   SELECT COUNT(*) AS bad_count
# MAGIC   FROM upsc_catalog.rag.contextual_chunks
# MAGIC   WHERE subject = 'Telugu Optional'
# MAGIC     AND source_file NOT IN (
# MAGIC       'MemoryLines_Telugu_Complete_UPSC.md',
# MAGIC       'History-of-Telugu-Literature.pdf',
# MAGIC       'TELUGU_LITERATURE_COMPLETE_SYSTEM.pdf',
# MAGIC       'Make_It_Telugu_Legitimizing_Author_Patro.pdf',
# MAGIC       'telugu lit paper1+paper2_compressed.pdf',
# MAGIC       'Gunanidhi-2.pdf',
# MAGIC       'ఆణిముత్యాలు_compressed.pdf',
# MAGIC       'telugu optionalpaper I 2025.pdf',
# MAGIC       'Schedule- Daily Answer Writing - Telugu Lit- Pioneer.pdf',
# MAGIC       'I am sharing ''Schedule- Daily Answer Writing - Telugu Lit- Pioneer (1)'' with you.pdf'
# MAGIC     )
# MAGIC ),
# MAGIC keep_chunks AS (
# MAGIC   SELECT COUNT(*) AS keep_count
# MAGIC   FROM upsc_catalog.rag.contextual_chunks
# MAGIC   WHERE subject = 'Telugu Optional'
# MAGIC     AND source_file IN (
# MAGIC       'MemoryLines_Telugu_Complete_UPSC.md',
# MAGIC       'History-of-Telugu-Literature.pdf',
# MAGIC       'TELUGU_LITERATURE_COMPLETE_SYSTEM.pdf',
# MAGIC       'Make_It_Telugu_Legitimizing_Author_Patro.pdf',
# MAGIC       'telugu lit paper1+paper2_compressed.pdf',
# MAGIC       'Gunanidhi-2.pdf',
# MAGIC       'ఆణిముత్యాలు_compressed.pdf',
# MAGIC       'telugu optionalpaper I 2025.pdf',
# MAGIC       'Schedule- Daily Answer Writing - Telugu Lit- Pioneer.pdf',
# MAGIC       'I am sharing ''Schedule- Daily Answer Writing - Telugu Lit- Pioneer (1)'' with you.pdf'
# MAGIC     )
# MAGIC )
# MAGIC SELECT
# MAGIC   b.bad_count AS chunks_to_delete,
# MAGIC   k.keep_count AS chunks_to_keep,
# MAGIC   b.bad_count + k.keep_count AS total_telugu_before
# MAGIC FROM bad_chunks b, keep_chunks k

# COMMAND ----------

# DBTITLE 1,Cell 3: Execute Delete (run after verifying counts above)
# MAGIC %sql
# MAGIC -- Delete garbled chunks
# MAGIC DELETE FROM upsc_catalog.rag.contextual_chunks
# MAGIC WHERE subject = 'Telugu Optional'
# MAGIC   AND source_file NOT IN (
# MAGIC     'MemoryLines_Telugu_Complete_UPSC.md',
# MAGIC     'History-of-Telugu-Literature.pdf',
# MAGIC     'TELUGU_LITERATURE_COMPLETE_SYSTEM.pdf',
# MAGIC     'Make_It_Telugu_Legitimizing_Author_Patro.pdf',
# MAGIC     'telugu lit paper1+paper2_compressed.pdf',
# MAGIC     'Gunanidhi-2.pdf',
# MAGIC     'ఆణిముత్యాలు_compressed.pdf',
# MAGIC     'telugu optionalpaper I 2025.pdf',
# MAGIC     'Schedule- Daily Answer Writing - Telugu Lit- Pioneer.pdf',
# MAGIC     'I am sharing ''Schedule- Daily Answer Writing - Telugu Lit- Pioneer (1)'' with you.pdf'
# MAGIC   );
# MAGIC
# MAGIC -- Delete orphan embeddings (chunks that no longer exist)
# MAGIC DELETE FROM upsc_catalog.rag.embedded_chunks
# MAGIC WHERE chunk_id NOT IN (SELECT chunk_id FROM upsc_catalog.rag.contextual_chunks);
# MAGIC
# MAGIC -- Verify
# MAGIC SELECT
# MAGIC   (SELECT COUNT(*) FROM upsc_catalog.rag.contextual_chunks WHERE subject = 'Telugu Optional') AS remaining_chunks,
# MAGIC   (SELECT COUNT(*) FROM upsc_catalog.rag.embedded_chunks WHERE subject = 'Telugu Optional') AS remaining_embeds

# COMMAND ----------

# DBTITLE 1,Cell 4: List Telugu PDFs to Re-OCR
# ══════════════════════════════════════════════════════════════════════
# LIST all Telugu PDFs that need re-OCR (excluding skip list + duplicates)
# ══════════════════════════════════════════════════════════════════════
import os

def classify_file(fname):
    fl = fname.lower()
    if any(k in fl for k in ['pyq', 'question', 'sikharam', 'vakyanalu']):
        return 'PYQ'
    elif any(k in fl for k in ['syllabus', 'syllubus']):
        return 'Syllabus'
    elif any(k in fl for k in ['schedule', 'pioneer', 'strategy']):
        return 'Strategy'
    elif any(k in fl for k in ['notes', 'note']):
        return 'Notes'
    else:
        return 'Textbook'

all_files = [f for f in os.listdir(TELUGU_DIR) if f.lower().endswith('.pdf')]

# Deduplicate: skip '(1)' copies and exact size matches
seen = {}
files_to_ocr = []
skipped_dup = []
skipped_clean = []

for f in sorted(all_files):
    if f in SKIP_FILES:
        skipped_clean.append(f)
        continue
    path = os.path.join(TELUGU_DIR, f)
    size = os.path.getsize(path)
    base = f.replace(" (1)", "").replace("(1)", "").strip()
    key = (base, size)
    if key in seen:
        skipped_dup.append((f, seen[key]))
    else:
        seen[key] = f
        files_to_ocr.append(f)

total_size_mb = sum(os.path.getsize(os.path.join(TELUGU_DIR, f)) for f in files_to_ocr) / (1024*1024)

print(f"{'='*70}")
print(f"  TELUGU PDFs TO RE-OCR")
print(f"  Total: {len(files_to_ocr)} files | {total_size_mb:.0f} MB")
print(f"  Skipped (clean): {len(skipped_clean)} | Skipped (duplicates): {len(skipped_dup)}")
print(f"{'='*70}")

for f in files_to_ocr:
    path = os.path.join(TELUGU_DIR, f)
    size_mb = os.path.getsize(path) / (1024*1024)
    doc_type = classify_file(f)
    flag = " \u26a0\ufe0f LARGE" if size_mb > 100 else ""
    print(f"  {size_mb:>7.1f} MB | {doc_type:<10} | {f}{flag}")

if skipped_dup:
    print(f"\n  Duplicates skipped:")
    for dup, orig in skipped_dup:
        print(f"    {dup} \u2192 dup of {orig}")

# COMMAND ----------

# DBTITLE 1,Cell 5: Re-OCR via ai_parse_document (all Telugu PDFs)
# ══════════════════════════════════════════════════════════════════════
# RE-OCR all Telugu PDFs using ai_parse_document()
# Processes each file individually so one failure doesn't block the rest
# Creates telugu_reocr_raw temp view (same schema as original SQL version)
# ══════════════════════════════════════════════════════════════════════
import os
from pyspark.sql.types import StructType, StructField, StringType, IntegerType

result_schema = StructType([
    StructField("source_file", StringType()),
    StructField("full_path", StringType()),
    StructField("element_count", IntegerType()),
    StructField("page_count", IntegerType()),
    StructField("full_text", StringType()),
    StructField("error_status", StringType()),
])

all_pdfs = [f for f in os.listdir(TELUGU_DIR) if f.lower().endswith('.pdf') and f not in SKIP_FILES]
print(f"Processing {len(all_pdfs)} Telugu PDFs individually...\n")

success_rows = []
failed_files = []

for i, fname in enumerate(sorted(all_pdfs)):
    fpath = os.path.join(TELUGU_DIR, fname)
    size_mb = os.path.getsize(fpath) / (1024*1024)
    try:
        row = spark.sql(f"""
            WITH parsed AS (
                SELECT ai_parse_document(content) AS doc
                FROM READ_FILES('{fpath}', format => 'binaryFile')
            )
            SELECT
                CAST(size(try_cast(doc:document:elements AS ARRAY<VARIANT>)) AS INT) AS element_count,
                CAST(size(try_cast(doc:document:pages AS ARRAY<VARIANT>)) AS INT) AS page_count,
                CAST(concat_ws('\\n', transform(try_cast(doc:document:elements AS ARRAY<VARIANT>), e -> try_cast(e:content AS STRING))) AS STRING) AS full_text,
                CAST(try_cast(doc:error_status AS STRING) AS STRING) AS error_status
            FROM parsed
        """).collect()[0]

        success_rows.append((fname, fpath, row["element_count"], row["page_count"], row["full_text"], row["error_status"]))
        print(f"  [{i+1}/{len(all_pdfs)}] ✅ {fname} ({size_mb:.1f}MB) → {row['element_count'] or 0} elements, {row['page_count'] or 0} pages")
    except Exception as e:
        err_msg = str(e)[:200]
        failed_files.append((fname, err_msg))
        print(f"  [{i+1}/{len(all_pdfs)}] ❌ {fname} ({size_mb:.1f}MB) → {err_msg}")

# Create the temp view from successful results
if success_rows:
    df = spark.createDataFrame(success_rows, result_schema)
    df.createOrReplaceTempView("telugu_reocr_raw")

print(f"\n{'='*70}")
print(f"  RE-OCR COMPLETE: {len(success_rows)} succeeded, {len(failed_files)} failed")
if failed_files:
    print(f"  Failed files:")
    for f, e in failed_files:
        print(f"    ❌ {f}: {e[:100]}")
print(f"{'='*70}")

# Show summary from temp view
if success_rows:
    display(spark.sql("""
        SELECT source_file, element_count, page_count,
               LENGTH(full_text) AS text_chars,
               SUBSTRING(full_text, 1, 150) AS text_preview,
               error_status
        FROM telugu_reocr_raw
        ORDER BY element_count DESC
    """))

# COMMAND ----------

# DBTITLE 1,Cell 6: Chunk Re-OCR'd Text → MERGE into contextual_chunks
# ══════════════════════════════════════════════════════════════════════
# CHUNK re-OCR'd text into ~500-token pieces with metadata
# Skip files in SKIP_FILES list, MERGE into contextual_chunks
# ══════════════════════════════════════════════════════════════════════
import hashlib
from datetime import datetime, timezone
from pyspark.sql import Row
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, TimestampType

chunks_schema = StructType([
    StructField("chunk_id", StringType()),
    StructField("source_file", StringType()),
    StructField("subject", StringType()),
    StructField("page_number", IntegerType()),
    StructField("chunk_index", IntegerType()),
    StructField("text", StringType()),
    StructField("raw_text", StringType()),
    StructField("context_header", StringType()),
    StructField("token_count", IntegerType()),
    StructField("ingested_at", TimestampType()),
    StructField("doc_type", StringType()),
    StructField("exam_stage", StringType()),
])

# Read the re-OCR'd data from temp view
reocr_df = spark.sql("SELECT source_file, full_text, page_count, error_status FROM telugu_reocr_raw")
reocr_rows = reocr_df.collect()

print(f"Files from ai_parse_document: {len(reocr_rows)}")

total_chunks = 0
failed_files = []
now_utc = datetime.now(timezone.utc)

for idx, row in enumerate(reocr_rows):
    fname = row.source_file
    full_text = row.full_text
    error = row.error_status

    # Skip clean files
    if fname in SKIP_FILES:
        print(f"  [{idx+1}/{len(reocr_rows)}] SKIP (clean): {fname}")
        continue

    # Skip errored files
    if error:
        failed_files.append((fname, f"ai_parse_document error: {error}"))
        print(f"  [{idx+1}/{len(reocr_rows)}] \u274c ERROR: {fname} -> {error}")
        continue

    # Skip empty results
    if not full_text or len(full_text.strip()) < 50:
        failed_files.append((fname, "Empty or near-empty text"))
        print(f"  [{idx+1}/{len(reocr_rows)}] \u26a0\ufe0f EMPTY: {fname}")
        continue

    doc_type = classify_file(fname)
    pages = row.page_count or 1

    # Chunk the full text into ~CHUNK_SIZE token pieces
    words = full_text.split()
    chunks = []
    for i in range(0, len(words), CHUNK_SIZE):
        chunk_words = words[i:i + CHUNK_SIZE]
        raw_text = " ".join(chunk_words)
        chunk_idx = len(chunks)
        # Estimate page number from position in text
        page_est = max(1, int((i / max(len(words), 1)) * pages) + 1)
        chunk_id = hashlib.md5(f"reocr_{fname}_c{chunk_idx}_{i}".encode()).hexdigest()

        ctx = f"Source: {fname} | Subject: {SUBJECT} | Page: ~{page_est} | Re-OCR: ai_parse_document"
        enriched = f"[{ctx}]\n\n{raw_text}"

        chunks.append({
            "chunk_id": chunk_id,
            "source_file": fname,
            "subject": SUBJECT,
            "page_number": int(page_est),
            "chunk_index": int(chunk_idx),
            "text": enriched,
            "raw_text": raw_text,
            "context_header": ctx,
            "token_count": int(len(chunk_words)),
            "ingested_at": now_utc,
            "doc_type": doc_type,
            "exam_stage": "Mains"
        })

    if chunks:
        chunk_rows = [Row(**c) for c in chunks]
        df = spark.createDataFrame(chunk_rows, chunks_schema)
        df.createOrReplaceTempView("reocr_batch")
        spark.sql(f"""
            MERGE INTO {CHUNKS_TABLE} t
            USING reocr_batch s ON t.chunk_id = s.chunk_id
            WHEN MATCHED THEN UPDATE SET *
            WHEN NOT MATCHED THEN INSERT *
        """)
        total_chunks += len(chunks)
        print(f"  [{idx+1}/{len(reocr_rows)}] \u2705 {fname}: {len(chunks)} chunks ({len(words):,} words, {pages} pages)")
    else:
        print(f"  [{idx+1}/{len(reocr_rows)}] \u26a0\ufe0f No chunks: {fname}")

print(f"\n{'='*70}")
print(f"  CHUNKING COMPLETE: {total_chunks:,} new chunks from {len(reocr_rows) - len(failed_files)} files")
if failed_files:
    print(f"  \u274c Failed: {len(failed_files)} files")
    for f, e in failed_files:
        print(f"     {f}: {e}")
print(f"{'='*70}")

# COMMAND ----------

# DBTITLE 1,Cell 7: Embed New Chunks → MERGE into embedded_chunks
# ══════════════════════════════════════════════════════════════════════
# EMBED new Telugu chunks (only those missing from embedded_chunks)
# Uses databricks-qwen3-embedding-0-6b via REST API in batches of 50
# ══════════════════════════════════════════════════════════════════════
import requests, time
import pandas as pd

# Databricks API credentials
db_host = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiUrl().get()
db_token = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
db_headers = {"Authorization": f"Bearer {db_token}", "Content-Type": "application/json"}

# Find chunks missing embeddings
missing = spark.sql(f"""
    SELECT c.chunk_id, c.text, c.subject, c.source_file, c.page_number, c.token_count
    FROM {CHUNKS_TABLE} c
    LEFT ANTI JOIN {EMBED_TABLE} e ON c.chunk_id = e.chunk_id
    WHERE c.subject = '{SUBJECT}'
""").collect()

print(f"Chunks needing embedding: {len(missing)}")

if missing:
    def _call_endpoint(texts):
        """Call embedding endpoint. Returns list of embeddings or raises."""
        url = f"{db_host}/serving-endpoints/{EMBEDDING_MODEL}/invocations"
        resp = requests.post(url, headers=db_headers, json={"input": texts}, timeout=120)
        resp.raise_for_status()
        return [d["embedding"] for d in resp.json()["data"]]

    def embed_batch(texts, batch_size=50):
        url = f"{db_host}/serving-endpoints/{EMBEDDING_MODEL}/invocations"
        all_emb = [None] * len(texts)  # pre-allocate to track indices
        skipped = 0
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            success = False
            for attempt in range(5):
                try:
                    resp = requests.post(url, headers=db_headers, json={"input": batch}, timeout=120)
                    resp.raise_for_status()
                    embs = [d["embedding"] for d in resp.json()["data"]]
                    for j, emb in enumerate(embs):
                        all_emb[i + j] = emb
                    success = True
                    break
                except requests.exceptions.HTTPError as e:
                    if e.response is not None and e.response.status_code == 400:
                        # Bad input — fallback to individual items to skip bad ones
                        detail = e.response.text[:300] if e.response.text else "no detail"
                        print(f"   ⚠️ Batch {i}-{i+len(batch)} got 400: {detail}")
                        print(f"   Falling back to individual embedding...")
                        for j, single_text in enumerate(batch):
                            try:
                                # Truncate very long texts (>8000 chars) that may exceed token limit
                                txt = single_text[:8000] if len(single_text) > 8000 else single_text
                                embs = _call_endpoint([txt])
                                all_emb[i + j] = embs[0]
                            except Exception as e2:
                                skipped += 1
                                print(f"   ❌ Skipped chunk at index {i+j} (len={len(single_text)}): {str(e2)[:100]}")
                        success = True
                        break
                    else:
                        if attempt < 4:
                            wait = 10 * (attempt + 1)
                            print(f"   ⏳ Retry {attempt+1}/5 in {wait}s: {e}")
                            time.sleep(wait)
                        else:
                            raise
                except Exception as e:
                    if attempt < 4:
                        wait = 10 * (attempt + 1)
                        print(f"   ⏳ Retry {attempt+1}/5 in {wait}s: {e}")
                        time.sleep(wait)
                    else:
                        raise
            if (i + batch_size) % 200 == 0:
                print(f"   Embedded {min(i+batch_size, len(texts))}/{len(texts)}")
        if skipped:
            print(f"   ⚠️ Total skipped: {skipped} chunks")
        return all_emb

    texts = [r["text"] for r in missing]
    print(f"Embedding {len(texts)} chunks...")
    embeddings = embed_batch(texts)
    # Filter out None (skipped) entries
    valid = [(r, emb) for r, emb in zip(missing, embeddings) if emb is not None]
    print(f"✅ Generated {len(valid)} embeddings ({len(missing) - len(valid)} skipped)")

    # Build DataFrame and MERGE
    records = []
    for r, emb in valid:
        records.append({
            "chunk_id": r["chunk_id"], "text": r["text"], "subject": r["subject"],
            "source_file": r["source_file"], "page_number": int(r["page_number"] or 0),
            "token_count": int(r["token_count"] or 0), "embedding": emb
        })

    if records:
        pdf = pd.DataFrame(records)
        staging_path = f"{DOCS_VOLUME}/tmp_telugu_reocr_embeds.parquet"
        pdf.to_parquet(staging_path, index=False)

        embed_df = spark.read.parquet(staging_path)
        embed_df = embed_df.withColumn("page_number", embed_df.page_number.cast("int")) \
                           .withColumn("token_count", embed_df.token_count.cast("int"))
        embed_df.createOrReplaceTempView("reocr_embeds")

        spark.sql(f"""
            MERGE INTO {EMBED_TABLE} t
            USING reocr_embeds s ON t.chunk_id = s.chunk_id
            WHEN MATCHED THEN UPDATE SET *
            WHEN NOT MATCHED THEN INSERT *
        """)
        print(f"✅ Embeddings merged into {EMBED_TABLE}")

        # Cleanup
        try:
            import os
            os.remove(staging_path)
        except:
            pass
    else:
        print("⚠️ No valid embeddings generated")
else:
    print("✅ All chunks already have embeddings!")

# COMMAND ----------

# DBTITLE 1,Cell 8a: Install FAISS (kernel restarts after this)
# MAGIC %pip install faiss-cpu -q
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# DBTITLE 1,Cell 8b: Rebuild FAISS Index (all embedded_chunks)
# ══════════════════════════════════════════════════════════════════════
# REBUILD FAISS INDEX from ALL embedded_chunks
# NOTE: %pip install restarted the kernel, so we re-define config here.
# ══════════════════════════════════════════════════════════════════════
import faiss
import numpy as np
import pickle
import time as _time
import os as _os
from datetime import datetime, timezone

# Re-define config (kernel was restarted by %pip install)
CATALOG = "upsc_catalog"
SCHEMA = "rag"
EMBED_TABLE = f"{CATALOG}.{SCHEMA}.embedded_chunks"
DOCS_VOLUME = f"/Volumes/{CATALOG}/{SCHEMA}/documents"
FAISS_INDEX_PATH = f"{DOCS_VOLUME}/upsc_faiss.index"
FAISS_META_PATH  = f"{DOCS_VOLUME}/upsc_faiss_meta.pkl"
EMBED_DIM = 1024

print(f"\u2550" * 60)
print(f"  FAISS Index Rebuild (post re-OCR)")
print(f"\u2550" * 60)

faiss_start = _time.time()

# 1. Load ALL vectors
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

# 3. L2 normalize for cosine similarity
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

print(f"\n{'='*60}")
print(f"\u2705 FAISS INDEX REBUILD COMPLETE")
print(f"{'='*60}")
print(f"  Vectors:  {index.ntotal:,}")
print(f"  Index:    {idx_size:.1f} MB")
print(f"  Metadata: {meta_size:.1f} MB")
print(f"  Time:     {faiss_elapsed:.1f}s")
print(f"{'='*60}")

# COMMAND ----------

# DBTITLE 1,Cell 9: Verification — Counts + Telugu Text Sample
# MAGIC %sql
# MAGIC -- ══════════════════════════════════════════════════════════════════════
# MAGIC -- VERIFICATION: Check Telugu re-OCR quality
# MAGIC -- ══════════════════════════════════════════════════════════════════════
# MAGIC
# MAGIC -- 1. Count summary
# MAGIC SELECT
# MAGIC   'Telugu chunks' AS metric,
# MAGIC   COUNT(*) AS count
# MAGIC FROM upsc_catalog.rag.contextual_chunks
# MAGIC WHERE subject = 'Telugu Optional'
# MAGIC
# MAGIC UNION ALL
# MAGIC
# MAGIC SELECT
# MAGIC   'Telugu embeddings' AS metric,
# MAGIC   COUNT(*) AS count
# MAGIC FROM upsc_catalog.rag.embedded_chunks
# MAGIC WHERE subject = 'Telugu Optional'
# MAGIC
# MAGIC UNION ALL
# MAGIC
# MAGIC SELECT
# MAGIC   'Total chunks (all subjects)' AS metric,
# MAGIC   COUNT(*) AS count
# MAGIC FROM upsc_catalog.rag.contextual_chunks
# MAGIC
# MAGIC UNION ALL
# MAGIC
# MAGIC SELECT
# MAGIC   'Total embeddings (all subjects)' AS metric,
# MAGIC   COUNT(*) AS count
# MAGIC FROM upsc_catalog.rag.embedded_chunks

# COMMAND ----------

# DBTITLE 1,Cell 10: Sample Telugu Text from Re-OCR'd Sources
# MAGIC %sql
# MAGIC -- Sample 5 chunks from previously-garbled PYQ/Textbook sources
# MAGIC -- These should now show actual Telugu script (తెలుగు లిపి), NOT Tamil/garbage
# MAGIC SELECT
# MAGIC   source_file,
# MAGIC   doc_type,
# MAGIC   page_number,
# MAGIC   SUBSTRING(context_header, 1, 80) AS context,
# MAGIC   SUBSTRING(raw_text, 1, 300) AS text_preview
# MAGIC FROM upsc_catalog.rag.contextual_chunks
# MAGIC WHERE subject = 'Telugu Optional'
# MAGIC   AND context_header LIKE '%Re-OCR: ai_parse_document%'
# MAGIC ORDER BY RAND()
# MAGIC LIMIT 5
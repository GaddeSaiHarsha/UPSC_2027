# 7-Day A/B Cost Experiment: Databricks Claude vs Gemini 2.5 Flash

## Goal

Determine whether swapping the NB6/NB7 generation LLM from
**Databricks Claude Sonnet 4** to **Gemini 2.5 Flash** (via Google AI API)
reduces cost while maintaining acceptable output quality for UPSC preparation.

Databricks remains the **source of truth** for all tables, Volumes, and
vector search. Only the LLM call is A/B-tested.

---

## Experiment Design

| | Control (A) | Treatment (B) |
|---|---|---|
| **LLM** | Databricks `databricks-claude-sonnet-4` via `ai_query()` | Google `gemini-2.5-flash` via `generativelanguage.googleapis.com` |
| **Runs** | Days 1, 3, 5, 7 (odd) | Days 2, 4, 6 (even) |
| **Notebooks** | NB6 + NB7 (unchanged) | NB6 + NB7 (model param swapped) |
| **Data store** | `upsc_catalog.rag.*` (unchanged) | Same tables — appended with `model_tag` column |

> **Nothing else changes.** Volume paths, Hermes bot, Obsidian sync, and NB8/NB9
> all run identically throughout the experiment.

---

## Day-by-Day Schedule

| Day | Date (example) | Run | Notes |
|---|---|---|---|
| 1 | Mon | Control A | Baseline — record DBU cost from Databricks Job UI |
| 2 | Tue | Treatment B | First Gemini run — note latency and token count |
| 3 | Wed | Control A | Compare quality vs Day 1 |
| 4 | Thu | Treatment B | |
| 5 | Fri | Control A | Mid-experiment quality review |
| 6 | Sat | Treatment B | |
| 7 | Sun | Control A | Final baseline; compile results |

---

## Switching the Model

### Activate Gemini 2.5 Flash (Treatment B)

In NB6, the model is controlled by the `gemini_api_key` widget and the
`GEMINI_MODEL` variable. To switch, update the notebook variable or Databricks
job parameter:

```python
# NB6 — replace the ai_query() call block with:
import requests, json

GEMINI_MODEL = "gemini-2.5-flash"   # treatment
GEMINI_KEY   = dbutils.secrets.get("upsc-bot-secrets", "google-ai-key")

def call_gemini(prompt: str, system: str = "") -> str:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_KEY}"
    )
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "systemInstruction": {"parts": [{"text": system}]} if system else {},
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 4096},
    }
    resp = requests.post(url, json=body, timeout=60)
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
```

### Revert to Control A (Claude Sonnet)

```python
# NB6 — restore the original ai_query() call:
result = spark.sql(f"""
    SELECT ai_query(
        'databricks-claude-sonnet-4',
        '{prompt_escaped}'
    ) AS response
""").collect()[0]["response"]
```

---

## Metrics to Capture

Log all metrics to `upsc_catalog.rag.ab_experiment_log` (create if absent):

```sql
CREATE TABLE IF NOT EXISTS upsc_catalog.rag.ab_experiment_log (
    run_date      DATE,
    model_tag     STRING,   -- 'claude-sonnet-4' or 'gemini-2.5-flash'
    notebook      STRING,   -- 'NB6' or 'NB7'
    latency_secs  DOUBLE,
    input_tokens  BIGINT,
    output_tokens BIGINT,
    estimated_cost_usd DOUBLE,
    quality_score INT,      -- 1-5, manually rated after reading output
    notes         STRING
);
```

### Cost

| Metric | Where to find |
|---|---|
| Databricks DBU cost | Databricks → Jobs → select run → Cluster tab → DBU usage |
| Gemini API cost | Google Cloud Console → Billing → Vertex AI / Generative Language API |
| Groq (Hermes) | console.groq.com → Usage (free tier, track req count) |

### Latency

Wrap each LLM call with `time.time()` start/end and log to the table above.
Target: NB6 end-to-end ≤ 8 minutes, NB7 ≤ 12 minutes.

### Output Quality

After each day's run, read the generated CA story and practice questions and
score 1–5 on:

| Dimension | 1 (Poor) | 5 (Excellent) |
|---|---|---|
| Factual accuracy | Multiple errors | No errors |
| UPSC relevance | Generic content | GS Paper 2/3 linkage clear |
| Question difficulty | Too easy/trivial | Appropriate prelims/mains level |
| Writing style | Choppy, template-y | Fluent, examiner-voice |

Record in `quality_score` and `notes` columns.

---

## Success Criteria

The experiment is a **success for Gemini Flash** if:

- Cost reduction ≥ 40 % vs Claude Sonnet baseline
- Latency ≤ Claude baseline (or within 20 %)
- Average quality score ≥ 3.5 / 5 across 3 Treatment days

If Gemini Flash meets all three criteria, switch NB6/NB7 to Gemini permanently
and keep Claude Sonnet as the evaluation model for Hermes `/evaluate` command.

---

## Log Locations

| Log | Location |
|---|---|
| Experiment metrics table | `upsc_catalog.rag.ab_experiment_log` |
| NB6 run output | Databricks → Jobs → NB6_CA_Orchestrator → latest run |
| NB7 run output | Databricks → Jobs → NB7_Daily_CA_Practice → latest run |
| Hermes usage | `~/.hermes_memory.db` → `sessions` table |
| Obsidian vault output | `~/Desktop/UPSC_2027/01_Current_Affairs/` (Control A days) |
| GitHub backup | `data_snapshots/{date}/` (NB9 pushes daily) |

---

## Quick SQL to Review Results

```sql
-- Daily cost and quality summary
SELECT
    run_date,
    model_tag,
    SUM(estimated_cost_usd)   AS total_cost_usd,
    AVG(latency_secs)         AS avg_latency_secs,
    AVG(quality_score)        AS avg_quality
FROM upsc_catalog.rag.ab_experiment_log
GROUP BY run_date, model_tag
ORDER BY run_date;

-- Control vs Treatment aggregate
SELECT
    model_tag,
    COUNT(*)                  AS runs,
    SUM(estimated_cost_usd)   AS total_cost_usd,
    AVG(latency_secs)         AS avg_latency_secs,
    AVG(quality_score)        AS avg_quality
FROM upsc_catalog.rag.ab_experiment_log
GROUP BY model_tag;
```

---

## Notes

- The `$400` Google Cloud credit balance covers well over 1,000 Gemini 2.5 Flash
  runs at typical UPSC CA generation lengths (~3,000 output tokens per story).
- Keep `GOOGLE_AI_KEY` in Databricks secret scope `upsc-bot-secrets` under key
  `google-ai-key` (already stored — verified 2026-04-09).
- Do **not** run both models on the same day — it will distort the cost comparison.

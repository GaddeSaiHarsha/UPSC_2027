# Databricks notebook source
# DBTITLE 1,Notebook 4: UPSC Examiner Agent v2
# MAGIC %md
# MAGIC # Notebook 4: UPSC Examiner Agent v2 (KARL Pattern)
# MAGIC ### UPSC AI Tutor — Active Answer Evaluation
# MAGIC
# MAGIC **Retrieval:** FAISS agent endpoint (`agents_upsc_catalog-rag-upsc_tutor_agent`) — 80,800 chunks + Knowledge Graph
# MAGIC
# MAGIC **Enhancements over v1:**
# MAGIC 1. **Multi-Step Retrieval** — 3 queries per question (direct + legal provisions + case law/CA) via FAISS agent
# MAGIC 2. **Weighted Nuggets** — Critical (60%), Important (30%), Optional (10%)
# MAGIC 3. **Model Answer Generation** — Shows what a perfect answer looks like
# MAGIC 4. **Safe Delta INSERT** — DataFrame API, no SQL injection risk
# MAGIC
# MAGIC **Flow:** Question → Multi-query retrieval (FAISS) → Weighted nugget extraction → Answer evaluation → Model answer → Log to Delta

# COMMAND ----------

# DBTITLE 1,Install Dependencies
# MAGIC %pip install langchain langchain-community langchain-databricks -q
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# DBTITLE 1,Configuration
# ── CONFIGURATION ─────────────────────────────────────────────────────────
CATALOG          = "upsc_catalog"
SCHEMA           = "rag"
EVAL_TABLE       = f"{CATALOG}.{SCHEMA}.answer_evaluations"

LLM_ENDPOINT     = "databricks-claude-sonnet-4"
EMBEDDING_MODEL  = "databricks-qwen3-embedding-0-6b"
FAISS_AGENT_URL  = "https://adb-7405615460529826.6.azuredatabricks.net/serving-endpoints/agents_upsc_catalog-rag-upsc_tutor_agent/invocations"
MEMORY_WINDOW    = 5  # Conversation turns to remember
# ──────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# DBTITLE 1,Create Evaluation Table
# Ensure evaluation table exists with enhanced schema
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {EVAL_TABLE} (
    eval_id STRING,
    timestamp TIMESTAMP,
    subject STRING,
    question STRING,
    user_answer STRING,
    score_given FLOAT,
    max_marks INT,
    nuggets_found STRING,
    nuggets_missing STRING,
    structure_grade STRING,
    detailed_feedback STRING,
    model_answer STRING
) USING DELTA
""")
print(f"✅ Evaluation table ready: {EVAL_TABLE}")

# COMMAND ----------

# DBTITLE 1,Initialize LLM and Vector Search
import requests
import uuid
import json
import os
from datetime import datetime, timezone
from langchain_community.chat_models import ChatDatabricks
from langchain_core.prompts import ChatPromptTemplate
from pyspark.sql import Row
from pyspark.sql.types import StructType, StructField, StringType, FloatType, IntegerType, TimestampType

try:
    token = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
    host  = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiUrl().get()
except Exception:
    token = os.environ.get("DATABRICKS_TOKEN")
    host  = os.environ.get("DATABRICKS_HOST")

llm = ChatDatabricks(endpoint=LLM_ENDPOINT, max_tokens=2048, temperature=0.1)


def search_kb(query: str, top_k: int = 10) -> str:
    """Search UPSC knowledge base via FAISS-powered agent endpoint (replaces Vector Search)."""
    payload = {
        "messages": [
            {"role": "user", "content": f"Search knowledge base for: {query}. Return top {top_k} relevant chunks."}
        ]
    }

    resp = requests.post(
        FAISS_AGENT_URL,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=120
    )

    try:
        data = resp.json()
        # Extract the text output from the agent's prediction array
        for item in data.get("predictions", {}).get("output", []):
            if isinstance(item, str):
                return item
            elif isinstance(item, dict) and "text" in item:
                return item["text"]
        return str(data)  # Fallback if structure varies
    except Exception as e:
        return f"Error querying FAISS agent: {str(e)}"


print("✅ LLM + FAISS agent search ready")

# COMMAND ----------

# DBTITLE 1,Enhancement 1: Multi-Step Retrieval
# ═══════════════════════════════════════════════════════════════════════════
# ENHANCEMENT 1: Multi-Step Agentic Retrieval (3 query angles)
# Now uses FAISS agent endpoint instead of Vector Search Classic
# ═══════════════════════════════════════════════════════════════════════════

def get_context_multiquery(question: str, subject: str = "General Studies") -> str:
    """
    Multi-step retrieval: 3 queries for broader coverage via FAISS agent.
    - Query 1: Direct question
    - Query 2: Constitutional/legal provisions related
    - Query 3: Supreme Court cases + current affairs
    """
    queries = [
        question,
        f"Constitutional provisions, Articles, and legal framework related to: {question}",
        f"Supreme Court judgments, current affairs, and recent developments on: {question}"
    ]

    all_contexts = []
    for q in queries:
        result = search_kb(q, top_k=5)
        if result and not result.startswith("Error"):
            all_contexts.append(result)

    print(f"   Retrieved context from {len(all_contexts)}/{len(queries)} queries via FAISS agent")
    return "\n\n---\n\n".join(all_contexts)

print("✅ Multi-step retrieval ready (FAISS agent endpoint)")

# COMMAND ----------

# DBTITLE 1,Enhancement 2: Weighted Nugget Extraction
# ═══════════════════════════════════════════════════════════════════════════
# ENHANCEMENT 2: Weighted Nuggets (Critical/Important/Optional)
# ═══════════════════════════════════════════════════════════════════════════

def extract_weighted_nuggets(context: str, question: str) -> dict:
    """
    Categorizes nuggets by priority:
    - CRITICAL (60%): Constitutional articles, landmark SC cases, statutory provisions
    - IMPORTANT (30%): Key concepts, definitions, mechanisms
    - OPTIONAL (10%): Examples, current affairs, recent developments
    """
    nugget_prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a strict UPSC Chief Examiner. Based on the authoritative context, categorize knowledge nuggets into three priority levels:

CRITICAL (Must-have): Constitutional articles, landmark Supreme Court cases, statutory provisions, key definitions that UPSC markers look for.
IMPORTANT (Should-have): Key concepts, mechanisms, committees, historical background.
OPTIONAL (Good-to-have): Examples, recent developments, current affairs connections, international comparisons.

Output ONLY valid JSON (no markdown, no explanation):
{{
    "critical": ["Article 21", "Maneka Gandhi v Union of India"],
    "important": ["Procedure established by law vs Due process", "Positive and negative rights"],
    "optional": ["COVID-19 impact on Article 21", "Right to clean environment"]
}}"""),
        ("human", "Context:\n{context}\n\nQuestion: {question}\n\nGenerate weighted nuggets JSON:")
    ])
    
    chain = nugget_prompt | llm
    raw = chain.invoke({"context": context, "question": question}).content
    
    try:
        clean_json = raw.replace('```json', '').replace('```', '').strip()
        nuggets = json.loads(clean_json)
        # Ensure all keys exist
        for key in ['critical', 'important', 'optional']:
            if key not in nuggets:
                nuggets[key] = []
        return nuggets
    except:
        return {"critical": [], "important": [raw], "optional": []}

def calculate_weighted_score(nuggets_found: dict, nuggets_missing: dict, max_marks: int) -> float:
    """Score based on: Critical 60%, Important 30%, Optional 10%."""
    weights = {'critical': 0.60, 'important': 0.30, 'optional': 0.10}
    score = 0.0
    
    for level, weight in weights.items():
        found = len(nuggets_found.get(level, []))
        missing = len(nuggets_missing.get(level, []))
        total = found + missing
        if total > 0:
            score += (found / total) * max_marks * weight
    
    return round(score, 2)

print("✅ Weighted nugget extraction ready")

# COMMAND ----------

# DBTITLE 1,Enhancement 3: Model Answer Generation
# ═══════════════════════════════════════════════════════════════════════════
# ENHANCEMENT 3: Model Answer Generation
# ═══════════════════════════════════════════════════════════════════════════

def generate_model_answer(question: str, nuggets: dict, max_marks: int) -> str:
    """Generate a UPSC-standard model answer using extracted nuggets."""
    model_prompt = ChatPromptTemplate.from_messages([
        ("system", """You are writing a perfect UPSC Mains answer scoring {max_marks}/{max_marks}.

Use ALL provided nuggets in proper UPSC structure:
- Introduction (1-2 sentences): Define topic, state its significance
- Body (structured paragraphs):
  * CRITICAL nuggets first (constitutional provisions, cases)
  * IMPORTANT nuggets next (concepts, mechanisms)
  * OPTIONAL nuggets last (examples, current affairs)
- Conclusion (1-2 sentences): Forward-looking, balanced

Word limit: ~250 words for 15 marks, ~150 for 10 marks.
Cite Article numbers, case names, committee names explicitly.
Use clear headings and bullet points where appropriate."""),
        ("human", "Question: {question}\n\nNuggets to include:\nCRITICAL: {critical}\nIMPORTANT: {important}\nOPTIONAL: {optional}\n\nWrite the model answer:")
    ])
    
    chain = model_prompt | llm
    return chain.invoke({
        "max_marks": max_marks,
        "question": question,
        "critical": nuggets.get('critical', []),
        "important": nuggets.get('important', []),
        "optional": nuggets.get('optional', [])
    }).content

print("✅ Model answer generator ready")

# COMMAND ----------

# DBTITLE 1,Main Evaluator v2
# ═══════════════════════════════════════════════════════════════════════════
# THE EXAMINER: Complete Evaluation Pipeline v2 (with Dual-Agent Validator)
# ═══════════════════════════════════════════════════════════════════════════

def evaluate_upsc_answer_v2(
    question: str, 
    user_answer: str, 
    max_marks: int = 15, 
    subject: str = "General Studies"
) -> dict:
    """
    Enhanced KARL-inspired evaluation with Dual-Agent Validation:
    1. Multi-step retrieval (3 queries)
    2. Weighted nuggets (critical/important/optional)
    3. Strict evaluation against nuggets
    3.5. VALIDATOR reviews evaluation for hallucinations
    4. Model answer for comparison
    5. Log to Delta table
    """
    print("🔍 1. Multi-step retrieval (3 perspectives)...")
    context = get_context_multiquery(question, subject)
    
    print("⛏️  2. Extracting weighted nuggets...")
    nuggets = extract_weighted_nuggets(context, question)
    nc = len(nuggets.get('critical',[])); ni = len(nuggets.get('important',[])); no = len(nuggets.get('optional',[]))
    print(f"   CRITICAL: {nc}, IMPORTANT: {ni}, OPTIONAL: {no}")
    
    print("📝 3. Evaluating student answer...")
    eval_prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a strict UPSC Evaluator grading a Mains answer out of {max_marks} marks.

You have weighted Gold Standard Nuggets. Check the student's answer against these nuggets.

UPSC Marking Rubric:
- Introduction & Conclusion present: 15% of marks
- CRITICAL nuggets (Articles, cases, provisions): 60% of marks
- IMPORTANT nuggets (concepts, mechanisms): 30% of marks  
- OPTIONAL nuggets (examples, CA): 10% of marks (bonus)
- Structure & Flow: Included in structure_grade
- A "perfect" UPSC answer rarely scores above 65% (e.g., 9.5/15 is excellent). Be strict.

Respond ONLY with valid JSON:
{{
    "nuggets_found": {{"critical": ["list"], "important": ["list"], "optional": ["list"]}},
    "nuggets_missing": {{"critical": ["list"], "important": ["list"], "optional": ["list"]}},
    "structure_grade": "A/B/C/D",
    "detailed_feedback": "2-3 sentences of strict, actionable feedback"
}}"""),
        ("human", "Question: {question}\n\nExpected Nuggets:\nCRITICAL: {critical}\nIMPORTANT: {important}\nOPTIONAL: {optional}\n\nStudent Answer:\n{user_answer}")
    ])
    
    eval_chain = eval_prompt | llm
    raw_eval = eval_chain.invoke({
        "max_marks": max_marks,
        "question": question,
        "critical": nuggets.get('critical', []),
        "important": nuggets.get('important', []),
        "optional": nuggets.get('optional', []),
        "user_answer": user_answer
    }).content
    
    try:
        clean_eval = raw_eval.replace('```json', '').replace('```', '').strip()
        evaluation = json.loads(clean_eval)
    except Exception as e:
        print(f"⚠️ JSON parse error: {e}")
        print(f"   Raw: {raw_eval[:300]}")
        return None
    
    # Calculate weighted score
    score = calculate_weighted_score(
        evaluation.get('nuggets_found', {}),
        evaluation.get('nuggets_missing', {}),
        max_marks
    )
    evaluation['score'] = score
    
    # ── UPGRADE 2: DUAL-AGENT VALIDATION ──────────────────────────────────
    print("✅ 3.5. Validator reviewing evaluation for hallucinations...")
    evaluation = validate_evaluation(evaluation, question, user_answer, max_marks)
    checks = evaluation.get('validation_checks', {})
    flags = [k for k, v in checks.items() if v is False]
    if flags:
        print(f"   ⚠️ Flags: {', '.join(flags)}")
    else:
        print(f"   ✅ All validation checks passed")
    if evaluation.get('priority_fix'):
        print(f"   🎯 Priority Fix: {evaluation['priority_fix']}")
    # ─────────────────────────────────────────────────────────────────────
    
    print("📄 4. Generating model answer for comparison...")
    model_ans = generate_model_answer(question, nuggets, max_marks)
    evaluation['model_answer'] = model_ans
    
    print("💾 5. Logging to Delta table...")
    eval_id = str(uuid.uuid4())
    
    # Safe DataFrame-based INSERT (no SQL injection)
    eval_row = Row(
        eval_id=eval_id,
        timestamp=datetime.now(timezone.utc),
        subject=subject,
        question=question,
        user_answer=user_answer,
        score_given=float(evaluation.get('score', 0)),
        max_marks=max_marks,
        nuggets_found=json.dumps(evaluation.get('nuggets_found', {})),
        nuggets_missing=json.dumps(evaluation.get('nuggets_missing', {})),
        structure_grade=evaluation.get('structure_grade', 'N/A'),
        detailed_feedback=evaluation.get('detailed_feedback', '') + 
            f"\n\n[VALIDATOR] {evaluation.get('validator_notes', '')}" +
            f"\n[PRIORITY FIX] {evaluation.get('priority_fix', '')}",
        model_answer=model_ans
    )
    
    schema = StructType([
        StructField("eval_id", StringType()),
        StructField("timestamp", TimestampType()),
        StructField("subject", StringType()),
        StructField("question", StringType()),
        StructField("user_answer", StringType()),
        StructField("score_given", FloatType()),
        StructField("max_marks", IntegerType()),
        StructField("nuggets_found", StringType()),
        StructField("nuggets_missing", StringType()),
        StructField("structure_grade", StringType()),
        StructField("detailed_feedback", StringType()),
        StructField("model_answer", StringType()),
    ])
    
    spark.createDataFrame([eval_row], schema).write.mode("append").saveAsTable(EVAL_TABLE)
    print(f"   ✅ Logged eval {eval_id[:8]}...")
    
    return evaluation

print("✅ Examiner v2 ready (with Dual-Agent Validator)")

# COMMAND ----------

# DBTITLE 1,Upgrade 2: Dual-Agent Validator
# ═══════════════════════════════════════════════════════════════════════════
# UPGRADE 2: DUAL-AGENT VALIDATOR
# Reviews the evaluator's output to catch grading hallucinations
# Uses same ChatDatabricks llm.invoke() pattern as extract_weighted_nuggets()
# ═══════════════════════════════════════════════════════════════════════════

def validate_evaluation(evaluation: dict, question: str, user_answer: str, max_marks: int) -> dict:
    """
    Second-pass validator that checks the evaluator's output for:
    1. Constitutional articles actually cited in the answer?
    2. Landmark SC cases referenced?
    3. Forward-looking conclusion present?
    4. Word count appropriate for marks?
    5. Score consistency with nuggets found/missing
    
    Returns revised evaluation with 'validator_notes' and 'priority_fix' fields.
    """
    validator_prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a VALIDATOR reviewing another AI's evaluation of a UPSC Mains answer.
Your job is to catch grading hallucinations and inconsistencies.

CHECK THESE 5 THINGS:
1. ARTICLES CHECK: Does the evaluator claim constitutional articles were found? Verify they actually appear in the student's answer text.
2. CASE LAW CHECK: Does the evaluator claim SC/HC cases were cited? Verify the case names exist in the answer.
3. CONCLUSION CHECK: Does the student's answer have a forward-looking conclusion (Way Forward / Suggestions)?
4. WORD COUNT CHECK: Is the answer roughly appropriate for {max_marks} marks? (Rule of thumb: ~30 words per mark)
5. SCORE CONSISTENCY: Given nuggets_found vs nuggets_missing, is the score reasonable? A score > 65% should be rare.

Respond ONLY with valid JSON:
{{
    "articles_verified": true/false,
    "cases_verified": true/false,
    "has_conclusion": true/false,
    "word_count_ok": true/false,
    "score_consistent": true/false,
    "revised_score": <float or null if no change needed>,
    "validator_notes": "2-3 sentences explaining any issues found",
    "priority_fix": "ONE specific thing the student should fix first"
}}"""),
        ("human", """QUESTION: {question}

STUDENT ANSWER:
{user_answer}

EVALUATOR'S OUTPUT:
- Score: {score}/{max_marks}
- Nuggets Found: {nuggets_found}
- Nuggets Missing: {nuggets_missing}
- Structure Grade: {structure_grade}
- Feedback: {feedback}

Please validate this evaluation.""")
    ])
    
    validator_chain = validator_prompt | llm
    raw_validation = validator_chain.invoke({
        "max_marks": max_marks,
        "question": question,
        "user_answer": user_answer,
        "score": evaluation.get('score', 0),
        "nuggets_found": json.dumps(evaluation.get('nuggets_found', {})),
        "nuggets_missing": json.dumps(evaluation.get('nuggets_missing', {})),
        "structure_grade": evaluation.get('structure_grade', 'N/A'),
        "feedback": evaluation.get('detailed_feedback', '')
    }).content
    
    try:
        clean = raw_validation.replace('```json', '').replace('```', '').strip()
        validation = json.loads(clean)
    except Exception as e:
        print(f"⚠️ Validator JSON parse error: {e}")
        validation = {
            "validator_notes": f"Parse error: {raw_validation[:200]}",
            "priority_fix": "Unable to validate — review manually"
        }
    
    # Apply revised score if validator disagrees
    if validation.get('revised_score') is not None:
        old_score = evaluation.get('score', 0)
        new_score = validation['revised_score']
        if abs(old_score - new_score) > 0.5:  # Only override if significant difference
            evaluation['score_before_validation'] = old_score
            evaluation['score'] = new_score
            print(f"   🔄 Score revised: {old_score:.1f} → {new_score:.1f}")
    
    evaluation['validator_notes'] = validation.get('validator_notes', '')
    evaluation['priority_fix'] = validation.get('priority_fix', '')
    evaluation['validation_checks'] = {
        'articles_verified': validation.get('articles_verified', None),
        'cases_verified': validation.get('cases_verified', None),
        'has_conclusion': validation.get('has_conclusion', None),
        'word_count_ok': validation.get('word_count_ok', None),
        'score_consistent': validation.get('score_consistent', None)
    }
    
    return evaluation

print("✅ Dual-Agent Validator ready")
print("   Validator checks: Articles, Case Law, Conclusion, Word Count, Score Consistency")

# COMMAND ----------

# DBTITLE 1,Test the Examiner
# ═══════════════════════════════════════════════════════════════════════════
# TEST: Above-average student answer on a classic GS-2 question
# ═══════════════════════════════════════════════════════════════════════════

test_question = """Discuss the role of the Finance Commission in maintaining fiscal federalism in India. How far has it succeeded in addressing the horizontal and vertical imbalances?"""

# Above-average student answer: knows key concepts, mentions some Articles,
# but misses specific FC recommendations, landmark cases, and recent developments
student_answer = """
The Finance Commission is a constitutional body established under Article 280 of the Indian Constitution. It is appointed by the President every five years to recommend the distribution of tax revenues between the Centre and the States.

The FC plays a crucial role in fiscal federalism by addressing two types of imbalances:

1. Vertical imbalance: The Centre collects most taxes (income tax, GST) but States handle major expenditures like health, education, and law & order. The FC recommends the share of central taxes to be devolved to States. The 15th FC recommended 41% devolution to States.

2. Horizontal imbalance: Different States have varying capacities to raise revenue. Poorer States like Bihar and UP need more grants. The FC uses criteria like population, area, income distance, and forest cover to distribute funds equitably among States.

The FC has also recommended grants-in-aid under Article 275 for States with revenue deficits. Special grants are given for disaster management and local bodies.

However, there are several challenges. States often complain that the FC recommendations are not fully implemented. The increasing use of cesses and surcharges by the Centre reduces the divisible pool, effectively reducing States' share. GST implementation has also created new fiscal tensions between Centre and States regarding compensation.

The FC has largely succeeded in maintaining a framework for fiscal federalism, but the growing tendency of centralisation through conditional transfers and CSS schemes undermines true fiscal autonomy of States.

In conclusion, while the Finance Commission remains the cornerstone of India's fiscal federalism, there is need for strengthening its recommendations' binding nature and reducing the Centre's tendency to bypass the devolution framework through extra-constitutional mechanisms.
"""

print("=" * 70)
print(f"✍️  QUESTION: {test_question.strip()}")
print("=" * 70)
print(f"📝 Student answer: {len(student_answer.split())} words")
print("=" * 70)

result = evaluate_upsc_answer_v2(
    question=test_question.strip(),
    user_answer=student_answer.strip(),
    max_marks=15,
    subject="Polity"
)

if result:
    print("\n" + "=" * 70)
    print(f"🏆 WEIGHTED SCORE: {result['score']:.2f} / 15")
    print(f"📑 STRUCTURE GRADE: {result['structure_grade']}")
    print("=" * 70)
    
    print("\n✅ NUGGETS HIT:")
    nf = result.get('nuggets_found', {})
    print(f"  CRITICAL:  {', '.join(nf.get('critical', ['None']))}")
    print(f"  IMPORTANT: {', '.join(nf.get('important', ['None']))}")
    print(f"  OPTIONAL:  {', '.join(nf.get('optional', ['None']))}")
    
    print("\n❌ NUGGETS MISSED:")
    nm = result.get('nuggets_missing', {})
    print(f"  CRITICAL:  {', '.join(nm.get('critical', ['None']))}")
    print(f"  IMPORTANT: {', '.join(nm.get('important', ['None']))}")
    print(f"  OPTIONAL:  {', '.join(nm.get('optional', ['None']))}")
    
    print("\n" + "-" * 70)
    print(f"🗣️  EXAMINER FEEDBACK:\n{result['detailed_feedback']}")
    print("-" * 70)
    
    print("\n📚 MODEL ANSWER (What a perfect answer looks like):")
    print(result['model_answer'])
    print("=" * 70)


# ── MLFLOW TRACKING — Added 2026-03-27 ──────────────────────────────────────
# Logs every KARL evaluation to MLflow Experiments
# View at: Experiments → /Users/your_email/UPSC_Answer_Quality

import mlflow
from datetime import datetime

def log_karl_score(subject: str, gs_paper: str, question: str,
                   score: float, grade: str, missing_nuggets: str,
                   your_answer: str = "", model_answer: str = ""):
    """Log a KARL evaluation to MLflow. Call after every NB4 evaluation."""

    mlflow.set_experiment("/Users/admin@mngenvmcap915189.onmicrosoft.com/UPSC_Answer_Quality")

    with mlflow.start_run(run_name=f"KARL_{datetime.now().strftime('%Y%m%d')}_{subject}"):
        # Params
        mlflow.log_param("subject",   subject)
        mlflow.log_param("gs_paper",  gs_paper)
        mlflow.log_param("question",  question[:200])
        mlflow.log_param("grade",     grade)
        mlflow.log_param("date",      datetime.now().strftime("%Y-%m-%d"))

        # Metrics
        mlflow.log_metric("karl_score", score)
        mlflow.log_metric("score_pct",  round(score / 15 * 100, 1))

        # Artifacts
        if your_answer:
            mlflow.log_text(your_answer,  "student_answer.txt")
        if model_answer:
            mlflow.log_text(model_answer, "model_answer.txt")
        if missing_nuggets:
            mlflow.log_text(missing_nuggets, "missing_nuggets.txt")

    # Also write to Delta table for Genie queries
    from pyspark.sql import Row
    spark.createDataFrame([Row(
        eval_id   = f"eval_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        date      = datetime.now().strftime("%Y-%m-%d"),
        subject   = subject,
        gs_paper  = gs_paper,
        question  = question,
        score     = score,
        grade     = grade,
        missing_critical = missing_nuggets
    )]).write.mode("append").saveAsTable("upsc_catalog.rag.answer_evaluations")

    print(f"✅ Logged KARL score {score}/15 ({grade}) for {subject} to MLflow + Delta")

print("✅ MLflow KARL logger ready — call log_karl_score() after each evaluation")
print("   View trends at: Experiments → UPSC_Answer_Quality")
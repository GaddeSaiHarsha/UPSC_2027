# Databricks notebook source
# DBTITLE 1,Notebook 5: Weakness Tracker
# MAGIC %md
# MAGIC # Notebook 5: Weakness Tracker & Adaptive Study Planner
# MAGIC ### UPSC AI Tutor — Pattern Detection at Scale
# MAGIC
# MAGIC **What this does:**
# MAGIC - Analyzes all evaluated answers from `answer_evaluations` table
# MAGIC - Detects patterns: Which nugget types do you consistently miss?
# MAGIC - Tracks weekly improvement trends
# MAGIC - Generates adaptive study plan for next week
# MAGIC - Predicts Prelims readiness
# MAGIC
# MAGIC **Requires:** At least 10-20 evaluated answers from Notebook 4

# COMMAND ----------

# DBTITLE 1,Configuration and Load Data
from pyspark.sql.functions import *
from pyspark.sql.types import *
import json
from datetime import datetime, timezone, timedelta

EVAL_TABLE = "upsc_catalog.rag.answer_evaluations"

# Load all evaluations
try:
    evaluations_df = spark.table(EVAL_TABLE)
    total_answers = evaluations_df.count()
    print(f"📊 Total Answers Evaluated: {total_answers}")
    
    if total_answers > 0:
        date_range = evaluations_df.agg(min('timestamp').alias('first'), max('timestamp').alias('last')).collect()[0]
        print(f"📅 Date Range: {date_range['first']} to {date_range['last']}")
    else:
        print("⚠️ No evaluations yet. Write answers using Notebook 4 first!")
except Exception as e:
    print(f"❌ Table not found: {e}")
    print("   Run Notebook 4 first to create the evaluation table.")
    total_answers = 0

# COMMAND ----------

# DBTITLE 1,Subject-Wise Performance
# Subject-wise performance breakdown
if total_answers > 0:
    subject_stats = evaluations_df.groupBy("subject").agg(
        count("*").alias("total_answers"),
        round(avg("score_given"), 2).alias("avg_score"),
        round(avg("max_marks"), 1).alias("avg_max_marks"),
        round(min("score_given"), 2).alias("min_score"),
        round(max("score_given"), 2).alias("max_score")
    ).withColumn(
        "accuracy_pct", round(col("avg_score") / col("avg_max_marks") * 100, 1)
    ).orderBy("accuracy_pct")
    
    print("📈 Subject-Wise Performance (Weakest First):")
    display(subject_stats)
else:
    print("⚠️ Need evaluation data. Run Notebook 4 to evaluate answers first.")

# COMMAND ----------

# DBTITLE 1,Critical Missing Nuggets Analysis
# Find the most frequently missed CRITICAL nuggets
if total_answers > 0:
    # Parse JSON nuggets_missing column
    missing_df = evaluations_df.select(
        "subject",
        "nuggets_missing"
    ).filter(col("nuggets_missing").isNotNull())
    
    # Try to parse as JSON and extract critical nuggets
    try:
        from pyspark.sql.functions import from_json, schema_of_json, explode_outer
        
        # Define schema for nuggets JSON
        nugget_schema = StructType([
            StructField("critical", ArrayType(StringType())),
            StructField("important", ArrayType(StringType())),
            StructField("optional", ArrayType(StringType()))
        ])
        
        parsed = missing_df.withColumn(
            "parsed", from_json(col("nuggets_missing"), nugget_schema)
        ).filter(col("parsed").isNotNull())
        
        # Critical nuggets missed
        critical_missed = parsed.select(
            "subject",
            explode_outer(col("parsed.critical")).alias("nugget")
        ).filter(col("nugget").isNotNull()).groupBy(
            "subject", "nugget"
        ).agg(
            count("*").alias("times_missed")
        ).orderBy(desc("times_missed"))
        
        print("🔴 Most Frequently Missed CRITICAL Nuggets:")
        display(critical_missed.limit(20))
        
        # Important nuggets missed
        important_missed = parsed.select(
            "subject",
            explode_outer(col("parsed.important")).alias("nugget")
        ).filter(col("nugget").isNotNull()).groupBy(
            "subject", "nugget"
        ).agg(
            count("*").alias("times_missed")
        ).orderBy(desc("times_missed"))
        
        print("\n🟠 Most Frequently Missed IMPORTANT Nuggets:")
        display(important_missed.limit(15))
        
    except Exception as e:
        # Fallback for non-JSON format (v1 evaluations)
        print(f"Parsing as plain text (v1 format): {e}")
        plain_missed = missing_df.groupBy("subject", "nuggets_missing").agg(
            count("*").alias("times_missed")
        ).orderBy(desc("times_missed"))
        display(plain_missed.limit(20))

# COMMAND ----------

# DBTITLE 1,Weekly Progress Trends
# Track improvement over time
if total_answers >= 5:
    weekly_progress = evaluations_df.withColumn(
        "week", date_trunc("week", "timestamp")
    ).groupBy("week").agg(
        count("*").alias("answers_written"),
        round(avg("score_given"), 2).alias("avg_score"),
        round(avg("max_marks"), 1).alias("avg_max_marks"),
        round(avg("score_given") / avg("max_marks") * 100, 1).alias("accuracy_pct")
    ).orderBy("week")
    
    print("📅 Weekly Improvement Trend:")
    display(weekly_progress)
    
    # Check if improving
    weeks = weekly_progress.collect()
    if len(weeks) >= 2:
        first_acc = weeks[0]['accuracy_pct']
        last_acc = weeks[-1]['accuracy_pct']
        delta = last_acc - first_acc
        if delta > 0:
            print(f"📈 Improving! +{delta:.1f}% from first to latest week")
        elif delta < 0:
            print(f"📉 Declining: {delta:.1f}% - review study strategy")
        else:
            print("➡️ Flat - need to change approach for weak areas")
else:
    print(f"⚠️ Need at least 5 evaluations for trend analysis (have {total_answers})")

# COMMAND ----------

# DBTITLE 1,Structure Grade Distribution
# How well are answers structured?
if total_answers > 0:
    structure_dist = evaluations_df.groupBy("structure_grade").agg(
        count("*").alias("count")
    ).orderBy("structure_grade")
    
    print("📝 Structure Grade Distribution:")
    display(structure_dist)
    
    # Get most common grade
    top_grade = structure_dist.orderBy(desc("count")).first()
    if top_grade:
        print(f"\nMost common structure grade: {top_grade['structure_grade']} ({top_grade['count']} answers)")
        if top_grade['structure_grade'] in ['C', 'D']:
            print("⚠️ Focus on answer structure: Intro → Body (with headings) → Conclusion")

# COMMAND ----------

# DBTITLE 1,Adaptive Study Plan Generator
# Generate personalized study plan based on weakness patterns
if total_answers >= 5:
    # Get weak subjects
    weak_subjects = subject_stats.filter(col("total_answers") >= 2).orderBy("accuracy_pct").limit(5).collect()
    
    # Get top missed critical nuggets  
    try:
        top_missed = critical_missed.limit(10).collect()
    except:
        top_missed = []
    
    plan = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "total_answers_analyzed": total_answers,
        "priority_subjects": [
            {
                "subject": row['subject'],
                "current_accuracy": float(row['accuracy_pct']),
                "target_accuracy": min(65.0, float(row['accuracy_pct']) + 10),
                "daily_hours": 2.0 if float(row['accuracy_pct']) < 40 else 1.0,
                "answers_evaluated": row['total_answers']
            }
            for row in weak_subjects
        ],
        "critical_nuggets_to_master": [
            {
                "nugget": row['nugget'],
                "subject": row['subject'],
                "times_missed": row['times_missed'],
                "action": f"Create flashcard + practice 3 questions on '{row['nugget']}'"
            }
            for row in top_missed
        ],
        "daily_routine": [
            "Morning (6-7 AM): Study weakest subject from priority list",
            "Afternoon (2-3 PM): Write 1 Mains answer on weak topic",
            "Evening (7-8 PM): Evaluate with Notebook 4 + review model answer",
            "Before bed: Review 10 flashcards (critical missed nuggets)"
        ]
    }
    
    print("\n" + "=" * 70)
    print("📋 ADAPTIVE STUDY PLAN")
    print("=" * 70)
    print(json.dumps(plan, indent=2))
    print("=" * 70)
    
    # Save plan to volume for Obsidian export
    plan_path = "/Volumes/upsc_catalog/rag/documents/latest_study_plan.json"
    try:
        with open(plan_path, 'w') as f:
            json.dump(plan, f, indent=2)
        print(f"\n💾 Plan saved to {plan_path}")
    except:
        pass
else:
    print(f"⚠️ Need at least 5 evaluated answers for a study plan (have {total_answers})")
    print("   Go to Notebook 4 and evaluate some answers first!")

# COMMAND ----------

# DBTITLE 1,Predicted Prelims Readiness
# Rough readiness estimator
if total_answers >= 10:
    current_avg = evaluations_df.agg(avg(col("score_given") / col("max_marks") * 100)).collect()[0][0]
    
    # UPSC Prelims: 100 Qs x 2 marks = 200. Cutoff usually ~110-120
    # Use Mains writing accuracy as a proxy (with 0.85 factor for Prelims traps)
    predicted_prelims = round(current_avg / 100 * 200 * 0.85, 1)
    
    print(f"🎯 READINESS ESTIMATE")
    print(f"   Current avg accuracy: {current_avg:.1f}%")
    print(f"   Predicted Prelims score: {predicted_prelims} / 200")
    print(f"   Target for safe selection: 115-120 / 200")
    
    gap = max(0, 115 - predicted_prelims)
    if gap == 0:
        print("   ✅ On track for comfortable Prelims clearance!")
    elif gap < 20:
        print(f"   ⚠️ Borderline - need {gap:.0f} more marks. Focus on weak areas.")
    else:
        print(f"   🔴 Gap of {gap:.0f} marks. Intensive revision needed.")
else:
    print(f"Need at least 10 evaluations for readiness prediction (have {total_answers})")
    print("Keep evaluating with Notebook 4!")

# COMMAND ----------

# DBTITLE 1,Next Steps
# MAGIC %md
# MAGIC ## What to Do Next
# MAGIC
# MAGIC 1. **Write 20 answers** using Notebook 4 → builds your evaluation dataset
# MAGIC 2. **Run this notebook weekly** (Saturday) → see patterns emerge
# MAGIC 3. **Focus on CRITICAL missed nuggets** → these are your mark-losers
# MAGIC 4. **Track weekly accuracy_pct** → if flat for 2 weeks, change strategy
# MAGIC 5. **Export study plan** to Obsidian for daily tracking
# MAGIC
# MAGIC **Target timeline:**
# MAGIC - Week 1-2: Write 20 answers, evaluate all
# MAGIC - Week 3-4: First meaningful trends appear
# MAGIC - Month 2+: Adaptive plans become highly personalized
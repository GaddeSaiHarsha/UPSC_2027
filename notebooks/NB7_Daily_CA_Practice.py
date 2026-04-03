# Databricks notebook source
# DBTITLE 1,Daily CA Practice Generator
# MAGIC %md
# MAGIC # Daily CA Practice Generator
# MAGIC ### Auto-generates UPSC practice material from today's Current Affairs + Telugu Optional
# MAGIC
# MAGIC **Schedule:** 8:00 AM IST daily | **Job:** [UPSC Daily CA Practice (8 AM IST)](#job-997836468367268) | **Depends on:** NB6 CA Orchestrator (7 AM IST)
# MAGIC
# MAGIC **Pipeline position:**
# MAGIC ```
# MAGIC 7:00 AM  NB6 CA Orchestrator    Perplexity → Delta → Embeddings → Obsidian
# MAGIC          │                      (stories, story_traps, deep_analysis, chunks)
# MAGIC          ▼
# MAGIC 8:00 AM  THIS NOTEBOOK           Delta tables → ai_query (Claude Sonnet 4) → Practice material
# MAGIC          │                      (8 modes: Q&A, KARL, MCQs, Ethics, Model Answers, Telugu, Tutor, Phone)
# MAGIC          ▼
# MAGIC Anytime  Morning Dashboard       Visual summary of all the above
# MAGIC          Review App (phone)      Chat with the UPSC AI Tutor agent
# MAGIC ```
# MAGIC
# MAGIC **8 Practice Modes:**
# MAGIC
# MAGIC | # | Mode | Input | Output |
# MAGIC |---|------|-------|--------|
# MAGIC | 1 | **Knowledge Q&A** | Top CA story + 65K textbook chunks (keyword match) | 15-mark Mains answer with Article citations, source files |
# MAGIC | 2 | **KARL Answer Evaluation** | Today's CA chunks | Auto question → sample answer → strict scoring (Critical 60% / Important 30% / Optional 10%) → model answer |
# MAGIC | 3 | **Prelims MCQs** | Stories + NB6 `story_traps` | 5 MCQs with trap-based wrong options, trap_type classification |
# MAGIC | 4 | **Ethics Case Study (GS4)** | CA stories + Ethics PYQs | Case study → stakeholder map → thinkers (Kant/Gandhi/Kautilya) → dilemma resolution → model answer |
# MAGIC | 5 | **Mains Model Answers + Interlinking** | `deep_analysis` + `geography_context` + `story_traps` | Cross-subject map (GS1-4 + Essay) → structured model answers → textbook anchors → PYQ connections |
# MAGIC | 6 | **Telugu Optional (Paper 1 & 2)** | 8,518 Telugu chunks (PYQs + Lakshmi Kanth + ఆంధ్ర మహాభారతం) | 5 PYQ model answers → approach + structure + తెలుగు సాహిత్య పదాలు + scoring tips |
# MAGIC | 7 | **AI Tutor Brief** *(NEW)* | Stories + traps + deep_analysis | 5-min tutor session: practice answer + model answer + memory hooks + revision plan |
# MAGIC | 8 | **Phone Summary** *(NEW)* | Modes 1, 5, 7 outputs | 2-3 min emoji-formatted quick read → saved to Obsidian vault |
# MAGIC
# MAGIC **Data sources:**
# MAGIC * `upsc_catalog.rag.stories` — today's CA stories (from NB6 Perplexity fetch)
# MAGIC * `upsc_catalog.rag.story_traps` — UPSC exam traps per story (from NB6)
# MAGIC * `upsc_catalog.rag.deep_analysis` — PYQ patterns, mains skeletons, static links (from NB6)
# MAGIC * `upsc_catalog.rag.geography_context` — strategic location mapping (from NB6)
# MAGIC * `upsc_catalog.rag.contextual_chunks` — **80,854 chunks** (textbooks + CA + PYQs + Telugu Optional 8,518)
# MAGIC * LLM: `databricks-claude-sonnet-4` via `ai_query()`
# MAGIC
# MAGIC **Note:** If NB6 hasn't run yet today, Modes 1-5 return NULL (no stories for current_date). Mode 6 (Telugu) works anytime. Modes 7-8 require today's stories.
# MAGIC
# MAGIC **Dedicated Telugu notebook:** [Telugu Optional Study System](#notebook-138096049883218) — syllabus tracker, period-wise generators, PYQ analysis, literary terms, practice

# COMMAND ----------

# DBTITLE 1,Mode 1: Knowledge Q&A
# MAGIC %sql
# MAGIC -- ═══════════════════════════════════════════════════════════════════════════
# MAGIC -- MODE 1: Knowledge Q&A — Today's top CA story + static textbook context
# MAGIC -- Uses 59,177 chunks (Laxmikanth 8e, Spectrum, PYQs, Economic Survey...)
# MAGIC -- ═══════════════════════════════════════════════════════════════════════════
# MAGIC WITH todays_stories AS (
# MAGIC   SELECT title, slug, gs_papers, topic_cluster, story_id
# MAGIC   FROM upsc_catalog.rag.stories
# MAGIC   WHERE date = cast(current_date() AS STRING)
# MAGIC   ORDER BY CASE priority WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2 WHEN 'MEDIUM' THEN 3 ELSE 4 END
# MAGIC   LIMIT 1
# MAGIC ),
# MAGIC ca_context AS (
# MAGIC   SELECT c.text, c.source_file
# MAGIC   FROM upsc_catalog.rag.contextual_chunks c
# MAGIC   WHERE c.doc_type = 'CurrentAffairs'
# MAGIC     AND c.source_file = concat('CA_', current_date(), '.md')
# MAGIC   LIMIT 3
# MAGIC ),
# MAGIC static_context AS (
# MAGIC   SELECT c.text, c.source_file
# MAGIC   FROM upsc_catalog.rag.contextual_chunks c, todays_stories s
# MAGIC   WHERE c.doc_type != 'CurrentAffairs'
# MAGIC     AND (lower(c.text) LIKE concat('%', lower(s.topic_cluster), '%'))
# MAGIC   LIMIT 3
# MAGIC ),
# MAGIC combined AS (
# MAGIC   SELECT concat_ws('\n---\n', collect_list(concat('[', source_file, ']: ', text))) AS knowledge,
# MAGIC          (SELECT title FROM todays_stories) AS story_title,
# MAGIC          (SELECT gs_papers FROM todays_stories) AS gs_papers
# MAGIC   FROM (SELECT * FROM ca_context UNION ALL SELECT * FROM static_context)
# MAGIC )
# MAGIC SELECT
# MAGIC   story_title,
# MAGIC   gs_papers,
# MAGIC   ai_query(
# MAGIC     'databricks-claude-sonnet-4',
# MAGIC     concat(
# MAGIC       'You are a strict UPSC examiner. Using ONLY the context below, answer a 15-mark GS Mains question.\n',
# MAGIC       'Cite specific Article numbers, Acts, committee names, and source files.\n',
# MAGIC       'Structure: Intro (2-3 lines) | Constitutional/Legal basis | Key features | Significance | Way forward\n\n',
# MAGIC       'CONTEXT:\n', knowledge, '\n\n',
# MAGIC       'Write a comprehensive UPSC Mains answer on: ', story_title,
# MAGIC       ' (15 marks, 250 words)'
# MAGIC     ),
# MAGIC     modelParameters => named_struct('max_tokens', 1024, 'temperature', 0.1)
# MAGIC   ) AS daily_answer
# MAGIC FROM combined

# COMMAND ----------

# DBTITLE 1,Mode 2: KARL Answer Evaluation
# MAGIC %sql
# MAGIC -- ═══════════════════════════════════════════════════════════════════════════
# MAGIC -- MODE 2: KARL Answer Evaluation — Auto question + sample answer + strict scoring
# MAGIC -- Scoring: Critical 60% | Important 30% | Optional 10% | Max ~65% = excellent
# MAGIC -- ═══════════════════════════════════════════════════════════════════════════
# MAGIC WITH todays_ca AS (
# MAGIC   SELECT text
# MAGIC   FROM upsc_catalog.rag.contextual_chunks
# MAGIC   WHERE doc_type = 'CurrentAffairs'
# MAGIC     AND source_file = concat('CA_', current_date(), '.md')
# MAGIC   LIMIT 5
# MAGIC ),
# MAGIC aggregated AS (
# MAGIC   SELECT concat_ws('\n---\n', collect_list(text)) AS knowledge
# MAGIC   FROM todays_ca
# MAGIC )
# MAGIC SELECT ai_query(
# MAGIC   'databricks-claude-sonnet-4',
# MAGIC   concat(
# MAGIC     'You are a STRICT UPSC Mains Examiner using the KARL evaluation pattern.\n\n',
# MAGIC     'CONTEXT (today''s Current Affairs):\n', knowledge, '\n\n',
# MAGIC     'TASKS:\n',
# MAGIC     '1. First, generate a 15-mark GS Mains question based on the most important story above\n',
# MAGIC     '2. Then, write a SAMPLE student answer (deliberately leave out 2-3 key points)\n',
# MAGIC     '3. Finally, EVALUATE that answer using this format:\n\n',
# MAGIC     'SCORE: X.X / 15 | STRUCTURE: [A/B/C/D]\n',
# MAGIC     'FOUND -- CRITICAL: [...] | IMPORTANT: [...] | OPTIONAL: [...]\n',
# MAGIC     'MISSING -- CRITICAL: [...] | IMPORTANT: [...] | OPTIONAL: [...]\n',
# MAGIC     'FEEDBACK: [2-3 strict sentences]\n',
# MAGIC     'MODEL ANSWER: [Perfect 250-word answer using ALL nuggets]\n\n',
# MAGIC     'SCORING: Critical=60%, Important=30%, Optional=10%. Max ~65% (9.5/15 = excellent). BE STRICT.'
# MAGIC   ),
# MAGIC   modelParameters => named_struct('max_tokens', 2000, 'temperature', 0.2)
# MAGIC ) AS daily_evaluation
# MAGIC FROM aggregated

# COMMAND ----------

# DBTITLE 1,Mode 3: Prelims MCQs
# MAGIC %sql
# MAGIC -- ═══════════════════════════════════════════════════════════════════════════
# MAGIC -- MODE 3: Prelims MCQs — From today's CA stories + NB6 trap data
# MAGIC -- Uses story_traps to plant realistic wrong options (the UPSC way)
# MAGIC -- ═══════════════════════════════════════════════════════════════════════════
# MAGIC WITH todays_stories_and_traps AS (
# MAGIC   SELECT
# MAGIC     s.title,
# MAGIC     s.gs_papers,
# MAGIC     s.topic_cluster,
# MAGIC     concat_ws(' | ', collect_list(
# MAGIC       concat('TRAP: ', t.wrong_belief, ' -> CORRECT: ', t.correct_belief, ' (', t.trap_type, ')')
# MAGIC     )) AS trap_context
# MAGIC   FROM upsc_catalog.rag.stories s
# MAGIC   LEFT JOIN upsc_catalog.rag.story_traps t
# MAGIC     ON t.story_slug = s.slug AND t.created_date = s.date
# MAGIC   WHERE s.date = cast(current_date() AS STRING)
# MAGIC   GROUP BY s.title, s.gs_papers, s.topic_cluster
# MAGIC ),
# MAGIC aggregated AS (
# MAGIC   SELECT concat_ws('\n', collect_list(
# MAGIC     concat('STORY: ', title, ' | Papers: ', gs_papers, ' | Traps: ', coalesce(trap_context, 'none'))
# MAGIC   )) AS stories_context,
# MAGIC   count(*) AS story_count
# MAGIC   FROM todays_stories_and_traps
# MAGIC )
# MAGIC SELECT
# MAGIC   story_count AS stories_used,
# MAGIC   ai_query(
# MAGIC     'databricks-claude-sonnet-4',
# MAGIC     concat(
# MAGIC       'You are a UPSC Prelims question setter. Generate MCQs from TODAY''s current affairs.\n\n',
# MAGIC       'TODAY''S CA STORIES + KNOWN TRAPS:\n', stories_context, '\n\n',
# MAGIC       'RULES:\n',
# MAGIC       '- Generate 5 MCQs (one per story where possible)\n',
# MAGIC       '- 4 options each (a, b, c, d). Exactly ONE correct answer.\n',
# MAGIC       '- USE the known traps above as wrong options where applicable\n',
# MAGIC       '- After each: Answer: [correct] | Trap: [explanation] | trap_type: [type]\n',
# MAGIC       '- Make questions HARD -- test precise facts, not general knowledge\n\n',
# MAGIC       'Generate 5 UPSC Prelims MCQs:'
# MAGIC     ),
# MAGIC     modelParameters => named_struct('max_tokens', 2000, 'temperature', 0.3)
# MAGIC   ) AS daily_mcqs
# MAGIC FROM aggregated

# COMMAND ----------

# DBTITLE 1,Mode 4: Ethics Case Study (GS4)
# MAGIC %sql
# MAGIC -- ═══════════════════════════════════════════════════════════════════════════
# MAGIC -- MODE 4: Ethics Case Study (GS4) — Today's CA reframed as ethical dilemma
# MAGIC -- Applies: Stakeholder mapping, Ethical thinkers, Dilemma resolution
# MAGIC -- ═══════════════════════════════════════════════════════════════════════════
# MAGIC WITH todays_stories AS (
# MAGIC   SELECT title, slug, gs_papers, topic_cluster, keywords
# MAGIC   FROM upsc_catalog.rag.stories
# MAGIC   WHERE date = cast(current_date() AS STRING)
# MAGIC   ORDER BY CASE priority WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2 WHEN 'MEDIUM' THEN 3 ELSE 4 END
# MAGIC   LIMIT 2
# MAGIC ),
# MAGIC ethics_pyqs AS (
# MAGIC   SELECT c.text
# MAGIC   FROM upsc_catalog.rag.contextual_chunks c
# MAGIC   WHERE c.subject = 'Ethics'
# MAGIC     AND c.doc_type = 'PYQ'
# MAGIC   ORDER BY RAND()
# MAGIC   LIMIT 2
# MAGIC ),
# MAGIC story_info AS (
# MAGIC   SELECT concat_ws('\n', collect_list(
# MAGIC     concat('STORY: ', title, ' | GS Papers: ', gs_papers, ' | Topic: ', topic_cluster, ' | Keywords: ', coalesce(keywords, ''))
# MAGIC   )) AS stories_text
# MAGIC   FROM todays_stories
# MAGIC ),
# MAGIC ethics_ref AS (
# MAGIC   SELECT concat_ws('\n---\n', collect_list(text)) AS ethics_knowledge
# MAGIC   FROM ethics_pyqs
# MAGIC )
# MAGIC SELECT ai_query(
# MAGIC   'databricks-claude-sonnet-4',
# MAGIC   concat(
# MAGIC     'You are a UPSC GS Paper IV (Ethics, Integrity & Aptitude) examiner and coach.\n\n',
# MAGIC     'TODAY''S CURRENT AFFAIRS:\n', s.stories_text, '\n\n',
# MAGIC     'REFERENCE ETHICS PYQ PATTERNS:\n', e.ethics_knowledge, '\n\n',
# MAGIC     'TASK: Convert the most ethically rich story above into a GS4 Case Study + Model Answer.\n\n',
# MAGIC     'FORMAT YOUR RESPONSE AS:\n\n',
# MAGIC     '== CASE STUDY (150 words) ==\n',
# MAGIC     'Write a realistic scenario based on the CA story. Name the officer/decision-maker.\n',
# MAGIC     'End with: "What are the ethical issues involved? How would you resolve this?" (20 marks)\n\n',
# MAGIC     '== ETHICAL ANALYSIS ==\n',
# MAGIC     '1. STAKEHOLDERS & THEIR CONCERNS (table: stakeholder | concern | ethical value at stake)\n',
# MAGIC     '2. ETHICAL DILEMMAS IDENTIFIED (list each with competing values)\n',
# MAGIC     '3. THINKERS APPLICABLE (reference 3-4: e.g., Kant duty-based, Gandhi trusteeship, Aristotle virtue, Rawls justice, Kautilya pragmatism)\n',
# MAGIC     '4. CONSTITUTIONAL/LEGAL ANCHORS (Articles, Acts, Supreme Court judgments)\n\n',
# MAGIC     '== MODEL ANSWER (250 words) ==\n',
# MAGIC     'Structure: Identify issues -> Apply ethical framework -> Stakeholder balance -> Action plan -> Conclusion\n',
# MAGIC     'Use keywords: probity, empathy, objectivity, non-partisanship, tolerance, compassion\n',
# MAGIC     'Cite specific thinkers and Articles.\n\n',
# MAGIC     '== QUICK REVISION ==\n',
# MAGIC     'List 5 ethics keywords + definitions this case tests (for last-minute revision)'
# MAGIC   ),
# MAGIC   modelParameters => named_struct('max_tokens', 2500, 'temperature', 0.25)
# MAGIC ) AS ethics_case_study
# MAGIC FROM story_info s, ethics_ref e

# COMMAND ----------

# DBTITLE 1,Mode 5: Mains Model Answers + Cross-Subject Interlinking
# MAGIC %sql
# MAGIC -- ═══════════════════════════════════════════════════════════════════════════
# MAGIC -- MODE 5: Mains Model Answers with Cross-Subject Interlinking
# MAGIC -- Pulls NB6 deep_analysis + geography + traps for rich structured answers
# MAGIC -- ═══════════════════════════════════════════════════════════════════════════
# MAGIC WITH todays_deep AS (
# MAGIC   SELECT
# MAGIC     s.title,
# MAGIC     s.priority,
# MAGIC     s.gs_papers,
# MAGIC     s.topic_cluster,
# MAGIC     s.keywords,
# MAGIC     d.pyq_patterns,
# MAGIC     d.mains_skeleton,
# MAGIC     d.static_links
# MAGIC   FROM upsc_catalog.rag.stories s
# MAGIC   LEFT JOIN upsc_catalog.rag.deep_analysis d
# MAGIC     ON d.story_id = s.story_id AND d.date = s.date
# MAGIC   WHERE s.date = cast(current_date() AS STRING)
# MAGIC ),
# MAGIC geo_context AS (
# MAGIC   SELECT
# MAGIC     g.story_id,
# MAGIC     concat_ws('; ', collect_list(
# MAGIC       concat(g.location_name, ': ', g.strategic_importance)
# MAGIC     )) AS geo_summary
# MAGIC   FROM upsc_catalog.rag.geography_context g
# MAGIC   WHERE g.date = cast(current_date() AS STRING)
# MAGIC   GROUP BY g.story_id
# MAGIC ),
# MAGIC trap_summary AS (
# MAGIC   SELECT
# MAGIC     t.story_slug,
# MAGIC     concat_ws('; ', collect_list(
# MAGIC       concat(t.trap_type, ': ', t.wrong_belief, ' -> ', t.correct_belief)
# MAGIC     )) AS traps
# MAGIC   FROM upsc_catalog.rag.story_traps t
# MAGIC   WHERE t.created_date = cast(current_date() AS STRING)
# MAGIC   GROUP BY t.story_slug
# MAGIC ),
# MAGIC enriched AS (
# MAGIC   SELECT
# MAGIC     d.title,
# MAGIC     d.priority,
# MAGIC     d.gs_papers,
# MAGIC     d.topic_cluster,
# MAGIC     d.keywords,
# MAGIC     coalesce(d.pyq_patterns, '[]') AS pyq_patterns,
# MAGIC     coalesce(d.mains_skeleton, '{}') AS mains_skeleton,
# MAGIC     coalesce(d.static_links, '[]') AS static_links,
# MAGIC     coalesce(g.geo_summary, 'N/A') AS geo_summary,
# MAGIC     coalesce(ts.traps, 'none') AS common_traps
# MAGIC   FROM todays_deep d
# MAGIC   LEFT JOIN upsc_catalog.rag.stories s2
# MAGIC     ON d.title = s2.title AND s2.date = cast(current_date() AS STRING)
# MAGIC   LEFT JOIN geo_context g ON s2.story_id = g.story_id
# MAGIC   LEFT JOIN trap_summary ts ON s2.slug = ts.story_slug
# MAGIC ),
# MAGIC aggregated AS (
# MAGIC   SELECT concat_ws('\n\n', collect_list(
# MAGIC     concat(
# MAGIC       '=== STORY: ', title, ' [', priority, '] ===\n',
# MAGIC       'GS Papers: ', gs_papers, '\n',
# MAGIC       'Topic: ', topic_cluster, ' | Keywords: ', coalesce(keywords, ''), '\n',
# MAGIC       'PYQ Patterns: ', pyq_patterns, '\n',
# MAGIC       'Mains Skeleton: ', mains_skeleton, '\n',
# MAGIC       'Textbook References: ', static_links, '\n',
# MAGIC       'Geography Context: ', geo_summary, '\n',
# MAGIC       'Common Traps to Avoid: ', common_traps
# MAGIC     )
# MAGIC   )) AS all_stories,
# MAGIC   count(*) AS story_count
# MAGIC   FROM enriched
# MAGIC )
# MAGIC SELECT
# MAGIC   story_count,
# MAGIC   ai_query(
# MAGIC     'databricks-claude-sonnet-4',
# MAGIC     concat(
# MAGIC       'You are a senior UPSC Mains answer-writing coach. Generate STRUCTURED MODEL ANSWERS for each story below.\n\n',
# MAGIC       'TODAY''S ENRICHED CA STORIES (with NB6 deep analysis):\n', all_stories, '\n\n',
# MAGIC       'FOR EACH STORY, generate:\n\n',
# MAGIC       '========================================\n',
# MAGIC       'STORY: [title]\n',
# MAGIC       '========================================\n\n',
# MAGIC       '>> MAINS QUESTION (15 marks, state which GS Paper)\n',
# MAGIC       '[Frame a proper UPSC-style question with directive word: Discuss/Examine/Critically Analyse/Comment]\n\n',
# MAGIC       '>> CROSS-SUBJECT MAP\n',
# MAGIC       '- GS1 connect: [history/geography/society angle]\n',
# MAGIC       '- GS2 connect: [governance/polity/IR angle]\n',
# MAGIC       '- GS3 connect: [economy/science/environment angle]\n',
# MAGIC       '- GS4 connect: [ethics/integrity angle]\n',
# MAGIC       '- Essay connect: [possible essay theme]\n\n',
# MAGIC       '>> MODEL ANSWER (250 words, structured)\n',
# MAGIC       'INTRO: [2-3 lines with a quote/data point/recent context]\n',
# MAGIC       'BODY:\n',
# MAGIC       '  - Constitutional/Legal Framework (cite specific Articles, Acts)\n',
# MAGIC       '  - Key Arguments (use subheadings, 3-4 points)\n',
# MAGIC       '  - Data/Examples (committees, international comparisons)\n',
# MAGIC       '  - Counter-view (if applicable)\n',
# MAGIC       'CONCLUSION: [Way forward with actionable recommendations]\n\n',
# MAGIC       '>> TEXTBOOK ANCHORS (from static_links above)\n',
# MAGIC       '[Which chapters in Laxmikanth/Spectrum/Ramesh Singh/etc. to revise]\n\n',
# MAGIC       '>> PYQ CONNECTIONS\n',
# MAGIC       '[List 2-3 past UPSC questions that tested similar concepts]\n\n',
# MAGIC       '>> TRAPS TO AVOID\n',
# MAGIC       '[Common mistakes from the trap data above]\n\n',
# MAGIC       'Generate for ALL stories. Be thorough and exam-ready.'
# MAGIC     ),
# MAGIC     modelParameters => named_struct('max_tokens', 4000, 'temperature', 0.15)
# MAGIC   ) AS model_answers_with_interlinking
# MAGIC FROM aggregated

# COMMAND ----------

# DBTITLE 1,Mode 6: Telugu Optional Model Answers (Paper 1 & 2)
# MAGIC %sql
# MAGIC -- ═══════════════════════════════════════════════════════════════════════════
# MAGIC -- MODE 6: Telugu Optional Model Answers (Paper 1 & 2)
# MAGIC -- Pulls PYQs from 8,518 Telugu chunks + textbook context for structured answers
# MAGIC -- Rubric: Content 40% | Language 30% | Presentation 20% | Originality 10%
# MAGIC -- ═══════════════════════════════════════════════════════════════════════════
# MAGIC WITH telugu_pyqs AS (
# MAGIC   SELECT c.text, c.source_file, c.page_number
# MAGIC   FROM upsc_catalog.rag.contextual_chunks c
# MAGIC   WHERE c.subject = 'Telugu Optional'
# MAGIC     AND c.doc_type = 'PYQ'
# MAGIC     AND (
# MAGIC       c.source_file LIKE '%SIKHARAM%'
# MAGIC       OR c.source_file LIKE '%UPDATED 2025%'
# MAGIC       OR c.source_file LIKE '%PYQ%'
# MAGIC       OR c.source_file LIKE '%VAKYANALU%'
# MAGIC       OR c.source_file LIKE '%Syllabus%'
# MAGIC     )
# MAGIC   ORDER BY RAND()
# MAGIC   LIMIT 8
# MAGIC ),
# MAGIC telugu_textbooks AS (
# MAGIC   SELECT c.text, c.source_file
# MAGIC   FROM upsc_catalog.rag.contextual_chunks c
# MAGIC   WHERE c.subject = 'Telugu Optional'
# MAGIC     AND c.doc_type IN ('Textbook', 'Notes')
# MAGIC     AND (
# MAGIC       c.source_file LIKE '%sahityam%'
# MAGIC       OR c.source_file LIKE '%COMPLETE_SYSTEM%'
# MAGIC       OR c.source_file LIKE '%History-of-Telugu%'
# MAGIC       OR c.source_file LIKE '%nannaya%'
# MAGIC       OR c.source_file LIKE '%LAKSHMI KANTH%'
# MAGIC       OR c.source_file LIKE '%LITERATUREE PAPER 1%'
# MAGIC       OR c.source_file LIKE '%lit paper1+paper2%'
# MAGIC       OR c.source_file LIKE '%Mahabharatam%'
# MAGIC       OR c.source_file LIKE '%మహాభారత%'
# MAGIC       OR c.source_file LIKE '%ద్రావిడ%'
# MAGIC       OR c.source_file LIKE '%Vachana gabbilam%'
# MAGIC       OR c.source_file LIKE '%shakuntala%'
# MAGIC     )
# MAGIC   ORDER BY RAND()
# MAGIC   LIMIT 8
# MAGIC ),
# MAGIC pyq_context AS (
# MAGIC   SELECT concat_ws('\n---\n', collect_list(
# MAGIC     concat('[PYQ: ', source_file, ' p.', page_number, ']:\n', text)
# MAGIC   )) AS pyq_knowledge
# MAGIC   FROM telugu_pyqs
# MAGIC ),
# MAGIC textbook_context AS (
# MAGIC   SELECT concat_ws('\n---\n', collect_list(
# MAGIC     concat('[', source_file, ']:\n', text)
# MAGIC   )) AS textbook_knowledge
# MAGIC   FROM telugu_textbooks
# MAGIC )
# MAGIC SELECT
# MAGIC   (SELECT COUNT(*) FROM upsc_catalog.rag.contextual_chunks WHERE subject = 'Telugu Optional') AS total_telugu_chunks,
# MAGIC   ai_query(
# MAGIC     'databricks-claude-sonnet-4',
# MAGIC     concat(
# MAGIC       'You are a senior UPSC Telugu Literature Optional examiner and tutor.\n',
# MAGIC       'You are training a student for UPSC Mains 2027 Telugu Optional (Paper 1 & 2, 250 marks each).\n\n',
# MAGIC       'TELUGU LITERATURE PYQ CONTEXT (recent years):\n', p.pyq_knowledge, '\n\n',
# MAGIC       'TEXTBOOK/REFERENCE CONTEXT:\n', t.textbook_knowledge, '\n\n',
# MAGIC       'TASK: Generate 5 STRUCTURED MODEL ANSWERS for Telugu Optional questions from the PYQ context above.\n',
# MAGIC       'Pick the 5 most important/representative questions. Mix Paper 1 and Paper 2.\n\n',
# MAGIC       'FOR EACH QUESTION, generate:\n\n',
# MAGIC       '=============================================\n',
# MAGIC       'Q[N]: [Full question text] (Year: [year], Paper: [1/2], Marks: [marks])\n',
# MAGIC       '=============================================\n\n',
# MAGIC       '>> APPROACH (What the examiner tests)\n',
# MAGIC       '- Core concept being tested\n',
# MAGIC       '- Key తెలుగు సాహిత్య concepts (Telugu literary concepts) to demonstrate\n',
# MAGIC       '- Common mistakes students make\n',
# MAGIC       '- What differentiates a 40+ answer from a 25-mark answer\n\n',
# MAGIC       '>> MODEL ANSWER STRUCTURE\n',
# MAGIC       'INTRO (2-3 lines): [Opening with a relevant Telugu quote/shloka or literary context]\n',
# MAGIC       'BODY (4 subpoints with subheadings):\n',
# MAGIC       '  1. [Historical/Literary Context] — place the work/author in the సాహిత్య పరిణామం (literary evolution)\n',
# MAGIC       '  2. [Core Analysis] — detailed examination of the theme/style/contribution\n',
# MAGIC       '  3. [Comparative Dimension] — compare with other కవులు/రచయితలు (poets/authors)\n',
# MAGIC       '  4. [Contemporary Relevance] — connect to modern Telugu literature/society\n',
# MAGIC       'CONCLUSION (2-3 lines): [Scholarly summary with literary significance]\n\n',
# MAGIC       '>> KEY TELUGU LITERARY TERMS (with meanings)\n',
# MAGIC       'List 5-7 తెలుగు సాహిత్య పదాలు (Telugu literary terms) relevant to this answer:\n',
# MAGIC       '- Term (తెలుగు): English meaning — how to use in the answer\n\n',
# MAGIC       '>> TEXTS TO CITE\n',
# MAGIC       '[List 3-5 specific గ్రంథాలు/కావ్యాలు (texts/poems) with author names to reference]\n\n',
# MAGIC       '>> SCORING TIPS\n',
# MAGIC       '- Content (40%): [specific content points that score marks]\n',
# MAGIC       '- Language (30%): [తెలుగు భాషా నైపుణ్యం (Telugu language proficiency) tips]\n',
# MAGIC       '- Presentation (20%): [structure, diagram suggestions if applicable]\n',
# MAGIC       '- Originality (10%): [how to add unique scholarly perspective]\n\n',
# MAGIC       'IMPORTANT: Use Telugu script (తెలుగు లిపి) for literary terms, quotes, and key concepts where appropriate.\n',
# MAGIC       'Generate 5 comprehensive model answers. Be thorough — this is 500 marks at stake.'
# MAGIC     ),
# MAGIC     modelParameters => named_struct('max_tokens', 8192, 'temperature', 0.2)
# MAGIC   ) AS telugu_model_answers
# MAGIC FROM pyq_context p, textbook_context t

# COMMAND ----------

# DBTITLE 1,Mode 7: AI Tutor Brief (5-min Morning Session)
# ── MODE 7: AI Tutor Brief ─────────────────────────────────────────────────
# Consolidates today's CA into a 5-min tutor session.
# ONE Claude call → practice answer + model answer + tutor brief.
# Sets Python variables (mode1_result, mode5_result, mode7_result)
# that Mode 8 (Phone Summary) consumes downstream.
# ─────────────────────────────────────────────────────────────────

import re as _re
import json as _json
from datetime import date as _date

today_date = _date.today().isoformat()
print(f"\u23f3 Mode 7: Building tutor brief for {today_date}...")

# ── 1. Fetch today's stories + traps + deep analysis from Delta ──
stories_rows = spark.sql(f"""
    SELECT s.title, s.priority, s.gs_papers, s.topic_cluster, s.keywords,
           d.pyq_patterns, d.mains_skeleton
    FROM upsc_catalog.rag.stories s
    LEFT JOIN upsc_catalog.rag.deep_analysis d
        ON d.story_id = s.story_id AND d.date = s.date
    WHERE s.date = '{today_date}'
    ORDER BY CASE s.priority
        WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2
        WHEN 'MEDIUM' THEN 3 ELSE 4 END
""").collect()

traps_rows = spark.sql(f"""
    SELECT trap_type, wrong_belief, correct_belief, severity
    FROM upsc_catalog.rag.story_traps
    WHERE created_date = '{today_date}'
    ORDER BY CASE severity WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END
""").collect()

print(f"   Stories: {len(stories_rows)} | Traps: {len(traps_rows)}")

# Parse gs_papers from JSON string to clean format (avoids quote issues in SQL)
def _parse_gs(raw):
    try:
        return ", ".join(_json.loads(raw)) if raw else "N/A"
    except Exception:
        return str(raw).replace('"', '').replace("[", "").replace("]", "")

story_context = "\n".join([
    f"[{r.priority}] {r.title} | Papers: {_parse_gs(r.gs_papers)} | Cluster: {r.topic_cluster}"
    for r in stories_rows
])
trap_context = "\n".join([
    f"TRAP ({r.severity} / {r.trap_type}): {r.wrong_belief} -> CORRECT: {r.correct_belief}"
    for r in traps_rows[:10]
])

# ── 2. ONE Claude call → three outputs ──
prompt_text = f"""You are an expert UPSC tutor preparing a 5-minute morning briefing.

TODAY'S STORIES ({today_date}):
{story_context}

KEY TRAPS TO AVOID:
{trap_context}

Generate THREE clearly labeled sections:

=== PRACTICE ANSWER ===
Write a concise 150-word practice answer for the most important story
(as if a student wrote it for a 15-mark Mains question). Include Article
references and committee names where relevant.

=== MODEL ANSWER ===
Write a 250-word model answer for the same story.
Structure: Intro -> 4 body points -> Forward-looking conclusion.
Include static anchors (constitutional articles, landmark cases, committees).

=== TUTOR BRIEF ===
Write a 5-minute tutor briefing covering:
- Today's 3 most important takeaways (1 line each)
- The #1 trap students will fall for today
- One memory hook per story
- What to revise from static syllabus tonight
- Motivational closer (1 sentence)
Keep it conversational, like talking to the student over chai."""

try:
    # Escape single quotes for safe SQL embedding
    safe_prompt = prompt_text.replace("'", "''")

    response = spark.sql(f"""
        SELECT ai_query(
            'databricks-claude-sonnet-4',
            '{safe_prompt}',
            modelParameters => named_struct('max_tokens', 2000, 'temperature', 0.3)
        ) AS response
    """).collect()[0]['response']

    # ── 3. Parse the three sections ──
    practice_m = _re.search(r'=== PRACTICE ANSWER ===(.*?)(?==== MODEL ANSWER ===|$)', response, _re.DOTALL)
    model_m    = _re.search(r'=== MODEL ANSWER ===(.*?)(?==== TUTOR BRIEF ===|$)',     response, _re.DOTALL)
    tutor_m    = _re.search(r'=== TUTOR BRIEF ===(.*?)$',                              response, _re.DOTALL)

    mode1_result = {'answer':       practice_m.group(1).strip() if practice_m else response[:500]}
    mode5_result = {'model_answer': model_m.group(1).strip()    if model_m    else response[500:1200]}
    mode7_result = tutor_m.group(1).strip()                     if tutor_m    else response[1200:]

    print(f"\u2705 Mode 7 complete!")
    print(f"   Practice answer : {len(mode1_result['answer']):,} chars")
    print(f"   Model answer    : {len(mode5_result['model_answer']):,} chars")
    print(f"   Tutor brief     : {len(mode7_result):,} chars")
    print(f"\n{'='*60}")
    print(f"TUTOR BRIEF PREVIEW:")
    print(f"{'='*60}")
    print(mode7_result[:800])
    if len(mode7_result) > 800:
        print(f"\n... [{len(mode7_result) - 800} more chars]")

except Exception as e:
    print(f"\u274c Mode 7 error: {e}")
    import traceback
    traceback.print_exc()
    mode1_result = None
    mode5_result = None
    mode7_result = None

# COMMAND ----------

# DBTITLE 1,Mode 8: Claude Sonnet 4 → Phone Summary
# ── MODE 8: Claude Sonnet 4 → Phone Summary ────────────────────────────────────────

def mode8_phone_summary(mode1_answer: str, mode5_model_answer: str, 
                        mode7_tutor_brief: str, ca_date: str):
    """
    Mode 8: Generate a 2-3 min phone-friendly summary.
    All 6 outputs → Claude → scannable emoji + bullets summary.
    Saves to Volume → syncs to Obsidian → appears in your vault.
    """
    
    combined_text = f"""
STUDENT PRACTICE ANSWER (Mode 1):
{mode1_answer[:800]}

MODEL ANSWER (Mode 5):
{mode5_model_answer[:800]}

TUTOR BRIEF (Mode 7):
{mode7_tutor_brief[:1000]}
"""
    
    prompt = f"""You are a UPSC phone tutor. Condense this into a 2-3 minute read.

RULES:
- Use emoji headers for sections (📌 🎯 ❌ 🧠 ✍️)
- Short bullet points (max 1 line each)
- One memory hook per section
- 300 words MAX
- Made for reading on phone while commuting

CONTENT TO SUMMARIZE:
{combined_text}

OUTPUT:
📌 The One Thing
[1 sentence — if nothing else, remember this]

⚡ What's Happening
- [Point 1]
- [Point 2]
- [Point 3]

🎯 Why UPSC Cares
[2 lines max]

❌ Students Always Miss
[1 mistake]

🧠 Memory Hook
"[Sticky one-liner for exam day]"

✍️ In Your Answer, Say
[2-3 key phrases to include]"""
    
    print(f"⏳ Mode 8: Generating phone summary for {ca_date}...")
    
    try:
        summary = spark.sql(f"""
            SELECT ai_query('databricks-claude-sonnet-4', 
                '{prompt.replace(chr(39), chr(34))}') AS summary
        """).collect()[0]['summary']
        
        # Save to Obsidian vault via Volume
        output_path = f"/Volumes/upsc_catalog/rag/obsidian_ca/UPSC_2026/01_Current_Affairs/2026/03-March/CA_{ca_date}_QUICK.md"
        
        header = f"""---
date: {ca_date}
type: quick-summary
duration: 2-3 minutes
---

# ⚡ Quick Summary — {ca_date}

> Read this while eating breakfast. Same value as an 18-min audio, way faster.

"""
        
        dbutils.fs.put(output_path, header + summary, overwrite=True)
        print(f"✅ Mode 8 complete: Summary saved to Volume")
        print(f"   Path: {output_path}")
        print(f"   Will appear in Obsidian at 8:15 AM sync")
        
        return {
            'status': 'success',
            'ca_date': ca_date,
            'summary_path': output_path,
            'summary_preview': summary[:500]
        }
        
    except Exception as e:
        print(f"❌ Mode 8 error: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

# COMMAND ----------

# DBTITLE 1,Mode 8 Execution
# ── Mode 8 execution ─────────────────────────────────────────────

if mode7_result:
    mode8_result = mode8_phone_summary(
        mode1_answer=mode1_result.get('answer', ''),
        mode5_model_answer=mode5_result.get('model_answer', ''),
        mode7_tutor_brief=mode7_result,
        ca_date=today_date
    )
    print(f"\n{'='*70}")
    print(f"MODE 8 RESULT: {mode8_result}")
    print(f"{'='*70}")
else:
    print("⚠️ Mode 7 did not complete, skipping Mode 8")

# COMMAND ----------

# =====================================
# POPULATE DAILY_PRACTICE_QUEUE TABLE
# =====================================

from datetime import datetime
import uuid
import json

ca_date = str(datetime.now().date())
queue_id = f"dpq_{ca_date}_{uuid.uuid4().hex[:8]}"

# Collect today's outputs from all 8 modes
queue_data = {
    'queue_id': queue_id,
    'ca_date': ca_date,
    'story_title': stories_rows[0].title if stories_rows else 'TBD',
    'priority': stories_rows[0].priority if stories_rows else 'MEDIUM',
    'gs_papers': json.loads(stories_rows[0].gs_papers) if stories_rows else [],
    'mode1_practice_answer': mode1_result.get('answer', '')[:1500] if mode1_result else '',
    'mode2_karl_eval': 'See Mode 2 SQL output above',
    'mode3_mcqs': 'See Mode 3 SQL output above',
    'mode4_ethics_case': 'See Mode 4 SQL output above',
    'mode5_model_answer': mode5_result.get('model_answer', '')[:2000] if mode5_result else '',
    'mode6_telugu_answer': 'See Mode 6 SQL output above',
    'mode7_tutor_brief': mode7_result[:1500] if mode7_result else '',
    'mode8_phone_summary': mode8_result.get('summary_preview', '') if mode8_result else '',
    'audio_script': '',  # Generated next
    'memory_hook': '',   # Extracted next
    'telegram_msg_id': '',
    'obsidian_path': f"/Volumes/upsc_catalog/rag/obsidian_ca/UPSC_2026/01_Current_Affairs/2026/{ca_date}.md"
}

# Insert into table
queue_df = spark.createDataFrame([queue_data])
queue_df.write.mode('append').saveAsTable('upsc_catalog.rag.daily_practice_queue')

print(f"✅ Queue entry created: {queue_id}")
print(f"   CA Date: {ca_date}")
print(f"   Story: {queue_data['story_title']}")
print(f"   Hermes can now fetch this data.")

# COMMAND ----------

# DBTITLE 1,Export Mode Outputs to Daily_Practice for NB8
# ═══════════════════════════════════════════════════════════════════════════
# EXPORT: Save all mode outputs to markdown files for NB8 Audio Generator
# NB8 reads these from /Volumes/.../Daily_Practice/{date}/
# ═══════════════════════════════════════════════════════════════════════════

from datetime import date as _export_date

_TODAY = _export_date.today().isoformat()
_OUTPUT_DIR = f"/Volumes/upsc_catalog/rag/obsidian_ca/Daily_Practice/{_TODAY}"
_MODEL_USED = "databricks-claude-sonnet-4"

print(f"📤 Exporting mode outputs to Daily_Practice/{_TODAY}/")
print(f"{'='*60}")

# Create output directory
try:
    dbutils.fs.mkdirs(_OUTPUT_DIR)
except Exception as e:
    print(f"   ⚠️  Dir creation note: {e}")

def _make_header(mode_num, mode_name):
    """Generate YAML frontmatter for each mode file."""
    return f"""---
date: {_TODAY}
mode: {mode_num}
title: {mode_name}
model: {_MODEL_USED}
pipeline: NB7_Daily_CA_Practice_Generator
---

# Mode {mode_num}: {mode_name}
**Date:** {_TODAY} | **Model:** {_MODEL_USED}

---

"""

def _safe_export(filepath, content):
    """Write file and return (success, byte_size)."""
    try:
        dbutils.fs.put(filepath, content, overwrite=True)
        return True, len(content.encode('utf-8'))
    except Exception as e:
        print(f"   ❌  Write failed: {e}")
        return False, 0

# Track results
_export_results = []

# ── Mode 1: Knowledge Q&A (from mode7 cell's mode1_result) ──────────────
if mode1_result and mode1_result.get('answer'):
    content = _make_header(1, "Knowledge Q&A") + mode1_result['answer']
    ok, sz = _safe_export(f"{_OUTPUT_DIR}/01_Knowledge_QA.md", content)
    _export_results.append(("Mode 1: Knowledge Q&A", ok, sz))
else:
    _export_results.append(("Mode 1: Knowledge Q&A", False, 0))

# ── Mode 2: KARL Evaluation (SQL-only, placeholder) ───────────────────
content = _make_header(2, "KARL Evaluation") + \
    "*KARL evaluation output is generated as SQL display in NB7 Mode 2.*\n\n" + \
    "Open the NB7 notebook to view the full KARL scoring output.\n"
if queue_data.get('mode2_karl_eval', '').startswith('See Mode'):
    content += "\n> Content available in NB7 cell output.\n"
ok, sz = _safe_export(f"{_OUTPUT_DIR}/02_KARL_Evaluation.md", content)
_export_results.append(("Mode 2: KARL Evaluation", ok, sz))

# ── Mode 3: Prelims MCQs (SQL-only, placeholder) ─────────────────────
content = _make_header(3, "Prelims MCQs") + \
    "*Prelims MCQ output is generated as SQL display in NB7 Mode 3.*\n\n" + \
    "Open the NB7 notebook to view the full MCQ set with trap-based options.\n"
ok, sz = _safe_export(f"{_OUTPUT_DIR}/03_Prelims_MCQs.md", content)
_export_results.append(("Mode 3: Prelims MCQs", ok, sz))

# ── Mode 4: Ethics Case Study (SQL-only, placeholder) ─────────────────
content = _make_header(4, "Ethics Case Study") + \
    "*Ethics case study output is generated as SQL display in NB7 Mode 4.*\n\n" + \
    "Open the NB7 notebook to view the full GS4 case study and model answer.\n"
ok, sz = _safe_export(f"{_OUTPUT_DIR}/04_Ethics_Case_Study.md", content)
_export_results.append(("Mode 4: Ethics Case Study", ok, sz))

# ── Mode 5: Mains Model Answers (from mode7 cell's mode5_result) ─────
if mode5_result and mode5_result.get('model_answer'):
    content = _make_header(5, "Mains Model Answers") + mode5_result['model_answer']
    ok, sz = _safe_export(f"{_OUTPUT_DIR}/05_Mains_Model_Answers.md", content)
    _export_results.append(("Mode 5: Mains Model Answers", ok, sz))
else:
    _export_results.append(("Mode 5: Mains Model Answers", False, 0))

# ── Mode 6: Telugu Optional (SQL-only, placeholder) ───────────────────
content = _make_header(6, "Telugu Optional") + \
    "*Telugu Optional model answers are generated as SQL display in NB7 Mode 6.*\n\n" + \
    "Open the NB7 notebook to view the full Telugu literature model answers.\n"
ok, sz = _safe_export(f"{_OUTPUT_DIR}/06_Telugu_Optional.md", content)
_export_results.append(("Mode 6: Telugu Optional", ok, sz))

# ── Mode 7: AI Tutor Brief (from mode7_result) ──────────────────────
if mode7_result:
    content = _make_header(7, "AI Tutor Brief") + mode7_result
    ok, sz = _safe_export(f"{_OUTPUT_DIR}/07_AI_Tutor_Brief.md", content)
    _export_results.append(("Mode 7: AI Tutor Brief", ok, sz))
else:
    _export_results.append(("Mode 7: AI Tutor Brief", False, 0))

# ── Mode 8: Phone Summary (from mode8_result) ───────────────────────
if mode8_result and mode8_result.get('summary_preview'):
    content = _make_header(8, "Phone Summary") + mode8_result['summary_preview']
    ok, sz = _safe_export(f"{_OUTPUT_DIR}/08_Phone_Summary.md", content)
    _export_results.append(("Mode 8: Phone Summary", ok, sz))
else:
    _export_results.append(("Mode 8: Phone Summary", False, 0))

# ── README.md index file ───────────────────────────────────────────────
story_count = len(stories_rows) if stories_rows else 0
links = "\n".join([
    f"- [[{fname}|Mode {num}: {fname.replace('.md','').replace('_',' ')}]]"
    for num, fname in {
        1: '01_Knowledge_QA.md', 2: '02_KARL_Evaluation.md',
        3: '03_Prelims_MCQs.md', 4: '04_Ethics_Case_Study.md',
        5: '05_Mains_Model_Answers.md', 6: '06_Telugu_Optional.md',
        7: '07_AI_Tutor_Brief.md', 8: '08_Phone_Summary.md'
    }.items()
])

readme = f"""---
date: {_TODAY}
type: practice-index
stories: {story_count}
---

# 📚 Daily Practice Index — {_TODAY}

## Practice Modes

{links}

## Quick Stats

| Metric | Value |
|--------|-------|
| Stories | {story_count} |
| Traps | {len(traps_rows) if traps_rows else 0} |
| Model | {_MODEL_USED} |
| Pipeline | NB6 → NB7 → NB8 |

## Audio & Insights (NB8)

- [[combined_for_podcast.md|Combined Podcast Source]]
- [[podcast_transcript.md|Podcast Transcript]]
- [[key_insights.md|Key Insights (5-min revision)]]
- [[Daily_Note.md|Daily Note (full index)]]

---
> Generated by NB7 export cell at {_export_date.today().isoformat()}
"""
ok, sz = _safe_export(f"{_OUTPUT_DIR}/README.md", readme)
_export_results.append(("README.md", ok, sz))

# ── Print summary ─────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"EXPORT SUMMARY")
print(f"{'='*60}")
total_ok = 0
total_bytes = 0
for name, ok, sz in _export_results:
    status = "✅" if ok else "⬜"
    sz_str = f"{sz:,}B" if sz > 0 else "--"
    print(f"   {status} {name:<30} {sz_str:>10}")
    if ok:
        total_ok += 1
        total_bytes += sz

print(f"{'='*60}")
print(f"   Exported: {total_ok}/{len(_export_results)} files | {total_bytes:,} bytes total")
print(f"   Dir: {_OUTPUT_DIR}")
print(f"   NB8 can now read these files for podcast generation.")
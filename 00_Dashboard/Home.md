---
tags: [dashboard, moc]
---

# UPSC 2026 — Command Center

> *Last updated: 2026-03-21 | Knowledge Base: 65,833 chunks | VS Index: synced*

## Quick Links
- [[01_Current_Affairs/CA_Master_Index|Today's CA]]
- [[04_Traps/Trap_Index|Trap Database]]
- [[05_Revision/Due_Today|Revision Due]]
- [[03_PYQs/My_Performance/Accuracy_Tracker|PYQ Stats]]
- [[06_Answer_Practice/KARL_Scores|KARL Scores]]

## Daily Pipeline (Automated)
| Time | What | Where |
|---|---|---|
| 7:00 AM | NB6 CA Orchestrator fetches top stories via Perplexity | Databricks → Delta tables |
| 7:00 AM | Stories, traps, deep analysis, geography context saved | `stories`, `story_traps`, `deep_analysis` |
| 7:05 AM | CA note auto-generated for Obsidian | `01_Current_Affairs/2026/` |
| 8:00 AM | NB7 Practice Generator runs 5 AI modes | Databricks → `ai_query()` |
| 8:15 AM | Obsidian vault syncs to Mac | `sync_from_databricks.py` |

## 5 Practice Modes (NB7 — Daily CA Practice Generator)
| # | Mode | What You Get |
|---|------|-------------|
| 1 | **Knowledge Q&A** | 15-mark Mains answer with Article citations from 59K chunks |
| 2 | **KARL Evaluation** | Auto question → sample answer → strict scoring → model answer |
| 3 | **Prelims MCQs** | 5 MCQs with trap-based wrong options from NB6 `story_traps` |
| 4 | **Ethics (GS4)** | Case study → stakeholder map → thinkers → model answer |
| 5 | **Model Answers + Interlinking** | Cross-subject map (GS1-4 + Essay) → textbook anchors → PYQ links |

## Study Routine (4 hours)
| Time | Activity | Tool |
|---|---|---|
| 7:00 AM | Vault syncs — read today's CA note | Obsidian (auto-generated) |
| 7:30 AM | Review traps from CA note | `04_Traps/` |
| 8:00 AM | Practice MCQs from Mode 3 | NB7 in Databricks |
| 8:30 AM | Study 1 topic — create note | Obsidian + Claude |
| 9:00 AM | PYQ quiz (25 questions) | Claude `/pyq quiz` |
| 9:30 AM | Answer writing (1 question) | NB4 Examiner Agent |
| 10:00 AM | Review model answers from Mode 5 | NB7 or Obsidian |
| 10:30 AM | Review revision-due topics | `/revision due` |

## Knowledge Base (65,833 chunks)
| Subject | Chunks | Source |
|---------|--------|--------|
| History | 13,924 | Spectrum, NCERTs, Bipan Chandra, PYQs |
| PYQ | 9,866 | Mains GS1-4, Prelims 2011-2025, CSAT |
| Economy | 7,771 | Ramesh Singh, Economic Survey 2025-26, Budget |
| Geography | 7,441 | NCERTs, PMF Human + Physical Geography |
| Polity | 6,461 | Laxmikanth 8e, NCERTs |
| Environment | 5,864 | Shankar IAS, NCERTs |
| S&T | 3,018 | PYQs + notes |
| Art & Culture | 1,432 | PYQs + 1 NCERT |
| Agriculture | 999 | PYQs only |
| Current Affairs | 764 | Indian Express x4, NB6 daily |
| Strategy | 525 | Anudeep Durishetty AIR 1 |

### Gaps to Fill
- [ ] Science & Tech — need Shankar IAS S&T PDF
- [ ] Agriculture — need textbook PDF
- [ ] Art & Culture — need Nitin Singhania PDF
- [ ] Ethics (GS4) — need Lexicon Ethics PDF
- [ ] Internal Security — need Ashok Kumar PDF
- [ ] IR — need Pavneet Singh IR PDF
- [ ] Telugu Optional — need literature PDFs

## This Week
![[00_Dashboard/Weekly_Review]]

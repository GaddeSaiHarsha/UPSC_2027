---
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

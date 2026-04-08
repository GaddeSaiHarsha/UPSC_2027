# Hermes V1.6 — Stateful `/drill` with Hidden Answer Keys

> **PR**: [#7 Hermes V1.6: stateful /drill with hidden answer keys](https://github.com/GaddeSaiHarsha/UPSC_2027/pull/7)
> **Date**: 2026-04-08
> **Status**: ✅ Merged
> **Base**: `copilot/update-documentation-for-project` (V1.5 session infrastructure from [[HERHERMES_V1_5_ROCK_SOLID_PLAN|PR #6]])
> **Lines changed**: +239 / −11 in `bot_code/hermes_full.py`

---

## Table of Contents

1. [Problem Statement](#problem-statement)
2. [What Changed — Before vs After](#what-changed--before-vs-after)
3. [Architecture & Data Flow](#architecture--data-flow)
4. [New Helper Functions — Deep Dive](#new-helper-functions--deep-dive)
5. [Session State Model](#session-state-model)
6. [Answer Parsing — Flexible Input Formats](#answer-parsing--flexible-input-formats)
7. [Grading & Follow-Up Logic](#grading--follow-up-logic)
8. [Weakness Tracking Integration](#weakness-tracking-integration)
9. [Solutions Extracted — Verification Checklist](#solutions-extracted--verification-checklist)
10. [Key Observations](#key-observations)
11. [Interlinks & Related Work](#interlinks--related-work)
12. [Testing & Verification Guide](#testing--verification-guide)

---

## Problem Statement

The `/drill` command was a **one-shot fire-and-forget** Groq call. It asked the LLM to generate 3 interleaved MCQs, sent the raw response (including answers) to the user, and then relied on the LLM again to grade the user's reply in the free-text handler. This had three critical flaws:

| Flaw | Impact |
|------|--------|
| **Answers leaked** in the initial response | User could see correct answers before attempting |
| **Non-deterministic grading** | Free-text handler re-asked the LLM to grade, which could hallucinate different correct answers |
| **No session tracking** | No way to track attempts, log weaknesses, or chain follow-ups |

> [!warning] The same flaw existed in `/quiz` before [[HERHERMES_V1_5_ROCK_SOLID_PLAN|V1.5]]. The `/drill` upgrade mirrors that fix but extends it to handle **3 MCQs** instead of 1.

---

## What Changed — Before vs After

### Before (V1.5 — one-shot `/drill`)

```python
async def cmd_drill(update, ctx):
    prompt = (
        "INTERLEAVED DRILL — mix 3 questions from 3 different subjects...\n"
        "Do NOT reveal answers. Number them 1, 2, 3.\n"
        "After I answer all three, grade each and explain."
    )
    mem = get_memory_context()
    resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)
    log_hermes("/drill", "interleaved", resp, tok, lat)
    await send_long(update, resp)  # ← raw LLM output, no session
```

**Problems**: No `[USER]/[KEY]` split. No session stored. Grading delegated to LLM on next message.

### After (V1.6 — stateful `/drill`)

```python
async def cmd_drill(update, ctx):
    public_text, keys, tok, lat = await generate_drill_with_keys(mem)
    set_session(ctx, "drill", {
        "questions_text": public_text,  # [USER] block only
        "drill_keys": keys,             # 3 validated JSON key dicts
        "attempts": 0,
        "started_at": datetime.utcnow().isoformat()
    })
    await send_long(update, public_text)  # ← only public questions
```

**Fixes**: Hidden keys stored in session. Deterministic grading. Full DB logging. Auto follow-up on weakest concept.

---

## Architecture & Data Flow

```
User sends /drill
       │
       ▼
┌──────────────────────────────┐
│  build_drill_prompt()        │  Structured prompt with [USER]/[KEY] format
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│  call_hermes (Groq)          │  Llama 3.3 70B generates 3 MCQs
│  asyncio.to_thread()         │
└──────────────┬───────────────┘
               │ raw response
               ▼
┌──────────────────────────────┐
│  parse_drill_payload()       │  Splits [USER] from [KEY]
│  ├─ extract_tagged_block()   │  Validates JSON array (len=3)
│  ├─ json.loads(key_block)    │  Checks all 7 required fields
│  └─ normalise correct_option │  Uppercase A/B/C/D check
└──────────────┬───────────────┘
               │ (public_text, keys)
               ▼
┌──────────────────────────────┐
│  set_session(ctx, "drill")   │  Stores keys + metadata
│  send_long(public_text)      │  Only questions reach Telegram
└──────────────────────────────┘

User answers: "1-B 2-D 3-A"
       │
       ▼
┌──────────────────────────────┐
│  handle_message()            │
│  session.mode == "drill"     │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│  parse_drill_answers()       │  Regex: numbered or bare letters
│  Validate {1,2,3} present    │
└──────────────┬───────────────┘
               │ {1:'B', 2:'D', 3:'A'}
               ▼
┌──────────────────────────────┐
│  Grade loop (deterministic)  │
│  ├─ Compare vs stored keys   │
│  ├─ _db_exec → quiz_history  │  All 3 Q logged individually
│  ├─ log_weakness() if wrong  │  Tracks concept + source
│  └─ render_single_drill_result│ Per-Q verdict block
└──────────────┬───────────────┘
               │
        ┌──────┴──────┐
        │             │
   All correct    Any wrong
        │             │
        ▼             ▼
  clear_session  generate_quiz_with_key()
  "✅ Complete"  on weakest concept
                      │
                      ▼
                set_session("quiz")
                Follow-up MCQ sent
```

---

## New Helper Functions — Deep Dive

### 1. `build_drill_prompt() → str`

**Location**: After quiz generation section (~line 843)

Generates a structured prompt that forces the LLM to output in a parseable format:

- **`[USER]` block**: 3 numbered MCQs (Q1, Q2, Q3), each with (A)–(D) options
- **`[KEY]` block**: JSON array of 3 objects, each with 7 fields

```python
"[KEY]\n"
"[{\"qno\":1,\"topic\":\"...\",\"concept\":\"...\",\"correct_option\":\"A/B/C/D\","
"\"explanation\":\"2-4 lines\",\"trap\":\"1-3 lines\",\"rule\":\"one memory rule\"},"
# ... Q2, Q3 ...
"]\n[/KEY]"
```

**Key design decisions**:
- No topic argument (unlike `build_quiz_prompt(topic, concept_hint)`) — drills are always interleaved across GS areas
- Explicit instruction "Each question from a different GS area or Optional"
- Format enforced: "The [KEY] block must be a valid JSON array of exactly 3 objects"

> [!info] Compare with [[HERHERMES_V1_5_ROCK_SOLID_PLAN#Block 2 Quiz Generation|V1.5 quiz prompt]]
> `/quiz` uses `build_quiz_prompt(topic, concept_hint)` for a single MCQ.
> `/drill` uses `build_drill_prompt()` for 3 MCQs — no topic param.

---

### 2. `parse_drill_payload(raw_text) → (str, list[dict])`

**Location**: ~line 874

Strict validation pipeline:

| Step | Check | Error on Failure |
|------|-------|------------------|
| 1 | Extract `[USER]` block | `"Missing [USER] block in drill payload"` |
| 2 | Extract `[KEY]` block | `"Missing [KEY] block in drill payload"` |
| 3 | `json.loads(key_block)` | `"Invalid drill KEY JSON: {e}"` |
| 4 | `isinstance(keys, list) and len(keys) == 3` | `"Expected 3 drill keys, got ..."` |
| 5 | For each key: check 7 required fields | `"Drill key {i+1} missing fields: {missing}"` |
| 6 | `correct_option` in `{A, B, C, D}` | `"Drill key {i+1}: correct_option must be A/B/C/D"` |
| 7 | `qno` cast to `int` | Normalisation |

**Required fields per key**: `qno`, `topic`, `concept`, `correct_option`, `explanation`, `trap`, `rule`

> [!tip] Observation
> The quiz payload parser (`parse_quiz_payload`) validates a **single dict**.
> The drill payload parser validates a **list of 3 dicts** — same field set plus `qno`.

---

### 3. `generate_drill_with_keys(mem) → (str, list[dict], int, int)`

**Location**: ~line 904

Orchestrator function. Mirrors `generate_quiz_with_key(topic, mem, concept_hint)`:

```python
async def generate_drill_with_keys(mem: str):
    prompt = build_drill_prompt()
    raw_resp, tok, lat = await asyncio.to_thread(call_hermes, prompt, mem)
    public_text, keys = parse_drill_payload(raw_resp)
    return public_text, keys, tok, lat
```

**Pattern**: `build_*_prompt() → call_hermes() → parse_*_payload() → return`

Both quiz and drill follow this exact 3-step pipeline. The difference is:
- `/quiz`: `(str, dict, int, int)` — single key dict
- `/drill`: `(str, list[dict], int, int)` — list of 3 key dicts

---

### 4. `parse_drill_answers(text) → dict[int, str]`

**Location**: ~line 912

Flexible regex parser that accepts multiple answer formats:

| Format | Example | Regex Pattern |
|--------|---------|---------------|
| Numbered-dash | `1-B 2-D 3-A` | `(\d)\s*[\-\)\.\:]\s*([ABCD])` |
| Numbered-paren | `1) B, 2) D, 3) A` | Same pattern |
| Numbered-dot | `1.B 2.D 3.A` | Same pattern |
| Bare letters | `B D A` | `\b([ABCD])\b` (exactly 3 matches) |
| Comma-separated | `B, D, A` | Same bare pattern |

**Priority**: Numbered patterns checked first. Bare letters only if no numbered matches found. This prevents `1-B` from also matching `B` as a bare letter.

**Returns `{}` (empty)** if format unrecognised → triggers the "Reply with all 3 answers in one line" prompt.

> [!warning] Edge case
> If user sends only 2 answers (e.g. `B D`), bare pattern finds 2 letters but `len(bare) == 3` fails → returns `{}`.
> If user sends `1-B 3-A` (missing Q2), numbered pattern finds 2 → `set(answers.keys()) != {1,2,3}` fails in handler.

---

### 5. `render_single_drill_result(qkey, user_answer, is_correct) → str`

**Location**: ~line 940

Per-question feedback block identical in structure to [[HERHERMES_V1_5_ROCK_SOLID_PLAN#Deterministic Quiz Grading|quiz feedback]] but more compact:

```
✅ Q1: Your answer: B | Correct: B
WHY: The Concurrent List allows both Union and State...
TRAP: "Only Parliament" is wrong because Article 254...
RULE: Article 254 — repugnancy doctrine applies
```

vs quiz feedback:

```
✅ CORRECT
Your answer: B
Correct option: B

WHY:
...
TRAP:
...
RULE:
...
```

**Observation**: Drill feedback is denser (single line per field, no blank lines) because 3 results stack in one message.

---

### 6. Replaced `cmd_drill()` (command handler)

**Location**: ~line 1221

| Aspect | Before | After |
|--------|--------|-------|
| LLM call | `call_hermes(prompt, mem)` | `generate_drill_with_keys(mem)` |
| What user sees | Full LLM response (incl. answers) | `[USER]` block only |
| Session | None | `set_session(ctx, "drill", {...})` |
| Error handling | None | `try/except` with user-friendly fallback |
| Logging | `log_hermes("/drill", ...)` | Same ✅ |

---

## Session State Model

### Drill session schema (stored in `ctx.user_data["_session"]`)

```python
{
    "mode": "drill",
    "data": {
        "questions_text": "Q1: Which article...\n(A)...",  # [USER] block
        "drill_keys": [                                      # 3 validated dicts
            {
                "qno": 1,
                "topic": "Polity",
                "concept": "Federalism",
                "correct_option": "B",
                "explanation": "Article 254 provides...",
                "trap": "Option A says 'only Parliament'...",
                "rule": "Repugnancy → Article 254"
            },
            # ... Q2, Q3
        ],
        "attempts": 0,
        "started_at": "2026-04-08T07:30:00"
    },
    "updated_at": "2026-04-08T07:30:00"
}
```

### Comparison with quiz session

| Field | Quiz (`/quiz`) | Drill (`/drill`) |
|-------|----------------|------------------|
| `mode` | `"quiz"` | `"drill"` |
| `topic` | ✅ Single topic | ❌ N/A (multi-subject) |
| `concept` | ✅ Single concept | ❌ N/A (per-key) |
| `question_text` / `questions_text` | 1 MCQ text | 3 MCQs text |
| `answer_key` / `drill_keys` | 1 dict | list of 3 dicts |
| `attempts` | ✅ Counter | ✅ Counter |
| `started_at` | ✅ ISO timestamp | ✅ ISO timestamp |

### Session lifecycle

```
/drill → set_session("drill") → user answers → grade
                                                  │
                                     ┌────────────┴────────────┐
                                     │                         │
                              All 3 correct              Any wrong
                                     │                         │
                              clear_session()        set_session("quiz")
                              "✅ Complete"          Follow-up on weakest
                                                     concept → quiz loop
```

> [!info] Session TTL
> All sessions expire after **45 minutes** (`SESSION_TTL_SECONDS = 2700`).
> `touch_session()` refreshes `updated_at` on each interaction.

---

## Answer Parsing — Flexible Input Formats

The `parse_drill_answers()` function was designed to handle real-world Telegram input patterns:

### Verified working formats

```
1-B 2-D 3-A       → {1:'B', 2:'D', 3:'A'}  ✅
B D A              → {1:'B', 2:'D', 3:'A'}  ✅
1) B, 2) D, 3) A  → {1:'B', 2:'D', 3:'A'}  ✅
1.B 2.D 3.A       → {1:'B', 2:'D', 3:'A'}  ✅
1:B 2:D 3:A       → {1:'B', 2:'D', 3:'A'}  ✅
b d a              → {1:'B', 2:'D', 3:'A'}  ✅  (lowercased → .upper())
B,D,A              → {1:'B', 2:'D', 3:'A'}  ✅
```

### Edge cases that correctly reject

```
B D                → {}  (only 2 bare letters)
1-B                → {1:'B'}  (missing Q2, Q3 → handler rejects)
hello              → {}  (no valid letters)
ABCD               → {}  (4 bare letters ≠ 3)
```

---

## Grading & Follow-Up Logic

### Deterministic grading loop (in `handle_message()`)

For each of the 3 questions:

```python
for qkey in drill_keys:
    user_answer = answers.get(qno, "?")
    is_correct = (user_answer == qkey["correct_option"])

    if is_correct:
        total_correct += 1
    else:
        incorrect_concepts.append(...)
        log_weakness("Prelims", concept, "drill")

    _db_exec("INSERT INTO quiz_history ...")
    result_blocks.append(render_single_drill_result(...))
```

### Follow-up branching

| Condition | Action |
|-----------|--------|
| `total_correct == 3` | `clear_session(ctx)` → "✅ Drill session complete" |
| `total_correct < 3` | `generate_quiz_with_key("Prelims", mem, concept_hint=weakest_concept)` |
| Follow-up succeeds | `set_session(ctx, "quiz", ...)` → user enters quiz loop |
| Follow-up fails | `clear_session(ctx)` → error message + "start again" |

> [!tip] Cross-mode transition
> On wrong answers, `/drill` **switches the session to `"quiz"` mode** targeting the weakest concept.
> The user is now in the `/quiz` handler loop from [[HERHERMES_V1_5_ROCK_SOLID_PLAN|V1.5]] — no new code needed.

---

## Weakness Tracking Integration

### What gets logged

| Table | When | Data |
|-------|------|------|
| `quiz_history` | Every drill Q (correct or not) | subject, question text (truncated 900), user_answer, was_correct, score (0.0/1.0), topic |
| `weak_topics` | Only incorrect answers | subject="Prelims", topic=concept, source="drill" |
| `hermes_interactions` | On `/drill` command | command="/drill", response=public_text, tokens, latency |
| `interactions` | On `/drill` command | Via `log_interaction()` called by `log_hermes()` |

### Weakness escalation path

```
User gets Q1 wrong (concept: "Federalism")
       │
       ▼
log_weakness("Prelims", "Federalism", "drill")
       │
       ▼
INSERT INTO weak_topics ... ON CONFLICT DO UPDATE SET miss_count=miss_count+1
       │
       ▼
weakest_concept = "Federalism"  (first incorrect)
       │
       ▼
generate_quiz_with_key("Prelims", mem, concept_hint="Federalism")
       │
       ▼
set_session("quiz", {...})  → quiz loop on Federalism
```

This means:
- `/weak` command will now surface drill-originated weaknesses
- `/stats` reflects drill attempts in `quiz_history` count
- Follow-up quiz on weakest concept reinforces spaced repetition

---

## Solutions Extracted — Verification Checklist

### Solution 1: `[USER]/[KEY]` Tag-Based Prompt Engineering

**What**: Force LLM to output in a parseable format with tagged blocks.

**Why it works**: LLMs (especially instruction-tuned models like Llama 3.3 70B) reliably follow structured output templates when the format is shown explicitly with delimiters.

**Verification**:
```python
# In a Python REPL or test script:
from hermes_full import build_drill_prompt, parse_drill_payload

prompt = build_drill_prompt()
assert "[USER]" in prompt
assert "[KEY]" in prompt
assert "valid JSON array of exactly 3 objects" in prompt

# Simulated LLM response:
test_response = """
[USER]
Q1: Which article deals with repugnancy?
(A) Article 245  (B) Article 254  (C) Article 256  (D) Article 262

Q2: The Tropic of Cancer passes through how many Indian states?
(A) 6  (B) 7  (C) 8  (D) 9

Q3: Who appoints the CAG?
(A) President  (B) PM  (C) CJI  (D) Speaker

Reply with answers for all 3 questions, e.g. 1-B 2-D 3-A
[/USER]

[KEY]
[{"qno":1,"topic":"Polity","concept":"Federalism","correct_option":"B",
  "explanation":"Article 254 deals with repugnancy","trap":"245 is general legislative powers","rule":"254 = repugnancy"},
 {"qno":2,"topic":"Geography","concept":"Tropic of Cancer","correct_option":"C",
  "explanation":"8 states: Gujarat, Rajasthan, MP, Chhattisgarh, Jharkhand, WB, Tripura, Mizoram","trap":"7 is commonly guessed","rule":"GR-MP-CJ-WT-M = 8"},
 {"qno":3,"topic":"Polity","concept":"Constitutional Bodies","correct_option":"A",
  "explanation":"Article 148 — President appoints CAG","trap":"PM recommends but doesn't appoint","rule":"CAG = President appoints under Art 148"}]
[/KEY]
"""

public, keys = parse_drill_payload(test_response)
assert len(keys) == 3
assert all(k["correct_option"] in {"A","B","C","D"} for k in keys)
assert keys[0]["qno"] == 1
```

---

### Solution 2: Deterministic Answer Grading

**What**: Store answer keys in session memory, grade by exact string match.

**Why it works**: Eliminates LLM hallucination during grading. `user_answer == correct_option` is O(1) and infallible.

**Verification**:
```python
# Grade drill answers deterministically:
stored_keys = [
    {"qno": 1, "correct_option": "B", "topic": "Polity", "concept": "Federalism", ...},
    {"qno": 2, "correct_option": "C", "topic": "Geography", "concept": "Tropic of Cancer", ...},
    {"qno": 3, "correct_option": "A", "topic": "Polity", "concept": "Constitutional Bodies", ...}
]

user_answers = {1: "B", 2: "D", 3: "A"}  # from parse_drill_answers("B D A")

results = []
for k in stored_keys:
    is_correct = (user_answers[k["qno"]] == k["correct_option"])
    results.append(is_correct)

assert results == [True, False, True]  # Q1 ✅, Q2 ❌, Q3 ✅
```

---

### Solution 3: Flexible Answer Parsing with Priority Regex

**What**: Accept numbered (`1-B`), bare (`B D A`), and mixed formats.

**Why it works**: Telegram users type in unpredictable formats. Two-pass regex (numbered first, bare second) handles all observed patterns.

**Verification**:
```python
from hermes_full import parse_drill_answers

# All should produce {1:'B', 2:'D', 3:'A'}
assert parse_drill_answers("1-B 2-D 3-A") == {1:'B', 2:'D', 3:'A'}
assert parse_drill_answers("B D A") == {1:'B', 2:'D', 3:'A'}
assert parse_drill_answers("1) B, 2) D, 3) A") == {1:'B', 2:'D', 3:'A'}
assert parse_drill_answers("1.b 2.d 3.a") == {1:'B', 2:'D', 3:'A'}  # case insensitive

# Rejection cases
assert parse_drill_answers("B D") == {}        # only 2 letters
assert parse_drill_answers("hello") == {}       # no matches
assert parse_drill_answers("1-B") == {1:'B'}   # incomplete → handler rejects
```

---

### Solution 4: Cross-Mode Session Transition (Drill → Quiz)

**What**: On wrong answers, auto-generate a follow-up quiz on the weakest concept and switch session mode from `"drill"` to `"quiz"`.

**Why it works**: Reuses the entire V1.5 quiz session handler. No duplicate code. The user seamlessly enters the quiz loop.

**Verification**:
```python
# After drill grading with wrong answers:
# weakest_concept = "Federalism"

# The code does:
set_session(ctx, "quiz", {
    "topic": followup_key.get("topic", "Prelims"),
    "concept": followup_key.get("concept", "Federalism"),
    "question_text": followup_public,
    "answer_key": followup_key,
    "attempts": 0,
    "started_at": datetime.utcnow().isoformat()
})

# Next user message → handle_message() → session.mode == "quiz"
# → V1.5 quiz handler grades deterministically
# → No new code needed for follow-up loop
```

---

### Solution 5: Per-Question Database Logging

**What**: Each drill question logged individually to `quiz_history` (not as a batch).

**Why it works**: `/stats` accuracy % and `/weak` topic analysis work unchanged. Each Q has its own `was_correct`, `score`, `topic`, and `concept`.

**Verification**:
```sql
-- After a drill with 2 correct, 1 wrong:
SELECT subject, topic, was_correct, score
FROM quiz_history
WHERE question LIKE 'Drill Q%'
ORDER BY rowid DESC LIMIT 3;

-- Expected:
-- Polity     | Federalism         | 1 | 1.0
-- Geography  | Tropic of Cancer   | 0 | 0.0
-- Polity     | Constitutional Bodies | 1 | 1.0
```

---

## Key Observations

### 1. Pattern Reuse — V1.5 as a Blueprint

The entire V1.6 drill implementation is a scaled-up clone of the V1.5 quiz pattern:

| Component | Quiz (V1.5) | Drill (V1.6) |
|-----------|-------------|--------------|
| Prompt builder | `build_quiz_prompt(topic, hint)` | `build_drill_prompt()` |
| Payload parser | `parse_quiz_payload()` → `(str, dict)` | `parse_drill_payload()` → `(str, list[dict])` |
| Generator | `generate_quiz_with_key()` | `generate_drill_with_keys()` |
| Answer normaliser | `normalise_mcq_answer()` → single letter | `parse_drill_answers()` → `{1:A, 2:B, 3:C}` |
| Feedback renderer | `render_quiz_feedback()` | `render_single_drill_result()` |
| Session mode | `"quiz"` | `"drill"` |
| Follow-up | Same-concept quiz | Weakest-concept quiz (reuses V1.5) |

### 2. Handler Ordering Matters

In `handle_message()`, the session dispatch order is:

```
quiz → drill → socratic → free chat
```

This is intentional: quiz and drill are MCQ-based (expect letter answers), socratic expects free text. Placing drill after quiz means if a drill follow-up switches to quiz mode, the quiz handler processes the next message — not the drill handler.

### 3. Error Recovery is Graceful

Both `/drill` command and the drill handler have `try/except` blocks:

| Point of failure | Recovery |
|------------------|----------|
| LLM response missing `[USER]/[KEY]` | "⚠️ Drill generation failed. Try /drill again." |
| User sends invalid answer format | Prompt with format examples (no session cleared) |
| Follow-up quiz generation fails | Clear session + error + "start again" |

The session is **never left in an inconsistent state** — it's either updated or cleared.

### 4. Token & Latency Tracking Preserved

```python
log_hermes("/drill", "interleaved", public_text, tok, lat)
log_hermes("drill_followup", weakest_concept, followup_public, tok, lat)
```

All calls tracked in `hermes_interactions` with `tokens_used` and `latency_ms`. This feeds `/stats` and helps monitor Groq free-tier usage.

### 5. No Changes to Existing Behaviour

- `/quiz` handler: **Unchanged** ✅
- `/socratic` handler: **Unchanged** ✅
- Free-text handler: **Unchanged** (drill branch inserted before socratic) ✅
- `/cancel`: Works for drill sessions (calls `clear_session()` which pops `_session`) ✅

---

## Interlinks & Related Work

| Document | Relevance |
|----------|-----------|
| [[HERHERMES_V1_5_ROCK_SOLID_PLAN]] | V1.5 plan that established the session infrastructure this builds on |
| [[UPSC_Audio_Pipeline_Docs]] | Audio pipeline that consumes practice mode outputs |
| [[00_Dashboard/Home\|Dashboard]] | Quick links to practice modes including `/drill` |
| [[04_Traps/Trap_Index\|Trap Index]] | Drill traps feed into the trap database via `/trap` |
| [[05_Revision/Due_Today\|Due Today]] | Weakness tracking from drills surfaces concepts for revision |
| [[06_Answer_Practice/KARL_Scores\|KARL Scores]] | Drill scores logged to `quiz_history` feed accuracy metrics |

### PR Chain

```
PR #5  User creates V1.5 rock-solid plan doc
  │
  ▼
PR #6  V1.5: stateful quiz/socratic sessions (session infra + deterministic grading)
  │
  ▼
PR #7  V1.6: stateful drill with hidden answer keys (THIS PR)
  │
  ▼
PR #8  This analysis document
```

### Related Fixes in Earlier PRs

| PR | Fix | Connection to V1.6 |
|----|-----|---------------------|
| PR #3 | `/mastery_update` SQL injection fix | Same `_db_exec()` used for drill DB logging |
| PR #6 | `cmd_eod` f-string fix | Same string interpolation pattern fixed |
| PR #6 | `cmd_cancel` session clear fix | `clear_session()` now works for drill sessions too |

---

## Testing & Verification Guide

### Manual Test Sequence (on Telegram)

1. **Send `/drill`** → Should receive 3 numbered MCQs without answers
2. **Reply `1-B 2-D 3-A`** → Should get per-question verdict with WHY/TRAP/RULE
3. **If wrong**: Should see follow-up MCQ on weakest concept + session switches to quiz
4. **Reply with quiz answer** → Should enter V1.5 quiz loop
5. **Send `/cancel`** at any point → Should clear session cleanly
6. **Send `/stats`** → Should show updated quiz count and accuracy

### Unit Test Scenarios

```python
# 1. Prompt format
prompt = build_drill_prompt()
assert "[USER]" in prompt and "[KEY]" in prompt
assert "exactly 3 objects" in prompt

# 2. Payload parsing — valid
valid_response = '[USER]\nQ1:...\n[/USER]\n[KEY]\n[...3 valid dicts...]\n[/KEY]'
public, keys = parse_drill_payload(valid_response)
assert isinstance(keys, list) and len(keys) == 3

# 3. Payload parsing — missing USER
try:
    parse_drill_payload("[KEY][...][/KEY]")
    assert False, "Should have raised"
except ValueError as e:
    assert "Missing [USER]" in str(e)

# 4. Payload parsing — wrong key count
try:
    parse_drill_payload('[USER]Q[/USER]\n[KEY][{"qno":1,...},{"qno":2,...}][/KEY]')
    assert False, "Should have raised"
except ValueError as e:
    assert "Expected 3" in str(e)

# 5. Answer parsing
assert parse_drill_answers("1-B 2-D 3-A") == {1:'B', 2:'D', 3:'A'}
assert parse_drill_answers("B D A") == {1:'B', 2:'D', 3:'A'}
assert parse_drill_answers("B D") == {}

# 6. Render feedback
result = render_single_drill_result(
    {"qno": 1, "correct_option": "B", "explanation": "Art 254",
     "trap": "245 confuses", "rule": "254 = repugnancy"},
    "A", False)
assert "❌" in result
assert "Art 254" in result
```

---

> **Last updated**: 2026-04-08
> **Author**: Copilot Agent (analysis of PR #7)
> **Next**: Deploy V1.6 to bot VM → `wget` raw `hermes_full.py` from GitHub → restart service

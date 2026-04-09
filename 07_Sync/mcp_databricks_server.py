#!/usr/bin/env python3
"""
UPSC Databricks MCP Server
===========================
Exposes your 80,800-chunk Delta knowledge base directly to Claude Code.
Claude can query stories, traps, deep analysis, and search chunks —
without you having to open Databricks notebooks.

Setup:
  1. pip install -r mcp_requirements.txt
  2. Fill sql_warehouse_id in sync_config.json
  3. Ensure ~/.databrickscfg has [upsc] profile with token
  4. MCP config in .claude/settings.local.json already wired up

Tools exposed to Claude:
  get_today_stories      — Today's CA stories (title, priority, GS papers)
  get_traps              — Traps for a topic or subject
  get_deep_analysis      — Mains skeleton + PYQ patterns for a story slug
  search_chunks          — Full-text search across 80K knowledge base chunks
  get_daily_summary      — Pipeline status: story count, trap count, NB run time
"""

import json
import os
import sys
import logging
from datetime import date
from pathlib import Path

# ── MCP imports ──
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ── Databricks SQL connector ──
from databricks import sql as dbsql

# ── Config ──
CONFIG_PATH = Path(__file__).parent / "sync_config.json"
with open(CONFIG_PATH) as f:
    _cfg = json.load(f)

HOST            = _cfg["databricks_host"].replace("https://", "")
WAREHOUSE_ID    = _cfg.get("sql_warehouse_id", "")
CLI_PROFILE     = _cfg.get("cli_profile", "upsc")
CATALOG         = _cfg.get("catalog", "upsc_catalog")
SCHEMA          = _cfg.get("schema", "rag")

# ── Auth: read token from ~/.databrickscfg profile ──
def _read_token_from_profile(profile: str) -> str:
    """Read PAT from ~/.databrickscfg [profile] section."""
    cfg_file = Path.home() / ".databrickscfg"
    if not cfg_file.exists():
        return os.environ.get("DATABRICKS_TOKEN", "")
    in_section = False
    for line in cfg_file.read_text().splitlines():
        line = line.strip()
        if line == f"[{profile}]":
            in_section = True
            continue
        if in_section:
            if line.startswith("["):
                break
            if line.startswith("token"):
                return line.split("=", 1)[1].strip()
    return os.environ.get("DATABRICKS_TOKEN", "")

TOKEN = _read_token_from_profile(CLI_PROFILE)

# ── Logging ──
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr
)
log = logging.getLogger("upsc_mcp")


# ── DB connection helper ──
def _get_conn():
    """Return a fresh Databricks SQL connection."""
    if not WAREHOUSE_ID or WAREHOUSE_ID == "REPLACE_WITH_YOUR_WAREHOUSE_ID":
        raise ValueError(
            "sql_warehouse_id not set in sync_config.json. "
            "Go to Databricks → SQL Warehouses → your warehouse → "
            "Connection Details → HTTP Path (last segment after /warehouses/)"
        )
    return dbsql.connect(
        server_hostname=HOST,
        http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}",
        access_token=TOKEN,
        catalog=CATALOG,
        schema=SCHEMA,
    )


def _query(sql_text: str, params=None) -> list[dict]:
    """Execute SQL and return list of row dicts."""
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql_text, params or [])
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


# ================================================================
# TOOL IMPLEMENTATIONS
# ================================================================

def tool_get_today_stories(date_str: str = "") -> str:
    """Return today's CA stories with priority and GS paper mapping."""
    target = date_str.strip() if date_str else date.today().isoformat()
    rows = _query(
        "SELECT story_id, title, priority, gs_papers, topic_cluster, keywords "
        "FROM stories WHERE date = ? ORDER BY "
        "CASE priority WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2 "
        "WHEN 'MEDIUM' THEN 3 ELSE 4 END",
        [target]
    )
    if not rows:
        return f"No stories found for {target}. NB6 may not have run yet (scheduled 7 AM IST)."

    lines = [f"CA STORIES — {target} ({len(rows)} total)\n"]
    for r in rows:
        kw = r.get("keywords", "[]")
        try:
            kw_list = json.loads(kw) if isinstance(kw, str) else kw
            kw_str = ", ".join(kw_list[:4])
        except Exception:
            kw_str = str(kw)[:60]
        lines.append(
            f"[{r['priority']}] {r['title']}\n"
            f"  GS: {r.get('gs_papers', 'N/A')} | Cluster: {r.get('topic_cluster', 'N/A')}\n"
            f"  Keywords: {kw_str}\n"
            f"  ID: {r['story_id']}\n"
        )
    return "\n".join(lines)


def tool_get_traps(topic: str = "", subject: str = "", limit: int = 10) -> str:
    """Return traps for a topic or subject. topic is a keyword search, subject filters by subject column."""
    if topic:
        rows = _query(
            "SELECT trap_id, subject, trap_type, wrong_belief, correct_belief, severity "
            "FROM story_traps "
            "WHERE LOWER(wrong_belief) LIKE ? OR LOWER(correct_belief) LIKE ? OR LOWER(subject) LIKE ? "
            "ORDER BY CASE severity WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END "
            f"LIMIT {int(limit)}",
            [f"%{topic.lower()}%", f"%{topic.lower()}%", f"%{topic.lower()}%"]
        )
    elif subject:
        rows = _query(
            "SELECT trap_id, subject, trap_type, wrong_belief, correct_belief, severity "
            "FROM story_traps WHERE LOWER(subject) LIKE ? "
            "ORDER BY CASE severity WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END "
            f"LIMIT {int(limit)}",
            [f"%{subject.lower()}%"]
        )
    else:
        # Return today's traps
        today = date.today().isoformat()
        rows = _query(
            "SELECT t.trap_id, t.subject, t.trap_type, t.wrong_belief, t.correct_belief, t.severity "
            "FROM story_traps t JOIN stories s ON t.story_slug = s.slug "
            f"WHERE s.date = '{today}' "
            "ORDER BY CASE t.severity WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END "
            f"LIMIT {int(limit)}"
        )
        if not rows:
            return f"No traps found for today ({today}). Try: get_traps(topic='polity') or get_traps(subject='Economy')"

    if not rows:
        return f"No traps found for topic='{topic}' subject='{subject}'."

    lines = [f"TRAPS ({len(rows)} found)\n{'─'*50}"]
    for r in rows:
        lines.append(
            f"[{r['severity']}] {r['trap_type']} — {r['subject']}\n"
            f"  WRONG:   {r['wrong_belief']}\n"
            f"  CORRECT: {r['correct_belief']}\n"
        )
    return "\n".join(lines)


def tool_get_deep_analysis(story_slug: str) -> str:
    """Return mains skeleton + PYQ patterns + static links for a story slug."""
    rows = _query(
        "SELECT pyq_patterns, traps_detailed, mains_skeleton, static_links "
        "FROM deep_analysis WHERE story_id = ? OR story_id LIKE ?",
        [story_slug, f"%{story_slug}%"]
    )
    if not rows:
        return (
            f"No deep analysis found for '{story_slug}'.\n"
            "Use get_today_stories() to see valid story IDs, then pass the story_id here."
        )

    r = rows[0]
    sections = []

    # Mains skeleton
    try:
        sk = json.loads(r["mains_skeleton"]) if isinstance(r["mains_skeleton"], str) else r["mains_skeleton"]
        q = sk.get("question", "")
        body = "\n".join(f"  • {pt}" for pt in sk.get("body_points", []))
        sections.append(
            f"MAINS SKELETON\n{'─'*40}\n"
            f"Q: {q}\n"
            f"Intro: {sk.get('intro', '')}\n"
            f"Body:\n{body}\n"
            f"Conclusion: {sk.get('conclusion', '')}"
        )
    except Exception:
        sections.append(f"MAINS SKELETON\n{r.get('mains_skeleton', 'N/A')}")

    # PYQ patterns
    try:
        pyq = json.loads(r["pyq_patterns"]) if isinstance(r["pyq_patterns"], str) else r["pyq_patterns"]
        pyq_lines = []
        for p in (pyq if isinstance(pyq, list) else [pyq]):
            pyq_lines.append(f"  [{p.get('year','')} {p.get('paper','')}] {p.get('theme','')}")
        sections.append("PYQ PATTERNS\n" + "\n".join(pyq_lines))
    except Exception:
        sections.append(f"PYQ PATTERNS\n{r.get('pyq_patterns', 'N/A')}")

    # Static links
    try:
        sl = json.loads(r["static_links"]) if isinstance(r["static_links"], str) else r["static_links"]
        sl_lines = []
        for s in (sl if isinstance(sl, list) else [sl]):
            sl_lines.append(f"  {s.get('book','')} — {s.get('topic','')}: {s.get('why','')}")
        sections.append("STATIC LINKS (textbook chapters)\n" + "\n".join(sl_lines))
    except Exception:
        sections.append(f"STATIC LINKS\n{r.get('static_links', 'N/A')}")

    return "\n\n".join(sections)


def tool_search_chunks(query: str, subject: str = "", limit: int = 5) -> str:
    """Full-text search across 80,800 knowledge base chunks. Returns top matches."""
    if not query.strip():
        return "Provide a search query. Example: search_chunks('Article 356 President Rule', subject='Polity')"

    if subject:
        rows = _query(
            "SELECT chunk_id, subject, source_file, page_number, text "
            "FROM contextual_chunks "
            "WHERE LOWER(text) LIKE ? AND LOWER(subject) LIKE ? "
            f"LIMIT {int(limit)}",
            [f"%{query.lower()}%", f"%{subject.lower()}%"]
        )
    else:
        rows = _query(
            "SELECT chunk_id, subject, source_file, page_number, text "
            "FROM contextual_chunks "
            "WHERE LOWER(text) LIKE ? "
            f"LIMIT {int(limit)}",
            [f"%{query.lower()}%"]
        )

    if not rows:
        return f"No chunks found for '{query}'" + (f" in subject '{subject}'" if subject else "") + "."

    lines = [f"CHUNKS — '{query}' ({len(rows)} results)\n{'─'*50}"]
    for r in rows:
        snippet = r["text"][:300].replace("\n", " ")
        lines.append(
            f"[{r['subject']}] {r['source_file']} p.{r['page_number']}\n"
            f"  {snippet}...\n"
        )
    return "\n".join(lines)


def tool_get_daily_summary(date_str: str = "") -> str:
    """Pipeline status: story count, trap count, deep analysis status for today."""
    target = date_str.strip() if date_str else date.today().isoformat()

    story_rows = _query("SELECT COUNT(*) as cnt FROM stories WHERE date = ?", [target])
    trap_rows  = _query(
        "SELECT COUNT(*) as cnt FROM story_traps t "
        "JOIN stories s ON t.story_slug = s.slug WHERE s.date = ?",
        [target]
    )
    da_rows    = _query("SELECT COUNT(*) as cnt FROM deep_analysis WHERE date = ?", [target])
    geo_rows   = _query("SELECT COUNT(*) as cnt FROM geography_context WHERE date = ?", [target])

    story_count = story_rows[0]["cnt"] if story_rows else 0
    trap_count  = trap_rows[0]["cnt"]  if trap_rows  else 0
    da_count    = da_rows[0]["cnt"]    if da_rows    else 0
    geo_count   = geo_rows[0]["cnt"]   if geo_rows   else 0

    # Total chunk count
    chunk_rows = _query("SELECT COUNT(*) as cnt FROM contextual_chunks")
    total_chunks = chunk_rows[0]["cnt"] if chunk_rows else 0

    status = "✅ Complete" if story_count > 0 else "⏳ NB6 not run yet (scheduled 7 AM IST)"

    return (
        f"DAILY PIPELINE SUMMARY — {target}\n"
        f"{'═'*40}\n"
        f"NB6 Status:     {status}\n"
        f"Stories today:  {story_count}\n"
        f"Traps today:    {trap_count}\n"
        f"Deep analysis:  {da_count} stories\n"
        f"Geo context:    {geo_count} stories\n"
        f"{'─'*40}\n"
        f"Total KB chunks: {total_chunks:,}\n"
        f"{'─'*40}\n"
        f"Use get_today_stories() to see today's stories.\n"
        f"Use get_traps() for today's trap list.\n"
    )


def tool_search_knowledge_graph(entity: str, limit: int = 10) -> str:
    """Search the Knowledge Graph for an entity and return its connections."""
    if not entity.strip():
        return "Provide an entity name. Example: search_knowledge_graph('Article 21')"

    # Find matching entities
    entity_rows = _query(
        "SELECT entity_id, entity_name, entity_type, description "
        "FROM kg_entities WHERE LOWER(entity_name) LIKE ? "
        f"LIMIT 5",
        [f"%{entity.lower()}%"]
    )
    if not entity_rows:
        return f"No entity found matching '{entity}' in Knowledge Graph."

    lines = [f"KNOWLEDGE GRAPH — '{entity}'\n{'─'*50}"]
    for e in entity_rows:
        lines.append(f"[{e['entity_type']}] {e['entity_name']}: {e.get('description','')[:120]}")

        # Get relationships for this entity
        rel_rows = _query(
            "SELECT r.relationship_type, e2.entity_name, e2.entity_type "
            "FROM kg_relationships r "
            "JOIN kg_entities e2 ON (r.target_entity_id = e2.entity_id OR r.source_entity_id = e2.entity_id) "
            "WHERE (r.source_entity_id = ? OR r.target_entity_id = ?) AND e2.entity_id != ? "
            f"LIMIT {int(limit)}",
            [e["entity_id"], e["entity_id"], e["entity_id"]]
        )
        if rel_rows:
            lines.append(f"  Connected to ({len(rel_rows)}):")
            for r in rel_rows:
                lines.append(f"    ─{r['relationship_type']}→ {r['entity_name']} ({r['entity_type']})")
        lines.append("")

    return "\n".join(lines)


# ================================================================
# MCP SERVER WIRING
# ================================================================

app = Server("upsc-databricks")

TOOLS = [
    Tool(
        name="get_today_stories",
        description=(
            "Get today's Current Affairs stories from the Databricks pipeline. "
            "Returns story titles, GS paper mapping, priority (CRITICAL/HIGH/MEDIUM/LOW), "
            "topic cluster, and keywords. Optionally pass a date string (YYYY-MM-DD)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date in YYYY-MM-DD format. Defaults to today."}
            }
        }
    ),
    Tool(
        name="get_traps",
        description=(
            "Get UPSC exam traps — wrong beliefs students commonly hold. "
            "Filter by topic keyword OR subject name. "
            "Returns: trap type, wrong belief, correct belief, severity. "
            "No args → returns today's traps."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "topic":   {"type": "string", "description": "Keyword to search in trap text (e.g. 'Article 356', 'GST')"},
                "subject": {"type": "string", "description": "Subject filter (e.g. 'Polity', 'Economy', 'History')"},
                "limit":   {"type": "integer", "description": "Max results (default 10)", "default": 10}
            }
        }
    ),
    Tool(
        name="get_deep_analysis",
        description=(
            "Get the full mains preparation package for a CA story: "
            "mains answer skeleton (Q + intro + body points + conclusion), "
            "PYQ patterns (which past year questions connect), "
            "and static textbook links (which chapter to read). "
            "Pass the story_id from get_today_stories()."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "story_slug": {"type": "string", "description": "story_id or slug from get_today_stories()"}
            },
            "required": ["story_slug"]
        }
    ),
    Tool(
        name="search_chunks",
        description=(
            "Full-text search across 80,800 knowledge base chunks "
            "(History, Polity, Economy, Geography, Environment, Ethics, S&T, "
            "Telugu Optional, PYQs, and more). "
            "Returns matching passages with source file and page number."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query":   {"type": "string", "description": "Search query (e.g. 'President Rule Article 356 Bommai')"},
                "subject": {"type": "string", "description": "Optional subject filter (e.g. 'Polity', 'History')"},
                "limit":   {"type": "integer", "description": "Max results (default 5)", "default": 5}
            },
            "required": ["query"]
        }
    ),
    Tool(
        name="get_daily_summary",
        description=(
            "Get pipeline status for today: how many stories, traps, and deep analysis entries "
            "were generated by NB6. Also shows total knowledge base chunk count. "
            "Use this first thing in the morning to check if NB6 has run."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date in YYYY-MM-DD format. Defaults to today."}
            }
        }
    ),
    Tool(
        name="search_knowledge_graph",
        description=(
            "Search the UPSC Knowledge Graph for an entity and see all its connections. "
            "Great for cross-paper interlinking — e.g., search 'Article 21' to find all related "
            "concepts (Right to Privacy, Maneka Gandhi case, DPSP, etc.) across GS1-GS4. "
            "Use this to build interconnected Mains answers."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "entity": {"type": "string", "description": "Entity name to search (e.g. 'Article 21', 'Finance Commission', 'Kavitrayam')"},
                "limit":  {"type": "integer", "description": "Max connections to show (default 10)", "default": 10}
            },
            "required": ["entity"]
        }
    ),
]


@app.list_tools()
async def list_tools():
    return TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: dict):
    try:
        if name == "get_today_stories":
            result = tool_get_today_stories(arguments.get("date", ""))
        elif name == "get_traps":
            result = tool_get_traps(
                arguments.get("topic", ""),
                arguments.get("subject", ""),
                int(arguments.get("limit", 10))
            )
        elif name == "get_deep_analysis":
            result = tool_get_deep_analysis(arguments["story_slug"])
        elif name == "search_chunks":
            result = tool_search_chunks(
                arguments["query"],
                arguments.get("subject", ""),
                int(arguments.get("limit", 5))
            )
        elif name == "get_daily_summary":
            result = tool_get_daily_summary(arguments.get("date", ""))
        elif name == "search_knowledge_graph":
            result = tool_search_knowledge_graph(
                arguments["entity"],
                int(arguments.get("limit", 10))
            )
        else:
            result = f"Unknown tool: {name}"
    except ValueError as e:
        result = f"Configuration error: {e}"
    except Exception as e:
        log.error(f"Tool {name} failed: {e}", exc_info=True)
        result = f"Error running {name}: {type(e).__name__}: {e}"

    return [TextContent(type="text", text=result)]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

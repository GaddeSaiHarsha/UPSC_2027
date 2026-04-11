#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# UPSC Obsidian + Databricks CLI Setup for Mac
# Run this in Terminal: bash ~/Desktop/setup_upsc_obsidian.sh
# ═══════════════════════════════════════════════════════════════════
set -e

echo "═══════════════════════════════════════════════════════════"
echo "  UPSC Obsidian Vault — Mac Setup"
echo "═══════════════════════════════════════════════════════════"

# ── Step 1: Install Homebrew (if missing) ──
if ! command -v brew &>/dev/null; then
    echo "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    eval "$(/opt/homebrew/bin/brew shellenv)"
fi

# ── Step 2: Install Databricks CLI v2 ──
echo ""
echo "Step 2: Installing Databricks CLI v2..."
brew tap databricks/tap 2>/dev/null || true
brew install databricks 2>/dev/null || brew upgrade databricks 2>/dev/null || true
echo "  CLI version: $(databricks --version)"

# ── Step 3: Install Obsidian (if missing) ──
if [ ! -d "/Applications/Obsidian.app" ]; then
    echo ""
    echo "Step 3: Installing Obsidian..."
    brew install --cask obsidian
else
    echo ""
    echo "Step 3: Obsidian already installed ✓"
fi

# ── Step 4: Configure Databricks CLI ──
echo ""
echo "Step 4: Configuring Databricks CLI..."
echo "  Host: https://adb-7405615460529826.6.azuredatabricks.net"
echo ""
echo "  You'll need a Personal Access Token (PAT)."
echo "  Generate one at: Settings → Developer → Access Tokens"
echo ""
databricks configure --profile upsc --host https://adb-7405615460529826.6.azuredatabricks.net

# ── Step 5: Test CLI connectivity ──
echo ""
echo "Step 5: Testing CLI connectivity..."
if databricks --profile upsc fs ls /Volumes/upsc_catalog/rag/obsidian_ca/UPSC_2026/ 2>/dev/null; then
    echo "  CLI connected to Databricks! ✓"
else
    echo "  ⚠️  CLI connection failed. Check your token."
    echo "  Re-run: databricks configure --profile upsc"
fi

# ── Step 6: Create local vault directory ──
VAULT_DIR="$HOME/Desktop/UPSC_2027"
echo ""
echo "Step 6: Creating local vault at ${VAULT_DIR}..."
mkdir -p "${VAULT_DIR}/07_Sync"

# ── Step 7: Initial full sync ──
echo ""
echo "Step 7: Running initial full sync from Databricks..."
echo "  This downloads UPSC_2026 vault content + Daily_Practice folder..."
databricks --profile upsc fs cp -r \
    /Volumes/upsc_catalog/rag/obsidian_ca/UPSC_2026/ \
    "${VAULT_DIR}/" \
    --overwrite
echo "  Vault content synced ✓"
databricks --profile upsc fs cp -r \
    /Volumes/upsc_catalog/rag/obsidian_ca/Daily_Practice/ \
    "${VAULT_DIR}/Daily_Practice/" \
    --overwrite 2>/dev/null && echo "  Daily_Practice synced ✓" || echo "  ⚠️  Daily_Practice not yet on volume — will appear after NB7 runs"
echo "  Initial sync complete! ✓"

# ── Step 8: Fix launchd plist with actual $HOME ──
echo ""
echo "Step 8: Setting up daily auto-sync (8:15 AM IST)..."
PLIST_SRC="${VAULT_DIR}/07_Sync/com.upsc.obsidian-sync.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.upsc.obsidian-sync.plist"

# Replace {HOME} placeholder with actual home dir
sed "s|{HOME}|$HOME|g" "${PLIST_SRC}" > "${PLIST_DST}"

# Load the launchd job
launchctl unload "${PLIST_DST}" 2>/dev/null || true
launchctl load "${PLIST_DST}"
echo "  LaunchAgent installed: syncs daily at 8:15 AM IST ✓"

# ── Step 9: Update sync script to use profile ──
SYNC_SCRIPT="${VAULT_DIR}/07_Sync/sync_from_databricks.py"
if [ -f "$SYNC_SCRIPT" ]; then
    # Add --profile upsc to CLI calls
    sed -i '' 's/\["databricks"\]/["databricks", "--profile", "upsc"]/g' "$SYNC_SCRIPT"
    echo "  Sync script updated with --profile upsc ✓"
fi

# ── Step 10: Install Claude Code MCP server dependencies ──
echo ""
echo "Step 10: Installing MCP server Python dependencies..."
echo "  (This lets Claude Code query your 80K-chunk Databricks knowledge base directly)"

MCP_REQ="${VAULT_DIR}/07_Sync/mcp_requirements.txt"
if [ -f "$MCP_REQ" ]; then
    pip3 install -r "$MCP_REQ" --quiet
    echo "  MCP dependencies installed ✓"
else
    echo "  ⚠️  mcp_requirements.txt not found — skipping"
fi

# ── Step 11: Prompt user to fill in SQL Warehouse ID ──
echo ""
echo "Step 11: Configure SQL Warehouse ID for MCP..."
echo ""
echo "  The MCP server needs your Databricks SQL Warehouse ID."
echo "  How to find it:"
echo "    1. Go to: Databricks → SQL Warehouses"
echo "    2. Click your warehouse → Connection Details tab"
echo "    3. Look at 'HTTP path' — copy the last part after /warehouses/"
echo "    4. Open: ${VAULT_DIR}/07_Sync/sync_config.json"
echo "    5. Replace REPLACE_WITH_YOUR_WAREHOUSE_ID with your ID"
echo ""
echo "  Example HTTP path: /sql/1.0/warehouses/abcd1234ef567890"
echo "  You'd put: abcd1234ef567890"

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  SETUP COMPLETE!"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "  Vault location:  ~/Desktop/UPSC_2027"
echo "  Open in Obsidian: Open Folder as Vault → ~/Desktop/UPSC_2027"
echo "  Auto-sync:        Daily at 8:15 AM IST via launchd"
echo ""
echo "  Manual sync commands:"
echo "    Full sync:  python3 ~/Desktop/UPSC_2027/07_Sync/sync_from_databricks.py"
echo "    CA only:    python3 ~/Desktop/UPSC_2027/07_Sync/sync_from_databricks.py --ca-only"
echo "    Daily only: python3 ~/Desktop/UPSC_2027/07_Sync/sync_from_databricks.py --daily-only"
echo "    Dry run:    python3 ~/Desktop/UPSC_2027/07_Sync/sync_from_databricks.py --dry-run"
echo ""
echo "  Claude Code MCP (once warehouse ID is set):"
echo "    Open Claude Code in this folder — 5 Databricks tools will be available:"
echo "    • get_daily_summary    — check if NB6 has run"
echo "    • get_today_stories    — today's CA stories"
echo "    • get_traps            — search traps by topic or subject"
echo "    • get_deep_analysis    — mains skeleton + PYQ patterns for a story"
echo "    • search_chunks        — full-text search across 80K knowledge base"
echo ""
echo "  Next: Open Obsidian → Open Folder as Vault → ~/Desktop/UPSC_2027"
echo "═══════════════════════════════════════════════════════════"

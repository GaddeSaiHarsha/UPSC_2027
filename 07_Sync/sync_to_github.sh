#!/bin/bash
# Run from ~/Desktop/UPSC_2026
# Syncs vault to GitHub after Databricks sync

cd ~/Desktop/UPSC_2026
git add .
git commit -m "vault sync $(date '+%Y-%m-%d %H:%M')"
git push origin main
echo "✅ Vault synced to GitHub"

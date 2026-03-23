#!/bin/bash
# One-time setup — run from ~/Desktop/UPSC_2026

git init
git remote add origin https://github.com/YOURUSERNAME/UPSC_2026.git
git branch -M main
git add .
git commit -m "Initial vault — 80,808 chunk UPSC AI system"
git push -u origin main
echo "✅ GitHub repo initialized"
echo "Next: Install Obsidian Git plugin and set auto-push every 10 min"

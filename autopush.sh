#!/bin/bash
# Description: Automatically adds, commits, and pushes changes to GitHub.
# Usage: ./autopush.sh "Your commit message"

COMMIT_MSG=${1:-"Update Circuit Copilot code"}

echo "--- Auto-Pushing to GitHub ---"
echo "Commit message: $COMMIT_MSG"

git add .
git commit -m "$COMMIT_MSG"
git push origin main

echo "Push complete!"

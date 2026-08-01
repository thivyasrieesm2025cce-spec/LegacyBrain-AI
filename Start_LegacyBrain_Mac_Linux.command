#!/bin/bash
cd "$(dirname "$0")"
echo "Starting LegacyBrain AI..."
if command -v python3 &> /dev/null; then
    python3 webapp.py
else
    python webapp.py
fi

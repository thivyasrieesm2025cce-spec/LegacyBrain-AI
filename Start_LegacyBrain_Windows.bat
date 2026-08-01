@echo off
title LegacyBrain AI
echo Starting LegacyBrain AI...
python webapp.py
if errorlevel 1 (
    py webapp.py
)
pause

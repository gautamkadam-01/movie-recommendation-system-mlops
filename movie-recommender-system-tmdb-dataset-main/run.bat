@echo off
title Netflix Movie Recommender
echo ========================================================
echo   Starting Netflix-Style AI Movie Recommender System
echo ========================================================
echo.
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
pause

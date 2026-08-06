@echo off
REM Double-click this file to start the QA AI Platform web server.
cd /d "%~dp0"
set PYTHONPATH=src
echo ============================================
echo   QA AI Platform - starting web server...
echo   Open http://localhost:8000 in your browser
echo   (Close this window or press Ctrl+C to stop)
echo ============================================
python -m uvicorn qa_agents.web.app:app --port 8000
pause

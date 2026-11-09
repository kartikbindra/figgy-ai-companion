@echo off
echo Starting Figgy System...
start "" "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" serve
timeout /t 2 /nobreak >nul
set PYTHONPATH=backend
start "" .venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000
echo Figgy Backend is running on http://localhost:8000
echo Opening Web Interface...
start "" client\web\index.html
pause

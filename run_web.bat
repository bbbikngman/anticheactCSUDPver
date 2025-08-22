@echo off
setlocal
REM Activate venv if exists
if exist venv_antifraud\Scripts\activate.bat (
  call venv_antifraud\Scripts\activate.bat
)

REM Ensure current dir is project root (this bat is at project root)
set PYTHONPATH=%CD%

REM Start uvicorn with reload on Win
python -m uvicorn whisper.web_server:app --reload --port 8000

endlocal


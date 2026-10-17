@echo off
setlocal

rem Every record lives in Postgres, so the server refuses to start without it.
rem A populated DATABASE_URL in .env counts: the application loads it itself.
if defined DATABASE_URL goto have_db
findstr /b /r "^DATABASE_URL=.." .env >nul 2>&1
if not errorlevel 1 goto have_db
echo DATABASE_URL is not set. Start a Postgres and put its URL in .env:
echo   docker run -d --name mps-postgres -e POSTGRES_USER=microplast -e POSTGRES_PASSWORD=microplast_dev_only -e POSTGRES_DB=microplast -p 5433:5432 postgres:17-alpine
echo   DATABASE_URL=postgresql://microplast:microplast_dev_only@127.0.0.1:5433/microplast
exit /b 1

:have_db
if not exist .venv (
  python -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

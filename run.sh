#!/usr/bin/env sh
set -eu

# Every record lives in Postgres, so the server refuses to start without it.
# .env counts as set: the application loads it itself.
if [ -z "${DATABASE_URL:-}" ] && ! grep -Eq '^DATABASE_URL=..*' .env 2>/dev/null; then
  echo "DATABASE_URL is not set. Start a Postgres and put its URL in .env:" >&2
  echo "  docker run -d --name mps-postgres -e POSTGRES_USER=microplast -e POSTGRES_PASSWORD=microplast_dev_only -e POSTGRES_DB=microplast -p 5433:5432 postgres:17-alpine" >&2
  echo "  echo 'DATABASE_URL=postgresql://microplast:microplast_dev_only@127.0.0.1:5433/microplast' >> .env" >&2
  exit 1
fi

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn backend.app.main:app --host "${HOST:-127.0.0.1}" --port "${PORT:-8000}"

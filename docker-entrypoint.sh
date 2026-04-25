#!/bin/sh
set -e

# Pasta de anexos (persistente quando houver volume em UPLOAD_FOLDER)
UPLOAD_DIR="${UPLOAD_FOLDER:-/data/gestorcontrato/uploads}"
mkdir -p "$UPLOAD_DIR"

# SQLAlchemy 2 não aceita postgres://; normaliza para postgresql+psycopg2://
if [ -n "$DATABASE_URL" ] && echo "$DATABASE_URL" | grep -q '^postgres://'; then
  export DATABASE_URL="postgresql+psycopg2://$(echo "$DATABASE_URL" | cut -c12-)"
fi
if [ -n "$DATABASE_URL" ] && echo "$DATABASE_URL" | grep -q '^postgresql://' && ! echo "$DATABASE_URL" | grep -q '^postgresql+'; then
  export DATABASE_URL="postgresql+psycopg2://$(echo "$DATABASE_URL" | cut -c14-)"
fi

# Migrações: aplica pendentes. Se falhar (ex.: tabelas já existem), marca DB como atualizado e segue
echo "Running database migrations..."
if ! flask db upgrade; then
  echo "Migration failed (tables may already exist). Stamping database to current revision..."
  flask db stamp head
fi

# Inicia o Gunicorn
exec gunicorn --bind "0.0.0.0:${PORT:-5000}" --workers 2 --threads 4 --timeout 120 run:app

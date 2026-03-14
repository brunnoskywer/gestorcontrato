#!/bin/sh
set -e

# SQLAlchemy 2 não aceita postgres://; normaliza para postgresql+psycopg2://
if [ -n "$DATABASE_URL" ] && echo "$DATABASE_URL" | grep -q '^postgres://'; then
  export DATABASE_URL="postgresql+psycopg2://$(echo "$DATABASE_URL" | cut -c12-)"
fi
if [ -n "$DATABASE_URL" ] && echo "$DATABASE_URL" | grep -q '^postgresql://' && ! echo "$DATABASE_URL" | grep -q '^postgresql+'; then
  export DATABASE_URL="postgresql+psycopg2://$(echo "$DATABASE_URL" | cut -c14-)"
fi

# Migrações: roda automaticamente antes de subir a aplicação
echo "Running database migrations..."
flask db upgrade

# Inicia o Gunicorn
exec gunicorn --bind "0.0.0.0:${PORT:-5000}" --workers 2 --threads 4 --timeout 120 run:app

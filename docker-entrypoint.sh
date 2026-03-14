#!/bin/sh
set -e

# Migrações: roda automaticamente antes de subir a aplicação
echo "Running database migrations..."
flask db upgrade

# Inicia o Gunicorn
exec gunicorn --bind "0.0.0.0:${PORT:-5000}" --workers 2 --threads 4 --timeout 120 run:app

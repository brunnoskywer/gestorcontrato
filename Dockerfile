# Build stage (optional: use multi-stage if you add build steps later)
FROM python:3.12-slim

# Evita criação de arquivos .pyc e buffer de stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Porta padrão (Coolify pode sobrescrever via PORT)
ENV PORT=5000

WORKDIR /app

# Dependências do sistema para psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código da aplicação
COPY . .

# Entrypoint: migrações + Gunicorn
ENV FLASK_APP=run.py
RUN chmod +x docker-entrypoint.sh
EXPOSE 5000
CMD ["./docker-entrypoint.sh"]

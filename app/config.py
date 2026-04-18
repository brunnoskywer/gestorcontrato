import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent

# Carrega variáveis de ambiente de um arquivo .env se existir
load_dotenv(BASE_DIR / ".env")


class Config:
    """Configuração padrão, já compatível com ambientes como Coolify."""

    # Segurança
    SECRET_KEY = os.getenv("SECRET_KEY", "change-this-in-production")

    # Banco de dados (PostgreSQL)
    # Coolify/Heroku usam postgres://; SQLAlchemy 2 só aceita postgresql+psycopg2
    _database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres:qwe123@localhost:5433/gestor_contrato",
    )
    if _database_url:
        if _database_url.startswith("postgres://"):
            _database_url = "postgresql+psycopg2://" + _database_url[11:]
        elif _database_url.startswith("postgresql://") and not _database_url.startswith("postgresql+"):
            _database_url = "postgresql+psycopg2://" + _database_url[13:]
    SQLALCHEMY_DATABASE_URI = _database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Evita "server closed the connection unexpectedly": testa conexão antes de usar e recicla após um tempo
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,   # testa se a conexão está viva antes de usar
        "pool_recycle": 300,      # recicla conexões após 5 min (evita timeout do servidor)
    }

    # Outros parâmetros de sistema
    APP_NAME = os.getenv("APP_NAME", "Contract Manager")
    ENVIRONMENT = os.getenv("FLASK_ENV", "development")
    # Anexos de contrato (PDF, imagens, etc.); em produção pode apontar para volume persistente.
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", str(BASE_DIR / "instance" / "uploads"))


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


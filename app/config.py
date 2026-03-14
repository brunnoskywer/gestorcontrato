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
    # Coolify/Heroku enviam postgres://; SQLAlchemy 2 exige postgresql://
    _database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres:qwe123@localhost:5433/gestor_contrato",
    )
    if _database_url and _database_url.startswith("postgres://"):
        _database_url = _database_url.replace("postgres://", "postgresql+psycopg2://", 1)
    SQLALCHEMY_DATABASE_URI = _database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Outros parâmetros de sistema
    APP_NAME = os.getenv("APP_NAME", "Contract Manager")
    ENVIRONMENT = os.getenv("FLASK_ENV", "development")


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


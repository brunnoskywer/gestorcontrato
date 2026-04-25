import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent

# Pasta de uploads em desenvolvimento (projeto).
_UPLOAD_FOLDER_DEV = str(BASE_DIR / "instance" / "uploads")
# Em Linux/produção: caminho estável para montar volume persistente (Docker/Coolify).
# Sem volume neste path, os arquivos ainda somem a cada novo container — configure o bind/volume no painel.
_UPLOAD_FOLDER_PROD = "/data/gestorcontrato/uploads"

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
    # Anexos (contratos, financeiro, etc.). Em desenvolvimento: pasta dentro do projeto.
    # Em produção use ProductionConfig (FLASK_ENV=production) ou defina UPLOAD_FOLDER explicitamente.
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", _UPLOAD_FOLDER_DEV)
    CEP_LOOKUP_URL = os.getenv("CEP_LOOKUP_URL", "https://buscarcep.com.br/")
    CEP_LOOKUP_KEY = os.getenv("CEP_LOOKUP_KEY", "1yDDoV7.XlC163D3JF/1dHfFYhQZhu.")
    CEP_LOOKUP_TIMEOUT_SECONDS = float(os.getenv("CEP_LOOKUP_TIMEOUT_SECONDS", "6"))
    OPENCNPJ_LOOKUP_URL = os.getenv("OPENCNPJ_LOOKUP_URL", "https://api.opencnpj.org")
    OPENCNPJ_LOOKUP_TIMEOUT_SECONDS = float(os.getenv("OPENCNPJ_LOOKUP_TIMEOUT_SECONDS", "6"))


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    # Padrão em servidores Linux: um único path para você mapear volume persistente no Coolify/Docker.
    # No Windows (produção rara), mantém instance/uploads a menos que UPLOAD_FOLDER esteja no .env.
    UPLOAD_FOLDER = os.getenv(
        "UPLOAD_FOLDER",
        _UPLOAD_FOLDER_PROD if os.name != "nt" else _UPLOAD_FOLDER_DEV,
    )


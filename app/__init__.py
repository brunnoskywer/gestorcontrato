from flask import Flask
from .extensions import db, migrate, login_manager
from .config import Config


def create_app(config_class: type[Config] | None = None) -> Flask:
    app = Flask(__name__)

    # Configuração
    config_obj = config_class() if config_class else Config()
    app.config.from_object(config_obj)

    # Extensões
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # Blueprints
    from .auth.routes import auth_bp
    from .main.routes import main_bp
    from .admin import admin_bp
    from .api.v1.routes import api_v1_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(api_v1_bp, url_prefix="/api/v1")

    from .filters import format_currency
    app.jinja_env.filters["format_currency"] = format_currency

    return app


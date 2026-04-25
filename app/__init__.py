import os
from pathlib import Path

from flask import Flask
from .extensions import db, migrate, login_manager
from .config import Config, ProductionConfig
from .admin.list_pagination import paginated_url


def create_app(config_class: type[Config] | None = None) -> Flask:
    app = Flask(__name__)

    # Configuração
    if config_class is None:
        config_class = (
            ProductionConfig
            if os.getenv("FLASK_ENV", "").strip().lower() == "production"
            else Config
        )
    config_obj = config_class()
    app.config.from_object(config_obj)

    # Garante diretório de uploads (volume montado ou pasta local).
    try:
        Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        app.logger.warning("Não foi possível criar UPLOAD_FOLDER (%s): %s", app.config.get("UPLOAD_FOLDER"), exc)

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

    from .filters import (
        attachment_file_on_disk,
        format_currency,
        finance_entry_stripe_class,
        finance_supplier_display,
        jinja_finalize,
        motoboy_status_label_pt,
        motoboy_status_stripe_class,
    )
    from .models.supplier import client_display_label

    app.jinja_env.finalize = jinja_finalize
    app.jinja_env.filters["format_currency"] = format_currency
    app.jinja_env.filters["motoboy_status_stripe_class"] = motoboy_status_stripe_class
    app.jinja_env.filters["motoboy_status_label_pt"] = motoboy_status_label_pt
    app.jinja_env.filters["finance_entry_stripe_class"] = finance_entry_stripe_class
    app.jinja_env.filters["attachment_file_on_disk"] = attachment_file_on_disk
    app.jinja_env.filters["finance_supplier_display"] = finance_supplier_display
    app.jinja_env.filters["client_display_label"] = client_display_label
    app.add_template_global(paginated_url)

    return app


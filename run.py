import os

from app import create_app


app = create_app()


if __name__ == "__main__":
    # Em desenvolvimento, ativa o reloader automático e debug
    debug = os.getenv("FLASK_ENV", "development") != "production"
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=debug)


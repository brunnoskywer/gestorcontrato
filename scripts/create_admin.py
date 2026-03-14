from pathlib import Path
import sys

# Garante que o diretório raiz do projeto esteja no PYTHONPATH,
# independentemente de onde o script for executado.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app  # type: ignore  # noqa: E402
from app.extensions import db  # type: ignore  # noqa: E402
from app.models import User  # type: ignore  # noqa: E402


def create_admin(email: str, name: str, password: str) -> None:
    app = create_app()

    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if user:
            print(f"User '{email}' already exists.")
            return

        user = User(email=email, name=name, is_admin=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        print(f"Admin user created: {email}")


if __name__ == "__main__":
    # Valores padrão — pode ajustar aqui se quiser
    email = "admin@example.com"
    name = "Admin"
    password = "admin123"
    create_admin(email, name, password)


param(
    [string]$AdminEmail = "admin@example.com",
    [string]$AdminName  = "Admin",
    [string]$AdminPassword = "admin123"
)

Write-Host "==> Ativando virtualenv (criando se necessário)..." -ForegroundColor Cyan
if (-not (Test-Path ".\.venv")) {
    python -m venv .venv
}
.\.venv\Scripts\activate

Write-Host "==> Instalando dependências..." -ForegroundColor Cyan
pip install -r requirements.txt

Write-Host "==> Configurando FLASK_APP..." -ForegroundColor Cyan
$env:FLASK_APP = "run.py"

Write-Host "==> Rodando migrações (db init/migrate/upgrade)..." -ForegroundColor Cyan
if (-not (Test-Path ".\migrations")) {
    flask db init
}
flask db migrate -m "initial"
flask db upgrade

Write-Host "==> Criando usuário admin (se não existir)..." -ForegroundColor Cyan
$script = @"
from app.extensions import db
from app.models import User

email = "$AdminEmail"
name = "$AdminName"
password = "$AdminPassword"

user = User.query.filter_by(email=email).first()
if not user:
    user = User(email=email, name=name, is_admin=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    print("Admin created:", email)
else:
    print("Admin already exists:", email)
"@

# Envia o script Python para a entrada padrão do interpretador
$script | python -

Write-Host ""
Write-Host "Pronto! Agora rode:  python .\run.py" -ForegroundColor Green
Write-Host "Login admin: $AdminEmail / $AdminPassword" -ForegroundColor Yellow


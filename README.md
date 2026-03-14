# Contract Manager Skeleton (Flask + PostgreSQL)

## Overview

This project is a skeleton for a contract management system built with **Flask**, **SQLAlchemy**, **PostgreSQL**, **Bootstrap 5** and ready for environment-based configuration (e.g. Coolify).

Entities (ORM models):
- User (authentication)
- Company
- Client
- Motoboy
- MotoboyContract
- ClientContract

## Running locally

1. Create and activate a virtualenv (optional but recommended).
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file based on `.env.example` and adjust `DATABASE_URL` and `SECRET_KEY` as needed.

4. Initialize the database (PostgreSQL must be running and accessible):

```bash
flask db init
flask db migrate -m "initial"
flask db upgrade
```

5. Run the application:

```bash
python run.py
```

Then access `http://localhost:5000`.


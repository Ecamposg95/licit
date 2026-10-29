# CLAUDE.md — Licit (licitaciones públicas · Grupo Dipromedic)

Plataforma para dar seguimiento a licitaciones públicas (IMSS, ISSSTE, SSA, estatales) en las que participa
Grupo Dipromedic (implantes de trauma y ortopedia). Stack Atlas: **FastAPI + SQLAlchemy + PostgreSQL** (`app/`)
y **React + Vite + TS + Tailwind + zustand** (`frontend/`), servido por el backend en prod. Deploy en **Railway**.

## Reglas
1. Commit/push solo cuando el usuario lo pida; trabajar en `feat/*` / `fix/*`.
2. **Sin Alembic.** Tablas nuevas: registrar el modelo en `app/models/__init__.py` (las crea `create_all`).
   Columnas nuevas en tablas existentes: agregar a `MIGRACIONES` en `scripts/railway_init.py` (corre en cada deploy).
3. PKs y FKs son UUID `String(36)`.
4. Enums se guardan como `String` con su `.value`; los schemas usan `use_enum_values=True`.

## Comandos
```bash
uv venv .venv && VIRTUAL_ENV=.venv uv pip install -r requirements.txt   # WSL: python3 no trae venv/pip, usar uv
.venv/bin/python scripts/railway_init.py      # crea DB + seed admin (ADMIN_EMAIL / ADMIN_PASSWORD)
.venv/bin/uvicorn app.main:app --reload       # :8000 · Swagger en /docs
.venv/bin/python -m pytest -q                 # SQLite
cd frontend && npm install && npm run dev     # :5173 (proxy /api → :8000)
cd frontend && npm run build                  # tsc && vite build
docker compose up -d                          # postgres:17 local
```

## Variables (Railway)
`DATABASE_URL` (referencia al Postgres), `SECRET_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `CORS_ORIGINS`.

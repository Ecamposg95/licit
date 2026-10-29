# Licit · Dipromedic · Demo

Demo comercial white label de una plataforma de licitaciones públicas para trauma y ortopedia. Recorrido:
radar de oportunidades → detalle y partidas → catálogo → matriz de requisitos → pendientes → borradores → ZIP.

> Los productos, precios, existencias, escenarios y documentos simulados son **ficticios** y están marcados
> como tales. Las tres referencias históricas conservan sus identificadores y enlaces oficiales reales.

## Arranque local

```bash
uv venv .venv && VIRTUAL_ENV=.venv uv pip install -r requirements.txt
cp .env.example .env            # define SESSION_SECRET y DEMO_USER_PASSWORD
docker compose up -d            # postgres:17
.venv/bin/alembic upgrade head
.venv/bin/python scripts/bootstrap.py
.venv/bin/uvicorn app.main:app --reload
cd frontend && npm install && npm run dev
```

Pruebas: `.venv/bin/python -m pytest -q` (añade `TEST_DATABASE_URL=postgresql://…` para correrlas contra Postgres).
Reinicio del demo: `python scripts/bootstrap.py --reset`, o «Reiniciar demo» en Operación (rol Administrador TI).

## Documentación

- Especificación: [`docs/spec/`](docs/spec/) (task pack, dossier y LEEME)
- Decisiones: [`docs/adr/`](docs/adr/)
- Avance: [`docs/BACKLOG.md`](docs/BACKLOG.md)
- Limitaciones: [`docs/LIMITACIONES.md`](docs/LIMITACIONES.md)
- Guía para agentes y despliegue: [`CLAUDE.md`](CLAUDE.md)
- API: `/docs` (Swagger) y `/openapi.json`

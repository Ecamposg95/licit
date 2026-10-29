# ADR-001 · Arquitectura del demo comercial

Estado: aceptado · 2026-10-28 · Decide: Emmanuel Campos

## Contexto

El task pack (§7) propone React + Vite, FastAPI + Pydantic, PostgreSQL + SQLAlchemy con Alembic, almacenamiento
S3 y un trabajador asíncrono, como monolito modular. El equipo usa por defecto el stack de Atlas (mismas piezas,
pero migraciones idempotentes sin Alembic y despliegue en Railway).

## Decisión

| Tema | Decisión | Motivo |
|---|---|---|
| Forma | Monolito modular: un servicio `web` (API + SPA) y, desde E2, un servicio `worker` con la misma imagen | El pack pide no distribuir servicios sin necesidad |
| Backend | FastAPI, Pydantic 2, SQLAlchemy 2, Python 3.11 | Stack Atlas y del pack |
| Frontend | React 18, Vite 5, TypeScript estricto, Tailwind 3, zustand | Stack Atlas y del pack |
| Base de datos | PostgreSQL 17 en Railway | — |
| Migraciones | **Alembic** (`alembic upgrade head` en cada arranque) | El pack exige migraciones reversibles. Se aparta del patrón Atlas (`railway_init.py`) a propósito |
| Cola de trabajos (E2) | Tabla en Postgres con `SELECT … FOR UPDATE SKIP LOCKED` | Evita operar Redis para un demo; reemplazable |
| Documentos (E2) | Railway Bucket (compatible con S3) | Binarios fuera de la base de datos |
| Búsqueda en vivo (E2) | Adaptador directo a DOF/SIDOF desde el servidor | Sin costo ni llave; Compras MX se investiga y, si bloquea, queda documentado con carga manual |
| IA | Ninguna en esta fase; interfaz `Extractor` con implementación manual/reglas | Decisión del usuario. Queda en el informe de limitaciones |
| Despliegue | Railway, Dockerfile multi-stage | Railway ya construye con Railpack, que ignora `nixpacks.toml` |
| Identidad | JWT con expiración (`SESSION_TTL_MINUTES`), bcrypt, 5 roles del pack con permisos granulares; una persona puede acumular roles | §3 |
| Multi-organización | `organization_id` en todo recurso y `get_owned()`; un recurso ajeno responde 404 | §8, aunque el demo tenga una sola organización |
| Auditoría | `audit_events` con actor, acción, recurso, antes, después y `correlation_id` | §7 y §13 |
| Errores | `{code, message, correlation_id, details}`; cabecera `X-Correlation-ID` | §9 |
| Identificadores | UUID; los datos de demo usan uuid5 del código del fixture para que el reinicio sea determinista | §1 «reinicio determinista» |

## Consecuencias

- Cambios de esquema: `alembic revision --autogenerate`, revisar el archivo y probar `upgrade`/`downgrade`.
  Las pruebas verifican el ciclo completo en SQLite y la suite corre contra Postgres con `TEST_DATABASE_URL`.
- `railway up` no debe ejecutarse desde `/mnt/c` (el CLI sube bytes nulos); ver CLAUDE.md.
- Planta y ERP sólo aparecen como integración futura en la arquitectura; no hay botones que simulen esas funciones.

"""Licit — demo comercial de licitaciones públicas (white label · Dipromedic · Demo)."""
import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import app.models  # noqa: F401  registra todas las tablas en Base.metadata
from app.core import config, errors
from app.routers import auth, catalog, documents, jobs as jobs_router, opportunities, resources
from app.services import jobs


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # El worker de trabajos corre en un hilo de este proceso; JOBS_WORKER=0 lo apaga (pruebas).
    if config.JOBS_WORKER:
        jobs.start_worker()
    yield
    # stop_worker espera hasta 10 s al trabajo en curso: fuera del event loop para no congelarlo.
    await asyncio.to_thread(jobs.stop_worker)


app = FastAPI(title="Licit · Dipromedic Demo API", version="1.0.0", lifespan=lifespan)

_cors = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Correlation-ID"],
)
errors.install(app)

app.include_router(auth.router)
app.include_router(opportunities.router)
app.include_router(resources.router)
app.include_router(catalog.router)
app.include_router(jobs_router.router)
app.include_router(documents.router)


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok", "commit": os.getenv("RAILWAY_GIT_COMMIT_SHA", "local")[:7]}


# ── SPA de React (frontend/dist) servida por el backend en prod ──────────────
_REACT_DIST = "frontend/dist"
if os.path.isdir(f"{_REACT_DIST}/assets"):
    app.mount("/assets", StaticFiles(directory=f"{_REACT_DIST}/assets"), name="react-assets")


@app.get("/{full_path:path}", include_in_schema=False)
def spa(full_path: str):
    if full_path.startswith("api/"):
        return JSONResponse(status_code=404, content={
            "code": "not_found", "message": "Ruta no encontrada",
            "correlation_id": errors.correlation_id_var.get(), "details": None})
    root = os.path.realpath(_REACT_DIST)
    candidate = os.path.realpath(os.path.join(root, full_path))
    # Sólo archivos dentro de dist/: bloquea ../ hacia el código del servidor.
    if full_path and candidate.startswith(root + os.sep) and os.path.isfile(candidate):
        return FileResponse(candidate)
    index = os.path.join(_REACT_DIST, "index.html")
    if os.path.isfile(index):
        return FileResponse(index)
    return {"detail": "Frontend no compilado. Corre `cd frontend && npm run build`."}

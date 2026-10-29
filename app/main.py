"""Licit — plataforma de licitaciones públicas para Grupo Dipromedic."""
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import app.models  # noqa: F401  registra todas las tablas en Base.metadata
from app.routers import auth, licitaciones

app = FastAPI(title="Licit · Dipromedic", version="0.1.0")

_cors = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(licitaciones.router)


@app.get("/health")
def health():
    return {"status": "ok", "commit": os.getenv("RAILWAY_GIT_COMMIT_SHA", "local")[:7]}


# ── SPA de React (frontend/dist) servida por el backend en prod ──────────────
_REACT_DIST = "frontend/dist"
if os.path.isdir(f"{_REACT_DIST}/assets"):
    app.mount("/assets", StaticFiles(directory=f"{_REACT_DIST}/assets"), name="react-assets")


@app.get("/{full_path:path}", include_in_schema=False)
def spa(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404)
    candidate = os.path.join(_REACT_DIST, full_path)
    if full_path and os.path.isfile(candidate):
        return FileResponse(candidate)
    index = os.path.join(_REACT_DIST, "index.html")
    if os.path.isfile(index):
        return FileResponse(index)
    return {"detail": "Frontend no compilado. Corre `cd frontend && npm run build`."}

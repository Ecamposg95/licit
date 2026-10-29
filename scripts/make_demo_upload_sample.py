#!/usr/bin/env python3
"""Genera `docs/demo/Ficha_tecnica_DEMO_para_carga.pdf`: el archivo de prueba (con marca DEMO) que el
presentador sube en el paso 7 del guion. Es determinista; se puede volver a generar cuando haga falta.

Uso: python scripts/make_demo_upload_sample.py [ruta_de_salida]
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services.demo_documents import UPLOAD_SAMPLE_NAME, render_upload_sample  # noqa: E402


def main(out: Path | None = None) -> Path:
    out = out or ROOT / "docs" / "demo" / UPLOAD_SAMPLE_NAME
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(render_upload_sample())
    return out


if __name__ == "__main__":
    target = main(Path(sys.argv[1]) if len(sys.argv) > 1 else None)
    print(f"Archivo de prueba generado: {os.path.relpath(target, ROOT)}")

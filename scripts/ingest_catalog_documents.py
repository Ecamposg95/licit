#!/usr/bin/env python3
"""Ingesta los PDFs del catálogo de Dipromedic y Traufix como documentos REAL (técnicas quirúrgicas, folletos).

Uso:
  python scripts/ingest_catalog_documents.py --local /ruta/a/docs/research/dipromedic/pdfs   # copias locales
  python scripts/ingest_catalog_documents.py --fetch                                          # descarga los que falten

Los PDFs propios se suben al almacenamiento configurado (OBJECT_STORAGE_* o STORAGE_DIR) con su SHA-256; los de otras
marcas solo se enlazan. Es idempotente: se puede repetir (por ejemplo, después de importar el catálogo de
productos para completar los vínculos).
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models import Organization  # noqa: E402
from app.services.catalog_documents import ingest_catalog_documents  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--local", type=Path, help="carpeta espejo de docs/research/dipromedic/pdfs")
    parser.add_argument("--fetch", action="store_true", help="descargar del sitio los PDFs propios sin copia local")
    args = parser.parse_args(argv)
    if args.local is not None and not args.local.is_dir():
        parser.error(f"La carpeta {args.local} no existe")

    with SessionLocal() as db:
        org = db.scalars(select(Organization).limit(1)).first()
        if org is None:
            print("No hay organización: corre primero scripts/bootstrap.py", file=sys.stderr)
            return 1
        result = ingest_catalog_documents(db, org.id, args.local, fetch=args.fetch)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

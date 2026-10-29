#!/usr/bin/env python3
"""Arranque en cada deploy, después de `alembic upgrade head`.

Crea organización, fuentes y usuarios (idempotente) y siembra el demo sólo si
no hay oportunidades. Para reiniciar el demo a voluntad: `python scripts/bootstrap.py --reset`.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal  # noqa: E402
from app.services.demo_seed import bootstrap, reset_demo  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        org = bootstrap(db)
        if "--reset" in sys.argv:
            print(reset_demo(db, org, actor_id=None))
            db.commit()
        print(f"✅ Organización lista: {org.name}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Operación de cuentas del beta. Se corre donde está la base (en Railway: `railway ssh --service web`).

    python scripts/cuentas.py listar
    python scripts/cuentas.py contrasena analista1@dipromedic.example   # pide la nueva contraseña
    python scripts/cuentas.py contrasena --demo                         # rota todas las cuentas demo
    python scripts/cuentas.py desactivar analista3@dipromedic.example
    python scripts/cuentas.py activar analista3@dipromedic.example
    python scripts/cuentas.py vence analista3@dipromedic.example 2026-11-30   # fin del día, hora CDMX
    python scripts/cuentas.py vence analista3@dipromedic.example nunca

La contraseña se lee de la terminal o de stdin, nunca de los argumentos (quedaría en el historial).
Cada cambio queda en la bitácora de auditoría.
"""
import argparse
import getpass
import os
import sys
from datetime import datetime, time
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core import config  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.services import accounts  # noqa: E402


def _read_password() -> str:
    if not sys.stdin.isatty():
        return sys.stdin.readline().rstrip("\n")
    first = getpass.getpass("Nueva contraseña: ")
    if getpass.getpass("Repítela: ") != first:
        raise accounts.AccountError("Las contraseñas no coinciden")
    return first


def _parse_expiry(value: str) -> datetime | None:
    if value.lower() == "nunca":
        return None
    if len(value) == 10:  # AAAA-MM-DD: vence al terminar ese día en la zona del demo
        day = datetime.strptime(value, "%Y-%m-%d").date()
        return datetime.combine(day, time(23, 59, 59), tzinfo=ZoneInfo(config.DISPLAY_TIMEZONE))
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise accounts.AccountError("Usa AAAA-MM-DD o una fecha ISO con zona (p. ej. 2026-11-30T18:00-06:00)")
    return parsed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Operación de cuentas del beta")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("listar")
    pw = sub.add_parser("contrasena")
    target = pw.add_mutually_exclusive_group(required=True)
    target.add_argument("email", nargs="?")
    target.add_argument("--demo", action="store_true", help="todas las cuentas demo")
    for name in ("desactivar", "activar"):
        sub.add_parser(name).add_argument("email")
    exp = sub.add_parser("vence")
    exp.add_argument("email")
    exp.add_argument("fecha", help="AAAA-MM-DD, ISO con zona o 'nunca'")
    args = parser.parse_args(argv)

    db = SessionLocal()
    try:
        if args.cmd == "listar":
            for r in accounts.list_accounts(db):
                estado = "activa" if r["is_active"] else "DESACTIVADA"
                print(f"{r['email']:<36} {estado:<12} vence: {r['expires_at'] or 'nunca':<26} {','.join(r['roles'])}")
            return 0
        if args.cmd == "contrasena":
            password = _read_password()
            if args.demo:
                print(f"Contraseña rotada en {accounts.set_demo_password(db, password)} cuentas demo")
            else:
                accounts.set_password(db, args.email, password)
                print(f"Contraseña cambiada: {args.email}")
            print("Las sesiones abiertas siguen vigentes hasta que expira su token; para cortarlas, rota SESSION_SECRET.")
        elif args.cmd == "desactivar":
            accounts.deactivate(db, args.email)
            print(f"Acceso retirado (también sesiones abiertas): {args.email}")
        elif args.cmd == "activar":
            accounts.activate(db, args.email)
            print(f"Acceso devuelto: {args.email}")
        elif args.cmd == "vence":
            when = _parse_expiry(args.fecha)
            accounts.set_expiry(db, args.email, when)
            print(f"Vencimiento de {args.email}: {when.isoformat() if when else 'nunca'}")
        db.commit()
        return 0
    except accounts.AccountError as exc:
        db.rollback()
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())

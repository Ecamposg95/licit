"""Captura respuestas reales de SIDOF como fixtures de prueba (tarea C1).

Es el único paso del frente C que toca la red. Hace exactamente las peticiones documentadas en
`docs/research/fuentes-licitaciones.md` §1.3–§1.4, una a la vez y con al menos 1 s entre ellas,
y guarda cada cuerpo tal cual llega (bytes sin tocar) en `tests/fixtures/sidof/`:

- `search_osteosintesis_2026.json`: POST /busqueda/CargaNotasAvanzadas/ («osteosintesis», 2026).
- `nota_5801639.json` y `nota_5797331.json`: GET /dof/sidof/notas/nota/{codNota} (servicio oficial).
- `search_zero.json`: la misma búsqueda con una palabra sin resultados («zzzxqv»).

Extras (más allá del brief, para probar notas irregulares con datos reales):
- `nota_5800141.json`: una nota con varios procedimientos (investigación §1.4).
- `nota_5800121.json`: convocante estatal con código de expediente de Compras MX.
- `nota_5799326.json`: aviso de fallo publicado en la sección de convocatorias.

Los archivos que ya existen no se vuelven a pedir (usar `--force` para recapturar).

Uso:
    .venv/bin/python scripts/capture_sidof_fixtures.py            # captura (red) y deriva la copia dañada
    .venv/bin/python scripts/capture_sidof_fixtures.py --derive-only   # solo rehace nota_mangled.json

`nota_mangled.json` NO es una captura: se deriva de `nota_5801639.json` con `derive_mangled()`
(sin fechas y con entidades HTML rotas) para probar que el parser tolera notas irregulares.
"""
import argparse
import json
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import httpx

BASE = "https://sidof.segob.gob.mx"
USER_AGENT = "LicitDemo/1.0 (+contacto Atlas Technologies)"
OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "sidof"
SPACING_S = 1.0


def search_form(term: str, date_from: date, date_to: date, start: int = 0, length: int = 100) -> dict:
    """Cuerpo del POST tal como lo arma `/assets/js/busqueda2.js` (investigación §1.3)."""
    return {
        "draw": "1",
        "columns[0][data]": "fecha",
        "columns[1][data]": "titulo",
        "columns[2][data]": "codOrgaUno",
        "columns[3][data]": "codOrgaDos",
        "order[0][column]": "0",
        "order[0][dir]": "desc",
        "start": str(start),
        "length": str(length),
        "tipoBus": "C",
        "textoBus": term,
        "fechaIni": date_from.strftime("%d-%m-%Y"),
        "fechaFin": date_to.strftime("%d-%m-%Y"),
        "idOrg": "TODOS",
        "codNotas": "",
        "sinonimos": "false",
        "tipoTexto": "Y",
    }


_PRIVATE_HOST = re.compile(rb"(https?:\\?/\\?/)(10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}"
                           rb"|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})")


def redact_internal_hosts(raw: bytes) -> bytes:
    """Sustituye por 0.0.0.0 las IP internas que SIDOF filtra en sus respuestas sin `messageCode`."""
    return _PRIVATE_HOST.sub(rb"\g<1>0.0.0.0", raw)


def derive_mangled(raw: bytes) -> bytes:
    """Copia deliberadamente dañada de una nota real: sin fechas y con entidades HTML rotas."""
    data = json.loads(raw)
    html = data["Nota"]["cadenaContenido"]
    gap = r"(?:\s|<[^>]*>)+"            # en el HTML real puede haber etiquetas dentro de una fecha
    months = r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|sep\s*tiembre|septiembre|octubre|noviembre|diciembre)"
    html = re.sub(r"\d{1,2}\s*/\s*\d{1,2}\s*/\s*\d{2,4}", "[fecha retirada]", html)
    html = re.sub(rf"\d{{1,2}}{gap}(de{gap})?{months}({gap}de)?{gap}\d{{4}}", "[fecha retirada]", html, flags=re.I)
    html = re.sub(r"\d{1,2}\s*:\s*\d\s*\d\s*(horas|hrs\.?|h)?", "[hora retirada]", html, flags=re.I)
    # Entidades rotas o desconocidas: sin punto y coma, numéricas inválidas y nombres inexistentes.
    html = html.replace("&nbsp;", "&nbsp").replace("ó", "&oacute").replace("é", "&#xE9").replace("á", "&#xZZ;")
    html = html.replace("</td>", "&bogus;</td>", 3)
    # Estructura rota: una fila sin cerrar y un párrafo final sin cerrar.
    html = html.replace("</td></tr>", "", 1)
    data["Nota"]["cadenaContenido"] = html + "<p>&#99999999; &amp &lt;sin cerrar"
    return json.dumps(data, ensure_ascii=False, indent=1).encode("utf-8")


def capture(force: bool = False) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    today = date.today()
    year_start = date(today.year, 1, 1)
    plan = [
        ("search_osteosintesis_2026.json", "POST", f"{BASE}/busqueda/CargaNotasAvanzadas/",
         search_form("osteosintesis", year_start, today)),
        ("nota_5801639.json", "GET", f"{BASE}/dof/sidof/notas/nota/5801639", None),
        ("nota_5797331.json", "GET", f"{BASE}/dof/sidof/notas/nota/5797331", None),
        ("search_zero.json", "POST", f"{BASE}/busqueda/CargaNotasAvanzadas/",
         search_form("zzzxqv", year_start, today)),
        ("nota_5800141.json", "GET", f"{BASE}/dof/sidof/notas/nota/5800141", None),
        ("nota_5800121.json", "GET", f"{BASE}/dof/sidof/notas/nota/5800121", None),
        ("nota_5799326.json", "GET", f"{BASE}/dof/sidof/notas/nota/5799326", None),
    ]
    if not force:
        plan = [item for item in plan if not (OUT / item[0]).exists()]
    log_path = OUT / "capture_log.json"
    log = json.loads(log_path.read_text(encoding="utf-8")) if log_path.exists() else []
    headers = {"User-Agent": USER_AGENT, "X-Requested-With": "XMLHttpRequest"}
    with httpx.Client(headers=headers, timeout=httpx.Timeout(20.0, connect=10.0)) as http:
        for i, (name, method, url, form) in enumerate(plan):
            if i:
                time.sleep(SPACING_S)
            started = time.monotonic()
            r = http.request(method, url, data=form) if form else http.request(method, url)
            elapsed = time.monotonic() - started
            # Único cambio a lo capturado: se ocultan IP internas del backend de SIDOF (ver README).
            (OUT / name).write_bytes(redact_internal_hosts(r.content))
            log.append({"file": name, "method": method, "url": url, "status": r.status_code,
                        "bytes": len(r.content), "seconds": round(elapsed, 2),
                        "form": form, "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
            print(f"{name}: HTTP {r.status_code}, {len(r.content)} bytes, {elapsed:.2f} s")
            if r.status_code != 200 or not r.content:
                sys.exit(f"Respuesta inesperada para {name}; no se completó la captura.")
    log_path.write_text(json.dumps(log, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--derive-only", action="store_true", help="No usa la red; solo rehace nota_mangled.json")
    parser.add_argument("--force", action="store_true", help="Vuelve a pedir también los archivos existentes")
    args = parser.parse_args()
    if not args.derive_only:
        capture(force=args.force)
    (OUT / "nota_mangled.json").write_bytes(derive_mangled((OUT / "nota_5801639.json").read_bytes()))
    print("nota_mangled.json derivada de nota_5801639.json")


if __name__ == "__main__":
    main()

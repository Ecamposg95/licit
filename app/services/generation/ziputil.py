"""ZIP reproducible: python-docx y openpyxl sellan cada entrada con la hora del reloj; aquí se fija otra."""
import io
import zipfile
from collections.abc import Callable
from datetime import datetime, timezone

DateTime = tuple[int, int, int, int, int, int]


def zip_date(moment: datetime | str) -> DateTime:
    dt = datetime.fromisoformat(moment) if isinstance(moment, str) else moment
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return (max(dt.year, 1980), dt.month, dt.day, dt.hour, dt.minute, dt.second)


Transforms = dict[str, Callable[[bytes], bytes]]


def normalize_zip(data: bytes, date_time: DateTime, transforms: Transforms | None = None) -> bytes:
    """Reescribe el ZIP con la misma lista de entradas, el mismo orden y una fecha fija en todas.

    `transforms` permite corregir el contenido de entradas concretas (p. ej. la fecha de modificación que openpyxl
    escribe con el reloj al guardar)."""
    transforms = transforms or {}
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as src, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            fixed = zipfile.ZipInfo(info.filename, date_time=date_time)
            fixed.compress_type = zipfile.ZIP_DEFLATED
            fixed.external_attr = info.external_attr
            content = src.read(info.filename)
            if info.filename in transforms:
                content = transforms[info.filename](content)
            dst.writestr(fixed, content)
    return out.getvalue()

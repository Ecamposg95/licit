"""Estado derivado de una oportunidad (§6 Vigencia).

Separa el estado reportado por la fuente (`reported_status`), el grado de
verificación (`verification_status`) y este estado derivado. Funciones puras:
reciben `now` explícito para poder probar el reloj posterior a la fecha límite.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.models.base import DataKind
from app.models.opportunity import VerificationStatus


@dataclass(frozen=True)
class DerivedStatus:
    code: str
    label: str
    reason: str


def _aware(dt: datetime) -> datetime:
    # SQLite devuelve datetimes naive; todo se guarda en UTC.
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def derive_status(opp, now: datetime, ttl_hours: int) -> DerivedStatus:
    if opp.data_kind == DataKind.SYNTHETIC.value:
        return DerivedStatus("simulada", "Escenario simulado",
                             "Datos ficticios con fechas relativas a la fecha base del demo.")

    if opp.verification_status == VerificationStatus.FUENTE_INACCESIBLE.value:
        return DerivedStatus("fuente_inaccesible", "Fuente inaccesible",
                             "La última consulta a la fuente falló; no implica ausencia de procedimiento.")

    if opp.submission_at is None:
        return DerivedStatus("por_verificar", "Por verificar", "No hay fecha de presentación verificable.")

    if _aware(opp.submission_at) <= now:
        result = opp.result or "desconocido"
        return DerivedStatus("fecha_transcurrida", "Fecha de presentación transcurrida",
                             f"Resultado del procedimiento: {result}.")

    if opp.data_kind == DataKind.HISTORICAL.value:
        return DerivedStatus("historica", "Referencia histórica", "Registro histórico; no es una oportunidad abierta.")

    checked = opp.last_checked_at
    if checked is None or now - _aware(checked) > timedelta(hours=ttl_hours):
        return DerivedStatus("desactualizada", "Desactualizada",
                             f"Sin comprobación en las últimas {ttl_hours} h; solicita nueva consulta.")

    if opp.verification_status == VerificationStatus.VERIFICADA.value:
        return DerivedStatus("abierta_verificada", "Abierta verificada",
                             "Fuente oficial accesible y fecha de presentación futura.")

    return DerivedStatus("por_verificar", "Por verificar", "Falta comprobar bases o fechas en la fuente oficial.")

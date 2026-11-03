"""Tablero «Hoy» (T17): qué llegó, de quién es y qué vence. Solo cuenta datos REAL; las tareas propias incluyen demo."""
from datetime import datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DataKind, Opportunity, SavedSearch, Task, User
from app.routers.opportunities import _open_counts, _row, task_out
from app.schemas.v1 import UserRef
from app.services import saved_searches, sweeps
from app.sources.dates_es import MX

REVISIT_AFTER = timedelta(minutes=30)
KEY_DATES_DAYS = 14
SUBMITTING_DAYS = 7
_OPEN_TASK = ("pendiente", "en_progreso")
_REAL = DataKind.REAL.value


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def touch_visit(user: User, now: datetime) -> datetime | None:
    """Registra la visita y devuelve la marca contra la que se calcula «nueva desde tu visita».

    Una recarga dentro de `REVISIT_AFTER` no mueve nada, para que la lista de nuevas no se vacíe al refrescar.
    """
    seen = _aware(user.hoy_seen_at)
    if seen is None:
        user.hoy_prev_seen_at, user.hoy_seen_at = None, now
    elif now - seen > REVISIT_AFTER:
        user.hoy_prev_seen_at, user.hoy_seen_at = seen, now
    return _aware(user.hoy_prev_seen_at)


def badge_count(db: Session, user: User) -> int:
    seen = _aware(user.hoy_seen_at)
    n = 0
    for created in db.scalars(select(Opportunity.created_at).where(
            Opportunity.organization_id == user.organization_id, Opportunity.data_kind == _REAL,
            Opportunity.triage_status == "nueva")):
        if seen is None or _aware(created) > seen:
            n += 1
    return n


def _warning(last) -> str | None:
    if last is None or last.status not in ("failed", "partial"):
        return None
    errors = last.errors or []
    detail = (errors[0].get("message") if errors and isinstance(errors[0], dict) else None) or "sin detalle"
    head = "El último barrido falló" if last.status == "failed" else "El último barrido quedó incompleto"
    return f"{head}: {detail.rstrip('.')}. Las cifras pueden estar incompletas."


def dashboard(db: Session, user: User, now: datetime, scope: Literal["mine", "team"]) -> dict:
    """Arma el tablero. Se llama después de `touch_visit`: la marca de «nueva desde tu visita» es `hoy_prev_seen_at`."""
    last_visit = _aware(user.hoy_prev_seen_at)
    org = user.organization_id
    now = _aware(now)
    today = now.astimezone(MX).date()

    # Nuevas (REAL, sin clasificar), más recientes primero.
    nuevas = list(db.scalars(select(Opportunity).where(
        Opportunity.organization_id == org, Opportunity.data_kind == _REAL, Opportunity.triage_status == "nueva")
        .order_by(Opportunity.created_at.desc(), Opportunity.id)).unique())
    seguidas = list(db.scalars(select(Opportunity).where(
        Opportunity.organization_id == org, Opportunity.data_kind == _REAL, Opportunity.triage_status == "siguiendo")
        ).unique())
    real_created = list(db.scalars(select(Opportunity.created_at).where(
        Opportunity.organization_id == org, Opportunity.data_kind == _REAL)))

    terr = saved_searches.territory(db, org, nuevas)
    counts = _open_counts(db, [o.id for o in nuevas])
    users = {u.id: u for u in db.scalars(select(User).where(User.organization_id == org))}

    new_items = []
    for o in nuevas:
        matched = terr.get(o.id, [])
        created = _aware(o.created_at)
        new_items.append({
            **_row(o, counts.get(o.id, 0), now),
            "is_new_since_visit": last_visit is None or created > last_visit,
            "matched": [{"id": s.id, "name": s.name,
                         "owner": UserRef.model_validate(users[s.user_id]) if s.user_id in users else None}
                        for s in matched],
            "mine": any(s.user_id == user.id for s in matched),
            "in_territory": bool(matched),
        })
    unassigned = [i for i in new_items if not i["in_territory"]]

    # Fechas clave de lo que se sigue (próximos 14 días).
    pool = [o for o in seguidas if scope == "team" or o.owner_id == user.id]
    horizon = now + timedelta(days=KEY_DATES_DAYS)
    dates = []
    for o in pool:
        for kind, at in (("questions", o.questions_at), ("submission", o.submission_at), ("ruling", o.ruling_at)):
            at = _aware(at)
            if at is not None and now <= at <= horizon:
                dates.append((at, o, kind))
    dates.sort(key=lambda d: (d[0], d[1].id, d[2]))
    pool_counts = _open_counts(db, list({o.id for _, o, _ in dates}))
    key_dates = [{"opportunity": _row(o, pool_counts.get(o.id, 0), now), "kind": kind, "at": at}
                 for at, o, kind in dates]

    submitting = sum(1 for o in pool if (s := _aware(o.submission_at)) is not None
                     and now <= s <= now + timedelta(days=SUBMITTING_DAYS))

    # Tareas propias abiertas (todas las data_kind); el KPI cuenta solo REAL.
    tasks = list(db.scalars(select(Task).where(
        Task.organization_id == org, Task.assignee_id == user.id, Task.status.in_(_OPEN_TASK))).unique())
    tasks.sort(key=lambda t: (t.due_date is None, t.due_date or today, t.code or "", t.id))
    overdue = sum(1 for t in tasks if t.data_kind == _REAL and t.due_date is not None and t.due_date < today)

    state = sweeps.today_state(db, org, now)
    last = state["last"]
    mine_unclassified = sum(1 for i in new_items if i["mine"])

    return {
        "kpis": {
            "new_24h": sum(1 for c in real_created if _aware(c) >= now - timedelta(hours=24)),
            "unclassified": len(new_items),
            "unclassified_mine": mine_unclassified,
            "submitting_7d": submitting,
            "my_overdue_tasks": overdue,
        },
        "kpis_warning": _warning(last),
        "sweep": {"last": sweeps.serialize(db, last) if last else None,
                  "scheduled_pending": state["scheduled_pending"]},
        "new_items": new_items,
        "unassigned": unassigned,
        "key_dates": key_dates,
        "my_tasks": [task_out(t) for t in tasks],
        "scope": scope,
        "last_visit": last_visit,
    }

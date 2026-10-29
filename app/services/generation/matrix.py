"""Matriz de cumplimiento en filas planas: la comparten el DOCX, el CSV y el XLSX para que digan lo mismo."""
from app.services.generation import formatting as fmt
from app.services.generation.formatting import pending
from app.services.matching import RESULT_LABELS

COLUMNS = ["Código", "Partida", "Requisito", "Tipo", "Obligatorio", "Estado", "Motivo del estado",
           "Evidencia vinculada", "Evaluación técnica automática", "Siguiente acción", "Responsable",
           "Fecha límite", "Procedencia del dato"]


def evidence_lines(req: dict) -> list[str]:
    lines = []
    for e in req["evidence"]:
        page = f", pág. {e['page']}" if e["page"] else ""
        lines.append(f"{e['document_code'] or 's/c'} · {e['document_title']}{page} "
                     f"({fmt.label(fmt.EVIDENCE_DECISION_LABEL, e['decision'])})")
    return lines


def assessment_lines(assessments: list[dict]) -> list[str]:
    if not assessments:
        return ["Sin evaluación técnica"]
    lines = []
    for a in assessments:
        line = f"{fmt.label(RESULT_LABELS, a['result'])}: {a['explanation']}"
        if a["catalog_value"]:
            line += f" · Catálogo: {a['catalog_value']}"
        if a["source_text"]:
            line += f" · Cita: «{a['source_text']}»"
        lines.append(line)
    return lines


def next_action(req: dict) -> str | None:
    if req["next_action"]:
        return req["next_action"]
    task = req["open_task"]
    return f"Tarea {task['code'] or 's/c'} ({task['status'].replace('_', ' ')})" if task else None


def requirement_text(req: dict) -> str:
    """El texto del requisito y, si compara un atributo, lo exigido («igual a 6 orificios»)."""
    if req["attribute"] and req["expected_value"]:
        op = fmt.label(fmt.OPERATOR_LABEL, req["operator"], "igual a")
        unit = f" {req['unit']}" if req["unit"] else ""
        return f"{req['text']} ({op} {req['expected_value']}{unit})"
    return req["text"]


def mandatory_text(req: dict) -> str:
    return {True: "Sí", False: "No", None: "Por determinar"}[req["mandatory"]]


def matrix_rows(snapshot: dict) -> list[list[str]]:
    """Una fila de texto por requisito; los datos que faltan en un requisito abierto llevan [PENDIENTE: …]."""
    rows = []
    for r in snapshot["requirements"]:
        task = r["open_task"] or {}
        evidence = evidence_lines(r) or ([pending("evidencia vinculada")] if r["open"] else ["—"])
        owner = task.get("assignee") or r["reviewer"]
        due = task.get("due_date") or r["due_date"]
        rows.append([
            r["code"] or "s/c", f"Partida {r['lot']}" if r["lot"] else "General", requirement_text(r),
            fmt.label(fmt.REQ_TYPE_LABEL, r["req_type"], "—"), mandatory_text(r),
            fmt.label(fmt.STATUS_LABEL, r["status"]), r["status_reason"] or "",
            "\n".join(evidence), "\n".join(assessment_lines(r["assessments"])), next_action(r) or "—",
            owner or (pending("responsable") if r["open"] else "—"),
            fmt.long_date(due) or (pending("fecha límite") if r["open"] else "—"),
            fmt.label(fmt.DATA_KIND_LABEL, r["data_kind"]),
        ])
    return rows

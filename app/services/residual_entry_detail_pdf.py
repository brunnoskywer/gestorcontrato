"""PDF de detalhamento do cálculo de lançamento residual de motoboy."""
from __future__ import annotations

import json
from io import BytesIO
from typing import Any

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
except ImportError:  # pragma: no cover
    A4 = None
    canvas = None


def _fmt_br(value: Any) -> str:
    try:
        n = float(value or 0)
    except (TypeError, ValueError):
        n = 0.0
    return f"{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def build_residual_entry_detail_pdf(snapshot: dict[str, Any]) -> bytes:
    if A4 is None or canvas is None:  # pragma: no cover
        raise RuntimeError("reportlab não está instalado no ambiente.")
    buf = BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    y = h - 48
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(40, y, "Detalhamento — Residual motoboy")
    y -= 22
    pdf.setFont("Helvetica", 10)
    period = snapshot.get("period_label") or "-"
    pdf.drawString(40, y, f"Referência: {period}")
    y -= 14
    pdf.drawString(40, y, f"Contrato motoboy: #{snapshot.get('contract_id', '-')}")
    y -= 14
    pdf.drawString(40, y, f"Motoboy: {snapshot.get('motoboy_name', '-')}")
    y -= 14
    cli = snapshot.get("client_name") or "-"
    pdf.drawString(40, y, f"Cliente (contrato): {cli}")
    y -= 22

    def line(label: str, value: str):
        nonlocal y
        if y < 72:
            pdf.showPage()
            y = h - 48
            pdf.setFont("Helvetica", 10)
        pdf.drawString(40, y, label)
        pdf.drawRightString(w - 40, y, value)
        y -= 14

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(40, y, "Composição do valor")
    y -= 16
    pdf.setFont("Helvetica", 10)
    line("Base (prestação + premiação conforme regra)", f"R$ {_fmt_br(snapshot.get('gross_amount'))}")
    if snapshot.get("has_absences"):
        line("Observação", "Houve falta(s) no mês — premiação zerada na base.")
    line("Desconto por valor de falta(s)", f"- R$ {_fmt_br(snapshot.get('missing_total'))}")
    line("Subtotal após faltas", f"R$ {_fmt_br(snapshot.get('after_missing'))}")

    y -= 6
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(40, y, "Pagamentos quitados no mês (abatimento por natureza)")
    y -= 14
    pdf.setFont("Helvetica", 9)
    for row in snapshot.get("paid_by_nature") or []:
        nm = row.get("name") or "-"
        am = _fmt_br(row.get("amount"))
        line(f"  {nm}", f"- R$ {am}")

    excluded = snapshot.get("paid_excluded_residual_nature") or snapshot.get(
        "paid_excluded_discount_nature"
    ) or []
    if excluded:
        y -= 4
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(
            40,
            y,
            "Naturezas marcadas como 'Não considera para abatimento?' (não abatem o residual)",
        )
        y -= 12
        pdf.setFont("Helvetica", 9)
        for row in excluded:
            nm = row.get("name") or "-"
            am = _fmt_br(row.get("amount"))
            line(f"  {nm} (ignorado)", f"R$ {am}")

    y -= 10
    pdf.setFont("Helvetica-Bold", 11)
    line("Valor líquido (residual)", f"R$ {_fmt_br(snapshot.get('net_amount'))}")

    pdf.showPage()
    pdf.save()
    return buf.getvalue()


def parse_residual_snapshot_json(raw: str | None) -> dict[str, Any] | None:
    if not raw or not str(raw).strip():
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None

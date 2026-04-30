"""PDF de detalhamento do cálculo de lançamento residual de motoboy."""
from __future__ import annotations

import json
from io import BytesIO
from datetime import datetime
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


def _parse_br_date(value: Any) -> datetime:
    raw = str(value or "").strip()
    try:
        return datetime.strptime(raw, "%d/%m/%Y")
    except ValueError:
        return datetime.min


def _fmt_contract_start_date(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "-"
    try:
        return datetime.fromisoformat(raw).strftime("%d/%m/%Y")
    except ValueError:
        return raw[:10]


def build_residual_entry_detail_pdf(
    snapshot: dict[str, Any], detail_mode: str = "synthetic"
) -> bytes:
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
    contract_start = _fmt_contract_start_date(snapshot.get("contract_start_date"))
    pdf.drawString(40, y, f"Início do contrato: {contract_start}")
    y -= 14
    pdf.drawString(40, y, f"Motoboy: {snapshot.get('motoboy_name', '-')}")
    y -= 14
    cli = snapshot.get("client_name") or "-"
    pdf.drawString(40, y, f"Cliente (contrato): {cli}")
    y -= 22

    detail_mode = (detail_mode or "synthetic").strip().lower()
    if detail_mode not in ("synthetic", "analytic"):
        detail_mode = "synthetic"

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
    # Exibe somente o valor base já ajustado por dias trabalhados (x/30),
    # sem linhas intermediárias de desconto/subtotal.
    abs_n = snapshot.get("absence_count")
    worked_days_label = None
    if abs_n is not None:
        try:
            abs_count = max(0, int(abs_n))
        except (TypeError, ValueError):
            abs_count = 0
        worked_days = max(0, 30 - abs_count)
        worked_days_label = f"({worked_days}/30)"
    if worked_days_label:
        base_lbl = f"Valor base {worked_days_label}"
    else:
        base_lbl = "Valor base"
    line(base_lbl, f"R$ {_fmt_br(snapshot.get('after_missing'))}")

    y -= 6
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(40, y, "Pagamentos quitados no mês (abatimento por natureza)")
    y -= 14
    pdf.setFont("Helvetica", 9)
    for row in snapshot.get("paid_by_nature") or []:
        nm = row.get("name") or "-"
        am = _fmt_br(row.get("amount"))
        line(f"  {nm}", f"- R$ {am}")

    if detail_mode == "analytic":
        y -= 4
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(40, y, "Extrato analítico de pagamentos quitados no mês")
        y -= 12
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(44, y, "Data")
        pdf.drawString(130, y, "Natureza")
        pdf.drawRightString(w - 40, y, "Valor")
        pdf.line(40, y - 2, w - 40, y - 2)
        y -= 12
        pdf.setFont("Helvetica", 9)
        paid_entries = snapshot.get("paid_entries") or []
        paid_entries = [r for r in paid_entries if not r.get("excluded_residual")]
        paid_entries.sort(key=lambda r: _parse_br_date(r.get("date")))
        if paid_entries:
            for row in paid_entries:
                if y < 72:
                    pdf.showPage()
                    y = h - 48
                    pdf.setFont("Helvetica-Bold", 9)
                    pdf.drawString(44, y, "Data")
                    pdf.drawString(130, y, "Natureza")
                    pdf.drawRightString(w - 40, y, "Valor")
                    pdf.line(40, y - 2, w - 40, y - 2)
                    y -= 12
                    pdf.setFont("Helvetica", 9)
                dt = str(row.get("date") or "-")
                nat = str(row.get("nature") or "-")
                amt = _fmt_br(row.get("amount"))
                pdf.drawString(44, y, dt[:10])
                pdf.drawString(130, y, nat[:46])
                pdf.drawRightString(w - 40, y, f"R$ {amt}")
                pdf.line(40, y - 2, w - 40, y - 2)
                y -= 12
        else:
            line("Sem extrato por data no snapshot", "-")

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

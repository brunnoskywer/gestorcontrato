"""Geração de PDF do instrumento de distrato (rescisão) do contrato de motoboy."""
from __future__ import annotations

import re
from datetime import date
from io import BytesIO
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models import Company, Contract

from app.models.supplier import client_display_label
from app.utils import format_address_line

from app.services.motoboy_contract_pdf import _MONTH_NAMES, _format_doc, _fmt_money_br

try:
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
except ImportError:  # pragma: no cover
    A4 = None
    TA_CENTER = TA_JUSTIFY = TA_LEFT = None
    ParagraphStyle = getSampleStyleSheet = None
    Paragraph = SimpleDocTemplate = Spacer = None


def _draw_page_footer(pdf_canvas, doc) -> None:
    pdf_canvas.setFont("Helvetica", 8)
    pdf_canvas.drawRightString(A4[0] - 35, 26, f"Página {pdf_canvas.getPageNumber()}")


def _highlight_roles(text: str) -> str:
    if not text:
        return text
    out = text.replace("CONTRATANTE", "<b>CONTRATANTE</b>")
    out = out.replace("CONTRATADA", "<b>CONTRATADA</b>")
    return out


def build_motoboy_distrato_pdf(
    contract: "Contract", company: "Company", document_date: date
) -> bytes:
    """PDF de distrato. `contract.end_date` deve estar preenchida (data efetiva da rescisão)."""
    if (
        A4 is None
        or SimpleDocTemplate is None
        or Paragraph is None
        or Spacer is None
        or ParagraphStyle is None
        or getSampleStyleSheet is None
    ):  # pragma: no cover
        raise RuntimeError("reportlab não está instalado no ambiente.")
    if contract.end_date is None:
        raise ValueError("Contrato sem data de distrato.")

    supplier = contract.supplier
    company_name = (company.legal_name or "").strip() or "-"
    company_address = (
        format_address_line(
            company.street,
            company.neighborhood,
            company.city,
            company.state,
            complement=company.address,
        ).strip()
        or (company.address or "").strip()
        or "-"
    )
    company_cnpj = _format_doc(company.cnpj)

    contractor_name = (supplier.name if supplier else "").strip() or "-"
    contractor_address = (
        format_address_line(
            supplier.street,
            supplier.neighborhood,
            supplier.city,
            supplier.state,
            complement=supplier.address,
        ).strip()
        or (supplier.address if supplier else "").strip()
        or "-"
    )
    contractor_cnpj = _format_doc(
        (supplier.document_secondary if supplier else None)
        or (supplier.document if supplier else None)
    )

    client_label = (
        client_display_label(contract.other_supplier) if contract.other_supplier else "-"
    )
    start_br = contract.start_date.strftime("%d/%m/%Y") if contract.start_date else "-"
    end_br = contract.end_date.strftime("%d/%m/%Y")
    monthly_value = _fmt_money_br(contract.service_value or 0)

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=42,
        rightMargin=42,
        topMargin=42,
        bottomMargin=38,
        title=f"Distrato Motoboy #{contract.id}",
    )

    styles = getSampleStyleSheet()
    style_title = ParagraphStyle(
        "distratoTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        alignment=TA_CENTER,
        leading=15,
        spaceAfter=4,
    )
    style_subtitle = ParagraphStyle(
        "distratoSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        alignment=TA_CENTER,
        leading=13,
        spaceAfter=12,
    )
    style_intro = ParagraphStyle(
        "distratoIntro",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        alignment=TA_JUSTIFY,
        firstLineIndent=22,
        spaceAfter=8,
    )
    style_clause = ParagraphStyle(
        "distratoClause",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=14,
        alignment=TA_LEFT,
        spaceBefore=5,
        spaceAfter=3,
    )
    style_body = ParagraphStyle(
        "distratoBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=13.5,
        alignment=TA_JUSTIFY,
        firstLineIndent=20,
        spaceAfter=3,
    )
    style_alinea = ParagraphStyle(
        "distratoAlinea",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=13.5,
        alignment=TA_JUSTIFY,
        leftIndent=18,
        firstLineIndent=-10,
        spaceAfter=2,
    )
    style_signature_label = ParagraphStyle(
        "distratoSigLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        spaceBefore=4,
        spaceAfter=1,
    )
    style_signature_text = ParagraphStyle(
        "distratoSigText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=13,
        spaceAfter=3,
    )

    story = []
    story.append(Paragraph("INSTRUMENTO PARTICULAR DE DISTRATO", style_title))
    story.append(
        Paragraph(
            "(Rescisão amigável do contrato de prestação de serviços de motofrete)",
            style_subtitle,
        )
    )

    intro = (
        "Por este instrumento particular, de um lado, como <b>CONTRATANTE</b>, "
        f"<b>{company_name}</b>, com sede em {company_address}, inscrita no CNPJ sob o nº <b>{company_cnpj}</b>; "
        "e, de outro lado, como <b>CONTRATADA</b>, "
        f"<b>{contractor_name}</b>, com sede em {contractor_address}, inscrita no CNPJ sob o nº "
        f"<b>{contractor_cnpj}</b>, qualificadas como na celebração do contrato de prestação de serviços "
        f"referente à prestação de serviços de entregas/motofrete em favor do cliente <b>{client_label}</b>, "
        f"têm entre si justo e contratado o presente distrato, nos termos a seguir."
    )
    story.append(Paragraph(intro, style_intro))

    sections = [
        (
            "CLÁUSULA 1ª - DO OBJETO",
            [
                f"As partes reconhecem a existência do contrato de prestação de serviços iniciado em {start_br}, "
                "com os encargos e condições então ajustados, inclusive quanto ao valor mensal da prestação "
                f"de R$ {monthly_value} (quando aplicável ao período), e pelo presente instrumento resolvem "
                "promover sua rescisão de forma amigável."
            ],
        ),
        (
            "CLÁUSULA 2ª - DA DATA DE EFICÁCIA",
            [
                f"A rescisão do contrato produz efeitos a partir de <b>{end_br}</b> (data de distrato registrada "
                "no sistema contratual), independentemente da data de assinatura deste instrumento, salvo "
                "disposição escrita diversa acordada entre as partes."
            ],
        ),
        (
            "CLÁUSULA 3ª - DAS OBRIGAÇÕES PENDENTES",
            [
                "As partes declaram que cumprirão as obrigações eventualmente pendentes até a data de eficácia "
                "da rescisão, inclusive quanto a valores, entregas e documentos, conforme o contrato originário "
                "e a legislação aplicável.",
                "a) A rescisão amigável não implica renúncia a créditos ou débitos já constituídos até a data de eficácia;",
                "b) Eventuais ajustes financeiros complementares serão tratados em documento ou lançamentos próprios, quando cabíveis.",
            ],
        ),
        (
            "CLÁUSULA 4ª - DA INEXISTÊNCIA DE VÍNCULO EMPREGATÍCIO",
            [
                "Mantém-se a natureza civil da relação contratual, sem vínculo empregatício entre as partes, "
                "nos termos já declinados no contrato principal."
            ],
        ),
        (
            "CLÁUSULA 5ª - DAS DISPOSIÇÕES FINAIS",
            [
                "Este distrato substitui, quanto à rescisão, eventuais entendimentos verbais sobre o encerramento, "
                "prevalecendo o escrito quanto à data de eficácia acima indicada.",
                "As partes elegem o foro da comarca de Fortaleza/CE para dirimir questões decorrentes deste instrumento, "
                "com renúncia de qualquer outro, por mais privilegiado que seja.",
            ],
        ),
    ]

    for title, items in sections:
        story.append(Paragraph(title, style_clause))
        for line in items:
            line_fmt = _highlight_roles(line)
            if re.match(r"^[a-z]\)", line.strip(), re.IGNORECASE):
                story.append(Paragraph(line_fmt, style_alinea))
            else:
                story.append(Paragraph(line_fmt, style_body))
        story.append(Spacer(1, 2))

    story.append(
        Paragraph(
            "E, por estarem assim justas e contratadas, firmam o presente distrato em 02 (duas) vias de igual "
            "teor e forma, na presença das testemunhas abaixo.",
            style_body,
        )
    )
    story.append(Spacer(1, 8))

    city = "Fortaleza"
    month_name = (
        _MONTH_NAMES[document_date.month]
        if 1 <= document_date.month <= 12
        else str(document_date.month)
    )
    story.append(
        Paragraph(
            f"{city}, {document_date.day:02d} de {month_name} de {document_date.year}.",
            style_body,
        )
    )
    story.append(Spacer(1, 10))

    signatures = [
        ("CONTRATANTE:", company_name, f"CNPJ: {company_cnpj}"),
        ("CONTRATADA:", contractor_name, f"CNPJ: {contractor_cnpj}"),
    ]
    for role, name, doc_text in signatures:
        story.append(Paragraph(role, style_signature_label))
        story.append(Paragraph(name, style_signature_text))
        story.append(Paragraph(doc_text, style_signature_text))
        story.append(Spacer(1, 16))

    story.append(Paragraph("TESTEMUNHAS:", style_signature_label))
    story.append(
        Paragraph(
            "NOME: __________________________   CPF: __________________________",
            style_signature_text,
        )
    )
    story.append(
        Paragraph(
            "NOME: __________________________   CPF: __________________________",
            style_signature_text,
        )
    )

    doc.build(story, onFirstPage=_draw_page_footer, onLaterPages=_draw_page_footer)
    return buf.getvalue()

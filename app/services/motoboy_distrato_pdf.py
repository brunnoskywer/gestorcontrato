"""Geração de PDF do instrumento de distrato (rescisão) do contrato de motoboy."""
from __future__ import annotations

from datetime import date
from io import BytesIO
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models import Company, Contract

from app.services.motoboy_contract_pdf import _MONTH_NAMES, _format_doc

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


def _esc(text: str) -> str:
    """Escapa texto dinâmico para Paragraph (mini-HTML do ReportLab)."""
    if not text:
        return ""
    return (
        str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def build_motoboy_distrato_pdf(
    contract: "Contract", company: "Company", document_date: date
) -> bytes:
    """PDF de distrato. `contract.end_date` = data de notificação / eficácia da rescisão."""
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
    company_name = _esc((company.legal_name or "").strip() or "-")
    company_cnpj = _esc(_format_doc(company.cnpj))

    contractor_name = _esc((supplier.name if supplier else "").strip() or "-")
    contractor_cnpj = _esc(
        _format_doc(
            (supplier.document_secondary if supplier else None)
            or (supplier.document if supplier else None)
        )
    )

    start_br = (
        contract.start_date.strftime("%d/%m/%Y") if contract.start_date else "-"
    )
    end_br = contract.end_date.strftime("%d/%m/%Y")

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=30,
        rightMargin=30,
        topMargin=30,
        bottomMargin=30,
        title=f"Distrato Motoboy #{contract.id}",
    )

    styles = getSampleStyleSheet()
    style_title = ParagraphStyle(
        "distratoTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        alignment=TA_CENTER,
        leading=12,
        spaceAfter=6,
    )
    style_intro = ParagraphStyle(
        "distratoIntro",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.8,
        leading=10.8,
        alignment=TA_JUSTIFY,
        spaceAfter=5,
    )
    style_section = ParagraphStyle(
        "distratoSection",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=10.8,
        alignment=TA_LEFT,
        spaceBefore=3,
        spaceAfter=1,
    )
    style_body = ParagraphStyle(
        "distratoBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.6,
        leading=10.4,
        alignment=TA_JUSTIFY,
        spaceAfter=2,
    )
    style_sub = ParagraphStyle(
        "distratoSub",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.6,
        leading=10.4,
        alignment=TA_JUSTIFY,
        leftIndent=8,
        spaceAfter=2,
    )
    style_party_line = ParagraphStyle(
        "distratoParty",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.8,
        leading=10.8,
        alignment=TA_LEFT,
        spaceAfter=1,
    )
    style_sig_label = ParagraphStyle(
        "distratoSigLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=10.5,
        alignment=TA_LEFT,
        spaceBefore=7,
        spaceAfter=4,
    )
    # Linha de assinatura (~60% da largura útil): texto curto centralizado
    style_sig_underline = ParagraphStyle(
        "distratoSigUnderline",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.7,
        leading=11.4,
        alignment=TA_CENTER,
        spaceAfter=3,
    )
    style_sig_name_center = ParagraphStyle(
        "distratoSigName",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.7,
        leading=10.8,
        alignment=TA_CENTER,
        spaceAfter=2,
    )
    style_sig_cnpj_center = ParagraphStyle(
        "distratoSigCnpj",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.7,
        leading=10.8,
        alignment=TA_CENTER,
        spaceAfter=8,
    )
    style_sig_line = ParagraphStyle(
        "distratoSigLine",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.2,
        leading=9.8,
        alignment=TA_CENTER,
        spaceAfter=1,
    )
    style_center_small = ParagraphStyle(
        "distratoCenter",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        alignment=TA_CENTER,
        leading=10.2,
        spaceAfter=3,
    )

    story = []
    story.append(
        Paragraph(
            "INSTRUMENTO DE DISTRATO DE CONTRATO DE PRESTAÇÃO DE SERVIÇOS DE ENTREGA",
            style_title,
        )
    )

    story.append(
        Paragraph(
            "As partes do presente distrato, abaixo identificadas, de livre e espontânea vontade, "
            "pactuam conforme as cláusulas a seguir, dando tudo como justo e acertado:",
            style_intro,
        )
    )

    story.append(Paragraph("I. DAS PARTES", style_section))
    story.append(
        Paragraph(
            f"<b>DISTRATANTE - CONTRATANTE:</b> {company_name}",
            style_party_line,
        )
    )
    story.append(
        Paragraph(
            f"<b>DISTRATANTE - CONTRATADA:</b> {contractor_name}",
            style_party_line,
        )
    )
    story.append(Spacer(1, 1))
    story.append(
        Paragraph(
            "Em comum acordo, as partes resolveram distratar o respectivo negócio jurídico, "
            "de acordo com os termos abaixo:",
            style_body,
        )
    )

    story.append(Paragraph("II. DO OBJETO DO DISTRATO", style_section))
    story.append(
        Paragraph(
            f"<b>II.1</b> AS PARTES concordam em rescindir e encerrar o Contrato de prestação de "
            f"serviços de entrega firmado em <b>{start_br}</b>, ficando acertado que, desde a data de "
            f"notificação de rescisão, fixada em <b>{end_br}</b>, todas as obrigações, direitos e "
            "responsabilidades previstas na lei e no contrato cessam, nos termos ajustados entre as partes.",
            style_sub,
        )
    )
    story.append(
        Paragraph(
            "<b>II.2</b> Em razão do encerramento da relação contratual, AS PARTES, para fins de "
            "quitação ampla e recíproca, declaram nada mais dever um ao outro, seja a que título for, "
            "seja relativo a dívida e/ou obrigação do passado, do presente e/ou do futuro.",
            style_sub,
        )
    )
    story.append(
        Paragraph(
            "<b>II.3</b> AS PARTES declaram, mutuamente, que cumpriram todas as obrigações e compromissos "
            "assumidos no âmbito do contrato de prestação de serviços até a presente data e concordam "
            "em renunciar, mutuamente, qualquer reivindicação ou obrigação futura decorrente do contrato "
            "ou de sua rescisão.",
            style_sub,
        )
    )
    story.append(
        Paragraph(
            "<b>II.4</b> O presente instrumento de distrato substitui e revoga todas as disposições "
            "conflitantes ou em contrário no Contrato originário, bem como eventuais instrumentos acessórios.",
            style_sub,
        )
    )

    story.append(Paragraph("III. DAS CONDIÇÕES DO DISTRATO", style_section))
    story.append(
        Paragraph(
            "AS PARTES resolvem, nesta data e por este instrumento, dissolver amigavelmente o contrato "
            "anteriormente firmado, resilindo quaisquer direitos e obrigações advindas daquele, de modo "
            "a que não permaneçam resquícios de ônus financeiro e/ou obrigacional para nenhum dos "
            "DISTRATANTES, na extensão aqui pactuada, de modo que o presente distrato abrange as "
            "cláusulas do contrato distratado quanto ao seu encerramento.",
            style_body,
        )
    )

    story.append(Paragraph("IV. DA QUITAÇÃO TOTAL", style_section))
    story.append(
        Paragraph(
            "Pelo presente distrato e na melhor forma do direito, ficam plenamente quitados todos os "
            "direitos e obrigações oriundos do contrato rescindido, não havendo quaisquer pendências "
            "recíprocas, sejam elas de ordem ética, administrativa, material, moral ou física. Fica "
            "estabelecido por este distrato que ambas as partes renunciam, ainda, a todo e qualquer "
            "pleito judicial ou extrajudicial que possam versar sobre pagamento, restituições, "
            "ressarcimento ou indenizações decorrentes do contrato originário ou deste distrato.",
            style_body,
        )
    )

    story.append(Paragraph("V. DA VIGÊNCIA", style_section))
    story.append(
        Paragraph(
            "O presente distrato ratifica os efeitos já operados desde a data de notificação de rescisão "
            "e é subscrito de modo irretratável e irrevogável.",
            style_body,
        )
    )
    story.append(
        Paragraph(
            "As partes, desde já, elegem o <b>FORO da comarca de Fortaleza, Estado do Ceará</b>, para "
            "dirimir quaisquer questões de direito, que direta ou indiretamente decorram deste instrumento, "
            "com renúncia expressa de qualquer outro, por mais privilegiado que seja.",
            style_body,
        )
    )

    story.append(
        Paragraph(
            "E por estarem assim justos e contratados, assinam o presente instrumento, depois de lido "
            "e achado conforme, em 02 (duas) vias de igual teor e forma, na presença das testemunhas "
            "abaixo assinadas para que produza os fins de direito.",
            style_body,
        )
    )
    story.append(Spacer(1, 4))

    city = "Fortaleza"
    month_name = (
        _MONTH_NAMES[document_date.month]
        if 1 <= document_date.month <= 12
        else str(document_date.month)
    )
    story.append(
        Paragraph(
            f"<b>{city}, {document_date.day:02d} de {month_name} de {document_date.year}.</b>",
            style_center_small,
        )
    )
    story.append(Spacer(1, 4))

    _sig_line_chars = (
        "________________________________________________________"
    )  # ~56 caracteres, linha visível centralizada para assinatura

    story.append(Paragraph("DISTRATANTE - CONTRATANTE:", style_sig_label))
    story.append(Paragraph(_sig_line_chars, style_sig_underline))
    story.append(Paragraph(company_name, style_sig_name_center))
    story.append(
        Paragraph(f"CNPJ: {company_cnpj}", style_sig_cnpj_center),
    )

    story.append(Paragraph("DISTRATANTE - CONTRATADA:", style_sig_label))
    story.append(Paragraph(_sig_line_chars, style_sig_underline))
    story.append(Paragraph(contractor_name, style_sig_name_center))
    story.append(
        Paragraph(f"CNPJ: {contractor_cnpj}", style_sig_cnpj_center),
    )

    story.append(Paragraph("TESTEMUNHAS:", style_sig_label))
    story.append(
        Paragraph(
            "_________________________________________________________________________",
            style_sig_line,
        )
    )
    story.append(
        Paragraph(
            "NOME: _________________________________ &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; "
            "NOME: _________________________________",
            style_sig_line,
        )
    )
    story.append(
        Paragraph(
            "CPF: ____________________________________ &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; "
            "CPF: ____________________________________",
            style_sig_line,
        )
    )

    doc.build(story, onFirstPage=_draw_page_footer, onLaterPages=_draw_page_footer)
    return buf.getvalue()

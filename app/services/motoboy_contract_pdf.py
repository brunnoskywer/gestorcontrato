"""Geração de PDF do contrato de prestação de serviços do motoboy."""
from __future__ import annotations

import re
from datetime import date
from io import BytesIO
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models import Company, Contract

from app.utils import format_address_line

try:
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
except ImportError:  # pragma: no cover - depende de pacote externo
    A4 = None
    TA_CENTER = TA_JUSTIFY = TA_LEFT = None
    ParagraphStyle = getSampleStyleSheet = None
    Paragraph = SimpleDocTemplate = Spacer = None


_MONTH_NAMES = (
    "",
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
)


def _fmt_money_br(value) -> str:
    try:
        num = float(value or 0)
    except (TypeError, ValueError):
        num = 0.0
    return f"{num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _only_digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def _format_doc(value: str | None) -> str:
    digits = _only_digits(value)
    if len(digits) == 11:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
    if len(digits) == 14:
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"
    return (value or "-").strip() or "-"


def _format_phone(value: str | None) -> str:
    digits = _only_digits(value)
    if len(digits) == 11:
        return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
    if len(digits) == 10:
        return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
    return (value or "-").strip() or "-"


def _highlight_roles(text: str) -> str:
    if not text:
        return text
    out = text.replace("CONTRATANTE", "<b>CONTRATANTE</b>")
    out = out.replace("CONTRATADA", "<b>CONTRATADA</b>")
    return out


def _draw_page_footer(pdf_canvas, doc) -> None:
    pdf_canvas.setFont("Helvetica", 8)
    pdf_canvas.drawRightString(A4[0] - 35, 26, f"Página {pdf_canvas.getPageNumber()}")


def build_motoboy_contract_pdf(contract: "Contract", company: "Company", signed_at: date) -> bytes:
    if (
        A4 is None
        or SimpleDocTemplate is None
        or Paragraph is None
        or Spacer is None
        or ParagraphStyle is None
        or getSampleStyleSheet is None
    ):  # pragma: no cover - ambiente sem reportlab
        raise RuntimeError("reportlab não está instalado no ambiente.")

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
    contact_phone = "(85) 98829-4588"
    monthly_value = _fmt_money_br(contract.service_value or 0)

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=42,
        rightMargin=42,
        topMargin=42,
        bottomMargin=38,
        title=f"Contrato Motoboy #{contract.id}",
    )

    styles = getSampleStyleSheet()
    style_title = ParagraphStyle(
        "contractTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        alignment=TA_CENTER,
        leading=15,
        spaceAfter=12,
    )
    style_intro = ParagraphStyle(
        "contractIntro",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        alignment=TA_JUSTIFY,
        firstLineIndent=22,
        spaceAfter=8,
    )
    style_clause = ParagraphStyle(
        "clauseTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=14,
        alignment=TA_LEFT,
        spaceBefore=5,
        spaceAfter=3,
    )
    style_body = ParagraphStyle(
        "clauseBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=13.5,
        alignment=TA_JUSTIFY,
        firstLineIndent=20,
        spaceAfter=3,
    )
    style_alinea = ParagraphStyle(
        "clauseAlinea",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=13.5,
        alignment=TA_JUSTIFY,
        leftIndent=18,
        firstLineIndent=-10,  # tabulação pendente para "a)"
        spaceAfter=2,
    )
    style_signature_label = ParagraphStyle(
        "signatureLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        spaceBefore=4,
        spaceAfter=1,
    )
    style_signature_text = ParagraphStyle(
        "signatureText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=13,
        spaceAfter=3,
    )

    story = []
    story.append(Paragraph("INSTRUMENTO DE PRESTAÇÃO DE SERVIÇOS", style_title))
    intro = (
        "Contrato particular de prestação de serviço que entre si fazem, de um lado, como "
        f"<b>CONTRATANTE</b>, doravante como tal denominada, <b>{company_name}</b>, "
        f"com sede em {company_address}, inscrita no CNPJ sob o nº <b>{company_cnpj}</b>; "
        f"de outro lado, como <b>CONTRATADA</b>, doravante como tal denominado, "
        f"<b>{contractor_name}</b>, empresa com sede em {contractor_address}, inscrita no CNPJ sob o nº "
        f"<b>{contractor_cnpj}</b>, segundo as cláusulas e condições a seguir:"
    )
    story.append(Paragraph(intro, style_intro))

    sections = [
        ("CLÁUSULA 1ª - DO OBJETO DO CONTRATO", [
            "O presente contrato tem por objeto a prestação, pela CONTRATADA à CONTRATANTE, de serviços de entrega de produtos e mercadorias de pequenos portes, efetuado por motoboys em veículo automotor, conforme disponibilidade e demanda ajustada entre as partes."
        ]),
        ("CLÁUSULA 2ª - DAS OBRIGAÇÕES", [
            "a) A CONTRATANTE entregará à CONTRATADA, pessoalmente ou através de terceiros, os produtos a serem transportados/entregues, indicando quantidade, remetente e destinatário, além dos valores a serem eventualmente recebidos no ato da entrega;",
            "b) A CONTRATADA se obriga a executar os serviços contratados de acordo com os padrões mínimos exigidos pela CONTRATANTE;",
            "c) A CONTRATADA se obriga, quando necessário, a informar a impossibilidade temporária ou permanente de prestação de serviço;",
            "d) A CONTRATADA deverá substituir, quando solicitada e de forma justificada, qualquer funcionário da equipe no prazo máximo de 72h;",
            "e) A CONTRATADA poderá designar pessoa com idêntica capacidade e expertise para execução dos serviços, mediante autorização prévia da CONTRATANTE;",
            "f) A CONTRATADA deverá promover a substituição imediata do veículo utilizado quando não estiver em condição de uso;",
            "g) A CONTRATADA se obriga à manutenção e abastecimento dos veículos, correndo todos os custos por sua exclusiva responsabilidade;",
            "h) A CONTRATADA se obriga a cumprir todas as leis federais, estaduais e municipais durante a execução dos serviços;",
            "i) A CONTRATADA se responsabiliza pelo absoluto sigilo de todas as informações que conhecer em decorrência da execução dos serviços.",
        ]),
        ("CLÁUSULA 3ª - DOS VALORES E CONDIÇÕES DE PAGAMENTO", [
            f"a) Pela realização dos serviços descritos neste contrato, a CONTRATANTE remunerará a CONTRATADA com o valor de R$ {monthly_value}, a ser pago até o quinto dia útil do mês subsequente à prestação, via pagamento bancário;",
            "b) As notas fiscais/faturas serão emitidas após o último dia do mês da prestação de serviço;",
            "c) O atraso no pagamento poderá sujeitar o contratante às penalidades pactuadas entre as partes;",
            "d) Mediante acordo, a forma de pagamento poderá ser quitada dentro do mês, conforme os serviços prestados.",
        ]),
        ("CLÁUSULA 4ª - DA VIGÊNCIA", [
            "O presente contrato terá vigência por prazo de 01 (um) ano, podendo ser prorrogado pelo mesmo período, por solicitação da CONTRATADA e autorização da CONTRATANTE."
        ]),
        ("CLÁUSULA 5ª - DA RESCISÃO", [
            "a) O contrato poderá ser rescindido a qualquer tempo, ainda que sem motivo relevante, desde que a outra parte seja avisada por escrito;",
            "b) A rescisão não extingue direitos e obrigações pendentes entre as partes;",
            "c) Havendo rescisão por requisição da CONTRATANTE, deverá pagar os serviços efetivamente prestados e ainda não quitados;",
            "d) Havendo rescisão por requisição da CONTRATADA, fará jus apenas aos serviços efetivamente prestados e inadimplidos até a comunicação;",
            "e) Havendo justo motivo para rescisão, a parte que deu causa deverá indenizar a outra em perdas e danos.",
        ]),
        ("CLÁUSULA 6ª - DA INEXISTÊNCIA DE VÍNCULO EMPREGATÍCIO", [
            "Declaram as partes estarem cientes da espécie de contratação firmada, sem qualquer exclusividade e/ou habitualidade, tendo sido devidamente esclarecidas, sabendo que o presente instrumento não estabelece relação de vínculo empregatício e se encerra quando da expiração do prazo de vigência fixado na cláusula 4ª ou em caso de rescisão, nas hipóteses previstas na cláusula quinta."
        ]),
        ("CLÁUSULA 7ª - DAS DISPOSIÇÕES FINAIS", [
            "Estando revestidas de boa-fé, CONTRATANTE e CONTRATADA declaram, garantindo uma à outra que:",
            "a) O presente Contrato não importa vício de consentimento, espelha fielmente tudo o que foi ajustado entre as Partes, que tiveram prévia e tempestivo conhecimento do conteúdo do presente Contrato, entendendo, perfeitamente, todas as disposições e reflexos jurídicos do presente instrumento;",
            "b) Forneceu e recebeu da outra Parte todas as informações devidas ou convenientes para a celebração do presente Contrato, sobretudo sobre a natureza da prestação de serviços e formato de contratação/pagamento;",
            "c) Não está em estado de perigo ou coação, nem incorre em erro, ignorância, dolo, fraude contra credores, lesão de direitos ou qualquer outra situação que impacte, limite ou inviabilize este Contrato;",
            "d) Guardará na execução do presente Contrato os princípios da probidade e da boa-fé, igualmente presentes na sua negociação e na sua celebração;",
        ]),
        ("CLÁUSULA 8ª - DAS COMUNICAÇÕES", [
            f"A CONTRATADA autoriza que as comunicações decorrentes deste contrato ocorram, preferencialmente, via WhatsApp no número {contact_phone}."
        ]),
        ("CLÁUSULA 9ª - DO FORO", [
            "As partes elegem o foro da comarca de Fortaleza/CE para dirimir quaisquer questões decorrentes deste instrumento, com renúncia expressa de qualquer outro."
        ]),
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
            "E por estarem assim justos e contratados, assinam o presente instrumento, depois de lido e achado conforme, em 02 (duas) vias de igual teor e forma, na presença das testemunhas abaixo assinadas para que produza os fins de direito.",
            style_body,
        )
    )
    story.append(Spacer(1, 8))

    city = "Fortaleza"
    month_name = _MONTH_NAMES[signed_at.month] if 1 <= signed_at.month <= 12 else str(signed_at.month)
    story.append(
        Paragraph(
            f"{city}, {signed_at.day:02d} de {month_name} de {signed_at.year}.",
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
    story.append(Paragraph("NOME: __________________________   CPF: __________________________", style_signature_text))
    story.append(Paragraph("NOME: __________________________   CPF: __________________________", style_signature_text))

    doc.build(story, onFirstPage=_draw_page_footer, onLaterPages=_draw_page_footer)
    return buf.getvalue()

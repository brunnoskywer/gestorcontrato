"""Geração de PDF do contrato de prestação de serviços do motoboy."""
from __future__ import annotations

import re
from datetime import date
from io import BytesIO
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models import Company, Contract

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
except ImportError:  # pragma: no cover - depende de pacote externo
    A4 = None
    canvas = None


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


def _draw_paragraph(
    pdf,
    text: str,
    x: float,
    y: float,
    max_width: float,
    *,
    font_name: str = "Helvetica",
    font_size: int = 10,
    line_height: int = 13,
    first_line_indent: float = 0,
    rest_indent: float = 0,
) -> float:
    words = (text or "").split()
    if not words:
        return y
    pdf.setFont(font_name, font_size)
    line = ""
    first = True
    for w in words:
        candidate = (line + " " + w).strip()
        indent = first_line_indent if first else rest_indent
        available = max_width - indent
        if pdf.stringWidth(candidate, font_name, font_size) <= available:
            line = candidate
            continue
        draw_x = x + indent
        pdf.drawString(draw_x, y, line)
        y -= line_height
        first = False
        line = w
    if line:
        indent = first_line_indent if first else rest_indent
        pdf.drawString(x + indent, y, line)
        y -= line_height
    return y


def _finish_page(pdf, width: float) -> None:
    pdf.setFont("Helvetica", 8)
    pdf.drawRightString(width - 35, 26, f"Página {pdf.getPageNumber()}")


def _ensure_space(pdf, y: float, width: float, height: float, margin_bottom: int = 55) -> float:
    if y > margin_bottom:
        return y
    _finish_page(pdf, width)
    pdf.showPage()
    return height - 50


def build_motoboy_contract_pdf(contract: "Contract", company: "Company", signed_at: date) -> bytes:
    if canvas is None or A4 is None:  # pragma: no cover - ambiente sem reportlab
        raise RuntimeError("reportlab não está instalado no ambiente.")

    supplier = contract.supplier
    company_name = (company.legal_name or "").strip() or "-"
    company_address = (company.address or "").strip() or "-"
    company_cnpj = _format_doc(company.cnpj)

    contractor_name = (supplier.name if supplier else "").strip() or "-"
    contractor_address = (supplier.address if supplier else "").strip() or "-"
    contractor_cnpj = _format_doc(
        (supplier.document_secondary if supplier else None)
        or (supplier.document if supplier else None)
    )
    contact_phone = _format_phone((supplier.contact_phone if supplier else None) or "")
    monthly_value = _fmt_money_br(contract.service_value or 0)

    buf = BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    margin_x = 40
    usable_width = width - (margin_x * 2)
    y = height - 48

    pdf.setTitle(f"Contrato Motoboy #{contract.id}")
    y = _draw_paragraph(
        pdf,
        "INSTRUMENTO DE PRESTAÇÃO DE SERVIÇOS",
        margin_x,
        y,
        usable_width,
        font_name="Helvetica-Bold",
        font_size=12,
        line_height=16,
    )
    y -= 8

    intro = (
        "Contrato particular de prestação de serviço que entre si fazem, de um lado, como CONTRATANTE, "
        f"{company_name}, com sede em {company_address}, inscrita no CNPJ sob o nº {company_cnpj}; "
        "de outro lado, como CONTRATADA, "
        f"{contractor_name}, empresa com sede em {contractor_address}, inscrita no CNPJ sob o nº {contractor_cnpj}, "
        "segundo as cláusulas e condições a seguir:"
    )
    y = _draw_paragraph(
        pdf,
        intro,
        margin_x,
        y,
        usable_width,
        first_line_indent=18,
        rest_indent=0,
    )
    y -= 3

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
            "Declaram as partes estarem cientes da espécie de contratação firmada, sem exclusividade e habitualidade, inexistindo vínculo empregatício."
        ]),
        ("CLÁUSULA 7ª - DAS DISPOSIÇÕES FINAIS", [
            "As partes declaram boa-fé, pleno conhecimento do conteúdo deste instrumento e das obrigações nele previstas, comprometendo-se com probidade e lealdade na execução."
        ]),
        ("CLÁUSULA 8ª - DAS COMUNICAÇÕES", [
            f"A CONTRATADA autoriza que as comunicações decorrentes deste contrato ocorram, preferencialmente, via WhatsApp no número {contact_phone}."
        ]),
        ("CLÁUSULA 9ª - DO FORO", [
            "As partes elegem o foro da comarca de Fortaleza/CE para dirimir quaisquer questões decorrentes deste instrumento, com renúncia expressa de qualquer outro."
        ]),
    ]

    for title, items in sections:
        y = _ensure_space(pdf, y, width, height)
        y = _draw_paragraph(
            pdf,
            title,
            margin_x,
            y,
            usable_width,
            font_name="Helvetica-Bold",
            line_height=14,
        )
        for line in items:
            y = _ensure_space(pdf, y, width, height)
            first_indent = 8 if re.match(r"^[a-z]\)", line.strip(), re.IGNORECASE) else 18
            rest_indent = 20 if first_indent == 8 else 0
            y = _draw_paragraph(
                pdf,
                line,
                margin_x,
                y,
                usable_width,
                first_line_indent=first_indent,
                rest_indent=rest_indent,
            )
        y -= 4

    y = _ensure_space(pdf, y, width, height, margin_bottom=145)
    city = "Fortaleza"
    month_name = _MONTH_NAMES[signed_at.month] if 1 <= signed_at.month <= 12 else str(signed_at.month)
    y = _draw_paragraph(
        pdf,
        f"{city}, {signed_at.day:02d} de {month_name} de {signed_at.year}.",
        margin_x,
        y,
        usable_width,
    )
    y -= 8

    signatures = [
        ("CONTRATANTE:", company_name, f"CNPJ: {company_cnpj}"),
        ("CONTRATADA:", contractor_name, f"CNPJ: {contractor_cnpj}"),
    ]
    for role, name, doc in signatures:
        y = _ensure_space(pdf, y, width, height, margin_bottom=105)
        y = _draw_paragraph(pdf, role, margin_x, y, usable_width, font_name="Helvetica-Bold")
        y = _draw_paragraph(pdf, name, margin_x, y, usable_width)
        y = _draw_paragraph(pdf, doc, margin_x, y, usable_width)
        y -= 6

    y = _ensure_space(pdf, y, width, height, margin_bottom=78)
    y = _draw_paragraph(pdf, "TESTEMUNHAS:", margin_x, y, usable_width, font_name="Helvetica-Bold")
    y -= 4
    y = _draw_paragraph(pdf, "NOME: __________________________   CPF: __________________________", margin_x, y, usable_width)
    y = _draw_paragraph(pdf, "NOME: __________________________   CPF: __________________________", margin_x, y, usable_width)

    _finish_page(pdf, width)
    pdf.save()
    return buf.getvalue()

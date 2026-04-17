"""Geração de PDF do contrato de prestação de serviços do motoboy."""
from __future__ import annotations

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


def _draw_wrapped_text(pdf, text: str, x: int, y: float, max_width: float, line_height: int = 14) -> float:
    """Desenha texto quebrando por largura e retorna o novo Y."""
    words = (text or "").split()
    if not words:
        return y
    line = ""
    for w in words:
        candidate = (line + " " + w).strip()
        if pdf.stringWidth(candidate, "Helvetica", 10) <= max_width:
            line = candidate
            continue
        pdf.drawString(x, y, line)
        y -= line_height
        line = w
    if line:
        pdf.drawString(x, y, line)
        y -= line_height
    return y


def _ensure_space(pdf, y: float, height: float, margin_bottom: int = 55) -> float:
    if y > margin_bottom:
        return y
    pdf.showPage()
    pdf.setFont("Helvetica", 10)
    return height - 55


def build_motoboy_contract_pdf(contract: "Contract", company: "Company", signed_at: date) -> bytes:
    if canvas is None or A4 is None:  # pragma: no cover - ambiente sem reportlab
        raise RuntimeError("reportlab não está instalado no ambiente.")

    supplier = contract.supplier
    company_name = (company.legal_name or "").strip() or "-"
    company_address = (company.address or "").strip() or "-"
    company_cnpj = (company.cnpj or "").strip() or "-"

    contractor_name = (supplier.name if supplier else "").strip() or "-"
    contractor_address = (supplier.address if supplier else "").strip() or "-"
    contractor_cnpj = (
        (supplier.document_secondary if supplier else None)
        or (supplier.document if supplier else None)
        or "-"
    )
    contact_phone = (supplier.contact_phone if supplier else None) or "-"
    monthly_value = _fmt_money_br(contract.service_value or 0)

    buf = BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    margin_x = 40
    usable_width = width - (margin_x * 2)
    y = height - 45

    pdf.setTitle(f"Contrato Motoboy #{contract.id}")
    pdf.setFont("Helvetica-Bold", 12)
    y = _draw_wrapped_text(pdf, "INSTRUMENTO DE PRESTAÇÃO DE SERVIÇOS", margin_x, y, usable_width, 16)
    y -= 6

    pdf.setFont("Helvetica", 10)
    intro = (
        "Contrato particular de prestação de serviço que entre si fazem, de um lado, como CONTRATANTE, "
        f"{company_name}, com sede em {company_address}, inscrita no CNPJ sob o nº {company_cnpj}; "
        "de outro lado, como CONTRATADA, "
        f"{contractor_name}, empresa com sede em {contractor_address}, inscrita no CNPJ sob o nº {contractor_cnpj}, "
        "segundo as cláusulas e condições a seguir:"
    )
    y = _draw_wrapped_text(pdf, intro, margin_x, y, usable_width)
    y -= 4

    sections = [
        ("CLÁUSULA 1ª - DO OBJETO DO CONTRATO", [
            "O presente contrato tem por objeto a prestação, pela CONTRATADA à CONTRATANTE, de serviços "
            "de entrega de produtos e mercadorias de pequenos portes, efetuado por motoboys em veículo "
            "automotor, conforme disponibilidade e demanda ajustada entre as partes."
        ]),
        ("CLÁUSULA 2ª - DAS OBRIGAÇÕES", [
            "a) A CONTRATANTE entregará à CONTRATADA, pessoalmente ou através de terceiros, os produtos a serem transportados/entregues.",
            "b) A CONTRATADA se obriga a executar os serviços contratados de acordo com os padrões mínimos exigidos pela CONTRATANTE.",
            "c) A CONTRATADA se obriga, quando necessário, a informar impossibilidade temporária ou permanente de prestação de serviço.",
            "d) A CONTRATADA deverá substituir, quando solicitado e de forma justificada, qualquer funcionário da equipe no prazo máximo de 72h.",
            "e) A CONTRATADA poderá designar substituto com idêntica capacidade e expertise, mediante conhecimento prévio e autorização da CONTRATANTE.",
            "f) A CONTRATADA deverá promover substituição imediata do veículo quando não estiver em condição de uso.",
            "g) A CONTRATADA se obriga à manutenção e abastecimento dos veículos utilizados, correndo todos os custos por sua exclusiva responsabilidade.",
            "h) A CONTRATADA se obriga a cumprir todas as leis federais, estaduais e municipais durante a execução dos serviços.",
            "i) A CONTRATADA se responsabiliza pelo absoluto sigilo de todas as informações que conhecer em decorrência da execução dos serviços.",
        ]),
        ("CLÁUSULA 3ª - DOS VALORES E CONDIÇÕES DE PAGAMENTO", [
            f"a) Pela realização dos serviços descritos neste contrato, a CONTRATANTE remunerará a CONTRATADA com o valor mensal de R$ {monthly_value}.",
            "b) As notas fiscais/faturas serão emitidas após o último dia do mês da prestação de serviço.",
            "c) O atraso no pagamento poderá sujeitar o contratante às penalidades pactuadas entre as partes.",
            "d) Mediante acordo, a forma de pagamento poderá ser quitada dentro do mês conforme os serviços prestados.",
        ]),
        ("CLÁUSULA 4ª - DA VIGÊNCIA", [
            "O presente contrato terá vigência por prazo de 01 (um) ano, podendo ser prorrogado pelo mesmo período, por solicitação da CONTRATADA e autorização da CONTRATANTE."
        ]),
        ("CLÁUSULA 5ª - DA RESCISÃO", [
            "a) O contrato poderá ser rescindido a qualquer tempo, desde que a outra parte seja avisada por escrito.",
            "b) A rescisão não extingue direitos e obrigações pendentes entre as partes.",
            "c) Havendo rescisão por requisição da CONTRATANTE, deverá pagar os serviços efetivamente prestados e ainda não quitados.",
            "d) Havendo rescisão por requisição da CONTRATADA, fará jus apenas aos serviços efetivamente prestados e inadimplidos até a comunicação.",
            "e) Havendo justo motivo para rescisão, a parte que deu causa deverá indenizar a outra em perdas e danos.",
        ]),
        ("CLÁUSULA 6ª - DA INEXISTÊNCIA DE VÍNCULO EMPREGATÍCIO", [
            "Declaram as partes estarem cientes da espécie de contratação firmada, sem exclusividade e habitualidade, inexistindo vínculo empregatício."
        ]),
        ("CLÁUSULA 7ª - DAS DISPOSIÇÕES FINAIS", [
            "As partes declaram boa-fé, pleno conhecimento do conteúdo deste instrumento e das obrigações nele previstas."
        ]),
        ("CLÁUSULA 8ª - DAS COMUNICAÇÕES", [
            f"A CONTRATADA autoriza que as comunicações decorrentes deste contrato ocorram, preferencialmente, via WhatsApp no número {contact_phone}."
        ]),
        ("CLÁUSULA 9ª - DO FORO", [
            "As partes elegem o foro da comarca de Fortaleza/CE para dirimir quaisquer questões decorrentes deste instrumento, com renúncia de qualquer outro."
        ]),
    ]

    for title, items in sections:
        y = _ensure_space(pdf, y, height)
        pdf.setFont("Helvetica-Bold", 10)
        y = _draw_wrapped_text(pdf, title, margin_x, y, usable_width)
        pdf.setFont("Helvetica", 10)
        for line in items:
            y = _ensure_space(pdf, y, height)
            y = _draw_wrapped_text(pdf, line, margin_x, y, usable_width)
        y -= 2

    y = _ensure_space(pdf, y, height, margin_bottom=120)
    city = "Fortaleza"
    month_name = _MONTH_NAMES[signed_at.month] if 1 <= signed_at.month <= 12 else str(signed_at.month)
    y = _draw_wrapped_text(
        pdf,
        f"{city}, {signed_at.day:02d} de {month_name} de {signed_at.year}.",
        margin_x,
        y,
        usable_width,
    )
    y -= 8

    signatures = [
        ("CONTRATANTE", company_name, f"CNPJ: {company_cnpj}"),
        ("CONTRATADA", contractor_name, f"CNPJ: {contractor_cnpj}"),
    ]
    for role, name, doc in signatures:
        y = _ensure_space(pdf, y, height, margin_bottom=90)
        y = _draw_wrapped_text(pdf, f"{role}:", margin_x, y, usable_width)
        y = _draw_wrapped_text(pdf, name, margin_x, y, usable_width)
        y = _draw_wrapped_text(pdf, doc, margin_x, y, usable_width)
        y -= 10

    y = _ensure_space(pdf, y, height, margin_bottom=70)
    y = _draw_wrapped_text(pdf, "TESTEMUNHAS:", margin_x, y, usable_width)
    y = _draw_wrapped_text(pdf, "NOME: ______________________   CPF: ______________________", margin_x, y, usable_width)
    y = _draw_wrapped_text(pdf, "NOME: ______________________   CPF: ______________________", margin_x, y, usable_width)

    pdf.save()
    return buf.getvalue()

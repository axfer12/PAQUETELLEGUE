"""
invoice_pdf.py
==============
Genera la Factura Comercial / Commercial Invoice en PDF.
Sin dependencias de GUI — funciona en servidor (Render.com).
"""
import os, datetime

PURPOSES_ES = {
    "personal": "Uso Personal / Personal Use",
    "commercial": "Uso Comercial / Commercial Use",
    "gift": "Regalo / Gift",
    "sample": "Muestra sin valor / Sample without commercial value",
    "return": "Devolución / Return",
    "goods": "Mercancía / Goods",
    "documents": "Documentos / Documents",
}

PAISES = {
    "MX": "México", "US": "United States", "CA": "Canada",
    "CN": "China", "ES": "Spain", "DE": "Germany",
    "FR": "France", "GB": "United Kingdom", "JP": "Japan",
    "BR": "Brazil", "CO": "Colombia", "AR": "Argentina",
}


def _normalizar_producto(p: dict) -> dict:
    """Normaliza un producto del formulario web al formato interno."""
    return {
        "description_es": p.get("description_es") or p.get("description_en") or p.get("descripcion") or "Mercancía",
        "description_en": p.get("description_en") or p.get("description_es") or "Merchandise",
        "hs_code":        p.get("hs_code") or p.get("codigo_hs") or "",
        "quantity":       int(p.get("quantity") or p.get("cantidad") or 1),
        "unit_price":     float(p.get("unit_price") or p.get("price") or p.get("precio") or 0),
        "weight":         float(p.get("weight") or p.get("peso") or 0.5),
        "country_of_origin": (p.get("country_of_origin") or p.get("country_code") or p.get("pais_origen") or "MX").upper(),
        # precio total
        "total": float(p.get("total") or p.get("price") or p.get("precio") or 0),
    }


def generar_pdf_invoice(remitente: dict, destinatario: dict,
                        productos: list, purpose: str = "personal",
                        numero_guia: str = "",
                        ruta_pdf: str = None) -> str:
    """
    Genera el PDF de la Factura Comercial / Commercial Invoice.
    Acepta productos del formulario web (description_en, price, country_code)
    o del formato GUI (description_es, unit_price, country_of_origin).
    Retorna la ruta al PDF generado.
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                    Paragraph, Spacer, HRFlowable)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT

    if ruta_pdf is None:
        data_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "facturas")
        os.makedirs(data_dir, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        ruta_pdf = os.path.join(data_dir, f"invoice_{ts}.pdf")

    doc = SimpleDocTemplate(
        ruta_pdf, pagesize=letter,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=12*mm, bottomMargin=12*mm,
    )

    s_title   = ParagraphStyle("t", fontSize=14, fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=4)
    s_sub     = ParagraphStyle("s", fontSize=9,  fontName="Helvetica", alignment=TA_CENTER, textColor=colors.grey, spaceAfter=8)
    s_section = ParagraphStyle("sc",fontSize=9,  fontName="Helvetica-Bold", textColor=colors.HexColor("#1a5276"), spaceAfter=4)
    s_normal  = ParagraphStyle("n", fontSize=8,  fontName="Helvetica", spaceAfter=2)
    s_small   = ParagraphStyle("sm",fontSize=7,  fontName="Helvetica", textColor=colors.grey)

    now = datetime.datetime.now()
    story = []
    W = letter[0] - 30*mm

    # ── Encabezado ───────────────────────────────────────────────
    story.append(Paragraph("FACTURA COMERCIAL / COMMERCIAL INVOICE", s_title))
    folio = f"  |  No. Guía: {numero_guia}" if numero_guia else ""
    story.append(Paragraph(
        f"Fecha / Date: {now.strftime('%d/%m/%Y')}{folio}  |  "
        f"Propósito: {PURPOSES_ES.get(purpose, purpose)}",
        s_sub))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#C9A84C")))
    story.append(Spacer(1, 4*mm))

    # ── Exportador / Importador ──────────────────────────────────
    def _addr(d):
        pais_nombre = PAISES.get(d.get("pais","MX"), d.get("pais","MX"))
        lines = [f"<b>{d.get('nombre','')}</b>"]
        calle = d.get("calle") or d.get("direccion","")
        if calle: lines.append(calle)
        col = d.get("colonia",""); ciu = d.get("ciudad","")
        if col or ciu: lines.append(f"{col}, {ciu}".strip(", "))
        est = d.get("estado",""); cp = d.get("cp","")
        if est or cp: lines.append(f"{est}  C.P. {cp}  {pais_nombre}")
        if d.get("telefono"): lines.append(f"Tel: {d['telefono']}")
        if d.get("email"):    lines.append(f"Email: {d['email']}")
        return "<br/>".join(lines)

    addr_tbl = Table([
        [Paragraph("<b>EXPORTADOR / EXPORTER</b>", s_section),
         Paragraph("<b>IMPORTADOR / IMPORTER</b>", s_section)],
        [Paragraph(_addr(remitente), s_normal),
         Paragraph(_addr(destinatario), s_normal)],
    ], colWidths=[W/2-3*mm, W/2-3*mm])
    addr_tbl.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#f0f0f0")),
        ("GRID",(0,0),(-1,-1),0.5,colors.HexColor("#cccccc")),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("PADDING",(0,0),(-1,-1),6),
    ]))
    story.append(addr_tbl)
    story.append(Spacer(1, 5*mm))

    # ── Tabla productos ──────────────────────────────────────────
    story.append(Paragraph("DESCRIPCIÓN DE MERCANCÍAS / DESCRIPTION OF GOODS", s_section))
    prods = [_normalizar_producto(p) for p in productos]

    col_w = [W*0.28, W*0.14, W*0.08, W*0.12, W*0.12, W*0.12, W*0.14]
    header_row = [
        Paragraph("<b>Description (EN)</b>",   s_small),
        Paragraph("<b>HS Code</b>",            s_small),
        Paragraph("<b>Qty</b>",               s_small),
        Paragraph("<b>Unit Price\nUSD</b>",   s_small),
        Paragraph("<b>Total\nUSD</b>",        s_small),
        Paragraph("<b>Weight\nkg</b>",        s_small),
        Paragraph("<b>Country\nof Origin</b>",s_small),
    ]
    rows = [header_row]
    total_usd = 0.0; total_kg = 0.0; total_qty = 0
    for p in prods:
        subtotal = p["unit_price"] * p["quantity"] if p["unit_price"] > 0 else p["total"]
        total_usd += subtotal; total_kg += p["weight"] * p["quantity"]; total_qty += p["quantity"]
        rows.append([
            Paragraph(p["description_en"], s_normal),
            Paragraph(p["hs_code"], s_normal),
            Paragraph(str(p["quantity"]), s_normal),
            Paragraph(f"${p['unit_price']:,.2f}", s_normal),
            Paragraph(f"${subtotal:,.2f}", s_normal),
            Paragraph(f"{p['weight']:.2f}", s_normal),
            Paragraph(p["country_of_origin"], s_normal),
        ])
    rows.append([
        Paragraph("<b>TOTAL</b>", s_normal), "",
        Paragraph(f"<b>{total_qty}</b>", s_normal), "",
        Paragraph(f"<b>${total_usd:,.2f}</b>", s_normal),
        Paragraph(f"<b>{total_kg:.2f}</b>", s_normal), "",
    ])

    prod_tbl = Table(rows, colWidths=col_w, repeatRows=1)
    prod_tbl.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#1a5276")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("BACKGROUND",(0,-1),(-1,-1),colors.HexColor("#f5f5f5")),
        ("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#cccccc")),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("ALIGN",(2,1),(5,-1),"RIGHT"),
        ("PADDING",(0,0),(-1,-1),5),
        ("ROWBACKGROUNDS",(0,1),(-1,-2),[colors.white,colors.HexColor("#f9f9f9")]),
    ]))
    story.append(prod_tbl)
    story.append(Spacer(1, 5*mm))

    # ── Resumen ──────────────────────────────────────────────────
    resumen = Table([
        ["Valor total declarado / Total Declared Value:", f"USD ${total_usd:,.2f}"],
        ["Peso total / Total Weight:", f"{total_kg:.2f} kg"],
        ["Moneda / Currency:", "USD – Dólares Americanos"],
        ["Incoterm:", "DAP (Delivered at Place)"],
    ], colWidths=[W*0.6, W*0.4])
    resumen.setStyle(TableStyle([
        ("FONTNAME",(0,0),(0,-1),"Helvetica-Bold"),
        ("FONTSIZE",(0,0),(-1,-1),8),
        ("ALIGN",(1,0),(1,-1),"RIGHT"),
        ("PADDING",(0,0),(-1,-1),4),
        ("LINEBELOW",(0,-1),(-1,-1),0.5,colors.grey),
    ]))
    story.append(resumen)
    story.append(Spacer(1, 8*mm))

    # ── Declaración y firma ──────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(
        "El suscrito declara que la información contenida en esta factura comercial es verdadera y correcta. / "
        "The undersigned declares that the information in this commercial invoice is true and correct.",
        s_small))
    story.append(Spacer(1, 10*mm))
    firma = Table([
        [f"Firma / Signature: {'_'*35}", f"Fecha / Date: {now.strftime('%d / %m / %Y')}"],
        [f"Nombre / Name: {remitente.get('nombre','')}", f"Lugar / Place: {remitente.get('ciudad','')}"],
    ], colWidths=[W*0.6, W*0.4])
    firma.setStyle(TableStyle([("FONTSIZE",(0,0),(-1,-1),8),("PADDING",(0,0),(-1,-1),4)]))
    story.append(firma)

    doc.build(story)
    return ruta_pdf

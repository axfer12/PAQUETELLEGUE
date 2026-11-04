# factura_comercial.py
# Genera PDF de Factura Comercial para envíos internacionales
# VERSIÓN ACTUALIZADA: Incluye campos adicionales requeridos por FedEx:
#   - what_is_it      (¿Qué es?)
#   - material        (¿De qué está hecho?)
#   - manufactured_in (¿Dónde se fabricó?)
#   - intended_use    (¿Para qué es?)
#   - detailed_description (Descripción detallada)

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                 Paragraph, Spacer, HRFlowable)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import os
import datetime


def generar_pdf_factura(remitente: dict, destinatario: dict, productos: list,
                        output_path: str, numero_guia: str = "",
                        moneda: str = "USD") -> str:
    """
    Genera una factura comercial PDF para envíos internacionales.

    remitente / destinatario: dicts con claves:
        nombre, empresa, calle, ciudad, estado, cp, pais, telefono, email

    productos: lista de dicts con claves:
        description_es, description_en, quantity, unit_price, price, weight,
        hs_code, country_of_origin (o country_code),
        what_is_it          → ¿Qué es? (nuevo campo FedEx)
        material            → ¿De qué está hecho? (nuevo campo FedEx)
        manufactured_in     → ¿Dónde se fabricó? (nuevo campo FedEx)
        intended_use        → ¿Para qué es? (nuevo campo FedEx)
        detailed_description → Descripción detallada (nuevo campo FedEx)

    output_path: ruta completa del archivo PDF a generar
    numero_guia: número de rastreo (opcional)
    moneda: 'USD' por defecto
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=0.5*inch,
        leftMargin=0.5*inch,
        topMargin=0.5*inch,
        bottomMargin=0.5*inch,
    )

    styles = getSampleStyleSheet()
    style_normal = ParagraphStyle('Normal2', parent=styles['Normal'],
                                   fontSize=8, leading=10)
    style_bold   = ParagraphStyle('Bold2',   parent=styles['Normal'],
                                   fontSize=8, leading=10, fontName='Helvetica-Bold')
    style_title  = ParagraphStyle('Title2',  parent=styles['Normal'],
                                   fontSize=14, leading=16, fontName='Helvetica-Bold',
                                   alignment=TA_CENTER)
    style_small  = ParagraphStyle('Small2',  parent=styles['Normal'],
                                   fontSize=7, leading=9)
    style_small_bold = ParagraphStyle('SmallBold2', parent=styles['Normal'],
                                       fontSize=7, leading=9, fontName='Helvetica-Bold')

    # ─── HELPERS ────────────────────────────────────────────────────────────
    def _addr_block(label: str, d: dict) -> list:
        """Construye un bloque de dirección como lista de Paragraphs."""
        rows = [Paragraph(label, style_bold)]
        nombre  = str(d.get("nombre") or d.get("name") or "")
        empresa = str(d.get("empresa") or d.get("company") or "")
        calle   = str(d.get("calle") or d.get("street1") or d.get("street") or "")
        ciudad  = str(d.get("ciudad") or d.get("city") or "")
        estado  = str(d.get("estado") or d.get("state") or d.get("area_level1") or "")
        cp      = str(d.get("cp") or d.get("postal_code") or "")
        pais    = str(d.get("pais") or d.get("country") or d.get("country_code") or "")
        tel     = str(d.get("telefono") or d.get("phone") or "")
        email   = str(d.get("email") or "")

        if nombre:  rows.append(Paragraph(nombre,  style_normal))
        if empresa: rows.append(Paragraph(empresa, style_normal))
        if calle:   rows.append(Paragraph(calle,   style_normal))
        line = ", ".join(filter(None, [ciudad, estado, cp]))
        if line:    rows.append(Paragraph(line,    style_normal))
        if pais:    rows.append(Paragraph(pais,    style_normal))
        if tel:     rows.append(Paragraph(f"Tel: {tel}", style_normal))
        if email:   rows.append(Paragraph(f"Email: {email}", style_normal))
        return rows

    # ─── CONTENIDO ──────────────────────────────────────────────────────────
    story = []

    # Título
    story.append(Paragraph("COMMERCIAL INVOICE / FACTURA COMERCIAL", style_title))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.black))
    story.append(Spacer(1, 4))

    # Fecha + número de guía
    fecha_hoy = datetime.date.today().strftime("%d/%m/%Y")
    info_rows = [
        [Paragraph("Date / Fecha:", style_bold),
         Paragraph(fecha_hoy, style_normal),
         Paragraph("Tracking No. / No. Guía:", style_bold),
         Paragraph(str(numero_guia), style_normal)],
    ]
    info_tbl = Table(info_rows, colWidths=[1.4*inch, 2.0*inch, 1.8*inch, 2.0*inch])
    info_tbl.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(info_tbl)
    story.append(Spacer(1, 8))

    # Remitente / Destinatario lado a lado
    rem_block  = _addr_block("SHIPPER / REMITENTE:", remitente)
    dest_block = _addr_block("CONSIGNEE / DESTINATARIO:", destinatario)

    max_rows = max(len(rem_block), len(dest_block))
    # Rellenar con espacios para que tengan la misma longitud
    rem_block  += [Paragraph("", style_normal)] * (max_rows - len(rem_block))
    dest_block += [Paragraph("", style_normal)] * (max_rows - len(dest_block))

    addr_data = [[rem_block[i], dest_block[i]] for i in range(max_rows)]
    addr_tbl  = Table(addr_data, colWidths=[3.6*inch, 3.6*inch])
    addr_tbl.setStyle(TableStyle([
        ('VALIGN',       (0,0), (-1,-1), 'TOP'),
        ('LINEAFTER',    (0,0), (0,-1),  0.5, colors.grey),
        ('LEFTPADDING',  (1,0), (1,-1),  8),
        ('BOTTOMPADDING',(0,0), (-1,-1), 1),
    ]))
    story.append(addr_tbl)
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Spacer(1, 6))

    # ── Encabezado de la tabla de productos ──────────────────────────────────
    # Columnas principales
    col_header = [
        Paragraph("Qty", style_small_bold),
        Paragraph("Description ES\n/ EN", style_small_bold),
        Paragraph("¿Qué es?\nWhat is it?", style_small_bold),
        Paragraph("Material", style_small_bold),
        Paragraph("Made in", style_small_bold),
        Paragraph("Use /\nUso", style_small_bold),
        Paragraph("HS Code", style_small_bold),
        Paragraph("Unit Price", style_small_bold),
        Paragraph("Total", style_small_bold),
    ]

    # Anchos de columnas (total ~7.2 pulgadas disponibles)
    col_widths = [
        0.35*inch,  # Qty
        1.60*inch,  # Description ES/EN
        1.00*inch,  # ¿Qué es?
        0.80*inch,  # Material
        0.60*inch,  # Made in
        0.80*inch,  # Use
        0.65*inch,  # HS Code
        0.70*inch,  # Unit Price
        0.70*inch,  # Total
    ]

    prod_data  = [col_header]
    total_peso = 0.0
    total_valor= 0.0

    for p in productos:
        _qty          = int(p.get("quantity") or 1)
        _uprice       = float(p.get("unit_price") or p.get("price") or 0.0)
        _weight       = float(p.get("weight") or 0.0)
        _desc_es      = str(p.get("description_es") or p.get("description_en") or "Mercancía")
        _desc_en      = str(p.get("description_en") or p.get("description_es") or "General merchandise")
        _hs           = str(p.get("hs_code") or "")
        _origen       = str(p.get("country_of_origin") or p.get("country_code") or "MX")
        subtotal      = float(p.get("price") or (_uprice * _qty))

        # ── Nuevos campos FedEx ───────────────────────────────────────────
        _what_is_it   = str(p.get("what_is_it") or p.get("que_es") or "")
        _material     = str(p.get("material") or p.get("de_que_esta_hecho") or "")
        _made_in      = str(p.get("manufactured_in") or p.get("donde_se_fabrico")
                            or _origen or "MX")
        _intended_use = str(p.get("intended_use") or p.get("para_que_es") or "")
        _detail       = str(p.get("detailed_description") or p.get("descripcion_detallada") or "")

        # Si hay descripción detallada, incluirla debajo de la desc principal
        desc_cell_text = f"{_desc_es}"
        if _desc_en and _desc_en != _desc_es:
            desc_cell_text += f"\n{_desc_en}"
        if _detail:
            desc_cell_text += f"\n({_detail})"

        total_peso  += _weight * _qty
        total_valor += subtotal

        prod_data.append([
            Paragraph(str(_qty), style_small),
            Paragraph(desc_cell_text, style_small),
            Paragraph(_what_is_it, style_small),
            Paragraph(_material, style_small),
            Paragraph(_made_in, style_small),
            Paragraph(_intended_use, style_small),
            Paragraph(_hs, style_small),
            Paragraph(f"{moneda} {_uprice:,.2f}", style_small),
            Paragraph(f"{moneda} {subtotal:,.2f}", style_small),
        ])

    # Fila de totales
    prod_data.append([
        Paragraph("", style_small),
        Paragraph(f"TOTAL WEIGHT / PESO TOTAL: {total_peso:.2f} kg", style_small_bold),
        "", "", "", "", "",
        Paragraph("TOTAL:", style_small_bold),
        Paragraph(f"{moneda} {total_valor:,.2f}", style_small_bold),
    ])

    prod_tbl = Table(prod_data, colWidths=col_widths, repeatRows=1)
    prod_tbl.setStyle(TableStyle([
        # Encabezado
        ('BACKGROUND',   (0,0), (-1,0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR',    (0,0), (-1,0), colors.white),
        ('GRID',         (0,0), (-1,-1), 0.4, colors.grey),
        ('VALIGN',       (0,0), (-1,-1), 'TOP'),
        ('FONTSIZE',     (0,0), (-1,-1), 7),
        ('TOPPADDING',   (0,0), (-1,-1), 2),
        ('BOTTOMPADDING',(0,0), (-1,-1), 2),
        # Fila de totales
        ('BACKGROUND',   (0,-1), (-1,-1), colors.HexColor('#ecf0f1')),
        ('LINEABOVE',    (0,-1), (-1,-1), 1, colors.black),
        # Columnas numéricas alineadas a la derecha
        ('ALIGN',        (0,0), (0,-1), 'CENTER'),   # Qty
        ('ALIGN',        (7,0), (8,-1), 'RIGHT'),    # Precios
    ]))

    story.append(prod_tbl)
    story.append(Spacer(1, 12))

    # ── Declaración / Firma ──────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Spacer(1, 6))
    declaracion = (
        "I declare that the information provided in this invoice is true and correct "
        "and that the contents and their value as described are accurate. / "
        "Declaro que la información proporcionada en esta factura es verdadera y correcta "
        "y que el contenido y su valor son exactos."
    )
    story.append(Paragraph(declaracion, style_small))
    story.append(Spacer(1, 20))

    # Firma
    firma_data = [
        [Paragraph("___________________________", style_normal),
         Paragraph("___________________________", style_normal)],
        [Paragraph("Signature / Firma", style_small),
         Paragraph("Date / Fecha", style_small)],
    ]
    firma_tbl = Table(firma_data, colWidths=[3.6*inch, 3.6*inch])
    firma_tbl.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN',  (0,0), (-1,-1), 'CENTER'),
    ]))
    story.append(firma_tbl)

    doc.build(story)
    return output_path

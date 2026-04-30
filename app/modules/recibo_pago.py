"""
Módulo de Recibo de Pago — Sistema de Guías de Envío
Genera un ticket de recibo similar al de Estafeta:
  - Datos de la empresa
  - Número de ticket y fecha
  - Por cada guía: número, destinatario, servicio, medidas, peso, precio
  - Total general + IVA
  - Imprime en impresora de tickets (o la que elija el usuario)

Tamaño: 80mm de ancho (estándar térmico) o carta si no hay térmica.
"""

import os
import platform
import subprocess
import tempfile
from datetime import datetime, timezone, timedelta
_MX_TZ = timezone(timedelta(hours=-6))  # México Centro UTC-6
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm

# ─── Dimensiones ticket 80mm ──────────────────────────────────────
ANCHO_TICKET = 80 * mm   # 80mm ancho estándar
# Alto calculado dinámicamente según cuántas guías haya

MARGEN = 4 * mm
ANCHO_UTIL = ANCHO_TICKET - 2 * MARGEN

# ─── Tipografías ─────────────────────────────────────────────────
F_TITULO   = ("Helvetica-Bold",  10)
F_SUBTITULO = ("Helvetica-Bold",   9)
F_NORMAL   = ("Helvetica-Bold",    8)
F_SMALL    = ("Helvetica-Bold",    7)
F_GRANDE   = ("Helvetica-Bold",   11)


def _linea(c, x1, y, x2=None, ancho_pagina=None):
    """Dibuja una línea divisoria."""
    if x2 is None:
        x2 = (ancho_pagina or ANCHO_TICKET) - MARGEN
    c.setLineWidth(0.3)
    c.line(x1, y, x2, y)


def _separador(c, y, x_ini=None, ancho_pagina=None):
    """Línea de guiones estilo Estafeta."""
    x = x_ini or MARGEN
    x2 = (ancho_pagina or ANCHO_TICKET) - MARGEN
    c.setFont("Helvetica-Bold", 7.0)
    guiones = "-" * 48
    c.drawString(x, y, guiones[:int((x2 - x) / 4.2)])
    return y


def _texto(c, x, y, texto, fuente, tamano, centrado=False, ancho_pagina=None):
    """Dibuja texto con fuente dada. Retorna nueva y."""
    c.setFont(fuente, tamano)
    if centrado:
        cx = (ancho_pagina or ANCHO_TICKET) / 2
        c.drawCentredString(cx, y, str(texto))
    else:
        c.drawString(x, y, str(texto))
    return y - (tamano + 1.5)


def _wrap_text(c, x, y, texto, fuente, tamano, max_ancho):
    """Texto con wrapping automático. Retorna nueva y."""
    c.setFont(fuente, tamano)
    palabras = str(texto).split()
    linea_actual = ""
    for palabra in palabras:
        prueba = (linea_actual + " " + palabra).strip()
        if c.stringWidth(prueba, fuente, tamano) <= max_ancho:
            linea_actual = prueba
        else:
            if linea_actual:
                c.drawString(x, y, linea_actual)
                y -= (tamano + 1.5)
            linea_actual = palabra
    if linea_actual:
        c.drawString(x, y, linea_actual)
        y -= (tamano + 1.5)
    return y


def _fila_tabla(c, y, col1, col2, col3, col4, x_ini, anchos):
    """Dibuja una fila de 4 columnas en tabla."""
    c.setFont("Helvetica-Bold", 7.5)
    x = x_ini
    for texto, ancho in zip([col1, col2, col3, col4], anchos):
        c.drawString(x, y, str(texto)[:int(ancho / 4)])
        x += ancho
    return y - 8


# ══════════════════════════════════════════════════════════════════
# FUNCIÓN PRINCIPAL
# ══════════════════════════════════════════════════════════════════

def generar_recibo(guias: list, config: dict, ruta_pdf: str = None) -> str:
    """
    Genera el PDF del recibo de pago.

    guias: lista de dicts con datos de cada guía:
        numero_guia, carrier, servicio, destinatario_nombre,
        destinatario_ciudad, destinatario_estado, peso,
        largo, ancho, alto, contenido, precio_final,
        costo_proveedor (solo admin), referencia

    config: dict con datos de la empresa:
        empresa_nombre, empresa_rfc, empresa_telefono,
        empresa_direccion, empresa_ciudad, empresa_estado,
        empresa_cp, iva

    ruta_pdf: si None, usa un temporal

    Retorna: ruta al PDF generado
    """
    if not guias:
        raise ValueError("No hay guías para generar recibo")

    if ruta_pdf is None:
        fd, ruta_pdf = tempfile.mkstemp(suffix=".pdf", prefix="recibo_")
        os.close(fd)

    # ── Calcular altura necesaria ──────────────────────────────────
    # Logo/encabezado: ~55mm, por guía: ~70mm + insumos, pie: ~35mm
    total_insumos_lineas = sum(len(g.get("insumos") or []) for g in guias)
    alto_mm = 60 + len(guias) * 95 + total_insumos_lineas * 8 + 40 + 60  # +60mm para QR, +20mm extra por iva/seguro
    alto_mm = max(alto_mm, 120)
    alto_pagina = alto_mm * mm  # convertir a puntos ReportLab

    c = canvas.Canvas(ruta_pdf, pagesize=(ANCHO_TICKET, alto_pagina))
    PH = alto_pagina  # altura en puntos

    # ── Margen inicial desde arriba ───────────────────────────────
    y = PH - (3 * mm)

    # ══ ENCABEZADO CON LOGO ════════════════════════════════════════
    # Logo de PAQUETELLEGUE en alta resolución para impresión
    logo_insertado = False
    try:
        import os as _os
        # Preferir versión hi-res, fallback a versión estándar
        for _nombre in ("logo_ticket_hires.png", "logo_ticket.png", "logo.png"):
            logo_path = _os.path.join(
                _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
                "assets", _nombre)
            if _os.path.exists(logo_path):
                break

        if _os.path.exists(logo_path):
            from reportlab.lib.utils import ImageReader
            from PIL import Image as _Img

            pil = _Img.open(logo_path)
            # Escalar a 64mm de ancho manteniendo proporción — alta calidad
            logo_w  = 64 * mm
            ratio   = logo_w / pil.width
            logo_h  = pil.height * ratio
            x_logo  = (ANCHO_TICKET - logo_w) / 2

            # Usar ImageReader para mejor calidad en ReportLab
            ir = ImageReader(logo_path)
            c.drawImage(ir, x_logo, y - logo_h,
                        width=logo_w, height=logo_h,
                        preserveAspectRatio=True,
                        mask="auto")
            y -= (logo_h + 4)
            logo_insertado = True
    except Exception as e:
        pass

    if not logo_insertado:
        # Fallback: nombre en texto
        nombre_empresa = config.get("empresa_nombre", "PAQUETELLEGUE").upper()
        y = _texto(c, 0, y, nombre_empresa, *F_TITULO, centrado=True, ancho_pagina=ANCHO_TICKET)
        y -= 1

    # Subtítulo MULTIPAQUETERÍA
    y = _texto(c, 0, y, "MULTIPAQUETERIA",
               "Helvetica-Bold", 8.0, centrado=True, ancho_pagina=ANCHO_TICKET)
    y = _texto(c, 0, y, "Porque lo importante es que llegue.",
               "Helvetica-Bold", 7.0, centrado=True, ancho_pagina=ANCHO_TICKET)
    y -= 2

    rfc = config.get("empresa_rfc", "")
    if rfc:
        y = _texto(c, 0, y, f"R.F.C. {rfc}", *F_SMALL, centrado=True, ancho_pagina=ANCHO_TICKET)

    dir_empresa = config.get("empresa_direccion", "")
    if dir_empresa:
        y = _wrap_text(c, MARGEN, y, dir_empresa.upper(), "Helvetica-Bold", 7.0, ANCHO_UTIL)

    ciudad = config.get("empresa_ciudad", "")
    estado = config.get("empresa_estado", "")
    cp     = config.get("empresa_cp", "")
    if ciudad or estado:
        y = _texto(c, MARGEN, y, f"{ciudad.upper()}, {estado.upper()}  C.P. {cp}",
                   *F_SMALL)
    tel = config.get("empresa_telefono", "")
    if tel:
        y = _texto(c, MARGEN, y, f"TEL: {tel}", *F_SMALL)

    sucursal = config.get("empresa_sucursal", "")
    if sucursal:
        y -= 2
        y = _texto(c, MARGEN, y, f"SUC: {sucursal.upper()}", *F_SMALL)

    y -= 2
    _separador(c, y)
    y -= 6

    # ── Número de ticket, fecha, hora ─────────────────────────────
    ahora = datetime.now(_MX_TZ)
    num_ticket = ahora.strftime("TK%Y%m%d%H%M%S")
    fecha_str  = ahora.strftime("%d/%m/%Y")
    hora_str   = ahora.strftime("%H:%M:%S")

    y = _texto(c, MARGEN, y, f"NUMERO DE TICKET: {num_ticket}", *F_NORMAL)
    y = _texto(c, MARGEN, y, f"FECHA: {fecha_str}   HORA: {hora_str}", *F_NORMAL)
    y = _texto(c, MARGEN, y, f"GUIAS EN ESTE RECIBO: {len(guias)}", *F_NORMAL)

    _separador(c, y)
    y -= 6

    # ══ DETALLE POR GUÍA ══════════════════════════════════════════
    subtotal_general = 0.0

    for i, g in enumerate(guias):
        # Número de guía y rastreo
        num_guia  = g.get("numero_guia", "N/D")
        carrier   = (g.get("carrier", "") or "").upper()
        servicio  = (g.get("servicio", "") or g.get("tipo_servicio", "TERRESTRE")).upper()
        precio    = float(g.get("precio_final", g.get("precio_venta", 0)) or 0)
        subtotal_general += precio

        y = _texto(c, MARGEN, y, f"GUIA {i+1} DE {len(guias)}", *F_SUBTITULO)

        # Número de rastreo
        y = _texto(c, MARGEN, y, f"NO. GUIA: {num_guia}", *F_NORMAL)

        # Paquetería y servicio
        if carrier:
            y = _texto(c, MARGEN, y, f"PAQUETERIA: {carrier}", *F_NORMAL)
        y = _texto(c, MARGEN, y, f"SERVICIO: {servicio}", *F_NORMAL)

        # Destinatario
        dest_nombre = (g.get("destinatario_nombre", "") or "").upper()
        dest_ciudad = (g.get("destinatario_ciudad", "") or "").upper()
        dest_estado = (g.get("destinatario_estado", "") or "").upper()
        dest_cp     = g.get("destinatario_cp", "")

        y = _texto(c, MARGEN, y, "DESTINATARIO:", *F_SMALL)
        if dest_nombre:
            y = _wrap_text(c, MARGEN + 2, y, dest_nombre, "Helvetica-Bold", 7.5, ANCHO_UTIL - 2)
        if dest_ciudad:
            y = _texto(c, MARGEN, y, f"DESTINO: {dest_ciudad}, {dest_estado}", *F_SMALL)

        # Contenido y referencia
        contenido = (g.get("contenido", "PRODUCTO") or "PRODUCTO").upper()
        y = _texto(c, MARGEN, y, f"CONTENIDO: {contenido}", *F_SMALL)
        ref = g.get("referencia", "")
        if ref:
            y = _texto(c, MARGEN, y, f"REFERENCIA: {str(ref).upper()}", *F_SMALL)

        # Valor declarado
        val_dec = float(g.get("valor_declarado", 0) or 0)
        y = _texto(c, MARGEN, y, f"VALOR DECLARADO: ${val_dec:.2f}", *F_SMALL)

        # Peso
        peso = g.get("peso", 1)
        y = _texto(c, MARGEN, y, f"PESO: {peso} KG", *F_SMALL)

        # Medidas
        largo = g.get("largo", ""); ancho = g.get("ancho", ""); alto = g.get("alto", "")
        if largo or ancho or alto:
            y = _texto(c, MARGEN, y, "MEDIDAS:", *F_SMALL)
            if ancho: y = _texto(c, MARGEN, y, f"  {ancho} CMS ANCHO", *F_SMALL)
            if alto:  y = _texto(c, MARGEN, y, f"  {alto} CMS ALTO",  *F_SMALL)
            if largo: y = _texto(c, MARGEN, y, f"  {largo} CMS LARGO", *F_SMALL)

        y -= 3
        # Tabla precio
        anchos = [ANCHO_UTIL * 0.12, ANCHO_UTIL * 0.40, ANCHO_UTIL * 0.24, ANCHO_UTIL * 0.24]
        y = _fila_tabla(c, y, "CANT", "DESCRIPCION", "$UNITARIO", "$TOTAL",
                        MARGEN, anchos)
        _linea(c, MARGEN, y + 5, ancho_pagina=ANCHO_TICKET)
        y -= 2
        # Precio del envío (sin seguro)
        precio_envio = float(g.get("precio_venta", precio) or precio)
        costo_seguro = float(g.get("costo_seguro", 0) or 0)
        y = _fila_tabla(c, y, "1", servicio[:16], f"${precio_envio:.2f}", f"${precio_envio:.2f}",
                        MARGEN, anchos)
        # Línea del seguro si aplica
        if costo_seguro > 0:
            y = _fila_tabla(c, y, "1", "SEGURO 10%", f"${costo_seguro:.2f}", f"${costo_seguro:.2f}",
                            MARGEN, anchos)

        # Líneas de descuentos/promociones — soporta múltiples
        promos_lista = g.get("promos", [])
        if promos_lista:
            # Múltiples promos
            for prom in promos_lista:
                p_nombre = (prom.get("nombre") or prom.get("codigo") or "DESCUENTO").upper()[:16]
                p_desc   = float(prom.get("descuento", 0) or 0)
                if p_desc > 0:
                    y = _fila_tabla(c, y, "1", f"PROMO:{p_nombre}", f"-${p_desc:.2f}", f"-${p_desc:.2f}",
                                    MARGEN, anchos)
        else:
            # Compatibilidad con promo única antigua
            descuento = float(g.get("descuento", 0) or 0)
            if descuento > 0:
                promo_nombre = (g.get("promo_nombre") or "DESCUENTO").upper()[:16]
                y = _fila_tabla(c, y, "1", promo_nombre, f"-${descuento:.2f}", f"-${descuento:.2f}",
                                MARGEN, anchos)

        # ── Insumos / Embalaje ────────────────────────────────────
        insumos_guia = g.get("insumos", [])
        if insumos_guia:
            _separador(c, y); y -= 4
            y = _texto(c, MARGEN, y, "INSUMOS / EMBALAJE:", *F_SMALL)
            for ins in insumos_guia:
                nombre_ins = (ins.get("nombre") or "")[:18].upper()
                cant_ins   = int(ins.get("cantidad") or 1)
                pu_ins     = float(ins.get("precio_unitario") or 0)
                sub_ins    = float(ins.get("subtotal") or 0)
                y = _fila_tabla(c, y,
                                str(cant_ins),
                                nombre_ins,
                                f"${pu_ins:.2f}",
                                f"${sub_ins:.2f}",
                                MARGEN, anchos)
        y -= 3

        # Método de pago
        metodo_raw = g.get("metodo_pago", "efectivo") or "efectivo"
        metodos_label = {
            "efectivo":         "EFECTIVO",
            "tarjeta_debito":   "TARJETA DEBITO",
            "tarjeta_credito":  "TARJETA CREDITO",
            "transferencia":    "TRANSFERENCIA",
        }
        metodo_label = metodos_label.get(metodo_raw, metodo_raw.upper())
        y = _texto(c, MARGEN, y, f"FORMA DE PAGO: {metodo_label}", *F_SMALL)

        # Confirmación de terminal si aplica
        conf = g.get("confirmacion_terminal", "")
        if conf:
            y = _texto(c, MARGEN, y, f"NO. APROBACION: {conf}", *F_SMALL)

        y -= 2

        # Sub-totales
        iva_pct = float(config.get("iva", "0") or 0)
        if iva_pct > 0:
            iva = precio * iva_pct / 100
            subtotal_sin_iva = precio - iva
            c.setFont("Helvetica-Bold", 7.5)
            c.drawRightString(ANCHO_TICKET - MARGEN, y, f"SUBTOTAL: ${subtotal_sin_iva:.2f}")
            y -= 8
            c.drawRightString(ANCHO_TICKET - MARGEN, y, f"IVA ({iva_pct:.0f}%): ${iva:.2f}")
            y -= 8
        c.setFont("Helvetica-Bold", 8.0)
        c.drawRightString(ANCHO_TICKET - MARGEN, y, f"TOTAL: ${precio:.2f}")
        y -= 8

        _separador(c, y)
        y -= 6

    # ══ TOTALES GENERALES ═════════════════════════════════════════
    iva_pct = float(config.get("iva", "0") or 0)
    if iva_pct > 0:
        iva_total = subtotal_general * iva_pct / 100
        subtotal_sin_iva = subtotal_general - iva_total
        c.setFont("Helvetica-Bold", 8.0)
        c.drawRightString(ANCHO_TICKET - MARGEN, y, f"SUBTOTAL: ${subtotal_sin_iva:.2f}")
        y -= 9
        c.drawRightString(ANCHO_TICKET - MARGEN, y, f"IVA: ${iva_total:.2f}")
        y -= 9

    c.setFont("Helvetica-Bold", 10.0)
    c.drawRightString(ANCHO_TICKET - MARGEN, y, f"TOTAL: ${subtotal_general:.2f}")
    y -= 12

    # ── Forma de pago ──────────────────────────────────────────────
    forma_pago = config.get("forma_pago_default", "EFECTIVO")
    c.setFont("Helvetica-Bold", 7.5)
    c.drawString(MARGEN, y, f"FORMA DE PAGO: {forma_pago}")
    y -= 12

    _separador(c, y)
    y -= 8

    # ── Mensaje de pie ─────────────────────────────────────────────
    msg_pie = config.get("mensaje_recibo",
        "Conserve su recibo. Para rastrear su envio visite el sitio de la paqueteria.")
    y = _wrap_text(c, MARGEN, y, msg_pie.upper(), "Helvetica-Bold", 7.0, ANCHO_UTIL)
    y -= 4

    # ── Aviso de privacidad breve ──────────────────────────────────
    c.setFont("Helvetica-Bold", 6.5)
    aviso = ("Al utilizar nuestros servicios acepta nuestro "
             "aviso de privacidad.")
    y = _wrap_text(c, MARGEN, y, aviso.upper(), "Helvetica-Bold", 6.5, ANCHO_UTIL)

    y -= 8
    _separador(c, y)
    y -= 6

    # ── QR de rastreo ──────────────────────────────────────────────
    try:
        import qrcode as _qr
        from reportlab.lib.utils import ImageReader as _IR
        import io as _io

        tracking_base = config.get("tracking_url",
            "https://tracking.skydropx.com/es-MX/page/PAQUETELLEGUELORETO")

        for g in guias:
            num = g.get("numero_rastreo") or g.get("numero_guia","")
            if not num or num in ("SIN_NUM",""):
                continue
            url_rastreo = f"{tracking_base}?tracking_number={num}"

            qr = _qr.QRCode(version=1, box_size=3, border=2,
                             error_correction=_qr.constants.ERROR_CORRECT_M)
            qr.add_data(url_rastreo)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white")

            buf = _io.BytesIO()
            qr_img.save(buf, format="PNG")
            buf.seek(0)
            ir = _IR(buf)

            qr_size = 25 * mm
            x_qr = (ANCHO_TICKET - qr_size) / 2

            # Si no hay espacio, ajustar y para que siempre quepa
            if y - qr_size - 20 < 0:
                y = qr_size + 30  # forzar espacio mínimo

            c.setFont("Helvetica-Bold", 7)
            c.drawCentredString(ANCHO_TICKET / 2, y, "RASTREA TU ENVIO:")
            y -= 8
            c.drawImage(ir, x_qr, y - qr_size,
                        width=qr_size, height=qr_size,
                        preserveAspectRatio=True, mask="auto")
            y -= qr_size + 4
            c.setFont("Helvetica-Bold", 6)
            short = url_rastreo[:44] + ("..." if len(url_rastreo) > 44 else "")
            c.drawCentredString(ANCHO_TICKET / 2, y, short)
            y -= 6
            break
    except Exception:
        pass  # Sin qrcode el recibo sigue funcionando

    _separador(c, y)

    c.save()
    return ruta_pdf


# ══════════════════════════════════════════════════════════════════
# IMPRIMIR RECIBO
# ══════════════════════════════════════════════════════════════════

def listar_impresoras() -> list[str]:
    """
    Detecta impresoras instaladas sin win32print.
    Retorna lista de nombres de impresoras.
    """
    impresoras = []
    sistema = platform.system()
    try:
        if sistema == "Windows":
            # Método 1: subprocess con wmic (sin dependencias)
            try:
                out = subprocess.run(
                    ["wmic", "printer", "get", "name"],
                    capture_output=True, text=True, timeout=8
                )
                for line in out.stdout.splitlines():
                    name = line.strip()
                    if name and name.lower() != "name":
                        impresoras.append(name)
            except Exception:
                pass

            # Método 2: PowerShell como fallback
            if not impresoras:
                try:
                    out = subprocess.run(
                        ["powershell", "-Command",
                         "Get-Printer | Select-Object -ExpandProperty Name"],
                        capture_output=True, text=True, timeout=8
                    )
                    for line in out.stdout.splitlines():
                        name = line.strip()
                        if name:
                            impresoras.append(name)
                except Exception:
                    pass

            # Método 3: win32print si está disponible
            if not impresoras:
                try:
                    import win32print
                    for p in win32print.EnumPrinters(
                            win32print.PRINTER_ENUM_LOCAL |
                            win32print.PRINTER_ENUM_CONNECTIONS):
                        impresoras.append(p[2])
                except ImportError:
                    pass

        elif sistema in ("Linux", "Darwin"):
            try:
                out = subprocess.run(["lpstat", "-a"],
                                     capture_output=True, text=True, timeout=5)
                for line in out.stdout.splitlines():
                    name = line.split()[0] if line.strip() else None
                    if name:
                        impresoras.append(name)
            except Exception:
                pass

    except Exception:
        pass

    return impresoras or ["Impresora predeterminada del sistema"]


def imprimir_recibo(ruta_pdf: str, nombre_impresora: str = None) -> tuple:
    """
    Imprime el recibo. No requiere win32api.
    Retorna (ok: bool, mensaje: str)
    """
    if not os.path.exists(ruta_pdf):
        return False, "El archivo de recibo no existe"

    sistema = platform.system()
    try:
        if sistema == "Windows":
            # Método 1: SumatraPDF (silencioso, ideal para tickets)
            sumatra_paths = [
                r"C:\Program Files\SumatraPDF\SumatraPDF.exe",
                r"C:\Program Files (x86)\SumatraPDF\SumatraPDF.exe",
                os.path.expanduser(r"~\AppData\Local\SumatraPDF\SumatraPDF.exe"),
            ]
            for exe in sumatra_paths:
                if os.path.exists(exe):
                    cmd = [exe, "-print-to",
                           nombre_impresora or "default",
                           ruta_pdf]
                    subprocess.Popen(cmd)
                    return True, f"Imprimiendo en {nombre_impresora or 'impresora predeterminada'}"

            # Método 2: Adobe Reader
            adobe_paths = [
                r"C:\Program Files\Adobe\Acrobat DC\Acrobat\Acrobat.exe",
                r"C:\Program Files (x86)\Adobe\Acrobat Reader DC\Reader\AcroRd32.exe",
                r"C:\Program Files\Adobe\Acrobat Reader DC\Reader\AcroRd32.exe",
            ]
            for exe in adobe_paths:
                if os.path.exists(exe):
                    cmd = [exe, "/t", ruta_pdf]
                    if nombre_impresora:
                        cmd.append(nombre_impresora)
                    subprocess.Popen(cmd)
                    return True, "Imprimiendo con Adobe Reader"

            # Método 3: PowerShell (nativo Windows, sin dependencias)
            try:
                ps_cmd = f'Start-Process -FilePath "{ruta_pdf}" -Verb Print -Wait'
                subprocess.Popen(
                    ["powershell", "-WindowStyle", "Hidden",
                     "-Command", ps_cmd],
                    creationflags=subprocess.CREATE_NO_WINDOW
                    if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
                )
                return True, "Imprimiendo con impresora predeterminada"
            except Exception as e_ps:
                pass

            # Método 4: os.startfile (abre visor PDF del sistema)
            try:
                os.startfile(ruta_pdf, "print")
                return True, "Enviado al visor de impresion"
            except Exception:
                os.startfile(ruta_pdf)
                return True, "PDF abierto — imprime manualmente con Ctrl+P"

        elif sistema in ("Linux", "Darwin"):
            cmd = ["lp", ruta_pdf]
            if nombre_impresora and nombre_impresora != "Impresora predeterminada del sistema":
                cmd += ["-d", nombre_impresora]
            if sistema == "Linux":
                cmd += ["-o", "media=Custom.80x200mm", "-o", "fit-to-page"]
            subprocess.run(cmd, check=True, capture_output=True, timeout=10)
            return True, "Recibo enviado a impresora"

    except Exception as e:
        return False, f"Error al imprimir: {e}"

    return False, "No se pudo imprimir automaticamente"

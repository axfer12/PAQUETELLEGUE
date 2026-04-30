"""
Generador de guías de envío en PDF usando ReportLab.
Optimizado para etiqueta térmica 4x6 pulgadas (101.6mm x 152.4mm).
Fuente: Helvetica-Bold en todo. Colores: negro intenso + blanco puro.
"""
from reportlab.lib.pagesizes import landscape
from reportlab.lib.units import mm, inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.graphics.barcode import code128
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics import renderPDF
from reportlab.pdfgen import canvas as pdfcanvas
import os
from datetime import datetime


GUIAS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "guias_pdf")
os.makedirs(GUIAS_DIR, exist_ok=True)

LABEL_W = 4 * inch
LABEL_H = 6 * inch
MARGIN  = 4 * mm

# ── Paleta máximo contraste ───────────────────────────────────────
NEGRO     = colors.HexColor("#000000")
BLANCO    = colors.HexColor("#FFFFFF")
GRIS_CLARO = colors.HexColor("#EEEEEE")   # fondo sección paquete
GRIS_PIE  = colors.HexColor("#555555")    # texto pie de página


def generar_pdf_guia(guia: dict, config: dict) -> str:
    filename = f"guia_{guia['numero_guia']}.pdf"
    filepath = os.path.join(GUIAS_DIR, filename)
    empresa     = config.get("empresa_nombre", "Envíos")
    empresa_tel = config.get("empresa_telefono", "")
    c = pdfcanvas.Canvas(filepath, pagesize=(LABEL_W, LABEL_H))
    _dibujar_etiqueta(c, guia, empresa, empresa_tel)
    c.save()
    return filepath


def _dibujar_etiqueta(c, guia, empresa, empresa_tel):
    W, H = LABEL_W, LABEL_H
    M = MARGIN

    # ── Fondo blanco puro ─────────────────────────────────────────
    c.setFillColor(BLANCO)
    c.rect(0, 0, W, H, fill=1, stroke=0)

    # ── Borde exterior negro grueso ───────────────────────────────
    c.setStrokeColor(NEGRO)
    c.setLineWidth(2)
    c.rect(M, M, W - 2*M, H - 2*M, fill=0, stroke=1)

    cursor = H - M

    # ══ ENCABEZADO negro ══════════════════════════════════════════
    header_h = 18*mm
    c.setFillColor(NEGRO)
    c.rect(M, cursor - header_h, W - 2*M, header_h, fill=1, stroke=0)

    c.setFillColor(BLANCO)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(M + 3*mm, cursor - 7*mm, empresa[:30])

    c.setFont("Helvetica-Bold", 9)
    num = guia.get("numero_guia", "")
    c.drawRightString(W - M - 3*mm, cursor - 7*mm, num)

    tel_txt = f"Tel: {empresa_tel}" if empresa_tel else ""
    c.setFont("Helvetica-Bold", 8)
    c.drawString(M + 3*mm, cursor - 14*mm, tel_txt)

    servicio = guia.get("servicio", "")
    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(W - M - 3*mm, cursor - 14*mm, servicio[:28])

    cursor -= header_h

    # ══ CÓDIGO DE BARRAS ══════════════════════════════════════════
    barcode_h = 20*mm
    _sep(c, cursor, W, M, grueso=False)
    cursor -= 1

    try:
        barcode = code128.Code128(
            num,
            barHeight=barcode_h - 6*mm,
            barWidth=0.65,
            humanReadable=True,
            fontSize=8,
            fontName="Helvetica-Bold"
        )
        bw = barcode.width
        bx = (W - bw) / 2
        barcode.drawOn(c, bx, cursor - barcode_h + 3*mm)
    except Exception:
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(NEGRO)
        c.drawCentredString(W/2, cursor - barcode_h/2, num)

    cursor -= barcode_h

    # ══ DATOS DEL PAQUETE ═════════════════════════════════════════
    _sep(c, cursor, W, M, grueso=False)
    cursor -= 1

    pkg_h = 12*mm
    c.setFillColor(GRIS_CLARO)
    c.rect(M, cursor - pkg_h, W - 2*M, pkg_h, fill=1, stroke=0)

    peso  = guia.get("peso", 0)
    alto  = guia.get("alto", 0)
    ancho = guia.get("ancho", 0)
    largo = guia.get("largo", 0)
    cont  = guia.get("contenido", "") or ""

    c.setFillColor(NEGRO)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(M + 3*mm, cursor - 5*mm, "PESO:")
    c.drawString(M + 18*mm, cursor - 5*mm, f"{peso} kg")

    c.drawString(M + 38*mm, cursor - 5*mm, "DIM (cm):")
    c.drawString(M + 60*mm, cursor - 5*mm, f"{alto}x{ancho}x{largo}")

    c.drawString(M + 3*mm, cursor - 10*mm, "CONTENIDO:")
    c.setFont("Helvetica-Bold", 8)
    c.drawString(M + 28*mm, cursor - 10*mm, cont[:38])

    cursor -= pkg_h

    # ══ REMITENTE ═════════════════════════════════════════════════
    _sep(c, cursor, W, M, grueso=False)
    cursor -= 1
    cursor -= 2*mm

    c.setFillColor(NEGRO)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(M + 3*mm, cursor - 4*mm, "DE (REMITENTE):")

    c.setFont("Helvetica-Bold", 9)
    rem_nombre = (guia.get("remitente_nombre") or "")[:35]
    c.drawString(M + 3*mm, cursor - 11*mm, rem_nombre)

    c.setFont("Helvetica-Bold", 7)
    rem_dir    = guia.get("remitente_direccion") or ""
    rem_col    = guia.get("remitente_colonia") or ""
    rem_ciudad = guia.get("remitente_ciudad") or ""
    rem_estado = guia.get("remitente_estado") or ""
    rem_cp     = guia.get("remitente_cp") or ""
    rem_tel    = guia.get("remitente_telefono") or ""
    c.drawString(M + 3*mm, cursor - 17*mm, f"{rem_dir}, Col. {rem_col}"[:52])
    c.drawString(M + 3*mm, cursor - 22*mm, f"{rem_ciudad}, {rem_estado}  C.P. {rem_cp}   Tel: {rem_tel}"[:55])

    cursor -= 24*mm

    # ══ DESTINATARIO ══════════════════════════════════════════════
    _sep(c, cursor, W, M, grueso=True)
    cursor -= 2

    dest_h = 30*mm

    c.setFillColor(NEGRO)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(M + 3*mm, cursor - 4*mm, "PARA (DESTINATARIO):")

    dest_nombre = (guia.get("destinatario_nombre") or "")
    font_size = 12 if len(dest_nombre) < 22 else (10 if len(dest_nombre) < 30 else 9)
    c.setFont("Helvetica-Bold", font_size)
    c.drawString(M + 3*mm, cursor - 12*mm, dest_nombre[:38])

    dest_tel = (guia.get("destinatario_telefono") or "")
    if dest_tel:
        c.setFont("Helvetica-Bold", 9)
        c.drawRightString(W - M - 3*mm, cursor - 12*mm, f"Tel: {dest_tel}")

    c.setFont("Helvetica-Bold", 8)
    dest_dir = guia.get("destinatario_direccion") or ""
    dest_col = guia.get("destinatario_colonia") or ""
    c.drawString(M + 3*mm, cursor - 19*mm, f"{dest_dir}, Col. {dest_col}"[:52])

    dest_ciudad = guia.get("destinatario_ciudad") or ""
    dest_estado = guia.get("destinatario_estado") or ""
    dest_cp     = guia.get("destinatario_cp") or ""

    c.setFont("Helvetica-Bold", 10)
    c.drawString(M + 3*mm, cursor - 26*mm, f"{dest_ciudad}, {dest_estado}"[:35])
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(W - M - 3*mm, cursor - 26*mm, f"C.P. {dest_cp}")

    cursor -= dest_h

    # ══ PIE ═══════════════════════════════════════════════════════
    _sep(c, cursor, W, M, grueso=False)
    fecha = str(guia.get("creado_en", ""))[:16].replace("T", " ")
    c.setFont("Helvetica-Bold", 6)
    c.setFillColor(GRIS_PIE)
    c.drawString(M + 3*mm, M + 3*mm,
                 f"Generado: {fecha}  |  Conserve esta guía hasta recibir su envío")


def _sep(c, y, W, M, grueso=False):
    c.setStrokeColor(NEGRO)
    c.setLineWidth(1.5 if grueso else 0.8)
    c.line(M, y, W - M, y)


def imprimir_pdf(filepath: str, impresora: str = None):
    import platform, subprocess
    sistema = platform.system()
    try:
        if sistema == "Windows":
            readers = [
                r"C:\Program Files\Adobe\Acrobat DC\Acrobat\Acrobat.exe",
                r"C:\Program Files (x86)\Adobe\Acrobat Reader DC\Reader\AcroRd32.exe",
                r"C:\Program Files\Foxit Software\Foxit PDF Reader\FoxitPDFReader.exe",
                r"C:\Program Files\SumatraPDF\SumatraPDF.exe",
            ]
            reader_found = next((r for r in readers if os.path.exists(r)), None)
            if reader_found and impresora:
                subprocess.Popen([reader_found, "/t", filepath, impresora])
            elif reader_found:
                subprocess.Popen([reader_found, filepath])
            else:
                sumatras = [
                    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "SumatraPDF.exe"),
                    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools", "SumatraPDF.exe"),
                ]
                sumatra = next((s for s in sumatras if os.path.exists(s)), None)
                if sumatra and impresora:
                    subprocess.Popen([sumatra, "-print-to", impresora, filepath])
                elif sumatra:
                    subprocess.Popen([sumatra, "-print-to-default", filepath])
                else:
                    try:
                        ps_cmd = f'Start-Process -FilePath "{filepath}" -Verb {"PrintTo" if impresora else "Print"} {("-ArgumentList " + chr(34) + impresora + chr(34)) if impresora else ""} -Wait'
                        subprocess.Popen(["powershell", "-WindowStyle", "Hidden", "-Command", ps_cmd],
                                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    except Exception:
                        try:
                            import win32api
                            if impresora:
                                win32api.ShellExecute(0, "printto", filepath, f'"{impresora}"', ".", 0)
                            else:
                                win32api.ShellExecute(0, "print", filepath, None, ".", 0)
                        except Exception:
                            os.startfile(filepath)
        elif sistema in ("Linux", "Darwin"):
            cmd = ["lp", "-o", "media=Custom.4x6in", "-o", "fit-to-page", filepath]
            if impresora:
                cmd = ["lp", "-d", impresora, "-o", "media=Custom.4x6in", "-o", "fit-to-page", filepath]
            subprocess.run(cmd, check=True)
        return True, "Impresión enviada correctamente ✅"
    except Exception as e:
        return False, f"Error al imprimir: {e}"


def get_impresoras_sistema():
    import platform, subprocess
    sistema = platform.system()
    impresoras = []
    try:
        if sistema == "Windows":
            import win32print
            for p in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS):
                impresoras.append(p[2])
        elif sistema == "Linux":
            result = subprocess.run(["lpstat", "-a"], capture_output=True, text=True)
            for line in result.stdout.splitlines():
                impresoras.append(line.split()[0])
        elif sistema == "Darwin":
            result = subprocess.run(["lpstat", "-p"], capture_output=True, text=True)
            for line in result.stdout.splitlines():
                if line.startswith("printer"):
                    impresoras.append(line.split()[1])
    except Exception:
        impresoras = ["Impresora predeterminada del sistema"]
    return impresoras

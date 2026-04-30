from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from app.modules import database as db
import tempfile, os

bp = Blueprint("impresion", __name__)

@bp.route("/config")
@login_required
def config():
    cfg = db.get_config()
    impresora_termica  = cfg.get("impresora_termica", "")
    impresora_etiqueta = cfg.get("impresora_etiqueta", "")
    impresora_normal   = cfg.get("impresora_normal", "")
    return render_template("impresion/config.html",
                           impresora_termica=impresora_termica,
                           impresora_etiqueta=impresora_etiqueta,
                           impresora_normal=impresora_normal)

@bp.route("/guardar", methods=["POST"])
@login_required
def guardar():
    nombre = request.form.get("impresora_termica", "").strip()
    db.set_config("impresora_termica", nombre)
    return jsonify({"ok": True})

@bp.route("/test_qr")
def test_qr():
    """Endpoint de diagnóstico — verifica que qrcode funciona."""
    resultado = {}
    # 1. Verificar qrcode instalado
    try:
        import qrcode as _qr
        resultado["qrcode_instalado"] = True
        resultado["qrcode_version"] = _qr.__version__
    except Exception as e:
        resultado["qrcode_instalado"] = False
        resultado["qrcode_error"] = str(e)

    # 2. Verificar Pillow
    try:
        from PIL import Image
        resultado["pillow_instalado"] = True
        resultado["pillow_version"] = Image.__version__
    except Exception as e:
        resultado["pillow_instalado"] = False
        resultado["pillow_error"] = str(e)

    # 3. Generar QR de prueba
    try:
        import qrcode as _qr, io as _io, base64 as _b64
        qr = _qr.QRCode(version=1, box_size=4, border=2)
        qr.add_data("https://tracking.skydropx.com/es-MX/page/PAQUETELLEGUELORETO?tracking_number=TEST123")
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = _io.BytesIO()
        img.save(buf, format="PNG")
        b64 = _b64.b64encode(buf.getvalue()).decode()
        resultado["qr_generado"] = True
        resultado["qr_b64_len"] = len(b64)
        # Retornar HTML con la imagen para verla directamente
        html = f"""<html><body style="background:#fff;text-align:center;padding:20px">
        <h2>✅ QR funcionando</h2>
        <p>qrcode v{resultado.get('qrcode_version','?')} | Pillow v{resultado.get('pillow_version','?')}</p>
        <img src="data:image/png;base64,{b64}" style="width:200px;height:200px"/>
        <p style="font-size:12px">Escanea para verificar</p>
        <pre style="font-size:11px;text-align:left">{resultado}</pre>
        </body></html>"""
        from flask import Response
        return Response(html, mimetype="text/html")
    except Exception as e:
        resultado["qr_generado"] = False
        resultado["qr_error"] = str(e)

    from flask import jsonify
    return jsonify(resultado)


@bp.route("/recibo_raw/<int:guia_id>")
@login_required
def recibo_raw(guia_id):
    """Retorna el recibo como texto ESC/POS listo para QZ Tray"""
    conn = db.get_connection()
    ph = db._ph()
    _cur = conn.cursor()
    _cur.execute(f"SELECT * FROM guias WHERE id={ph}", (guia_id,))
    row = _cur.fetchone()
    conn.close()
    if not row:
        return jsonify({"ok": False, "error": "Guia no encontrada"})
    g      = dict(row)
    cfg    = db.get_config()
    metodo = request.args.get("metodo_pago", g.get("metodo_pago","efectivo"))
    conf   = request.args.get("confirmacion", g.get("confirmacion_terminal",""))

    empresa = cfg.get("empresa_nombre","PAQUETELLEGUE")
    tel     = cfg.get("empresa_telefono","")
    dir_    = cfg.get("empresa_direccion","")
    ciudad  = cfg.get("empresa_ciudad","")
    msg     = cfg.get("mensaje_recibo","Gracias por su preferencia")
    iva_pct = float(cfg.get("iva","0") or 0)

    # Insumos de esta guía
    insumos_guia = db.get_insumos_de_guia(guia_id)
    total_insumos = sum(float(i.get("subtotal") or 0) for i in insumos_guia)
    precio_envio  = float(g.get("precio_final") or 0) - total_insumos
    precio_total  = float(g.get("precio_final") or 0)
    seguro  = float(g.get("costo_seguro") or 0)

    sep  = "-" * 42
    sep2 = "=" * 42

    def center(txt, w=42):
        return txt.center(w)
    def lr(left, right, w=42):
        gap = w - len(left) - len(right)
        return left + " " * max(1, gap) + right

    lines = [
        center(empresa),
        center("Multipaqueteria"),
    ]
    if tel:   lines.append(center("Tel: " + tel))
    if dir_:  lines.append(center(dir_))
    if ciudad: lines.append(center(ciudad))
    lines += [
        sep2,
        center("RECIBO DE PAGO"),
        sep2,
        lr("Guia:", g.get("numero_guia","") or ""),
        lr("Fecha:", (g.get("creado_en","") or "")[:16]),
        sep,
        center("-- SERVICIO DE ENVIO --"),
        sep,
        lr("Destinatario:", ""),
        "  " + (g.get("destinatario_nombre","") or ""),
        "  " + (g.get("destinatario_ciudad","") or "") + ", " + (g.get("destinatario_estado","") or ""),
        lr("Servicio:", (g.get("servicio","") or "")[:25]),
        lr("Peso:", str(g.get("peso","")) + " kg"),
        lr("Contenido:", (g.get("contenido","") or "")[:20]),
    ]
    if seguro > 0:
        lines.append(lr("Seguro:", "$%.2f" % seguro))
    lines.append(lr("Subtotal envio:", "$%.2f" % precio_envio))

    # Insumos — sección separada si hay
    if insumos_guia:
        lines += [
            sep,
            center("-- INSUMOS / EMBALAJE --"),
            sep,
        ]
        for ins in insumos_guia:
            nombre_ins = (ins.get("nombre") or "")[:28]
            cant       = int(ins.get("cantidad") or 1)
            subtotal   = float(ins.get("subtotal") or 0)
            lines.append(lr(f"  {nombre_ins} x{cant}", "$%.2f" % subtotal))
        lines.append(lr("Subtotal insumos:", "$%.2f" % total_insumos))

    lines += [sep]
    if iva_pct > 0:
        base    = precio_total / (1 + iva_pct/100)
        iva_amt = precio_total - base
        lines += [
            lr("Subtotal:", "$%.2f" % base),
            lr("IVA (%.0f%%):" % iva_pct, "$%.2f" % iva_amt),
        ]
    lines += [
        lr("TOTAL:", "$%.2f MXN" % precio_total),
        lr("Metodo pago:", metodo.upper()),
    ]
    if conf:
        lines.append(lr("Aprobacion:", conf))
    # QR de rastreo — URL para escanear
    tracking_base = cfg.get("tracking_url",
        "https://tracking.skydropx.com/es-MX/page/PAQUETELLEGUELORETO")
    num_rastreo = g.get("numero_rastreo") or g.get("numero_guia","")
    qr_url = ""
    if num_rastreo and num_rastreo not in ("SIN_NUM",""):
        qr_url = f"{tracking_base}?tracking_number={num_rastreo}"

    lines += [sep2, center(msg)]
    if qr_url:
        lines += [
            "",
            center("-- RASTREA TU ENVIO --"),
            center(qr_url[:42]),
        ]
    lines += ["", "", ""]

    # Generar QR como base64 para QZ Tray
    qr_b64 = ""
    if qr_url:
        try:
            import qrcode as _qr, io as _io, base64 as _b64
            qr = _qr.QRCode(version=1, box_size=4, border=2,
                            error_correction=_qr.constants.ERROR_CORRECT_M)
            qr.add_data(qr_url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = _io.BytesIO()
            img.save(buf, format="PNG")
            qr_b64 = _b64.b64encode(buf.getvalue()).decode()
        except Exception:
            pass

    return jsonify({"ok": True, "lines": lines, "empresa": empresa,
                    "qr_url": qr_url, "qr_b64": qr_b64})


@bp.route("/guia_pdf_b64/<int:guia_id>")
@login_required
def guia_pdf_b64(guia_id):
    """Retorna el PDF de la guia en base64 para QZ Tray"""
    import base64
    conn = db.get_connection()
    ph = db._ph()
    _cur = conn.cursor()
    _cur.execute(f"SELECT label_url, numero_guia FROM guias WHERE id={ph}", (guia_id,))
    row = _cur.fetchone()
    conn.close()
    if not row or not row["label_url"]:
        return jsonify({"ok": False, "error": "Sin URL de etiqueta"})
    from app.modules import api_proveedor as api
    try:
        pdf_bytes = api.descargar_guia_pdf(row["label_url"])
        b64 = base64.b64encode(pdf_bytes).decode("utf-8")
        return jsonify({"ok": True, "b64": b64, "numero_guia": row["numero_guia"]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@bp.route("/config_etiqueta", methods=["POST"])
@login_required
def config_etiqueta():
    nombre = request.form.get("impresora_etiqueta","").strip()
    db.set_config("impresora_etiqueta", nombre)
    return jsonify({"ok": True})


@bp.route("/invoice_pdf/<int:guia_id>")
@login_required
def invoice_pdf(guia_id):
    """Genera y retorna la factura comercial PDF para una guia internacional"""
    import base64, json
    conn = db.get_connection()
    ph = db._ph()
    _cur = conn.cursor()
    _cur.execute(f"SELECT * FROM guias WHERE id={ph}", (guia_id,))
    row = _cur.fetchone()
    conn.close()
    if not row:
        return jsonify({"ok": False, "error": "Guia no encontrada"})
    g = dict(row)

    # Reconstruir remitente y destinatario
    remitente = {
        "nombre":    g.get("remitente_nombre",""),
        "direccion": g.get("remitente_direccion",""),
        "colonia":   g.get("remitente_colonia",""),
        "ciudad":    g.get("remitente_ciudad",""),
        "estado":    g.get("remitente_estado",""),
        "cp":        g.get("remitente_cp",""),
        "pais":      "MX",
        "telefono":  g.get("remitente_telefono",""),
    }
    destinatario = {
        "nombre":    g.get("destinatario_nombre",""),
        "direccion": g.get("destinatario_direccion",""),
        "colonia":   g.get("destinatario_colonia",""),
        "ciudad":    g.get("destinatario_ciudad",""),
        "estado":    g.get("destinatario_estado",""),
        "cp":        g.get("destinatario_cp",""),
        "pais":      g.get("destinatario_pais","US"),
        "telefono":  g.get("destinatario_telefono",""),
    }

    # Productos desde JSON guardado o construir uno genérico
    productos_raw = g.get("productos_factura_json","") or ""
    try:
        productos = json.loads(productos_raw) if productos_raw else []
    except Exception:
        productos = []

    if not productos:
        # Fallback: un producto genérico con los datos del envío
        productos = [{
            "description_en": g.get("contenido","Merchandise"),
            "quantity":       1,
            "price":          float(g.get("valor_declarado") or g.get("precio_final") or 10),
            "weight":         float(g.get("peso") or 1),
            "hs_code":        "9999.99",
            "country_code":   "MX",
        }]

    purpose = g.get("shipment_purpose","personal") or "personal"

    from app.modules import factura_comercial as fc
    try:
        ruta = fc.generar_pdf_factura(remitente, destinatario, productos, purpose)
        with open(ruta, "rb") as f_:
            data = f_.read()
        import os as _os
        _os.unlink(ruta)
        b64 = base64.b64encode(data).decode("utf-8")
        return jsonify({"ok": True, "b64": b64,
                        "numero_guia": g.get("numero_guia","")})
    except Exception as e:
        import traceback
        return jsonify({"ok": False, "error": str(e),
                        "trace": traceback.format_exc()})

@bp.route("/invoice_download/<int:guia_id>")
@login_required
def invoice_download(guia_id):
    """Descarga directa del invoice como PDF"""
    import json
    conn = db.get_connection()
    ph = db._ph()
    _cur = conn.cursor()
    _cur.execute(f"SELECT * FROM guias WHERE id={ph}", (guia_id,))
    row = _cur.fetchone()
    conn.close()
    if not row:
        return "Guia no encontrada", 404
    g = dict(row)
    remitente = {
        "nombre": g.get("remitente_nombre",""), "direccion": g.get("remitente_direccion",""),
        "colonia": g.get("remitente_colonia",""), "ciudad": g.get("remitente_ciudad",""),
        "estado": g.get("remitente_estado",""), "cp": g.get("remitente_cp",""),
        "pais": "MX", "telefono": g.get("remitente_telefono",""),
    }
    destinatario = {
        "nombre": g.get("destinatario_nombre",""), "direccion": g.get("destinatario_direccion",""),
        "colonia": g.get("destinatario_colonia",""), "ciudad": g.get("destinatario_ciudad",""),
        "estado": g.get("destinatario_estado",""), "cp": g.get("destinatario_cp",""),
        "pais": g.get("destinatario_pais","US"), "telefono": g.get("destinatario_telefono",""),
    }
    try:
        productos = json.loads(g.get("productos_factura_json","") or "[]")
    except Exception:
        productos = []
    if not productos:
        productos = [{"description_en": g.get("contenido","Merchandise"), "quantity":1,
                      "price": float(g.get("valor_declarado") or 10), "weight": float(g.get("peso") or 1),
                      "hs_code":"9999.99","country_code":"MX"}]
    from app.modules import factura_comercial as fc
    from flask import send_file
    from io import BytesIO
    ruta = fc.generar_pdf_factura(remitente, destinatario, productos, g.get("shipment_purpose","personal") or "personal")
    with open(ruta,"rb") as f_:
        data = f_.read()
    import os as _os; _os.unlink(ruta)
    return send_file(BytesIO(data), mimetype="application/pdf",
                     download_name=f"invoice_{g.get('numero_guia','')}.pdf")

@bp.route("/config_normal", methods=["POST"])
@login_required
def config_normal():
    nombre = request.form.get("impresora_normal","").strip()
    db.set_config("impresora_normal", nombre)
    return jsonify({"ok": True})

from flask import Blueprint, render_template, request, jsonify, send_file, flash, redirect, url_for
from flask_login import login_required, current_user
from app.modules import database as db
import os, tempfile

bp = Blueprint("guias", __name__)


@bp.route("/nueva")
@login_required
def nueva():
    config = db.get_config_sucursal(current_user.sucursal_id)
    return render_template("guias/nueva_guia.html", config=config)


@bp.route("/historial")
@login_required
def historial():
    filtro    = request.args.get("q", "")
    fecha_ini = request.args.get("desde", "") or None
    fecha_fin = request.args.get("hasta", "") or None
    # TODOS los usuarios ven TODAS las guías de su sucursal
    # sin importar quién las generó — así LULU ve las del admin también
    sid = None if current_user.is_admin_global else (current_user.sucursal_id or None)
    guias = db.get_guias(filtro=filtro, fecha_ini=fecha_ini,
                         fecha_fin=fecha_fin, operario_id=None,
                         sucursal_id=sid)
    return render_template("guias/historial.html", guias=guias, filtro=filtro)


@bp.route("/guia/<int:guia_id>")
@login_required
def detalle(guia_id):
    conn = db.get_connection()
    cur = conn.cursor(); ph = db._ph(); cur.execute(f"SELECT * FROM guias WHERE id={ph}", (guia_id,)); row = cur.fetchone()
    conn.close()
    if not row:
        flash("Guia no encontrada", "error")
        return redirect(url_for("guias.historial"))
    g = dict(row)
    config = db.get_config_sucursal(g.get("sucursal_id") or current_user.sucursal_id)
    return render_template("guias/detalle.html", guia=g, config=config)


@bp.route("/guia/<int:guia_id>/pdf_oficial")
@login_required
def pdf_oficial(guia_id):
    conn = db.get_connection()
    cur = conn.cursor(); ph = db._ph(); cur.execute(f"SELECT * FROM guias WHERE id={ph}", (guia_id,)); row = cur.fetchone()
    conn.close()
    if not row:
        return "Guia no encontrada", 404
    g = dict(row)
    label_url   = g.get("label_url", "") or ""
    shipment_id = g.get("shipment_id_proveedor", "") or ""
    numero_guia = g.get("numero_guia", "guia") or "guia"
    from app.modules import api_proveedor as api

    def _fetch_fresh_label_url(sid):
        """Consulta Skydropx y extrae la label_url actualizada para un shipment_id."""
        try:
            r = api._request("GET", f"/shipments/{sid}")
            data  = r.get("data", r)
            attrs = data.get("attributes", data) if isinstance(data, dict) else {}
            url = (attrs.get("label_url") or attrs.get("label") or "")
            if not url:
                for inc in r.get("included", []):
                    if inc.get("type") == "package":
                        ia = inc.get("attributes", {})
                        url = ia.get("label_url") or ia.get("label") or ""
                        if url: break
            return url
        except Exception:
            return ""

    def _guardar_label_url(nuevo_url):
        """Actualiza label_url en BD."""
        try:
            conn2, cur2, ph2 = db.get_conn()
            cur2.execute(f"UPDATE guias SET label_url={ph2} WHERE id={ph2}", (nuevo_url, guia_id))
            conn2.commit(); conn2.close()
        except Exception:
            pass

    # Si no hay label_url en BD, intentar obtenerla desde Skydropx
    if not label_url and shipment_id:
        label_url = _fetch_fresh_label_url(shipment_id)
        if label_url:
            _guardar_label_url(label_url)

    if not label_url:
        return """<html><body style='font-family:sans-serif;padding:40px;text-align:center'>
            <h2>⚠️ Sin PDF disponible</h2>
            <p>Esta guía no tiene URL de etiqueta guardada.</p>
            <p>Número de guía: <strong>{}</strong></p>
            <p>Si la guía fue generada, búscala directamente en
            <a href='https://pro.skydropx.com' target='_blank'>pro.skydropx.com</a></p>
            </body></html>""".format(numero_guia), 404

    # Intentar descargar — si da 404 la URL expiró, re-obtener fresca desde Skydropx
    import sys
    for _intento in range(2):
        try:
            pdf_bytes = api.descargar_guia_pdf(label_url)
            from io import BytesIO
            return send_file(BytesIO(pdf_bytes), mimetype="application/pdf",
                             download_name=f"guia_{numero_guia}.pdf")
        except Exception as e:
            err_str = str(e)
            es_404 = "404" in err_str or "Not Found" in err_str or "not found" in err_str.lower()
            print(f"[PDF_OFICIAL] intento={_intento+1} guia={guia_id} 404={es_404} url={label_url[:60]}: {err_str[:120]}", file=sys.stderr, flush=True)
            if es_404 and _intento == 0 and shipment_id:
                # URL caducada — obtener URL fresca de Skydropx y reintentar
                nueva_url = _fetch_fresh_label_url(shipment_id)
                if nueva_url and nueva_url != label_url:
                    label_url = nueva_url
                    _guardar_label_url(label_url)
                    continue  # reintentar con nueva URL
            # Sin más reintentos o no es 404 — mostrar error
            return f"""<html><body style='font-family:sans-serif;padding:40px;text-align:center'>
                <h2>⚠️ Error descargando PDF</h2>
                <p>No fue posible descargar la etiqueta de la paquetería.</p>
                <p>N° de guía: <strong>{numero_guia}</strong></p>
                <p style='color:#aaa;font-size:13px'>{err_str[:200]}</p>
                <p>Intenta descargarla directamente en
                <a href='https://pro.skydropx.com' target='_blank'>pro.skydropx.com</a></p>
                </body></html>""", 500
            break


@bp.route("/guia/<int:guia_id>/factura_comercial_pdf")
@login_required
def factura_comercial_pdf(guia_id):
    """
    Descarga la Factura Comercial PDF de un envío internacional.
    Si el PDF ya fue generado y está guardado en pdf_path, lo sirve directamente.
    Si no, lo genera al vuelo desde los datos de la guía.
    """
    conn = db.get_connection()
    cur = conn.cursor(); ph = db._ph(); cur.execute(f"SELECT * FROM guias WHERE id={ph}", (guia_id,)); row = cur.fetchone()
    conn.close()
    if not row:
        return "Guia no encontrada", 404
    g = dict(row)
    numero_guia = g.get("numero_guia", "guia") or "guia"

    # Intentar servir el PDF ya guardado
    pdf_path = g.get("pdf_path") or ""
    if pdf_path and os.path.isfile(pdf_path):
        from io import BytesIO
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        return send_file(BytesIO(pdf_bytes), mimetype="application/pdf",
                         download_name=f"factura_comercial_{numero_guia}.pdf")

    # Regenerar al vuelo desde los datos de la guía
    import json as _json
    productos_raw = []
    try:
        productos_raw = _json.loads(g.get("productos_factura_json") or "[]") or []
    except Exception:
        pass

    if not productos_raw:
        return """<html><body style='font-family:sans-serif;padding:40px;text-align:center'>
            <h2>⚠️ Sin productos registrados</h2>
            <p>Esta guía no tiene productos de factura comercial guardados.</p>
            <p>Número de guía: <strong>{}</strong></p>
            </body></html>""".format(numero_guia), 404

    try:
        from app.modules.factura_comercial import generar_pdf_factura
        from app import modules as db_mod

        rem_fc = {
            "nombre":   g.get("remitente_nombre",""),
            "calle":    g.get("remitente_direccion",""),
            "colonia":  g.get("remitente_colonia",""),
            "ciudad":   g.get("remitente_ciudad",""),
            "estado":   g.get("remitente_estado",""),
            "cp":       g.get("remitente_cp",""),
            "pais":     "MX",
            "telefono": g.get("remitente_telefono",""),
        }
        dest_fc = {
            "nombre":   g.get("destinatario_nombre",""),
            "calle":    g.get("destinatario_direccion",""),
            "colonia":  g.get("destinatario_colonia",""),
            "ciudad":   g.get("destinatario_ciudad",""),
            "estado":   g.get("destinatario_estado",""),
            "cp":       g.get("destinatario_cp",""),
            "pais":     g.get("destinatario_pais","US"),
            "telefono": g.get("destinatario_telefono",""),
        }
        # Normalizar productos
        contenido_fb = g.get("contenido","General merchandise")
        prods_norm = []
        for _p in productos_raw:
            _desc_en = str(_p.get("description_en") or _p.get("descripcion") or contenido_fb)
            _desc_es = str(_p.get("description_es") or _desc_en)
            _qty     = int(_p.get("quantity") or 1)
            _uprice  = float(_p.get("unit_price") or _p.get("price") or 1.0)
            _weight  = float(_p.get("weight") or _p.get("peso") or round(float(g.get("peso",1))/_qty, 3))
            _hs      = str(_p.get("hs_code") or "")
            _origen  = str(_p.get("country_of_origin") or _p.get("country_code") or "MX").upper()
            prods_norm.append({
                "description_es":    _desc_es,
                "description_en":    _desc_en,
                "hs_code":           _hs,
                "quantity":          _qty,
                "unit_price":        _uprice,
                "price":             round(_uprice * _qty, 2),
                "weight":            _weight,
                "country_of_origin": _origen,
            })

        pdf_path_nuevo = generar_pdf_factura(
            remitente=rem_fc,
            destinatario=dest_fc,
            productos=prods_norm,
            purpose=g.get("shipment_purpose","commercial"),
        )
        # Guardar ruta para próximas descargas
        try:
            conn2 = db.get_connection()
            cur2 = conn2.cursor(); ph2 = db._ph()
            cur2.execute(f"UPDATE guias SET pdf_path={ph2} WHERE id={ph2}", (pdf_path_nuevo, guia_id))
            conn2.commit(); conn2.close()
        except Exception:
            pass

        from io import BytesIO
        with open(pdf_path_nuevo, "rb") as f:
            pdf_bytes = f.read()
        return send_file(BytesIO(pdf_bytes), mimetype="application/pdf",
                         download_name=f"factura_comercial_{numero_guia}.pdf")
    except Exception as e:
        return f"Error generando Factura Comercial: {e}", 500


@bp.route("/guia/<int:guia_id>/recibo_pdf")
@login_required
def recibo_pdf(guia_id):
    conn = db.get_connection()
    cur = conn.cursor(); ph = db._ph(); cur.execute(f"SELECT * FROM guias WHERE id={ph}", (guia_id,)); row = cur.fetchone()
    conn.close()
    if not row:
        return "Guia no encontrada", 404
    g = dict(row)
    g["metodo_pago"]           = request.args.get("metodo_pago", "efectivo")
    g["confirmacion_terminal"] = request.args.get("confirmacion", "")
    # Separar carrier y servicio del campo combinado
    partes = g.get("servicio", "").split("—")
    g["carrier"]  = partes[0].strip() if len(partes) > 1 else ""
    g["servicio"] = partes[-1].strip()

    from app.modules import recibo_pago as rp
    # Usar config de la sucursal que generó la guía
    sucursal_id_guia = g.get("sucursal_id") or (current_user.sucursal_id if hasattr(current_user, 'sucursal_id') else 1)
    config = db.get_config_sucursal(sucursal_id_guia)
    insumos_guia = db.get_insumos_de_guia(guia_id)
    g["insumos"] = insumos_guia
    # Agregar nombre de la promoción si aplica
    if g.get("promocion_id"):
        try:
            conn2 = db.get_connection()
            cur2 = conn2.cursor(); ph2 = db._ph()
            cur2.execute(f"SELECT nombre FROM promociones WHERE id={ph2}", (g["promocion_id"],))
            prow = cur2.fetchone()
            conn2.close()
            if prow:
                g["promo_nombre"] = dict(prow)["nombre"]
        except:
            pass
    # promos acumuladas (se pasan por query param como JSON)
    import json as _json
    promos_json = request.args.get("promos", "")
    if promos_json:
        try:
            g["promos"] = _json.loads(promos_json)
        except:
            pass
    try:
        fd, ruta = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        rp.generar_recibo([g], config, ruta)
        from io import BytesIO
        with open(ruta, "rb") as f:
            data = f.read()
        os.unlink(ruta)
        return send_file(BytesIO(data), mimetype="application/pdf",
                         download_name=f"recibo_{g['numero_guia']}.pdf")
    except Exception as e:
        import traceback
        return f"Error generando recibo: {e}<br><pre>{traceback.format_exc()}</pre>", 500


@bp.route("/guia/<int:guia_id>/recibo")
@login_required
def recibo(guia_id):
    conn = db.get_connection()
    cur = conn.cursor(); ph = db._ph(); cur.execute(f"SELECT * FROM guias WHERE id={ph}", (guia_id,)); row = cur.fetchone()
    conn.close()
    if not row:
        flash("Guia no encontrada", "error")
        return redirect(url_for("guias.historial"))
    g = dict(row)
    config = db.get_config_sucursal(g.get("sucursal_id") or current_user.sucursal_id)
    return render_template("guias/recibo.html", guia=g, config=config)

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
    solo_op   = None if current_user.is_supervisor else current_user.id
    sid = None if current_user.is_admin_global else current_user.sucursal_id
    guias = db.get_guias(filtro=filtro, fecha_ini=fecha_ini,
                         fecha_fin=fecha_fin, operario_id=solo_op,
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

    # Intentar obtener label_url desde Skydropx si no está guardado
    if not label_url and shipment_id:
        try:
            r = api._request("GET", f"/shipments/{shipment_id}")
            data  = r.get("data", r)
            attrs = data.get("attributes", data) if isinstance(data, dict) else {}
            label_url = (attrs.get("label_url") or attrs.get("label") or "")
            if not label_url:
                for inc in r.get("included", []):
                    if inc.get("type") == "package":
                        ia = inc.get("attributes", {})
                        label_url = ia.get("label_url") or ia.get("label") or ""
                        if label_url: break
            # Guardar en BD para próximas veces
            if label_url:
                conn2, cur2, ph2 = db.get_conn()
                cur2.execute(f"UPDATE guias SET label_url={ph2} WHERE id={ph2}", (label_url, guia_id))
                conn2.commit(); conn2.close()
        except Exception:
            pass

    if not label_url:
        return """<html><body style='font-family:sans-serif;padding:40px;text-align:center'>
            <h2>⚠️ Sin PDF disponible</h2>
            <p>Esta guía no tiene URL de etiqueta guardada.</p>
            <p>Número de guía: <strong>{}</strong></p>
            <p>Si la guía fue generada, búscala directamente en 
            <a href='https://pro.skydropx.com' target='_blank'>pro.skydropx.com</a></p>
            </body></html>""".format(numero_guia), 404

    try:
        pdf_bytes = api.descargar_guia_pdf(label_url)
        from io import BytesIO
        return send_file(BytesIO(pdf_bytes), mimetype="application/pdf",
                         download_name=f"guia_{numero_guia}.pdf")
    except Exception as e:
        return f"Error descargando PDF: {e}", 500


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

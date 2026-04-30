"""
cancelaciones.py — Solicitudes de cancelación con autorización supervisor/admin
Flujo:
  1. Operario solicita desde historial o detalle de guía
  2. Supervisor aprueba por PIN inmediato O desde cola de pendientes
  3. Se ejecuta la eliminación definitiva
"""
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app.modules import database as db

bp = Blueprint("cancelaciones", __name__)


# ── API: crear solicitud ─────────────────────────────────────────────────────

@bp.route("/api/solicitar_cancelacion", methods=["POST"])
@login_required
def solicitar():
    d      = request.get_json() or {}
    tipo   = d.get("tipo")          # 'guia' | 'insumo_guia'
    ref_id = d.get("referencia_id")
    motivo = d.get("motivo","").strip()

    if not tipo or not ref_id or not motivo:
        return jsonify({"ok": False, "error": "Faltan datos"}), 400

    # Descripción legible
    if tipo == "guia":
        conn, cur, ph = db.get_conn()
        cur.execute(f"SELECT numero_guia, destinatario_nombre FROM guias WHERE id={ph}", (ref_id,))
        row = cur.fetchone()
        conn.close()
        if not row:
            return jsonify({"ok": False, "error": "Guía no encontrada"}), 404
        num  = row[0] if not hasattr(row,'keys') else row['numero_guia']
        dest = row[1] if not hasattr(row,'keys') else row['destinatario_nombre']
        desc = f"Guía #{num} — {dest}"
    elif tipo == "insumo_guia":
        conn, cur, ph = db.get_conn()
        cur.execute(f"""
            SELECT i.nombre, gi.cantidad, g.numero_guia
            FROM guia_insumos gi
            JOIN insumos i ON gi.insumo_id=i.id
            JOIN guias g ON gi.guia_id=g.id
            WHERE gi.id={ph}
        """, (ref_id,))
        row = cur.fetchone()
        conn.close()
        if not row:
            return jsonify({"ok": False, "error": "Insumo no encontrado"}), 404
        nombre = row[0] if not hasattr(row,'keys') else row['nombre']
        cant   = row[1] if not hasattr(row,'keys') else row['cantidad']
        nguia  = row[2] if not hasattr(row,'keys') else row['numero_guia']
        desc   = f"Insumo: {nombre} ×{cant} en guía #{nguia}"
    else:
        return jsonify({"ok": False, "error": "Tipo inválido"}), 400

    ok, result = db.crear_solicitud_cancelacion(tipo, ref_id, desc, motivo, current_user.id, sucursal_id=current_user.sucursal_id)
    if not ok:
        return jsonify({"ok": False, "error": result}), 500

    return jsonify({"ok": True, "solicitud_id": result, "descripcion": desc})


# ── API: autorizar con PIN (inmediato) ────────────────────────────────────────

@bp.route("/api/autorizar_cancelacion_pin", methods=["POST"])
@login_required
def autorizar_pin():
    d            = request.get_json() or {}
    solicitud_id = d.get("solicitud_id")
    pin          = d.get("pin","").strip()

    if not solicitud_id or not pin:
        return jsonify({"ok": False, "error": "Faltan datos"}), 400

    # Verificar PIN
    supervisor = db.verificar_supervisor_pin(pin)
    if not supervisor:
        return jsonify({"ok": False, "error": "PIN incorrecto"}), 403

    solicitud = db.get_solicitud(solicitud_id)
    if not solicitud:
        return jsonify({"ok": False, "error": "Solicitud no encontrada"}), 404
    if solicitud["estatus"] != "pendiente":
        return jsonify({"ok": False, "error": "Solicitud ya resuelta"}), 400

    # Aprobar y ejecutar eliminación
    db.resolver_solicitud(solicitud_id, supervisor["id"], aprobar=True)
    ok, msg = _ejecutar_cancelacion(solicitud)
    if not ok:
        return jsonify({"ok": False, "error": msg}), 500

    return jsonify({"ok": True, "msg": f"Autorizado por {supervisor['nombre']}. {msg}"})


# ── Vista: cola de solicitudes pendientes (supervisor/admin) ──────────────────

@bp.route("/cancelaciones")
@login_required
def lista():
    if not current_user.is_supervisor and not current_user.is_admin:
        flash("Acceso no autorizado", "error")
        return redirect(url_for("guias.historial"))
    sid = None if current_user.is_admin_global else current_user.sucursal_id
    pendientes = db.get_solicitudes_pendientes(sucursal_id=sid)
    return render_template("cancelaciones/lista.html", pendientes=pendientes)


@bp.route("/cancelaciones/<int:sid>/resolver", methods=["POST"])
@login_required
def resolver(sid):
    if not current_user.is_supervisor and not current_user.is_admin:
        return jsonify({"ok": False, "error": "No autorizado"}), 403

    accion = request.form.get("accion")  # 'aprobar' | 'rechazar'
    if accion not in ("aprobar", "rechazar"):
        flash("Acción inválida", "error")
        return redirect(url_for("cancelaciones.lista"))

    solicitud = db.get_solicitud(sid)
    if not solicitud or solicitud["estatus"] != "pendiente":
        flash("Solicitud no encontrada o ya resuelta", "error")
        return redirect(url_for("cancelaciones.lista"))

    aprobar = (accion == "aprobar")
    db.resolver_solicitud(sid, current_user.id, aprobar)

    if aprobar:
        ok, msg = _ejecutar_cancelacion(solicitud)
        flash(f"✅ Aprobado y ejecutado: {msg}" if ok else f"⚠️ Aprobado pero error al ejecutar: {msg}",
              "success" if ok else "error")
    else:
        flash("❌ Solicitud rechazada", "warning")

    return redirect(url_for("cancelaciones.lista"))


# ── Configurar PIN propio (supervisor/admin) ──────────────────────────────────

@bp.route("/cuenta/pin", methods=["POST"])
@login_required
def set_pin():
    if not current_user.is_supervisor and not current_user.is_admin:
        return jsonify({"ok": False, "error": "No autorizado"}), 403
    pin = request.get_json().get("pin","").strip()
    if len(pin) < 4:
        return jsonify({"ok": False, "error": "El PIN debe tener al menos 4 dígitos"}), 400
    db.set_supervisor_pin(current_user.id, pin)
    return jsonify({"ok": True, "msg": "PIN actualizado"})


# ── Ejecución real de la cancelación ─────────────────────────────────────────

def _cancelar_en_proveedor(shipment_id, es_internacional):
    """Llama a la API del proveedor para cancelar el shipment."""
    import sys
    try:
        from app.modules import api_proveedor as api
        # Endpoint correcto: POST /shipments/{id}/cancellations (plural)
        if es_internacional:
            resp = api._ei_request("POST", f"/shipments/{shipment_id}/cancellations", data={})
        else:
            resp = api._request("POST", f"/shipments/{shipment_id}/cancellations", data={})
        print(f"[CANCEL] Proveedor resp: {resp}", file=sys.stderr)
        return True, "Cancelado en proveedor"
    except Exception as e:
        print(f"[CANCEL] Error proveedor: {e}", file=sys.stderr)
        return False, str(e)

def _ejecutar_cancelacion(solicitud):
    tipo   = solicitud["tipo"]
    ref_id = solicitud["referencia_id"]

    try:
        if tipo == "guia":
            conn, cur, ph = db.get_conn()
            # Obtener shipment_id y país para cancelar en proveedor
            cur.execute(f"""
                SELECT shipment_id_proveedor, destinatario_pais
                FROM guias WHERE id={ph}
            """, (ref_id,))
            row = cur.fetchone()
            shipment_id  = (row[0] if row and not hasattr(row,'keys') else (row['shipment_id_proveedor'] if row else None)) or ""
            dest_pais    = (row[1] if row and not hasattr(row,'keys') else (row['destinatario_pais'] if row else "MX")) or "MX"
            es_int       = dest_pais.upper() != "MX"

            # Cancelar en proveedor si hay shipment_id
            proveedor_msg = ""
            if shipment_id:
                ok_prov, proveedor_msg = _cancelar_en_proveedor(shipment_id, es_int)
                if not ok_prov:
                    proveedor_msg = f" (aviso: no se pudo cancelar en proveedor: {proveedor_msg})"
                else:
                    proveedor_msg = " + cancelado en proveedor"

            # Restaurar stock de insumos antes de borrar
            cur.execute(f"SELECT insumo_id, cantidad FROM guia_insumos WHERE guia_id={ph}", (ref_id,))
            for row in cur.fetchall():
                iid  = row[0] if not hasattr(row,'keys') else row['insumo_id']
                cant = row[1] if not hasattr(row,'keys') else row['cantidad']
                cur.execute(f"UPDATE insumos SET stock=stock+{ph} WHERE id={ph}", (cant, iid))
            # Borrar insumos de la guía
            cur.execute(f"DELETE FROM guia_insumos WHERE guia_id={ph}", (ref_id,))
            # Borrar guía
            cur.execute(f"DELETE FROM guias WHERE id={ph}", (ref_id,))
            conn.commit()
            conn.close()
            return True, f"Guía eliminada{proveedor_msg}"

        elif tipo == "insumo_guia":
            conn, cur, ph = db.get_conn()
            # Obtener datos para restaurar stock y ajustar precio_final
            cur.execute(f"""
                SELECT gi.insumo_id, gi.cantidad, gi.subtotal, gi.guia_id
                FROM guia_insumos gi WHERE gi.id={ph}
            """, (ref_id,))
            row = cur.fetchone()
            if not row:
                conn.close()
                return False, "Registro de insumo no encontrado"
            iid      = row[0] if not hasattr(row,'keys') else row['insumo_id']
            cant     = row[1] if not hasattr(row,'keys') else row['cantidad']
            subtotal = row[2] if not hasattr(row,'keys') else row['subtotal']
            guia_id  = row[3] if not hasattr(row,'keys') else row['guia_id']
            # Restaurar stock
            cur.execute(f"UPDATE insumos SET stock=stock+{ph} WHERE id={ph}", (cant, iid))
            # Ajustar precio_final de la guía
            cur.execute(f"UPDATE guias SET precio_final=precio_final-{ph} WHERE id={ph}", (subtotal, guia_id))
            # Borrar registro
            cur.execute(f"DELETE FROM guia_insumos WHERE id={ph}", (ref_id,))
            conn.commit()
            conn.close()
            return True, "Insumo removido de la guía y stock restaurado"

    except Exception as e:
        return False, str(e)

    return False, "Tipo desconocido"


@bp.route("/api/eliminar_directo/<int:guia_id>", methods=["POST"])
@login_required
def eliminar_directo(guia_id):
    """Admin elimina directamente sin solicitud."""
    if not current_user.is_admin:
        return jsonify({"ok": False, "error": "Solo administradores"}), 403
    solicitud_fake = {"tipo": "guia", "referencia_id": guia_id}
    ok, msg = _ejecutar_cancelacion(solicitud_fake)
    return jsonify({"ok": ok, "msg": msg})

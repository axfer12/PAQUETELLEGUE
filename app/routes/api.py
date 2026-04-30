from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.modules import api_proveedor as api
from app.modules import database as db
import traceback, os, json

bp = Blueprint("api", __name__)

@bp.route("/cotizar", methods=["POST"])
@login_required
def cotizar():
    d = request.get_json(force=True) or {}
    try:
        rates = api.cotizar_envio(
            cp_origen=d.get("cp_origen",""), cp_destino=d.get("cp_destino",""),
            peso=float(d.get("peso",1)), alto=float(d.get("alto",10)),
            ancho=float(d.get("ancho",10)), largo=float(d.get("largo",10)),
            pais_origen=d.get("pais_origen","MX"), pais_destino=d.get("pais_destino","MX"),
            estado_origen=d.get("estado_origen",""),  ciudad_origen=d.get("ciudad_origen",""),
            colonia_origen=d.get("colonia_origen",""),
            estado_destino=d.get("estado_destino",""), ciudad_destino=d.get("ciudad_destino",""),
            colonia_destino=d.get("colonia_destino",""),
            contenido=d.get("contenido","Mercancia"),
            valor_declarado=float(d.get("valor_declarado",100)),
        )
        config = db.get_config_sucursal(current_user.sucursal_id)
        markup_raw = config.get("markup_json","30") or "30"
        # Parsear markup — soporta número simple o JSON {nacional, internacional}
        try:
            import json as _json
            _m = _json.loads(markup_raw)
            if isinstance(_m, dict):
                pct_nac  = float(_m.get("nacional",  _m.get("default", {}).get("porcentaje", 30)))
                pct_int  = float(_m.get("internacional", pct_nac))
            else:
                pct_nac = pct_int = float(_m)
        except:
            try: pct_nac = pct_int = float(markup_raw)
            except: pct_nac = pct_int = 30.0
        for r in rates:
            pp  = r["precio"]
            # Internacional = destino diferente a MX
            _es_int = d.get("pais_destino","MX").upper() != "MX"
            pct = pct_int if _es_int else pct_nac
            r["precio_proveedor"] = pp
            r["precio_venta"] = round(pp * (1 + pct/100), 2)
        return jsonify({"ok": True, "rates": rates})
    except api.APIError as e:
        msg = str(e)
        _sin_saldo = any(k in msg.lower() for k in ("saldo insuficiente","balance","credito","crédito","credit","insufficient","funds","payment required","wallet"))
        if _sin_saldo:
            return jsonify({"ok": False, "error": msg, "tipo": "sin_creditos"}), 400
        return jsonify({"ok": False, "error": msg}), 400
    except Exception as e:
        tb = traceback.format_exc()
        print("ERROR COTIZAR:", tb, flush=True)
        return jsonify({"ok": False, "error": str(e), "trace": tb}), 500

@bp.route("/generar_guia", methods=["POST"])
@login_required
def generar_guia():
    d = request.get_json(force=True) or {}
    try:
        rem = d["remitente"]; dest = d["destinatario"]
        paq = d["paquete"];   rate = d["rate"]
        metodo = d.get("metodo_pago","efectivo")
        conf   = d.get("confirmacion_terminal","")
        con_seg = d.get("con_seguro", False)
        precio_venta = float(rate.get("precio_venta",0))
        precio_prov  = float(rate.get("precio_proveedor", rate.get("precio",0)))
        descuento    = float(d.get("descuento",0))
        costo_seguro = 0.0
        if con_seg:
            try: costo_seguro = round(float(paq.get("valor_declarado",100))*0.10, 2)
            except: pass
        precio_final = round(precio_venta - descuento + costo_seguro, 2)

        import sys
        print(f"[RATE SELECCIONADO] {rate}", flush=True, file=sys.stderr)

        # Validar que el rate sea válido (success != false)
        if rate.get("success") is False:
            return jsonify({"ok": False, "error": "La tarifa seleccionada no está disponible. Por favor cotiza de nuevo y selecciona una tarifa válida."}), 400

        envio = api.crear_envio(
            quotation_id=rate["quotation_id"], rate_id=rate["rate_id"],
            remitente=rem, destinatario=dest, paquete=paq,
            contenido=paq.get("contenido") or d.get("contenido") or "Mercancia",
            customs_payment_payer=d.get("customs_payment_payer","recipient"),
            shipment_purpose=d.get("shipment_purpose","personal"),
            printing_format=rate.get("printing_format","letter"),
        )
        # Si Skydropx aún procesa, guardar en BD como "en_espera" y regresar pending
        if envio.get("pending"):
            # Guardar en BD con estatus en_espera para que no se pierda
            cliente_id = d.get("cliente_id") or None
            if not cliente_id:
                cs = db.get_clientes(rem.get("nombre",""), sucursal_id=current_user.sucursal_id)
                if cs:
                    row0 = cs[0]; cliente_id = (dict(row0) if not isinstance(row0, dict) else row0).get("id") or row0[0]
                else:
                    cliente_id = db.guardar_cliente({"nombre":rem.get("nombre",""),"telefono":rem.get("telefono",""),"direccion":rem.get("calle",""),"colonia":rem.get("colonia",""),"ciudad":rem.get("ciudad",""),"estado":rem.get("estado",""),"cp":rem.get("cp",""),"sucursal_id":current_user.sucursal_id})
            import uuid
            num_temporal = f"EN_ESPERA_{envio['shipment_id']}"
            data_pendiente = {
                "numero_guia": num_temporal, "cliente_id": cliente_id, "operario_id": current_user.id,
                "servicio": f"{rate.get('carrier','')} — {rate.get('servicio',rate.get('service',''))}",
                "remitente_nombre": rem.get("nombre",""), "remitente_telefono": rem.get("telefono",""),
                "remitente_direccion": rem.get("calle",""), "remitente_colonia": rem.get("colonia",""),
                "remitente_ciudad": rem.get("ciudad",""), "remitente_estado": rem.get("estado",""),
                "remitente_cp": rem.get("cp",""),
                "destinatario_nombre": dest.get("nombre",""), "destinatario_telefono": dest.get("telefono",""),
                "destinatario_direccion": dest.get("calle",""), "destinatario_colonia": dest.get("colonia",""),
                "destinatario_ciudad": dest.get("ciudad",""), "destinatario_estado": dest.get("estado",""),
                "destinatario_cp": dest.get("cp",""),
                "peso": paq.get("peso",1), "alto": paq.get("alto",10), "ancho": paq.get("ancho",10), "largo": paq.get("largo",10),
                "contenido": paq.get("contenido") or d.get("contenido") or "Mercancia",
                "costo_proveedor": precio_prov, "precio_venta": precio_venta, "descuento": descuento,
                "precio_final": precio_final, "costo_seguro": costo_seguro, "metodo_pago": metodo,
                "confirmacion_terminal": conf, "promocion_id": d.get("promo_id"),
                "shipment_id_proveedor": envio["shipment_id"], "label_url": "",
                "productos_factura_json": __import__("json").dumps((d.get("paquete") or {}).get("productos_factura") or []),
                "destinatario_pais": d.get("destinatario",{}).get("pais","MX"),
                "shipment_purpose": d.get("shipment_purpose","personal"),
                "numero_rastreo": "", "pdf_path": None,
                "estatus": "en_espera", "status": "en_espera",
            }
            guia_bd = db.crear_guia(data_pendiente)
            guia_id_bd = guia_bd["id"] if guia_bd else None
            return jsonify({"ok": True, "pending": True,
                            "shipment_id": envio["shipment_id"],
                            "guia_id": guia_id_bd,
                            "precio_final": precio_final,
                            "_ctx": {
                                "rem": rem, "dest": dest, "paq": paq,
                                "precio_prov": precio_prov, "precio_venta": precio_venta,
                                "descuento": descuento, "precio_final": precio_final,
                                "costo_seguro": costo_seguro, "metodo": metodo, "conf": conf,
                                "cliente_id": cliente_id, "promo_id": d.get("promo_id"),
                                "operario_id": current_user.id,
                                "guia_id_bd": guia_id_bd,
                                "productos_factura_json": __import__("json").dumps((d.get("paquete") or {}).get("productos_factura") or []),
                                "destinatario_pais": d.get("destinatario",{}).get("pais","MX"),
                                "shipment_purpose": d.get("shipment_purpose","personal"),
                            }})

        if con_seg and costo_seguro > 0:
            try: api.proteger_envio(envio["shipment_id"], float(paq.get("valor_declarado",100)))
            except: pass

        cliente_id = d.get("cliente_id") or None
        if not cliente_id:
            cs = db.get_clientes(rem.get("nombre",""), sucursal_id=current_user.sucursal_id)
            if cs:
                row0 = cs[0]; cliente_id = (dict(row0) if not isinstance(row0, dict) else row0).get("id") or row0[0]
            else:  cliente_id = db.guardar_cliente({"nombre":rem.get("nombre",""),"telefono":rem.get("telefono",""),"direccion":rem.get("calle",""),"colonia":rem.get("colonia",""),"ciudad":rem.get("ciudad",""),"estado":rem.get("estado",""),"cp":rem.get("cp",""),"sucursal_id":current_user.sucursal_id})

        num_guia = envio.get("numero_rastreo") or envio.get("tracking_number") or envio.get("shipment_id","SIN_NUM")
        data_guia = {
            "numero_guia": num_guia, "cliente_id": cliente_id, "operario_id": current_user.id,
            "servicio": f"{envio.get(chr(39)+'carrier'+chr(39),chr(39)+chr(39))} — {envio.get(chr(39)+'servicio'+chr(39),chr(39)+chr(39))}",
            "remitente_nombre": rem.get("nombre",""), "remitente_telefono": rem.get("telefono",""),
            "remitente_direccion": rem.get("calle",""), "remitente_colonia": rem.get("colonia",""),
            "remitente_ciudad": rem.get("ciudad",""), "remitente_estado": rem.get("estado",""),
            "remitente_cp": rem.get("cp",""),
            "destinatario_nombre": dest.get("nombre",""), "destinatario_telefono": dest.get("telefono",""),
            "destinatario_direccion": dest.get("calle",""), "destinatario_colonia": dest.get("colonia",""),
            "destinatario_ciudad": dest.get("ciudad",""), "destinatario_estado": dest.get("estado",""),
            "destinatario_cp": dest.get("cp",""),
            "peso": paq.get("peso",1), "alto": paq.get("alto",10), "ancho": paq.get("ancho",10), "largo": paq.get("largo",10),
            "contenido": paq.get("contenido") or d.get("contenido") or "Mercancia",
            "costo_proveedor": precio_prov, "precio_venta": precio_venta, "descuento": descuento,
            "precio_final": precio_final, "costo_seguro": costo_seguro, "metodo_pago": metodo,
            "confirmacion_terminal": conf, "promocion_id": d.get("promo_id"),
            "shipment_id_proveedor": envio.get("shipment_id",""), "label_url": envio.get("label_url",""),
            "productos_factura_json": __import__("json").dumps((d.get("paquete") or {}).get("productos_factura") or []),
            "destinatario_pais": d.get("destinatario",{}).get("pais","MX"),
            "shipment_purpose": d.get("shipment_purpose","personal"),
            "numero_rastreo": num_guia, "pdf_path": None,
            "sucursal_id": current_user.sucursal_id,
        }
        guia_bd = db.crear_guia(data_guia)
        return jsonify({"ok": True, "guia_id": guia_bd["id"] if guia_bd else None,
                        "numero_guia": num_guia, "label_url": envio.get("label_url",""),
                        "carrier": envio.get("carrier",""), "precio_final": precio_final, "costo_seguro": costo_seguro})
    except api.APIError as e:
        msg = str(e)
        _sin_saldo = any(k in msg.lower() for k in ("saldo insuficiente","balance","credito","crédito","credit","insufficient","funds","payment required","wallet"))
        if _sin_saldo:
            return jsonify({"ok": False, "error": msg, "tipo": "sin_creditos"}), 400
        return jsonify({"ok": False, "error": msg}), 400
    except (KeyError, TypeError, IndexError) as e:
        return jsonify({"ok": False, "error": f"Campo faltante: {e}", "trace": traceback.format_exc()}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()}), 500

@bp.route("/buscar-cp/<cp>")
@bp.route("/cp_info/<cp>")
@login_required
def buscar_cp(cp):
    from app.modules import cp_lookup as cpl
    pais = request.args.get("pais", "MX").upper()
    try: return jsonify(cpl.buscar_cp(cp, pais) or {})
    except: return jsonify({})

@bp.route("/clientes/buscar")
@login_required
def buscar_clientes():
    q = request.args.get("q","")
    if len(q) < 2:
        return jsonify([])
    # Admin global sin sucursal seleccionada ve todos
    sid = None if current_user.is_admin_global else current_user.sucursal_id
    try:
        return jsonify(db.get_clientes(q, sucursal_id=sid))
    except Exception as e:
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

@bp.route("/clientes/<int:cid>")
@login_required
def get_cliente(cid):
    c = db.get_cliente(cid)
    return jsonify(dict(c) if c else {})

@bp.route("/clientes", methods=["POST"])
@login_required
def crear_cliente_api():
    data = request.get_json(force=True) or {}
    data["sucursal_id"] = current_user.sucursal_id
    try:
        cid = db.guardar_cliente(data)
        return jsonify({"ok": True, "id": cid})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()}), 500

@bp.route("/promocion/validar", methods=["POST"])
@login_required
def validar_promocion():
    d = request.get_json(force=True) or {}
    codigo     = d.get("codigo", "")
    precio     = float(d.get("precio", 0))
    servicio   = d.get("servicio")
    cliente_id = d.get("cliente_id")
    if not codigo:
        return jsonify({"ok": False, "error": "Ingresa un código"})
    try:
        descuento, promo_id, nombre = db.aplicar_promocion(codigo, precio, servicio, cliente_id)
        if descuento > 0:
            return jsonify({"ok": True, "descuento": descuento, "promo_id": promo_id, "nombre": nombre})
        else:
            return jsonify({"ok": False, "error": "Código inválido o no aplica"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@bp.route("/verificar_skydropx")
@login_required
def verificar_skydropx():
    ok, msg = api.verificar_credenciales()
    return jsonify({"ok": ok, "mensaje": msg})


@bp.route("/rastrear/<tracking>")
@login_required
def rastrear(tracking):
    from app.modules import api_proveedor as api
    conn = db.get_connection()
    ph = db._ph()
    _cur = conn.cursor()
    _cur.execute(f"SELECT servicio FROM guias WHERE numero_rastreo={ph} OR numero_guia={ph}", (tracking, tracking))
    row = _cur.fetchone()
    conn.close()
    carrier = ""
    if row:
        partes  = (row["servicio"] or "").split("—")
        carrier = partes[0].strip() if len(partes) > 1 else ""
    try:
        data = api.rastrear_envio(tracking, carrier)
        return jsonify({"ok": True, "data": data})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@bp.route("/cancelar/<int:guia_id>", methods=["POST"])
@login_required
def cancelar(guia_id):
    conn = db.get_connection()
    ph = db._ph()
    _cur = conn.cursor()
    _cur.execute(f"SELECT * FROM guias WHERE id={ph}", (guia_id,))
    row = _cur.fetchone()
    conn.close()
    if not row:
        return jsonify({"ok": False, "error": "Guia no encontrada"})
    g = dict(row)
    shipment_id = g.get("shipment_id_proveedor","")
    if not shipment_id:
        return jsonify({"ok": False, "error": "Sin shipment_id para cancelar"})
    from app.modules import api_proveedor as api
    try:
        api._request("DELETE", f"/shipments/{shipment_id}")
        conn = db.get_connection()
        ph = db._ph()
        _cur = conn.cursor()
        _cur.execute(f"UPDATE guias SET estatus={ph} WHERE id={ph}", ("cancelada", guia_id))
        conn.commit()
        conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@bp.route("/shipment_status/<shipment_id>")
@login_required
def shipment_status(shipment_id):
    """Polling endpoint: consulta estado de un shipment en Skydropx o EI sin bloquear."""
    try:
        proveedor = request.args.get("proveedor", "sky")
        if proveedor == "ei":
            r = api._ei_request("GET", f"/shipments/{shipment_id}")
        else:
            r = api._request("GET", f"/shipments/{shipment_id}")
        data  = r.get("data", r)
        attrs = data.get("attributes", data) if isinstance(data, dict) else {}
        st    = attrs.get("workflow_status") or attrs.get("status") or ""
        trk   = (attrs.get("tracking_number") or attrs.get("tracking") or
                 attrs.get("master_tracking_number") or "")
        url   = (attrs.get("label_url") or attrs.get("label") or "")
        # Buscar tracking/label en included
        for inc in r.get("included", []):
            if inc.get("type") == "package":
                ia = inc.get("attributes", {})
                trk = trk or ia.get("tracking_number") or ia.get("tracking") or ""
                url = url or ia.get("label_url") or ia.get("label") or ""
        pending = st in ("in_progress", "pending", "waiting", "processing")
        return jsonify({"ok": True, "status": st, "pending": pending,
                        "tracking": trk, "label_url": url,
                        "carrier": attrs.get("carrier_name","").upper()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/completar_guia", methods=["POST"])
@login_required
def completar_guia():
    """Guarda la guía en BD después de que el shipment esté listo."""
    d = request.get_json(force=True) or {}
    try:
        ctx = d.get("_ctx", {})
        rem  = ctx.get("rem", {}); dest = ctx.get("dest", {}); paq = ctx.get("paq", {})
        num_guia = d.get("tracking") or d.get("shipment_id", "SIN_NUM")
        carrier  = d.get("carrier", "")
        servicio = d.get("servicio", "")
        cliente_id = ctx.get("cliente_id") or None
        if not cliente_id:
            cs = db.get_clientes(rem.get("nombre",""), sucursal_id=current_user.sucursal_id)
            if cs:
                row0 = cs[0]; cliente_id = (dict(row0) if not isinstance(row0, dict) else row0).get("id") or row0[0]
            else:
                cliente_id = db.guardar_cliente({"nombre": rem.get("nombre",""), "telefono": rem.get("telefono",""),
                    "direccion": rem.get("calle",""), "colonia": rem.get("colonia",""),
                    "ciudad": rem.get("ciudad",""), "estado": rem.get("estado",""), "cp": rem.get("cp",""),
                    "sucursal_id": current_user.sucursal_id})
        data_guia = {
            "numero_guia": num_guia, "cliente_id": cliente_id, "operario_id": ctx.get("operario_id", current_user.id),
            "servicio": f"{carrier} — {servicio}", "sucursal_id": current_user.sucursal_id,
            "remitente_nombre": rem.get("nombre",""), "remitente_telefono": rem.get("telefono",""),
            "remitente_direccion": rem.get("calle",""), "remitente_colonia": rem.get("colonia",""),
            "remitente_ciudad": rem.get("ciudad",""), "remitente_estado": rem.get("estado",""), "remitente_cp": rem.get("cp",""),
            "destinatario_nombre": dest.get("nombre",""), "destinatario_telefono": dest.get("telefono",""),
            "destinatario_direccion": dest.get("calle",""), "destinatario_colonia": dest.get("colonia",""),
            "destinatario_ciudad": dest.get("ciudad",""), "destinatario_estado": dest.get("estado",""), "destinatario_cp": dest.get("cp",""),
            "peso": paq.get("peso",1), "alto": paq.get("alto",10), "ancho": paq.get("ancho",10), "largo": paq.get("largo",10),
            "contenido": paq.get("contenido") or "Mercancia",
            "costo_proveedor": ctx.get("precio_prov",0), "precio_venta": ctx.get("precio_venta",0),
            "descuento": ctx.get("descuento",0), "precio_final": ctx.get("precio_final",0),
            "costo_seguro": ctx.get("costo_seguro",0), "metodo_pago": ctx.get("metodo","efectivo"),
            "confirmacion_terminal": ctx.get("conf",""), "promocion_id": ctx.get("promo_id"),
            "shipment_id_proveedor": d.get("shipment_id",""), "label_url": d.get("label_url",""),
            "productos_factura_json": ctx.get("productos_factura_json","[]"),
            "destinatario_pais": ctx.get("destinatario_pais","MX"),
            "shipment_purpose": ctx.get("shipment_purpose","personal"),
            "numero_rastreo": num_guia, "pdf_path": None,
        }
        guia_bd = db.crear_guia(data_guia)
        return jsonify({"ok": True, "guia_id": guia_bd["id"] if guia_bd else None,
                        "numero_guia": num_guia, "label_url": d.get("label_url",""),
                        "carrier": carrier, "precio_final": ctx.get("precio_final",0)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()}), 500


@bp.route("/guias_en_espera")
@login_required
def guias_en_espera():
    """Devuelve las guías con estatus en_espera para mostrar en UI."""
    try:
        conn, cur, ph = db.get_conn()
        cur.execute("""
            SELECT id, numero_guia, shipment_id_proveedor, servicio,
                   destinatario_nombre, destinatario_ciudad, precio_final, creado_en
            FROM guias WHERE estatus='en_espera' ORDER BY creado_en DESC LIMIT 20
        """)
        rows = cur.fetchall()
        guias = []
        for r in rows:
            g = dict(r) if hasattr(r,'keys') else {
                'id':r[0],'numero_guia':r[1],'shipment_id_proveedor':r[2],
                'servicio':r[3],'destinatario_nombre':r[4],
                'destinatario_ciudad':r[5],'precio_final':r[6],'creado_en':str(r[7])
            }
            guias.append(g)
        return jsonify({"ok": True, "guias": guias})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@bp.route("/actualizar_guia_espera/<int:guia_id>", methods=["POST"])
@login_required
def actualizar_guia_espera(guia_id):
    """Actualiza una guía en_espera cuando el polling del frontend completa."""
    d = request.get_json() or {}
    try:
        conn, cur, ph = db.get_conn()
        updates = {}
        if d.get("numero_guia"):
            updates["numero_guia"] = d["numero_guia"]
            updates["numero_rastreo"] = d["numero_guia"]
        if d.get("label_url"):
            updates["label_url"] = d["label_url"]
        if d.get("pdf_path"):
            updates["pdf_path"] = d["pdf_path"]
        updates["estatus"] = "activa"
        updates["status"] = "activa"

        if updates:
            sets = ", ".join([f"{k}={ph}" for k in updates.keys()])
            vals = list(updates.values()) + [guia_id]
            cur.execute(f"UPDATE guias SET {sets} WHERE id={ph}", vals)
            conn.commit()
        return jsonify({"ok": True, "guia_id": guia_id, "updates": updates})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@bp.route("/insumos")
@login_required
def listar_insumos():
    return jsonify(db.get_insumos(solo_activos=True))

@bp.route("/guia/<int:guia_id>/insumos", methods=["POST"])
@login_required
def guardar_insumos_guia(guia_id):
    items = request.get_json() or []
    db.guardar_guia_insumos(guia_id, items)
    # Actualizar precio_final sumando insumos
    total_insumos = sum(it.get('subtotal', 0) for it in items)
    if total_insumos > 0:
        conn, cur, ph = db.get_conn()
        cur.execute(f"SELECT precio_final FROM guias WHERE id={ph}", (guia_id,))
        row = cur.fetchone()
        if row:
            pf = float(row[0] if not hasattr(row,'keys') else row['precio_final'])
            cur.execute(f"UPDATE guias SET precio_final={ph} WHERE id={ph}",
                        (pf + total_insumos, guia_id))
            conn.commit()
        conn.close()
    return jsonify({"ok": True})

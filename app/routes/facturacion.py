"""
facturacion.py — Portal de auto-facturación CFDI 4.0
paquetellegue.shop/facturacion

Integración con factura.com API v4
"""
from flask import Blueprint, render_template, request, jsonify, send_file
import requests, json, datetime, re, os
from io import BytesIO

bp = Blueprint("facturacion", __name__, url_prefix="/facturacion")

# ── Credenciales factura.com (se cargan desde config/env) ────────
def _get_creds():
    from flask import current_app
    return {
        "api_key":    current_app.config.get("FACTURAMA_API_KEY", os.environ.get("FACTURAMA_API_KEY", "")),
        "secret_key": current_app.config.get("FACTURAMA_SECRET_KEY", os.environ.get("FACTURAMA_SECRET_KEY", "")),
    }

FACTURA_BASE = "https://api.factura.com/v4"
FACTURA_PLUGIN = "9d4095c8f7ed5785cb14c0e3b033eeb8252416ed"

def _headers():
    c = _get_creds()
    return {
        "Content-Type": "application/json",
        "F-PLUGIN":     FACTURA_PLUGIN,
        "F-Api-Key":    c["api_key"],
        "F-Secret-Key": c["secret_key"],
    }

# ── Usos de CFDI comunes ──────────────────────────────────────────
def _obtener_uid_cliente(rfc, razon, cp_fiscal, regimen, email):
    """
    Busca el cliente por RFC en factura.com.
    Si existe, actualiza el CP. Si no existe, lo crea.
    Retorna el UID.
    """
    import sys
    hdrs = _headers()

    # 1. Buscar cliente por RFC
    uid_existente = None
    try:
        r = requests.get(
            f"https://api.factura.com/v1/clients/{rfc}",
            headers=hdrs, timeout=15
        )
        print(f"[FACTURA] GET v1/clients/{rfc} status={r.status_code} body={r.text[:200]}", file=sys.stderr, flush=True)
        if r.status_code == 200 and r.text.strip() and r.text.strip()[0] == '{':
            data = r.json()
            uid_existente = (data.get("Data") or {}).get("UID") or (data.get("Data") or {}).get("uid")
    except Exception as e:
        print(f"[FACTURA] Error buscando cliente: {e}", file=sys.stderr, flush=True)

    if uid_existente:
        # Actualizar datos del cliente — factura.com usa POST a /clients/update/{uid}
        try:
            upd = requests.post(
                f"https://api.factura.com/v1/clients/{uid_existente}/update",
                headers=hdrs,
                json={"codpos": cp_fiscal, "rfc": rfc, "razons": razon,
                      "regimen": str(regimen), "email": email, "pais": "MEX"},
                timeout=15
            )
            print(f"[FACTURA] POST clients/{uid_existente}/update regimen={regimen} cp={cp_fiscal} status={upd.status_code} body={upd.text[:150]}", file=sys.stderr, flush=True)
        except Exception as e:
            print(f"[FACTURA] Warn actualizando cliente: {e}", file=sys.stderr, flush=True)
        return uid_existente

    # 2. Crear cliente
    payload_cliente = {
        "rfc": rfc, "razons": razon, "codpos": cp_fiscal,
        "email": email, "regimen": str(regimen), "pais": "MEX", "usocfdi": "G03",
    }
    print(f"[FACTURA] POST v1/clients/create rfc={rfc} cp={cp_fiscal}", file=sys.stderr, flush=True)
    try:
        r2 = requests.post(
            "https://api.factura.com/v1/clients/create",
            headers=hdrs, json=payload_cliente, timeout=15
        )
        print(f"[FACTURA] POST clients/create status={r2.status_code} body={r2.text[:300]}", file=sys.stderr, flush=True)
        if not r2.text.strip() or r2.text.strip()[0] != '{':
            raise Exception(f"Respuesta inválida ({r2.status_code})")
        data2 = r2.json()
        uid = (data2.get("Data") or {}).get("UID") or (data2.get("Data") or {}).get("uid")
        if uid:
            return uid
        msg = data2.get("message") or data2.get("error") or "Sin UID"
        if isinstance(msg, dict):
            msg = "; ".join(f"{k}: {v}" for k, v in msg.items())
        raise Exception(str(msg))
    except Exception as e:
        raise Exception(f"No se pudo crear receptor: {e}")


USOS_CFDI = [
    ("G01", "Adquisición de mercancias"),
    ("G03", "Gastos en general"),
    ("D01", "Honorarios médicos, dentales y gastos hospitalarios"),
    ("D04", "Donativos"),
    ("S01", "Sin efectos fiscales"),
    ("CP01", "Pagos"),
]

REGIMENES = [
    ("601", "General de Ley Personas Morales"),
    ("603", "Personas Morales con Fines no Lucrativos"),
    ("605", "Sueldos y Salarios e Ingresos Asimilados a Salarios"),
    ("606", "Arrendamiento"),
    ("608", "Demás ingresos"),
    ("609", "Consolidación"),
    ("616", "Sin obligaciones fiscales"),
    ("621", "Incorporación Fiscal"),
    ("625", "Régimen de las Actividades Empresariales con ingresos a través de Plataformas Tecnológicas"),
    ("626", "Régimen Simplificado de Confianza"),
]

# ── Página principal ──────────────────────────────────────────────
@bp.route("/")
def index():
    return render_template("facturacion/index.html",
                           usos_cfdi=USOS_CFDI,
                           regimenes=REGIMENES)

# ── Buscar envío por número de guía / ticket / teléfono ──────────
@bp.route("/api/test-timbrar")
def test_timbrar():
    """Prueba timbrar con diferentes configuraciones para diagnosticar."""
    import sys
    creds = _get_creds()
    if not creds["api_key"]:
        return jsonify({"error": "Sin credenciales"})

    resultados = {}
    # Probar diferentes valores de TipoDocumento con serie FAC
    for tipo, serie in [("factura","FAC"),("factura","2026"),("factura","F"),
                        ("1","FAC"),("ingreso","FAC"),("factura40","FAC")]:
        payload = {
            "Receptor": {"UID": "prueba", "RFCReceptor": "XAXX010101000",
                         "NombreReceptor": "PUBLICO EN GENERAL",
                         "UsoCFDI": "S01", "RegimenFiscalReceptor": "616",
                         "Domicilio": {"CodigoPostal": "98830"}, "Correo": "test@test.com"},
            "TipoDocumento": tipo, "Serie": serie,
            "Conceptos": [{"ClaveProdServ":"78102205","Cantidad":"1","ClaveUnidad":"E48",
                           "Unidad":"Servicio","Descripcion":"Test","ValorUnitario":"1.00",
                           "Importe":"1.00","Descuento":"0","ObjetoImp":"02",
                           "Impuestos":{"Traslados":[{"Base":"1.00","Impuesto":"002",
                           "TipoFactor":"Tasa","TasaOCuota":"0.160000","Importe":"0.16"}],"Retenciones":[]}}],
            "UsoCFDI":"S01","FormaPago":"01","MetodoPago":"PUE","Moneda":"MXN","TipoCambio":"1",
            "EnviarCorreo": False,
        }
        try:
            r = requests.post(f"{FACTURA_BASE}/cfdi40/create", headers=_headers(),
                              json=payload, timeout=10)
            body = r.text[:200] if r.text else ""
            resultados[f"{tipo}|{serie}"] = {"status": r.status_code, "body": body}
            print(f"[TEST] tipo={tipo} serie={serie} → {r.status_code} {body[:100]}", file=sys.stderr, flush=True)
        except Exception as e:
            resultados[f"{tipo}|{serie}"] = {"error": str(e)}
    return jsonify(resultados)
    """Consulta las series disponibles en factura.com para diagnóstico."""
    import sys
    try:
        r = requests.get(
            "https://api.factura.com/v4/series",
            headers=_headers(),
            timeout=10
        )
        print(f"[FACTURA] GET series status={r.status_code} body={r.text[:500]}", file=sys.stderr, flush=True)
        return jsonify({"ok": True, "status": r.status_code, "data": r.json() if r.text.strip() else {}})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@bp.route("/api/buscar", methods=["POST"])
def buscar_envio():
    d = request.get_json(force=True) or {}
    termino = (d.get("termino") or "").strip()
    if not termino:
        return jsonify({"ok": False, "error": "Ingresa un número de guía, ticket o teléfono"}), 400

    from app.modules import database as db
    import traceback as tb

    try:
        conn, cur, ph = db.get_conn()

        # Intentar búsqueda principal (sin numero_ticket si no existe)
        rows = []
        # Solo un query — buscar por número de guía, teléfonos y nombre
        for query_tpl, params in [
            (f"""SELECT g.id, g.numero_guia, g.creado_en,
                    g.destinatario_nombre, g.destinatario_ciudad, g.destinatario_pais,
                    g.precio_final, g.servicio, g.servicio as carrier,
                    g.remitente_nombre, g.remitente_telefono, g.metodo_pago, g.estatus
                 FROM guias g
                 LEFT JOIN clientes r ON g.cliente_id = r.id
                 WHERE g.numero_guia = {ph}
                    OR g.remitente_telefono LIKE {ph}
                    OR g.destinatario_telefono LIKE {ph}
                    OR g.destinatario_nombre ILIKE {ph}
                    OR r.telefono LIKE {ph}
                 ORDER BY g.id DESC LIMIT 10""",
             (termino, f"%{termino}%", f"%{termino}%", f"%{termino}%", f"%{termino}%")),
            # Fallback sin ILIKE (SQLite)
            (f"""SELECT g.id, g.numero_guia, g.creado_en,
                    g.destinatario_nombre, g.destinatario_ciudad, g.destinatario_pais,
                    g.precio_final, g.servicio, g.servicio as carrier,
                    g.remitente_nombre, g.remitente_telefono, g.metodo_pago, g.estatus
                 FROM guias g
                 LEFT JOIN clientes r ON g.cliente_id = r.id
                 WHERE g.numero_guia = {ph}
                    OR g.remitente_telefono LIKE {ph}
                    OR g.destinatario_telefono LIKE {ph}
                    OR UPPER(g.destinatario_nombre) LIKE UPPER({ph})
                    OR r.telefono LIKE {ph}
                 ORDER BY g.id DESC LIMIT 10""",
             (termino, f"%{termino}%", f"%{termino}%", f"%{termino}%", f"%{termino}%")),
        ]:
            try:
                cur.execute(query_tpl, params)
                rows = cur.fetchall()
                break  # Si funcionó, salir del loop
            except Exception:
                # Reabrir conexión limpia para el fallback
                try: conn.close()
                except: pass
                conn, cur, ph = db.get_conn()
                continue

        conn.close()

    except Exception as e:
        import traceback as _tb
        _tb.print_exc()  # Log en Render
        return jsonify({"ok": False, "error": f"Error al buscar: {str(e)}"}), 500

    if not rows:
        return jsonify({"ok": False,
            "error": "No encontramos envíos con ese dato. Verifica el número e intenta de nuevo."}), 404

    # Normalizar filas y verificar periodo de facturación
    hoy = datetime.date.today()
    resultados = []
    cols = ['id','numero_guia','creado_en','destinatario_nombre','destinatario_ciudad',
            'destinatario_pais','precio_final','servicio','carrier',
            'remitente_nombre','remitente_telefono','metodo_pago','estatus']
    for row in rows:
        if hasattr(row, 'keys'):
            r = dict(row)
        else:
            r = {cols[i]: row[i] for i in range(min(len(cols), len(row)))}

        # Verificar si ya fue facturada
        uuid_existente = r.get('uuid_cfdi') or ''
        r['ya_facturada'] = bool(uuid_existente)
        r['uuid_cfdi']    = uuid_existente
        r['rfc_factura']  = r.get('rfc_factura') or ''

        try:
            fecha_guia = datetime.datetime.fromisoformat(str(r.get('creado_en',''))[:19]).date()
            if r['ya_facturada']:
                # Ya facturada — no permitir de nuevo
                r['facturable'] = False
                r['razon_no_facturable'] = (
                    f"Este envío ya fue facturado. "
                    f"RFC: {r['rfc_factura']}. "
                    f"Puedes descargar la factura existente."
                )
            elif fecha_guia.year == hoy.year and fecha_guia.month == hoy.month:
                r['facturable'] = True
                r['razon_no_facturable'] = None
            else:
                r['facturable'] = False
                r['razon_no_facturable'] = (
                    f"El período de facturación fue "
                    f"{fecha_guia.strftime('%B %Y')} y ya venció"
                )
        except Exception:
            r['facturable'] = not r['ya_facturada']
            r['razon_no_facturable'] = None

        # precio_final siempre numérico
        try: r['precio_final'] = float(r.get('precio_final') or 0)
        except: r['precio_final'] = 0.0

        resultados.append(r)

    return jsonify({"ok": True, "envios": resultados})


# ── Generar CFDI ──────────────────────────────────────────────────
@bp.route("/api/generar", methods=["POST"])
def generar_cfdi():
    d = request.get_json(force=True) or {}

    guia_id    = d.get("guia_id")
    rfc        = (d.get("rfc") or "").strip().upper()
    razon      = (d.get("razon_social") or "").strip().upper()
    uso_cfdi   = d.get("uso_cfdi") or "G03"
    regimen    = d.get("regimen_fiscal") or "616"
    cp_fiscal  = (d.get("cp_fiscal") or "").strip()
    email      = (d.get("email") or "").strip().lower()
    forma_pago_manual = d.get("forma_pago") or ""   # forma de pago elegida por el cliente
    direccion  = d.get("direccion") or None          # dirección fiscal opcional

    # Validaciones básicas
    if not all([guia_id, rfc, razon, cp_fiscal, email]):
        return jsonify({"ok": False, "error": "Todos los campos son requeridos"}), 400

    if not re.match(r'^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$', rfc):
        return jsonify({"ok": False, "error": "RFC inválido. Verifica el formato (ej: XAXX010101000)"}), 400

    if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
        return jsonify({"ok": False, "error": "Email inválido"}), 400

    if not re.match(r'^\d{5}$', cp_fiscal):
        return jsonify({"ok": False, "error": "Código postal fiscal debe tener 5 dígitos"}), 400

    # Obtener datos de la guía
    from app.modules import database as db
    conn, cur, ph = db.get_conn()
    cur.execute(f"SELECT * FROM guias WHERE id={ph}", (guia_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return jsonify({"ok": False, "error": "Envío no encontrado"}), 404

    guia = dict(row) if hasattr(row, 'keys') else {'id': row[0]}
    if not guia.get('precio_final'):
        return jsonify({"ok": False, "error": "Este envío no tiene precio registrado"}), 400

    # CANDADO — verificar si ya fue facturada
    if guia.get('uuid_cfdi'):
        return jsonify({
            "ok": False,
            "error": f"Este envío ya fue facturado anteriormente (RFC: {guia.get('rfc_factura','')}).",
            "uuid_existente": guia.get('uuid_cfdi'),
            "ya_facturada": True
        }), 400

    # Verificar mes natural
    try:
        hoy = datetime.date.today()
        fecha_guia = datetime.datetime.fromisoformat(str(guia.get('creado_en',''))[:19]).date()
        if fecha_guia.year != hoy.year or fecha_guia.month != hoy.month:
            return jsonify({"ok": False,
                "error": f"El periodo de facturación para este envío ya venció. Solo se puede facturar en el mes natural del envío."}), 400
    except Exception:
        pass

    # Calcular subtotal e IVA
    total   = round(float(guia.get('precio_final') or 0), 2)
    iva     = round(total / 1.16 * 0.16, 2)
    subtotal = round(total - iva, 2)

    # Descripción del concepto
    carrier  = guia.get('carrier') or guia.get('servicio') or 'Paquetería'
    servicio = guia.get('servicio') or 'Envío'
    num_guia = guia.get('numero_guia') or ''
    descripcion = f"Servicio de paquetería {carrier} {servicio} - Guía: {num_guia}"

    # Verificar credenciales antes de todo
    creds = _get_creds()
    if not creds["api_key"] or not creds["secret_key"]:
        return jsonify({"ok": False,
            "error": "El sistema de facturación no está configurado. Contacta a PAQUETELLEGUE."}), 503

    # ── Obtener o crear el receptor en factura.com ────────────────
    try:
        receptor_uid = _obtener_uid_cliente(rfc, razon, cp_fiscal, regimen, email)
        import sys
        print(f"[FACTURA] receptor_uid={receptor_uid} len={len(str(receptor_uid))}", file=sys.stderr, flush=True)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Error al registrar receptor: {str(e)}"}), 400

    # ── Payload para factura.com ──────────────────────────────────
    # Forma de pago: usar la elegida por el cliente, o deducir del método del sistema
    forma_final = forma_pago_manual if forma_pago_manual else _forma_pago(guia.get('metodo_pago', ''))

    # Domicilio fiscal: CP mínimo + dirección completa si se proporcionó
    domicilio_receptor = {"CodigoPostal": cp_fiscal}
    if direccion and isinstance(direccion, dict):
        if direccion.get('calle'):      domicilio_receptor["Calle"]          = direccion["calle"]
        if direccion.get('numero_ext'): domicilio_receptor["NumeroExterior"] = direccion["numero_ext"]
        if direccion.get('numero_int'): domicilio_receptor["NumeroInterior"] = direccion["numero_int"]
        if direccion.get('colonia'):    domicilio_receptor["Colonia"]        = direccion["colonia"]
        if direccion.get('municipio'):  domicilio_receptor["Municipio"]      = direccion["municipio"]
        if direccion.get('estado'):     domicilio_receptor["Estado"]         = direccion["estado"]

    payload = {
        "Receptor": {
            "UID":                   receptor_uid,
            "RFCReceptor":           rfc,
            "NombreReceptor":        razon,
            "UsoCFDI":               uso_cfdi,
            "RegimenFiscalReceptor": regimen,
            "Domicilio":             domicilio_receptor,
            "Correo":                email,
        },
        "TipoDocumento":  "factura",
        "Conceptos": [{
            "ClaveProdServ":    "78102205",  # Servicios de mensajería y paquetería
            "NoIdentificacion": num_guia,
            "Cantidad":         "1",
            "ClaveUnidad":      "E48",
            "Unidad":           "Servicio",
            "Descripcion":      descripcion,
            "ValorUnitario":    str(round(subtotal, 6)),
            "Importe":          str(round(subtotal, 6)),
            "Descuento":        "0",
            "ObjetoImp":        "02",
            "Impuestos": {
                "Traslados": [{
                    "Base":       str(round(subtotal, 6)),
                    "Impuesto":   "002",
                    "TipoFactor": "Tasa",
                    "TasaOCuota": "0.160000",
                    "Importe":    str(round(iva, 6)),
                }],
                "Retenciones": []
            }
        }],
        "UsoCFDI":       uso_cfdi,
        "Serie":         1215621,
        "FormaPago":     forma_final,
        "MetodoPago":    "PUE",
        "Moneda":        "MXN",
        "TipoCambio":    "1",
        "NumOrder":      str(guia_id),
        "Observaciones": f"Folio de guía: {num_guia}",
        "EnviarCorreo":  True,
    }

    # Verificar que las credenciales están configuradas
    try:
        resp = requests.post(
            f"{FACTURA_BASE}/cfdi40/create",
            headers=_headers(),
            json=payload,
            timeout=30
        )
        import sys, json as _json
        print(f"[FACTURA] PAYLOAD: {_json.dumps(payload)[:600]}", file=sys.stderr, flush=True)
        print(f"[FACTURA] cfdi40/create status={resp.status_code} body={resp.text[:600]}", file=sys.stderr, flush=True)
        resp_data = resp.json()
    except requests.exceptions.Timeout:
        return jsonify({"ok": False, "error": "Tiempo de espera agotado con factura.com. Intenta de nuevo."}), 503
    except Exception as e:
        return jsonify({"ok": False, "error": f"Error de conexión: {str(e)}"}), 503

    if resp.status_code not in (200, 201) or resp_data.get("response") != "success":
        msg = resp_data.get("message") or resp_data.get("error") or "Error al timbrar"
        if isinstance(msg, dict):
            msg = msg.get("message") or str(msg)
        msg = str(msg)
        # Mensajes amigables para errores comunes del SAT
        if "CFDI40158" in msg or "RegimenFiscalR" in msg or "RegimenFiscal" in msg:
            msg = ("El Régimen Fiscal seleccionado no coincide con el que tienes registrado ante el SAT. "
                   "Consulta tu Constancia de Situación Fiscal y usa exactamente el régimen "
                   "que aparece ahí. Puedes obtenerla en sat.gob.mx → 'Genera tu constancia de situación fiscal'.")
        elif "CFDI40148" in msg or "DomicilioFiscalReceptor" in msg:
            msg = ("El Código Postal fiscal no coincide con el que tienes registrado ante el SAT. "
                   "Consúltalo en tu Constancia de Situación Fiscal — es el CP que aparece en "
                   "'Domicilio Fiscal', no el de tu casa o trabajo.")
        elif "CFDI40" in msg:
            msg = f"El SAT rechazó la factura: {msg}"
        return jsonify({"ok": False, "error": msg}), 400

    uuid = resp_data.get("UUID") or resp_data.get("uuid") or ""
    uid  = resp_data.get("uid")  or resp_data.get("invoice_uid") or ""

    # ── Guardar UUID en la guía ───────────────────────────────────
    try:
        conn2, cur2, ph2 = db.get_conn()
        cur2.execute(
            f"UPDATE guias SET uuid_cfdi={ph2}, rfc_factura={ph2}, email_factura={ph2} WHERE id={ph2}",
            (uuid, rfc, email, guia_id)
        )
        conn2.commit(); conn2.close()
    except Exception:
        pass  # No bloquear si falla el update

    return jsonify({
        "ok":    True,
        "uuid":  uuid,
        "uid":   uid,
        "folio": resp_data.get("Folio") or resp_data.get("folio") or "",
        "serie": resp_data.get("Serie") or "PL",
        "total": total,
        "email": email,
        "mensaje": f"Factura generada exitosamente. Se envió a {email}",
    })


# ── Descargar PDF/XML de CFDI ya generado ────────────────────────
@bp.route("/api/descargar/<uid>/<tipo>")
def descargar_cfdi(uid, tipo):
    """tipo: pdf o xml"""
    if tipo not in ("pdf", "xml"):
        return "Tipo inválido", 400
    try:
        resp = requests.get(
            f"{FACTURA_BASE}/cfdi40/{uid}/{tipo}",
            headers=_headers(),
            timeout=20
        )
        if resp.status_code != 200:
            return "No se pudo descargar el documento", 404
        mime = "application/pdf" if tipo == "pdf" else "application/xml"
        ext  = "pdf" if tipo == "pdf" else "xml"
        return send_file(BytesIO(resp.content), mimetype=mime,
                         download_name=f"factura_{uid[:8]}.{ext}")
    except Exception as e:
        return f"Error: {e}", 500


# ── Validar RFC contra SAT ────────────────────────────────────────
@bp.route("/api/validar-rfc", methods=["POST"])
def validar_rfc():
    d    = request.get_json(force=True) or {}
    rfc  = (d.get("rfc") or "").strip().upper()
    # Validación local de formato
    patron_moral  = r'^[A-ZÑ&]{3}\d{6}[A-Z0-9]{3}$'
    patron_fisica = r'^[A-ZÑ&]{4}\d{6}[A-Z0-9]{3}$'
    if re.match(patron_moral, rfc) or re.match(patron_fisica, rfc):
        tipo = "Persona Moral" if len(rfc) == 12 else "Persona Física"
        return jsonify({"ok": True, "valido": True, "tipo": tipo, "rfc": rfc})
    return jsonify({"ok": True, "valido": False,
                    "error": "El RFC no tiene el formato correcto"})


# ── Helper: forma de pago SAT ────────────────────────────────────
def _forma_pago(metodo: str) -> str:
    m = (metodo or "").lower()
    if "efectivo" in m or "cash" in m: return "01"
    if "tarjeta" in m and "débito" in m: return "28"
    if "tarjeta" in m or "credito" in m: return "04"
    if "transfer" in m or "spei" in m:  return "03"
    if "cheque" in m:                    return "02"
    return "99"  # Por definir

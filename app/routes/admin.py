from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.modules import database as db
from functools import wraps

bp = Blueprint("admin", __name__)

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            flash("Acceso solo para administradores", "error")
            return redirect(url_for("guias.nueva"))
        return f(*args, **kwargs)
    return decorated

def supervisor_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_supervisor:
            flash("Acceso solo para supervisores o administradores", "error")
            return redirect(url_for("guias.nueva"))
        return f(*args, **kwargs)
    return decorated


@bp.route("/")
@admin_required
def index():
    config   = db.get_config()
    usuarios = db.get_usuarios()
    conn     = db.get_connection()
    ph       = db._ph()
    cur      = conn.cursor()
    cur.execute("SELECT COUNT(*) as n FROM guias")
    total    = cur.fetchone()["n"]
    cur.execute("SELECT COALESCE(SUM(precio_final),0) as s FROM guias")
    ventas   = cur.fetchone()["s"]
    cur.execute("SELECT COUNT(*) as n FROM clientes")
    clientes = cur.fetchone()["n"]
    conn.close()
    stats = {"total_guias": total, "total_ventas": float(ventas), "total_clientes": clientes}
    return render_template("admin/index.html", config=config, usuarios=usuarios, stats=stats)


@bp.route("/config", methods=["GET","POST"])
@admin_required
def configuracion():
    config = db.get_config()
    if request.method == "POST":
        for campo in ["empresa_nombre","empresa_telefono","empresa_direccion",
                      "empresa_ciudad","empresa_estado","empresa_cp","empresa_rfc",
                      "empresa_email","iva","mensaje_recibo","tracking_url"]:
            db.set_config(campo, request.form.get(campo,""))
        # Guardar markup como JSON dual {nacional, internacional}
        import json as _json
        try:
            _nac  = float(request.form.get("markup_nacional",  "30") or "30")
            _intl = float(request.form.get("markup_internacional", "40") or "40")
            db.set_config("markup_json", _json.dumps({"nacional": _nac, "internacional": _intl}))
        except:
            db.set_config("markup_json", "30")
        flash("Configuracion guardada correctamente", "success")
        return redirect(url_for("admin.configuracion"))
    return render_template("admin/configuracion.html", config=config)


@bp.route("/usuarios")
@admin_required
def usuarios():
    users  = db.get_usuarios()
    config = db.get_config()
    sucursales = db.get_sucursales(solo_activas=True)
    return render_template("admin/usuarios.html", usuarios=users, config=config, sucursales=sucursales)


@bp.route("/usuarios/nuevo", methods=["POST"])
@admin_required
def nuevo_usuario():
    nombre      = request.form.get("nombre","").strip()
    usuario     = request.form.get("usuario","").strip()
    password    = request.form.get("password","")
    rol         = request.form.get("rol","operario")
    sucursal_id = request.form.get("sucursal_id", 1)
    if not all([nombre, usuario, password]):
        flash("Todos los campos son requeridos", "error")
        return redirect(url_for("admin.usuarios"))
    ok, msg = db.crear_usuario(nombre, usuario, password, rol, sucursal_id=int(sucursal_id))
    flash(msg, "success" if ok else "error")
    return redirect(url_for("admin.usuarios"))


@bp.route("/usuarios/<int:uid>/toggle", methods=["POST"])
@admin_required
def toggle_usuario(uid):
    conn = db.get_connection()
    cur  = conn.cursor()
    ph   = db._ph()
    cur.execute(f"SELECT activo FROM usuarios WHERE id={ph}", (uid,))
    row = cur.fetchone()
    if row:
        nuevo = 0 if row["activo"] else 1
        cur.execute(f"UPDATE usuarios SET activo={ph} WHERE id={ph}", (nuevo, uid))
        conn.commit()
    conn.close()
    flash("Usuario actualizado", "success")
    return redirect(url_for("admin.usuarios"))


@bp.route("/reportes")
@admin_required
def reportes():
    from_date = request.args.get("desde", "")
    to_date   = request.args.get("hasta", "")
    operario  = request.args.get("operario", "")
    conn = db.get_connection()
    cur  = conn.cursor()
    ph   = db._ph()
    query = """
        SELECT g.*, u.nombre as operario_nombre
        FROM guias g LEFT JOIN usuarios u ON g.operario_id = u.id
        WHERE 1=1
    """
    params = []
    if from_date:
        query += f" AND DATE(g.creado_en) >= {ph}"; params.append(from_date)
    if to_date:
        query += f" AND DATE(g.creado_en) <= {ph}"; params.append(to_date)
    if operario:
        query += f" AND g.operario_id = {ph}"; params.append(operario)
    query += " ORDER BY g.creado_en DESC"
    cur.execute(query, params)
    guias    = [dict(r) for r in cur.fetchall()]
    usuarios = db.get_usuarios()
    total_guias  = len(guias)
    total_ventas = sum(g.get("precio_final", 0) or 0 for g in guias)
    total_costo  = sum(g.get("costo_proveedor", 0) or 0 for g in guias)
    por_pago = {}
    for g in guias:
        mp = g.get("metodo_pago") or "efectivo"
        por_pago[mp] = por_pago.get(mp, 0) + (g.get("precio_final") or 0)
    por_operario = {}
    for g in guias:
        op = g.get("operario_nombre") or "Sin asignar"
        if op not in por_operario:
            por_operario[op] = {"guias": 0, "ventas": 0}
        por_operario[op]["guias"] += 1
        por_operario[op]["ventas"] += g.get("precio_final") or 0
    conn.close()
    return render_template("admin/reportes.html",
        guias=guias, usuarios=usuarios,
        from_date=from_date, to_date=to_date, operario=operario,
        total_guias=total_guias, total_ventas=total_ventas,
        total_costo=total_costo, por_pago=por_pago, por_operario=por_operario)


@bp.route("/promociones")
@admin_required
def promociones():
    promos = db.get_promociones()
    clientes = db.get_clientes()
    config = db.get_config()
    return render_template("admin/promociones.html", promociones=promos, clientes=clientes, config=config)


@bp.route("/promociones/nueva", methods=["POST"])
@admin_required
def nueva_promocion():
    data = {
        "nombre":       request.form.get("nombre", "").strip(),
        "tipo":         request.form.get("tipo", "porcentaje"),
        "valor":        float(request.form.get("valor", 0) or 0),
        "cliente_id":   request.form.get("cliente_id") or None,
        "servicio":     request.form.get("servicio") or None,
        "fecha_inicio": request.form.get("fecha_inicio") or None,
        "fecha_fin":    request.form.get("fecha_fin") or None,
        "activa":       1,
        "codigo":       request.form.get("codigo", "").strip() or None,
    }
    if not data["nombre"]:
        flash("El nombre es requerido", "error")
        return redirect(url_for("admin.promociones"))
    db.guardar_promocion(data)
    flash(f"Promoción '{data['nombre']}' creada", "success")
    return redirect(url_for("admin.promociones"))


@bp.route("/promociones/<int:pid>/toggle", methods=["POST"])
@admin_required
def toggle_promocion(pid):
    conn = db.get_connection()
    cur  = conn.cursor()
    ph   = db._ph()
    cur.execute(f"SELECT activa FROM promociones WHERE id={ph}", (pid,))
    row = cur.fetchone()
    if row:
        nuevo = 0 if row["activa"] else 1
        cur.execute(f"UPDATE promociones SET activa={ph} WHERE id={ph}", (nuevo, pid))
        conn.commit()
    conn.close()
    flash("Promoción actualizada", "success")
    return redirect(url_for("admin.promociones"))


@bp.route("/promociones/<int:pid>/eliminar", methods=["POST"])
@admin_required
def eliminar_promocion(pid):
    conn = db.get_connection()
    cur  = conn.cursor()
    ph   = db._ph()
    cur.execute(f"DELETE FROM promociones WHERE id={ph}", (pid,))
    conn.commit()
    conn.close()
    flash("Promoción eliminada", "success")
    return redirect(url_for("admin.promociones"))


@bp.route("/corte")
@login_required
def corte():
    from datetime import date
    modo      = request.args.get("modo", "diario")
    desde     = request.args.get("desde", str(date.today()))
    hasta     = request.args.get("hasta", str(date.today()))

    if modo == "diario":
        desde = hasta = request.args.get("fecha", str(date.today()))

    # Filtro de operario
    if current_user.is_supervisor:
        operario = request.args.get("operario", "")
    else:
        operario = str(current_user.id)

    # Filtro de sucursal: admin global puede elegir, resto ve solo la suya
    if current_user.is_admin_global:
        sucursal_filtro = request.args.get("sucursal", "")  # "" = todas
    else:
        sucursal_filtro = str(current_user.sucursal_id)

    conn, cur, ph = db.get_conn()
    query = """
        SELECT g.id, g.numero_guia, g.servicio, g.destinatario_nombre,
               g.destinatario_ciudad, g.precio_final, g.costo_proveedor,
               g.metodo_pago, g.estatus, g.creado_en,
               u.nombre as operario_nombre,
               s.nombre as sucursal_nombre
        FROM guias g
        LEFT JOIN usuarios u ON g.operario_id = u.id
        LEFT JOIN sucursales s ON g.sucursal_id = s.id
        WHERE DATE(g.creado_en) >= {ph} AND DATE(g.creado_en) <= {ph}
    """.replace("{ph}", ph)
    params = [desde, hasta]
    if operario:
        query += f" AND g.operario_id = {ph}"; params.append(operario)
    if sucursal_filtro:
        query += f" AND g.sucursal_id = {ph}"; params.append(sucursal_filtro)
    query += " ORDER BY g.creado_en DESC"
    cur.execute(query, params)
    guias = [dict(r) if hasattr(r, 'keys') else {
        'id':r[0],'numero_guia':r[1],'servicio':r[2],'destinatario_nombre':r[3],
        'destinatario_ciudad':r[4],'precio_final':r[5],'costo_proveedor':r[6],
        'metodo_pago':r[7],'estatus':r[8],'creado_en':str(r[9]),'operario_nombre':r[10],
        'sucursal_nombre':r[11]
    } for r in cur.fetchall()]
    conn.close()

    usuarios   = db.get_usuarios()
    sucursales = db.get_sucursales(solo_activas=True)
    total_guias   = len(guias)
    total_ventas  = sum(g.get("precio_final") or 0 for g in guias)
    total_costo   = sum(g.get("costo_proveedor") or 0 for g in guias)
    total_utilidad= total_ventas - total_costo

    total_insumos_venta = 0
    total_insumos_costo = 0
    insumos_detalle = {}
    todos_insumos = {i["id"]: i for i in db.get_insumos(solo_activos=False)}
    for g in guias:
        ins_guia = db.get_insumos_de_guia(g["id"])
        for ins in ins_guia:
            subtotal_venta = float(ins.get("subtotal") or 0)
            cantidad       = int(ins.get("cantidad") or 1)
            iid            = ins.get("insumo_id")
            costo_u        = float((todos_insumos.get(iid) or {}).get("costo") or 0)
            costo_total    = costo_u * cantidad
            total_insumos_venta += subtotal_venta
            total_insumos_costo += costo_total
            nombre = ins.get("nombre","")
            if nombre not in insumos_detalle:
                insumos_detalle[nombre] = {"cantidad":0,"venta":0,"costo":0,"utilidad":0}
            insumos_detalle[nombre]["cantidad"]  += cantidad
            insumos_detalle[nombre]["venta"]     += subtotal_venta
            insumos_detalle[nombre]["costo"]     += costo_total
            insumos_detalle[nombre]["utilidad"]  += subtotal_venta - costo_total
    total_insumos_utilidad = total_insumos_venta - total_insumos_costo

    por_pago = {}
    for g in guias:
        mp = g.get("metodo_pago") or "efectivo"
        por_pago[mp] = por_pago.get(mp, 0) + (g.get("precio_final") or 0)

    por_operario = {}
    for g in guias:
        op = g.get("operario_nombre") or "Sin asignar"
        if op not in por_operario:
            por_operario[op] = {"guias": 0, "ventas": 0, "utilidad": 0}
        por_operario[op]["guias"]   += 1
        por_operario[op]["ventas"]  += g.get("precio_final") or 0
        por_operario[op]["utilidad"]+= (g.get("precio_final") or 0) - (g.get("costo_proveedor") or 0)

    por_servicio = {}
    for g in guias:
        sv = g.get("servicio") or "Otro"
        if sv not in por_servicio:
            por_servicio[sv] = {"guias": 0, "ventas": 0}
        por_servicio[sv]["guias"]  += 1
        por_servicio[sv]["ventas"] += g.get("precio_final") or 0

    # Resumen por sucursal (solo para admin global)
    por_sucursal = {}
    if current_user.is_admin_global:
        for g in guias:
            sn = g.get("sucursal_nombre") or "Sin sucursal"
            if sn not in por_sucursal:
                por_sucursal[sn] = {"guias":0,"ventas":0,"utilidad":0}
            por_sucursal[sn]["guias"]   += 1
            por_sucursal[sn]["ventas"]  += g.get("precio_final") or 0
            por_sucursal[sn]["utilidad"]+= (g.get("precio_final") or 0) - (g.get("costo_proveedor") or 0)

    return render_template("admin/corte.html",
        guias=guias, usuarios=usuarios, sucursales=sucursales,
        modo=modo, desde=desde, hasta=hasta, operario=operario,
        sucursal_filtro=sucursal_filtro,
        total_guias=total_guias, total_ventas=total_ventas,
        total_costo=total_costo, total_utilidad=total_utilidad,
        total_insumos_venta=total_insumos_venta, total_insumos_costo=total_insumos_costo,
        total_insumos_utilidad=total_insumos_utilidad, insumos_detalle=insumos_detalle,
        por_pago=por_pago, por_operario=por_operario, por_servicio=por_servicio,
        por_sucursal=por_sucursal)


@bp.route("/insumos")
@admin_required
def insumos():
    sid = None if current_user.is_admin_global else current_user.sucursal_id
    items  = db.get_insumos(solo_activos=False, sucursal_id=sid)
    config = db.get_config()
    return render_template("admin/insumos.html", insumos=items, config=config)

@bp.route("/insumos/nuevo", methods=["POST"])
@admin_required
def nuevo_insumo():
    nombre       = request.form.get("nombre","").strip()
    descripcion  = request.form.get("descripcion","").strip()
    costo        = request.form.get("costo", 0)
    precio       = request.form.get("precio", 0)
    stock        = request.form.get("stock", 0)
    stock_minimo = request.form.get("stock_minimo", 3)
    if not nombre:
        flash("El nombre es requerido", "error")
        return redirect(url_for("admin.insumos"))
    ok, msg = db.crear_insumo(nombre, descripcion, costo, precio, stock, stock_minimo,
                               sucursal_id=current_user.sucursal_id)
    flash(msg, "success" if ok else "error")
    return redirect(url_for("admin.insumos"))

@bp.route("/insumos/<int:iid>/toggle", methods=["POST"])
@admin_required
def toggle_insumo(iid):
    conn, cur, ph = db.get_conn()
    cur.execute(f"SELECT activo FROM insumos WHERE id={ph}", (iid,))
    row = cur.fetchone()
    if row:
        nuevo = 0 if (row[0] if not hasattr(row,'keys') else row['activo']) else 1
        cur.execute(f"UPDATE insumos SET activo={ph} WHERE id={ph}", (nuevo, iid))
        conn.commit()
    conn.close()
    flash("Insumo actualizado", "success")
    return redirect(url_for("admin.insumos"))

@bp.route("/insumos/<int:iid>/editar", methods=["POST"])
@admin_required
def editar_insumo(iid):
    db.actualizar_insumo(
        iid,
        request.form.get("nombre","").strip(),
        request.form.get("descripcion","").strip(),
        request.form.get("costo", 0),
        request.form.get("precio", 0),
        request.form.get("stock", 0),
        request.form.get("stock_minimo", 3),
        int(request.form.get("activo", 1))
    )
    flash("Insumo actualizado", "success")
    return redirect(url_for("admin.insumos"))

@bp.route("/insumos/<int:iid>/restock", methods=["POST"])
@admin_required
def restock_insumo(iid):
    cantidad = int(request.form.get("cantidad", 0))
    if cantidad > 0:
        db.agregar_stock_insumo(iid, cantidad)
        flash(f"Se agregaron {cantidad} piezas al inventario", "success")
    return redirect(url_for("admin.insumos"))


@bp.route("/corte_raw")
@login_required
def corte_raw():
    """Genera líneas de texto para impresora térmica 80mm — igual que recibo_raw."""
    from datetime import date as _date
    modo     = request.args.get("modo", "diario")
    desde    = request.args.get("desde", str(_date.today()))
    hasta    = request.args.get("hasta", str(_date.today()))
    if modo == "diario":
        desde = hasta = request.args.get("fecha", str(_date.today()))
    # Operario: supervisor/admin filtra cualquiera, operario solo el suyo
    if current_user.is_supervisor:
        operario = request.args.get("operario", "")
    else:
        operario = str(current_user.id)

    conn, cur, ph = db.get_conn()
    query = """
        SELECT g.id, g.numero_guia, g.servicio, g.destinatario_nombre,
               g.destinatario_ciudad, g.precio_final, g.costo_proveedor,
               g.metodo_pago, g.estatus, g.creado_en,
               u.nombre as operario_nombre
        FROM guias g LEFT JOIN usuarios u ON g.operario_id = u.id
        WHERE DATE(g.creado_en) >= {ph} AND DATE(g.creado_en) <= {ph}
    """.replace("{ph}", ph)
    params = [desde, hasta]
    if operario:
        query += f" AND g.operario_id = {ph}"; params.append(operario)
    query += " ORDER BY g.creado_en"
    cur.execute(query, params)
    guias = [dict(r) if hasattr(r,'keys') else {
        'id':r[0],'numero_guia':r[1],'servicio':r[2],'destinatario_nombre':r[3],
        'destinatario_ciudad':r[4],'precio_final':r[5],'costo_proveedor':r[6],
        'metodo_pago':r[7],'estatus':r[8],'creado_en':str(r[9]),'operario_nombre':r[10]
    } for r in cur.fetchall()]
    conn.close()

    cfg     = db.get_config()
    empresa = cfg.get("empresa_nombre", "PAQUETELLEGUE")
    iva_pct = float(cfg.get("iva","0") or 0)

    total_guias   = len(guias)
    total_ventas  = sum(float(g.get("precio_final") or 0) for g in guias)
    total_costo   = sum(float(g.get("costo_proveedor") or 0) for g in guias)
    total_utilidad= total_ventas - total_costo

    # Totales por método de pago
    por_pago = {}
    for g in guias:
        mp = (g.get("metodo_pago") or "efectivo").upper()
        por_pago[mp] = por_pago.get(mp, 0) + float(g.get("precio_final") or 0)

    # Totales por paquetería
    por_servicio = {}
    for g in guias:
        sv = (g.get("servicio") or "Otro").split("—")[-1].strip().upper()[:18]
        if sv not in por_servicio:
            por_servicio[sv] = {"guias": 0, "ventas": 0}
        por_servicio[sv]["guias"]  += 1
        por_servicio[sv]["ventas"] += float(g.get("precio_final") or 0)

    # Insumos
    todos_insumos = {i["id"]: i for i in db.get_insumos(solo_activos=False)}
    total_insumos_venta = 0
    insumos_detalle = {}
    for g in guias:
        for ins in db.get_insumos_de_guia(g["id"]):
            sub = float(ins.get("subtotal") or 0)
            cant = int(ins.get("cantidad") or 1)
            total_insumos_venta += sub
            nombre = (ins.get("nombre") or "")[:20]
            if nombre not in insumos_detalle:
                insumos_detalle[nombre] = {"cantidad": 0, "venta": 0}
            insumos_detalle[nombre]["cantidad"] += cant
            insumos_detalle[nombre]["venta"]    += sub

    from datetime import datetime as _dt
    ahora = _dt.now().strftime("%d/%m/%Y %H:%M")

    W = 42
    def sep(c="-"):  return c * W
    def center(t):   return t.center(W)
    def lr(l, r):
        gap = W - len(l) - len(r)
        return l + " " * max(1, gap) + r

    lines = [
        center(empresa),
        center("CORTE DE ENVIOS"),
        sep("="),
    ]
    if modo == "diario":
        lines.append(center(f"Fecha: {desde}"))
    else:
        lines.append(center(f"Del {desde} al {hasta}"))
    lines += [center(f"Impreso: {ahora}"), sep("=")]

    # Resumen general
    lines += [
        center("-- RESUMEN GENERAL --"),
        sep(),
        lr("Total guias:", str(total_guias)),
        lr("Total cobrado:", f"${total_ventas:.2f}"),
    ]
    if current_user.is_admin:
        lines += [
            lr("Costo proveedor:", f"${total_costo:.2f}"),
            lr("UTILIDAD:", f"${total_utilidad:.2f}"),
        ]
    lines.append(sep())

    # Por método de pago
    lines.append(center("-- POR METODO DE PAGO --"))
    lines.append(sep())
    for mp, total in por_pago.items():
        lines.append(lr(f"  {mp}:", f"${total:.2f}"))
    lines.append(sep())

    # Por paquetería
    lines.append(center("-- POR PAQUETERIA --"))
    lines.append(sep())
    for sv, data in por_servicio.items():
        lines.append(lr(f"  {sv} ({data['guias']})", f"${data['ventas']:.2f}"))
    lines.append(sep())

    # Insumos
    if insumos_detalle:
        lines.append(center("-- INSUMOS VENDIDOS --"))
        lines.append(sep())
        for nombre, data in insumos_detalle.items():
            lines.append(lr(f"  {nombre} x{data['cantidad']}", f"${data['venta']:.2f}"))
        lines.append(lr("Total insumos:", f"${total_insumos_venta:.2f}"))
        lines.append(sep())

    # Detalle de guías
    lines += [center("-- DETALLE DE GUIAS --"), sep()]
    for i, g in enumerate(guias, 1):
        hora = (g.get("creado_en") or "")
        hora = hora[11:16] if len(hora) > 11 else ""
        num  = (g.get("numero_guia") or "en espera")[-16:]
        dest = (g.get("destinatario_nombre") or "")[:18]
        sv   = (g.get("servicio") or "").split("—")[-1].strip()[:10]
        mp   = (g.get("metodo_pago") or "efe")[:3].upper()
        pf   = float(g.get("precio_final") or 0)
        op   = (g.get("operario_nombre") or "")[:10]
        lines.append(f"{i:>2}. {hora} {dest}")
        lines.append(f"    {sv:<10} {mp:<4} ${pf:>7.2f}  {op}")
        lines.append(f"    {num}")
        if i < len(guias): lines.append("")

    lines += [sep("="), center(f"TOTAL: ${total_ventas:.2f}"), sep("="), "", "", ""]

    return jsonify({"ok": True, "lines": lines, "empresa": empresa,
                    "total_guias": total_guias, "total_ventas": total_ventas})


@bp.route("/corte_pdf")
@login_required
def corte_pdf():
    """Genera PDF en hoja carta del corte — para impresora normal."""
    import tempfile, os
    from datetime import date as _date
    modo     = request.args.get("modo", "diario")
    desde    = request.args.get("desde", str(_date.today()))
    hasta    = request.args.get("hasta", str(_date.today()))
    if modo == "diario":
        desde = hasta = request.args.get("fecha", str(_date.today()))
    if current_user.is_supervisor:
        operario = request.args.get("operario", "")
    else:
        operario = str(current_user.id)

    conn, cur, ph = db.get_conn()
    query = """
        SELECT g.id, g.numero_guia, g.servicio, g.destinatario_nombre,
               g.destinatario_ciudad, g.precio_final, g.costo_proveedor,
               g.metodo_pago, g.estatus, g.creado_en,
               u.nombre as operario_nombre
        FROM guias g LEFT JOIN usuarios u ON g.operario_id = u.id
        WHERE DATE(g.creado_en) >= {ph} AND DATE(g.creado_en) <= {ph}
    """.replace("{ph}", ph)
    params = [desde, hasta]
    if operario:
        query += f" AND g.operario_id = {ph}"; params.append(operario)
    query += " ORDER BY g.creado_en"
    cur.execute(query, params)
    guias = [dict(r) if hasattr(r,'keys') else {
        'id':r[0],'numero_guia':r[1],'servicio':r[2],'destinatario_nombre':r[3],
        'destinatario_ciudad':r[4],'precio_final':r[5],'costo_proveedor':r[6],
        'metodo_pago':r[7],'estatus':r[8],'creado_en':str(r[9]),'operario_nombre':r[10]
    } for r in cur.fetchall()]
    conn.close()

    cfg      = db.get_config()
    empresa  = cfg.get("empresa_nombre","PAQUETELLEGUE")
    iva_pct  = float(cfg.get("iva","0") or 0)
    es_admin = current_user.is_admin

    total_ventas   = sum(float(g.get("precio_final") or 0) for g in guias)
    total_costo    = sum(float(g.get("costo_proveedor") or 0) for g in guias)
    total_utilidad = total_ventas - total_costo

    por_pago = {}
    for g in guias:
        mp = (g.get("metodo_pago") or "efectivo").capitalize()
        por_pago[mp] = por_pago.get(mp, 0) + float(g.get("precio_final") or 0)

    por_servicio = {}
    for g in guias:
        sv = (g.get("servicio") or "Otro").split("—")[-1].strip()
        if sv not in por_servicio:
            por_servicio[sv] = {"guias": 0, "ventas": 0}
        por_servicio[sv]["guias"]  += 1
        por_servicio[sv]["ventas"] += float(g.get("precio_final") or 0)

    insumos_detalle = {}
    total_insumos   = 0
    for g in guias:
        for ins in db.get_insumos_de_guia(g["id"]):
            sub = float(ins.get("subtotal") or 0)
            total_insumos += sub
            nombre = ins.get("nombre","")
            if nombre not in insumos_detalle:
                insumos_detalle[nombre] = {"cantidad":0,"venta":0}
            insumos_detalle[nombre]["cantidad"] += int(ins.get("cantidad") or 1)
            insumos_detalle[nombre]["venta"]    += sub

    from datetime import datetime as _dt
    ahora = _dt.now().strftime("%d/%m/%Y %H:%M")
    periodo = desde if modo=="diario" else f"{desde} al {hasta}"

    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import mm
    from reportlab.lib import colors

    fd, ruta = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)

    W, H = letter  # 612 x 792 pts
    MAR  = 18 * mm
    UTIL = W - 2 * MAR
    c    = rl_canvas.Canvas(ruta, pagesize=letter)
    y    = H - 15 * mm

    def titulo(txt, size=14, bold=True):
        nonlocal y
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.drawString(MAR, y, txt)
        y -= size + 4

    def subtitulo(txt):
        nonlocal y
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(colors.HexColor("#333333"))
        c.drawString(MAR, y, txt)
        c.setFillColor(colors.black)
        y -= 14

    def linea_sep(grosor=0.5):
        nonlocal y
        c.setLineWidth(grosor)
        c.line(MAR, y, W - MAR, y)
        y -= 6

    def fila_lr(izq, der, size=9, bold_der=False):
        nonlocal y
        c.setFont("Helvetica", size)
        c.drawString(MAR + 4, y, izq)
        c.setFont("Helvetica-Bold" if bold_der else "Helvetica", size)
        c.drawRightString(W - MAR, y, der)
        y -= size + 3

    def nueva_pag():
        nonlocal y
        c.showPage()
        y = H - 15 * mm

    # ── Encabezado ──
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(W / 2, y, empresa.upper())
    y -= 20
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(W / 2, y, "CORTE DE ENVÍOS")
    y -= 16
    c.setFont("Helvetica", 9)
    c.drawCentredString(W / 2, y, f"Período: {periodo}   |   Impreso: {ahora}")
    y -= 8
    c.setLineWidth(1.5)
    c.line(MAR, y, W - MAR, y)
    y -= 12

    # ── Resumen en cajas ──
    boxes = [("Guías", str(len(guias))), ("Total cobrado", f"${total_ventas:.2f}")]
    if es_admin:
        boxes += [("Costo", f"${total_costo:.2f}"), ("Utilidad", f"${total_utilidad:.2f}")]
    bw = UTIL / len(boxes)
    bx = MAR
    for label, val in boxes:
        c.setLineWidth(0.5)
        c.rect(bx, y - 26, bw - 4, 30)
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(bx + (bw - 4) / 2, y - 14, val)
        c.setFont("Helvetica", 8)
        c.drawCentredString(bx + (bw - 4) / 2, y - 24, label)
        bx += bw
    y -= 36

    # ── Por método de pago ──
    linea_sep()
    subtitulo("MÉTODO DE PAGO")
    for mp, total in por_pago.items():
        fila_lr(f"  {mp}", f"${total:.2f}")
    y -= 4

    # ── Por paquetería ──
    linea_sep()
    subtitulo("POR PAQUETERÍA")
    for sv, data in por_servicio.items():
        fila_lr(f"  {sv[:35]} ({data['guias']} guías)", f"${data['ventas']:.2f}")
    y -= 4

    # ── Insumos ──
    if insumos_detalle:
        linea_sep()
        subtitulo("INSUMOS VENDIDOS")
        for nombre, data in insumos_detalle.items():
            fila_lr(f"  {nombre} × {data['cantidad']}", f"${data['venta']:.2f}")
        fila_lr("  TOTAL INSUMOS", f"${total_insumos:.2f}", bold_der=True)
        y -= 4

    # ── Tabla detalle ──
    linea_sep(1)
    subtitulo("DETALLE DE GUÍAS")
    # Cabecera
    COL = [MAR, MAR+70, MAR+170, MAR+295, MAR+360, W-MAR]
    HDR = ["Hora", "Destinatario", "Servicio", "Pago", "Total"]
    if es_admin:
        HDR.append("")
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(colors.HexColor("#eeeeee"))
    c.rect(MAR, y - 2, UTIL, 12, fill=1, stroke=0)
    c.setFillColor(colors.black)
    for i, h in enumerate(HDR):
        c.drawString(COL[i] + 2, y, h)
    y -= 14
    c.setLineWidth(0.3)
    c.line(MAR, y + 2, W - MAR, y + 2)

    for idx, g in enumerate(guias):
        if y < 25 * mm:
            nueva_pag()
            # repetir cabecera
            c.setFont("Helvetica-Bold", 8)
            c.setFillColor(colors.HexColor("#eeeeee"))
            c.rect(MAR, y - 2, UTIL, 12, fill=1, stroke=0)
            c.setFillColor(colors.black)
            for i, h in enumerate(HDR):
                c.drawString(COL[i] + 2, y, h)
            y -= 14

        hora = (g.get("creado_en") or "")[11:16]
        dest = (g.get("destinatario_nombre") or "")[:22]
        sv   = (g.get("servicio") or "").split("—")[-1].strip()[:20]
        mp   = (g.get("metodo_pago") or "efectivo")[:12].capitalize()
        pf   = float(g.get("precio_final") or 0)

        bg = colors.HexColor("#f9f9f9") if idx % 2 == 0 else colors.white
        c.setFillColor(bg)
        c.rect(MAR, y - 2, UTIL, 11, fill=1, stroke=0)
        c.setFillColor(colors.black)
        c.setFont("Helvetica", 8)
        c.drawString(COL[0] + 2, y, hora)
        c.drawString(COL[1] + 2, y, dest)
        c.drawString(COL[2] + 2, y, sv)
        c.drawString(COL[3] + 2, y, mp)
        c.drawRightString(W - MAR - 2, y, f"${pf:.2f}")
        y -= 11

    # ── Totales finales ──
    c.setLineWidth(1)
    c.line(MAR, y, W - MAR, y)
    y -= 10
    c.setFont("Helvetica-Bold", 11)
    c.drawString(MAR, y, f"TOTAL: ${total_ventas:.2f} MXN")
    if es_admin:
        c.setFont("Helvetica", 9)
        c.drawRightString(W - MAR, y, f"Utilidad: ${total_utilidad:.2f}")
    y -= 20
    c.setFont("Helvetica", 8)
    c.drawCentredString(W / 2, y, f"{empresa} — {ahora}")

    c.save()

    with open(ruta, "rb") as f:
        data = f.read()
    os.unlink(ruta)
    from io import BytesIO
    from flask import send_file as _sf
    nombre = f"corte_{desde.replace('-','')}.pdf"
    return _sf(BytesIO(data), mimetype="application/pdf", download_name=nombre)


@bp.route("/consignment_notes")
@login_required
def consignment_notes():
    """Endpoint temporal para ver catálogo de Carta Porte de Skydropx."""
    if not current_user.is_admin:
        return "No autorizado", 403
    from app.modules import api_proveedor as api
    import json
    try:
        import json as _json, time as _t
        # Buscar términos clave en múltiples páginas
        terminos = ["mercancia","mercancía","general","varios","miscelaneo","miscelánea",
                    "instrumento musical","instrumento","ropa","calzado","electronico","celular",
                    "juguete","mueble","herramienta","cosmetico","alimento","libro","joyeria",
                    "deporte","artesania","paquete","envio","envío"]
        
        resultados = []
        total_pages = None
        
        # Escanear páginas específicas donde están los códigos de bienes de consumo
        # Basado en distribución de 48,757 códigos SAT ordenados numéricamente
        paginas_a_escanear = (
            list(range(1200, 1206)) +   # ~43xx electrónica/celulares
            list(range(1500, 1506)) +   # ~49xx deportes
            list(range(1650, 1656)) +   # ~52xx muebles
            list(range(1720, 1726)) +   # ~53xx ropa/calzado/accesorios
            list(range(1820, 1826)) +   # ~54xx joyería
            list(range(1880, 1886)) +   # ~55xx publicaciones/libros
            list(range(2020, 2026)) +   # ~60xx instrumentos/juguetes/arte
            list(range(2100, 2106)) +   # ~62xx-65xx varios
            list(range(2200, 2206))     # ~70xx+ mercancía general
        )
        
        for page in paginas_a_escanear:
            try:
                resp = api._request("GET", f"/shipments/consignment_notes?page={page}&per_page=20")
                items = resp.get("data", [])
                meta  = resp.get("meta", {})
                
                if total_pages is None:
                    total_pages = meta.get("total_pages", "?")
                    total_count = meta.get("total_count", "?")
                
                for item in items:
                    code = item.get("consignment_note","")
                    desc = item.get("description","").lower()
                    for t in terminos:
                        if t in desc:
                            resultados.append(f"{code} -> {item.get('description','')}")
                            break
                
                if not items: break
                _t.sleep(0.5)  # Respetar rate limit
            except Exception as _pe:
                resultados.append(f"[Error página {page}: {_pe}]")
                _t.sleep(1)
        
        html = "<pre style='font-family:monospace;padding:20px;background:#111;color:#0f0;font-size:12px'>"
        html += f"Scaneadas: 50 páginas de {total_pages} | Encontrados: {len(resultados)}\n\n"
        html += "\n".join(sorted(set(resultados)))
        html += "</pre>"
        return html
    except Exception as e:
        import traceback
        return f"<pre style='color:red'>Error: {e}\n\n{traceback.format_exc()}</pre>", 500


@bp.route("/api_log")
@login_required
def api_log():
    if not current_user.is_admin:
        return "No autorizado", 403
    import os
    log_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            "data", "api_debug.log")
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        # Últimas 200 líneas, filtrar las de ADDR
        todas = lines[-200:]
        # Resaltar líneas de direcciones
        html_lines = []
        for l in todas:
            l = l.rstrip()
            if "ADDR" in l or "PAYLOAD SHIPMENT COMPLETO" in l:
                html_lines.append(f'<span style="color:#4CAF50;font-weight:bold">{l}</span>')
            elif "ERROR" in l or "EXCEP" in l:
                html_lines.append(f'<span style="color:#ff5555">{l}</span>')
            else:
                html_lines.append(l)
        contenido = "\n".join(html_lines)
    except Exception as e:
        contenido = f"No se pudo leer el log: {e}"

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>API Log - PAQUETELLEGUE</title>
<style>
body{{background:#0d0d0d;color:#f0f0f0;font-family:monospace;font-size:12px;padding:20px}}
pre{{white-space:pre-wrap;word-break:break-all;line-height:1.6}}
.top{{display:flex;gap:10px;margin-bottom:14px;align-items:center}}
a{{color:#C9A84C;text-decoration:none;padding:6px 12px;border:1px solid #C9A84C;border-radius:4px}}
h2{{color:#C9A84C;margin:0}}
</style>
<meta http-equiv="refresh" content="10">
</head><body>
<div class="top">
  <h2>🔍 API Log — Skydropx</h2>
  <a href="/admin/api_log">🔄 Refrescar</a>
  <a href="/admin">← Admin</a>
  <span style="color:#9a9a9a;font-size:11px">Se refresca automáticamente cada 10s</span>
</div>
<pre>{contenido}</pre>
</body></html>"""


# ─── SUCURSALES ────────────────────────────────────────────────────

@bp.route("/sucursales")
@admin_required
def sucursales():
    todas = db.get_sucursales()
    return render_template("admin/sucursales.html", sucursales=todas)

@bp.route("/sucursales/nueva", methods=["GET","POST"])
@admin_required
def nueva_sucursal():
    if request.method == "POST":
        data = {k: request.form.get(k,"") for k in ["nombre","direccion","ciudad","estado","cp","telefono","email","activa"]}
        data["activa"] = 1 if data.get("activa") else 0
        sid = db.guardar_sucursal(data)
        flash(f"Sucursal creada correctamente (ID: {sid})", "success")
        return redirect(url_for("admin.sucursales"))
    return render_template("admin/sucursal_form.html", sucursal=None)

@bp.route("/sucursales/<int:sid>/editar", methods=["GET","POST"])
@admin_required
def editar_sucursal(sid):
    sucursal = db.get_sucursal(sid)
    if not sucursal:
        flash("Sucursal no encontrada", "error")
        return redirect(url_for("admin.sucursales"))
    if request.method == "POST":
        data = {k: request.form.get(k,"") for k in ["nombre","direccion","ciudad","estado","cp","telefono","email","activa"]}
        data["activa"] = 1 if data.get("activa") else 0
        db.guardar_sucursal(data, sid=sid)
        flash("Sucursal actualizada", "success")
        return redirect(url_for("admin.sucursales"))
    return render_template("admin/sucursal_form.html", sucursal=sucursal)

@bp.route("/sucursales/<int:sid>/config", methods=["GET","POST"])
@admin_required
def config_sucursal(sid):
    sucursal = db.get_sucursal(sid)
    if not sucursal:
        flash("Sucursal no encontrada", "error")
        return redirect(url_for("admin.sucursales"))
    if request.method == "POST":
        for clave in ["empresa_nombre","empresa_telefono","empresa_direccion",
                      "empresa_colonia","empresa_ciudad","empresa_estado","empresa_cp",
                      "empresa_rfc","empresa_email","markup_json"]:
            val = request.form.get(clave)
            if val is not None:
                db.set_config_sucursal(sid, clave, val)
        flash("Configuración guardada", "success")
        return redirect(url_for("admin.config_sucursal", sid=sid))
    config = db.get_config_sucursal(sid)
    return render_template("admin/sucursal_config.html", sucursal=sucursal, config=config)

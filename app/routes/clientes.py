from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.modules import database as db

bp = Blueprint("clientes", __name__)

@bp.route("/clientes")
@login_required
def lista():
    q       = request.args.get("q", "")
    clientes = db.get_clientes(q)
    return render_template("clientes/lista.html", clientes=clientes, q=q)

@bp.route("/clientes/nuevo", methods=["GET","POST"])
@login_required
def nuevo():
    if request.method == "POST":
        data = {k: request.form.get(k,"") for k in
                ["nombre","empresa","telefono","email","rfc",
                 "direccion","colonia","ciudad","estado","cp","notas"]}
        if not data["nombre"].strip():
            flash("El nombre es requerido", "error")
            return render_template("clientes/form.html", cliente=data, accion="Crear")
        db.guardar_cliente(data)
        flash(f"Cliente {data['nombre']} creado", "success")
        return redirect(url_for("clientes.lista"))
    return render_template("clientes/form.html", cliente={}, accion="Crear")

@bp.route("/clientes/<int:cid>/editar", methods=["GET","POST"])
@login_required
def editar(cid):
    cliente = db.get_cliente(cid)
    if not cliente:
        flash("Cliente no encontrado", "error")
        return redirect(url_for("clientes.lista"))
    if request.method == "POST":
        data = {k: request.form.get(k,"") for k in
                ["nombre","empresa","telefono","email","rfc",
                 "direccion","colonia","ciudad","estado","cp","notas"]}
        db.guardar_cliente(data, cid=cid)
        flash(f"Cliente actualizado", "success")
        return redirect(url_for("clientes.lista"))
    return render_template("clientes/form.html", cliente=cliente, accion="Guardar")

@bp.route("/clientes/<int:cid>")
@login_required
def detalle(cid):
    cliente = db.get_cliente(cid)
    if not cliente:
        flash("Cliente no encontrado", "error")
        return redirect(url_for("clientes.lista"))
    conn  = db.get_connection()
    ph    = db._ph()
    cur   = conn.cursor()
    cur.execute(f"SELECT * FROM guias WHERE cliente_id={ph} ORDER BY creado_en DESC LIMIT 20", (cid,))
    guias = cur.fetchall()
    conn.close()
    return render_template("clientes/detalle.html", cliente=cliente,
                           guias=[dict(g) for g in guias])

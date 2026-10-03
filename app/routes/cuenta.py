from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.modules import database as db
import hashlib

bp = Blueprint("cuenta", __name__)

@bp.route("/mi-cuenta")
@login_required
def index():
    return render_template("cuenta/index.html")

@bp.route("/mi-cuenta/password", methods=["POST"])
@login_required
def cambiar_password():
    actual   = request.form.get("password_actual","")
    nuevo    = request.form.get("password_nuevo","")
    confirma = request.form.get("password_confirma","")

    if not all([actual, nuevo, confirma]):
        flash("Todos los campos son requeridos", "error")
        return redirect(url_for("cuenta.index"))
    if nuevo != confirma:
        flash("Las contrasenas nuevas no coinciden", "error")
        return redirect(url_for("cuenta.index"))
    if len(nuevo) < 6:
        flash("La contrasena debe tener al menos 6 caracteres", "error")
        return redirect(url_for("cuenta.index"))

    # Verificar contrasena actual
    user = db.verificar_login(current_user.usuario, actual)
    if not user:
        flash("La contrasena actual es incorrecta", "error")
        return redirect(url_for("cuenta.index"))

    h = hashlib.sha256(nuevo.encode()).hexdigest()
    conn = db.get_connection()
    cur = conn.cursor(); ph = db._ph(); cur.execute(f"UPDATE usuarios SET password_hash={ph} WHERE id={ph}", (h, current_user.id))
    conn.commit()
    conn.close()
    flash("Contrasena actualizada correctamente", "success")
    return redirect(url_for("cuenta.index"))

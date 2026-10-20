from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask import session
from flask_login import login_user, logout_user, login_required
from app.models import User
import app.modules.database as db
from app.modules import mailer

bp = Blueprint("auth", __name__)

@bp.route("/")
def index():
    return redirect(url_for("guias.nueva"))

@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario  = request.form.get("usuario", "").strip()
        password = request.form.get("password", "")
        user     = User.authenticate(usuario, password)
        if user and user.activo:
            login_user(user, remember=True)
            return redirect(request.args.get("next") or url_for("guias.nueva"))
        flash("Usuario o contraseña incorrectos", "error")
    return render_template("auth/login.html")

@bp.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("auth.login"))


# ─── RECUPERACIÓN DE CONTRASEÑA ──────────────────────────────────────────────

@bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        if not email:
            flash("Ingresa tu correo electrónico", "error")
            return render_template("auth/forgot_password.html")

        usuario = db.get_usuario_por_email(email)
        # Siempre mostramos el mismo mensaje (seguridad — no revelar si el email existe)
        if usuario and mailer.esta_configurado():
            try:
                token = db.crear_reset_token(usuario["id"])
                mailer.enviar_reset_password(email, usuario["nombre"], token)
            except Exception as e:
                # Log del error pero no lo mostramos al usuario
                print(f"[MAIL ERROR] {e}")
        flash("Si ese correo está registrado, recibirás un enlace en minutos.", "ok")
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html")


@bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    uid = db.verificar_reset_token(token)
    if not uid:
        flash("El enlace no es válido o ya expiró. Solicita uno nuevo.", "error")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        pwd1 = request.form.get("password", "")
        pwd2 = request.form.get("password2", "")
        if len(pwd1) < 6:
            flash("La contraseña debe tener al menos 6 caracteres", "error")
            return render_template("auth/reset_password.html", token=token)
        if pwd1 != pwd2:
            flash("Las contraseñas no coinciden", "error")
            return render_template("auth/reset_password.html", token=token)

        ok = db.consumir_reset_token(token, pwd1)
        if ok:
            flash("Contraseña actualizada correctamente. Inicia sesión.", "ok")
            return redirect(url_for("auth.login"))
        else:
            flash("Enlace inválido o expirado", "error")
            return redirect(url_for("auth.forgot_password"))

    return render_template("auth/reset_password.html", token=token)

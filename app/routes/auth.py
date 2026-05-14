from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask import session
from flask_login import login_user, logout_user, login_required
from app.models import User

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
        flash("Usuario o contrasena incorrectos", "error")
    return render_template("auth/login.html")

@bp.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()  # Limpia toda la sesión al cerrar
    return redirect(url_for("auth.login"))

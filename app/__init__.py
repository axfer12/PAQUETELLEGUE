"""PAQUETELLEGUE Web — Flask App Factory"""
import os, logging
from datetime import timedelta
from flask import Flask, jsonify, request, make_response
from flask_login import LoginManager, current_user, logout_user
from config import Config

logging.basicConfig(level=logging.INFO)
login_manager = LoginManager()

def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

    # ── Filtro de zona horaria México (UTC-6) ─────────────────────────────
    from datetime import datetime, timezone, timedelta
    _MX_TZ = timezone(timedelta(hours=-6))  # México Centro (sin DST desde 2022)

    @app.template_filter('mx_time')
    def mx_time_filter(value):
        """Convierte fecha UTC a hora México (UTC-6) para mostrar en templates."""
        if not value:
            return ''
        try:
            # Parsear la fecha — puede venir como string o datetime
            if isinstance(value, str):
                # Limpiar microsegundos y timezone si vienen en el string
                v = value[:19].replace('T', ' ')
                dt = datetime.strptime(v, '%Y-%m-%d %H:%M:%S')
            else:
                dt = value
            # Asumir que viene en UTC y convertir a México
            dt_utc = dt.replace(tzinfo=timezone.utc)
            dt_mx  = dt_utc.astimezone(_MX_TZ)
            return dt_mx.strftime('%Y-%m-%d %H:%M')
        except Exception:
            return str(value)[:16]
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config.from_object(Config)

    for d in [Config.DATA_DIR, Config.GUIAS_DIR, Config.RECIBOS_DIR, Config.FACTURAS_DIR]:
        os.makedirs(d, exist_ok=True)

    from app.modules import database as db
    db.DB_PATH = Config.DB_PATH
    db.init_db()

    login_manager.init_app(app)
    login_manager.login_view             = "auth.login"
    login_manager.login_message          = "Inicia sesion para continuar"
    login_manager.login_message_category = "warning"

    from app.models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.get_by_id(int(user_id))

    @app.route("/debug_db")
    def debug_db():
        import sqlite3
        info = {"db_path": db.DB_PATH, "exists": os.path.exists(db.DB_PATH)}
        try:
            conn = db.get_connection()
            cur = conn.cursor()
            cur.execute("SELECT id, numero_guia, label_url, estatus FROM guias ORDER BY id DESC LIMIT 3")
            guias = cur.fetchall()
            info["ultimas_guias"] = [dict(g) for g in guias]
            conn.close()
        except Exception as e:
            info["error"] = str(e)
        return jsonify(info)

    from app.routes.auth     import bp as auth_bp
    from app.routes.guias    import bp as guias_bp
    from app.routes.api      import bp as api_bp
    from app.routes.admin    import bp as admin_bp
    from app.routes.clientes import bp as clientes_bp
    from app.routes.cuenta     import bp as cuenta_bp
    from app.routes.impresion  import bp as impresion_bp
    from app.routes.webhook    import bp as webhook_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(guias_bp)
    app.register_blueprint(api_bp,      url_prefix="/api")
    app.register_blueprint(admin_bp,    url_prefix="/admin")
    app.register_blueprint(clientes_bp)
    app.register_blueprint(cuenta_bp)
    app.register_blueprint(impresion_bp, url_prefix='/impresion')
    app.register_blueprint(webhook_bp)  # /webhook/skydropx

    from app.routes.cancelaciones import bp as cancelaciones_bp
    app.register_blueprint(cancelaciones_bp)

    # ── Sesión permanente de 30 min ──────────────────────────────────────────
    from flask import session
    @app.before_request
    def renovar_sesion():
        session.permanent = True

    @app.context_processor
    def inyectar_pendientes():
        """Inyecta el conteo de solicitudes pendientes en todos los templates."""
        try:
            from flask_login import current_user
            if current_user.is_authenticated and (current_user.is_supervisor or current_user.is_admin):
                from app.modules import database as _db
                pendientes = _db.get_solicitudes_pendientes()
                return {"cancelaciones_pendientes": len(pendientes)}
        except Exception:
            pass
        return {"cancelaciones_pendientes": 0}

    # ── Headers anti-caché en todas las respuestas HTML ──────────────────────
    @app.after_request
    def no_cache(response):
        # Archivos estáticos: no-store
        if request.path.startswith('/static/'):
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        # Páginas HTML: no guardar en historial del navegador tras logout
        elif response.content_type.startswith('text/html'):
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
        return response

    return app

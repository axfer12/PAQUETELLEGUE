from flask_login import UserMixin
from app.modules import database as db


class User(UserMixin):
    def __init__(self, data: dict):
        self.id             = data["id"]
        self.nombre         = data["nombre"]
        self.usuario        = data["usuario"]
        self.rol            = data["rol"]
        self.activo         = data.get("activo", 1)
        self.sucursal_id    = data.get("sucursal_id", 1) or 1
        self.sucursal_nombre= data.get("sucursal_nombre", "")

    def get_id(self):
        return str(self.id)

    @property
    def is_admin(self):
        return self.rol == "admin"

    @property
    def is_supervisor(self):
        return self.rol in ("admin", "supervisor")

    @property
    def is_admin_global(self):
        """Admin global puede ver y gestionar todas las sucursales."""
        return self.rol == "admin"

    @staticmethod
    def get_by_id(user_id):
        conn = db.get_connection()
        cur = conn.cursor()
        ph = "%s" if db._is_postgres() else "?"
        cur.execute(f"""
            SELECT u.*, s.nombre as sucursal_nombre
            FROM usuarios u
            LEFT JOIN sucursales s ON u.sucursal_id = s.id
            WHERE u.id={ph}
        """, (user_id,))
        row = cur.fetchone()
        conn.close()
        return User(dict(row)) if row else None

    @staticmethod
    def authenticate(usuario, password):
        u = db.verificar_login(usuario, password)
        if not u: return None
        conn = db.get_connection()
        cur = conn.cursor()
        ph = "%s" if db._is_postgres() else "?"
        cur.execute(f"""
            SELECT u.*, s.nombre as sucursal_nombre
            FROM usuarios u
            LEFT JOIN sucursales s ON u.sucursal_id = s.id
            WHERE u.id={ph}
        """, (u["id"],))
        row = cur.fetchone()
        conn.close()
        return User(dict(row)) if row else None

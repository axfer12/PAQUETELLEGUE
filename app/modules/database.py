"""
Módulo de base de datos — PostgreSQL (Render) con fallback a SQLite (local).
"""
import hashlib
import json
from datetime import datetime
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "")

def _is_postgres():
    return bool(DATABASE_URL and DATABASE_URL.startswith("postgres"))

def get_connection():
    if _is_postgres():
        import psycopg2
        import psycopg2.extras
        url = DATABASE_URL.replace("postgresql://", "postgres://", 1)
        conn = psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)
        conn.autocommit = False
        return conn
    else:
        import sqlite3
        DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sistema.db")
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

def _migrate_insumos(conn, pg):
    """Agrega columnas nuevas a insumos si no existen (migración segura)."""
    cur = conn.cursor()
    columnas_nuevas = [
        ("costo",         "REAL NOT NULL DEFAULT 0"),
        ("stock",         "INTEGER NOT NULL DEFAULT 0"),
        ("stock_minimo",  "INTEGER NOT NULL DEFAULT 3"),
    ]
    for col, tipo in columnas_nuevas:
        try:
            if pg:
                cur.execute(f"ALTER TABLE insumos ADD COLUMN {col} {tipo}")
            else:
                cur.execute(f"ALTER TABLE insumos ADD COLUMN {col} {tipo}")
            conn.commit()
        except Exception:
            conn.rollback()  # Columna ya existe — ignorar

def _migrate_clientes(conn, pg):
    """Agrega columna pais a clientes si no existe."""
    cur = conn.cursor()
    try:
        cur.execute("ALTER TABLE clientes ADD COLUMN pais TEXT DEFAULT 'MX'")
        conn.commit()
    except Exception:
        conn.rollback()  # Ya existe

def _ph():
    return "%s" if _is_postgres() else "?"

def get_conn():
    """Retorna (conn, cursor, placeholder) listo para usar."""
    conn = get_connection()
    cur = conn.cursor()
    ph = _ph()
    return conn, cur, ph

def init_db():
    conn = get_connection()
    pg = _is_postgres()
    cur = conn.cursor()

    tables = [
        """CREATE TABLE IF NOT EXISTS sucursales (
            id {pk},
            nombre TEXT NOT NULL,
            direccion TEXT DEFAULT '',
            ciudad TEXT DEFAULT '',
            estado TEXT DEFAULT '',
            cp TEXT DEFAULT '',
            telefono TEXT DEFAULT '',
            email TEXT DEFAULT '',
            activa INTEGER DEFAULT 1,
            creado_en TEXT DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS usuarios (
            id {pk},
            nombre TEXT NOT NULL,
            usuario TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            rol TEXT NOT NULL DEFAULT 'operario',
            activo INTEGER DEFAULT 1,
            sucursal_id INTEGER DEFAULT 1,
            creado_en TEXT DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS impresoras (
            id {pk},
            nombre TEXT NOT NULL,
            nombre_sistema TEXT NOT NULL,
            activa INTEGER DEFAULT 1,
            predeterminada INTEGER DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS clientes (
            id {pk},
            sucursal_id INTEGER DEFAULT 1,
            nombre TEXT NOT NULL,
            empresa TEXT, telefono TEXT, email TEXT, rfc TEXT,
            direccion TEXT, colonia TEXT, ciudad TEXT, estado TEXT, cp TEXT, pais TEXT DEFAULT 'MX', notas TEXT,
            creado_en TEXT DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS tarifas (
            id {pk},
            servicio TEXT NOT NULL, zona TEXT,
            peso_min REAL DEFAULT 0, peso_max REAL DEFAULT 999,
            costo_proveedor REAL NOT NULL, precio_venta REAL NOT NULL,
            activa INTEGER DEFAULT 1, notas TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS promociones (
            id {pk},
            sucursal_id INTEGER DEFAULT 1,
            nombre TEXT NOT NULL, tipo TEXT NOT NULL, valor REAL NOT NULL,
            cliente_id INTEGER, servicio TEXT, fecha_inicio TEXT, fecha_fin TEXT,
            activa INTEGER DEFAULT 1, codigo TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS guias (
            id {pk},
            sucursal_id INTEGER DEFAULT 1,
            numero_guia TEXT UNIQUE NOT NULL,
            cliente_id INTEGER, operario_id INTEGER NOT NULL, servicio TEXT NOT NULL,
            remitente_nombre TEXT, remitente_telefono TEXT, remitente_direccion TEXT,
            remitente_colonia TEXT, remitente_ciudad TEXT, remitente_estado TEXT, remitente_cp TEXT,
            destinatario_nombre TEXT NOT NULL, destinatario_telefono TEXT,
            destinatario_direccion TEXT NOT NULL, destinatario_colonia TEXT,
            destinatario_ciudad TEXT NOT NULL, destinatario_estado TEXT NOT NULL, destinatario_cp TEXT NOT NULL,
            peso REAL, alto REAL, ancho REAL, largo REAL, contenido TEXT,
            costo_proveedor REAL NOT NULL, precio_venta REAL NOT NULL,
            descuento REAL DEFAULT 0, precio_final REAL NOT NULL, costo_seguro REAL DEFAULT 0,
            promocion_id INTEGER, status TEXT DEFAULT 'activa',
            pdf_path TEXT, shipment_id_proveedor TEXT, label_url TEXT, numero_rastreo TEXT,
            metodo_pago TEXT DEFAULT 'efectivo', confirmacion_terminal TEXT DEFAULT '',
            estatus TEXT DEFAULT 'activa', productos_factura_json TEXT DEFAULT '[]',
            destinatario_pais TEXT DEFAULT 'MX', shipment_purpose TEXT DEFAULT 'personal',
            creado_en TEXT DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS configuracion (
            clave TEXT PRIMARY KEY,
            valor TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS configuracion_sucursal (
            sucursal_id INTEGER NOT NULL,
            clave TEXT NOT NULL,
            valor TEXT,
            PRIMARY KEY (sucursal_id, clave)
        )""",
        """CREATE TABLE IF NOT EXISTS solicitudes_cancelacion (
            id {pk},
            sucursal_id INTEGER DEFAULT 1,
            tipo TEXT NOT NULL,
            referencia_id INTEGER NOT NULL,
            descripcion TEXT NOT NULL,
            motivo TEXT NOT NULL,
            operario_id INTEGER NOT NULL,
            estatus TEXT NOT NULL DEFAULT 'pendiente',
            supervisor_id INTEGER,
            creado_en TEXT DEFAULT CURRENT_TIMESTAMP,
            resuelto_en TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS supervisor_pins (
            usuario_id INTEGER PRIMARY KEY,
            pin_hash TEXT NOT NULL,
            actualizado_en TEXT DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS insumos (
            id {pk},
            sucursal_id INTEGER DEFAULT 1,
            nombre TEXT NOT NULL,
            descripcion TEXT DEFAULT '',
            costo REAL NOT NULL DEFAULT 0,
            precio REAL NOT NULL DEFAULT 0,
            stock INTEGER NOT NULL DEFAULT 0,
            stock_minimo INTEGER NOT NULL DEFAULT 3,
            activo INTEGER DEFAULT 1,
            creado_en TEXT DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS guia_insumos (
            id {pk},
            guia_id INTEGER NOT NULL,
            insumo_id INTEGER NOT NULL,
            cantidad INTEGER NOT NULL DEFAULT 1,
            precio_unitario REAL NOT NULL,
            subtotal REAL NOT NULL
        )""",
    ]

    pk = "SERIAL PRIMARY KEY" if pg else "INTEGER PRIMARY KEY AUTOINCREMENT"
    for t in tables:
        try:
            cur.execute(t.format(pk=pk))
            conn.commit()
        except Exception:
            conn.rollback()

    # Sucursal 1 por defecto
    try:
        if pg:
            cur.execute("INSERT INTO sucursales (id,nombre,activa) VALUES (1,'Sucursal Principal',1) ON CONFLICT (id) DO NOTHING")
        else:
            cur.execute("INSERT OR IGNORE INTO sucursales (id,nombre,activa) VALUES (1,'Sucursal Principal',1)")
        conn.commit()
    except Exception:
        conn.rollback()

    # Admin por defecto
    admin_hash = hashlib.sha256("admin123".encode()).hexdigest()
    try:
        if pg:
            cur.execute("INSERT INTO usuarios (nombre,usuario,password_hash,rol,sucursal_id) VALUES (%s,%s,%s,%s,1) ON CONFLICT (usuario) DO NOTHING",
                        ("Administrador","admin",admin_hash,"admin"))
        else:
            cur.execute("INSERT OR IGNORE INTO usuarios (nombre,usuario,password_hash,rol,sucursal_id) VALUES (?,?,?,?,1)",
                        ("Administrador","admin",admin_hash,"admin"))
        conn.commit()
    except Exception:
        conn.rollback()

    # Config por defecto
    defaults = [
        ("empresa_nombre","PAQUETELLEGUE"),("empresa_telefono",""),("empresa_direccion",""),
        ("empresa_colonia",""),("empresa_ciudad",""),("empresa_estado",""),
        ("empresa_cp",""),("empresa_rfc",""),("empresa_email",""),("empresa_logo",""),
        ("moneda","MXN"),("iva","0"),("mostrar_iva","0"),("markup_json",'{"nacional":30,"internacional":40}'),
        ("forma_pago_default","EFECTIVO"),
        ("mensaje_recibo","Gracias por su preferencia. Conserve su recibo para cualquier aclaracion."),
        ("recibo_mostrar_ventana","1"),("recibo_auto_imprimir","0"),
        ("tracking_url","https://tracking.skydropx.com/es-MX/page/PAQUETELLEGUELORETO"),
    ]
    for clave, valor in defaults:
        try:
            if pg:
                cur.execute("INSERT INTO configuracion (clave,valor) VALUES (%s,%s) ON CONFLICT (clave) DO NOTHING", (clave,valor))
            else:
                cur.execute("INSERT OR IGNORE INTO configuracion VALUES (?,?)", (clave,valor))
            conn.commit()
        except Exception:
            conn.rollback()

    # Migraciones
    _migrate_insumos(conn, pg)
    _migrate_clientes(conn, pg)
    _migrate_multisucursal(conn, pg)

    conn.close()


def _migrate_multisucursal(conn, pg):
    """Agrega sucursal_id a tablas existentes y crea tabla sucursales."""
    cur = conn.cursor()
    pk_def = "SERIAL PRIMARY KEY" if pg else "INTEGER PRIMARY KEY AUTOINCREMENT"
    # Crear tabla sucursales si no existe
    try:
        cur.execute(f"""CREATE TABLE IF NOT EXISTS sucursales (
            id {pk_def},
            nombre TEXT NOT NULL,
            direccion TEXT DEFAULT '',
            ciudad TEXT DEFAULT '',
            estado TEXT DEFAULT '',
            cp TEXT DEFAULT '',
            telefono TEXT DEFAULT '',
            email TEXT DEFAULT '',
            activa INTEGER DEFAULT 1,
            creado_en TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.commit()
    except Exception: conn.rollback()
    # Crear tabla configuracion_sucursal si no existe
    try:
        cur.execute("""CREATE TABLE IF NOT EXISTS configuracion_sucursal (
            sucursal_id INTEGER NOT NULL,
            clave TEXT NOT NULL,
            valor TEXT,
            PRIMARY KEY (sucursal_id, clave)
        )""")
        conn.commit()
    except Exception: conn.rollback()
    # Insertar sucursal principal
    try:
        if pg:
            cur.execute("INSERT INTO sucursales (id,nombre,activa) VALUES (1,'Sucursal Principal',1) ON CONFLICT (id) DO NOTHING")
        else:
            cur.execute("INSERT OR IGNORE INTO sucursales (id,nombre,activa) VALUES (1,'Sucursal Principal',1)")
        conn.commit()
    except Exception: conn.rollback()
    # Agregar sucursal_id a tablas existentes
    for tabla in ["usuarios","clientes","guias","insumos","promociones","solicitudes_cancelacion"]:
        try:
            cur.execute(f"ALTER TABLE {tabla} ADD COLUMN sucursal_id INTEGER DEFAULT 1")
            conn.commit()
        except Exception: conn.rollback()
    # Asignar sucursal_id=1 a registros sin sucursal
    for tabla in ["usuarios","clientes","guias","insumos","promociones","solicitudes_cancelacion"]:
        try:
            cur.execute(f"UPDATE {tabla} SET sucursal_id=1 WHERE sucursal_id IS NULL")
            conn.commit()
        except Exception: conn.rollback()


# ─── SUCURSALES ───────────────────────────────────────────────────

def get_sucursales(solo_activas=False):
    conn, cur, ph = get_conn()
    q = "SELECT * FROM sucursales" + (" WHERE activa=1" if solo_activas else "") + " ORDER BY id"
    cur.execute(q)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_sucursal(sid):
    conn, cur, ph = get_conn()
    cur.execute(f"SELECT * FROM sucursales WHERE id={ph}", (sid,))
    r = cur.fetchone()
    conn.close()
    return dict(r) if r else None

def guardar_sucursal(data, sid=None):
    conn, cur, ph = get_conn()
    campos = ["nombre","direccion","ciudad","estado","cp","telefono","email","activa"]
    vals   = [data.get(c,"") for c in campos]
    try:
        if sid:
            sets = ", ".join(f"{c}={ph}" for c in campos)
            cur.execute(f"UPDATE sucursales SET {sets} WHERE id={ph}", vals+[sid])
        else:
            cols = ", ".join(campos)
            phs  = ", ".join([ph]*len(campos))
            if _is_postgres():
                cur.execute(f"INSERT INTO sucursales ({cols}) VALUES ({phs}) RETURNING id", vals)
                sid = cur.fetchone()[0]
            else:
                cur.execute(f"INSERT INTO sucursales ({cols}) VALUES ({phs})", vals)
                sid = cur.lastrowid
        conn.commit(); conn.close()
        return sid
    except Exception as e:
        conn.rollback(); conn.close(); raise e

def get_config_sucursal(sucursal_id):
    """Config de sucursal con fallback a config global."""
    conn, cur, ph = get_conn()
    def _row_to_kv(r):
        if hasattr(r, 'keys'):
            return r['clave'], r['valor']
        return r[0], r[1]
    cur.execute("SELECT clave, valor FROM configuracion")
    cfg = dict(_row_to_kv(r) for r in cur.fetchall())
    cur.execute(f"SELECT clave, valor FROM configuracion_sucursal WHERE sucursal_id={ph}", (sucursal_id,))
    for r in cur.fetchall():
        k, v = _row_to_kv(r)
        cfg[k] = v
    conn.close()
    return cfg

def set_config_sucursal(sucursal_id, clave, valor):
    conn, cur, ph = get_conn()
    pg = _is_postgres()
    try:
        if pg:
            cur.execute(f"INSERT INTO configuracion_sucursal (sucursal_id,clave,valor) VALUES ({ph},{ph},{ph}) ON CONFLICT (sucursal_id,clave) DO UPDATE SET valor=EXCLUDED.valor",
                       (sucursal_id, clave, valor))
        else:
            cur.execute(f"INSERT OR REPLACE INTO configuracion_sucursal (sucursal_id,clave,valor) VALUES ({ph},{ph},{ph})",
                       (sucursal_id, clave, valor))
        conn.commit(); conn.close()
    except Exception as e:
        conn.rollback(); conn.close(); raise e

def verificar_login(usuario, password):
    h = hashlib.sha256(password.encode()).hexdigest()
    conn = get_connection()
    cur = conn.cursor()
    ph = _ph()
    cur.execute(f"SELECT * FROM usuarios WHERE usuario={ph} AND password_hash={ph} AND activo=1", (usuario,h))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def get_usuarios():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id,nombre,usuario,rol,activo,creado_en FROM usuarios ORDER BY nombre")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def crear_usuario(nombre, usuario, password, rol, sucursal_id=1):
    h = hashlib.sha256(password.encode()).hexdigest()
    conn = get_connection()
    ph = _ph()
    try:
        cur = conn.cursor()
        cur.execute(f"INSERT INTO usuarios (nombre,usuario,password_hash,rol,sucursal_id) VALUES ({ph},{ph},{ph},{ph},{ph})",
                    (nombre,usuario,h,rol,sucursal_id or 1))
        conn.commit()
        return True, "Usuario creado correctamente"
    except Exception:
        conn.rollback()
        return False, "El nombre de usuario ya existe"
    finally:
        conn.close()

def actualizar_usuario(uid, nombre, rol, activo, nueva_password=None):
    conn = get_connection()
    cur = conn.cursor()
    ph = _ph()
    if nueva_password:
        h = hashlib.sha256(nueva_password.encode()).hexdigest()
        cur.execute(f"UPDATE usuarios SET nombre={ph},rol={ph},activo={ph},password_hash={ph} WHERE id={ph}",
                    (nombre,rol,activo,h,uid))
    else:
        cur.execute(f"UPDATE usuarios SET nombre={ph},rol={ph},activo={ph} WHERE id={ph}",
                    (nombre,rol,activo,uid))
    conn.commit()
    conn.close()

def cambiar_password(uid, nueva_password):
    h = hashlib.sha256(nueva_password.encode()).hexdigest()
    conn = get_connection()
    cur = conn.cursor()
    ph = _ph()
    cur.execute(f"UPDATE usuarios SET password_hash={ph} WHERE id={ph}", (h,uid))
    conn.commit()
    conn.close()


# ─── CLIENTES ────────────────────────────────────────────────────

def get_clientes(busqueda="", sucursal_id=None):
    conn = get_connection()
    cur = conn.cursor()
    ph = _ph()
    pg = _is_postgres()
    q = f"%{busqueda}%"
    like = "ILIKE" if pg else "LIKE"
    base = f"SELECT * FROM clientes WHERE (nombre {like} {ph} OR empresa {like} {ph} OR telefono {like} {ph} OR email {like} {ph})"
    params = [q,q,q,q]
    if sucursal_id:
        base += f" AND sucursal_id={ph}"
        params.append(sucursal_id)
    cur.execute(base + " ORDER BY nombre", params)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_cliente(cid):
    conn = get_connection()
    cur = conn.cursor()
    ph = _ph()
    cur.execute(f"SELECT * FROM clientes WHERE id={ph}", (cid,))
    r = cur.fetchone()
    conn.close()
    if not r: return None
    d = dict(r)
    d['calle'] = d.get('direccion','')
    if 'pais' not in d: d['pais'] = 'MX'
    return d

def guardar_cliente(data, cid=None):
    if 'calle' in data and 'direccion' not in data:
        data = dict(data)
        data['direccion'] = data.pop('calle')
    campos = ["nombre","empresa","telefono","email","rfc","direccion","colonia","ciudad","estado","cp","pais","notas","sucursal_id"]
    conn = get_connection()
    cur = conn.cursor()
    ph = _ph()
    pg = _is_postgres()
    if cid:
        sets = ", ".join(f"{c}={ph}" for c in campos)
        vals = [data.get(c,"") for c in campos] + [cid]
        cur.execute(f"UPDATE clientes SET {sets} WHERE id={ph}", vals)
    else:
        cols = ", ".join(campos)
        phs = ", ".join(ph for _ in campos)
        vals = [data.get(c,"") for c in campos]
        cur.execute(f"INSERT INTO clientes ({cols}) VALUES ({phs})", vals)
        if pg:
            cur.execute("SELECT lastval()")
            _r = cur.fetchone(); cid = _r["lastval"] if isinstance(_r, dict) else _r[0]
        else:
            cid = cur.lastrowid
    conn.commit()
    conn.close()
    return cid


# ─── TARIFAS ─────────────────────────────────────────────────────

def get_tarifas():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tarifas ORDER BY servicio,peso_min")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_servicios_activos():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT servicio FROM tarifas WHERE activa=1")
    rows = cur.fetchall()
    conn.close()
    return [r["servicio"] if isinstance(r,dict) else r[0] for r in rows]

def guardar_tarifa(data, tid=None):
    campos = ["servicio","zona","peso_min","peso_max","costo_proveedor","precio_venta","activa","notas"]
    conn = get_connection()
    cur = conn.cursor()
    ph = _ph()
    if tid:
        sets = ", ".join(f"{c}={ph}" for c in campos)
        vals = [data.get(c) for c in campos] + [tid]
        cur.execute(f"UPDATE tarifas SET {sets} WHERE id={ph}", vals)
    else:
        cols = ", ".join(campos)
        phs = ", ".join(ph for _ in campos)
        vals = [data.get(c) for c in campos]
        cur.execute(f"INSERT INTO tarifas ({cols}) VALUES ({phs})", vals)
    conn.commit()
    conn.close()

def eliminar_tarifa(tid):
    conn = get_connection()
    cur = conn.cursor()
    ph = _ph()
    cur.execute(f"DELETE FROM tarifas WHERE id={ph}", (tid,))
    conn.commit()
    conn.close()


# ─── PROMOCIONES ──────────────────────────────────────────────────

def get_promociones():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT p.*,c.nombre as cliente_nombre FROM promociones p LEFT JOIN clientes c ON p.cliente_id=c.id ORDER BY p.nombre")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def guardar_promocion(data, pid=None):
    campos = ["nombre","tipo","valor","cliente_id","servicio","fecha_inicio","fecha_fin","activa","codigo"]
    conn = get_connection()
    cur = conn.cursor()
    ph = _ph()
    if pid:
        sets = ", ".join(f"{c}={ph}" for c in campos)
        vals = [data.get(c) for c in campos] + [pid]
        cur.execute(f"UPDATE promociones SET {sets} WHERE id={ph}", vals)
    else:
        cols = ", ".join(campos)
        phs = ", ".join(ph for _ in campos)
        vals = [data.get(c) for c in campos]
        cur.execute(f"INSERT INTO promociones ({cols}) VALUES ({phs})", vals)
    conn.commit()
    conn.close()

def aplicar_promocion(codigo, precio, servicio=None, cliente_id=None):
    hoy = datetime.now().strftime("%Y-%m-%d")
    conn = get_connection()
    cur = conn.cursor()
    ph = _ph()
    cur.execute(f"""
        SELECT * FROM promociones WHERE activa=1
        AND (fecha_inicio IS NULL OR fecha_inicio <= {ph})
        AND (fecha_fin IS NULL OR fecha_fin >= {ph})
        AND codigo = {ph}
        AND (cliente_id IS NULL OR cliente_id = {ph})
        AND (servicio IS NULL OR servicio = {ph})
        LIMIT 1
    """, (hoy,hoy,codigo,cliente_id,servicio))
    row = cur.fetchone()
    conn.close()
    if not row: return 0, None, None
    p = dict(row)
    nombre = p.get("nombre", "Descuento")
    if p["tipo"] == "porcentaje": return round(precio*p["valor"]/100,2), p["id"], nombre
    elif p["tipo"] == "fijo": return min(p["valor"],precio), p["id"], nombre
    return 0, None, None


# ─── GUÍAS ───────────────────────────────────────────────────────

def crear_guia(data):
    import random, string
    if not data.get("numero_guia"):
        num = "GU"+datetime.now().strftime("%y%m%d")+"".join(random.choices(string.digits,k=5))
        data["numero_guia"] = num
    num = data["numero_guia"]
    campos = [
        "numero_guia","cliente_id","operario_id","servicio","sucursal_id",
        "remitente_nombre","remitente_telefono","remitente_direccion",
        "remitente_colonia","remitente_ciudad","remitente_estado","remitente_cp",
        "destinatario_nombre","destinatario_telefono","destinatario_direccion",
        "destinatario_colonia","destinatario_ciudad","destinatario_estado","destinatario_cp",
        "peso","alto","ancho","largo","contenido",
        "costo_proveedor","precio_venta","descuento","precio_final","costo_seguro","promocion_id",
        "pdf_path","shipment_id_proveedor","label_url","numero_rastreo",
        "metodo_pago","confirmacion_terminal",
        "productos_factura_json","destinatario_pais","shipment_purpose"
    ]
    # Campos enteros — convertir string vacío a None para Postgres
    _int_campos = {"cliente_id","operario_id","sucursal_id","promocion_id"}
    conn = get_connection()
    try:
        cur = conn.cursor()
        ph = _ph()
        cols = ", ".join(campos)
        phs = ", ".join(ph for _ in campos)
        vals = []
        for c in campos:
            v = data.get(c)
            if c in _int_campos:
                try: v = int(v) if v not in (None, "", "None") else None
                except: v = None
            vals.append(v)
        cur.execute(f"INSERT INTO guias ({cols}) VALUES ({phs})", vals)
        conn.commit()
        cur.execute(f"SELECT * FROM guias WHERE numero_guia={ph}", (num,))
        row = cur.fetchone()
        return dict(row) if row else {"id": None, "numero_guia": num}
    except Exception as _e:
        try: conn.rollback()
        except: pass
        print(f"ERROR crear_guia BD: {_e}", flush=True)
        raise
    finally:
        try: conn.close()
        except: pass

def get_guias(filtro="", fecha_ini=None, fecha_fin=None, operario_id=None, sucursal_id=None):
    conn = get_connection()
    cur = conn.cursor()
    ph = _ph()
    pg = _is_postgres()
    like = "ILIKE" if pg else "LIKE"
    q = f"%{filtro}%"
    params = [q,q,q]
    query = f"""
        SELECT g.*,u.nombre as operario_nombre,c.nombre as cliente_nombre_rel
        FROM guias g
        LEFT JOIN usuarios u ON g.operario_id=u.id
        LEFT JOIN clientes c ON g.cliente_id=c.id
        WHERE (g.numero_guia {like} {ph} OR g.destinatario_nombre {like} {ph} OR g.destinatario_ciudad {like} {ph})
    """
    if fecha_ini:
        query += f" AND DATE(g.creado_en) >= {ph}"; params.append(fecha_ini)
    if fecha_fin:
        query += f" AND DATE(g.creado_en) <= {ph}"; params.append(fecha_fin)
    if operario_id:
        query += f" AND g.operario_id = {ph}"; params.append(operario_id)
    if sucursal_id:
        query += f" AND g.sucursal_id = {ph}"; params.append(sucursal_id)
    query += " ORDER BY g.creado_en DESC"
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_guia(gid):
    conn = get_connection()
    cur = conn.cursor()
    ph = _ph()
    cur.execute(f"SELECT g.*,u.nombre as operario_nombre FROM guias g LEFT JOIN usuarios u ON g.operario_id=u.id WHERE g.id={ph}", (gid,))
    r = cur.fetchone()
    conn.close()
    return dict(r) if r else None

def cancelar_guia(gid):
    conn = get_connection()
    cur = conn.cursor()
    ph = _ph()
    cur.execute(f"UPDATE guias SET status='cancelada',estatus='cancelada' WHERE id={ph}", (gid,))
    conn.commit()
    conn.close()


# ─── CONFIGURACIÓN ───────────────────────────────────────────────

def get_config():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT clave,valor FROM configuracion")
    rows = cur.fetchall()
    conn.close()
    return {r["clave"]:r["valor"] for r in rows}

def set_config(clave, valor):
    conn = get_connection()
    cur = conn.cursor()
    if _is_postgres():
        cur.execute("INSERT INTO configuracion (clave,valor) VALUES (%s,%s) ON CONFLICT (clave) DO UPDATE SET valor=EXCLUDED.valor", (clave,valor))
    else:
        cur.execute("INSERT OR REPLACE INTO configuracion VALUES (?,?)", (clave,valor))
    conn.commit()
    conn.close()


# ─── REPORTES ────────────────────────────────────────────────────

def get_reporte(fecha_ini, fecha_fin, operario_id=None, sucursal_id=None):
    conn = get_connection()
    cur = conn.cursor()
    ph = _ph()
    params = [fecha_ini,fecha_fin]
    extras = ""
    if operario_id:
        extras += f" AND g.operario_id={ph}"; params.append(operario_id)
    if sucursal_id:
        extras += f" AND g.sucursal_id={ph}"; params.append(sucursal_id)
    cur.execute(f"""
        SELECT COUNT(*) as total_guias, SUM(precio_final) as total_ventas,
               SUM(costo_proveedor) as total_costo,
               SUM(precio_final-costo_proveedor) as ganancia_bruta,
               SUM(descuento) as total_descuentos
        FROM guias g WHERE DATE(creado_en) BETWEEN {ph} AND {ph}
        AND status != 'cancelada' {extras}
    """, params)
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else {}


# ─── IMPRESORAS ──────────────────────────────────────────────────

def get_impresoras():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM impresoras ORDER BY predeterminada DESC,nombre")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def guardar_impresora(data, iid=None):
    conn = get_connection()
    cur = conn.cursor()
    ph = _ph()
    if data.get("predeterminada"):
        cur.execute("UPDATE impresoras SET predeterminada=0")
    if iid:
        cur.execute(f"UPDATE impresoras SET nombre={ph},nombre_sistema={ph},activa={ph},predeterminada={ph} WHERE id={ph}",
                    (data["nombre"],data["nombre_sistema"],data.get("activa",1),data.get("predeterminada",0),iid))
    else:
        cur.execute(f"INSERT INTO impresoras (nombre,nombre_sistema,activa,predeterminada) VALUES ({ph},{ph},{ph},{ph})",
                    (data["nombre"],data["nombre_sistema"],data.get("activa",1),data.get("predeterminada",0)))
    conn.commit()
    conn.close()

def eliminar_impresora(iid):
    conn = get_connection()
    cur = conn.cursor()
    ph = _ph()
    cur.execute(f"DELETE FROM impresoras WHERE id={ph}", (iid,))
    conn.commit()
    conn.close()


# ── Insumos ──────────────────────────────────────────────────────────────────

def get_insumos(solo_activos=True, sucursal_id=None):
    conn, cur, ph = get_conn()
    cond = "WHERE activo=1" if solo_activos else "WHERE 1=1"
    params = []
    if sucursal_id:
        cond += f" AND sucursal_id={ph}"
        params.append(sucursal_id)
    cur.execute(f"SELECT * FROM insumos {cond} ORDER BY nombre", params)
    rows = []
    for r in cur.fetchall():
        if hasattr(r, 'keys'):
            rows.append(dict(r))
        else:
            rows.append({'id':r[0],'nombre':r[1],'descripcion':r[2],
                         'costo':r[3],'precio':r[4],'stock':r[5],
                         'stock_minimo':r[6],'activo':r[7],'creado_en':str(r[8])})
    conn.close()
    return rows

def crear_insumo(nombre, descripcion, costo, precio, stock, stock_minimo, sucursal_id=1):
    conn, cur, ph = get_conn()
    try:
        cur.execute(
            f"INSERT INTO insumos (nombre,descripcion,costo,precio,stock,stock_minimo,sucursal_id) "
            f"VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph})",
            (nombre, descripcion, float(costo), float(precio), int(stock), int(stock_minimo), sucursal_id or 1)
        )
        conn.commit()
        return True, "Insumo creado"
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def actualizar_insumo(iid, nombre, descripcion, costo, precio, stock, stock_minimo, activo):
    conn, cur, ph = get_conn()
    try:
        cur.execute(
            f"UPDATE insumos SET nombre={ph},descripcion={ph},costo={ph},precio={ph},"
            f"stock={ph},stock_minimo={ph},activo={ph} WHERE id={ph}",
            (nombre, descripcion, float(costo), float(precio), int(stock), int(stock_minimo), activo, iid)
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()

def agregar_stock_insumo(iid, cantidad):
    """Suma cantidad al stock existente (reabastecimiento)."""
    conn, cur, ph = get_conn()
    try:
        cur.execute(f"UPDATE insumos SET stock=stock+{ph} WHERE id={ph}", (int(cantidad), iid))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()

def guardar_guia_insumos(guia_id, items):
    """items = [{'insumo_id':x,'cantidad':n,'precio_unitario':p,'subtotal':s}, ...]"""
    if not items:
        return
    conn, cur, ph = get_conn()
    try:
        # Restaurar stock de items anteriores si existían
        cur.execute(f"SELECT insumo_id, cantidad FROM guia_insumos WHERE guia_id={ph}", (guia_id,))
        anteriores = cur.fetchall()
        for ant in anteriores:
            aid = ant[0] if not hasattr(ant,'keys') else ant['insumo_id']
            acant = ant[1] if not hasattr(ant,'keys') else ant['cantidad']
            cur.execute(f"UPDATE insumos SET stock=stock+{ph} WHERE id={ph}", (acant, aid))

        cur.execute(f"DELETE FROM guia_insumos WHERE guia_id={ph}", (guia_id,))
        for it in items:
            cur.execute(
                f"INSERT INTO guia_insumos (guia_id,insumo_id,cantidad,precio_unitario,subtotal) "
                f"VALUES ({ph},{ph},{ph},{ph},{ph})",
                (guia_id, it['insumo_id'], it['cantidad'], it['precio_unitario'], it['subtotal'])
            )
            # Descontar stock
            cur.execute(f"UPDATE insumos SET stock=stock-{ph} WHERE id={ph}",
                        (it['cantidad'], it['insumo_id']))
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()

def get_insumos_de_guia(guia_id):
    conn, cur, ph = get_conn()
    cur.execute(f"""
        SELECT gi.*, i.nombre, i.descripcion
        FROM guia_insumos gi JOIN insumos i ON gi.insumo_id=i.id
        WHERE gi.guia_id={ph}
    """, (guia_id,))
    rows = [dict(r) if hasattr(r,'keys') else
            {'id':r[0],'guia_id':r[1],'insumo_id':r[2],'cantidad':r[3],
             'precio_unitario':r[4],'subtotal':r[5],'nombre':r[6],'descripcion':r[7]}
            for r in cur.fetchall()]
    conn.close()
    return rows


# ── Solicitudes de cancelación ───────────────────────────────────────────────

def crear_solicitud_cancelacion(tipo, referencia_id, descripcion, motivo, operario_id, sucursal_id=1):
    conn, cur, ph = get_conn()
    try:
        cur.execute(
            f"INSERT INTO solicitudes_cancelacion (tipo,referencia_id,descripcion,motivo,operario_id,sucursal_id) "
            f"VALUES ({ph},{ph},{ph},{ph},{ph},{ph})",
            (tipo, referencia_id, descripcion, motivo, operario_id, sucursal_id or 1)
        )
        conn.commit()
        cur.execute("SELECT id FROM solicitudes_cancelacion ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        return True, int(row[0] if not hasattr(row,'keys') else row['id'])
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def get_solicitudes_pendientes(sucursal_id=None):
    conn, cur, ph = get_conn()
    q = """
        SELECT s.*, u.nombre as operario_nombre
        FROM solicitudes_cancelacion s
        LEFT JOIN usuarios u ON s.operario_id = u.id
        WHERE s.estatus='pendiente'
    """
    params = []
    if sucursal_id:
        q += f" AND s.sucursal_id={ph}"
        params.append(sucursal_id)
    q += " ORDER BY s.creado_en DESC"
    cur.execute(q, params)
    rows = [dict(r) if hasattr(r,'keys') else {
        'id':r[0],'tipo':r[1],'referencia_id':r[2],'descripcion':r[3],
        'motivo':r[4],'operario_id':r[5],'estatus':r[6],'supervisor_id':r[7],
        'creado_en':str(r[8]),'resuelto_en':r[9],'operario_nombre':r[10]
    } for r in cur.fetchall()]
    conn.close()
    return rows

def resolver_solicitud(solicitud_id, supervisor_id, aprobar):
    conn, cur, ph = get_conn()
    try:
        import datetime
        ahora = datetime.datetime.now().isoformat()
        estatus = 'aprobada' if aprobar else 'rechazada'
        cur.execute(
            f"UPDATE solicitudes_cancelacion SET estatus={ph},supervisor_id={ph},resuelto_en={ph} WHERE id={ph}",
            (estatus, supervisor_id, ahora, solicitud_id)
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()

def get_solicitud(solicitud_id):
    conn, cur, ph = get_conn()
    cur.execute(f"SELECT * FROM solicitudes_cancelacion WHERE id={ph}", (solicitud_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return dict(row) if hasattr(row,'keys') else {
        'id':row[0],'tipo':row[1],'referencia_id':row[2],'descripcion':row[3],
        'motivo':row[4],'operario_id':row[5],'estatus':row[6],'supervisor_id':row[7],
        'creado_en':str(row[8]),'resuelto_en':row[9]
    }

# ── PIN de supervisor ────────────────────────────────────────────────────────

def set_supervisor_pin(usuario_id, pin):
    import hashlib, datetime
    h = hashlib.sha256(str(pin).encode()).hexdigest()
    conn, cur, ph = get_conn()
    try:
        if _is_postgres():
            cur.execute(
                f"INSERT INTO supervisor_pins (usuario_id,pin_hash,actualizado_en) VALUES ({ph},{ph},{ph}) "
                f"ON CONFLICT (usuario_id) DO UPDATE SET pin_hash={ph},actualizado_en={ph}",
                (usuario_id, h, datetime.datetime.now().isoformat(), h, datetime.datetime.now().isoformat())
            )
        else:
            cur.execute(
                f"INSERT OR REPLACE INTO supervisor_pins (usuario_id,pin_hash,actualizado_en) VALUES ({ph},{ph},{ph})",
                (usuario_id, h, datetime.datetime.now().isoformat())
            )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()

def verificar_supervisor_pin(pin):
    """Verifica el PIN contra todos los supervisores/admins. Retorna el usuario si es válido."""
    import hashlib
    h = hashlib.sha256(str(pin).encode()).hexdigest()
    conn, cur, ph = get_conn()
    cur.execute(f"""
        SELECT u.id, u.nombre, u.rol FROM supervisor_pins sp
        JOIN usuarios u ON sp.usuario_id = u.id
        WHERE sp.pin_hash={ph} AND u.activo=1 AND u.rol IN ('admin','supervisor')
    """, (h,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {'id': row[0] if not hasattr(row,'keys') else row['id'],
            'nombre': row[1] if not hasattr(row,'keys') else row['nombre'],
            'rol': row[2] if not hasattr(row,'keys') else row['rol']}

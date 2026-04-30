"""
cp_lookup.py — Autocompletado de Códigos Postales
Usa DB local SQLite primero, luego APIs externas como fallback.
"""
from __future__ import annotations
import json
import urllib.request
import urllib.error
import threading
import sqlite3
import os
from functools import lru_cache

# Cache en memoria para no repetir llamadas
_cache: dict[str, dict] = {}
_lock  = threading.Lock()

# Ruta de la DB local de colonias
_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "colonias_mx.sqlite")


def _buscar_local(cp: str) -> dict | None:
    """Busca en la DB SQLite local. Devuelve colonias EXACTAS del CP."""
    try:
        if not os.path.exists(_DB_PATH):
            return None
        conn = sqlite3.connect(_DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Colonias del CP exacto — sin expandir al municipio completo
        cur.execute(
            "SELECT DISTINCT colonia, municipio, estado FROM colonias WHERE cp=? ORDER BY colonia",
            (cp,)
        )
        rows = cur.fetchall()
        conn.close()

        if not rows:
            return None  # CP no encontrado -> modo manual en el frontend

        municipio = rows[0]["municipio"]
        estado    = rows[0]["estado"]
        colonias  = [r["colonia"] for r in rows]
        return {"ciudad": municipio, "estado": estado, "colonias": colonias, "pais": "MX"}
    except Exception:
        return None

def _fetch(url: str, timeout: int = 6) -> dict | None:
    """GET JSON con timeout. Retorna None en error."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "PAQUETELLEGUE/2.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def buscar_cp(cp: str, pais: str = "MX") -> dict | None:
    """
    Busca un código postal y retorna:
        {"ciudad": ..., "estado": ..., "colonias": [...], "pais": ...}
    Primero consulta DB local, luego APIs externas como fallback.
    """
    cp = cp.strip()
    if not cp:
        return None

    cache_key = f"{pais}:{cp}"
    with _lock:
        if cache_key in _cache:
            return _cache[cache_key]

    result = None

    if pais == "MX":
        # 1. Envíos Internacionales — catálogo exacto igual al de Skydropx
        result = _buscar_envios_internacionales(cp)
        # 2. BD local como fallback (sin internet o fallo de API)
        if not result:
            result = _buscar_local(cp)
        # 3. Sepomex como último recurso
        if not result:
            result = _buscar_mx(cp)
    elif pais == "US":
        result = _buscar_us(cp)
    else:
        result = _buscar_us(cp)

    if result:
        with _lock:
            _cache[cache_key] = result

    return result


# Caché del token OAuth de Envíos Internacionales
_ei_token_cache = {"token": None, "expires": 0}

def _get_ei_token() -> str:
    """Obtiene (y cachea) el token OAuth de Envíos Internacionales."""
    import time, urllib.request, json
    now = time.time()
    if _ei_token_cache["token"] and _ei_token_cache["expires"] > now + 60:
        return _ei_token_cache["token"]
    token_url = "https://app.enviosinternacionales.com/api/v1/oauth/token"
    token_data = json.dumps({
        "grant_type": "client_credentials",
        "client_id": "gtXpeDxcoHGCsbSJXBpa_6ygxbw4usoesc868XEAZ2I",
        "client_secret": "MvcA6bSwXRPT03Jh4QO5u0rs_id-qtbfxJERWGnXB8E"
    }).encode("utf-8")
    req = urllib.request.Request(
        token_url, data=token_data,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=6) as r:
        resp = json.loads(r.read())
    token = resp.get("access_token", "")
    expires_in = int(resp.get("expires_in", 7200))
    _ei_token_cache["token"] = token
    _ei_token_cache["expires"] = now + expires_in
    return token


def _buscar_envios_internacionales(cp: str) -> dict | None:
    """
    Consulta el endpoint de Envíos Internacionales para obtener colonias
    exactamente como las tiene su catálogo (mismo catálogo que Skydropx).
    Usa token OAuth de Envíos Internacionales.
    """
    try:
        import urllib.request, urllib.parse, json, re

        # 1. Obtener token OAuth (cacheado)
        token = _get_ei_token()
        if not token:
            return None

        # 2. Consultar colonias por CP
        url = (f"https://app.enviosinternacionales.com/es-MX/quotations/addresses/search"
               f"?code={cp}&country_code=MX&allow_fallback_postal_code=false")
        addr_req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {token}",
            "Accept": "text/vnd.turbo-stream.html, text/html",
            "User-Agent": "Mozilla/5.0",
        })
        with urllib.request.urlopen(addr_req, timeout=6) as r:
            html = r.read().decode("utf-8", errors="replace")

        # 3. Parsear data-area-level3/2/1
        colonias = [m.group(1) for m in re.finditer(r"data-area-level3='([^']+)'", html)]
        ciudades  = [m.group(1) for m in re.finditer(r"data-area-level2='([^']+)'", html)]
        estados   = [m.group(1) for m in re.finditer(r"data-area-level1='([^']+)'", html)]
        colonias  = list(dict.fromkeys(colonias))  # deduplicar

        if colonias:
            return {
                "ciudad": ciudades[0] if ciudades else "",
                "estado": estados[0] if estados else "",
                "colonias": colonias,
                "pais": "MX",
                "fuente": "envios_internacionales"
            }
    except Exception:
        pass
    return None


# Alias para compatibilidad
_buscar_skydropx = _buscar_envios_internacionales


def _buscar_mx(cp: str) -> dict | None:
    """
    Busca CP mexicano usando múltiples APIs públicas.
    Prioriza obtener TODAS las colonias del CP.
    """
    # API 1: sepomex (mejor cobertura de colonias)
    url1 = f"https://sepomex.icalialabs.com/api/v1/zip_codes?zip_code={cp}"
    data = _fetch(url1)
    if data:
        try:
            zcs = data.get("zip_codes", [])
            if zcs:
                z = zcs[0]
                ciudad   = z.get("d_mnpio", z.get("d_ciudad", "")).title()
                estado   = z.get("d_estado", "").title()
                colonias = [zc.get("d_asenta", "") for zc in zcs[:30] if zc.get("d_asenta")]
                if ciudad and estado and colonias:
                    return {"ciudad": ciudad, "estado": estado,
                            "colonias": colonias, "pais": "MX"}
        except Exception:
            pass

    # API 2: copomex endpoint completo (no simplified)
    url2 = f"https://api.copomex.com/query/info_cp/{cp}"
    data = _fetch(url2)
    if data and not data.get("error"):
        try:
            items = data if isinstance(data, list) else [data]
            item = items[0]
            ciudad = (item.get("municipio") or item.get("ciudad") or
                      item.get("d_mnpio") or "")
            estado = (item.get("estado") or item.get("d_estado") or "")
            colonias = [d.get("asentamiento", d.get("d_asenta", ""))
                        for d in items if d.get("asentamiento") or d.get("d_asenta")]
            if ciudad and estado:
                return {"ciudad": ciudad.title(), "estado": estado.title(),
                        "colonias": colonias[:30], "pais": "MX"}
        except Exception:
            pass

    # API 4: zippopotam (sin colonias pero al menos ciudad/estado)
    url4 = f"https://api.zippopotam.us/mx/{cp}"
    data = _fetch(url4)
    if data and data.get("places"):
        try:
            p = data["places"][0]
            ciudad = p.get("place name", "").title()
            estado = p.get("state", "").title()
            if ciudad:
                return {"ciudad": ciudad, "estado": estado,
                        "colonias": [], "pais": "MX"}
        except Exception:
            pass

    return None


def _buscar_us(cp: str) -> dict | None:
    """Busca ZIP code de Estados Unidos."""
    # Solo ZIPs de 5 dígitos
    cp5 = cp[:5]
    if not cp5.isdigit():
        return None

    url = f"https://api.zippopotam.us/us/{cp5}"
    data = _fetch(url)
    if data and data.get("places"):
        try:
            p = data["places"][0]
            ciudad = p.get("place name", "").title()
            estado = p.get("state", "").title()
            estado_abr = p.get("state abbreviation", "").upper()
            if ciudad:
                return {"ciudad": ciudad,
                        "estado": estado,
                        "estado_abr": estado_abr,
                        "colonias": [],
                        "pais": "US"}
        except Exception:
            pass

    return None


def buscar_cp_async(cp: str, pais: str, callback):
    """
    Versión asíncrona. Llama a callback(resultado) desde un hilo.
    resultado es dict o None.
    """
    def _run():
        res = buscar_cp(cp, pais)
        try:
            callback(res)
        except Exception:
            pass
    threading.Thread(target=_run, daemon=True).start()

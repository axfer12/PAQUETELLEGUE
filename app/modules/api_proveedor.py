"""
api_proveedor.py — Integración con Skydropx PRO API
Base URL: https://pro.skydropx.com/api/v1
Auth:     OAuth2 client_credentials → Bearer token (expira 2h)
"""
from __future__ import annotations
import json, time, threading, os, sys

try:
    import requests as _requests
    _REQUESTS_OK = True
except ImportError:
    _REQUESTS_OK = False

try:
    import brotli as _brotli
    _BROTLI_OK = True
except ImportError:
    _BROTLI_OK = False

# cloudscraper para bypassear Cloudflare en peticiones a EI
try:
    import cloudscraper as _cloudscraper
    _CLOUDSCRAPER_OK = True
except ImportError:
    _CLOUDSCRAPER_OK = False

# ── Tipo de cambio MXN/USD (cacheado 1 hora) ─────────────────────
_TC_CACHE = {"value": 17.5, "ts": 0}
_TC_LOCK  = threading.Lock()

def _get_tc_mxn_usd() -> float:
    """Retorna el tipo de cambio USD→MXN. Cacheado 1 hora."""
    with _TC_LOCK:
        if time.time() - _TC_CACHE["ts"] < 3600:
            return _TC_CACHE["value"]
    try:
        import urllib.request as _ur
        r = _ur.urlopen("https://open.er-api.com/v6/latest/USD", timeout=3)
        d = json.loads(r.read())
        tc = float(d.get("rates", {}).get("MXN", 17.5))
        with _TC_LOCK:
            _TC_CACHE["value"] = tc
            _TC_CACHE["ts"]    = time.time()
        return tc
    except Exception:
        return _TC_CACHE["value"]  # fallback

# ── Config Skydropx (Envíos NACIONALES) ──────────────────────────
API_BASE   = "https://pro.skydropx.com/api/v1"
CLIENT_ID  = "BCFhzgf1_BwKuYfzMRaf2Kncm0pigheSo94CFdrmZcs"
CLIENT_SEC = "-Fq2tF48UNrhsGAN6oB9rkoywkw2x2cWXq9KuSu_lnY"

# ── Config Envíos Internacionales (Envíos INTERNACIONALES) ────────
EI_API_BASE   = "https://app.enviosinternacionales.com/api/v1"
EI_CLIENT_ID  = "gtXpeDxcoHGCsbSJXBpa_6ygxbw4usoesc868XEAZ2I"
EI_CLIENT_SEC = "MvcA6bSwXRPT03Jh4QO5u0rs_id-qtbfxJERWGnXB8E"
# Proxy HostGator — ya no se usa, variables mantenidas por compatibilidad con admin.py
EI_PROXY_URL  = os.environ.get("EI_PROXY_URL", "")
EI_PROXY_KEY  = os.environ.get("EI_PROXY_KEY", "")
_ei_token_cache: dict = {}
_ei_token_lock  = threading.Lock()

def _ei_http(method: str, endpoint: str, data=None,
              headers: dict | None = None, timeout: int = 45):
    """Realiza una petición HTTP directa a EI con hasta 3 reintentos."""
    url  = f"{EI_API_BASE}{endpoint}"
    sess = _get_session()
    last_exc = None
    for intento in range(3):
        try:
            if sess:
                fn = sess.post if method.upper() == "POST" else sess.get
                r  = fn(url, json=data, headers=headers, timeout=timeout)
                return r
            else:
                import urllib.request as _ur
                body_bytes = json.dumps(data).encode() if data else None
                req = _ur.Request(url, body_bytes, headers or {}, method=method)
                with _ur.urlopen(req, timeout=timeout) as r:
                    class _R:
                        status_code = r.status
                        ok = r.status < 400
                        def json(self_): return json.loads(r.read())
                        text = ""
                    return _R()
        except Exception as e:
            last_exc = e
            _log(f"EI HTTP intento {intento+1}/3 fallido: {e}")
            time.sleep(1.5 * (intento + 1))
    raise APIError(f"EI HTTP sin respuesta tras 3 intentos: {last_exc}")

# HS Codes del catálogo (HS_Codes-v2.xlsx destino US)
# HS Codes por categoría y país destino (fuente: Skydropx HS_Codes-v2.xlsx)
# Códigos validados directamente del catálogo HS_Codes-v2.xlsx de Skydropx/EI
HS_CODES_BY_COUNTRY: dict[str, dict[str, str]] = {
    "documentos":   {"CA":"4906.000000","CN":"4906.000010999","CO":"4906.000000","ES":"4906.000000","FR":"4906.000000","GB":"4906.000000","US":"4906.000000"},
    "ropa":         {"CA":"6109.100019","CN":"6109.100000302","CO":"6109.100000","ES":"6109.100090","FR":"6109.100090","GB":"6109.100090","US":"6109.100011"},
    "zapatos":      {"CA":"6404.209000","CN":"6404.209000101","CO":"6404.200000","ES":"6404.209000","FR":"6404.209000","GB":"6404.209000","US":"6404.204090"},
    "celular":      {"CA":"8517.610000","CN":"8517.611020999","CO":"8517.710000","ES":"8517.610000","FR":"8517.610000","GB":"8517.610000","US":"8517.110000"},
    "electronica":  {"CA":"8471.600040","CN":"8471.606000999","CO":"8471.602000","ES":"8471.606000","FR":"8471.606000","GB":"8471.606000","US":"8471.809000"},
    "cosmeticos":   {"CA":"3304.200000","CN":"3304.200013104","CO":"3304.200000","ES":"3304.200000","FR":"3304.200000","GB":"3304.200000","US":"3304.991000"},
    "joyeria":      {"CA":"7113.201010","CN":"7113.111000999","CO":"7113.200000","ES":"7113.200000","FR":"7113.200000","GB":"7113.200000","US":"7113.202900"},
    "juguetes":     {"CA":"9503.009040","CN":"9503.002100102","CO":"9503.002200","ES":"9503.002110","FR":"9503.002110","GB":"9503.002110","US":"9503.000013"},
    "herramientas": {"CA":"8201.401000","CN":"8201.400010102","CO":"8201.401000","ES":"8201.400000","FR":"8201.400000","GB":"8201.400000","US":"8201.100000"},
    "libros":       {"CA":"4901.100000","CN":"4901.100000999","CO":"4901.101000","ES":"4901.100000","FR":"4901.100000","GB":"4901.100000","US":"4901.100020"},
    "alimentos":    {"CA":"1806.101000","CN":"1806.100000102","CO":"1806.100000","ES":"1806.102000","FR":"1806.102000","GB":"1806.102000","US":"1806.209800"},
    "medicamentos": {"CA":"3002.120021","CN":"3002.510010102","CO":"3002.121300","ES":"3002.120000","FR":"3002.120000","GB":"3002.120000","US":"3002.120010"},
}

# Aliases de categorías (normalizado sin acentos)
HS_ALIASES: dict[str, str] = {
    "documentos personales":"documentos","papeles":"documentos","sobre":"documentos","documentos":"documentos",
    "ropa usada":"ropa","playera":"ropa","camisa":"ropa","pantalon":"ropa","vestido":"ropa",
    "calzado":"zapatos","tenis":"zapatos",
    "telefono":"celular","smartphone":"celular","movil":"celular",
    "electronica":"electronica","computadora":"electronica","laptop":"electronica","tablet":"electronica",
    "cosmeticos":"cosmeticos","perfume":"cosmeticos","belleza":"cosmeticos","maquillaje":"cosmeticos",
    "joyeria":"joyeria","accesorios":"joyeria","bisuteria":"joyeria",
    "juguete":"juguetes",
    "herramienta":"herramientas","refacciones":"herramientas","autopartes":"herramientas",
    "libro":"libros","revista":"libros","libros":"libros",
    "comida":"alimentos","alimento":"alimentos",
    "medicina":"medicamentos","farmacia":"medicamentos","medicamento":"medicamentos",
}

# Fallback por país — usar libros/impresos como genérico (4901 existe en todos los países)
HS_DEFAULT_BY_COUNTRY: dict[str, str] = {
    "CA":"4901.100000","CN":"4901.100000999","CO":"4901.101000",
    "ES":"4901.100000","FR":"4901.100000","GB":"4901.100000","US":"4901.100020",
}
HS_DEFAULT = "4901.100020"

# ── HS Codes EXCLUSIVOS para Skydropx (dfcd8021-HS_Codes-v2_1.xlsx) ──────────
# Separados de HS_CODES_BY_COUNTRY (que usa EI) para no generar conflictos.
# Skydropx no acepta 9999.x — fallback siempre a 4901 (libros/impresos).
HS_CODES_SKY: dict[str, dict[str, str]] = {
    "documentos":   {"US":"4906.000000","CA":"4906.000000","GB":"4906.000000","FR":"4906.000000","ES":"4906.000000","CO":"4906.000000","CN":"4906.000010999","DE":"4906.00","AU":"4906.00","JP":"4906.00","IT":"4906.00","BR":"4906.00","AR":"4906.00","CL":"4906.00","PE":"4906.00","AE":"4906.00","CH":"4906.00","GLOBAL":"4906.00"},
    "ropa":         {"US":"6109.100004","CA":"6109.100011","GB":"6109.100010","FR":"6109.100010","ES":"6109.100010","CO":"6109.100000","CN":"6109.100000301","DE":"6109.10","AU":"6109.10","JP":"6109.10","IT":"6109.10","BR":"6109.10","AR":"6109.10","CL":"6109.10","PE":"6109.10","AE":"6109.10","CH":"6109.10","GLOBAL":"6109.10"},
    "zapatos":      {"US":"6404.112030","CA":"6404.111100","GB":"6404.110000","FR":"6404.110000","ES":"6404.110000","CO":"6404.111000","CN":"6404.110000999","DE":"6404.11","AU":"6404.11","JP":"6404.11","IT":"6404.11","BR":"6404.11","AR":"6404.11","CL":"6404.11","PE":"6404.11","AE":"6404.11","CH":"6404.11","GLOBAL":"6404.01"},
    "celular":      {"US":"8517.110000","CA":"8517.110010","GB":"8517.110000","FR":"8517.110000","ES":"8517.110000","CO":"8517.110000","CN":"8517.110010999","DE":"8517.11","AU":"8517.11","JP":"8517.11","IT":"8517.11","BR":"8517.11","AR":"8517.11","CL":"8517.11","PE":"8517.11","AE":"8517.11","CH":"8517.11","GLOBAL":"8517.11"},
    "electronica":  {"US":"8471.300100","CA":"8471.300000","GB":"8471.300000","FR":"8471.300000","ES":"8471.300000","CO":"8471.300000","CN":"8471.900000","DE":"8471.30","AU":"8471.30","JP":"8471.30","IT":"8471.30","BR":"8471.30","AR":"8471.30","CL":"8471.30","PE":"8471.30","AE":"8471.30","CH":"8471.30","GLOBAL":"8471.04"},
    "cosmeticos":   {"US":"3304.100000","CA":"3304.100000","GB":"3304.100000","FR":"3304.100000","ES":"3304.100000","CO":"3304.100000","CN":"3304.100011101","DE":"3304.10","AU":"3304.10","JP":"3304.10","IT":"3304.10","BR":"3304.10","AR":"3304.10","CL":"3304.10","PE":"3304.10","AE":"3304.10","CH":"3304.10","GLOBAL":"3304.09"},
    "joyeria":      {"US":"7113.111000","CA":"7113.111010","GB":"7113.110000","FR":"7113.110000","ES":"7113.110000","CO":"7113.110000","CN":"7113.111000999","DE":"7113.11","AU":"7113.11","JP":"7113.11","IT":"7113.11","BR":"7113.11","AR":"7113.11","CL":"7113.11","PE":"7113.11","AE":"7113.11","CH":"7113.11","GLOBAL":"7113.01"},
    "juguetes":     {"US":"9503.000011","CA":"9503.001010","GB":"9503.001000","FR":"9503.001000","ES":"9503.001000","CO":"9503.001000","CN":"9503.001000101","DE":"9503.00","AU":"9503.00","JP":"9503.00","IT":"9503.00","BR":"9503.00","AR":"9503.00","CL":"9503.00","PE":"9503.00","AE":"9503.00","CH":"9503.00","GLOBAL":"9503.00"},
    "herramientas": {"US":"8201.100000","CA":"8201.101000","GB":"8201.100000","FR":"8201.100000","ES":"8201.100000","CO":"8201.100000","CN":"8201.100010101","DE":"8201.10","AU":"8201.10","JP":"8201.10","IT":"8201.10","BR":"8201.10","AR":"8201.10","CL":"8201.10","PE":"8201.10","AE":"8201.10","CH":"8201.10","GLOBAL":"8201.10"},
    "libros":       {"US":"4901.100020","CA":"4901.100000","GB":"4901.100000","FR":"4901.100000","ES":"4901.100000","CO":"4901.101000","CN":"4901.100000999","DE":"4901.10","AU":"4901.10","JP":"4901.10","IT":"4901.10","BR":"4901.10","AR":"4901.10","CL":"4901.10","PE":"4901.10","AE":"4901.10","CH":"4901.10","GLOBAL":"4901.09"},
    "alimentos":    {"US":"2106.100000","CA":"2106.100000","GB":"2106.102020","FR":"2106.102020","ES":"2106.102020","CO":"2106.101100","CN":"2106.100000101","GLOBAL":"2106.10"},
    "medicamentos": {"US":"3004.101010","CA":"3004.100010","GB":"3004.100000","FR":"3004.100000","ES":"3004.100000","CO":"3004.101000","CN":"3004.905590","DE":"3004.10","AU":"3004.10","JP":"3004.10","IT":"3004.10","BR":"3004.10","AR":"3004.10","CL":"3004.10","PE":"3004.10","AE":"3004.10","CH":"3004.10","GLOBAL":"3004.03"},
}
# Fallback por país para Skydropx — 4901 existe en todos (9999.x no está en su catálogo)
HS_DEFAULT_BY_COUNTRY_SKY: dict[str, str] = {
    "US":"4901.100020","CA":"4901.100000","GB":"4901.100000","FR":"4901.100000",
    "ES":"4901.100000","CO":"4901.101000","CN":"4901.100000999","DE":"4901.10",
    "AU":"4901.10","JP":"4901.10","IT":"4901.10","BR":"4901.10","AR":"4901.10",
    "CL":"4901.10","PE":"4901.10","AE":"4901.10","CH":"4901.10","GLOBAL":"4901.09",
}
HS_DEFAULT_SKY = "4901.100020"

# Mantener compat con código existente
HS_CODES: dict[str, str] = {k: v.get("US", HS_DEFAULT) for k, v in HS_CODES_BY_COUNTRY.items()}
HS_CODES.update({"mercancia":"9999.000000","general":"9999.000000"})

DESC_EN: dict[str, str] = {
    "documentos":   "Personal documents and letters",
    "papeles":      "Documents and papers for personal use",
    "libros":       "Books and printed materials",
    "ropa":         "Clothing and textile garments new",
    "zapatos":      "Footwear and shoes new pair",
    "electronica":  "Electronic devices and accessories",
    "celular":      "Mobile phone and accessories new",
    "juguetes":     "Toys and games for children",
    "cosmeticos":   "Cosmetics and beauty products",
    "joyeria":      "Jewelry and fashion accessories",
    "medicamentos": "Medicine and pharmaceutical products",
    "herramientas": "Tools and hardware equipment",
    "alimentos":    "Food products and groceries",
    "mercancia":    "General merchandise and goods",
}

_DEBUG = True  # siempre log a archivo

def _log(m):
    import sys, datetime
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}][API] {m}", flush=True, file=sys.stderr)
    try:
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "data", "api_debug.log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as lf:
            lf.write(f"[{ts}][API] {m}\n")
    except Exception:
        pass

_session = None
def _get_session():
    global _session
    if not _REQUESTS_OK: return None
    if _session is None:
        _session = _requests.Session()
        _session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept":          "application/json, text/plain, */*",
            "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection":      "keep-alive",
        })
    return _session

_token_cache: dict = {}
_token_lock = threading.Lock()

class APIError(Exception):
    def __init__(self, message, status_code=0, response=""):
        super().__init__(message)
        self.status_code = status_code
        self.response    = response

def get_token() -> str:
    with _token_lock:
        now = time.time()
        if _token_cache.get("token") and now < _token_cache.get("exp", 0) - 60:
            return _token_cache["token"]
        url  = f"{API_BASE}/oauth/token"
        body = {"grant_type":"client_credentials","client_id":CLIENT_ID,"client_secret":CLIENT_SEC}
        sess = _get_session()
        try:
            if sess:
                r = sess.post(url, json=body, timeout=20)
                text = r.content.decode("utf-8", errors="replace")
                if not r.ok:
                    raise APIError(f"Auth {r.status_code}: {text[:200]}")
                data = json.loads(text)
            else:
                import urllib.request
                req = urllib.request.Request(url, json.dumps(body).encode(),
                      {"Content-Type":"application/json"}, method="POST")
                with urllib.request.urlopen(req, timeout=20) as rr:
                    data = json.loads(rr.read())
            tok = data.get("access_token") or data.get("token")
            if not tok: raise APIError(f"Token vacío: {data}")
            _token_cache["token"] = tok
            _token_cache["exp"]   = now + int(data.get("expires_in", 7200))
            _log(f"Token OK")
            return tok
        except APIError: raise
        except Exception as e: raise APIError(f"Error auth: {e}")

def get_ei_token() -> str:
    """Obtiene token OAuth de Envíos Internacionales.
    Si EI_PROXY_URL está configurado, usa el proxy HostGator (bypass Cloudflare).
    """
    with _ei_token_lock:
        now = time.time()
        if _ei_token_cache.get("token") and now < _ei_token_cache.get("exp", 0) - 60:
            return _ei_token_cache["token"]
        body = {"grant_type":"client_credentials","client_id":EI_CLIENT_ID,"client_secret":EI_CLIENT_SEC}
        via = "directo"
        _log(f"EI: solicitando token via {via} (client_id={EI_CLIENT_ID[:8]}...)")
        try:
            r = _ei_http("POST", "/oauth/token", data=body,
                         headers={"Content-Type":"application/json","Accept":"application/json"},
                         timeout=30)
            _log(f"EI Auth response: {r.status_code}")
            if not r.ok:
                _log(f"EI Auth FAIL {r.status_code}: {r.text[:300]}")
                raise APIError(f"EI Auth {r.status_code}: {r.text[:300]}")
            data = r.json()
            tok = data.get("access_token","")
            if not tok: raise APIError(f"EI token vacío: {data}")
            _ei_token_cache["token"] = tok
            _ei_token_cache["exp"]   = now + int(data.get("expires_in", 7200))
            _log(f"EI Token OK (expira en {data.get('expires_in',7200)}s)")
            return tok
        except APIError: raise
        except Exception as e: raise APIError(f"EI Auth error: {e}")


def _ei_request(method, endpoint, data=None, timeout=45, _retry_auth=True):
    """Request a la API de EI.
    Si EI_PROXY_URL está configurado, usa el proxy HostGator (bypass Cloudflare).
    Si recibe 401/403 limpia caché de token y reintenta una vez automáticamente.
    """
    token = get_ei_token()
    hdrs  = {"Content-Type":"application/json","Accept":"application/json",
             "Authorization":f"Bearer {token}"}
    try:
        r = _ei_http(method, endpoint, data=data, headers=hdrs, timeout=timeout)
        if not r.ok:
            _log(f"EI ERROR {r.status_code}: {r.text[:1000]}")
            if r.status_code in (401, 403) and _retry_auth:
                _log("EI Auth expirado — limpiando caché y renovando token...")
                with _ei_token_lock:
                    _ei_token_cache.clear()
                return _ei_request(method, endpoint, data=data,
                                   timeout=timeout, _retry_auth=False)
            raise APIError(f"EI HTTP {r.status_code}: {r.text[:500]}")
        return r.json()
    except APIError: raise
    except Exception as ex:
        raise APIError(f"EI Error: {ex}")


def _es_internacional(pais_origen: str, pais_destino: str) -> bool:
    """Determina si el envío es internacional."""
    return (pais_origen or "MX").upper() != (pais_destino or "MX").upper()


def _request(method, endpoint, data=None, raw=False, timeout=45):
    url     = f"{API_BASE}{endpoint}"
    headers = {"Content-Type":"application/json","Authorization":f"Bearer {get_token()}"}
    sess    = _get_session()
    try:
        if sess:
            r = sess.request(method, url, json=data, headers=headers, timeout=timeout)
            if raw: r.raise_for_status(); return r.content
            content = r.content
            if "br" in r.headers.get("Content-Encoding","") and _BROTLI_OK:
                try: content = _brotli.decompress(content)
                except: pass
            try: text = content.decode("utf-8")
            except: text = content.decode("latin-1", errors="replace")
            text = text.strip()
            if not r.ok:
                try:
                    e = json.loads(text)
                    msg = e.get("error_description") or e.get("errors") or e.get("message") or text[:400]
                    if isinstance(msg, (list, dict)):
                        msg = str(msg)
                except:
                    msg = text[:400]
                # Detectar crash HTML (500 sin JSON)
                if r.status_code == 500 and text.strip().startswith('<'):
                    raise APIError(
                        "Error interno en Skydropx (500).\n\n"
                        "Este es un problema del lado de Skydropx, no de tu información.\n"
                        "Intenta de nuevo en unos minutos o contacta a soporte@skydropx.com.",
                        status_code=500, response=text[:200])
                # Detectar saldo insuficiente
                msg_lower = str(msg).lower()
                if any(k in msg_lower for k in ("balance","credito","credit","saldo",
                                                 "insufficient","funds","payment required",
                                                 "pago","wallet","cuenta")):
                    raise APIError(
                        "SALDO INSUFICIENTE\n\n"
                        "No tienes saldo suficiente en Skydropx "
                        "para generar esta guia.\n\n"
                        "Recarga en: pro.skydropx.com\n"
                        f"Detalle: {str(msg)[:120]}",
                        status_code=r.status_code, response=text)
                if r.status_code == 402:
                    raise APIError(
                        "SALDO INSUFICIENTE (Codigo 402)\n\n"
                        "Recarga saldo en pro.skydropx.com para continuar.",
                        status_code=402, response=text)
                raise APIError(f"HTTP {r.status_code}: {msg}", r.status_code, text)
            return json.loads(text) if text else {}
        else:
            import urllib.request
            b = json.dumps(data).encode() if data else None
            req = urllib.request.Request(url, b, headers, method=method)
            with urllib.request.urlopen(req, timeout=35) as rr:
                c = rr.read(); return c if raw else json.loads(c)
    except APIError: raise
    except Exception as e: raise APIError(f"Conexión: {e}")

def verificar_credenciales():
    try:
        t = get_token()
        return True, f"✓ Skydropx conectado (token: {t[:16]}...)"
    except APIError as e: return False, str(e)
    except Exception as e: return False, f"Error: {e}"


def _cotizar_ei(
    cp_origen, cp_destino, peso, alto, ancho, largo,
    pais_origen="MX", pais_destino="US",
    estado_origen="", ciudad_origen="", colonia_origen="",
    estado_destino="", ciudad_destino="", colonia_destino="",
    contenido="Mercancía", valor_declarado=1.0, valor_declarado_usd=0.0,
    desc_en="", hs_code="",
) -> list[dict]:
    """Cotiza envío INTERNACIONAL usando Envíos Internacionales."""
    pais_origen  = (pais_origen  or "MX").upper().strip()
    pais_destino = (pais_destino or "US").upper().strip()
    _PAIS_MAP = {"USA":"US","ESTADOS UNIDOS":"US","UNITED STATES":"US",
                 "MEXICO":"MX","MÉXICO":"MX","SPAIN":"ES","ESPAÑA":"ES",
                 "CANADA":"CA","FRANCE":"FR","FRANCIA":"FR",
                 "CHINA":"CN","COLOMBIA":"CO","UK":"GB","REINO UNIDO":"GB"}
    pais_origen  = _PAIS_MAP.get(pais_origen,  pais_origen)
    pais_destino = _PAIS_MAP.get(pais_destino, pais_destino)
    _log(f"COTIZAR EI internacional {pais_origen}→{pais_destino}")
    _cat_lower = (contenido or "").lower().strip()
    _cat_key   = HS_ALIASES.get(_cat_lower, _cat_lower)
    _pais_d    = (pais_destino or "US").upper()
    if _cat_key in HS_CODES_BY_COUNTRY:
        hs = (hs_code or "").strip() or HS_CODES_BY_COUNTRY[_cat_key].get(_pais_d, HS_DEFAULT)
    else:
        hs = (hs_code or "").strip() or HS_DEFAULT
    desc_ingles = desc_en or contenido or "General merchandise"
    # EI usa price directamente en USD — garantizar mínimo 1.0
    _tc_ei = _get_tc_mxn_usd()
    try:
        _vdu = float(valor_declarado_usd) if valor_declarado_usd else 0.0
        _vdm = float(valor_declarado) if valor_declarado else 0.0
        valor_usd = _vdu if _vdu > 0 else (_vdm / _tc_ei if _vdm > 0 else 1.0)
    except (TypeError, ValueError):
        valor_usd = 1.0
    precio_para_ei = round(max(valor_usd, 1.0), 2)
    _log(f"EI cotizar: price_USD={precio_para_ei}")
    payload = {"quotation": {
        "address_from": {
            "country_code": pais_origen, "postal_code": cp_origen,
            "area_level1": estado_origen or "NA",
            "area_level2": ciudad_origen or "NA",
            "area_level3": colonia_origen or "NA",
        },
        "address_to": {
            "country_code": pais_destino, "postal_code": cp_destino,
            "area_level1": estado_destino or "NA",
            "area_level2": ciudad_destino or "NA",
            "area_level3": colonia_destino or "NA",
        },
        "parcels": [{"length":int(largo),"width":int(ancho),"height":int(alto),"weight":float(peso),
            "products": [{
                "description_en": (desc_ingles)[:50],
                "quantity": 1,
                "price": precio_para_ei,
                "hs_code": hs,
                "country_code": pais_origen,
            }]
        }],
    }}
    _log(f"EI PAYLOAD: {json.dumps(payload)[:500]}")
    resp = _ei_request("POST", "/quotations", data=payload)
    _log(f"EI COTIZ RESP: {json.dumps(resp)[:500]}")
    qid  = resp.get("id") or (resp.get("data") or {}).get("id","")
    if not qid:
        raise APIError(f"EI sin ID cotización: {str(resp)[:300]}")
    import time as _t
    for i in range(18):
        _t.sleep(3)
        r2     = _ei_request("GET", f"/quotations/{qid}")
        done   = r2.get("is_completed", False)
        rates  = r2.get("rates", [])
        listos = [r for r in rates if r.get("total") and r.get("status") not in ("pending","error","no_coverage","failed")]
        _log(f"EI Poll {i+1} done={done} listos={len(listos)}")
        if done or listos:
            _rates_log = listos or rates
            _log(f"EI rates COMPLETO: {json.dumps(_rates_log[:2])[:1000]}")
            return _parsear_rates_ei(_rates_log, qid)
    raise APIError("EI cotización tardó demasiado. Intenta de nuevo.")


def _parsear_rates_ei(rates_raw, qid) -> list[dict]:
    """Parsea rates de Envíos Internacionales al formato estándar."""
    INVALIDOS = {"error","no_coverage","failed","pending"}
    _log(f"EI rates brutos: {len(rates_raw)} | providers: {[r.get('provider_name','?') for r in rates_raw]}")
    rates_letter = []
    rates_thermal = []
    for r in rates_raw:
        status = (r.get("status") or "").lower()
        if status in INVALIDOS:
            _log(f"EI rate EXCLUIDO (status={status}): {r.get('provider_name','?')}")
            continue
        # Solo excluir success=False si tampoco tienen precio
        try: precio = float(str(r.get("total") or r.get("amount") or "0").replace(",",""))
        except: precio = 0.0
        if r.get("success") is False and precio <= 0:
            _log(f"EI rate EXCLUIDO (success=false sin precio): {r.get('provider_name','?')}")
            continue
        if precio <= 0:
            _log(f"EI rate EXCLUIDO (sin precio): {r.get('provider_name','?')}")
            continue
        # Excluir FedEx — requiere acuerdo comercial en EI
        if (r.get("provider_name") or "").lower() == "fedex":
            _log(f"EI rate EXCLUIDO (fedex sin acuerdo): {r.get('provider_name','?')}")
            continue
        carrier  = (r.get("provider_display_name") or r.get("provider_name") or "Carrier").upper()
        servicio = r.get("provider_service_name") or r.get("name") or "Servicio"
        try: dias = int(r.get("days") or 0)
        except: dias = 0
        try: arancel = float(str(r.get("import_duty_amount") or "0").replace(",",""))
        except: arancel = 0.0
        pf = (r.get("printing_format") or "letter").lower()
        _log(f"EI rate OK: {carrier}/{servicio} ${precio} pf={pf} success={r.get('success')}")
        # Capturar qué pagadores permite esta tarifa (para respetar restricción al crear guía)
        _cpp_raw = r.get("customs_payment_payer")
        _cpp_entry = _cpp_raw if isinstance(_cpp_raw, list) and _cpp_raw else None
        entry = {
            "carrier": carrier, "servicio": servicio, "precio": precio,
            "dias": dias, "arancel": arancel,
            "moneda": r.get("currency_code") or "MXN",
            "rate_id": r.get("id") or "",
            "quotation_id": qid, "status": status,
            "printing_format": pf,
            "proveedor": "ei",
            "customs_payment_payer": _cpp_entry,  # ej: ["sender"] o ["sender","recipient"]
        }
        if pf == "thermal":
            rates_thermal.append(entry)
        else:
            rates_letter.append(entry)
    resultado = rates_letter if rates_letter else rates_thermal
    if not resultado:
        raise APIError("EI: Sin tarifas disponibles para este destino.")
    resultado.sort(key=lambda x: x["precio"])
    _log(f"EI rates finales: {len(resultado)}")
    return resultado


def cotizar_envio(
    cp_origen, cp_destino, peso, alto, ancho, largo,
    pais_origen="MX", pais_destino="MX",
    estado_origen="", ciudad_origen="", colonia_origen="", nombre_origen="Remitente",
    estado_destino="", ciudad_destino="", colonia_destino="", nombre_destino="Destinatario",
    contenido="Mercancía", valor_declarado=1.0, valor_declarado_usd=0.0,
    desc_en="", hs_code="",
) -> list[dict]:

    es_int = _es_internacional(pais_origen, pais_destino)

    payload = {"quotation": {
        "address_from": {
            "country_code": pais_origen,  "postal_code": cp_origen,
            "area_level1":  estado_origen  or "",
            "area_level2":  ciudad_origen  or "",
            "area_level3":  colonia_origen or "",
        },
        "address_to": {
            "country_code": pais_destino, "postal_code": cp_destino,
            "area_level1":  estado_destino  or "",
            "area_level2":  ciudad_destino  or "",
            "area_level3":  colonia_destino or "",
        },
        "parcels": [{"length":int(largo),"width":int(ancho),"height":int(alto),"weight":float(peso)}],
    }}

    if es_int:
        # ── Cotización internacional: EI + Skydropx en paralelo ──────────────
        _tc2 = _get_tc_mxn_usd()
        _usd2 = float(valor_declarado_usd) if valor_declarado_usd and float(valor_declarado_usd) > 0 else max(float(valor_declarado or 1), 1.0) / _tc2
        precio_ei_cotiz = round(_usd2, 2)
        _log(f"EI cotizar_envio: price_USD={precio_ei_cotiz}")
        cat   = (contenido or "").lower().strip()
        _cat_key2 = HS_ALIASES.get(cat, cat)
        _pais_d2 = (pais_destino or "US").upper()
        if _cat_key2 in HS_CODES_BY_COUNTRY:
            hs = (hs_code or "").strip() or HS_CODES_BY_COUNTRY[_cat_key2].get(_pais_d2, HS_CODES_BY_COUNTRY[_cat_key2].get("US", HS_DEFAULT))
        else:
            hs = (hs_code or "").strip() or HS_DEFAULT_BY_COUNTRY.get(_pais_d2, HS_DEFAULT)
        en = (desc_en or "").strip() or DESC_EN.get(_cat_key2, f"General merchandise: {contenido}")
        payload["quotation"]["parcels"][0]["products"] = [{
            "hs_code": hs, "description_en": en,
            "country_code": pais_origen, "quantity": 1, "price": round(precio_ei_cotiz, 2),
        }]
        _log(f"EI INT {pais_origen}→{pais_destino} hs={hs} price_MXN={precio_ei_cotiz}")

        # Payload Skydropx internacional
        # Skydropx PRO requiere products a nivel de quotation (no solo dentro del parcel)
        # HS code para Skydropx — diccionario SEPARADO de EI (HS_CODES_SKY vs HS_CODES_BY_COUNTRY)
        # Skydropx no acepta 9999.x — fallback siempre a 4901 (HS_DEFAULT_SKY)
        if _cat_key2 in HS_CODES_SKY:
            hs_sky = (hs_code or "").strip() or HS_CODES_SKY[_cat_key2].get(_pais_d2, HS_CODES_SKY[_cat_key2].get("GLOBAL", HS_DEFAULT_SKY))
        else:
            hs_sky = (hs_code or "").strip() or HS_DEFAULT_BY_COUNTRY_SKY.get(_pais_d2, HS_DEFAULT_SKY)
        _log(f"SKY INT hs_sky={hs_sky} (EI hs={hs})")
        _sky_price = round(max(precio_ei_cotiz, 1.0), 2)  # mínimo 1 USD para evitar 422
        _sky_product = {"hs_code": hs_sky or HS_DEFAULT_SKY, "description_en": en or f"General merchandise: {contenido}",
                        "country_code": pais_origen, "quantity": 1,
                        "price": _sky_price}
        payload_sky = {"quotation": {
            "address_from": payload["quotation"]["address_from"],
            "address_to":   payload["quotation"]["address_to"],
            "parcels": [{"length": int(largo), "width": int(ancho),
                         "height": int(alto), "weight": float(peso),
                         "products": [_sky_product]}],
            "products": [_sky_product],
        }}

        rates_ei  = []
        rates_sky = []
        err_ei    = None
        err_sky   = None

        def _cotizar_ei():
            nonlocal rates_ei, err_ei
            try:
                _log(f"POST /quotations (EI)")
                resp_ei = _ei_request("POST", "/quotations", data=payload)
                data_ei = resp_ei.get("data", {})
                qid_ei  = (resp_ei.get("id") or data_ei.get("id")
                           or (data_ei.get("attributes") or {}).get("id"))
                if not qid_ei:
                    raise APIError(f"EI sin ID: {json.dumps(resp_ei)[:200]}")
                done_ei = resp_ei.get("is_completed") or (data_ei.get("attributes") or {}).get("is_completed")
                if done_ei:
                    rr = resp_ei.get("rates") or data_ei.get("rates") or []
                    if rr:
                        rates_ei = _parsear_rates(rr, qid_ei, es_internacional=True)
                        return
                rates_ei = _esperar_rates(qid_ei, use_ei=True)
            except Exception as e:
                err_ei = e
                _log(f"EI cotización falló: {e}")

        def _cotizar_sky():
            nonlocal rates_sky, err_sky
            try:
                _log(f"POST /quotations (SKY int)")
                resp_sky = _request("POST", "/quotations", data=payload_sky)
                data_sky = resp_sky.get("data", {})
                qid_sky  = (resp_sky.get("id") or data_sky.get("id")
                            or (data_sky.get("attributes") or {}).get("id"))
                if not qid_sky:
                    raise APIError(f"SKY sin ID: {json.dumps(resp_sky)[:200]}")
                done_sky = resp_sky.get("is_completed") or (data_sky.get("attributes") or {}).get("is_completed")
                if done_sky:
                    rr = resp_sky.get("rates") or data_sky.get("rates") or []
                    if rr:
                        rates_sky = _parsear_rates(rr, qid_sky, es_internacional=True)
                        return
                rates_sky = _esperar_rates(qid_sky, use_ei=False)
            except Exception as e:
                err_sky = e
                _log(f"SKY int cotización falló: {e}")

        t_ei  = threading.Thread(target=_cotizar_ei,  daemon=True)
        t_sky = threading.Thread(target=_cotizar_sky, daemon=True)
        t_ei.start(); t_sky.start()
        t_ei.join(); t_sky.join()

        # Marcar proveedor en rates de Skydropx (EI ya viene con "ei")
        for r in rates_sky:
            r.setdefault("proveedor", "skydropx")

        combinados = rates_ei + rates_sky
        if not combinados:
            raise APIError(
                f"Sin tarifas internacionales disponibles.\n"
                f"EI: {err_ei or 'sin rates'} | SKY: {err_sky or 'sin rates'}"
            )
        combinados.sort(key=lambda x: x["precio"])
        _log(f"INT combinados: {len(rates_ei)} EI + {len(rates_sky)} SKY = {len(combinados)} total")
        return combinados

    else:
        # ── Cotización nacional: Skydropx + EI en paralelo ───────────────────
        rates_nac_sky = []
        rates_nac_ei  = []
        err_nac_sky   = None
        err_nac_ei    = None

        def _cotizar_nac_sky():
            nonlocal rates_nac_sky, err_nac_sky
            try:
                _log(f"POST /quotations (SKY nac)")
                r = _request("POST", "/quotations", data=payload)
                data_s = r.get("data", {})
                qid_s  = (r.get("id") or data_s.get("id")
                          or (data_s.get("attributes") or {}).get("id"))
                if not qid_s:
                    raise APIError(f"SKY nac sin ID: {json.dumps(r)[:200]}")
                done_s = r.get("is_completed") or (data_s.get("attributes") or {}).get("is_completed")
                if done_s:
                    rr = r.get("rates") or data_s.get("rates") or []
                    if rr:
                        rates_nac_sky = _parsear_rates(rr, qid_s, es_internacional=False)
                        return
                rates_nac_sky = _esperar_rates(qid_s, use_ei=False)
            except Exception as e:
                err_nac_sky = e
                _log(f"SKY nac cotización falló: {e}")

        def _cotizar_nac_ei():
            nonlocal rates_nac_ei, err_nac_ei
            try:
                _log(f"POST /quotations (EI nac)")
                r = _ei_request("POST", "/quotations", data=payload)
                qid_e = r.get("id") or (r.get("data") or {}).get("id", "")
                if not qid_e:
                    raise APIError(f"EI nac sin ID: {json.dumps(r)[:200]}")
                done_e = r.get("is_completed", False)
                if done_e:
                    rr = r.get("rates", [])
                    if rr:
                        rates_nac_ei = _parsear_rates_ei(rr, qid_e)
                        return
                rates_nac_ei = _esperar_rates(qid_e, use_ei=True)
            except Exception as e:
                err_nac_ei = e
                _log(f"EI nac cotización falló: {e}")

        t_nac_sky = threading.Thread(target=_cotizar_nac_sky, daemon=True)
        t_nac_ei  = threading.Thread(target=_cotizar_nac_ei,  daemon=True)
        t_nac_sky.start(); t_nac_ei.start()
        t_nac_sky.join(); t_nac_ei.join()

        for r in rates_nac_sky:
            r.setdefault("proveedor", "skydropx")

        combinados_nac = rates_nac_sky + rates_nac_ei
        if not combinados_nac:
            raise APIError(
                f"Sin tarifas disponibles.\n"
                f"SKY: {err_nac_sky or 'sin rates'} | EI: {err_nac_ei or 'sin rates'}"
            )
        combinados_nac.sort(key=lambda x: x["precio"])
        _log(f"NAC combinados: {len(rates_nac_sky)} SKY + {len(rates_nac_ei)} EI = {len(combinados_nac)} total")
        return combinados_nac

def _esperar_rates(qid, max_intentos=18, intervalo=3.0, use_ei=False):
    _req = _ei_request if use_ei else _request
    for i in range(max_intentos):
        time.sleep(intervalo)
        resp  = _req("GET", f"/quotations/{qid}")
        data  = resp.get("data", {})
        attrs = data.get("attributes", {}) if isinstance(data, dict) else {}
        completada = resp.get("is_completed") or attrs.get("is_completed")
        rates_raw  = (resp.get("rates") or attrs.get("rates") or data.get("rates") or [])

        rates_listos = [r for r in rates_raw
                        if (r.get("attributes", r).get("total") or
                            r.get("attributes", r).get("amount")) is not None]

        _log(f"Poll {i+1}/{max_intentos} completed={completada} total_rates={len(rates_raw)} listos={len(rates_listos)}")

        if completada:
            _log(f"RATES FINALES: {json.dumps(rates_raw)[:3000]}")
            if not rates_raw:
                raise APIError("Cotización completada sin tarifas disponibles.")
            return _parsear_rates(rates_raw, qid, es_internacional=use_ei)

        if rates_listos and len(rates_listos) >= 1:
            _log(f"Rates listos antes de completar: {len(rates_listos)}")
            return _parsear_rates(rates_listos, qid, es_internacional=use_ei)

    raise APIError(
        "La cotizacion tardo demasiado en responder.\n"
        "Intenta de nuevo en unos segundos."
    )


def _parsear_rates(rates_raw, qid, es_internacional=False):
    _log(f"PARSEAR {len(rates_raw)} rates raw (int={es_internacional}): {json.dumps(rates_raw)[:3000]}")
    INVALIDOS = {"tariff_price_not_found","no_coverage","not_applicable","error","failed","pending"}
    resultado = []
    for r in rates_raw:
        # En internacionales: success=false puede significar precio externo válido
        # Solo excluir si realmente no tiene precio
        if es_internacional and r.get("success") is False:
            _status = (r.get("status") or "").lower()
            _tiene_precio = bool(r.get("total") or r.get("amount"))
            if not _tiene_precio or _status in ("pending","no_coverage","not_applicable","error","failed"):
                _log(f"Rate INT EXCLUIDO (sin precio): {r.get('id','')} {r.get('provider_name','')} status={_status}")
                continue
        attrs   = r.get("attributes", r)
        status  = (attrs.get("status") or "").lower()
        if status in INVALIDOS:
            continue
        # Excluir tarifas que requieren verificación de dirección de origen —
        # Skydropx rechaza el shipment con 422 si la dirección no está verificada para ese carrier.
        if attrs.get("requires_origin_verification"):
            _log(f"Rate EXCLUIDO (requires_origin_verification): {r.get('id','')} {attrs.get('provider_name','')} {attrs.get('provider_service_name','')}")
            continue
        precio_s = attrs.get("total") or attrs.get("amount") or attrs.get("price") or "0"
        try: precio = float(str(precio_s).replace(",",""))
        except: precio = 0.0
        if precio <= 0: continue

        carrier  = (attrs.get("provider_display_name") or attrs.get("carrier_name")
                    or attrs.get("provider_name") or "Carrier").upper()
        servicio = (attrs.get("provider_service_name") or attrs.get("service_name")
                    or attrs.get("name") or "Servicio")
        try: dias = int(attrs.get("days") or attrs.get("delivery_days") or 0)
        except: dias = 0
        try: arancel = float(str(attrs.get("import_duty_amount") or "0").replace(",",""))
        except: arancel = 0.0

        resultado.append({
            "carrier":      carrier,
            "servicio":     servicio,
            "precio":       precio,
            "dias":         dias,
            "arancel":      arancel,
            "moneda":       attrs.get("currency_code") or attrs.get("currency") or "MXN",
            "rate_id":      r.get("id") or attrs.get("id") or "",
            "quotation_id": qid,
            "status":       status,
            "success":      True,
        })

    if not resultado:
        raise APIError("Sin tarifas disponibles para este destino.\nVerifica los códigos postales.")
    resultado.sort(key=lambda x: x["precio"])
    return resultado

import unicodedata as _ud
def _norm(s):
    """Normaliza string: quita acentos, minúsculas, strip."""
    return _ud.normalize("NFD", str(s)).encode("ascii","ignore").decode().lower().strip()

_CN_MAP = {
    # ── Documentos/Papelería ──────────────────────────────────────────────────
    # 14111812 = "Formatos o libros de inventarios" — catálogo oficial Skydropx ✓
    "documentos": "14111812", "documento": "14111812",
    "documentos personales": "14111812", "papeles": "14111812",
    "papeleria": "14111812", "papelería": "14111812",
    "sobre": "14111812", "carta": "14111812", "correspondencia": "14111812",
    "acta": "14111812", "escritura": "14111812", "titulo": "14111812",
    "expediente": "14111812", "contrato": "14111812",
    "libro": "14111812", "libros": "14111812",
    "revista": "14111812", "publicacion": "14111812", "publicación": "14111812",
    # ── Ropa ──────────────────────────────────────────────────────────────────
    # 53103001 = "Camisetas (t-shirts) para hombre" — catálogo Skydropx ✓
    "ropa": "53103001", "vestimenta": "53103001", "ropa usada": "53103001",
    "camisa": "53103001", "pantalon": "53103001", "vestido": "53103001",
    "blusa": "53103001", "falda": "53103001", "playera": "53103001",
    "ropa de bebe": "53103001", "ropa de bebé": "53103001",
    "camiseta": "53103001", "sudadera": "53103001", "pantalón": "53103001",
    # 53102511 = "Badanas" (cuero/calzado) — catálogo Skydropx ✓
    "calzado": "53102511", "zapatos": "53102511", "tenis": "53102511",
    "botas": "53102511", "sandalias": "53102511",
    # ── Higiene/Cosméticos ─────────────────────────────────────────────────────
    # 53131615 = "Productos para la higiene femenina" — catálogo Skydropx ✓
    "cosmetico": "53131615", "cosmético": "53131615",
    "cosmeticos": "53131615", "cosméticos": "53131615",
    "maquillaje": "53131615", "belleza": "53131615",
    "perfume": "53131615", "colonia": "53131615", "fragancia": "53131615",
    "perfumes": "53131615", "fragancias": "53131615",
    "shampoo": "53131615", "crema": "53131615", "locion": "53131615",
    "higiene": "53131615",
    # ── Electrónicos ──────────────────────────────────────────────────────────
    # 43201827 = "Dispositivo de almacenamiento de disco duro portátil" — catálogo Skydropx ✓
    "electronica": "43201827", "electrónica": "43201827",
    "electronico": "43201827", "electrónico": "43201827",
    "celular": "43201827", "smartphone": "43201827",
    "telefono": "43201827", "teléfono": "43201827",
    "computadora": "43201827", "laptop": "43201827",
    "tablet": "43201827", "consola": "43201827",
    "audifono": "43201827", "audífono": "43201827",
    # ── Muebles/Hogar ─────────────────────────────────────────────────────────
    # 56101532 = "Set de muebles" — catálogo Skydropx ✓
    "mueble": "56101532", "muebles": "56101532",
    "silla": "56101532", "sofa": "56101532", "sofá": "56101532",
    "cama": "56101532", "escritorio": "56101532",
    # 52141537 = "Olla de cocción lenta para uso doméstico" — catálogo Skydropx ✓
    "electrodomestico": "52141537", "electrodoméstico": "52141537",
    "electrodomesticos": "52141537", "electrodomésticos": "52141537",
    "licuadora": "52141537", "cafetera": "52141537",
    # ── Deportes/Juguetes ─────────────────────────────────────────────────────
    # 49181500 = "Equipos y juegos de mesa" — catálogo Skydropx ✓
    "deporte": "49181500", "deportes": "49181500",
    "juguete": "49181500", "juguetes": "49181500",
    "juego": "49181500", "juegos": "49181500",
    "juego de mesa": "49181500", "rompecabezas": "49181500",
    "muneca": "49181500", "muñeca": "49181500", "peluche": "49181500",
    "disfraz": "49181500",
    # ── Arte/Manualidades ─────────────────────────────────────────────────────
    # 60121600 = "Materiales de estudio" — catálogo Skydropx ✓
    "arte": "60121600", "artesania": "60121600", "artesanía": "60121600",
    "artesanias": "60121600", "artesanías": "60121600",
    "manualidades": "60121600", "cuadro": "60121600", "pintura": "60121600",
    # ── Instrumentos musicales ────────────────────────────────────────────────
    # 60131506 = "Accesorios para instrumentos de cuerda" — catálogo Skydropx ✓
    "instrumento": "60131506", "instrumentos": "60131506",
    "guitarra": "60131506", "violin": "60131506", "bateria": "60131506",
    # ── Joyería ───────────────────────────────────────────────────────────────
    # 54101513 = "Pisacorbatas" — catálogo Skydropx ✓
    "bisuteria": "54101513", "bisutería": "54101513",
    "joyeria": "54101513", "joyería": "54101513",
    "joyas": "54101513", "anillo": "54101513", "collar": "54101513",
    "pulsera": "54101513", "aretes": "54101513", "reloj": "54101513",
    # ── Todo lo demás → 14111812 (más neutro disponible en catálogo Skydropx)
    "mercancia": "14111812", "mercancía": "14111812",
    "paquete": "14111812", "varios": "14111812",
    "medicamento": "14111812", "medicamentos": "14111812",
    "medicina": "14111812", "farmacia": "14111812",
    "alimento": "14111812", "alimentos": "14111812",
    "comida": "14111812", "dulce": "14111812", "dulces": "14111812",
    "herramienta": "14111812", "herramientas": "14111812",
    "refaccion": "14111812", "refacción": "14111812",
    "refacciones": "14111812", "autoparte": "14111812",
    "autopartes": "14111812", "pieza": "14111812", "mesa": "14111812",
}


def _normalizar_colonia(colonia: str) -> str:
    """Convierte colonia a Title Case para coincidir con catálogo Skydropx/Sepomex."""
    if not colonia or colonia == "NA":
        return colonia or ""
    # Si viene en mayúsculas (TRES MISIONES -> Tres Misiones)
    if colonia == colonia.upper():
        return colonia.title()
    return colonia

def crear_guia(
    rate_id, quotation_id,
    nombre_origen, calle_origen, cp_origen, ciudad_origen, estado_origen,
    pais_origen="MX", colonia_origen="", empresa_origen="", tel_origen="",
    email_origen="", ref_origen="",
    nombre_destino="", calle_destino="", cp_destino="", ciudad_destino="",
    estado_destino="", pais_destino="MX", colonia_destino="", empresa_destino="",
    tel_destino="", email_destino="", ref_destino="",
    peso=1.0, alto=10, ancho=10, largo=10,
    contenido="Mercancía", valor_declarado=1.0, valor_declarado_usd=0.0, hs_code="", desc_en="",
    consignment_note_class_code="14111812",  # Mercancía general (fallback correcto)
    consignment_note_packaging_code="4G",    # Caja de cartón (default más común)
    customs_payment_payer="recipient", shipment_purpose="personal",
    **kwargs,
) -> dict:
    es_int = (pais_origen != pais_destino)
    # Mapear contenido a código SAT correcto según catálogo UNSPSC
    _cat_lower = (contenido or "").lower().strip()
    # Mapa Carta Porte SAT — códigos 100% verificados en el catálogo de Skydropx
    # Fuente: Listado_de_CartaPorte.pdf (catálogo oficial SAT exportado de Skydropx)
    _cat_norm = _norm(_cat_lower)
    # 01010000 = Mercancía general — acepta CUALQUIER producto en Skydropx
    _cn_code = "14111812"  # Mercancía general — fallback correcto
    for _k, _v in _CN_MAP.items():
        if _norm(_k) in _cat_norm or _cat_norm in _norm(_k):
            _cn_code = _v
            break

    # Carta Porte SAT: API PRO usa "consignment_note" y "package_type" a nivel RAIZ
    _declared = round(max(float(valor_declarado or 1), 1.0), 2)
    payload = {"shipment": {
        "quotation_id":    quotation_id,
        "rate_id":         rate_id,
        "consignment_note": _cn_code,
        "package_type":     consignment_note_packaging_code,
        "declared_value":   _declared,
        "address_from": {
            "name":str(nombre_origen),
            "street1": str(calle_origen)[:45],
            "postal_code":cp_origen,"area_level1":estado_origen or "NA",
            "area_level2":ciudad_origen or "NA","area_level3":_normalizar_colonia(colonia_origen) or "NA",
            "country_code":pais_origen,"company":empresa_origen or "N/A",
            "phone":tel_origen,"email":email_origen,"reference":ref_origen or "-",
        },
        "address_to": {
            "name":str(nombre_destino),
            "street1": str(calle_destino)[:45],
            "postal_code":cp_destino,"area_level1":estado_destino or "NA",
            "area_level2":ciudad_destino or "NA","area_level3":_normalizar_colonia(colonia_destino) or "NA",
            "country_code":pais_destino,"company":empresa_destino or "N/A",
            "phone":tel_destino,"email":email_destino or email_origen,"reference":ref_destino or "-",
        },
        "description": str(contenido or "Mercancía"),
        "parcels": [{
            "length": int(largo),
            "width":  int(ancho),
            "height": int(alto),
            "weight": float(peso),
            "description":     str(contenido or "Mercancía"),
            "package_content": str(contenido or "Mercancía"),
        }],
    }}

    if es_int:
        _INVALID_HS = {"", "9999.99", "9999.000000", None}
        _cat_key_fb = HS_ALIASES.get(_norm(contenido or ""), _norm(contenido or ""))
        _pais_dest_upper = (pais_destino or "US").upper()
        # Skydropx: usar HS_CODES_SKY (separado de EI). Skydropx no acepta 9999.x → fallback 4901
        if _cat_key_fb in HS_CODES_SKY:
            _hs_fallback = (hs_code or "").strip() or HS_CODES_SKY[_cat_key_fb].get(_pais_dest_upper, HS_CODES_SKY[_cat_key_fb].get("GLOBAL", HS_DEFAULT_SKY))
        else:
            _hs_fallback = (hs_code or "").strip() or HS_DEFAULT_BY_COUNTRY_SKY.get(_pais_dest_upper, HS_DEFAULT_SKY)

        _prods_factura = kwargs.get("productos_factura", [])
        # Skydropx internacional usa precio en USD — garantizar mínimo 1.0
        _tc3 = _get_tc_mxn_usd()
        try:
            _vdu = float(valor_declarado_usd) if valor_declarado_usd else 0.0
            _vdm = float(valor_declarado) if valor_declarado else 0.0
            if _vdu > 0:
                _valor_usd = _vdu
            elif _vdm > 0:
                _valor_usd = _vdm / _tc3
            else:
                _valor_usd = 1.0
        except (TypeError, ValueError):
            _valor_usd = 1.0
        _valor_mxn_para_ei = round(max(_valor_usd, 1.0), 2)
        _log(f"SKY INT crear_guia: price_USD={_valor_mxn_para_ei}")
        if _prods_factura:
            _products_parcel = []
            for _p in _prods_factura:
                _p_hs = _p.get("hs_code","") if _p.get("hs_code","") not in _INVALID_HS else _hs_fallback
                _desc_en = _p.get("description_en", _p.get("description_es","")) or str(contenido or "General merchandise")
                _desc_es = _p.get("description_es", _p.get("descripcion","")) or str(contenido or "General merchandise")
                _qty   = int(_p.get("quantity") or _p.get("cantidad") or 1)
                # precio en USD directo para EI
                _p_price = float(_p.get("price") or _p.get("unit_price") or _p.get("precio") or round(_valor_mxn_para_ei / max(_qty, 1), 2))
                # Si el precio viene en MXN (>500), convertir a USD
                if _p_price > 200 and _tc3 > 1:
                    _p_price = round(_p_price / _tc3, 2)
                _products_parcel.append({
                    "description":         _desc_es[:60],
                    "description_en":      _desc_en[:60],
                    "hs_code":             _p_hs,
                    "quantity":            _qty,
                    "price":               round(_p_price, 2),
                    "weight":              float(_p.get("weight") or _p.get("peso") or round(float(peso)/_qty, 2)),
                    "country_code":        (_p.get("country_code") or _p.get("country_of_origin") or pais_origen or "MX").upper(),
                    "product_type":        _p.get("product_type", "goods"),
                    "product_type_code":   _p.get("product_type_code", "goods"),
                })
        else:
            _en = (desc_en or "").strip() or DESC_EN.get(_cat_key_fb, f"General merchandise {contenido or ''}")
            _products_parcel = [{
                "description":        str(contenido or "General merchandise")[:60],
                "description_en":     _en[:60],
                "hs_code":            _hs_fallback,
                "quantity":           1,
                "price":              round(_valor_mxn_para_ei, 2),
                "weight":             float(peso),
                "country_code":       (pais_origen or "MX").upper(),
                "product_type":       "goods",
                "product_type_code":  "goods",
            }]

        _SKY_PURPOSE_MAP = {
            "personal":   "goods",
            "commercial": "goods",
            "gift":       "gift",
            "sample":     "sample",
            "repair":     "return_of_goods",
        }
        _purpose_sky = _SKY_PURPOSE_MAP.get(str(shipment_purpose).lower(), "goods")
        # Determinar customs_payment_payer correcto según lo que la tarifa permite.
        # rate_allowed_payers puede llegar como kwarg desde api.py/crear_envio.
        # Si la tarifa solo permite "sender", forzarlo independientemente de la selección del usuario.
        _rate_allowed = kwargs.get("rate_allowed_payers", None)
        _cpp = str(customs_payment_payer or "recipient").strip().lower()
        if _rate_allowed:
            # Normalizar la lista de pagadores permitidos
            _allowed_norm = [str(p).strip().lower() for p in _rate_allowed]
            if _cpp not in _allowed_norm:
                # El payer solicitado no está permitido — usar el primero disponible
                _cpp = _allowed_norm[0] if _allowed_norm else "sender"
                _log(f"INT customs_payment_payer corregido de '{customs_payment_payer}' a '{_cpp}' (rate permite: {_allowed_norm})")
        _cpp_final = _cpp  # valor validado
        _log(f"INT shipment_purpose={_purpose_sky} customs_payment_payer={_cpp_final}")

        # Estructura según Skydropx: consignment_note y package_type a nivel raíz
        # addresses solo llevan name/street1/company/phone/email/reference
        # Skydropx internacional: addresses completas (con country_code, postal_code, area_level1/2)
        payload_int = {"shipment": {
            "quotation_id":          quotation_id,
            "rate_id":               rate_id,
            "customs_payment_payer": _cpp_final,
            "shipment_purpose":      _purpose_sky,
            "printing_format":       "standard",
            "consignment_note":      _cn_code,
            "package_type":          consignment_note_packaging_code,
            "declared_value":        float(_valor_mxn_para_ei),
            "currency":              "USD",
            "address_from": {
                "name":         str(nombre_origen),
                "street1":      str(calle_origen)[:45],
                "company":      empresa_origen or "N/A",
                "phone":        tel_origen,
                "email":        email_origen,
                "reference":    ref_origen or "-",
                "country_code": pais_origen or "MX",
                "postal_code":  cp_origen or "",
                "area_level1":  estado_origen or "",
                "area_level2":  ciudad_origen or "",
                "area_level3":  _normalizar_colonia(colonia_origen) or "NA",
            },
            "address_to": {
                "name":         str(nombre_destino),
                "street1":      str(calle_destino)[:45],
                "company":      empresa_destino or "N/A",
                "phone":        tel_destino,
                "email":        email_destino or email_origen,
                "reference":    ref_destino or "-",
                "country_code": pais_destino or "US",
                "postal_code":  cp_destino or "",
                "area_level1":  estado_destino or "",
                "area_level2":  ciudad_destino or "",
                "area_level3":  _normalizar_colonia(colonia_destino) or "NA",
            },
            "parcels": [{
                "weight":        float(peso),
                "height":        int(alto),
                "width":         int(ancho),
                "length":        int(largo),
                "declared_value": float(_valor_mxn_para_ei),
                "products": _products_parcel,  # Skydropx también acepta products dentro del parcel
            }],
            "products": _products_parcel,
        }}
        _log(f"SKY INT PARCEL declared_value={_valor_mxn_para_ei} tipo={type(_valor_mxn_para_ei)}")
        _log(f"SKY INT PRODUCTS: {json.dumps(_products_parcel)}")
        _log(f"POST /shipments (SKY internacional)")
        _log(f"SKY INT PAYLOAD COMPLETO: {json.dumps(payload_int)[:3000]}")
        try:
            resp = _request("POST", "/shipments", data=payload_int, timeout=90)
        except APIError as _ae:
            _log(f"ERROR SHIPMENT SKY INT: {_ae}")
            raise
        _log(f"SKY INT GUIA RESP: {json.dumps(resp)[:600]}")
        # Mismo flujo que nacionales — si está in_progress, retornar pending para polling
        _data_i  = resp.get("data", resp)
        _attrs_i = _data_i.get("attributes", _data_i) if isinstance(_data_i, dict) else {}
        _sid_i   = _data_i.get("id") or _attrs_i.get("id") or ""
        _st_i    = _attrs_i.get("workflow_status") or _attrs_i.get("status") or ""
        if _sid_i and _st_i in ("in_progress", "pending", "waiting", "processing"):
            _log(f"INT Shipment '{_sid_i}' en estado '{_st_i}' — polling en frontend")
            return {"pending": True, "shipment_id": _sid_i, "carrier": _attrs_i.get("carrier_name","").upper(), "servicio": ""}
        return _parsear_guia(resp)

    _log("POST /shipments")
    _log(f"[v9-PRO-ROOT] PAYLOAD SHIPMENT parcels={json.dumps(payload.get('shipment',{}).get('parcels','?'))}")
    _log(f"PAYLOAD SHIPMENT COMPLETO: {json.dumps(payload)[:2000]}")
    try:
        resp = _request("POST", "/shipments", data=payload, timeout=90)
    except APIError as _ae:
        _log(f"ERROR SHIPMENT: {_ae}")
        raise
    except Exception as _ex:
        _log(f"EXCEPCION SHIPMENT: {_ex}")
        raise APIError(f"Error al crear guía: {_ex}")
    _log(f"GUIA RESP: {json.dumps(resp)[:600]}")
    # Log de direcciones normalizadas por Skydropx (para depurar colonias)
    try:
        _inc = resp.get("included", [])
        for _item in _inc:
            if _item.get("type") in ("address", "addresses"):
                _ia = _item.get("attributes", {})
                _log(f"ADDR SKYDROPX: type={_item.get('type')} level1={_ia.get('area_level1')} level2={_ia.get('area_level2')} level3={_ia.get('area_level3')} street1={_ia.get('street1')} cp={_ia.get('postal_code')}")
        # También buscar en data.attributes
        _da = resp.get("data", {})
        for _ak in ("address_from", "address_to"):
            _addr = (_da.get("attributes") or {}).get(_ak) or {}
            if _addr:
                _log(f"ADDR_ATTRS {_ak}: level3={_addr.get('area_level3')} cp={_addr.get('postal_code')}")
    except Exception as _le:
        _log(f"Error logueando dirs: {_le}")
    # Regresar inmediatamente — el frontend hará polling con /api/shipment_status/<sid>
    # NO hacer sleep aquí para no bloquear el worker de Gunicorn
    _data  = resp.get("data", resp)
    _attrs = _data.get("attributes", _data) if isinstance(_data, dict) else {}
    _sid   = _data.get("id") or _attrs.get("id") or ""
    _st    = _attrs.get("workflow_status") or _attrs.get("status") or ""
    if _sid and _st in ("in_progress", "pending", "waiting", "processing"):
        _log(f"Shipment '{_sid}' en estado '{_st}' — regresando para polling en frontend")
        # Retornar con pending=True para que el frontend haga polling
        return {"pending": True, "shipment_id": _sid, "carrier": _attrs.get("carrier_name","").upper(), "servicio": ""}
    return _parsear_guia(resp)

def _parsear_guia(resp):
    data  = resp.get("data", resp)
    attrs = data.get("attributes", data) if isinstance(data, dict) else data
    sid   = data.get("id") or attrs.get("id") or ""
    trk   = (attrs.get("tracking_number") or attrs.get("tracking") or
             attrs.get("tracking_code") or attrs.get("waybill") or "")
    url   = (attrs.get("label_url") or attrs.get("label") or
             attrs.get("pdf_label_url") or attrs.get("pdf_url") or "")

    # *** API PRO Skydropx: tracking y label_url están en included[type=package] ***
    included = resp.get("included", [])
    for item in included:
        if item.get("type") == "package":
            ia = item.get("attributes", {})
            trk = trk or ia.get("tracking_number") or ia.get("tracking") or ""
            url = url or ia.get("label_url") or ia.get("label") or ia.get("pdf_url") or ""
        if trk and url:
            break

    # master_tracking_number como fallback para tracking
    if not trk:
        trk = attrs.get("master_tracking_number") or ""

    if not trk and not url:
        _log(f"SIN TRACKING - RESP COMPLETA: {json.dumps(resp)}")
        raise APIError(f"Guía creada sin tracking/etiqueta.\nID: {sid}\nRevisa en pro.skydropx.com\nResp: {json.dumps(resp)[:200]}")
    # Obtener carrier/servicio desde los datos del rate o del included
    _carrier = (attrs.get("carrier_name") or attrs.get("carrier") or "").upper()
    _servicio = attrs.get("service_name") or attrs.get("service") or ""
    # Buscar servicio en included si no está en attrs
    for _inc in included:
        if _inc.get("type") == "service":
            _ia = _inc.get("attributes", {})
            _servicio = _servicio or _ia.get("service_name") or _ia.get("name") or ""

    return {
        "shipment_id":     sid,
        "numero_rastreo":  trk,   # alias para _envio_creado
        "tracking_number": trk,
        "label_url":       url,
        "carrier":         _carrier,
        "servicio":        _servicio,
        "estado":          attrs.get("status") or attrs.get("workflow_status") or "",
    }

def descargar_guia_pdf(label_url: str) -> bytes:
    """
    Descarga el PDF de la guía desde la URL del proveedor.
    Usa una sesión requests SIN proxy para evitar bloqueos del proxy de Render
    con URLs de CDN externas (Skydropx, EI, etc.).
    """
    import requests as _req
    _VERIFY = os.environ.get("REQUESTS_CA_BUNDLE") or True
    try:
        # Sesión limpia sin proxy — las URLs de etiquetas son CDN públicos
        # que no requieren autenticación pero el proxy de Render puede bloquearlas
        _s = _req.Session()
        _s.proxies = {}  # Sin proxy
        r = _s.get(label_url, timeout=30, verify=_VERIFY)
        r.raise_for_status()
        # Verificar que es realmente un PDF o imagen
        ct = r.headers.get("Content-Type", "")
        if len(r.content) < 100:
            raise APIError(f"Respuesta vacía o muy pequeña ({len(r.content)} bytes)")
        return r.content
    except APIError:
        raise
    except Exception as e:
        # Fallback: intentar con urllib (sin proxy por defecto en Render)
        try:
            import urllib.request
            import urllib.error
            req = urllib.request.Request(label_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
                if len(data) < 100:
                    raise APIError(f"Respuesta vacía en fallback ({len(data)} bytes)")
                return data
        except APIError:
            raise
        except Exception as e2:
            raise APIError(f"Error descargando PDF: {e} | fallback: {e2}")

def guardar_label_pdf(label_url: str, ruta_destino: str) -> str:
    """
    Descarga la guía PDF del proveedor y la guarda en ruta_destino.
    Retorna la ruta donde fue guardada.
    """
    import os
    os.makedirs(os.path.dirname(ruta_destino), exist_ok=True)
    pdf_bytes = descargar_guia_pdf(label_url)
    with open(ruta_destino, "wb") as f:
        f.write(pdf_bytes)
    _log(f"Guía oficial guardada: {ruta_destino} ({len(pdf_bytes)} bytes)")
    return ruta_destino

def descargar_guia_por_id(shipment_id: str) -> bytes:
    resp  = _request("GET", f"/shipments/{shipment_id}")
    data  = resp.get("data", resp)
    attrs = data.get("attributes", data) if isinstance(data, dict) else {}
    url   = attrs.get("label_url") or attrs.get("label") or attrs.get("pdf_label_url")
    if not url: raise APIError(f"Sin URL de etiqueta para {shipment_id}")
    return descargar_guia_pdf(url)

def get_productos() -> list[dict]:
    resp = _request("GET", "/products")
    out  = []
    for item in resp.get("data", []):
        a = item.get("attributes", {})
        out.append({"id":item.get("id"),"carrier":a.get("carrier_name",""),
                    "servicio":a.get("service_name",""),"codigo":a.get("service_code",""),
                    "dias":a.get("days",""),"descripcion":a.get("description","")})
    return out

def proteger_envio(shipment_id: str, valor_declarado: float) -> dict:
    """
    Agrega seguro a un envío ya creado.
    Endpoint: POST /api/v1/shipments/{shipment_id}/protect
    valor_declarado: valor en MXN de la mercancía
    """
    payload = {"shipment": {"declared_value": round(float(valor_declarado), 2)}}
    try:
        resp = _request("POST", f"/shipments/{shipment_id}/protect", data=payload)
        _log(f"PROTECT resp: {json.dumps(resp)[:300]}")
        return resp
    except Exception as e:
        raise APIError(f"Error al proteger envío: {e}")

def rastrear_envio(tracking_number: str, carrier_name: str = "") -> dict:
    return _request("GET", f"/shipments/tracking?tracking_number={tracking_number}&carrier_name={carrier_name}")


# ── Wrapper de compatibilidad ─────────────────────────────────────
def _crear_guia_ei(quotation_id, rate_id, remitente, destinatario, paquete,
                   contenido="Mercancía", shipment_purpose="personal",
                   customs_payment_payer="recipient",
                   printing_format="letter",
                   rate_allowed_payers=None) -> dict:
    """Crea envío INTERNACIONAL en Envíos Internacionales."""
    _log(f"CREAR GUIA EI qid={quotation_id} rid={rate_id}")

    # HS Code para products (aduana)
    _cat_lower = _norm(contenido or "")
    _cat_key = HS_ALIASES.get(_cat_lower, _cat_lower)
    _pais_d = destinatario.get("pais", "US").upper()
    if _cat_key in HS_CODES_BY_COUNTRY:
        _hs = HS_CODES_BY_COUNTRY[_cat_key].get(_pais_d, HS_CODES_BY_COUNTRY[_cat_key].get("US", HS_DEFAULT))
    else:
        _hs = HS_DEFAULT_BY_COUNTRY.get(_pais_d, HS_DEFAULT)
    _desc_en = DESC_EN.get(_cat_key, DESC_EN.get("mercancia", "General merchandise"))

    # Código SAT UNSPSC para consignment_note (igual que Skydropx nacional)
    _cat_norm = _norm(contenido or "")
    _cn_code = "14111812"  # Mercancía general — código correcto SAT
    for _k, _v in _CN_MAP.items():
        if _norm(_k) in _cat_norm or _cat_norm in _norm(_k):
            _cn_code = _v
            break

    # shipment_purpose — valores confirmados por EI
    # EI: shipment_purpose y customs_payment_payer
    _PURPOSE_MAP_EI = {
        "personal":   "gift",
        "gift":       "gift",
        "commercial": "gift",
        "sample":     "gift",
        "repair":     "gift",
    }
    _purpose_ei = _PURPOSE_MAP_EI.get(str(shipment_purpose).lower(), "gift")
    # customs_payment_payer: Estafeta y la mayoría de carriers EI SOLO permiten "sender".
    # Siempre forzamos "sender" para evitar 422 "Pagador de aranceles no permitido".
    # Si en el futuro hay carriers que permitan "recipient", se puede personalizar aquí.
    _payer_ei = "sender"
    _log(f"EI customs_payment_payer forzado a 'sender' (input era '{customs_payment_payer}', rate_allowed={rate_allowed_payers})")

    # Valor declarado y precio por producto
    _valor = float(paquete.get("valor_declarado", 0) or 0) or 1.0
    _peso  = float(paquete.get("peso", 1.0) or 1.0)
    _largo = int(paquete.get("largo", 10) or 10)
    _ancho = int(paquete.get("ancho", 10) or 10)
    _alto  = int(paquete.get("alto",  10) or 10)

    # Productos para aduana — mínimo requerido por EI
    _INVALID_HS = {"", "9999.99", "9999.000000", None}
    _productos_factura = paquete.get("productos_factura", [])
    # EI requiere product_type_code (UNSPSC) y product_type_name — NO "product_type".
    # Usamos el mismo código UNSPSC que ya calculamos para consignment_note (_cn_code).
    # Mapa UNSPSC → nombre en inglés para product_type_name
    _UNSPSC_NAME_MAP = {
        "14111812": "Documents and stationery",
        "53103001": "Clothing and garments",
        "53102511": "Footwear",
        "60141200": "Toys and games",
        "43211500": "Computers and peripherals",
        "44121618": "Books",
        "46182001": "Sports equipment",
        "52152003": "Jewelry",
        "50000000": "Food and beverage",
        "70111800": "Home decor",
        "31162700": "Electronic components",
        "25172700": "Automotive parts",
        "51101512": "Pharmaceuticals",
        "53102800": "Bags and luggage",
    }
    _prod_type_code = _cn_code  # UNSPSC code ya calculado según contenido
    _prod_type_name = _UNSPSC_NAME_MAP.get(_prod_type_code, "General merchandise")
    _log(f"EI product_type_code={_prod_type_code} product_type_name={_prod_type_name}")
    if _productos_factura:
        _products = []
        for _p in _productos_factura:
            _p_desc_en = (_p.get("description_en") or _desc_en or "General merchandise")[:60]
            _p_hs = _p.get("hs_code","") if _p.get("hs_code","") not in _INVALID_HS else _hs
            _p_ptc = _p.get("product_type_code", _prod_type_code)
            _p_ptn = _p.get("product_type_name", _UNSPSC_NAME_MAP.get(_p_ptc, _prod_type_name))
            _products.append({
                "description":       str(_p.get("descripcion") or _p.get("description") or contenido)[:60],
                "description_en":    _p_desc_en,
                "quantity":          int(_p.get("cantidad") or _p.get("quantity") or 1),
                "price":             float(_p.get("price") or _p.get("precio") or _valor),
                "weight":            float(_p.get("weight") or _p.get("peso") or _peso),
                "hs_code":           _p_hs,
                "hs_code_description": str(_p_desc_en)[:60],
                "country_code":      str(_p.get("country_code") or "MX"),
                "product_type_code": _p_ptc,
                "product_type_name": _p_ptn,
            })
    else:
        _products = [{
            "description":       str(contenido or "General merchandise")[:60],
            "description_en":    str(_desc_en or "General merchandise")[:60],
            "quantity":          1,
            "price":             _valor,
            "weight":            _peso,
            "hs_code":           _hs,
            "hs_code_description": str(_desc_en or "General merchandise")[:60],
            "country_code":      "MX",
            "product_type_code": _prod_type_code,
            "product_type_name": _prod_type_name,
        }]

    payload = {"shipment": {
        "quotation_id": quotation_id,
        "rate_id":      rate_id,
        "address_from": {
            "name":        str(remitente.get("nombre", "Remitente")),
            "street1":     str(remitente.get("calle", remitente.get("direccion","")) or "")[:45],
            "postal_code": remitente.get("cp",""),
            "area_level1": remitente.get("estado",""),
            "area_level2": remitente.get("ciudad",""),
            "area_level3": _normalizar_colonia(remitente.get("colonia","")),
            "country_code":remitente.get("pais","MX"),
            "phone":       remitente.get("telefono",""),
            "email":       remitente.get("email","noreply@paquetellegue.com"),
            "reference":   "-",
        },
        "address_to": {
            "name":        str(destinatario.get("nombre", "Destinatario")),
            "street1":     str(destinatario.get("calle", destinatario.get("direccion","")) or "")[:45],
            "postal_code": destinatario.get("cp",""),
            "area_level1": destinatario.get("estado",""),
            "area_level2": destinatario.get("ciudad",""),
            "area_level3": _normalizar_colonia(destinatario.get("colonia","")),
            "country_code":destinatario.get("pais","US"),
            "phone":       destinatario.get("telefono",""),
            "email":       destinatario.get("email","") or "noreply@paquetellegue.com",
            "reference":   "-",
        },
        "description":           str(contenido or "General merchandise")[:60],
        "shipment_purpose":      _purpose_ei,
        "customs_payment_payer": _payer_ei,
        "consignment_note":      _cn_code,
        "package_type":          "4G",
        "parcels": [{
            "length":                          _largo,
            "width":                           _ancho,
            "height":                          _alto,
            "weight":                          _peso,
            "description":                     str(contenido or "General merchandise")[:60],
            "consignment_note":                _cn_code,
            "consignment_note_class_code":     _cn_code,
            "commodity_code":                  _cn_code,
            "package_type":                    "4G",
            "packaging_type":                  "package",
            "consignment_note_packaging_code": "4G",
        }],
        "products": _products,
    }}

    # (campos opcionales eliminados del nivel raíz — EI los requiere solo en parcels)

    _log(f"EI rate_allowed_payers={rate_allowed_payers} customs_input={customs_payment_payer} payer_final={_payer_ei}")
    _log(f"EI PRODUCTS: {json.dumps(_products)}")
    _log(f"EI SHIPMENT PAYLOAD: {json.dumps(payload)[:3000]}")
    resp  = _ei_request("POST", "/shipments", data=payload)
    _log(f"EI GUIA RESP: {json.dumps(resp)[:1000]}")

    _data  = resp.get("data", resp)
    _attrs = _data.get("attributes", _data) if isinstance(_data, dict) else {}
    _sid   = _data.get("id") or _attrs.get("id") or ""
    _st    = _attrs.get("workflow_status") or _attrs.get("status") or ""

    if _sid and _st in ("in_progress","pending","waiting","processing"):
        return {"pending": True, "shipment_id": _sid,
                "carrier": _attrs.get("carrier_name","").upper(), "proveedor": "ei"}

    # Buscar tracking y label en included
    included = resp.get("included", [])
    trk = _attrs.get("tracking_number") or _attrs.get("master_tracking_number") or ""
    url = _attrs.get("label_url") or ""
    for item in included:
        if item.get("type") == "package":
            ia = item.get("attributes", {})
            trk = trk or ia.get("tracking_number","")
            url = url or ia.get("label_url","")
    return {
        "shipment_id": _sid, "numero_rastreo": trk,
        "label_url": url, "carrier": _attrs.get("carrier_name","").upper(),
        "servicio": _attrs.get("service_name",""), "proveedor": "ei",
    }


def crear_envio(quotation_id, rate_id, remitente: dict,
                destinatario: dict, paquete: dict,
                contenido="Mercancía general", referencia="",
                valor_declarado=None, valor_declarado_usd=0.0,
                customs_payment_payer="recipient",
                shipment_purpose="personal",
                printing_format="letter",
                rate_allowed_payers=None,
                proveedor="") -> dict:
    """
    Interfaz de alto nivel: recibe dicts remitente/destinatario/paquete.
    Para internacionales usa EI por defecto, o Skydropx si proveedor="skydropx".
    """
    import datetime, random

    pais_dest = destinatario.get("pais","MX")
    pais_orig = remitente.get("pais","MX")
    es_int = _es_internacional(pais_orig, pais_dest)

    # EI: internacionales por defecto, o nacionales si el rate viene de EI
    if proveedor.lower() == "ei" or (es_int and proveedor.lower() != "skydropx"):
        return _crear_guia_ei(
            quotation_id=quotation_id,
            rate_id=rate_id,
            remitente=remitente,
            destinatario=destinatario,
            paquete=paquete,
            contenido=contenido,
            shipment_purpose=shipment_purpose,
            customs_payment_payer=customs_payment_payer,
            printing_format=printing_format,
            rate_allowed_payers=rate_allowed_payers,
        )

    # Nacionales → Skydropx
    # email_origen: usar el del remitente, o fallback genérico
    email_origen = (remitente.get("email") or "").strip()
    if not email_origen:
        # Intentar leer de la configuración de la empresa
        try:
            from modules import database as _db
            cfg = _db.get_config()
            email_origen = cfg.get("empresa_email", "").strip()
        except Exception:
            pass
    if not email_origen:
        email_origen = "noreply@paquetellegue.com"

    return crear_guia(
        rate_id=rate_id,
        quotation_id=quotation_id,
        # Origen
        nombre_origen=remitente.get("nombre", ""),
        calle_origen=remitente.get("calle", remitente.get("direccion", "")),
        cp_origen=remitente.get("cp", ""),
        ciudad_origen=remitente.get("ciudad", ""),
        estado_origen=remitente.get("estado", ""),
        pais_origen=remitente.get("pais", "MX"),
        colonia_origen=remitente.get("colonia", ""),
        empresa_origen=remitente.get("empresa", ""),
        tel_origen=remitente.get("telefono", remitente.get("tel", "")),
        email_origen=email_origen,
        ref_origen=referencia,
        # Destino
        nombre_destino=destinatario.get("nombre", ""),
        calle_destino=" ".join(filter(None, [
            destinatario.get("calle", ""),
            destinatario.get("num_interior", "")
        ])),
        cp_destino=destinatario.get("cp", ""),
        ciudad_destino=destinatario.get("ciudad", ""),
        estado_destino=destinatario.get("estado", ""),
        pais_destino=destinatario.get("pais", "MX"),
        colonia_destino=destinatario.get("colonia", ""),
        empresa_destino=destinatario.get("empresa", ""),
        tel_destino=destinatario.get("telefono", destinatario.get("tel", "")),
        email_destino=destinatario.get("email", ""),
        ref_destino=destinatario.get("referencia", ""),
        # Paquete
        peso=paquete.get("peso", 1.0),
        alto=paquete.get("alto", 10),
        ancho=paquete.get("ancho", 10),
        largo=paquete.get("largo", 10),
        contenido=contenido,
        valor_declarado=valor_declarado if valor_declarado is not None else paquete.get("valor_declarado", 1.0),
        valor_declarado_usd=valor_declarado_usd or paquete.get("valor_declarado_usd", 0.0),
        hs_code=paquete.get("hs_code", ""),
        desc_en=paquete.get("desc_en", ""),
        consignment_note_class_code=paquete.get("consignment_note_class_code", "14111812"),
        consignment_note_packaging_code=paquete.get("consignment_note_packaging_code", "4G"),
        customs_payment_payer=customs_payment_payer,
        shipment_purpose=shipment_purpose,
        productos_factura=paquete.get("productos_factura", []),
        rate_allowed_payers=rate_allowed_payers,
    )

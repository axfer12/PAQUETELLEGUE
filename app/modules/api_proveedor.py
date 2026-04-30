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

# ── Config Skydropx (Envíos NACIONALES) ──────────────────────────
API_BASE   = "https://pro.skydropx.com/api/v1"
CLIENT_ID  = "BCFhzgf1_BwKuYfzMRaf2Kncm0pigheSo94CFdrmZcs"
CLIENT_SEC = "-Fq2tF48UNrhsGAN6oB9rkoywkw2x2cWXq9KuSu_lnY"

# ── Config Envíos Internacionales (Envíos INTERNACIONALES) ────────
EI_API_BASE   = "https://app.enviosinternacionales.com/api/v1"
EI_CLIENT_ID  = "gtXpeDxcoHGCsbSJXBpa_6ygxbw4usoesc868XEAZ2I"
EI_CLIENT_SEC = "MvcA6bSwXRPT03Jh4QO5u0rs_id-qtbfxJERWGnXB8E"
_ei_token_cache: dict = {}
_ei_token_lock  = threading.Lock()

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
    print(f"[{ts}][SKY] {m}", flush=True, file=sys.stderr)
    try:
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "data", "api_debug.log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as lf:
            lf.write(f"[{ts}][SKY] {m}\n")
    except Exception:
        pass

_session = None
def _get_session():
    global _session
    if not _REQUESTS_OK: return None
    if _session is None:
        _session = _requests.Session()
        _session.headers.update({"User-Agent":"PAQUETELLEGUE/2.0","Accept":"application/json"})
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
    """Obtiene token OAuth de Envíos Internacionales (envíos internacionales)."""
    with _ei_token_lock:
        now = time.time()
        if _ei_token_cache.get("token") and now < _ei_token_cache.get("exp", 0) - 60:
            return _ei_token_cache["token"]
        url  = f"{EI_API_BASE}/oauth/token"
        body = {"grant_type":"client_credentials","client_id":EI_CLIENT_ID,"client_secret":EI_CLIENT_SEC}
        sess = _get_session()
        try:
            if sess:
                r = sess.post(url, json=body, timeout=20)
                if not r.ok:
                    raise APIError(f"EI Auth {r.status_code}: {r.text[:200]}")
                data = r.json()
            else:
                import urllib.request as _ur
                req = _ur.Request(url, json.dumps(body).encode(),
                      {"Content-Type":"application/json"}, method="POST")
                with _ur.urlopen(req, timeout=20) as r:
                    data = json.loads(r.read())
            tok = data.get("access_token","")
            if not tok: raise APIError(f"EI token vacío: {data}")
            _ei_token_cache["token"] = tok
            _ei_token_cache["exp"]   = now + int(data.get("expires_in", 7200))
            _log("EI Token OK")
            return tok
        except APIError: raise
        except Exception as e: raise APIError(f"EI Auth error: {e}")


def _ei_request(method, endpoint, data=None, timeout=45):
    """Request a la API de Envíos Internacionales usando requests.Session."""
    url   = f"{EI_API_BASE}{endpoint}"
    token = get_ei_token()
    hdrs  = {"Content-Type":"application/json","Authorization":f"Bearer {token}"}
    sess  = _get_session()
    try:
        if sess:
            if method.upper() == "POST":
                r = sess.post(url, json=data, headers=hdrs, timeout=timeout)
            else:
                r = sess.get(url, headers=hdrs, timeout=timeout)
            if not r.ok:
                _log(f"EI ERROR {r.status_code}: {r.text[:1000]}")
                raise APIError(f"EI HTTP {r.status_code}: {r.text[:500]}")
            return r.json()
        else:
            import urllib.request as _ur, urllib.error as _ue
            body = json.dumps(data).encode() if data else None
            req  = _ur.Request(url, body, hdrs, method=method)
            try:
                with _ur.urlopen(req, timeout=timeout) as r:
                    return json.loads(r.read())
            except _ue.HTTPError as e:
                txt = e.read().decode("utf-8","replace")
                raise APIError(f"EI HTTP {e.code}: {txt[:300]}")
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
    contenido="Mercancía", valor_declarado=1.0, desc_en="", hs_code="",
) -> list[dict]:
    """Cotiza envío INTERNACIONAL usando Envíos Internacionales."""
    pais_origen  = (pais_origen  or "MX").upper().strip()
    pais_destino = (pais_destino or "US").upper().strip()
    # Mapear nombres completos a códigos ISO
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
    valor = max(float(valor_declarado or 1), 1.0)
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
        "parcels": [{"length":int(largo),"width":int(ancho),"height":int(alto),"weight":float(peso)}],
        "products": [{
            "description": desc_ingles,
            "description_en": (desc_ingles + " - general merchandise")[:50],
            "quantity": 1,
            "price": str(valor),
            "hs_code": hs,
            "currency": "MXN",
            "country_code": pais_origen,
            "weight": float(peso),
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
    """Parsea rates de Envíos Internacionales al formato estándar.
    Filtra rates thermal — EI los rechaza al crear shipment si el carrier no los soporta.
    Prefiere rates con printing_format letter/pdf/label.
    """
    INVALIDOS = {"error","no_coverage","failed","pending"}
    _rate_providers = {r.get("id",""): r.get("provider_name","?") for r in rates_raw}
    _log(f"EI rate_providers: {_rate_providers}")
    rates_letter = []
    rates_thermal = []
    for r in rates_raw:
        # CRÍTICO: excluir rates con success=false
        if r.get("success") is False:
            _log(f"EI rate EXCLUIDO (success=false): {r.get('id','')} {r.get('provider_name','')}")
            continue
        # Excluir FedEx — genera error 500 en EI (requiere acuerdo comercial)
        if (r.get("provider_name") or "").lower() == "fedex":
            _log(f"EI rate EXCLUIDO (fedex): {r.get('id','')} {r.get('provider_service_name','')}")
            continue
        status = (r.get("status") or "").lower()
        if status in INVALIDOS: continue
        try: precio = float(str(r.get("total") or r.get("amount") or "0").replace(",",""))
        except: precio = 0.0
        if precio <= 0: continue
        carrier  = (r.get("provider_display_name") or r.get("provider_name") or "Carrier").upper()
        servicio = r.get("provider_service_name") or r.get("name") or "Servicio"
        try: dias = int(r.get("days") or 0)
        except: dias = 0
        try: arancel = float(str(r.get("import_duty_amount") or "0").replace(",",""))
        except: arancel = 0.0
        pf = (r.get("printing_format") or "letter").lower()
        entry = {
            "carrier": carrier, "servicio": servicio, "precio": precio,
            "dias": dias, "arancel": arancel,
            "moneda": r.get("currency_code") or "MXN",
            "rate_id": r.get("id") or "",
            "quotation_id": qid, "status": status,
            "printing_format": pf,
            "proveedor": "ei",
        }
        if pf == "thermal":
            rates_thermal.append(entry)
        else:
            rates_letter.append(entry)
    resultado = rates_letter if rates_letter else rates_thermal
    if not resultado:
        raise APIError("EI: Sin tarifas disponibles para este destino.")
    resultado.sort(key=lambda x: x["precio"])
    return resultado


def cotizar_envio(
    cp_origen, cp_destino, peso, alto, ancho, largo,
    pais_origen="MX", pais_destino="MX",
    estado_origen="", ciudad_origen="", colonia_origen="", nombre_origen="Remitente",
    estado_destino="", ciudad_destino="", colonia_destino="", nombre_destino="Destinatario",
    contenido="Mercancía", valor_declarado=1.0, desc_en="", hs_code="",
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
        valor = max(float(valor_declarado or 1), 1.0)
        cat   = (contenido or "").lower().strip()
        _cat_key2 = HS_ALIASES.get(cat, cat)
        _pais_d2 = (pais_destino or "US").upper()
        if _cat_key2 in HS_CODES_BY_COUNTRY:
            hs = (hs_code or "").strip() or HS_CODES_BY_COUNTRY[_cat_key2].get(_pais_d2, HS_CODES_BY_COUNTRY[_cat_key2].get("US", HS_DEFAULT))
        else:
            hs = (hs_code or "").strip() or HS_DEFAULT_BY_COUNTRY.get(_pais_d2, HS_DEFAULT)
        en = (desc_en or "").strip() or DESC_EN.get(_cat_key2, f"General merchandise: {contenido}")
        # products va DENTRO de cada parcel
        payload["quotation"]["parcels"][0]["products"] = [{
            "hs_code": hs, "description_en": en,
            "country_code": pais_origen, "quantity": 1, "price": round(valor, 2),
        }]
        _log(f"EI INT {pais_origen}→{pais_destino} hs={hs}")
        _log(f"POST /quotations (EI)")
        resp = _ei_request("POST", "/quotations", data=payload)
    else:
        _log(f"POST /quotations")
        resp = _request("POST", "/quotations", data=payload)
    _log(f"RESP COMPLETA: {json.dumps(resp)[:3000]}")

    data_obj     = resp.get("data", {})
    qid = (resp.get("id") or data_obj.get("id")
           or (data_obj.get("attributes") or {}).get("id"))
    is_completed = resp.get("is_completed") or (data_obj.get("attributes") or {}).get("is_completed")

    if not qid:
        raise APIError(f"Respuesta inesperada (sin ID): {json.dumps(resp)[:300]}")

    # Si ya completó en el POST (raro), parsear directo
    if is_completed:
        rates_raw = resp.get("rates") or (data_obj or {}).get("rates") or []
        if rates_raw:
            return _parsear_rates(rates_raw, qid, es_internacional=es_int)

    # Polling — pasar use_ei para internacionales
    return _esperar_rates(qid, use_ei=es_int)

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
    # ── Documentos ──────────────────────────────────────────────────────────
    "documentos": "14111813", "documento": "14111813",
    "documentos personales": "14111813", "papeles": "14111813",
    "papeleria": "14111813", "papelería": "14111813",
    "sobre": "14111813", "carta": "14111813", "correspondencia": "14111813",
    "acta": "14111813", "escritura": "14111813", "titulo": "14111813",
    "expediente": "14111813", "contrato": "14111813",
    # ── Instrumentos musicales (60131xxx) ───────────────────────────────────
    "instrumento musical": "60131000", "instrumentos musicales": "60131000",
    "piano": "60131001", "acordeon": "60131002", "acordeón": "60131002",
    "organo": "60131003", "órgano": "60131003", "sintetizador": "60131006",
    "trompeta": "60131101", "trombon": "60131102", "saxofon": "60131104",
    "clarinete": "60131201", "flauta": "60131203", "armonica": "60131207",
    "guitarra": "60131303", "violin": "60131304", "arpa": "60131305",
    "mandolina": "60131307", "ukelele": "60131324", "viola": "60131325",
    "bateria": "60131400", "platillo": "60131401", "tambor": "60131405",
    "xilofono": "60131406", "marimba": "60131448", "percusion": "60131400",
    "instrumento": "60131000", "instrumentos": "60131000",
    "musica": "60131000", "música": "60131000",
    "accesorios musicales": "60131500",
    # ── Juguetes y juegos (60141xxx) ────────────────────────────────────────
    "juguete": "60141000", "juguetes": "60141000",
    "muneca": "60141002", "muñeca": "60141002", "peluche": "60141004",
    "juego de mesa": "60141102", "naipes": "60141103", "rompecabezas": "60141105",
    "juego": "60141100", "juegos": "60141100",
    "disfraz": "60141401", "disfraces": "60141401",
    # ── Arte y manualidades (60121xxx) ──────────────────────────────────────
    "arte": "60121000", "pintura": "60121001", "escultura": "60121002",
    "artesania": "60121000", "artesanía": "60121000",
    "artesanias": "60121000", "artesanías": "60121000",
    "manualidades": "60121000", "cuadro": "60121006",
    # ── Cosméticos y perfumes (53131xxx) ────────────────────────────────────
    "cosmetico": "53131619", "cosmético": "53131619",
    "cosmeticos": "53131619", "cosméticos": "53131619",
    "maquillaje": "53131619", "belleza": "53131619",
    "perfume": "53131620", "colonia": "53131620", "fragancia": "53131620",
    "perfumes": "53131620", "fragancias": "53131620",
    # ── Bisutería y joyería (54101xxx) ──────────────────────────────────────
    "bisuteria": "54101600", "bisutería": "54101600",
    "joyeria": "54101600", "joyería": "54101600",
    "joyas": "54101600", "anillo": "54101600", "collar": "54101600",
    "pulsera": "54101600", "aretes": "54101600",
    # ── Electrodomésticos (52141xxx) ─────────────────────────────────────────
    "electrodomestico": "52141800", "electrodoméstico": "52141800",
    "electrodomesticos": "52141800", "electrodomésticos": "52141800",
    "licuadora": "52141500", "cafetera": "52141500", "tostadora": "52141500",
    # ── Electrónica (43201xxx) ───────────────────────────────────────────────
    "electronica": "43201604", "electrónica": "43201604",
    "elektronico": "43201604", "electrónico": "43201604",
    # ── Teléfonos (43191xxx) ─────────────────────────────────────────────────
    "telefono": "43191501", "teléfono": "43191501",
    "celular": "43191501", "smartphone": "43191501",
    "telefonos": "43191501", "teléfonos": "43191501",
    # ── Muebles (56101xxx) ───────────────────────────────────────────────────
    "mueble": "56101500", "muebles": "56101500",
    "silla": "56101504", "sofa": "56101502", "sofá": "56101502",
    "cama": "56101515", "mesa": "56101519", "escritorio": "56101703",
    "mobiliario": "56101500",
    # ── Publicaciones (55101xxx) ─────────────────────────────────────────────
    "libro": "55101500", "libros": "55101500",
    "revista": "55101519", "publicacion": "55101500", "publicación": "55101500",
    # ── Medicamentos ─────────────────────────────────────────────────────────
    "medicamento": "14111824", "medicamentos": "14111824",
    "medicina": "14111824", "farmacia": "14111824",
    # ── Ropa y calzado (60105xxx - diseño textil educativo es lo más cercano)
    # Para ropa usar 53131619 como categoría general de productos personales
    "ropa": "53131619", "vestimenta": "53131619", "ropa usada": "53131619",
    "camisa": "53131619", "pantalon": "53131619", "vestido": "53131619",
    "calzado": "53131619", "zapatos": "53131619", "tenis": "53131619",
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
    contenido="Mercancía", valor_declarado=1.0, hs_code="", desc_en="",
    consignment_note_class_code="53131619",  # Mercancía general (fallback seguro)
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
    _cn_code = "53131619"
    for _k, _v in _CN_MAP.items():
        if _norm(_k) in _cat_norm or _cat_norm in _norm(_k):
            _cn_code = _v
            break

    # Carta Porte SAT: API PRO usa "consignment_note" y "package_type" a nivel RAIZ
    payload = {"shipment": {
        "quotation_id":    quotation_id,
        "rate_id":         rate_id,
        "consignment_note": _cn_code,
        "package_type":     consignment_note_packaging_code,
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
            "description": str(contenido or "Mercancía"),
        }],
    }}

    if es_int:
        _INVALID_HS = {"", "9999.99", "9999.000000", None}
        _cat_key_fb = HS_ALIASES.get(_norm(contenido or ""), _norm(contenido or ""))
        _pais_dest_upper = (pais_destino or "US").upper()
        if _cat_key_fb in HS_CODES_BY_COUNTRY:
            _hs_fallback = (hs_code or "").strip() or HS_CODES_BY_COUNTRY[_cat_key_fb].get(_pais_dest_upper, HS_CODES_BY_COUNTRY[_cat_key_fb].get("US", HS_DEFAULT))
        else:
            _hs_fallback = (hs_code or "").strip() or HS_DEFAULT_BY_COUNTRY.get(_pais_dest_upper, HS_DEFAULT)

        _prods_factura = kwargs.get("productos_factura", [])
        if _prods_factura:
            _products_parcel = []
            for _p in _prods_factura:
                _p_hs = _p.get("hs_code","") if _p.get("hs_code","") not in _INVALID_HS else _hs_fallback
                _desc = _p.get("description_en", _p.get("description_es","")) or str(contenido or "General merchandise")
                _products_parcel.append({
                    "name":              _desc[:100],
                    "sku":               _p.get("sku","SKU-1"),
                    "product_type_code": _p_hs,
                    "product_type_name": _desc[:100],
                })
        else:
            _en = (desc_en or "").strip() or DESC_EN.get(_cat_key_fb, f"General merchandise {contenido or ''}")
            _products_parcel = [{
                "name":              _en[:100],
                "sku":               "SKU-1",
                "product_type_code": _hs_fallback,
                "product_type_name": _en[:100],
            }]

        _SKY_PURPOSE_MAP = {
            "personal":   "goods",
            "commercial": "goods",
            "gift":       "gift",
            "sample":     "sample",
            "repair":     "return_of_goods",
        }
        _purpose_sky = _SKY_PURPOSE_MAP.get(str(shipment_purpose).lower(), "goods")
        _log(f"INT shipment_purpose={_purpose_sky} customs_payment_payer={customs_payment_payer}")

        # Estructura según Skydropx: consignment_note y package_type a nivel raíz
        # addresses solo llevan name/street1/company/phone/email/reference
        # products a nivel raíz del shipment
        payload_int = {"shipment": {
            "rate_id":               rate_id,
            "customs_payment_payer": customs_payment_payer,
            "shipment_purpose":      _purpose_sky,
            "printing_format":       "standard",
            "consignment_note":      _cn_code,
            "package_type":          consignment_note_packaging_code,
            "address_from": {
                "name":        str(nombre_origen),
                "street1":     str(calle_origen)[:45],
                "company":     empresa_origen or "N/A",
                "phone":       tel_origen,
                "email":       email_origen,
                "reference":   ref_origen or "-",
                "area_level3": _normalizar_colonia(colonia_origen) or "NA",
            },
            "address_to": {
                "name":        str(nombre_destino),
                "street1":     str(calle_destino)[:45],
                "company":     empresa_destino or "N/A",
                "phone":       tel_destino,
                "email":       email_destino or email_origen,
                "reference":   ref_destino or "-",
                "area_level3": _normalizar_colonia(colonia_destino) or "NA",
            },
            "parcels": [{
                "package_number":  "1",
                "package_protected": False,
                "declared_value":  round(max(float(valor_declarado or 1), 1.0), 2),
                "weight":          float(peso),
                "height":          int(alto),
                "width":           int(ancho),
                "length":          int(largo),
            }],
            "products": _products_parcel,
        }}
        _log(f"POST /shipments (EI internacional)")
        _log(f"PAYLOAD INT COMPLETO: {json.dumps(payload_int)[:2000]}")
        try:
            resp = _ei_request("POST", "/shipments", data=payload_int, timeout=90)
        except APIError as _ae:
            _log(f"ERROR SHIPMENT EI: {_ae}")
            raise
        _log(f"GUIA INT RESP: {json.dumps(resp)[:600]}")
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
    sess = _get_session()
    try:
        if sess:
            r = sess.get(label_url, timeout=30); r.raise_for_status(); return r.content
        else:
            import urllib.request
            with urllib.request.urlopen(label_url, timeout=30) as r: return r.read()
    except Exception as e: raise APIError(f"Error descargando PDF: {e}")

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
                   printing_format="letter") -> dict:
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
    _cn_code = "53131619"  # Mercancía general — fallback seguro
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
    # customs_payment_payer: EI usa "sender" o "recipient"
    _payer_ei = "recipient" if str(customs_payment_payer).lower() in ("recipient","destinatario") else "sender"

    # Valor declarado y precio por producto
    _valor = float(paquete.get("valor_declarado", 0) or 0) or 1.0
    _peso  = float(paquete.get("peso", 1.0) or 1.0)
    _largo = int(paquete.get("largo", 10) or 10)
    _ancho = int(paquete.get("ancho", 10) or 10)
    _alto  = int(paquete.get("alto",  10) or 10)

    # Productos para aduana — mínimo requerido por EI
    _INVALID_HS = {"", "9999.99", "9999.000000", None}
    _productos_factura = paquete.get("productos_factura", [])
    if _productos_factura:
        _products = []
        for _p in _productos_factura:
            _p_desc_en = (_p.get("description_en") or _desc_en or "General merchandise")[:60]
            _p_hs = _p.get("hs_code","") if _p.get("hs_code","") not in _INVALID_HS else _hs
            _products.append({
                "description":    str(_p.get("descripcion") or _p.get("description") or contenido)[:60],
                "description_en": _p_desc_en,
                "quantity":       int(_p.get("cantidad") or _p.get("quantity") or 1),
                "price":          float(_p.get("price") or _p.get("precio") or _valor),
                "weight":         float(_p.get("weight") or _p.get("peso") or _peso),
                "hs_code":        _p_hs,
                "country_code":   str(_p.get("country_code") or "MX"),
            })
    else:
        _products = [{
            "description":    str(contenido or "General merchandise")[:60],
            "description_en": str(_desc_en or "General merchandise")[:60],
            "quantity":       1,
            "price":          _valor,
            "weight":         _peso,
            "hs_code":        _hs,
            "country_code":   "MX",
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

    _log(f"EI SHIPMENT PAYLOAD: {json.dumps(payload)[:2000]}")
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
                customs_payment_payer="recipient",
                shipment_purpose="personal",
                printing_format="letter") -> dict:
    """
    Interfaz de alto nivel: recibe dicts remitente/destinatario/paquete
    y los desempaca para llamar a crear_guia().
    Usa Skydropx para todos los envíos (nacional e internacional).
    """
    import datetime, random

    pais_dest = destinatario.get("pais","MX")
    pais_orig = remitente.get("pais","MX")
    es_int = _es_internacional(pais_orig, pais_dest)

    # Siempre Skydropx — EI desactivado
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
        valor_declarado=paquete.get("valor_declarado", 1.0),
        hs_code=paquete.get("hs_code", ""),
        desc_en=paquete.get("desc_en", ""),
        consignment_note_class_code=paquete.get("consignment_note_class_code", "53131619"),
        consignment_note_packaging_code=paquete.get("consignment_note_packaging_code", "4G"),
        customs_payment_payer=customs_payment_payer,
        shipment_purpose=shipment_purpose,
        productos_factura=paquete.get("productos_factura", []),
    )

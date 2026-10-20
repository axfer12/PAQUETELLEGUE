"""
fix_cartaporte.py v9 — Parche Carta Porte SAT para API PRO de Skydropx
Garantiza que consignment_note y package_type estén a nivel RAÍZ del shipment.
(API PRO: pro.skydropx.com/api/v1)
"""

_CONSIGNMENT_NOTE_DEFAULT = "53131600"
_PACKAGE_TYPE_DEFAULT     = "4G"   # Caja cartón — default seguro

def _parchear_api_proveedor():
    try:
        from modules import api_proveedor as _api
    except ImportError:
        return
    if getattr(_api, "_fix_cartaporte_aplicado", False):
        return
    _request_original = _api._request

    def _request_parchado(method, endpoint, data=None, **kwargs):
        if method.upper() == "POST" and "/shipments" in endpoint and data:
            shipment = data.get("shipment", {})
            # Inyectar a nivel RAÍZ — API PRO usa "consignment_note" y "package_type"
            if not shipment.get("consignment_note"):
                shipment["consignment_note"] = _CONSIGNMENT_NOTE_DEFAULT
            if not shipment.get("package_type"):
                shipment["package_type"] = _PACKAGE_TYPE_DEFAULT
            # Limpiar parcels (no deben tener estos campos)
            for parcel in shipment.get("parcels", []):
                parcel.pop("consignment_note", None)
                parcel.pop("package_type", None)
            # Limpiar nombres alternativos a nivel raíz
            shipment.pop("consignment_note_class_code", None)
            shipment.pop("consignment_note_packaging_code", None)
            try:
                _api._log(f"[fix v9] consignment_note={shipment.get('consignment_note')} package_type={shipment.get('package_type')}")
            except Exception:
                pass
        return _request_original(method, endpoint, data=data, **kwargs)

    _api._request = _request_parchado
    _api._fix_cartaporte_aplicado = True

_parchear_api_proveedor()

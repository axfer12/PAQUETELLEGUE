"""
webhook.py — Receptor de webhooks de Skydropx
Cuando una guía tardó en generarse, Skydropx avisa aquí automáticamente.
"""
import hmac, hashlib, json, logging
from flask import Blueprint, request, jsonify, current_app
from ..modules import database as db

bp = Blueprint("webhook", __name__, url_prefix="/webhook")
logger = logging.getLogger(__name__)


def _verificar_firma(body_bytes: bytes, auth_header: str, secret: str) -> bool:
    """Verifica la firma HMAC-SHA512 de Skydropx."""
    if not auth_header or not secret:
        return True  # Sin secret configurado, aceptar todo (desarrollo)
    try:
        firma_recibida = auth_header.replace("HMAC ", "").strip()
        firma_esperada = hmac.new(
            secret.encode(), body_bytes, hashlib.sha512
        ).hexdigest()
        return hmac.compare_digest(firma_recibida, firma_esperada)
    except Exception:
        return False


@bp.route("/skydropx", methods=["POST"])
def skydropx_webhook():
    """
    Endpoint que Skydropx llama cuando hay cambio de estatus en un envío.
    Registrar en Skydropx Pro: Settings → Webhooks → URL: https://paquetellegue.onrender.com/webhook/skydropx
    """
    body_bytes = request.get_data()
    auth_header = request.headers.get("Authorization", "")
    secret = current_app.config.get("SKYDROPX_WEBHOOK_SECRET", "")

    # Verificar firma
    if not _verificar_firma(body_bytes, auth_header, secret):
        logger.warning("Webhook Skydropx: firma inválida")
        return jsonify({"error": "Unauthorized"}), 401

    try:
        evento = json.loads(body_bytes)
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400

    logger.info(f"Webhook Skydropx recibido: {json.dumps(evento)[:300]}")

    # Extraer datos del evento
    data = evento.get("data", {})
    attrs = data.get("attributes", {})
    tipo = data.get("type", "")

    # Evento de shipment (guía generada o actualizada)
    shipment_id = str(data.get("id", ""))
    status = attrs.get("status", "") or attrs.get("workflow_status", "")
    tracking = attrs.get("tracking_number", "") or attrs.get("number", "")
    label_url = attrs.get("label_url", "") or attrs.get("label", {}).get("url", "") if isinstance(attrs.get("label"), dict) else attrs.get("label_url", "")

    # También puede venir en formato v2
    if not shipment_id and "shipment_id" in attrs:
        shipment_id = str(attrs["shipment_id"])
    if not tracking and "tracking" in attrs:
        tracking = attrs["tracking"]

    logger.info(f"Skydropx webhook: shipment_id={shipment_id} status={status} tracking={tracking}")

    if not shipment_id:
        return jsonify({"ok": True, "msg": "Sin shipment_id, ignorado"}), 200

    # Buscar guía pendiente en BD con este shipment_id
    try:
        conn, cur, ph = db.get_conn()
        cur.execute(
            f"SELECT id, estatus, numero_guia FROM guias WHERE shipment_id_proveedor={ph}",
            (shipment_id,)
        )
        row = cur.fetchone()

        if not row:
            logger.info(f"Webhook: shipment {shipment_id} no encontrado en BD")
            return jsonify({"ok": True, "msg": "Shipment no registrado localmente"}), 200

        guia_id = row[0]
        estatus_actual = row[1]
        numero_guia = row[2]

        updates = {}

        # Si hay tracking number nuevo, actualizar
        if tracking and (not numero_guia or numero_guia == "SIN_NUM"):
            updates["numero_guia"] = tracking
            updates["numero_rastreo"] = tracking

        # Si hay label URL, actualizar
        if label_url:
            updates["label_url"] = label_url

        # Mapear estatus de Skydropx a estatus local
        status_map = {
            "WAITING":    "en_espera",
            "GENERATED":  "activa",
            "CREATED":    "activa",
            "PICKED_UP":  "en_transito",
            "IN_TRANSIT": "en_transito",
            "LAST_MILE":  "en_transito",
            "DELIVERED":  "entregada",
            "EXCEPTION":  "excepcion",
            "CANCELLED":  "cancelada",
        }
        nuevo_estatus = status_map.get(status.upper(), estatus_actual)

        if nuevo_estatus and nuevo_estatus != estatus_actual:
            updates["estatus"] = nuevo_estatus
            updates["status"] = nuevo_estatus

        # Aplicar actualizaciones
        if updates:
            sets = ", ".join([f"{k}={ph}" for k in updates.keys()])
            vals = list(updates.values()) + [guia_id]
            cur.execute(f"UPDATE guias SET {sets} WHERE id={ph}", vals)
            conn.commit()
            logger.info(f"Guía {guia_id} actualizada via webhook: {updates}")

        return jsonify({"ok": True, "guia_id": guia_id, "updates": updates}), 200

    except Exception as e:
        logger.error(f"Error procesando webhook Skydropx: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/skydropx/test", methods=["GET"])
def webhook_test():
    """Endpoint para verificar que el webhook está activo."""
    return jsonify({
        "ok": True,
        "msg": "Webhook PAQUETELLEGUE activo ✅",
        "url": "https://paquetellegue.onrender.com/webhook/skydropx"
    }), 200

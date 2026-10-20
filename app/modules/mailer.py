"""
Módulo de envío de correos — API Resend (https://resend.com).
Render bloquea SMTP (puertos 465 y 587), por eso se usa HTTP.

Variables de entorno necesarias:
  RESEND_API_KEY  API key de Resend (empieza con re_...)
  MAIL_FROM_EMAIL correo remitente verificado en Resend (ej: noreply@paquetellegue.shop)
                  o usa el dominio sandbox: onboarding@resend.dev (solo envía a tu propio email)
  MAIL_FROM       nombre que aparece (default: PAQUETELLEGUE)
  APP_URL         URL base del sistema, ej: https://paquetellegue.shop
"""
import os
import json
import urllib.request
import urllib.error

RESEND_API_KEY  = os.environ.get("RESEND_API_KEY", "")
MAIL_FROM_EMAIL = os.environ.get("MAIL_FROM_EMAIL", "onboarding@resend.dev")
MAIL_FROM       = os.environ.get("MAIL_FROM", "PAQUETELLEGUE")
APP_URL         = os.environ.get("APP_URL", "https://paquetellegue.shop").rstrip("/")


def _send(to: str, subject: str, html: str):
    """Envía un correo HTML vía API de Resend usando requests si está disponible."""
    payload = {
        "from":    f"{MAIL_FROM} <{MAIL_FROM_EMAIL}>",
        "to":      [to],
        "subject": subject,
        "html":    html,
    }
    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type":  "application/json",
    }

    # Intentar con requests (maneja mejor proxies y TLS)
    try:
        import requests as _req
        r = _req.post("https://api.resend.com/emails",
                      json=payload, headers=headers, timeout=15)
        print(f"[MAIL] Resend status={r.status_code} body={r.text[:200]}")
        if not r.ok:
            raise Exception(f"Resend error {r.status_code}: {r.text}")
        return r.json()
    except ImportError:
        pass

    # Fallback: urllib
    body_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=body_bytes, headers=headers, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            resp_body = r.read()
            print(f"[MAIL OK] Resend: {resp_body.decode('utf-8', errors='replace')[:200]}")
            return json.loads(resp_body)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"[MAIL ERROR] code={e.code} body={body}")
        raise Exception(f"Resend error {e.code}: {body}")
    except Exception as e:
        print(f"[MAIL ERROR] {type(e).__name__}: {e}")
        raise


def enviar_reset_password(to: str, nombre: str, token: str):
    """Envía correo con el enlace para restablecer contraseña."""
    link = f"{APP_URL}/reset-password/{token}"
    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head><meta charset="UTF-8"></head>
    <body style="margin:0;padding:0;background:#0d0d0d;font-family:Arial,sans-serif">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr><td align="center" style="padding:40px 20px">
          <table width="480" cellpadding="0" cellspacing="0"
                 style="background:#1a1a1a;border:1px solid #3a3020;border-radius:12px;overflow:hidden">
            <tr>
              <td style="background:#C9A84C;padding:24px;text-align:center">
                <span style="font-size:28px;font-weight:900;color:#000;
                             letter-spacing:2px;font-family:Arial,sans-serif">PAQUETELLEGUE</span>
              </td>
            </tr>
            <tr>
              <td style="padding:32px 36px">
                <h2 style="color:#F5E6C8;margin:0 0 12px">Restablece tu contraseña</h2>
                <p style="color:#9A8A6A;font-size:14px;margin:0 0 24px">
                  Hola <strong style="color:#F5E6C8">{nombre}</strong>,<br><br>
                  Recibimos una solicitud para restablecer la contraseña de tu cuenta.<br>
                  Haz clic en el botón de abajo. El enlace expira en <strong style="color:#C9A84C">1 hora</strong>.
                </p>
                <table cellpadding="0" cellspacing="0" width="100%">
                  <tr><td align="center">
                    <a href="{link}"
                       style="display:inline-block;background:#C9A84C;color:#000;
                              text-decoration:none;padding:14px 36px;border-radius:8px;
                              font-weight:700;font-size:15px;letter-spacing:1px">
                      RESTABLECER CONTRASEÑA →
                    </a>
                  </td></tr>
                </table>
                <p style="color:#6a5a4a;font-size:12px;margin:24px 0 0;word-break:break-all">
                  Si el botón no funciona, copia este enlace:<br>
                  <a href="{link}" style="color:#C9A84C">{link}</a>
                </p>
                <p style="color:#4a3a2a;font-size:11px;margin:16px 0 0;border-top:1px solid #3a3020;padding-top:16px">
                  Si no solicitaste este cambio, ignora este correo. Tu contraseña no cambiará.
                </p>
              </td>
            </tr>
          </table>
        </td></tr>
      </table>
    </body>
    </html>
    """
    _send(to, "Restablece tu contraseña — PAQUETELLEGUE", html)


def esta_configurado() -> bool:
    """Devuelve True si la API key de Resend está configurada."""
    return bool(RESEND_API_KEY)

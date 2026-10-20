"""
Módulo de envío de correos — API SendGrid (https://sendgrid.com).
Render bloquea SMTP; SendGrid usa HTTP y no tiene el bloqueo de Cloudflare.

Variables de entorno necesarias:
  SENDGRID_API_KEY  API key de SendGrid (empieza con SG.)
  MAIL_FROM_EMAIL   correo remitente verificado en SendGrid (ej: noreply@paquetellegue.shop)
  MAIL_FROM         nombre que aparece (default: PAQUETELLEGUE)
  APP_URL           URL base del sistema, ej: https://paquetellegue.shop
"""
import os
import json
import urllib.request
import urllib.error

SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
MAIL_FROM_EMAIL  = os.environ.get("MAIL_FROM_EMAIL", "")
MAIL_FROM        = os.environ.get("MAIL_FROM", "PAQUETELLEGUE")
APP_URL          = os.environ.get("APP_URL", "https://paquetellegue.shop").rstrip("/")

print(f"[MAILER INIT] SG_KEY_len={len(SENDGRID_API_KEY)} FROM_EMAIL={MAIL_FROM_EMAIL!r}")


def _send(to: str, subject: str, html: str):
    """Envía un correo HTML vía API de SendGrid."""
    api_key    = os.environ.get("SENDGRID_API_KEY", "").strip()
    from_email = os.environ.get("MAIL_FROM_EMAIL", "").strip()
    from_name  = os.environ.get("MAIL_FROM", MAIL_FROM)
    payload = json.dumps({
        "personalizations": [{"to": [{"email": to}]}],
        "from": {"email": from_email, "name": from_name},
        "subject": subject,
        "content": [{"type": "text/html", "value": html}],
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.sendgrid.com/v3/mail/send",
        data    = payload,
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type":  "application/json",
        },
        method = "POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            print(f"[MAIL OK] SendGrid status={r.status}")
            return True
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"[MAIL ERROR] SendGrid code={e.code} body={body}")
        raise Exception(f"SendGrid error {e.code}: {body}")
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
                <h2 style="color:#F5E6C8;margin:0 0 12px">Restablece tu contrase&#241;a</h2>
                <p style="color:#9A8A6A;font-size:14px;margin:0 0 24px">
                  Hola <strong style="color:#F5E6C8">{nombre}</strong>,<br><br>
                  Recibimos una solicitud para restablecer la contrase&#241;a de tu cuenta.<br>
                  Haz clic en el bot&#243;n de abajo. El enlace expira en
                  <strong style="color:#C9A84C">1 hora</strong>.
                </p>
                <table cellpadding="0" cellspacing="0" width="100%">
                  <tr><td align="center">
                    <a href="{link}"
                       style="display:inline-block;background:#C9A84C;color:#000;
                              text-decoration:none;padding:14px 36px;border-radius:8px;
                              font-weight:700;font-size:15px;letter-spacing:1px">
                      RESTABLECER CONTRASE&#209;A &#8594;
                    </a>
                  </td></tr>
                </table>
                <p style="color:#6a5a4a;font-size:12px;margin:24px 0 0;word-break:break-all">
                  Si el bot&#243;n no funciona, copia este enlace:<br>
                  <a href="{link}" style="color:#C9A84C">{link}</a>
                </p>
                <p style="color:#4a3a2a;font-size:11px;margin:16px 0 0;
                          border-top:1px solid #3a3020;padding-top:16px">
                  Si no solicitaste este cambio, ignora este correo.
                  Tu contrase&#241;a no cambiar&#225;.
                </p>
              </td>
            </tr>
          </table>
        </td></tr>
      </table>
    </body>
    </html>
    """
    _send(to, "Restablece tu contrasena - PAQUETELLEGUE", html)


def esta_configurado() -> bool:
    """Devuelve True si la API key de SendGrid y el remitente están configurados."""
    key   = os.environ.get("SENDGRID_API_KEY", "").strip()
    email = os.environ.get("MAIL_FROM_EMAIL", "").strip()
    return bool(key and email)

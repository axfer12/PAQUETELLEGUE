"""
Módulo de envío de correos — SMTP (Gmail por defecto).
Variables de entorno necesarias:
  MAIL_SERVER   (default: smtp.gmail.com)
  MAIL_PORT     (default: 587)
  MAIL_USER     correo remitente
  MAIL_PASSWORD contraseña de aplicación (App Password de Gmail)
  MAIL_FROM     nombre que aparece como remitente (default: PAQUETELLEGUE)
  APP_URL       URL base del sistema, ej: https://paquetellegue.shop
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

MAIL_SERVER   = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
MAIL_PORT     = int(os.environ.get("MAIL_PORT", "465"))
MAIL_USER     = os.environ.get("MAIL_USER", "")
MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
MAIL_FROM     = os.environ.get("MAIL_FROM", "PAQUETELLEGUE")
APP_URL       = os.environ.get("APP_URL", "https://paquetellegue.shop").rstrip("/")


def _send(to: str, subject: str, html: str):
    """Envía un correo HTML usando SSL (puerto 465). Lanza excepción si falla."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"{MAIL_FROM} <{MAIL_USER}>"
    msg["To"]      = to
    msg.attach(MIMEText(html, "html", "utf-8"))

    # Puerto 465 = SSL directo (SMTP_SSL), no STARTTLS
    # Render bloquea el puerto 587; el 465 sí pasa su firewall
    with smtplib.SMTP_SSL(MAIL_SERVER, MAIL_PORT) as srv:
        srv.login(MAIL_USER, MAIL_PASSWORD)
        srv.sendmail(MAIL_USER, to, msg.as_string())


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
    """Devuelve True si las variables de correo están configuradas."""
    return bool(MAIL_USER and MAIL_PASSWORD)

"""SMTP email sender."""
from __future__ import annotations

import smtplib
from email.message import EmailMessage


def send_email(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    secure: str,
    from_email: str,
    from_name: str,
    to_email: str,
    subject: str,
    html: str,
    text: str,
) -> tuple[bool, str | None]:
    if not host or not port:
        return False, "missing_smtp"
    if not from_email:
        return False, "missing_from"
    msg = EmailMessage()
    msg["Subject"] = subject or "Teachbase AI"
    msg["From"] = f"{from_name} <{from_email}>" if from_name else from_email
    msg["To"] = to_email
    if text:
        msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")
    try:
        if secure == "ssl":
            server = smtplib.SMTP_SSL(host, port, timeout=10)
        else:
            server = smtplib.SMTP(host, port, timeout=10)
        try:
            if secure == "tls":
                server.starttls()
            if username:
                server.login(username, password or "")
            server.send_message(msg)
        finally:
            server.quit()
    except Exception as e:
        return False, str(e)[:200]
    return True, None

"""Email Sender Module.

Sends the digest via SMTP using user-provided credentials, with one retry on
failure and a console fallback so a delivery failure never silently loses the
digest.
"""
from __future__ import annotations

import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .config_loader import EmailConfig
from .digest_builder import Digest

log = logging.getLogger("digest.email")


class EmailError(Exception):
    """Raised when the digest could not be sent after retrying."""


def _build_message(cfg: EmailConfig, digest: Digest) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = digest.subject
    msg["From"] = cfg.from_address or cfg.address
    msg["To"] = cfg.address
    msg.attach(MIMEText(digest.text, "plain", "utf-8"))
    msg.attach(MIMEText(digest.html, "html", "utf-8"))
    return msg


def _send_once(cfg: EmailConfig, msg: MIMEMultipart) -> None:
    if cfg.use_tls:
        context = ssl.create_default_context()
        with smtplib.SMTP(cfg.smtp_server, cfg.smtp_port, timeout=60) as server:
            server.starttls(context=context)
            if cfg.smtp_password:
                server.login(cfg.smtp_username or cfg.address, cfg.smtp_password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(cfg.smtp_server, cfg.smtp_port, timeout=60) as server:
            if cfg.smtp_password:
                server.login(cfg.smtp_username or cfg.address, cfg.smtp_password)
            server.send_message(msg)


def send_digest(cfg: EmailConfig, digest: Digest, dry_run: bool = False) -> bool:
    """Send the digest. Returns True on success.

    On ``dry_run`` the digest is printed to the console instead of sent.
    Retries once on SMTP failure; on final failure logs the error and prints a
    console fallback, then raises ``EmailError``.
    """
    if dry_run:
        log.info("[dry-run] Would send '%s' to %s", digest.subject, cfg.address)
        print("=" * 70)
        print(f"TO: {cfg.address}\nSUBJECT: {digest.subject}\n")
        print(digest.text)
        print("=" * 70)
        return True

    msg = _build_message(cfg, digest)
    last_exc: Exception | None = None
    for attempt in (1, 2):  # send once, retry once
        try:
            _send_once(cfg, msg)
            log.info("Digest sent to %s (subject: %s)", cfg.address, digest.subject)
            return True
        except (smtplib.SMTPException, OSError) as exc:
            last_exc = exc
            log.warning("SMTP send attempt %d failed: %s", attempt, exc)

    log.error("Failed to send digest after retry: %s", last_exc)
    print("\n" + "!" * 70)
    print("EMAIL DELIVERY FAILED — digest could not be sent.")
    print(f"Reason: {last_exc}")
    print(f"Subject: {digest.subject}")
    print("The digest content is available above / in the logs.")
    print("!" * 70 + "\n")
    raise EmailError(str(last_exc)) from last_exc

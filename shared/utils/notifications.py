import json
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger("naso-notifications")


class NotificationService:
    """
    Servizio per l'invio di Alert e Notifiche (#9).
    """

    @staticmethod
    def send_breach_alert(recipient_email, identity_identifier, leak_source, severity, is_priority=False):
        """
        Invia un'email di alert per un'identità compromessa.
        """
        smtp_host = os.getenv("SMTP_HOST", "smtp.naso.local")
        smtp_port = int(os.getenv("SMTP_PORT", 587))
        smtp_user = os.getenv("SMTP_USER", "notifications@naso.local")
        smtp_pass = os.getenv("SMTP_PASSWORD", "change_me_rigorously")
        smtp_from = os.getenv("SMTP_FROM", "naso-engine@naso.local")

        prefix = "[NASO PRIORITY ALERT]" if is_priority else "[NASO CRITICAL ALERT]"
        subject = f"{prefix} Identity Compromised: {identity_identifier}"

        header_color = "#f00" if not is_priority else "#ffea00"  # Yellow for priority/VIP
        header_text = "BREACH DETECTED" if not is_priority else "VIP ASSET COMPROMISED"

        body = f"""
        <html>
        <body style="font-family: monospace; background-color: #000; color: #0f0; padding: 20px;">
            <h1 style="color: {header_color}; border-bottom: 2px solid {header_color};">[NASO FORENSIC ENGINE] - {header_text}</h1>
            <p style="color: {"#fff" if is_priority else "#0f0"}; font-size: 1.2em;"><strong>Identity:</strong> {identity_identifier}</p>
            <p><strong>Source:</strong> {leak_source}</p>
            <p><strong>Severity:</strong> {severity}/100</p>
            {'<p style="color: #ffea00; font-weight: bold;">[!] ATTENZIONE: Questa identità è marcata come PROTETTA (VIP Asset).</p>' if is_priority else ""}
            <hr style="border: 1px solid #333;">
            <p style="color: #888; font-size: 0.8em;">This is an automated forensic alert. Access the dashboard for full analysis.</p>
        </body>
        </html>
        """

        msg = MIMEMultipart()
        msg["From"] = smtp_from
        msg["To"] = recipient_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html"))

        try:
            # Modalità Dry-Run per testing e DevOps
            if os.getenv("NASO_DRY_RUN", "0") == "1" or "naso.local" in smtp_host:
                logger.info(
                    f"[DRY-RUN] Alert successfully intercepted for {recipient_email}. Target: {identity_identifier}"
                )
                return True

            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)

            logger.info(
                json.dumps(
                    {
                        "event": "notification_sent",
                        "recipient": recipient_email,
                        "identity": identity_identifier,
                        "status": "success",
                    }
                )
            )
            return True
        except Exception as e:
            logger.error(json.dumps({"event": "notification_failed", "recipient": recipient_email, "error": str(e)}))
            return False

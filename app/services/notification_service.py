"""Local SMTP email notifications (no external API)."""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app



def _send_email(to_email: str, subject: str, body_text: str):
    """Send email via local SMTP."""
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@surpluslink.local')
        msg['To'] = to_email
        msg.attach(MIMEText(body_text, 'plain'))

        with smtplib.SMTP(
            current_app.config.get('MAIL_SERVER', 'localhost'),
            current_app.config.get('MAIL_PORT', 1025),
            timeout=5
        ) as server:
            server.send_message(msg)
    except Exception as e:
        current_app.logger.warning(f"Email send failed (local SMTP may be off): {e}")


def notify_food_request_accepted(donor_email: str, ngo_name: str, food_type: str):
    """Notify donor when NGO accepts their food post."""
    subject = "SurplusLink: Your food has been accepted!"
    body = f"""
Hello,

Great news! {ngo_name} has accepted your food donation ({food_type}).

You will be notified when delivery is completed.

- SurplusLink
"""
    _send_email(donor_email, subject, body.strip())


def notify_delivery_started(donor_email: str, ngo_email: str, food_type: str):
    """Notify both parties when delivery has started."""
    subject = "SurplusLink: Delivery has started"
    body_donor = f"""
Hello,

Delivery of your donated food ({food_type}) has started. Track progress on your dashboard.

- SurplusLink
"""
    body_ngo = f"""
Hello,

Delivery of {food_type} has started. Track progress on your dashboard.

- SurplusLink
"""
    _send_email(donor_email, subject, body_donor.strip())
    _send_email(ngo_email, subject, body_ngo.strip())


def notify_delivery_completed(donor_email: str, ngo_email: str, food_type: str):
    """Notify both donor and NGO when delivery is completed."""
    subject = "SurplusLink: Delivery completed successfully"
    body = f"""
Hello,

The delivery of {food_type} has been completed successfully. Please rate each other on the platform.

- SurplusLink
"""
    _send_email(donor_email, subject, body.strip())
    _send_email(ngo_email, subject, body.strip())

"""Send the approved or denied decision to the member.

Default is outbox mode: the message is written to outbox/ instead of being sent, so
cloning this repo and clicking Approve cannot email a stranger. Configure SMTP in
.env to send for real.
"""
import smtplib
import subprocess
from email.message import EmailMessage
from pathlib import Path

import agents
import db
from config import (ROOT, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_FROM,
                    SMTP_PASSWORD, SMTP_KEYCHAIN_SERVICE)

OUTBOX = ROOT / "outbox"

NEXT_STEPS = {
    "approved": ("The credit will appear on your account within 5 business days. "
                 "We will write again when the investigation closes."),
    "denied": ("If you disagree with this outcome you can appeal within 60 days, and you "
               "may request copies of the documents we relied on."),
}


def _password():
    if SMTP_PASSWORD:
        return SMTP_PASSWORD
    if not SMTP_KEYCHAIN_SERVICE:
        return None
    try:
        return subprocess.run(
            ["security", "find-generic-password", "-a", SMTP_USER,
             "-s", SMTP_KEYCHAIN_SERVICE, "-w"],
            check=True, capture_output=True, text=True).stdout.strip().replace(" ", "")
    except Exception:
        return None


def build(dispute_id: int) -> EmailMessage:
    d = db.get_dispute(dispute_id)
    dec = db.latest_decision(dispute_id)
    if not dec:
        raise ValueError("no decision recorded yet")

    # Defence in depth: never let internal triage notes reach a member, even if an
    # older or hand-edited draft still carries them.
    final = dec["final_body"] or ""
    if agents.MEMBER_MARKER in final:
        final = final.split(agents.MEMBER_MARKER, 1)[1].strip()

    verdict = "resolved in your favour" if dec["decision"] == "approved" else "closed"
    msg = EmailMessage()
    msg["Subject"] = f"Your dispute D-{dispute_id} has been {verdict}"
    msg["From"] = SMTP_FROM or "disputes@example.com"
    msg["To"] = d["member_email"]
    body = (f"{final}\n\n"
            f"Next steps: {NEXT_STEPS[dec['decision']]}\n\n"
            f"Case reference: D-{dispute_id}\n"
            f"Disputed amount: ${d['amount_cents']/100:,.2f} at {d['merchant']}\n")
    msg.set_content(body)
    return msg


def send_decision(dispute_id: int) -> tuple[bool, str]:
    """Returns (sent_for_real, detail). Never raises: a failed send must not lose the decision."""
    try:
        msg = build(dispute_id)
    except Exception as e:
        return False, f"could not build the message: {e}"

    password = _password()
    if not (SMTP_HOST and SMTP_USER and password):
        OUTBOX.mkdir(exist_ok=True)
        path = OUTBOX / f"D-{dispute_id}.eml"
        path.write_bytes(bytes(msg))
        db.log(dispute_id, "system", "decision written to the outbox",
               f"{path.name} -> {msg['To']} (SMTP not configured, nothing was sent)")
        return False, f"written to outbox/{path.name}"

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as s:
            s.login(SMTP_USER, password)
            s.send_message(msg)
        db.log(dispute_id, "system", "decision emailed to the member", msg["To"])
        return True, f"emailed to {msg['To']}"
    except Exception as e:
        db.log(dispute_id, "system", "email failed", f"{type(e).__name__}: {e}")
        return False, f"send failed: {type(e).__name__}"

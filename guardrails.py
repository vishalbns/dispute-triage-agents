"""Two layers: local deterministic checks, and Bedrock Guardrails when configured.

The local layer always runs, so the demo is safe without AWS. The Bedrock layer is
the one you would point at in an audit.
"""
import re
from config import GUARDRAIL_ID, GUARDRAIL_VERSION, AWS_REGION

CARD = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
ACCT = re.compile(r"\b(?:account|acct)[^\d]{0,10}(\d{6,})\b", re.I)


def redact(text: str) -> tuple[str, list[str]]:
    """Mask anything that must never reach a model, a log or a member letter."""
    found = []
    def card_sub(m):
        digits = re.sub(r"\D", "", m.group(0))
        if len(digits) < 13:
            return m.group(0)
        found.append("card_number")
        return f"card ending {digits[-4:]}"
    out = CARD.sub(card_sub, text)
    if SSN.search(out):
        found.append("ssn"); out = SSN.sub("[ssn removed]", out)
    if ACCT.search(out):
        found.append("account_number"); out = ACCT.sub("account [removed]", out)
    return out, found


def bedrock_screen(text: str, source: str) -> tuple[bool, str]:
    """Independent check with Bedrock Guardrails. Returns (allowed, text_or_reason)."""
    if not GUARDRAIL_ID:
        return True, text
    import boto3
    client = boto3.client("bedrock-runtime", region_name=AWS_REGION)
    r = client.apply_guardrail(
        guardrailIdentifier=GUARDRAIL_ID,
        guardrailVersion=GUARDRAIL_VERSION,
        source=source,                       # "INPUT" or "OUTPUT"
        content=[{"text": {"text": text}}],
    )
    if r.get("action") == "GUARDRAIL_INTERVENED":
        return False, r["outputs"][0]["text"]
    return True, text


def screen_input(text: str):
    clean, found = redact(text)
    ok, result = bedrock_screen(clean, "INPUT")
    return ok, result, found


def screen_output(text: str):
    clean, found = redact(text)
    ok, result = bedrock_screen(clean, "OUTPUT")
    return ok, result, found

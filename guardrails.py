"""Two layers: local deterministic checks, and Bedrock Guardrails when configured.

The local layer always runs, so the demo is safe without AWS. The Bedrock layer is
the one you would point at in an audit.
"""
import re
from config import GUARDRAIL_ID, GUARDRAIL_VERSION, AWS_REGION

CARD = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
SSN_BARE = re.compile(r"\b(?:ssn|social security)\b[^\d]{0,30}(\d{9})\b", re.I)
# Keyword-anchored, with a generous window: "account number is 9342853" puts 11
# characters between the keyword and the digits, which a tight window misses.
KEYED = re.compile(
    r"\b(?:account|acct|a/c|routing|aba|iban|sort\s*code|member\s*number|card)\b[^\d]{0,30}(\d{5,})\b",
    re.I)
# Backstop: any run of 7 or more digits in free text. Word boundaries keep ids like
# txn_88213 and amounts like 240.00 intact, and a long bare number a member types is
# almost always an account, card, routing or phone number.
LONG_DIGITS = re.compile(r"\b\d{7,}\b")


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
    for pattern, label, repl in (
        (SSN,      "ssn",            "[ssn removed]"),
        (SSN_BARE, "ssn",            "SSN [removed]"),
        (KEYED,    "account_number", "account [removed]"),
    ):
        if pattern.search(out):
            found.append(label)
            out = pattern.sub(repl, out)
    if LONG_DIGITS.search(out):
        found.append("long_number")
        out = LONG_DIGITS.sub("[number removed]", out)
    return out, sorted(set(found))


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

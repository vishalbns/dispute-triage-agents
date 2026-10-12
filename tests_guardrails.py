"""Redaction tests. Run: python tests_guardrails.py

These exist because a tight keyword window let a real account number through:
"account number is 9342853" puts 11 characters between the keyword and the
digits, and the window only allowed 10. Every case below is a regression.
"""
import guardrails

MUST_MASK = [
    "My SSN is 123-45-6789 and account number is 9342853.",
    "account number 1231231",
    "my acct is 44829301 please check",
    "routing 021000021 and a/c 5567281",
    "Card 4111 1111 1111 1111 was charged",
    "ssn 123456789",
    "member number: 8847211",
    "here is my account #, it is 55512340",
    "the number on my card, which is 4111111111111111, is wrong",
]

MUST_SURVIVE = [
    "The $240.00 charge at NORTHGATE on txn_88213 card ending 4417",
    "Loan ln_51720, premium $960.00 charged 2026-09-02",
    "I was charged twice on 10/02 for 45.99",
    "Dispute filed under Reg E within 60 days",
]


def main() -> int:
    failures = 0
    for text in MUST_MASK:
        out, found = guardrails.redact(text)
        if not found:
            print(f"FAIL (not masked): {text}")
            failures += 1
    for text in MUST_SURVIVE:
        out, found = guardrails.redact(text)
        if out != text:
            print(f"FAIL (over-masked): {text}\n            became: {out}")
            failures += 1
    total = len(MUST_MASK) + len(MUST_SURVIVE)
    print(f"{total - failures}/{total} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

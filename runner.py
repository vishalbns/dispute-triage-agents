"""Run one dispute through the agents and leave a draft for a human.

This is the only place that orchestrates. The Streamlit apps never call an agent
directly, which is what lets the same function run locally, in the worker, or
inside AgentCore Runtime without change.
"""
import json
import re

import agents
import db
import guardrails

EXTRACT_PROMPT = """From the case note below, return ONLY a JSON object, no prose:
{"recommendation": "approve" | "deny" | "more_info" | "escalate_fraud",
 "amount_cents": <integer, 0 if no credit is being requested>,
 "citations": [<policy tags mentioned, e.g. "P-001 1.3">]}

Case note:
"""


def _extract(model, text: str) -> dict:
    """Second, separate call: generate the letter first, classify it after."""
    from strands import Agent
    classifier = Agent(model=model, system_prompt="You return only valid JSON. No commentary.")
    raw = str(classifier(EXTRACT_PROMPT + text))
    match = re.search(r"\{.*\}", raw, re.S)
    if not match:
        return {"recommendation": "more_info", "amount_cents": 0, "citations": []}
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"recommendation": "more_info", "amount_cents": 0, "citations": []}
    return {
        "recommendation": str(data.get("recommendation", "more_info")),
        "amount_cents": int(data.get("amount_cents") or 0),
        "citations": [str(c) for c in (data.get("citations") or [])],
    }


def process(dispute_id: int) -> str:
    d = db.get_dispute(dispute_id)
    if d is None:
        raise ValueError(f"no dispute {dispute_id}")

    token = agents.CURRENT.set(dispute_id)
    sources_token = agents.SOURCES.set([])
    try:
        db.set_status(dispute_id, "processing")
        db.log(dispute_id, "system", "triage started")

        member_text = f"{d['reason']}. {d['description'] or ''}".strip()
        ok, safe_text, found = guardrails.screen_input(member_text)
        if found:
            db.log(dispute_id, "guardrail", "redacted sensitive data from member text",
                   ", ".join(sorted(set(found))))
        if not ok:
            db.log(dispute_id, "guardrail", "input blocked", safe_text)
            db.set_status(dispute_id, "awaiting_approval")
            db.save_draft(dispute_id, safe_text, "more_info", 0, [])
            return safe_text

        model = agents.build_model()
        policy_agent = agents.make_policy_agent(model)
        case_agent = agents.make_case_agent(model, policy_agent)

        case_type = d["case_type"] if "case_type" in d.keys() else "card_dispute"
        if case_type == "insurance_tracking":
            subject = (f"Loan: {d['txn_id']}\n"
                       f"Lender-placed premium charged: ${d['amount_cents']/100:,.2f}")
        else:
            subject = (f"Transaction: {d['txn_id']} for ${d['amount_cents']/100:,.2f} "
                       f"at {d['merchant'] or 'unknown merchant'}")
        prompt = (
            f"Case reference: D-{dispute_id}\n"
            f"Case type: {case_type}\n"
            f"Member: {d['member_name']}\n"
            f"{subject}\n"
            f"Complaint: {d['reason']}\n"
            f"Member says: {safe_text}\n\n"
            "Triage this case."
        )
        db.log(dispute_id, "case_agent", "started", prompt)
        answer = str(case_agent(prompt))

        ok, safe_answer, found = guardrails.screen_output(answer)
        if found:
            db.log(dispute_id, "guardrail", "redacted sensitive data from the draft",
                   ", ".join(sorted(set(found))))
        if not ok:
            db.log(dispute_id, "guardrail", "output blocked, draft withheld", safe_answer)
            safe_answer = "The draft was blocked by the output guardrail and needs manual handling."

        # The agent returns internal notes, a marker, then the member letter. Keep them apart:
        # the reviewer sees the notes in the trace, the member only ever sees the letter.
        if agents.MEMBER_MARKER in safe_answer:
            notes, member_msg = safe_answer.split(agents.MEMBER_MARKER, 1)
            db.log(dispute_id, "case_agent", "internal triage notes", notes.strip())
            member_msg = member_msg.strip()
        else:
            member_msg = safe_answer

        summary = _extract(model, safe_answer)
        # Cite what was actually retrieved, not what the model recalls citing.
        retrieved = agents.SOURCES.get() or []
        citations = retrieved or summary["citations"]
        db.log(dispute_id, "system", "classified the draft", summary)
        db.save_draft(dispute_id, member_msg, summary["recommendation"],
                      summary["amount_cents"], citations)
        db.set_status(dispute_id, "awaiting_approval")
        db.log(dispute_id, "system", "waiting for a human reviewer")
        return member_msg
    except Exception as e:
        db.log(dispute_id, "system", "triage failed", f"{type(e).__name__}: {e}")
        db.set_status(dispute_id, "submitted")      # leave it for a retry
        raise
    finally:
        agents.CURRENT.reset(token)
        agents.SOURCES.reset(sources_token)

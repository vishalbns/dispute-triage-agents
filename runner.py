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

        prompt = (
            f"Case reference: D-{dispute_id}\n"
            f"Member: {d['member_name']}\n"
            f"Transaction: {d['txn_id']} for ${d['amount_cents']/100:,.2f} at {d['merchant'] or 'unknown merchant'}\n"
            f"Dispute type: {d['reason']}\n"
            f"Member says: {safe_text}\n\n"
            "Triage this dispute."
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

        summary = _extract(model, safe_answer)
        db.log(dispute_id, "system", "classified the draft", summary)
        db.save_draft(dispute_id, safe_answer, summary["recommendation"],
                      summary["amount_cents"], summary["citations"])
        db.set_status(dispute_id, "awaiting_approval")
        db.log(dispute_id, "system", "waiting for a human reviewer")
        return safe_answer
    except Exception as e:
        db.log(dispute_id, "system", "triage failed", f"{type(e).__name__}: {e}")
        db.set_status(dispute_id, "submitted")      # leave it for a retry
        raise
    finally:
        agents.CURRENT.reset(token)

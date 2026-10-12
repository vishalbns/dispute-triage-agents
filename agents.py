"""The two agents, built with Strands.

policy_agent  : retrieval only, no write tools, cites every claim.
case_agent    : holds the case, calls tools, and can only QUEUE money movement.

Every tool writes to the trace table, which is what the operations UI renders as
"backend processing". The agent cannot act without leaving a record.
"""
from contextvars import ContextVar
from strands import Agent, tool

import db
import fixtures
import retrieval
from config import (MODEL_PROVIDER, BEDROCK_MODEL_ID, ANTHROPIC_MODEL_ID, AWS_REGION,
                    GUARDRAIL_ID, GUARDRAIL_VERSION)

# Which dispute the current run belongs to, so tools can write to the right trace.
CURRENT: ContextVar[int] = ContextVar("current_dispute", default=0)

# Sources touched during one run, so the draft can cite what was actually retrieved
# rather than whatever the model remembers having read.
SOURCES: ContextVar[list] = ContextVar("sources", default=None)

MEMBER_MARKER = "---MEMBER MESSAGE---"


def build_model():
    """Bedrock is the target. Anthropic direct keeps the demo runnable without AWS."""
    if MODEL_PROVIDER == "bedrock":
        from strands.models import BedrockModel
        kwargs = dict(model_id=BEDROCK_MODEL_ID, region_name=AWS_REGION, temperature=0.2)
        if GUARDRAIL_ID:
            kwargs.update(guardrail_id=GUARDRAIL_ID, guardrail_version=GUARDRAIL_VERSION,
                          guardrail_trace="enabled",
                          # mask rather than hard-fail when the guardrail catches PII
                          guardrail_redact_input=True, guardrail_redact_output=True)
        return BedrockModel(**kwargs)

    import os
    from strands.models.anthropic import AnthropicModel
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("Set ANTHROPIC_API_KEY, or set MODEL_PROVIDER=bedrock with working AWS credentials.")
    # note: this SDK version rejects temperature through its streaming helper, so it is omitted
    return AnthropicModel(client_args={"api_key": key}, model_id=ANTHROPIC_MODEL_ID,
                          max_tokens=2048)


# ---------------------------------------------------------------- policy agent
@tool
def search_policy(question: str) -> str:
    """Retrieve the policy passages relevant to a dispute question."""
    hits = retrieval.search(question, k=4)
    bucket = SOURCES.get()
    if bucket is not None:
        for h in hits:
            if h["source"] not in bucket:
                bucket.append(h["source"])
    db.log(CURRENT.get(), "policy_agent", "retrieved policy",
           "\n".join(f"- {h['source']}" for h in hits) or "(nothing found)")
    if not hits:
        return "No matching policy text."
    return "\n\n".join(f"[{h['source']}]\n{h['text']}" for h in hits)


def make_policy_agent(model):
    return Agent(
        name="policy",
        model=model,
        tools=[search_policy],
        system_prompt=(
            "You answer questions about dispute policy for a financial institution. "
            "Use search_policy, then answer ONLY from the retrieved text. "
            "Cite the source tag, for example [P-001 1.3], after every claim. "
            "If the retrieved text does not answer the question, say so plainly."
        ),
    )


# ------------------------------------------------------------------ case agent
@tool
def get_transaction(txn_id: str) -> dict:
    """Look up one transaction by id. Read only."""
    data = fixtures.get(txn_id)
    db.log(CURRENT.get(), "case_agent", f"looked up {txn_id}", data)
    return data


@tool
def get_loan(loan_id: str) -> dict:
    """Look up a mortgage loan: escrow, lender-placed premium and the notice dates. Read only."""
    data = fixtures.get_loan(loan_id)
    db.log(CURRENT.get(), "case_agent", f"looked up {loan_id}", data)
    return data


def make_case_agent(model, policy_agent):
    @tool
    def ask_policy(question: str) -> str:
        """Ask the policy specialist what the rules require. Returns an answer with citations."""
        db.log(CURRENT.get(), "case_agent", "asked the policy agent", question)
        answer = str(policy_agent(question))
        db.log(CURRENT.get(), "policy_agent", "answered", answer)
        return answer

    @tool
    def queue_provisional_credit(txn_id: str, amount_cents: int, rationale: str) -> str:
        """Queue a credit or refund for human approval. This does NOT move money."""
        db.log(CURRENT.get(), "case_agent", f"queued provisional credit {amount_cents} cents",
               f"txn {txn_id}\n\n{rationale}")
        return (f"Queued {amount_cents} cents on {txn_id} for reviewer approval. "
                "No funds have moved and none will until a reviewer approves.")

    return Agent(
        name="case",
        model=model,
        tools=[get_transaction, get_loan, ask_policy, queue_provisional_credit],
        system_prompt=(
            "You triage member cases at a financial institution. Two kinds reach you:\n"
            "  card_dispute: a disputed card transaction. Use get_transaction.\n"
            "  insurance_tracking: a borrower disputes a lender-placed insurance premium charged "
            "to escrow. Use get_loan, and check the notice dates against the policy before "
            "anything else, because a missed notice invalidates the charge on its own.\n"
            "Process: look up the record, ask the policy agent what the rules require for this "
            "case type and timing, then decide a recommendation.\n"
            "You may NEVER move money. The only money related tool you have queues a request for "
            "a human reviewer, and you must use it whenever a provisional credit is warranted.\n"
            "Escalate to the fraud team instead of resolving routinely when the policy's escalation "
            "triggers are met.\n"
            "Finish your reply with your internal triage notes, then a line containing exactly "
            f"{MEMBER_MARKER} and nothing else, then the message to the member and nothing after it.\n"
            "The member message states what happens next, by when, and the case reference. Never "
            "include full card or account numbers, only the last four digits. Do not admit liability "
            "before the investigation concludes."
        ),
    )

"""AgentCore Runtime entrypoint.

Satisfies the AgentCore contract: an entrypoint module exposing a handler. The
same runner.process powers the local worker, so deploying changes where the code
runs, not what it does.

Local check:
    python main.py            # serves /invocations and /ping on :8080
"""
from bedrock_agentcore import BedrockAgentCoreApp

import db
import runner

app = BedrockAgentCoreApp()


@app.entrypoint
async def handler(payload):
    """payload: {"dispute_id": 12} or {"prompt": "12"}"""
    db.init()
    raw = payload.get("dispute_id") or payload.get("prompt")
    dispute_id = int(str(raw).strip().lstrip("D-"))
    draft = runner.process(dispute_id)
    row = db.get_dispute(dispute_id)
    return {"dispute_id": dispute_id, "status": row["status"], "draft": draft}


if __name__ == "__main__":
    app.run()

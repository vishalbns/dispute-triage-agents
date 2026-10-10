# Dispute triage: two agents, a human, and an audit trail

A working demo of agentic AI inside a regulated workflow. A member disputes a card
transaction, two agents triage it against policy, and a bank reviewer approves or
denies before anything moves. The member then sees the outcome and what happens next.

Built with [Strands Agents](https://strandsagents.com/), deployable to Amazon
Bedrock AgentCore Runtime, and runnable end to end on a laptop with no AWS account.

## Why it is shaped this way

- **The agent that can act and the agent that reads policy are separate.** The case
  agent holds tools; the policy agent is retrieval only. The surface that can do
  damage is as small as possible.
- **The agent cannot move money.** Its only money related tool *queues* a request
  for a reviewer. That is a structural guarantee, not a prompt instruction.
- **Everything is on the record.** Every tool call, retrieval and guardrail action
  writes to a trace table, which is what the operations UI renders.
- **Guardrails run on the way in and the way out.** Local redaction always, Bedrock
  Guardrails when configured.

## Architecture

```
member (Streamlit)                 worker                      operations (Streamlit)
      |                               |                                  |
 raise dispute ---> SQLite  <--- poll 'submitted'                        |
                      ^              |                                   |
                      |         runner.process()                         |
                      |              |                                   |
                      |       +------+------+                            |
                      |       | case agent  |-- get_transaction -> core banking (mock)
                      |       |             |-- ask_policy ---> policy agent -> Chroma
                      |       |             |-- queue_credit -> approval queue
                      |       +------+------+                            |
                      |              |                                   |
                      +---- trace + draft written --------------------> review
                                                                          |
                                                              approve / deny
                                                                          |
                      member sees outcome and next steps <----------------+
```

`runner.process(dispute_id)` is the only orchestration. The local worker and the
AgentCore entrypoint both call it, so deployment changes where the code runs, not
what it does.

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # then edit

python retrieval.py             # build the policy index (prints chunk count)

# three terminals, all with the venv active
python worker.py
streamlit run ui/customer.py --server.port 8501
streamlit run ui/ops.py --server.port 8502
```

Raise a dispute at :8501, watch the worker triage it, review and decide at :8502,
then return to :8501 to see the outcome.

### Without AWS

Set `MODEL_PROVIDER=anthropic` and `ANTHROPIC_API_KEY` in `.env`. Embeddings stay
local by default, so nothing else is needed.

### With Bedrock

Set `MODEL_PROVIDER=bedrock` and working AWS credentials, with model access enabled
in your region. Optionally set `EMBEDDINGS=titan` and a `GUARDRAIL_ID`.

## Deploying the agent to AgentCore

`main.py` satisfies the AgentCore Runtime contract through `@app.entrypoint`.

```bash
npm install -g @aws/agentcore
agentcore create --project-name DisputeTriage --name CaseAgent \
  --language Python --framework Strands --model-provider Bedrock --build CodeZip
agentcore dev --no-browser      # local, serves /invocations on :8080
agentcore deploy
agentcore invoke '{"dispute_id": 1}'
```

Notes that cost time if you learn them the hard way: AgentCore Runtime is **arm64
only**, so wheels must be built for `aarch64-manylinux2014`; the deployment zip caps
at 250 MB; and `idleRuntimeSessionTimeout` is worth setting so idle sessions stop
billing.

## What is deliberately fake

- `fixtures.py` stands in for a core banking API.
- The policy documents in `policies/` are synthetic. They are written around real
  Regulation E timings and liability tiers so the reasoning is realistic, but they
  are illustrative and are not anyone's actual policy.
- SQLite stands in for the case management system. The `db.py` interface is narrow
  on purpose so DynamoDB or Postgres can replace it without touching the agents.

## Layout

| File | What it does |
|---|---|
| `agents.py` | The two Strands agents and their tools |
| `runner.py` | Orchestration: guardrails, agents, classification, draft |
| `retrieval.py` | Chunking, indexing and vector search over `policies/` |
| `guardrails.py` | Local redaction plus optional Bedrock Guardrails |
| `db.py` | SQLite schema and the whole data interface |
| `worker.py` | Polls for new disputes, stands in for the event trigger |
| `main.py` | AgentCore Runtime entrypoint |
| `ui/customer.py`, `ui/ops.py` | The two Streamlit apps |

"""SQLite store for disputes, the agent trace, and approvals.

One file, no server. The interface is deliberately narrow so the storage can be
swapped for DynamoDB later without touching the agents or the UI.
"""
import json
import sqlite3
from datetime import datetime, timezone
from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS disputes (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  case_type     TEXT NOT NULL DEFAULT 'card_dispute',
  member_name   TEXT NOT NULL,
  member_email  TEXT NOT NULL,
  txn_id        TEXT NOT NULL,
  amount_cents  INTEGER NOT NULL,
  merchant      TEXT,
  reason        TEXT NOT NULL,
  description   TEXT,
  status        TEXT NOT NULL DEFAULT 'submitted',
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS trace (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  dispute_id  INTEGER NOT NULL REFERENCES disputes(id),
  actor       TEXT NOT NULL,      -- case_agent | policy_agent | guardrail | system | reviewer
  event       TEXT NOT NULL,
  detail      TEXT,
  created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS drafts (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  dispute_id     INTEGER NOT NULL REFERENCES disputes(id),
  body           TEXT NOT NULL,
  recommendation TEXT,             -- approve | deny | more_info
  amount_cents   INTEGER DEFAULT 0,
  citations      TEXT,             -- json list
  created_at     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS approvals (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  dispute_id  INTEGER NOT NULL REFERENCES disputes(id),
  decision    TEXT NOT NULL,       -- approved | denied
  reviewer    TEXT NOT NULL,
  note        TEXT,
  final_body  TEXT,
  created_at  TEXT NOT NULL
);
"""

STATUSES = ["submitted", "processing", "awaiting_approval", "approved", "denied"]


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def conn():
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")      # two Streamlit apps read and write at once
    return c


def init():
    with conn() as c:
        c.executescript(SCHEMA)
        cols = [r["name"] for r in c.execute("PRAGMA table_info(disputes)")]
        if "case_type" not in cols:        # upgrade a database created before case types
            c.execute("ALTER TABLE disputes ADD COLUMN case_type TEXT NOT NULL DEFAULT 'card_dispute'")


def create_dispute(**kw) -> int:
    with conn() as c:
        cur = c.execute(
            """INSERT INTO disputes (case_type, member_name, member_email, txn_id, amount_cents,
               merchant, reason, description, status, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,'submitted',?,?)""",
            (kw.get("case_type", "card_dispute"),
             kw["member_name"], kw["member_email"], kw["txn_id"], kw["amount_cents"],
             kw.get("merchant", ""), kw["reason"], kw.get("description", ""), now(), now()))
        return cur.lastrowid


def set_status(dispute_id: int, status: str):
    assert status in STATUSES, status
    with conn() as c:
        c.execute("UPDATE disputes SET status=?, updated_at=? WHERE id=?", (status, now(), dispute_id))


def log(dispute_id: int, actor: str, event: str, detail=None):
    if detail is not None and not isinstance(detail, str):
        detail = json.dumps(detail, indent=2, default=str)
    with conn() as c:
        c.execute("INSERT INTO trace (dispute_id, actor, event, detail, created_at) VALUES (?,?,?,?,?)",
                  (dispute_id, actor, event, detail, now()))


def save_draft(dispute_id: int, body: str, recommendation: str, amount_cents: int, citations: list):
    with conn() as c:
        c.execute("""INSERT INTO drafts (dispute_id, body, recommendation, amount_cents, citations, created_at)
                     VALUES (?,?,?,?,?,?)""",
                  (dispute_id, body, recommendation, amount_cents, json.dumps(citations), now()))


def decide(dispute_id: int, decision: str, reviewer: str, note: str, final_body: str):
    assert decision in ("approved", "denied")
    with conn() as c:
        c.execute("""INSERT INTO approvals (dispute_id, decision, reviewer, note, final_body, created_at)
                     VALUES (?,?,?,?,?,?)""", (dispute_id, decision, reviewer, note, final_body, now()))
    set_status(dispute_id, decision)
    log(dispute_id, "reviewer", f"decision: {decision}", note or "")


def get_dispute(dispute_id: int):
    with conn() as c:
        return c.execute("SELECT * FROM disputes WHERE id=?", (dispute_id,)).fetchone()


def list_disputes(status=None):
    q = "SELECT * FROM disputes"
    args = ()
    if status:
        q += " WHERE status=?"
        args = (status,)
    q += " ORDER BY id DESC"
    with conn() as c:
        return c.execute(q, args).fetchall()


def get_trace(dispute_id: int):
    with conn() as c:
        return c.execute("SELECT * FROM trace WHERE dispute_id=? ORDER BY id", (dispute_id,)).fetchall()


def latest_draft(dispute_id: int):
    with conn() as c:
        return c.execute("SELECT * FROM drafts WHERE dispute_id=? ORDER BY id DESC LIMIT 1",
                         (dispute_id,)).fetchone()


def latest_decision(dispute_id: int):
    with conn() as c:
        return c.execute("SELECT * FROM approvals WHERE dispute_id=? ORDER BY id DESC LIMIT 1",
                         (dispute_id,)).fetchone()

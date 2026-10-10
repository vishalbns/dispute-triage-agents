"""Bank side app: watch the agents work, then approve or deny."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import db

st.set_page_config(page_title="Dispute operations", page_icon="🏦", layout="wide")
db.init()

ACTOR_ICON = {"case_agent": "🧭", "policy_agent": "📘", "guardrail": "🛡️",
              "system": "⚙️", "reviewer": "🧑‍⚖️"}

st.title("Dispute operations")
reviewer = st.sidebar.text_input("Reviewer", value="", placeholder="your name")
show = st.sidebar.radio("Queue", ["Awaiting approval", "All"], index=0)
if st.sidebar.button("Refresh"):
    st.rerun()

rows = db.list_disputes(status="awaiting_approval") if show == "Awaiting approval" else db.list_disputes()
st.sidebar.caption(f"{len(rows)} case(s)")

if not rows:
    st.info("Nothing in the queue. Raise a dispute in the member app and make sure the worker is running.")
    st.stop()

choice = st.sidebar.radio(
    "Cases", [r["id"] for r in rows],
    format_func=lambda i: f"D-{i} · {db.get_dispute(i)['merchant']}")
d = db.get_dispute(choice)

left, right = st.columns([1, 1])

with left:
    st.subheader(f"D-{d['id']}  ·  {d['status'].replace('_', ' ')}")
    st.markdown(f"**{d['member_name']}** · {d['member_email']}")
    st.markdown(f"{d['txn_id']} · **${d['amount_cents']/100:,.2f}** · {d['merchant']}")
    st.caption(d["reason"])
    if d["description"]:
        st.write(d["description"])

    st.markdown("##### Backend processing")
    for t in db.get_trace(d["id"]):
        icon = ACTOR_ICON.get(t["actor"], "•")
        with st.expander(f"{icon} {t['actor']} · {t['event']}", expanded=False):
            st.caption(t["created_at"])
            if t["detail"]:
                st.code(t["detail"][:4000])

with right:
    draft = db.latest_draft(d["id"])
    if not draft:
        st.info("No draft yet. The worker triages cases with status 'submitted'.")
        st.stop()

    cites = json.loads(draft["citations"] or "[]")
    cols = st.columns(2)
    cols[0].metric("Recommendation", draft["recommendation"].replace("_", " "))
    cols[1].metric("Credit requested", f"${draft['amount_cents']/100:,.2f}")
    if cites:
        st.caption("Policy relied on: " + " · ".join(cites))

    st.markdown("##### Draft to the member")
    body = st.text_area("Edit before sending", value=draft["body"], height=320,
                        label_visibility="collapsed")

    note = st.text_input("Reviewer note (recorded on the case)")
    decided = d["status"] in ("approved", "denied")
    if decided:
        dec = db.latest_decision(d["id"])
        st.success(f"Already {dec['decision']} by {dec['reviewer']} on {dec['created_at'][:16]}")
    else:
        c1, c2 = st.columns(2)
        if c1.button("Approve", type="primary", use_container_width=True, disabled=not reviewer):
            db.decide(d["id"], "approved", reviewer, note, body)
            st.rerun()
        if c2.button("Deny", use_container_width=True, disabled=not reviewer):
            db.decide(d["id"], "denied", reviewer, note, body)
            st.rerun()
        if not reviewer:
            st.caption("Enter your name in the sidebar to decide.")

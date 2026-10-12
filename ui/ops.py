"""Operations portal: watch the agents work, then approve or deny."""
import json
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

import db
import notify
import theme

theme.page("Dispute operations", "🏦", "Dispute operations", wide=True)
db.init()

CASE_LABEL = {"card_dispute": "Card dispute", "insurance_tracking": "Insurance tracking"}
ACTOR = {
    "case_agent":   ("🧭", "Case agent"),
    "policy_agent": ("📘", "Policy agent"),
    "guardrail":    ("🛡️", "Guardrail"),
    "system":       ("⚙️", "System"),
    "reviewer":     ("🧑‍⚖️", "Reviewer"),
}

with st.sidebar:
    st.markdown("#### Reviewer")
    reviewer = st.text_input("Your name", placeholder="required to decide",
                             label_visibility="collapsed")
    st.divider()
    queue = st.radio("Queue", ["Awaiting approval", "All cases"], index=0)
    if st.button("Refresh", use_container_width=True):
        st.rerun()

    in_flight = [r for r in db.list_disputes() if r["status"] in ("submitted", "processing")]
    live = st.toggle("Live updates", value=True, help="Polls every 3s while cases are being triaged")
    if in_flight:
        st.caption(f"⏳ {len(in_flight)} case(s) being triaged")

rows = db.list_disputes(status="awaiting_approval") if queue == "Awaiting approval" else db.list_disputes()

if not rows:
    theme.demo_note()
    st.info("Nothing in this queue. Raise a case in the member portal, and make sure the worker is running.")
    if in_flight and live:
        time.sleep(3); st.rerun()
    st.stop()

with st.sidebar:
    st.divider()
    st.markdown("#### Cases")
    choice = st.radio(
        "Cases", [r["id"] for r in rows], label_visibility="collapsed",
        format_func=lambda i: f"D-{i} · {db.get_dispute(i)['merchant'][:22]}")

d = db.get_dispute(choice)
ctype = d["case_type"] if "case_type" in d.keys() else "card_dispute"
theme.demo_note("Decisions here send a real email to the address on the case.")

left, right = st.columns([1, 1.05], gap="large")

with left:
    head = st.columns([3, 1.4])
    head[0].markdown(f"### D-{d['id']}")
    head[1].markdown(theme.pill(d["status"]), unsafe_allow_html=True)
    st.markdown(f"<span class='meta'>{CASE_LABEL.get(ctype, ctype)} · raised {d['created_at'][:16]}</span>",
                unsafe_allow_html=True)

    with st.container(border=True):
        c = st.columns(2)
        c[0].markdown(f"**{d['member_name']}**  \n<span class='meta'>{d['member_email']}</span>",
                      unsafe_allow_html=True)
        ref = "Loan" if ctype == "insurance_tracking" else "Transaction"
        c[1].markdown(f"**${d['amount_cents']/100:,.2f}**  \n<span class='meta'>{ref} {d['txn_id']}</span>",
                      unsafe_allow_html=True)
        st.markdown(f"<span class='meta'>{d['merchant']}</span>", unsafe_allow_html=True)
        st.write(f"**{d['reason']}**")
        if d["description"]:
            st.write(d["description"])

    st.markdown("<div class='sect'>Backend processing</div>", unsafe_allow_html=True)
    for t in db.get_trace(d["id"]):
        icon, who = ACTOR.get(t["actor"], ("•", t["actor"]))
        with st.expander(f"{icon}  {who} · {t['event']}"):
            st.markdown(f"<span class='meta'>{t['created_at']}</span>", unsafe_allow_html=True)
            if t["detail"]:
                st.code(t["detail"][:4000], language=None)

with right:
    draft = db.latest_draft(d["id"])
    if not draft:
        st.info("No draft yet. The worker triages cases with status 'submitted'.")
        st.stop()

    m = st.columns(2)
    m[0].metric("Recommendation", draft["recommendation"].replace("_", " "))
    m[1].metric("Credit requested", f"${draft['amount_cents']/100:,.2f}")
    cites = json.loads(draft["citations"] or "[]")
    if cites:
        st.markdown("<div class='sect'>Policy relied on</div>", unsafe_allow_html=True)
        st.markdown("<span class='meta'>" + " · ".join(cites[:8]) + "</span>", unsafe_allow_html=True)

    st.markdown("<div class='sect'>Message to the member</div>", unsafe_allow_html=True)
    body = st.text_area("Edit before sending", value=draft["body"], height=330,
                        label_visibility="collapsed")

    if d["status"] in ("approved", "denied"):
        dec = db.latest_decision(d["id"])
        st.success(f"{dec['decision'].title()} by {dec['reviewer']} on {dec['created_at'][:16]}")
        if dec["note"]:
            st.caption(f"Note: {dec['note']}")
        kind, detail = st.session_state.pop("last_notice", (None, None))
        if kind == "sent":
            st.info(f"Member notified: {detail}")
        elif kind == "outbox":
            st.warning(f"SMTP is not configured, so nothing was sent. {detail}")
    else:
        note = st.text_input("Reviewer note (recorded on the case)")

        def finish(decision):
            db.decide(d["id"], decision, reviewer, note, body)
            sent, detail = notify.send_decision(d["id"])
            st.session_state["last_notice"] = ("sent" if sent else "outbox", detail)
            st.rerun()

        b = st.columns(2)
        if b[0].button("Approve", type="primary", use_container_width=True, disabled=not reviewer):
            finish("approved")
        if b[1].button("Deny", use_container_width=True, disabled=not reviewer):
            finish("denied")
        if not reviewer:
            st.caption("Enter your name in the sidebar to decide.")

if in_flight and live:
    time.sleep(3)
    st.rerun()

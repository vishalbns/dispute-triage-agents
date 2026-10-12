"""Member portal: raise a case, then watch for the outcome."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

import db
import fixtures
import theme

theme.page("Member portal", "💳", "Member portal")
db.init()

CASE_LABELS = {
    "card_dispute": "A card transaction",
    "insurance_tracking": "An insurance charge on my mortgage escrow",
}
PROGRESS = {
    "submitted": "We have your case and will start the review shortly.",
    "processing": "We are checking it against our policies.",
    "awaiting_approval": "A member of our team is reviewing the case.",
}

st.markdown("### Raise a dispute")
theme.demo_note()

email = st.text_input("Your email", placeholder="you@example.com")
if not email:
    st.caption("Enter your email to raise a case or check one you already filed.")
    st.stop()

tab_new, tab_mine = st.tabs(["Raise a case", "My cases"])

with tab_new:
    case_type = st.radio("What are you disputing?", list(CASE_LABELS),
                         format_func=CASE_LABELS.get, horizontal=True)

    if case_type == "insurance_tracking":
        with st.form("ins"):
            name = st.text_input("Your name")
            loan = st.selectbox("Loan", list(fixtures.LOANS),
                                format_func=lambda l: f"{l} · {fixtures.LOANS[l]['property']}")
            prem = fixtures.LOANS[loan]["lender_placed_premium_cents"] / 100
            st.caption(f"Lender-placed premium charged to escrow: ${prem:,.2f}")
            reason = st.selectbox("What is wrong?", [
                "I had my own insurance the whole time",
                "I never received the notices about this charge",
                "The premium charged is wrong",
            ])
            description = st.text_area("Tell us what happened", height=110,
                                       placeholder="When did your own policy start, and with which carrier?")
            go = st.form_submit_button("Submit case", type="primary")
        if go:
            if not name.strip():
                st.error("Please enter your name.")
            else:
                ln = fixtures.LOANS[loan]
                did = db.create_dispute(case_type="insurance_tracking", member_name=name.strip(),
                                        member_email=email.strip(), txn_id=loan,
                                        amount_cents=ln["lender_placed_premium_cents"],
                                        merchant="Lender-placed insurance premium",
                                        reason=reason, description=description.strip())
                st.success(f"Case raised. Your reference is **D-{did}**.")
                st.caption("Open the My cases tab to follow progress.")
    else:
        with st.form("card"):
            name = st.text_input("Your name")
            txn = st.selectbox("Transaction", list(fixtures.TRANSACTIONS),
                               format_func=lambda t: (f"{t} · ${fixtures.TRANSACTIONS[t]['amount_cents']/100:,.2f}"
                                                      f" · {fixtures.TRANSACTIONS[t]['merchant']}"))
            reason = st.selectbox("What is wrong?", [
                "I did not authorize this transaction",
                "I was charged twice for the same thing",
                "The goods or services never arrived",
                "The item was not as described",
                "I cancelled this subscription and was charged anyway",
            ])
            description = st.text_area("Tell us what happened", height=110,
                                       placeholder="When did you notice, and have you contacted the merchant?")
            go = st.form_submit_button("Submit case", type="primary")
        if go:
            if not name.strip():
                st.error("Please enter your name.")
            else:
                t = fixtures.TRANSACTIONS[txn]
                did = db.create_dispute(case_type="card_dispute", member_name=name.strip(),
                                        member_email=email.strip(), txn_id=txn,
                                        amount_cents=t["amount_cents"], merchant=t["merchant"],
                                        reason=reason, description=description.strip())
                st.success(f"Case raised. Your reference is **D-{did}**.")
                st.caption("Open the My cases tab to follow progress.")

with tab_mine:
    rows = [r for r in db.list_disputes() if r["member_email"].lower() == email.strip().lower()]
    if not rows:
        st.caption("Nothing here yet.")
    for r in rows:
        with st.container(border=True):
            top = st.columns([3, 1.4])
            top[0].markdown(f"**D-{r['id']}** · {r['merchant']} · ${r['amount_cents']/100:,.2f}")
            top[1].markdown(theme.pill(r["status"]), unsafe_allow_html=True)
            st.markdown(f"<span class='meta'>{r['reason']} · raised {r['created_at'][:10]}</span>",
                        unsafe_allow_html=True)

            if r["status"] in ("approved", "denied"):
                dec = db.latest_decision(r["id"])
                if dec:
                    with st.expander("Our decision", expanded=True):
                        st.markdown(dec["final_body"])
                        if r["status"] == "approved":
                            st.success("Next steps: the credit will appear within 5 business days. "
                                       "We will write again when the investigation closes.")
                        else:
                            st.warning("Next steps: you can appeal within 60 days, and you may "
                                       "request the documents we relied on.")
            else:
                st.caption(PROGRESS.get(r["status"], ""))

    if st.button("Refresh"):
        st.rerun()

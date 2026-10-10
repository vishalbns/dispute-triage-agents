"""Member facing app: raise a dispute, then watch for the outcome."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import db
import fixtures

st.set_page_config(page_title="Member disputes", page_icon="💳", layout="centered")
db.init()

STATUS_TEXT = {
    "submitted":         ("Received", "We have your dispute and will start the review shortly."),
    "processing":        ("In review", "We are checking the transaction against our policies."),
    "awaiting_approval": ("With an analyst", "A member of our disputes team is reviewing the case."),
    "approved":          ("Resolved in your favour", ""),
    "denied":            ("Closed", ""),
}

st.title("Dispute a transaction")

email = st.text_input("Your email", key="email", placeholder="you@example.com")
if not email:
    st.info("Enter your email to raise a dispute or check one you already filed.")
    st.stop()

tab_new, tab_mine = st.tabs(["Raise a dispute", "My disputes"])

with tab_new:
    with st.form("dispute"):
        name = st.text_input("Your name")
        txn = st.selectbox("Transaction", list(fixtures.TRANSACTIONS.keys()),
                           format_func=lambda t: (f"{t} · ${fixtures.TRANSACTIONS[t]['amount_cents']/100:,.2f} · "
                                                  f"{fixtures.TRANSACTIONS[t]['merchant']}"))
        reason = st.selectbox("What is wrong?", [
            "I did not authorize this transaction",
            "I was charged twice for the same thing",
            "The goods or services never arrived",
            "The item was not as described",
            "I cancelled this subscription and was charged anyway",
        ])
        description = st.text_area("Tell us what happened", height=120,
                                   placeholder="When did you notice, and have you contacted the merchant?")
        submitted = st.form_submit_button("Submit dispute", type="primary")

    if submitted:
        if not name.strip():
            st.error("Please enter your name.")
        else:
            t = fixtures.TRANSACTIONS[txn]
            did = db.create_dispute(member_name=name.strip(), member_email=email.strip(),
                                    txn_id=txn, amount_cents=t["amount_cents"],
                                    merchant=t["merchant"], reason=reason, description=description.strip())
            st.success(f"Dispute raised. Your case reference is **D-{did}**.")
            st.caption("Check the My disputes tab for progress.")

with tab_mine:
    rows = [r for r in db.list_disputes() if r["member_email"].lower() == email.strip().lower()]
    if not rows:
        st.caption("Nothing here yet.")
    for r in rows:
        label, blurb = STATUS_TEXT.get(r["status"], (r["status"], ""))
        with st.container(border=True):
            top = st.columns([3, 2])
            top[0].markdown(f"**D-{r['id']}** · {r['merchant']} · ${r['amount_cents']/100:,.2f}")
            top[1].markdown(f"**{label}**")
            st.caption(f"{r['reason']} · raised {r['created_at'][:10]}")

            if r["status"] in ("approved", "denied"):
                dec = db.latest_decision(r["id"])
                if dec:
                    st.markdown(dec["final_body"])
                    if r["status"] == "approved":
                        st.success("Next steps: the credit will appear on your account within "
                                   "5 business days. We will write again when the investigation closes.")
                    else:
                        st.warning("Next steps: if you disagree you can appeal within 60 days, and you "
                                   "may request the documents we relied on.")
            elif blurb:
                st.caption(blurb)

    if st.button("Refresh"):
        st.rerun()

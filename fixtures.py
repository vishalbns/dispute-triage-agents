"""Stand-in for the core banking API. Replace with the real client later."""
TRANSACTIONS = {
    "txn_88213": {"txn_id": "txn_88213", "amount_cents": 24000, "merchant": "NORTHGATE ELECTRONICS",
                  "posted": "2026-09-28", "card_last4": "4417", "channel": "card_not_present",
                  "country": "US", "member_travel_history": ["US"], "disputes_last_30d": 0},
    "txn_90114": {"txn_id": "txn_90114", "amount_cents": 129900, "merchant": "LUMA TRAVEL GROUP",
                  "posted": "2026-09-19", "card_last4": "4417", "channel": "card_not_present",
                  "country": "PT", "member_travel_history": ["US"], "disputes_last_30d": 2},
    "txn_77320": {"txn_id": "txn_77320", "amount_cents": 4599, "merchant": "BRIGHTLEAF COFFEE",
                  "posted": "2026-10-02", "card_last4": "4417", "channel": "card_present",
                  "country": "US", "member_travel_history": ["US"], "disputes_last_30d": 0},
}


def get(txn_id: str):
    return TRANSACTIONS.get(txn_id, {"error": f"no transaction {txn_id}"})


LOANS = {
    "ln_40881": {"loan_id": "ln_40881", "property": "400 N 2nd Ave, Phoenix AZ 85003",
                 "lender_placed_premium_cents": 184500, "charged_on": "2026-09-15",
                 "first_notice_sent": "2026-07-28", "second_notice_sent": "2026-08-29",
                 "coverage_on_file": None, "escrow_balance_cents": 212000},
    "ln_51720": {"loan_id": "ln_51720", "property": "1180 Camino Real, San Antonio TX 78216",
                 "lender_placed_premium_cents": 96000, "charged_on": "2026-09-02",
                 "first_notice_sent": "2026-08-20",          # only 13 days before the charge
                 "second_notice_sent": None,
                 "coverage_on_file": None, "escrow_balance_cents": 143000},
}


def get_loan(loan_id: str):
    return LOANS.get(loan_id, {"error": f"no loan {loan_id}"})

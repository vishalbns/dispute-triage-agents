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

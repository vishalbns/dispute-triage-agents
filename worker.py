"""Polls for new disputes and triages them.

Stands in for the event-driven piece: in production a new dispute would raise an
event and AgentCore Runtime would host the agent. The orchestration in runner.py
is identical either way.
"""
import time
import traceback

import db
import runner

POLL_SECONDS = 2


def main():
    db.init()
    print("worker running. ctrl-c to stop.")
    while True:
        for row in db.list_disputes(status="submitted"):
            print(f"  triaging D-{row['id']} ...", flush=True)
            try:
                runner.process(row["id"])
                print(f"  D-{row['id']} ready for review")
            except Exception:
                traceback.print_exc()
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()

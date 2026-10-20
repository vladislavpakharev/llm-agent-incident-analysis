"""Incident report from the agent's tool-call log.

    python3 src/report.py [path/to/agent_log.jsonl]

The log is JSON Lines: one tool call per line with `time`, `tool`, `args`, `result`.
The script reconstructs the incident in five steps:

  1. keep only successful calls (failed ones have no `data`);
  2. remember who created every order and when;
  3. find the *beneficiary*: the account with the most orders marked as picked up
     within a minute of creation (a suspiciously fast hand-over);
  4. find cancellations of orders that do not belong to the beneficiary; the first
     one is the boundary of the incident;
  5. count orders created for the beneficiary after that boundary.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

DEFAULT_LOG = Path(__file__).resolve().parents[1] / "data" / "agent_log.jsonl"
FAST_PICKUP_SECONDS = 60  # an order picked up faster than a minute is suspicious
TIME_FORMAT = "%Y-%m-%dT%H:%M:%S"


def read_log(path):
    records = []
    with open(path, encoding="utf-8") as source:
        for line in source:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def seconds_between(start, end):
    delta = datetime.strptime(end, TIME_FORMAT) - datetime.strptime(start, TIME_FORMAT)
    return delta.total_seconds()


def analyse(records):
    """Return the incident summary as a dict, or None if no suspicious pattern is found."""
    # Step 1. Successful calls only.
    successful = [r for r in records if r["result"].get("ok")]

    # Step 2. Order id -> owner and creation time.
    owner, created_at = {}, {}
    for record in successful:
        if record["tool"] == "create_order":
            order_id = record["result"]["data"]["order_id"]
            owner[order_id] = record["args"]["user_id"]
            created_at[order_id] = record["time"]

    # Step 3. Beneficiary = most fast pick-ups.
    fast = {}
    for record in successful:
        if record["tool"] == "confirm_pickup":
            order_id = record["result"]["data"]["order_id"]
            if order_id in created_at and \
                    seconds_between(created_at[order_id], record["time"]) <= FAST_PICKUP_SECONDS:
                fast[owner[order_id]] = fast.get(owner[order_id], 0) + 1
    if not fast:
        return None
    beneficiary = max(fast, key=fast.get)

    # Step 4. Cancellations of other people's orders; the first one is the boundary.
    cancelled_foreign = set()
    boundary = None
    for record in successful:
        if record["tool"] == "cancel_order":
            order_id = record["result"]["data"]["order_id"]
            if owner.get(order_id) != beneficiary:
                cancelled_foreign.add(order_id)
                if boundary is None:
                    boundary = record["time"]
    if boundary is None:
        return None

    # Step 5. Orders for the beneficiary after the boundary (earlier ones are normal work).
    created_after = sum(
        1 for record in successful
        if record["tool"] == "create_order"
        and record["args"]["user_id"] == beneficiary
        and record["time"] > boundary
    )
    return {"boundary": boundary, "cancelled_foreign": len(cancelled_foreign),
            "beneficiary": beneficiary, "created_after": created_after}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    path = argv[0] if argv else DEFAULT_LOG
    summary = analyse(read_log(path))
    if summary is None:
        print("no suspicious pattern found")
        return 0
    print("first suspicious call: %s" % summary["boundary"])
    print("foreign orders cancelled: %d" % summary["cancelled_foreign"])
    print("beneficiary account: %s" % summary["beneficiary"])
    print("orders created for this account: %d" % summary["created_after"])
    return 0


if __name__ == "__main__":
    sys.exit(main())

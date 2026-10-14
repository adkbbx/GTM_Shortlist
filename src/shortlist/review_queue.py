"""Read-only operator triage; never fabricate review completion or buying intent."""
from shortlist.store import Store


def review_queue(store: Store) -> list[dict]:
    queue = []
    for summary in reversed(store.list_runs()):
        if summary["status"] not in ("ready", "partial"):
            continue
        run = store.get_run(summary["id"])
        for item in run["records"]:
            decision = item["review"]
            if decision and decision["decision"] != "needs_research":
                continue
            queue.append({"run_id": run["id"], "seller_url": run["profile"]["seller_url"],
                          "offer": run["profile"]["offer"], "target": run["profile"]["target"],
                          "research": item["research"], "customer_review": decision,
                          "operator_review": None})
            if len(queue) == 25:
                return queue
    return queue

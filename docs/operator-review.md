# Operator research triage

A read-only triage command lists at most25 unreviewed or needs-research company sheets from the latest100 saved runs, oldest within that window first. It includes the seller offer/target, preserved research/sources/unknowns and customer review decision. It does not make findings stronger, accept a company, contact anyone or mark an operator review complete.

```sh
shortlist review-queue
```

Hosted mode requires a separate restricted worker login and an explicit workspace:

```sh
shortlist review-queue --workspace VERIFIED-WORKSPACE-UUID
```

Run this only in a trusted operator environment. An assigned worker obeys that owner's row policies; the command never enumerates other accounts automatically. It is not a public admin endpoint. For the container, invoke python -m shortlist.cli review-queue using a trusted worker environment and entrypoint override.

Customer acceptance/rejection is separate from operator verification. Accepted/rejected customer sheets leave this triage view; needs-research sheets remain with their note. operator_review is explicitly null: no completed human review is inferred. This is an initial triage tool, not the finished managed-review workflow. Independent operator identity, annotation history, completion outcomes, requeueing and customer-visible service delivery still need implementation. Do not sell or claim a completed human review based on this list.

The actual development database currently returns16 saved items without provider calls or writes. Tests prove read-only behavior, inclusion of customer needs-research notes, exclusion of deleted/accepted sheets and assigned-worker isolation against real Postgres. This is not external reviewer feedback or a customer interview.

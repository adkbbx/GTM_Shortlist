# Independent service review

The operator queue and annotation commands are implemented for a trusted local operator or an explicitly selected hosted workspace using the separate worker credential. Customer acceptance, model qualification and operator review remain independent. The software does not verify the human identity behind a reviewer label or infer buying intent.

## Read and annotate

Run `shortlist review-queue` locally. Hosted commands require `--workspace` with the verified customer's workspace UUID. Read the saved company sheet and inspect its cited passages before writing a note. A customer's accepted or rejected decision does not remove a pending service review from this queue. The queue contains at most 25 pending sheets within the latest 100 runs, oldest first in that window.

Create a JSON command file with `run_id`, `record_id`, `request_key`, `previous_id` and `annotation`. Copy company/run/source identities from the saved queue; do not invent them. The first note has `previous_id: null`; subsequent notes must name the latest operator review ID. Use a new request key for a new note and retain the original key when retrying the same command.

The annotation contains:

- `outcome`: `reviewed` or `needs_research`.
- `reviewer`: a non-empty operator-supplied label, not a verified identity claim.
- `note`: the human's observations and unresolved questions, up to 2,000 characters.
- `source_ids`: unique saved sources the operator inspected, at most 21. `reviewed` requires at least one source; `needs_research` may have none.

Apply the file with `shortlist annotate review.json`. Inspect the saved history with `shortlist review-history RUN_ID RECORD_ID`. Append another note to correct or reopen the review. Notes do not edit evidence, model findings, qualification, customer decisions or credit usage. An operator's `reviewed` outcome only says the recorded review happened; it does not turn unknown facts into supported ones.

Latest `reviewed` notes leave the pending operator queue; `needs_research` notes stay. Research without readable sources cannot be marked reviewed through this command. API reads and JSON/CSV exports preserve the latest operator note separately from the customer review. CSV names the new column `operator_review_json`. Full note history remains available through the scoped operator command.

## Persistence and access

Notes append to their own table and include a server-generated identity, timestamp and hash of the exact immutable stored research snapshot. Two simultaneous notes against the same previous ID cannot silently replace each other: one succeeds, the other must read the new history and retry. Replaying the same command returns its existing note; changing payload under the same key fails. At most 100 notes can be recorded per sheet.

Alternative considered: updating a second mutable review field on the company row. That would erase corrections and conflate current display with audit history. The separate append-only table preserves history and leaves existing customer acceptance untouched. It is scoped through forced Postgres row policies; customer API credentials can read but cannot insert, update or delete notes directly. Assigned worker credentials can append but cannot rewrite or delete notes directly. The unassigned scheduler cannot annotate.

Deleting the owning research cascades to its annotations, including note text and reviewer labels. This exception follows the application's research deletion policy; it does not claim forensic erasure of database storage or backups. Operator notes are not financial ledger entries and are not retained to enforce signup/spending allowances. Retention uses the existing pipeline update time, not the time a note was added.

Migration 008 adds this hosted table and its composite run/record/workspace foreign key. Never edit prior applied migrations. Before using this workflow with real customers, verify operator access procedures and the remaining real-account and deployment gates. No external human review or paid pilot is claimed by the implementation tests.

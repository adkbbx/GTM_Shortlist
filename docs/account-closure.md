# Managed account closure

The bounded server-operator command and workspace access guard are implemented and covered with real Postgres and labelled Supabase transports. No real Supabase identity has been deleted by development tests.

## Operator command

Copy deploy/closure.env.example to the ignored deploy/secrets/closure.env and provide the customer's exact project configuration, restricted worker login and a dedicated current Supabase sb_secret_ admin key. Never put this key in the regular API/worker environment, browser or repository. Apply migration009 before using the updated hosted runtime. Use the same worker login in both database variables; no migration/superuser credential is needed.

After verifying the customer's closure request and preserving any export they requested, invoke the reviewed image without publishing ports:

```sh
docker run --rm --env-file deploy/secrets/closure.env --entrypoint python gtm-shortlist:COMMIT -m shortlist.cli close-account --workspace WORKSPACE_UUID --confirm WORKSPACE_UUID
```

Replace both workspace placeholders with the same exact user/workspace UUID. The command also works as shortlist close-account in a trusted server environment with those variables already configured. It rejects local mode, missing admin/worker configuration and a mismatched confirmation. A remaining closing state prints honest progress and exits2; repeat only after checking the reason. Closed prints confirmed completion and exits0. Secure and remove the temporary admin environment when the operation is finished. No recurring closure task is installed.

## Design

Use a server-only operator command with an explicit workspace UUID and a matching confirmation UUID. Keep the Supabase admin secret out of the browser, regular API configuration and research worker environment. No account-closure mutation endpoint or customer button is introduced in this step.

The personal workspace moves through open, closing and closed. Before closing, verify the configured admin credential against the exact Auth user and reject queued/running research. The short database transition freezes further app access and new jobs. Erase at most100 inactive research runs per command using existing deletion/tombstone behavior. Repeat the command to process any remaining runs. Delete the Supabase identity only after app research is erased, then mark the workspace closed. Keep network calls outside database transactions.

If an identity deletion times out or fails, leave the workspace closing. It remains inaccessible while an operator resolves the provider problem and repeats the same command. A confirmed user-not-found response is success on retry; an arbitrary404 is not. Successful identity deletion followed by process death is recoverable because the next call confirms absence and finishes the database transition. A closed workspace cannot receive a new signup grant, restart research or reopen via the same user UUID.

Alternative considered: delete the database workspace and Auth user together inside one database transaction. Supabase's remote API cannot participate in that transaction; a timeout would leave an ambiguous outcome, and deleting the local workspace could recreate the signup allowance. The persistent monotonic lifecycle keeps that uncertainty explicit and allows retry.

## Boundaries still required for release

Customer self-service, operator authorization procedures, an actual Supabase deletion/retry test and production retention/backup terms remain gates. Supabase user deletion removes refresh sessions but cannot retroactively invalidate an already-issued stateless access token. This app therefore also checks the workspace lifecycle before protected data access and again after acquiring mutation locks. Requests that began before closure may finish; no successful closure claim implies recall of already-delivered data.

Retain the content-free workspace/run identities, once-only signup decision, provider attempt counts and credit ledger under the existing spending policy. Ledger business keys/descriptions can retain company-domain identifiers and financial metadata; do not describe this as complete erasure of all associated information. Define and publish the precise retained fields, durations and restoration/deletion replay policy before launch. This step does not introduce email fingerprinting or claim prevention of a new free grant to a different Auth UUID.

Sources: [Supabase user deletion and sessions](https://supabase.com/docs/guides/auth/managing-user-data), [server-only Auth administration](https://supabase.com/docs/reference/python/admin-api), [current secret-key headers](https://supabase.com/docs/guides/getting-started/api-keys).

import argparse
import json
import os
import sys
from datetime import timedelta
from pathlib import Path
from uuid import UUID

from shortlist.config import Settings
from shortlist.domain import OperatorReviewCommand, Profile, utcnow
from shortlist.export import export_run
from shortlist.local_server import serve
from shortlist.providers import CapturedSearch
from shortlist.store import Store
from shortlist.worker import execute_run, work

# Plans until payments exist: operator grants on top of the 3 free signup credits, never a payment.
# "pro" is a customer-facing test plan; "dev" is internal and only for workspaces in SHORTLIST_INTERNAL_WORKSPACES.
PLAN_CREDITS = {"pro": 50, "dev": 500}


def internal_workspaces() -> set[UUID]:
    values = (value.strip() for value in os.getenv("SHORTLIST_INTERNAL_WORKSPACES", "").split(","))
    try:
        return {UUID(value) for value in values if value}
    except ValueError:
        raise SystemExit("SHORTLIST_INTERNAL_WORKSPACES must be comma-separated Supabase user IDs") from None


def main():
    parser = argparse.ArgumentParser(description="GTM Shortlist evidence-first research")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("config")
    run = sub.add_parser("run")
    run.add_argument("profile", type=Path)
    run.add_argument("--request-key", required=True)
    run.add_argument("--search-capture", type=Path, help="Replay a labelled, saved external search capture")
    resume = sub.add_parser("resume")
    resume.add_argument("run_id")
    worker = sub.add_parser("worker")
    worker.add_argument("--once", action="store_true")
    server = sub.add_parser("serve", help="Start the local API and research worker together")
    server.add_argument("--port", type=int, choices=range(1024, 65536), default=8014, metavar="PORT")
    server.add_argument("--open", action="store_true", help="Open the app in your browser once it is ready")
    show = sub.add_parser("show")
    show.add_argument("run_id")
    export = sub.add_parser("export")
    export.add_argument("run_id")
    export.add_argument("--format", choices=("json", "csv", "xlsx"), default="json")
    export.add_argument("--output", type=Path, help="Save the export to this file (required for Excel)")
    export.add_argument("--accepted-only", action="store_true")
    retention = sub.add_parser("retention", help="Preview or erase old inactive research; never resets credits")
    retention.add_argument("--older-than-days", type=int, choices=range(1, 3651), required=True, metavar="DAYS")
    retention.add_argument("--apply", action="store_true", help="Erase the previewed eligible content (up to100 per command)")
    queue = sub.add_parser("review-queue", help="Read-only triage of pending operator reviews (up to25)")
    queue.add_argument("--workspace", type=UUID, help="Required explicit workspace for hosted operator access")
    annotation = sub.add_parser("annotate", help="Append an independent operator review from a JSON command file")
    annotation.add_argument("command_file", type=Path)
    annotation.add_argument("--workspace", type=UUID)
    history = sub.add_parser("review-history", help="Inspect up to100 saved operator notes for a company sheet")
    history.add_argument("run_id")
    history.add_argument("record_id")
    history.add_argument("--workspace", type=UUID)
    closure = sub.add_parser("close-account", help="Server-only irreversible managed account closure (up to100 runs per call)")
    closure.add_argument("--workspace", type=UUID, required=True)
    closure.add_argument("--confirm", type=UUID, required=True, help="Repeat the exact workspace UUID to confirm closure")
    grant = sub.add_parser("grant-credits", help="Server-only operator credit grant for testing or an agreed pilot; never a payment")
    grant.add_argument("--workspace", type=UUID, required=True, help="The account's Supabase user ID; it must have signed in once")
    grant.add_argument("--plan", choices=tuple(PLAN_CREDITS), help="pro adds 50 credits; dev (internal accounts only) adds 500")
    grant.add_argument("--credits", type=int, choices=range(1, 10001), metavar="1-10000", help="Exact credits instead of a plan")
    grant.add_argument("--key", help="Operation key; repeating a key never grants twice (default: plan, credits and date)")
    args = parser.parse_args()
    settings = Settings.load()
    if args.command not in ("serve", "worker", "close-account"):
        from shortlist.local_credentials import apply_local_credentials
        settings = apply_local_credentials(settings)
    if args.command == "close-account":
        from shortlist.account_closure import close_account
        result = close_account(settings, args.workspace, args.confirm)
        print(result.model_dump_json())
        if result.state == "closing":
            raise SystemExit(2)
        return
    if args.command == "grant-credits":
        if settings.mode != "hosted" or not settings.worker_database_url.get_secret_value():
            parser.error("Credit grants are hosted-only and need the separate worker database credential")
        if (args.plan is None) == (args.credits is None):
            parser.error("Choose exactly one of --plan or --credits")
        if args.plan == "dev" and args.workspace not in internal_workspaces():
            parser.error("dev is internal: add this Supabase user ID to SHORTLIST_INTERNAL_WORKSPACES first")
        quantity = args.credits or PLAN_CREDITS[args.plan]
        key = args.key or f"operator-{args.plan or 'credits'}-{quantity}-{utcnow():%Y-%m-%d}"
        label = f"{args.plan.title()} test plan" if args.plan else "Operator credits"
        import psycopg

        from shortlist.credits import CreditWallet
        from shortlist.postgres import PostgresStore
        wallet = CreditWallet(PostgresStore(settings.worker_database_url, args.workspace, worker=True))
        try:
            wallet.grant(quantity, key, f"{label}: operator grant, no payment")
        except psycopg.errors.ForeignKeyViolation:
            parser.error("No workspace for this user yet: sign in once with the account, then grant credits")
        print(json.dumps({"workspace": str(args.workspace), "granted": quantity, "operation_key": key,
                          **wallet.balance().model_dump()}))
        return
    if args.command == "config":
        print(json.dumps({"db": str(settings.db_path), "providers": settings.readiness()}))
        return
    if args.command == "worker":
        work(settings, args.once)
        return
    if args.command in ("review-queue", "annotate", "review-history"):
        if settings.mode == "hosted":
            if args.workspace is None or not settings.worker_database_url.get_secret_value():
                parser.error("Hosted operator access requires an explicit workspace and the separate worker credential")
            from shortlist.postgres import PostgresStore
            store = PostgresStore(settings.worker_database_url, args.workspace, worker=True)
        else:
            if args.workspace is not None:
                parser.error("Local research has one operator; no hosted workspace selector")
            store = Store(settings.db_path)
        if args.command == "annotate":
            command = OperatorReviewCommand.model_validate_json(args.command_file.read_text(encoding="utf-8"))
            result = store.annotate(command)
        elif args.command == "review-history":
            result = store.operator_history(args.run_id, args.record_id)
        else:
            from shortlist.review_queue import review_queue
            result = review_queue(store)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.command == "retention":
        if settings.mode == "hosted":
            if not settings.worker_database_url.get_secret_value():
                parser.error("Hosted retention requires the separate worker database credential")
            from shortlist.postgres import PostgresStore
            store = PostgresStore(settings.worker_database_url, None, worker=True)
        else:
            store = Store(settings.db_path)
        candidates = store.retention_candidates(utcnow() - timedelta(days=args.older_than_days))
        for identity in candidates if args.apply else ():
            scoped = store.for_run(identity) if settings.mode == "hosted" else store
            scoped.delete_run(identity)
        print(json.dumps({"dry_run": not args.apply, "run_ids": candidates, "batch_limit": 100}))
        return
    if settings.mode == "hosted":
        parser.error("Hosted research commands require verified API access; launch API and worker separately")
    store = Store(settings.db_path)
    if args.command == "run":
        profile = Profile.model_validate_json(args.profile.read_text(encoding="utf-8"))
        run_id = store.create_run(profile, args.request_key)
        print(run_id)
        execute_run(store, settings, run_id, search=CapturedSearch(args.search_capture) if args.search_capture else None)
    elif args.command == "resume":
        execute_run(store, settings, args.run_id)
    elif args.command == "serve":
        serve(settings, args.port, args.open)
    elif args.command == "show":
        print(json.dumps(store.get_run(args.run_id), ensure_ascii=False, indent=2))
    elif args.command == "export":
        if args.format == "xlsx" and args.output is None:
            parser.error("Excel export requires --output FILE.xlsx")
        content = export_run(store.get_run(args.run_id), args.format, args.accepted_only)
        if args.output:
            if isinstance(content, bytes):
                args.output.write_bytes(content)
            else:
                args.output.write_text(content, encoding="utf-8")
        else:
            print(content)


def home_database() -> Path:
    """Where the installed app keeps research, so it does not depend on the folder the command runs from."""
    if os.name == "nt" and os.getenv("LOCALAPPDATA"):
        folder = Path(os.environ["LOCALAPPDATA"]) / "GTM Shortlist"
    elif sys.platform == "darwin":
        folder = Path.home() / "Library" / "Application Support" / "GTM Shortlist"
    else:
        folder = Path(os.getenv("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "gtm-shortlist"
    return folder / "shortlist.sqlite3"


def start():
    """`gtm-shortlist` (for example `uvx gtm-shortlist`): the whole local app in one command, opened in the browser."""
    parser = argparse.ArgumentParser(prog="gtm-shortlist", description="Run GTM Shortlist on this computer and open it in your browser.")
    parser.add_argument("--port", type=int, choices=range(1024, 65536), default=8014, metavar="PORT")
    parser.add_argument("--no-browser", action="store_true", help="Start without opening a browser tab")
    args = parser.parse_args()
    os.environ["SHORTLIST_MODE"] = "local"
    os.environ.setdefault("SHORTLIST_DB", str(home_database()))
    settings = Settings.load()
    print(f"Research is saved in {settings.db_path.resolve().parent}", flush=True)
    serve(settings, args.port, open_browser=not args.no_browser)


if __name__ == "__main__":
    main()

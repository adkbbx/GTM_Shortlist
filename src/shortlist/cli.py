import argparse
import json
from datetime import timedelta
from pathlib import Path

from shortlist.config import Settings
from shortlist.domain import Profile, utcnow
from shortlist.export import export_run
from shortlist.local_server import serve
from shortlist.providers import CapturedSearch
from shortlist.store import Store
from shortlist.worker import execute_run, work


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
    show = sub.add_parser("show")
    show.add_argument("run_id")
    export = sub.add_parser("export")
    export.add_argument("run_id")
    export.add_argument("--format", choices=("json", "csv"), default="json")
    export.add_argument("--accepted-only", action="store_true")
    retention = sub.add_parser("retention", help="Preview or erase old inactive research; never resets credits")
    retention.add_argument("--older-than-days", type=int, choices=range(1, 3651), required=True, metavar="DAYS")
    retention.add_argument("--apply", action="store_true", help="Erase the previewed eligible content (up to100 per command)")
    args = parser.parse_args()
    settings = Settings.load()
    if args.command == "config":
        print(json.dumps({"db": str(settings.db_path), "providers": settings.readiness()}))
        return
    if args.command == "worker":
        work(settings, args.once)
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
        serve(settings, args.port)
    elif args.command == "show":
        print(json.dumps(store.get_run(args.run_id), ensure_ascii=False, indent=2))
    elif args.command == "export":
        print(export_run(store.get_run(args.run_id), args.format, args.accepted_only))


if __name__ == "__main__":
    main()

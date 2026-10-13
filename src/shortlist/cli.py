import argparse
import json
from pathlib import Path

from shortlist.config import Settings
from shortlist.domain import Profile
from shortlist.export import export_run
from shortlist.store import Store
from shortlist.worker import execute_run, work


def main():
    parser = argparse.ArgumentParser(description="GTM Shortlist evidence-first research")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("config")
    run = sub.add_parser("run")
    run.add_argument("profile", type=Path)
    run.add_argument("--request-key", required=True)
    resume = sub.add_parser("resume")
    resume.add_argument("run_id")
    worker = sub.add_parser("worker")
    worker.add_argument("--once", action="store_true")
    show = sub.add_parser("show")
    show.add_argument("run_id")
    export = sub.add_parser("export")
    export.add_argument("run_id")
    export.add_argument("--format", choices=("json", "csv"), default="json")
    export.add_argument("--accepted-only", action="store_true")
    args = parser.parse_args()
    settings = Settings.load()
    if args.command == "config":
        print(json.dumps({"db": str(settings.db_path), "providers": settings.readiness()}))
        return
    store = Store(settings.db_path)
    if args.command == "run":
        profile = Profile.model_validate_json(args.profile.read_text(encoding="utf-8"))
        run_id = store.create_run(profile, args.request_key)
        print(run_id)
        execute_run(store, settings, run_id)
    elif args.command == "resume":
        execute_run(store, settings, args.run_id)
    elif args.command == "worker":
        work(settings, args.once)
    elif args.command == "show":
        print(json.dumps(store.get_run(args.run_id), ensure_ascii=False, indent=2))
    elif args.command == "export":
        print(export_run(store.get_run(args.run_id), args.format, args.accepted_only))


if __name__ == "__main__":
    main()

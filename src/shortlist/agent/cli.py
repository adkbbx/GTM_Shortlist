"""`shortlist agent run <website>` and `shortlist agent eval <labels.csv>`."""
import argparse
import sys
from datetime import timedelta
from pathlib import Path

from shortlist.agent.evaluation import batches, combine, describe, read_labels, score, without_skeptic
from shortlist.agent.models import MAX_COMPANIES, Overrides, RunResult
from shortlist.agent.pipeline import AgentRunner, Providers
from shortlist.agent.providers import AgentProviderError
from shortlist.agent.service import real_providers, website_url
from shortlist.agent.settings import AgentSettings
from shortlist.agent.storage import HISTORY_DAYS, SQLiteAgentRuns
from shortlist.domain import utcnow
from shortlist.fetch import FetchError, domain_of

LABEL = {"shortlisted": "Shortlisted", "needs_look": "Needs a look", "rejected": "Rejected"}


def providers_for(args, settings: AgentSettings) -> Providers:
    if args.synthetic:
        from shortlist.agent.synthetic import synthetic_providers
        return synthetic_providers()
    return real_providers(settings)


def print_event(event):
    where = f" [{event.company}]" if event.company else ""
    print(f"{event.stage}{where}: {event.message}", file=sys.stderr, flush=True)


def summary(result: RunResult) -> str:
    lines = [f"Run {result.id}: {result.status}" + (" (SYNTHETIC TEST DATA)" if result.synthetic else "")
             + ("" if result.skeptic else " (no skeptic)")]
    if result.error:
        lines.append(f"  {result.error}")
    for company in result.companies:
        verdict = company.verdict
        if verdict is None:
            continue
        lines.append(f"  {LABEL[verdict.kind]}: {company.domain} - {verdict.summary}")
        if verdict.disqualifier:
            lines.append(f'      "{verdict.disqualifier.quote.text}" ({verdict.disqualifier.quote.url})')
        lines += [f"      missing: {item}" for item in verdict.missing]
    t = result.telemetry
    lines.append(f"  {t.model_calls} model calls, {t.searches} searches, {t.pages_fetched} pages, "
                 f"${t.cost_usd:.4f} estimated, {t.elapsed_ms / 1000:.1f}s" + (" (budget reached)" if t.budget_reached else ""))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="shortlist agent", description="Website-only research agent")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Research companies for a seller website")
    run.add_argument("website")
    run.add_argument("--companies", type=int, choices=range(1, MAX_COMPANIES + 1), metavar=f"1-{MAX_COMPANIES}")
    run.add_argument("--output", type=Path, help="Write the full run JSON to this file")
    run.add_argument("--no-skeptic", action="store_true", help="Ablation: accept grounded quotes without the skeptic")
    run.add_argument("--synthetic", action="store_true", help="Use the labelled synthetic test world: no network")
    run.add_argument("--no-save", action="store_true", help="Do not save the run in the local database")
    evaluate = sub.add_parser("eval", help="Score verdicts against a labelled CSV")
    evaluate.add_argument("labels", type=Path)
    source = evaluate.add_mutually_exclusive_group(required=True)
    source.add_argument("--website", help="Seller website: research exactly the labelled domains")
    source.add_argument("--run", type=Path, help="Score a saved run JSON without any model call")
    evaluate.add_argument("--no-skeptic", action="store_true", help="Ablation without the skeptic")
    evaluate.add_argument("--synthetic", action="store_true", help="Use the labelled synthetic test world: no network")
    evaluate.add_argument("--output", type=Path, help="Write the report JSON to this file")
    args = parser.parse_args(argv)

    if args.command == "eval":
        try:
            labels = read_labels(args.labels)
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
        if args.run:
            result = RunResult.model_validate_json(args.run.read_text(encoding="utf-8"))
            if args.no_skeptic:
                result = without_skeptic(result)
        else:
            parts = []
            for batch in batches(labels, MAX_COMPANIES):
                part = execute(args, args.website, domains=[label.domain for label in batch], save=False)
                if part is None:
                    return 2
                parts.append(part)
            result = combine(parts)
        report = score(result, labels)
        print(describe(report))
        if args.output:
            args.output.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        return 0

    result = execute(args, args.website, count=args.companies, save=not args.no_save)
    if result is None:
        return 2
    print(summary(result))
    if args.output:
        args.output.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        print(f"Saved {args.output}", file=sys.stderr)
    return 0 if result.status in ("complete", "needs_choice") else 1


def execute(args, website: str, *, count: int | None = None, domains: list[str] | None = None,
            save: bool = True) -> RunResult | None:
    settings = AgentSettings.load()
    if args.no_skeptic:
        settings = settings.model_copy(update={"use_skeptic": False})
    try:
        url = website_url(website)
        providers = providers_for(args, settings)
    except (FetchError, AgentProviderError) as exc:
        print(f"Cannot start: {exc}", file=sys.stderr)
        return None
    store = None
    if save:
        from shortlist.config import Settings
        store = SQLiteAgentRuns(Settings.load().db_path)
    runner = AgentRunner(providers, budget_usd=settings.run_budget_usd, concurrency=settings.concurrency,
                         use_skeptic=settings.use_skeptic, on_event=print_event,
                         on_save=store.save if store else None)
    if store is not None:
        events = []
        runner.on_event = lambda event: (print_event(event), events.append(event))
    # Saved runs remember what was researched for this seller; a labelled list (eval) is researched as given.
    history = store.researched(domain_of(url), utcnow() - timedelta(days=HISTORY_DAYS)) if store and not domains else None
    result = runner.run(url, Overrides(company_count=count) if count else None, domains=domains, history=history)
    if store is not None:
        for event in events:
            store.append_event(result.id, event)
        print(f"Saved run {result.id}; open it at /?agent={result.id}", file=sys.stderr)
    return result


if __name__ == "__main__":
    raise SystemExit(main())

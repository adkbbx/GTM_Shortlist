"""Construct labelled semantic evaluation inputs without network discovery."""
import hashlib
from datetime import UTC, datetime

from shortlist.domain import Criterion, Profile, Source
from shortlist.providers import validate_extraction


def semantic_case(case: dict):
    is_exclusion = case["kind"] == "exclusion"
    profile = Profile(seller_url="https://seller.example", offer="Labelled semantic evaluation only",
                      target="Synthetic evaluation company",
                      criteria=(Criterion(id="check", description=case["condition"] if not is_exclusion else
                                          "Company identity is established", required=not is_exclusion),),
                      exclusions=(case["condition"],) if is_exclusion else ())
    source = Source(id="source-" + case["id"], url="https://company.example", company_domain="company.example",
                    title=case["provenance"], text=case["source_text"],
                    content_hash=hashlib.sha256(case["source_text"].encode()).hexdigest(),
                    retrieved_at=datetime(2026, 10, 14, tzinfo=UTC))
    finding = {"status": case["status"], "exclusion_id" if is_exclusion else "criterion_id":
               "exclude-1" if is_exclusion else "check", "evidence": [
                   {"source_id": source.id, "passage": case["passage"], "claim": case["claim"]}]}
    record = validate_extraction({"name": "Labelled evaluation company", "findings": [] if is_exclusion else [finding],
                                 "exclusion_findings": [finding] if is_exclusion else []},
                                profile, source.company_domain, (source,))
    return profile, record

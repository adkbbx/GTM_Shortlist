"""Shortlist order: the companies with the most supporting evidence first. An ordering aid, never a fit score."""

QUALIFICATION_ORDER = {"fits": 0, "needs_verification": 1, "does_not_fit": 2}


def evidence_key(profile: dict, research: dict) -> tuple[int, int, int, int]:
    criteria = (profile or {}).get("criteria", [])
    status = {finding["criterion_id"]: finding["status"] for finding in research.get("findings", [])}
    required = [criterion["id"] for criterion in criteria if criterion.get("required", True)]
    optional = [criterion["id"] for criterion in criteria if not criterion.get("required", True)]
    return (QUALIFICATION_ORDER.get(research.get("qualification"), 1),
            -sum(status.get(identifier) == "supported" for identifier in required),
            -sum(status.get(identifier) == "supported" for identifier in optional),
            sum(status.get(identifier) == "unknown" for identifier in required))


def by_evidence(profile: dict, records: list[dict]) -> list[dict]:
    """Fits first, then unverified companies by how many required checks are supported, then mismatches. Stable, so
    equally supported companies keep their research order. A Needs-verification company with three of four required
    checks supported is a better next call than one with none; both remain unverified until checked."""
    return sorted(records, key=lambda record: evidence_key(profile, record["research"]))

"""Model-free competitor scan of a company's fetched pages: script sources, badges, "powered by" lines and
integrations pages. A hit is only a candidate: the skeptic still has to agree it shows current use."""
import re
from urllib.parse import urlsplit

from shortlist.agent.models import Competitor, EvidenceItem, PageSignature, Quote

PLACE = {"script": "script source", "link": "linked stylesheet or resource", "iframe": "embedded frame",
         "img": "badge or logo", "a": "link", "source": "embedded media", "embed": "embedded media"}


def rule_id(competitor_domain: str) -> str:
    return f"uses_direct_competitor:{competitor_domain}"


def brand_names(competitor: Competitor) -> list[str]:
    """Words that name the competitor in text: its name, and its domain without the suffix."""
    names = {" ".join(competitor.name.split())}
    stem = competitor.domain.split(".")[0]
    names |= {stem, stem.replace("-", " "), stem.replace("-", "")}
    # Short or generic stems ("app", "go") would match ordinary words.
    return sorted((name for name in names if len(name.replace(" ", "")) >= 4), key=len, reverse=True)


def _named(text: str, competitor: Competitor) -> bool:
    lowered = text.casefold()
    if competitor.domain in lowered:
        return True
    return any(re.search(r"(?<![\w-])" + re.escape(name.casefold()) + r"(?![\w-])", lowered)
               for name in brand_names(competitor))


def _host_matches(value: str, domain: str) -> bool:
    try:
        host = (urlsplit(value if "//" in value else "https://" + value).hostname or "").casefold()
    except ValueError:
        return False
    return host == domain or host.endswith("." + domain)


def scan(signature: PageSignature, competitors: list[Competitor], company: str) -> list[EvidenceItem]:
    hits: list[EvidenceItem] = []
    seen: set[tuple[str, str]] = set()

    def hit(competitor: Competitor, place: str, text: str, location: str):
        key = (competitor.domain, text)
        if key in seen:
            return
        seen.add(key)
        where = "homepage" if signature.kind == "homepage" else "integrations page" \
            if signature.kind == "integrations" else "page"
        hits.append(EvidenceItem(
            claim_type="disqualifier", criterion_id=rule_id(competitor.domain), found_by="scan",
            claim=f"{competitor.name} appears in the {where} {place} of {company}",
            quote=Quote(text=text[:1500], url=signature.url, source_type="own_site",
                        fetched_at=signature.fetched_at, location=location)))

    for competitor in competitors:
        for attribute in signature.attributes:
            if attribute.attr in ("src", "href"):
                if _host_matches(attribute.value, competitor.domain):
                    hit(competitor, PLACE.get(attribute.tag, "code"), attribute.value, "html")
            elif _named(attribute.value, competitor):
                hit(competitor, PLACE.get(attribute.tag, "code") + " text", attribute.value, "html")
        for line in signature.powered_by:
            if _named(line, competitor):
                hit(competitor, '"powered by" line', line, "text")
        for line in signature.lines:
            if _named(line, competitor):
                hit(competitor, "listing", line, "text")
    return hits

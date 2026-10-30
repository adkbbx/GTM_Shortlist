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


# Vendors serve their widgets from other domains than their website; a scan by website domain alone missed them.
VENDOR_HOSTS = {
    "intercom.com": ("intercom.io", "intercomcdn.com"), "zendesk.com": ("zdassets.com", "zopim.com", "zendesk.co.jp"),
    "drift.com": ("driftt.com",), "livechat.com": ("livechatinc.com",), "tidio.com": ("tidio.co",),
    "hubspot.com": ("hs-scripts.com", "hsforms.net", "hs-analytics.net", "hubspot.net", "usemessages.com"),
    "freshdesk.com": ("freshworks.com", "freshchat.com"), "gorgias.com": ("gorgias.chat", "gorgias.io"),
    "helpscout.com": ("helpscout.net",), "frontapp.com": ("front.com",),
}
# A host label that is the brand plus a common hosting suffix ("intercomcdn", "livechatinc") is the vendor's own.
HOST_SUFFIXES = ("", "cdn", "inc", "app", "hq", "static", "assets", "js")


def _host(value: str) -> str:
    try:
        return (urlsplit(value if "//" in value else "https://" + value).hostname or "").casefold()
    except ValueError:
        return ""


def _vendor_host(value: str, competitor: Competitor) -> bool:
    """The competitor's website domain, a known widget domain of that vendor, or a host label that is its brand."""
    host = _host(value)
    if not host:
        return False
    domains = (competitor.domain, *VENDOR_HOSTS.get(competitor.domain, ()))
    if any(host == domain or host.endswith("." + domain) for domain in domains):
        return True
    stem = competitor.domain.split(".")[0].casefold()
    return len(stem) >= 5 and any(label == stem + suffix for label in host.split(".")[:-1] for suffix in HOST_SUFFIXES)


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
            if attribute.attr == "inline":
                if _vendor_host(attribute.value, competitor):
                    hit(competitor, "inline script", attribute.value, "html")
            elif attribute.attr in ("src", "href"):
                if _vendor_host(attribute.value, competitor):
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

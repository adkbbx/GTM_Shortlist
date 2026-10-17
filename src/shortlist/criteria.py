"""Fit checks a company's own website almost never states. Mirrors web/criteria.ts, which advises on confirmation.

In saved research every such required check stayed unknown (ownership 16 of 16, funding stage 3 of 3, internal pains 15
of 15), so it held every company at Needs verification. Drafted checks like these start as nice to have: they still
order the shortlist when a page happens to state them, and remain questions for a conversation.
"""
import re

RARELY_PUBLIC = (
    # Ownership and funding: in investor databases and press, rarely on the company's own pages.
    re.compile(r"\b(?:privately[- ]held|privately owned|publicly (?:traded|listed)|ownership|owned by|funding (?:stage|round)|"
               r"funded by|recently funded|venture[- ]backed|vc[- ]backed|pe[- ]backed|backed by (?:investors|venture|private equity)|"
               r"pre-seed|seed[- ]stage|series [a-e]\b|raised (?:a |an )?(?:\$|seed|series|funding|capital|round))", re.IGNORECASE),
    # Financial thresholds and budgets.
    re.compile(r"\b(?:revenue|arr|mrr|turnover)\s+(?:of|above|over|under|below|between|exceeding|greater|less|more)\b|"
               r"[$€£]\s?\d[\d.,]*\s?[kmb]?\+?\s+(?:in\s+)?(?:revenue|arr|mrr|turnover|budget)|\bprofitab\w*|"
               r"\bbudgets?\s+(?:for|of|over|above|to)\b|\b(?:growth|burn) rate\b", re.IGNORECASE),
    # Internal states, pains and intent: what a company thinks or plans, not what it publishes.
    re.compile(r"\b(?:unsure|uncertain\w*|struggl\w*|frustrat\w*|lacks?|lacking|wants? to|wish\w* to|plans? to|planning to|"
               r"looking (?:for|to)|evaluating|in[- ]market|buying intent|pain points?|(?:does not|doesn't|don't|do not) know|"
               r"(?:without|not) knowing|needs? (?:to|help|a|an|more|better))\b", re.IGNORECASE),
)


def rarely_public(description: str) -> bool:
    return any(pattern.search(description) for pattern in RARELY_PUBLIC)

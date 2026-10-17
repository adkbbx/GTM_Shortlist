/* Fit checks a company's own website almost never states. In saved research every one of them stayed unknown (16 of 16
   ownership checks, 3 of 3 funding-stage checks, 15 of 15 internal-pain checks), so as required checks they hold every
   company at Needs verification. They are still worth asking about in a conversation; this only advises the target. */
const rarelyPublic = [
  // Ownership and funding: in investor databases and press, rarely on the company's own pages.
  /\b(?:privately[- ]held|privately owned|publicly (?:traded|listed)|ownership|owned by|funding (?:stage|round)|funded by|recently funded|venture[- ]backed|vc[- ]backed|pe[- ]backed|backed by (?:investors|venture|private equity)|pre-seed|seed[- ]stage|series [a-e]\b|raised (?:a |an )?(?:\$|seed|series|funding|capital|round))/i,
  // Financial thresholds and budgets.
  /\b(?:revenue|arr|mrr|turnover)\s+(?:of|above|over|under|below|between|exceeding|greater|less|more)\b|[$€£]\s?\d[\d.,]*\s?[kmb]?\+?\s+(?:in\s+)?(?:revenue|arr|mrr|turnover|budget)|\bprofitab\w*|\bbudgets?\s+(?:for|of|over|above|to)\b|\b(?:growth|burn) rate\b/i,
  // Internal states, pains and intent: what a company thinks or plans, not what it publishes.
  /\b(?:unsure|uncertain\w*|struggl\w*|frustrat\w*|lacks?|lacking|wants? to|wish\w* to|plans? to|planning to|looking (?:for|to)|evaluating|in[- ]market|buying intent|pain points?|(?:does not|doesn't|don't|do not) know|(?:without|not) knowing|needs? (?:to|help|a|an|more|better))\b/i,
];

export function rarelyPublicCheck(description: string): boolean {
  return rarelyPublic.some(pattern => pattern.test(description));
}

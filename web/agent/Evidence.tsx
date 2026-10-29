import { useId } from 'react';
import type { ReactNode } from 'react';
import { domainOf, quoteLink } from './agent-api';
import type { Company, EvidenceItem, Quote } from './agent-api';

const sourceLabel: { [kind in Quote['source_type']]: string } = {
  own_site: 'Company site', job_post: 'Job post', news: 'News', review: 'Review site',
  competitor_site: 'Competitor site', other: 'Other site',
};
const day = (value: string) => new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(value));
const pathOf = (url: string) => { try { const path = new URL(url).pathname; return path === '/' ? '' : path; } catch { return ''; } };

/** An exact quote. The words link to the source page, scrolled to the quote where the browser supports it. */
export function QuoteBlock({ quote }: { quote: Quote }) {
  return <figure className="agent-quote">
    <a className="agent-quote-text" href={quoteLink(quote)} target="_blank" rel="noopener noreferrer">“{quote.text}”</a>
    <figcaption>
      <span>{domainOf(quote.url)}{pathOf(quote.url)}</span>
      <span>{sourceLabel[quote.source_type]}{quote.location === 'html' ? ', found in the page code' : ''}</span>
      <span>{quote.published_date ? `Published ${day(quote.published_date)}` : 'Publication date not stated'}</span>
      {quote.open_posting && <span>Job post open when read</span>}
      <span>Read {day(quote.fetched_at)}</span>
    </figcaption>
  </figure>;
}

/** A compact label that opens its quotes and optional edit controls in a native popover. */
export function Chip({ label, tag, quotes, note, off = false, tone = 'neutral', children }: {
  label: string; tag?: string; quotes: Quote[]; note?: string; off?: boolean;
  tone?: 'neutral' | 'good' | 'bad' | 'open'; children?: ReactNode;
}) {
  const id = `chip-${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`;
  return <>
    <button type="button" className={`agent-chip tone-${tone}${off ? ' is-off' : ''}`} popoverTarget={id}
      aria-label={`${label}${tag ? `, ${tag}` : ''}${off ? ', not used' : ''}. Show the quote`}>
      <span className="agent-chip-label">{label}</span>{tag && <span className="agent-chip-tag">{tag}</span>}
    </button>
    <div id={id} popover="auto" className="agent-popover" role="dialog" aria-label={label}>
      <div className="agent-popover-head">
        <p>{label}</p>
        <button type="button" className="agent-popover-close" popoverTarget={id} popoverTargetAction="hide" aria-label="Close">
          <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="m7 7 10 10M17 7 7 17" /></svg>
        </button>
      </div>
      {quotes.length ? quotes.map((quote, index) => <QuoteBlock key={index} quote={quote} />)
        : <p className="agent-popover-note">{note ?? 'No quote: you added this.'}</p>}
      {quotes.length > 0 && note && <p className="agent-popover-note">{note}</p>}
      {children}
    </div>
  </>;
}

const claimLabel: { [kind in EvidenceItem['claim_type']]: string } = {
  fit: 'Fit', need: 'Need', timing: 'Timing', disqualifier: 'Disqualifier',
};
const decisionLabel = { supports: 'Supports', contradicts: 'Contradicts', insufficient: 'Not enough' } as const;

export function EvidenceList({ company, checkName }: { company: Company; checkName: (item: EvidenceItem) => string }) {
  const decisions = new Map(company.decisions.map(decision => [decision.evidence_id, decision]));
  const supported = company.evidence.filter(item => decisions.get(item.id)?.decision === 'supports' && item.claim_type !== 'disqualifier');
  return <>
    {supported.length > 0 && <div className="agent-evidence-chips" aria-label="Supported evidence">
      {supported.map(item => <Chip key={item.id} label={checkName(item)} tag={claimLabel[item.claim_type]} quotes={[item.quote]}
        tone="good" note={`Skeptic: ${decisions.get(item.id)?.reason || 'supports'}`} />)}
    </div>}
    {company.evidence.length > 0 && <details className="agent-all-quotes">
      <summary>All checked quotes ({company.evidence.length})</summary>
      <ul>
        {company.evidence.map(item => {
          const decision = decisions.get(item.id);
          return <li key={item.id}>
            <p className="agent-evidence-line"><span className={`agent-decision ${decision?.decision ?? 'insufficient'}`}>
              {decision ? decisionLabel[decision.decision] : 'Not checked'}</span>{claimLabel[item.claim_type]}: {checkName(item)}</p>
            <QuoteBlock quote={item.quote} />
            {decision?.reason && <p className="agent-decision-reason">{decision.decided_by === 'rule' ? 'Rule' : decision.decided_by === 'no_skeptic' ? 'No skeptic' : 'Skeptic'}: {decision.reason}</p>}
          </li>;
        })}
      </ul>
    </details>}
  </>;
}

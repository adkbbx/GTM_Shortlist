import type { Run } from './api';

type Campaign = NonNullable<Run['market']>['campaigns'][number];

export function MarketOverview({ run, selected, onChoose }: {
  run: Run; selected: string | null; onChoose: (campaign: Campaign) => void;
}) {
  if (!run.market) return null;
  const market = run.market;
  const chosen = market.campaigns.find(campaign => campaign.name === selected);
  return <div className="market-overview">
    <section className="seller-brief" aria-label="Company offer summary"><h3>Your company, in brief</h3>
      <p className="market-domain">{run.seller_url ? new URL(run.seller_url).hostname : run.company_name}</p>
      <p>{run.draft?.offer}</p><p className="hint">Drafted from your website. Correct the offer below before continuing.</p>
      {run.seller_source && <details className="seller-source"><summary>Inspect the saved company page</summary><blockquote>{run.seller_source.text}</blockquote><a href={run.seller_source.url} target="_blank" rel="noopener noreferrer">Open source website</a><p className="hint">Retrieved {new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(run.seller_source.retrieved_at))}. The summary remains a draft for your confirmation.</p></details>}
    </section>
    <section aria-labelledby="competitors-heading"><div className="market-heading"><h3 id="competitors-heading">Explore the market</h3><span>{market.competitors.length} potential competitors</span></div>
      <p className="hint">This search explores similar offers. Relevance still needs verification.</p>
      {market.competitors.length > 0 && <ul className="competitor-list">{market.competitors.map(company => <li key={company.domain}>
        <details><summary>{company.domain}</summary><p>{company.excerpt || 'No search excerpt was returned.'}</p><a href={company.url} target="_blank" rel="noopener noreferrer">Inspect search result</a><p className="hint">Found {new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(company.discovered_at))}. Search observation, not a verified comparison.</p></details>
      </li>)}</ul>}
    </section>
    <section aria-labelledby="campaigns-heading"><div className="market-heading"><h3 id="campaigns-heading">Choose a campaign direction</h3><span>{market.campaigns.length} suggestions</span></div>
      <p className="hint">Campaigns are hypotheses. Apply one to the editable target below, or define your own.</p>
      <div className="campaign-list" role="group" aria-label="Campaign directions">{market.campaigns.map(campaign => <button key={campaign.name} type="button" className="secondary campaign-choice" aria-label={`${selected === campaign.name ? 'Applied' : 'Apply'} ${campaign.name}`} aria-pressed={selected === campaign.name} onClick={() => onChoose(campaign)}>{campaign.name}</button>)}</div>
      {chosen && <div className="campaign-detail"><h4>{chosen.name}</h4><p>{chosen.target}</p><details><summary>Why explore this segment?</summary><p>{chosen.rationale}</p>{chosen.signals_to_check.length > 0 && <><h5>Signals to check</h5><ul>{chosen.signals_to_check.map(signal => <li key={signal}>{signal}</li>)}</ul></>}{chosen.hypotheses.length > 0 && <><h5>Assumptions to test</h5><ul>{chosen.hypotheses.map(hypothesis => <li key={hypothesis}>{hypothesis}</li>)}</ul></>}</details></div>}
    </section>
    {market.issues.length > 0 && <div className="notice" role="status">{market.issues.map(issue => <p key={issue}>{issue}</p>)}</div>}
    {selected && <p className="hint" role="status">Target adapted from {selected}. Review the fields below before confirming.</p>}
  </div>;
}

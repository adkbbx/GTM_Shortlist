import { useEffect, useState } from 'react';
import { SiteIcon } from '../SiteIcon';
import { EmailDialog } from './AgentBoard';
import { agentApi, domainOf, ownSearches } from './agent-api';
import type { AgentRunView, Company } from './agent-api';
import { useAgentConfig } from './agent-config';

type Entry = { company: Company; view: AgentRunView };

/** Runs to gather from: on the public demo only searches this browser started; locally every saved search. */
async function myRuns(publicDemo: boolean): Promise<AgentRunView[]> {
  const ids = publicDemo ? ownSearches().map(own => own.id) : (await agentApi.list()).map(item => item.id).slice(0, 20);
  const views = await Promise.all(ids.map(id => agentApi.run(id).catch(() => null)));
  return views.filter((view): view is AgentRunView => view !== null);
}

const day = (value: string) => new Date(value).toLocaleDateString(undefined, { day: 'numeric', month: 'short' });

function Row({ entry, onOpen }: { entry: Entry; onOpen: (id: string) => void }) {
  const { company, view } = entry;
  const [mail, setMail] = useState(false);
  return <li className="agent-row ys-row">
    <div className="agent-row-main">
      <SiteIcon lookup domain={company.domain} fallback={(company.name || company.domain).slice(0, 1).toUpperCase()} className="agent-logo agent-row-logo" />
      <div className="agent-row-text">
        <div className="agent-row-title"><h3>{company.name || company.domain}</h3>
          <span className="ys-for">for {domainOf(view.run.website)} · {day(view.created_at)}</span></div>
        <p className="agent-row-reason">{company.pitch?.why_now ?? company.verdict?.summary}</p>
      </div>
      <div className="agent-row-actions">
        {company.outreach && <button type="button" className="agent-expand" onClick={() => setMail(true)}>View email</button>}
        <button type="button" className="agent-expand" onClick={() => onOpen(view.id)}>Open search</button>
      </div>
    </div>
    <EmailDialog company={company} open={mail} drafting={false} error="" onClose={() => setMail(false)} />
  </li>;
}

/** Every Shortlisted company from your searches in one list, newest first. */
export function YourShortlist({ onOpen, onNew }: { onOpen: (id: string) => void; onNew: () => void }) {
  const { publicDemo } = useAgentConfig();
  const [entries, setEntries] = useState<Entry[] | null>(null);
  useEffect(() => {
    let cancelled = false;
    myRuns(publicDemo).then(views => {
      if (cancelled) return;
      const seen = new Set<string>();
      const found: Entry[] = [];
      for (const view of [...views].sort((a, b) => b.created_at.localeCompare(a.created_at)))
        for (const company of view.run.companies)
          if (company.verdict?.kind === 'shortlisted' && !seen.has(company.domain)) { seen.add(company.domain); found.push({ company, view }); }
      setEntries(found);
    }).catch(() => { if (!cancelled) setEntries([]); });
    return () => { cancelled = true; };
  }, [publicDemo]);
  return <section className="ys" aria-labelledby="ys-heading">
    <div className="agent-board-head">
      <div><p className="agent-eyebrow">{publicDemo ? 'From searches in this browser' : 'From your searches'}</p>
        <h1 id="ys-heading">Your shortlist</h1></div>
      <div className="agent-board-actions"><button type="button" className="secondary" onClick={onNew}>New search</button></div>
    </div>
    {entries === null ? <p className="agent-status" role="status">Loading your shortlist</p>
      : entries.length === 0 ? <div className="ys-empty"><p>No Shortlisted companies yet.</p>
        <p>Every company that passes a search lands here, with its reason and any email you drafted.</p></div>
        : <><p className="ys-count">{entries.length} {entries.length === 1 ? 'company' : 'companies'}</p>
          <ul className="ys-list">{entries.map(entry => <Row key={entry.company.domain} entry={entry} onOpen={onOpen} />)}</ul></>}
  </section>;
}

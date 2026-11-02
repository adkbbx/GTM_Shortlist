import { useEffect, useState } from 'react';
import { SiteIcon } from '../SiteIcon';
import { EmailDialog } from './AgentBoard';
import { agentApi, domainOf, keepShortlist, keptShortlist, ownSearches } from './agent-api';
import type { Company, KeptShortlist } from './agent-api';
import { useAgentConfig } from './agent-config';

type Search = KeptShortlist & { gone: boolean };
type Entry = { company: Company; search: Search };

/** Searches to gather from: on the public demo only searches this browser started; locally every saved search. A
    search the server no longer has (the free demo forgets them when it restarts) comes from this browser's copy. */
async function mySearches(publicDemo: boolean): Promise<Search[]> {
  const ids = publicDemo ? ownSearches().map(own => own.id) : (await agentApi.list()).map(item => item.id).slice(0, 20);
  const found = await Promise.all(ids.map(async (id): Promise<Search | null> => {
    try {
      const view = await agentApi.run(id);
      keepShortlist(view);
      return { id, website: view.run.website, created_at: view.created_at, companies: view.run.companies, gone: false };
    } catch {
      const kept = keptShortlist(id);
      return kept ? { ...kept, gone: true } : null;
    }
  }));
  return found.filter((search): search is Search => search !== null);
}

const day = (value: string) => new Date(value).toLocaleDateString(undefined, { day: 'numeric', month: 'short' });

function Row({ entry, onOpen }: { entry: Entry; onOpen: (id: string) => void }) {
  const { company, search } = entry;
  const [mail, setMail] = useState(false);
  return <li className="agent-row ys-row">
    <div className="agent-row-main">
      <SiteIcon lookup domain={company.domain} fallback={(company.name || company.domain).slice(0, 1).toUpperCase()} className="agent-logo agent-row-logo" />
      <div className="agent-row-text">
        <div className="agent-row-title"><h3>{company.name || company.domain}</h3>
          <span className="ys-for">for {domainOf(search.website)} · {day(search.created_at)}</span></div>
        <p className="agent-row-reason">{company.pitch?.why_now ?? company.verdict?.summary}</p>
      </div>
      <div className="agent-row-actions">
        {company.outreach && <button type="button" className="agent-expand" onClick={() => setMail(true)}>View email</button>}
        {!search.gone && <button type="button" className="agent-expand" onClick={() => onOpen(search.id)}>Open search</button>}
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
    mySearches(publicDemo).then(searches => {
      if (cancelled) return;
      const seen = new Set<string>();
      const found: Entry[] = [];
      for (const search of [...searches].sort((a, b) => b.created_at.localeCompare(a.created_at)))
        for (const company of search.companies)
          if (company.verdict?.kind === 'shortlisted' && !seen.has(company.domain)) { seen.add(company.domain); found.push({ company, search }); }
      setEntries(found);
    }).catch(() => { if (!cancelled) setEntries([]); });
    return () => { cancelled = true; };
  }, [publicDemo]);
  const gone = entries?.some(entry => entry.search.gone);
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
          {gone && <p className="ys-note" role="note">Some searches are no longer on the server, so their full page cannot open.
            This browser kept their Shortlisted companies and emails.</p>}
          <ul className="ys-list">{entries.map(entry => <Row key={entry.company.domain} entry={entry} onOpen={onOpen} />)}</ul></>}
  </section>;
}

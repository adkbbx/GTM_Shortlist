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
const count = (search: Search, kind: string) => search.companies.filter(c => c.verdict?.kind === kind).length;

function Card({ entry, onOpen }: { entry: Entry; onOpen: (id: string) => void }) {
  const { company, search } = entry;
  const [mail, setMail] = useState(false);
  return <li className="ys-card">
    <div className="ys-card-head">
      <SiteIcon lookup domain={company.domain} fallback={(company.name || company.domain).slice(0, 1).toUpperCase()} className="agent-logo ys-logo" />
      <div className="ys-card-title"><h3>{company.name || company.domain}</h3><p>{company.domain}</p></div>
      <span className="ys-pill">Shortlisted</span>
    </div>
    <p className="ys-why">{company.pitch?.why_now ?? company.verdict?.summary}</p>
    <div className="ys-card-foot">
      <span className="ys-for">From your search for {domainOf(search.website)} · {day(search.created_at)}</span>
      <div className="ys-actions">
        {company.outreach && <button type="button" className="ys-button is-primary" onClick={() => setMail(true)}>View message</button>}
        {!search.gone && <button type="button" className="ys-button" onClick={() => onOpen(search.id)}>Open search</button>}
      </div>
    </div>
    <EmailDialog company={company} open={mail} drafting={false} error="" onClose={() => setMail(false)} />
  </li>;
}

function Searches({ searches, onOpen }: { searches: Search[]; onOpen: (id: string) => void }) {
  return <section className="ys-section" aria-labelledby="ys-searches-heading">
    <h2 id="ys-searches-heading">Your searches</h2>
    <ul className="ys-searches">{searches.slice(0, 12).map(search => <li key={search.id}>
      <SiteIcon lookup domain={domainOf(search.website)} fallback={domainOf(search.website).slice(0, 1).toUpperCase()} className="agent-logo ys-search-logo" />
      <div className="ys-search-text">
        {search.gone ? <strong>{domainOf(search.website)}</strong>
          : <a href={`?agent=${search.id}`} onClick={event => { event.preventDefault(); onOpen(search.id); }}>{domainOf(search.website)}</a>}
        <span>{day(search.created_at)}{search.gone ? ' · no longer on the server' : ''}</span>
      </div>
      <span className="ys-tally"><b>{count(search, 'shortlisted')}</b> shortlisted<i aria-hidden="true">·</i>
        {count(search, 'needs_look') + count(search, 'rejected')} held back</span>
    </li>)}</ul>
  </section>;
}

/** Every Shortlisted company from your searches in one place, newest first, then the searches themselves. */
export function YourShortlist({ onOpen, onNew }: { onOpen: (id: string) => void; onNew: () => void }) {
  const { publicDemo } = useAgentConfig();
  const [entries, setEntries] = useState<Entry[] | null>(null);
  const [searches, setSearches] = useState<Search[]>([]);
  useEffect(() => {
    let cancelled = false;
    mySearches(publicDemo).then(found => {
      if (cancelled) return;
      const newest = [...found].sort((a, b) => b.created_at.localeCompare(a.created_at));
      setSearches(newest);
      const seen = new Set<string>();
      const list: Entry[] = [];
      for (const search of newest)
        for (const company of search.companies)
          if (company.verdict?.kind === 'shortlisted' && !seen.has(company.domain)) { seen.add(company.domain); list.push({ company, search }); }
      setEntries(list);
    }).catch(() => { if (!cancelled) setEntries([]); });
    return () => { cancelled = true; };
  }, [publicDemo]);
  const gone = entries?.some(entry => entry.search.gone);
  return <section className="ys" aria-labelledby="ys-heading">
    <header className="ys-head">
      <div>
        <p className="ys-eyebrow">{publicDemo ? 'Saved in this browser' : 'From your searches'}</p>
        <h1 id="ys-heading">Your shortlist</h1>
        <p className="ys-sub">Every company that passed a search, with the evidence behind it and your first message.</p>
      </div>
      <button type="button" className="ys-button is-dark" onClick={onNew}>New search</button>
    </header>
    {entries === null ? <p className="agent-status" role="status">Loading your shortlist</p>
      : entries.length === 0 ? <div className="ys-empty">
        <p className="ys-empty-title">No Shortlisted companies yet.</p>
        <p>{searches.length ? `${searches.length === 1 ? 'Your search' : `Your ${searches.length} searches`} found no company with every check passed yet. Open one to see what each company was missing.`
          : 'Every company that passes a search lands here, with its reason and any message you drafted.'}</p>
        {!searches.length && <button type="button" className="ys-button is-dark" onClick={onNew}>Start a search</button>}
      </div>
      : <>
        <p className="ys-count">{entries.length} {entries.length === 1 ? 'company' : 'companies'} ready to contact</p>
        {gone && <p className="ys-note" role="note">Some searches are no longer on the server, so their full page cannot open.
          This browser kept their Shortlisted companies and messages.</p>}
        <ul className="ys-list">{entries.map(entry => <Card key={entry.company.domain} entry={entry} onOpen={onOpen} />)}</ul>
      </>}
    {searches.length > 0 && <Searches searches={searches} onOpen={onOpen} />}
  </section>;
}

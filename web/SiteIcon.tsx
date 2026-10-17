import { useContext, useEffect, useRef, useState } from 'react';
import { BrandfetchContext } from './BrandfetchSettings';
import { api } from './api';
import './SiteIcon.css';

const declarations = new Map<string, Promise<string | null>>();

/** Prefer a supplied or declared icon, then root favicon and opt-in Brandfetch. Suggestions without a directory logo
    can look up the site's declared icon when `lookup` is set. */
export function SiteIcon({ domain, runId, icon, fallback, className, lookup = false }: { domain?: string; runId?: string; icon?: string; fallback: string; className: string; lookup?: boolean }) {
  const [failed, setFailed] = useState<ReadonlySet<string>>(() => new Set());
  const container = useRef<HTMLSpanElement>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const observer = new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting)) { setVisible(true); observer.disconnect(); }
    });
    if (container.current) observer.observe(container.current);
    return () => observer.disconnect();
  }, []);
  const clientId = useContext(BrandfetchContext);
  // A suggestion asks for its declared icon only when the directory supplied none, or that logo failed to load.
  const key = !domain ? '' : runId ? `${runId}:${domain}` : lookup && (!icon || failed.has(icon)) ? `site:${domain}` : '';
  const [declared, setDeclared] = useState<{ key: string; url: string | null } | null>(null);
  useEffect(() => {
    if (!visible || !domain || !key) return;
    let active = true;
    let pending = declarations.get(key);
    if (!pending) {
      pending = (runId ? api.siteIcon(runId, domain) : api.suggestionIcon(domain)).catch(() => null);
      if (declarations.size >= 256) declarations.delete(declarations.keys().next().value ?? '');
      declarations.set(key, pending);
    }
    void pending.then(url => { if (active) setDeclared({ key, url }); });
    return () => { active = false; };
  }, [runId, domain, key, visible]);
  const branded = domain && clientId ? `https://cdn.brandfetch.io/domain/${encodeURIComponent(domain)}/fallback/404?c=${encodeURIComponent(clientId)}` : undefined;
  const declaration = declared?.key === key ? declared.url : undefined;
  const resolving = Boolean(key && declared?.key !== key);
  const source = (resolving && !icon ? [] : [icon, declaration, domain ? `https://${domain}/favicon.ico` : undefined, branded]).find(url => url && !failed.has(url));
  const brandfetch = source && new URL(source).hostname.endsWith('.brandfetch.io');
  return <span ref={container} className={`site-icon ${className}`} aria-hidden="true">{source ? <img src={source} alt="" referrerPolicy={brandfetch ? 'origin' : 'no-referrer'} onError={() => setFailed(previous => new Set([...previous, source]))} /> : fallback}</span>;
}

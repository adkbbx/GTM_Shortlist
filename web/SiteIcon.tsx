import { useState } from 'react';
import './SiteIcon.css';

/** The site's own icon, with no third-party icon service or referrer. */
export function SiteIcon({ domain, icon, fallback, className }: { domain?: string; icon?: string; fallback: string; className: string }) {
  const [failed, setFailed] = useState<ReadonlySet<string>>(() => new Set());
  const source = [icon, domain ? `https://${domain}/favicon.ico` : undefined].find(url => url && !failed.has(url));
  return <span className={`site-icon ${className}`} aria-hidden="true">{source ? <img src={source} alt="" referrerPolicy="no-referrer" onError={() => setFailed(previous => new Set([...previous, source]))} /> : fallback}</span>;
}

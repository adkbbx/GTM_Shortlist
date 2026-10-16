import { useState } from 'react';
import './SiteIcon.css';

/** The site's own icon, with no third-party icon service or referrer. */
export function SiteIcon({ domain, fallback, className }: { domain?: string; fallback: string; className: string }) {
  const [failedDomain, setFailedDomain] = useState<string>();
  return <span className={`site-icon ${className}`} aria-hidden="true">{!domain || failedDomain === domain ? fallback : <img src={`https://${domain}/favicon.ico`} alt="" referrerPolicy="no-referrer" onError={() => setFailedDomain(domain)} />}</span>;
}

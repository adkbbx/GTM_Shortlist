import { createContext, useContext } from 'react';
import type { ReactNode } from 'react';
import { exampleMark, exampleName } from './landing/landing-data';

/** True while the open run is local sample data: invented companies on reserved .example addresses. */
export const SampleContext = createContext(false);

/** How a company address, or a saved label that names one, reads on screen. In a sample run, each reserved address
    reads as its invented company's name; anything else is unchanged. */
export function useSiteLabel() {
  const sample = useContext(SampleContext);
  return (text: string) => sample ? text.replace(/\b[a-z0-9-]+\.example\b/g, domain => exampleName(domain) ?? 'the sample company') : text;
}

/** A link to a company or source page. Sample pages do not exist on the web, so in a sample run it reads as plain text. */
export function OutboundLink({ href, className, children }: { href: string; className?: string; children: ReactNode }) {
  return useContext(SampleContext)
    ? <span className={className}>{children}</span>
    : <a className={className} href={href} target="_blank" rel="noopener noreferrer">{children}</a>;
}

/** The drawn logo shared with the landing page, so sample companies never borrow a real brand's icon. */
export function sampleMark(sample: boolean | undefined, domain: string | undefined) {
  return sample && domain ? exampleMark(domain) : undefined;
}

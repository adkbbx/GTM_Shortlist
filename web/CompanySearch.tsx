import { useEffect, useState } from 'react';
import { ComboBox, Input, ListBox, ListBoxItem, Popover, Text } from 'react-aria-components';
import { directorySuggestions } from './company-suggestions';
import type { CompanySuggestion } from './company-suggestions';
import { SiteIcon } from './SiteIcon';
import './CompanySearch.css';

type Lookup = { kind: 'idle' } | { kind: 'loading'; query: string } | { kind: 'loaded'; query: string; items: CompanySuggestion[] } | { kind: 'error'; query: string; message: string };

export function CompanySearch({ value, onChange, clientId, disabled }: {
  value: string; onChange: (value: string) => void; clientId: string; disabled: boolean;
}) {
  const [focused, setFocused] = useState(false);
  const [picked, setPicked] = useState<string | null>(null);
  const [lookup, setLookup] = useState<Lookup>({ kind: 'idle' });
  const query = value.trim().slice(0, 120);
  useEffect(() => {
    if (!focused || !clientId || query.length < 2 || query === picked) return;
    let disposed = false;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      setLookup({ kind: 'loading', query });
      void directorySuggestions(query, clientId, controller.signal)
        .then(items => { if (!disposed) setLookup({ kind: 'loaded', query, items }); })
        .catch(() => { if (!disposed) setLookup({ kind: 'error', query, message: 'Company suggestions are unavailable. Enter a website to continue.' }); });
    }, 300);
    const timeout = setTimeout(() => controller.abort(), 5300);
    return () => { disposed = true; clearTimeout(timer); clearTimeout(timeout); controller.abort(); };
  }, [query, focused, clientId, picked]);
  const directory = clientId && query.length >= 2;
  const current = lookup.kind !== 'idle' && lookup.query === query ? lookup : null;
  const items = directory && current?.kind === 'loaded' ? current.items : [];
  const message = directory ? current?.kind === 'error' ? current.message : current?.kind === 'loaded' ? 'No matching companies. Enter a website to continue.' : 'Finding companies…' : 'Enter a company name or website.';
  return <ComboBox<CompanySuggestion> className="company-search" aria-label="Company name or website" inputValue={value} onInputChange={next => { if (next !== picked) setPicked(null); onChange(next); }}
    items={items} selectedKey={picked} allowsCustomValue allowsEmptyCollection={Boolean(directory)} menuTrigger="input" isDisabled={disabled}
    onSelectionChange={key => { setPicked(key === null ? null : String(key)); if (key !== null) onChange(String(key)); }} onFocus={() => setFocused(true)} onBlur={() => setFocused(false)}>
    <Input id="website" type="text" autoComplete="off" autoCapitalize="none" autoCorrect="off" spellCheck={false} placeholder="Company name or example.com" required maxLength={2048} />
    <Popover className="company-suggestions" placement="bottom start" offset={8}>
      <p className="company-suggestions-source">Company suggestions</p>
      <ListBox<CompanySuggestion> aria-label="Company suggestions" className="company-suggestions-list" renderEmptyState={() => <p className="suggestions-empty" role="status">{message}</p>}>
        {company => <ListBoxItem id={company.domain} textValue={company.domain} className="company-suggestion">
          <SiteIcon key={`${company.domain}:${company.icon ?? ''}`} domain={company.domain} icon={company.icon} fallback={company.name.slice(0, 1).toUpperCase()} className="suggestion-icon" />
          <span className="suggestion-copy"><Text slot="label">{company.name}</Text></span>
          <span className="suggestion-domain">{company.domain}</span>
        </ListBoxItem>}
      </ListBox>
    </Popover>
  </ComboBox>;
}

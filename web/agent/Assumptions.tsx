import { useState } from 'react';
import type { FormEvent, MouseEvent } from 'react';
import { Chip } from './Evidence';
import { useAgentConfig } from './agent-config';
import type { AgentRun, Overrides, Profile } from './agent-api';

type Apply = (overrides: Overrides) => void;

/** Close the popover an edit control sits in, so the board shows the re-checked result. */
const closing = (event: MouseEvent<HTMLElement> | FormEvent<HTMLElement>) =>
  (event.currentTarget.closest('[popover]') as HTMLElement | null)?.hidePopover?.();

function CriterionEdit({ criterion, apply, busy }: { criterion: Profile['fit_criteria'][number]; apply: Apply; busy: boolean }) {
  const [text, setText] = useState(criterion.text);
  const fieldId = `wording-${criterion.id}`;
  return <div className="agent-edit">
    <p className="agent-edit-title">Optional changes</p>
    <div className="agent-edit-row">
      <button type="button" className="secondary" disabled={busy} onClick={event => { closing(event); apply({ criteria: [{ id: criterion.id, required: !criterion.required }] }); }}>
        {criterion.required ? 'Make it nice to have' : 'Make it required'}
      </button>
      <button type="button" className="secondary" disabled={busy} onClick={event => { closing(event); apply({ criteria: [{ id: criterion.id, enabled: !criterion.enabled }] }); }}>
        {criterion.enabled ? "Don't use this check" : 'Use this check'}
      </button>
    </div>
    <form onSubmit={event => { event.preventDefault(); if (text.trim().length >= 3 && text.trim() !== criterion.text) { closing(event); apply({ criteria: [{ id: criterion.id, text: text.trim() }] }); } }}>
      <label htmlFor={fieldId}>Wording</label>
      <div className="agent-edit-row"><input id={fieldId} value={text} maxLength={500} onChange={event => setText(event.target.value)} />
        <button type="submit" className="secondary" disabled={busy || text.trim().length < 3 || text.trim() === criterion.text}>Save</button></div>
    </form>
  </div>;
}

function SmallForm({ label, placeholder, action, busy, onSubmit }: { label: string; placeholder: string; action: string; busy: boolean; onSubmit: (value: string) => void }) {
  const [value, setValue] = useState('');
  const fieldId = `small-${label.replace(/\W+/g, '-').toLowerCase()}`;
  return <details className="agent-add">
    <summary>{label}</summary>
    <form onSubmit={event => { event.preventDefault(); if (value.trim().length >= 3) { onSubmit(value.trim()); setValue(''); } }}>
      <label className="sr-only" htmlFor={fieldId}>{label}</label>
      <div className="agent-edit-row"><input id={fieldId} value={value} placeholder={placeholder} maxLength={200} onChange={event => setValue(event.target.value)} />
        <button type="submit" className="secondary" disabled={busy || value.trim().length < 3}>{action}</button></div>
    </form>
  </details>;
}

const originNote = (origin: string) => origin === 'user' ? 'You described this.' : origin === 'interpretation' ? 'The reading you chose.' : undefined;

export function Assumptions({ run, apply, busy }: { run: AgentRun; apply: Apply; busy: boolean }) {
  const { editable } = useAgentConfig();
  const profile = run.profile!;
  const competitors = run.competitors.filter(c => c.classification !== 'not_competitor');
  const rules = run.disqualifiers.filter(rule => rule.rule !== 'uses_direct_competitor');
  return <section className="agent-assumptions" aria-labelledby="assumed-heading">
    <div className="agent-section-head">
      <h2 id="assumed-heading">What we assumed</h2>
      <p>Read from your website. Open any item to see the exact words it rests on.{editable ? ' Changes are optional.' : ''}</p>
    </div>
    <dl className="agent-assumption-list">
      {profile.offer && <div><dt>Offer</dt><dd><Chip label={profile.offer.value} quotes={profile.offer.quotes} note={originNote(profile.offer.origin)} /></dd></div>}
      {profile.buyer && <div><dt>Buyer</dt><dd><Chip label={profile.buyer.value} quotes={profile.buyer.quotes} note={originNote(profile.buyer.origin)} /></dd></div>}
      {(profile.target_size || editable) && <div><dt>Company size</dt><dd>
        {profile.target_size && <Chip label={profile.target_size.value} tag={profile.target_size.origin === 'user' ? 'You set' : 'Inferred'}
          quotes={profile.target_size.quotes}
          note={profile.target_size.origin === 'user' ? 'You set this.' : 'Inferred from who your site speaks to. A company is rejected only when a quote shows it is clearly bigger.'} />}
        {editable && <SmallForm label="Change the company size" placeholder="For example: seed to Series A startups, 5 to 50 people" action="Save"
          busy={busy} onSubmit={value => apply({ target_size: value })} />}
      </dd></div>}
      <div><dt>Fit checks</dt><dd>
        {profile.fit_criteria.map(criterion => <Chip key={criterion.id} label={criterion.text} off={!criterion.enabled}
          tag={criterion.required ? 'Required' : 'Nice to have'} quotes={criterion.quotes}>
          {editable && <CriterionEdit criterion={criterion} apply={apply} busy={busy} />}</Chip>)}
        {editable && <SmallForm label="Add a fit check" placeholder="For example: sells through its own online store" action="Add" busy={busy}
          onSubmit={text => apply({ criteria: [{ id: `user-${Date.now().toString(36)}`, text, required: true }] })} />}
      </dd></div>
      {(profile.need_signals.length > 0 || profile.timing_signals.length > 0) && <div><dt>Need and timing</dt><dd>
        {profile.need_signals.map(signal => <Chip key={signal.id} label={signal.text} tag="Need" quotes={signal.quotes} />)}
        {profile.timing_signals.map(signal => <Chip key={signal.id} label={signal.text} tag="Timing" quotes={signal.quotes}
          note={signal.standard ? 'A common buying moment. Your site did not name one, so the agent also looks for this.' : undefined} />)}
      </dd></div>}
      <div><dt>Competitors</dt><dd>
        {competitors.length === 0 && <span className="agent-empty">None proven</span>}
        {competitors.map(competitor => <Chip key={competitor.domain} label={competitor.name} tone={competitor.classification === 'direct' ? 'bad' : 'neutral'}
          tag={competitor.classification === 'direct' ? 'Direct' : 'Adjacent'}
          quotes={[competitor.same_job, competitor.same_buyer].filter((quote): quote is NonNullable<typeof quote> => Boolean(quote))}
          note={competitor.origin === 'user' ? 'You marked this as a direct competitor.' : competitor.reason || undefined}>
          {editable && <div className="agent-edit"><p className="agent-edit-title">{competitor.domain}</p><div className="agent-edit-row">
            <button type="button" className="secondary" disabled={busy} onClick={event => { closing(event); apply({ remove_competitors: [competitor.domain] }); }}>Not a competitor</button>
            {competitor.classification !== 'direct' && <button type="button" className="secondary" disabled={busy} onClick={event => { closing(event); apply({ add_competitors: [competitor.domain] }); }}>Treat as direct</button>}
          </div></div>}
        </Chip>)}
        {editable && <SmallForm label="Add a competitor" placeholder="competitor.com" action="Add" busy={busy} onSubmit={value => apply({ add_competitors: [value] })} />}
      </dd></div>
      <div><dt>Disqualifiers</dt><dd>
        {run.disqualifiers.filter(rule => rule.rule === 'uses_direct_competitor').length > 0 && <Chip label="Uses a direct competitor" tone="bad" quotes={[]}
          note={run.disqualifiers.filter(rule => rule.rule === 'uses_direct_competitor').map(rule => rule.text).join('. ')} />}
        {rules.map(rule => <Chip key={rule.id} label={rule.text} tone="bad" quotes={[]}
          note={rule.id === 'outside_target_size' ? 'From the company size above; change it there if it is wrong.'
            : rule.rule === 'outside_stated_size_or_region' ? 'From what your site says you serve.'
              : 'Applied automatically. A company is rejected only when the skeptic agrees a quote shows it.'} />)}
        {run.overrides.exclusions.map(entry => <Chip key={entry} label={`Excluded: ${entry}`} tone="bad" quotes={[]} note="You excluded this." />)}
        {editable && <SmallForm label="Exclude a company" placeholder="company.com or name" action="Exclude" busy={busy} onSubmit={value => apply({ exclusions: [value] })} />}
      </dd></div>
      {profile.stated_limits.length > 0 && <div><dt>You serve</dt><dd>
        {profile.stated_limits.map(limit => <Chip key={limit.value} label={limit.value} tag={limit.kind === 'size' ? 'Size' : 'Region'} quotes={limit.quotes} />)}
      </dd></div>}
      {profile.existing_customers.length > 0 && <div><dt>Your customers</dt><dd>
        {profile.existing_customers.map(customer => <Chip key={customer.name} label={customer.name} tag="Set aside" quotes={customer.quotes} />)}
      </dd></div>}
    </dl>
  </section>;
}

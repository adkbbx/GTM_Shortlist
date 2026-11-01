import { useId } from 'react';
import './count-picker.css';

/** How many companies to research, as one row of choices (1 · 3 · 5) instead of a dropdown. Native radios: arrow keys
 *  move between choices and screen readers announce the group. */
export function CountPicker({ label, value, options, disabled = false, onChange }: {
  label: string; value: number; options: number[]; disabled?: boolean; onChange: (value: number) => void;
}) {
  const name = useId();
  return <fieldset className="count-picker" disabled={disabled}>
    <legend>{label}</legend>
    <div className="count-picker-options">{options.map(option => <label key={option} className={option === value ? 'is-on' : ''}>
      <input type="radio" name={name} value={option} checked={option === value} onChange={() => onChange(option)} />
      <span>{option}</span>
    </label>)}</div>
  </fieldset>;
}

import { createContext, useContext } from 'react';

/** What the server allows: the public demo caps companies, may ask for a browser check, and lets only the browser
 *  that started a search edit it. Locally everything is open. */
export type AgentConfig = { publicDemo: boolean; maxCompanies: number; turnstileSiteKey: string | null; editable: boolean };

export const localConfig: AgentConfig = { publicDemo: false, maxCompanies: 20, turnstileSiteKey: null, editable: true };
export const AgentConfigContext = createContext<AgentConfig>(localConfig);
export const useAgentConfig = () => useContext(AgentConfigContext);

/** Company counts to offer: the usual steps up to the server's cap, always including the cap and the current value. */
export function countOptions(max: number, current?: number): number[] {
  const steps = (max >= 10 ? [5, 10, 15, 20] : [3, 5]).filter(value => value <= max);
  return [...new Set([...steps, max, ...(current ? [current] : [])])].sort((a, b) => a - b);
}

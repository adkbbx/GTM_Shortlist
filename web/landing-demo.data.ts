/** Presentation-only sample. These objects must never enter the research API. */
export const demoStages = [
  { id: 'offer', title: 'Understand offer', detail: 'Start with what you sell.', hold: 6000 },
  { id: 'market', title: 'Explore market', detail: 'Turn observations into a direction.', hold: 8000 },
  { id: 'confirm', title: 'Confirm target', detail: 'You set the research criteria.', hold: null },
  { id: 'discover', title: 'Discover companies', detail: 'Build a focused candidate list.', hold: 6000 },
  { id: 'evidence', title: 'Inspect evidence', detail: 'Open the words behind a finding.', hold: null },
  { id: 'review', title: 'Review and draft', detail: 'Make your own decision.', hold: null },
] as const;
export type DemoStage = typeof demoStages[number]['id'];
export type DemoState =
  | { mode: 'playing'; stage: DemoStage }
  | { mode: 'paused'; stage: DemoStage }
  | { mode: 'waiting'; stage: DemoStage }
  | { mode: 'finished'; stage: 'review' };
export type DemoAction =
  | { type: 'play' }
  | { type: 'pause' }
  | { type: 'confirm' }
  | { type: 'next' }
  | { type: 'previous' }
  | { type: 'select'; stage: DemoStage }
  | { type: 'reduce' };

export function demoTransition(state: DemoState, action: DemoAction): DemoState {
  if (action.type === 'reduce') return state.stage === 'review' ? { mode: 'finished', stage: 'review' } : { mode: 'waiting', stage: state.stage };
  if (action.type === 'confirm') return state.stage === 'confirm' ? { mode: 'playing', stage: 'discover' } : state;
  if (action.type === 'pause') return state.mode === 'playing' ? { mode: 'paused', stage: state.stage } : state;
  if (action.type === 'select') return { mode: 'waiting', stage: action.stage };
  if (action.type === 'play') {
    return state.stage === 'review' ? { mode: 'playing', stage: 'offer' }
      : demoStages.find(stage => stage.id === state.stage)?.hold === null ? state
        : { mode: 'playing', stage: state.stage };
  }
  const index = demoStages.findIndex(stage => stage.id === state.stage);
  const next = demoStages[index + (action.type === 'previous' ? -1 : 1)];
  if (!next) return state;
  if (next.id === 'review') return { mode: 'finished', stage: 'review' };
  return { mode: action.type === 'previous' || next.hold === null || state.mode !== 'playing' ? 'waiting' : 'playing', stage: next.id };
}

export const sample = {
  seller: 'Relay Studio',
  domain: 'relay-studio.example',
  offer: 'Customer onboarding workflow reviews for B2B software teams.',
  company: 'Northstar Cloud',
  companyDomain: 'northstar.example',
  passage: 'Our platform helps business teams manage customer onboarding, from the first welcome to the handover.',
  unknown: 'Who owns the onboarding budget is not established.',
};

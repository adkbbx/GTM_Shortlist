import assert from 'node:assert/strict';
import { demoTransition } from '../web/landing-demo.data.ts';

let state = demoTransition({ mode: 'finished', stage: 'review' }, { type: 'play' });
assert.deepEqual(state, { mode: 'playing', stage: 'offer' });
state = demoTransition(state, { type: 'next' });
assert.equal(state.stage, 'market');
state = demoTransition(state, { type: 'next' });
assert.deepEqual(state, { mode: 'waiting', stage: 'confirm' });
assert.deepEqual(demoTransition(state, { type: 'play' }), state, 'Play cannot bypass a confirmation pause');
state = demoTransition(state, { type: 'confirm' });
assert.deepEqual(state, { mode: 'playing', stage: 'discover' });
state = demoTransition(state, { type: 'next' });
assert.deepEqual(state, { mode: 'waiting', stage: 'evidence' });
assert.deepEqual(demoTransition(state, { type: 'confirm' }), state, 'Confirmation is scoped to its own stage');
assert.deepEqual(demoTransition(state, { type: 'reduce' }), { mode: 'finished', stage: 'review' });
assert.deepEqual(demoTransition({ mode: 'playing', stage: 'market' }, { type: 'pause' }), { mode: 'paused', stage: 'market' });
assert.deepEqual(demoTransition({ mode: 'playing', stage: 'discover' }, { type: 'select', stage: 'offer' }), { mode: 'waiting', stage: 'offer' });
console.log('Landing demo scenarios passed: timed stages stop at human actions, pause preserves stage, selection is manual, reduced motion reaches the result.');

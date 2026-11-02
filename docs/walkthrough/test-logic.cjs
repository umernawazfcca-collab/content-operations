// Source-level checks for the walkthrough. Runs the pure state model in a sandbox
// and inspects the HTML source. This is not browser, layout or accessibility QA.
'use strict';
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');

const html = fs.readFileSync(__dirname + '/index.html', 'utf8');
const results = [];
const pass = (name) => results.push('- ' + name + ': PASS');

// 1. Pure gating model
const modelSource = html.match(/<script id="walkthrough-model">([\s\S]*?)<\/script>/);
assert(modelSource, 'model script block present');
const sandbox = {};
vm.runInNewContext(modelSource[1] + '\nthis.M = WalkthroughModel;', sandbox);
const M = sandbox.M;
const expectedGates = { approval: 1, duplicate: 4, follower: 5, sensitive: 4 };
assert.deepStrictEqual({ ...M.GATES }, expectedGates);
for (let t = 0; t <= 6; t++) {
  assert.strictEqual(M.clamp('approved', t), t);
  assert.strictEqual(M.isLocked('approved', t), false);
}
assert.strictEqual(M.canAdvance('approved', 6), false);
pass('Approved example reaches all seven stages and stops at the last');
for (const [path, gate] of Object.entries(expectedGates)) {
  for (let t = 0; t <= 6; t++) {
    const landed = M.clamp(path, t);
    assert.ok(landed <= gate, path + ' bypassed its gate via stage ' + (t + 1));
    assert.strictEqual(landed, Math.min(t, gate));
    assert.strictEqual(M.isLocked(path, t), t > gate);
  }
  assert.strictEqual(M.isHeld(path, gate), true);
  assert.strictEqual(M.canAdvance(path, gate), false);
  assert.strictEqual(M.canAdvance(path, gate - 1), true);
}
pass('Every exception path holds at its gate; direct selection of any later stage clamps to the gate');
for (const bad of [-3, 99, NaN, '4', null, undefined, 2.7, Infinity]) {
  const landed = M.clamp('approval', bad);
  assert.ok(Number.isInteger(landed) && landed >= 0 && landed <= 1, 'bad target ' + bad);
}
assert.strictEqual(M.gateFor('constructor'), null);
assert.strictEqual(M.gateFor('__proto__'), null);
pass('Out-of-range, non-numeric and prototype-name inputs cannot escape the clamp');

// 2. Truthful labelling
const ui = html.match(/<script>([\s\S]*?)<\/script>/)[1];
assert(html.includes('Please check your DMs for the next step.'));
assert(/SIMULATED · NOT SENT/.test(ui));
assert(/Next-step acknowledgement, not guide delivery/.test(ui));
assert(/Trigger fired<small>Shows the flow started; proves nothing about delivery/.test(ui));
pass('Public acknowledgement is a labelled, unsent example and trigger is distinguished from delivery');
for (const phrase of ['Simulation', 'Synthetic data', 'Nothing is scheduled, posted or sent', 'Not a scheduler, posting service, follower checker or ManyChat replacement']) {
  assert(html.includes(phrase), 'missing label: ' + phrase);
}
pass('Simulation and capability-boundary labels present');
// Exception renders must never reuse the approved-state copy at the gate.
for (const key of Object.keys(expectedGates)) {
  const block = ui.slice(ui.indexOf(key + ': {'), ui.indexOf('scene:', ui.indexOf(key + ': {')));
  assert(!/Example approval recorded|Example gate satisfied|Illustrative receipt/.test(block), key + ' reuses approved copy');
}
assert(/var held = M\.isHeld\(path, current\)[^;]*d = held \? ex : s/.test(ui), 'held stage renders exception content');
pass('Held stages render exception content, never the approved-state copy');

// 3. Controls and motion policy
for (const id of ['prev', 'play', 'next', 'reset', 'paths', 'steps']) assert(html.includes('id="' + id + '"'), id);
assert(/function manual\(fn\) \{ return function \(e\) \{ autoPending = false; stop\(\);/.test(ui), 'manual interactions pause playback');
for (const id of ['prev', 'next', 'reset']) assert(new RegExp("\\$\\('" + id + "'\\)\\.addEventListener\\('click', manual\\(").test(ui), id + ' pauses');
assert(/\$\('paths'\)\.addEventListener\('change', manual\(/.test(ui));
assert(/steps\.addEventListener\('click', manual\(/.test(ui));
assert(/e\.preventDefault\(\); stop\(\);/.test(ui), 'keyboard navigation pauses');
pass('Previous, Play/Pause, Next and Reset present; every manual interaction pauses playback');
assert(html.includes('@media (prefers-reduced-motion:reduce)'));
assert(/var autoPending = !reduce\.matches;/.test(ui) && /if \(autoPending && !document\.hidden\)/.test(ui), 'autoplay only when motion allowed');
assert(!/infinite/.test(html), 'no endless animation');
assert(/visibilitychange[^;]*stop\(\)/.test(ui));
pass('Self-advance only when motion is allowed, never loops, stops when hidden');

// 4. Self-containment
assert(!/\b(fetch|XMLHttpRequest|WebSocket|EventSource|sendBeacon|localStorage|sessionStorage|indexedDB|document\.cookie)\b/.test(html));
assert(!/(?:src|href)=["']?(?:https?:)?\/\//i.test(html), 'no remote src/href');
assert(!/@import|@font-face|url\(\s*["']?(?:https?:)?\/\//i.test(html), 'no remote fonts or CSS');
assert(!/<(?:img|iframe|link|object|embed)\b/i.test(html), 'no external embeds');
pass('No network APIs, storage, remote fonts or external assets');

console.log('# Walkthrough source checks\n\n' + results.join('\n') +
  '\n\nNOT RUN by this script: browser rendering, layout, keyboard, reduced-motion runtime, screen readers, network observation.' +
  '\nwalkthrough logic checks passed');

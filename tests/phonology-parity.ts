import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {evaluateEvidence, proposalInput} from '../worker/phonology-evaluator.ts';

const payload = JSON.parse(readFileSync(process.argv[2], 'utf8'));
for (const {input, expected} of payload.cases) {
  const p = proposalInput(input), r = payload.records;
  const pairs = new Map<string, any[]>();
  for (const [key, value] of Object.entries(r)) if (key.startsWith(`pair:${p.inventory_scope}:`)) pairs.set(key.split(':')[2], value as any[]);
  const actual = evaluateEvidence(p, {catalog: r.catalog, inventory: r.inventory, tokens: r.tokens, pairs, doc: r['doc:' + p.reference_doculect]});
  assert.deepEqual(actual, expected, JSON.stringify(input));
}
for (const input of [null, [], {}, {inventory: []}, {inventory: ['p', 'p']}, {inventory: ['p a']},
  {inventory: ['p\u001c']}, {inventory: ['p'], words: ['pa']}, {inventory: ['p'], syllable_templates: ['CV\n']},
  {inventory: ['p'], prosody: {stress: []}}, {inventory: ['p'], reference_doculect: 1}, {inventory: ['p'], bogus: true}]) {
  assert.throws(() => proposalInput(input));
}
console.log(`${payload.cases.length} complete Python/TypeScript report parity cases passed.`);

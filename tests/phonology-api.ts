import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {getPlatformProxy} from 'wrangler';
import worker from '../worker/index.ts';
import {Snapshot} from '../worker/phonology-api.ts';

const payload = JSON.parse(readFileSync(process.argv[3], 'utf8'));
const proxy = await getPlatformProxy({configPath: 'wrangler.jsonc', persist: {path: process.argv[2]}, remoteBindings: false});
const db = proxy.env.conlang_reference as D1Database;
const call = (path: string, init?: RequestInit) => worker.fetch(new Request('http://localhost' + path, init), proxy.env as Env);
try {
  const status = await call('/api/phonology/status');
  assert.equal(status.status, 200);
  assert.equal((await status.json()).snapshot, payload.snapshot);
  for (const {input, expected} of payload.cases) {
    const response = await call('/api/phonology/evaluate', {method: 'POST', body: JSON.stringify(input)});
    assert.equal(response.status, 200);
    const actual = await response.json();
    assert.equal(actual.serving_snapshot, payload.snapshot);
    delete actual.serving_snapshot;
    assert.deepEqual(actual, expected);
  }
  for (const body of ['{', JSON.stringify({inventory: []}), JSON.stringify({inventory: ['p'], reference_doculect: 'not-in-snapshot'})]) {
    assert.equal((await call('/api/phonology/evaluate', {method: 'POST', body})).status, 400);
  }
  assert.equal((await call('/api/phonology/evaluate')).status, 405);
  assert.equal((await call('/api/phonology/missing')).status, 404);
  assert.equal((await call('/api/phonology/evaluate', {method: 'POST', body: 'x'.repeat(1024 * 1024 + 1)})).status, 400);
  assert.equal((await (await call('/api/health')).json()).concept_count, 2);
  assert.equal((await (await call('/api/concepts?search=mountain')).json()).results[0].gloss, 'MOUNTAIN');
  assert.equal((await (await call('/api/concepts/1')).json()).relations[0].related_gloss, 'HILL');
  const snapshot = await Snapshot.open(db);
  await db.prepare("UPDATE phonology_web_chunk SET payload='corrupted' WHERE snapshot=? AND key='tokens' AND position=0").bind(snapshot.id).run();
  await assert.rejects(() => snapshot.read('tokens'), /Corrupt/);
  // Repair is exercised by the Python caller's next sync; clear receipts so it
  // reimports the changed data. Existing semantic tables must remain untouched.
  await db.prepare('DELETE FROM phonology_web_part WHERE snapshot=?').bind(snapshot.id).run();
  console.log(`${payload.cases.length} local D1/Worker parity cases, API failures, checksum rejection, and Concept Explorer regression passed.`);
} finally {
  await proxy.dispose();
}

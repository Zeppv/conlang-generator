// One persistent LOCAL Wrangler runtime for an entire import and verification.
// Keeping it alive avoids a CLI/runtime startup for every SQL part and readback.
import {getPlatformProxy} from 'wrangler';
import {createInterface} from 'node:readline';
import {resolve} from 'node:path';

const send = result => process.stdout.write('PHONOLOGY_RPC ' + JSON.stringify(result) + '\n');
let proxy;
try {
  proxy = await getPlatformProxy({configPath: resolve('wrangler.jsonc'), remoteBindings: false,
    ...(process.argv[2] ? {persist: {path: resolve(process.argv[2], 'v3')}} : {})});
  const db = proxy.env.conlang_reference;
  if (!db) throw new Error('Missing conlang_reference binding');
  send({ready: true});
  for await (const line of createInterface({input: process.stdin, crlfDelay: Infinity})) {
    try {
      const request = JSON.parse(line);
      const results = await db.batch(request.statements.map(s => db.prepare(s)));
      if (results.some(r => !r.success)) throw new Error('D1 statement failed');
      send({results: results.flatMap(r => r.results ?? [])});
    } catch (error) { send({error: error.message}); }
  }
} catch (error) {
  send({error: error.message});
  process.exitCode = 1;
} finally { if (proxy) await proxy.dispose(); }

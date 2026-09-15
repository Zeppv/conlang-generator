import { readFileSync } from 'node:fs';
import { realizeBundle } from '../shared/phonology-rules.ts';
import { phonologyApi } from '../worker/phonology-api.ts';
const cases = JSON.parse(readFileSync(0, 'utf8'));
const output = [];
for (const item of cases) {
  try {
    if (item.http) {
      const request = new Request('http://localhost/api/phonology/realize', {
        method: item.method ?? 'POST', headers: {'content-type': item.contentType ?? 'application/json'},
        ...(item.method === 'GET' ? {} : {body: item.raw ?? JSON.stringify(item.bundle)}),
      });
      // Access to any D1 property would fail: realization must be self-contained.
      const response = await phonologyApi(request, new Proxy({}, {get() { throw new Error('Unexpected D1 access'); }}));
      output.push({status: response.status, body: await response.json()});
    } else output.push({bundle: await realizeBundle(item.bundle)});
  } catch (error) { output.push({error: error.message}); }
}
process.stdout.write(JSON.stringify(output));

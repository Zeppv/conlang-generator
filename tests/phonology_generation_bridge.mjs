import { readFileSync } from 'node:fs';
import { generatePhonology } from '../shared/phonology-generator.ts';
import { parseJson, sha256 } from '../shared/phonology-rules.ts';
import { phonologyApi } from '../worker/phonology-api.ts';
const input = JSON.parse(readFileSync(0, 'utf8'));
// Emulates the three serving tables, including chunk hashes and activation.
class SnapshotDB {
  constructor(snapshots, active, corrupt) { this.snapshots = snapshots; this.active = active; this.corrupt = corrupt; this.reads = []; }
  prepare(sql) {
    const self = this;
    if (!sql.startsWith('SELECT ')) throw new Error('Unexpected write');
    if (sql === 'SELECT snapshot FROM phonology_web_active WHERE id=1') return {first: async () => self.active ? {snapshot: self.active} : null};
    if (!sql.startsWith('SELECT key,position,payload,checksum FROM phonology_web_chunk')) throw new Error('Unexpected reference query');
    return {bind(snapshot, ...keys) { return {all: async () => {
      self.reads.push(...keys);
      const rows = self.snapshots[snapshot] ?? [];
      return {results: rows.filter(r => keys.includes(r.key)).map(r => self.corrupt === r.key ? {...r, payload: r.payload + ' '} : r)};
    }}; }};
  }
}
const output = [];
for (const item of input.cases) {
  try {
    if (item.http) {
      const db = new SnapshotDB(input.snapshots, item.active ?? input.active, item.corrupt);
      const response = await phonologyApi(new Request('http://local/api/phonology/generate', {
        method: item.method ?? 'POST', headers: {'content-type': item.contentType ?? 'application/json'},
        ...(item.method === 'GET' ? {} : {body: item.raw ?? JSON.stringify(item.input)}),
      }), db);
      output.push({status: response.status, body: await response.json(), reads: db.reads});
    } else {
      const spec = parseJson(item.input.specification_json), r = item.input.request;
      const records = input.records;
      const pairs = new Map(Object.entries(records).filter(([k]) => k.startsWith(`pair:${r.inventory_scope ?? 'language'}:`)).map(([k,v]) => [k.split(':')[2], v]));
      const result = await generatePhonology(spec, r, {catalog: records.catalog, inventory: records.inventory, tokens: records.tokens, doc: records['doc:' + r.reference_doculect], pairs}, await sha256(item.input.specification_json), item.budget);
      output.push({generation: result});
    }
  } catch (error) { output.push({error: error.message}); }
}
process.stdout.write(JSON.stringify(output));

import { evaluateEvidence, InputError, proposalInput } from './phonology-evaluator.ts';
import type { Row } from './phonology-evaluator.ts';

async function hash(text: string) {
  return [...new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text)))].map(b => b.toString(16).padStart(2, '0')).join('');
}

// Pin one immutable snapshot for the entire request. Activation during a request
// cannot combine evidence from two versions. Old snapshots remain readable.
export class Snapshot {
  db: D1Database;
  id: string;
  hashes: Record<string, string> = {};
  constructor(db: D1Database, id: string) { this.db = db; this.id = id; }
  async readMany(keys: string[], sealed = true): Promise<Map<string, any>> {
    const output = new Map<string, any>();
    for (let start = 0; start < keys.length; start += 80) {
      const group = keys.slice(start, start + 80);
      const rows = await this.db.prepare(`SELECT key,position,payload,checksum FROM phonology_web_chunk WHERE snapshot=? AND key IN (${group.map(() => '?').join(',')}) ORDER BY key,position`).bind(this.id, ...group).all<{key: string; position: number; payload: string; checksum: string}>();
      for (const key of group) {
        const chunks = rows.results.filter(row => row.key === key);
        if (!chunks.length || chunks.some((row, index) => row.position !== index)) throw new Error('Missing snapshot chunks');
        for (const chunk of chunks) if (await hash(chunk.payload) !== chunk.checksum) throw new Error('Corrupt snapshot chunk');
        const text = chunks.map(row => row.payload).join('');
        if (await hash(text) !== (sealed ? this.hashes[key] : this.id)) throw new Error('Snapshot checksum mismatch');
        output.set(key, JSON.parse(text));
      }
    }
    return output;
  }
  async read(key: string) { return (await this.readMany([key])).get(key); }
  static async open(db: D1Database) {
    const active = await db.prepare('SELECT snapshot FROM phonology_web_active WHERE id=1').first<{snapshot: string}>();
    if (!active) throw new Error('No active snapshot');
    const snapshot = new Snapshot(db, active.snapshot);
    const manifest = (await snapshot.readMany(['manifest'], false)).get('manifest');
    if (manifest.format_version !== 1) throw new Error('Unsupported snapshot format');
    snapshot.hashes = manifest.records;
    return snapshot;
  }
}

async function boundedJson(request: Request) {
  const reader = request.body?.getReader();
  if (!reader) throw new InputError('A JSON proposal is required');
  const chunks: Uint8Array[] = [];
  let bytes = 0;
  while (true) {
    const {value, done} = await reader.read();
    if (done) break;
    bytes += value.byteLength;
    if (bytes > 1024 * 1024) { await reader.cancel(); throw new InputError('Proposal exceeds 1 MiB'); }
    chunks.push(value);
  }
  const body = new Uint8Array(bytes);
  let offset = 0;
  for (const chunk of chunks) { body.set(chunk, offset); offset += chunk.length; }
  try { return JSON.parse(new TextDecoder('utf-8', {fatal: true, ignoreBOM: false}).decode(body)); }
  catch { throw new InputError('Proposal must be valid UTF-8 JSON'); }
}

export async function phonologyApi(request: Request, db: D1Database): Promise<Response> {
  const url = new URL(request.url);
  const isStatus = url.pathname === '/api/phonology/status';
  const isEvaluation = url.pathname === '/api/phonology/evaluate';
  if (!isStatus && !isEvaluation) return Response.json({error: 'API route not found.'}, {status: 404});
  if (request.method !== (isStatus ? 'GET' : 'POST')) return Response.json({error: 'Method not allowed.'}, {status: 405, headers: {Allow: isStatus ? 'GET' : 'POST'}});
  try {
    const proposal = isEvaluation ? proposalInput(await boundedJson(request)) : null;
    const snapshot = await Snapshot.open(db);
    const catalog = await snapshot.read('catalog');
    if (catalog.format_version !== 1 || Object.values(catalog.evidence_builds as Record<string, Row>).some(r => r.method_version !== '1.0.0')) throw new Error('Unsupported evidence build');
    if (isStatus) return Response.json({ready: true, snapshot: snapshot.id, doculects: catalog.doculects, evidence_builds: catalog.evidence_builds});
    const p = proposal!;
    if (p.reference_doculect && !catalog.doculects.some((r: Row) => r.lexibank_id === p.reference_doculect)) throw new InputError('The selected doculect is not included in the active website snapshot');
    const common = await snapshot.readMany(['tokens', 'inventory', ...(p.reference_doculect ? ['doc:' + p.reference_doculect] : [])]);
    const inventory = common.get('inventory');
    const ids: number[] = inventory.segments.filter((r: Row) => p.inventory.includes(r.phoneme)).map((r: Row) => r.id);
    const keys = ids.map(id => `pair:${p.inventory_scope}:${id}`).filter(key => Object.hasOwn(snapshot.hashes, key));
    const records = await snapshot.readMany(keys);
    const pairs = new Map<string, any[]>();
    for (const [key, rows] of records) pairs.set(key.split(':')[2], rows.filter((row: any[]) => ids.includes(row[0])));
    const report = evaluateEvidence(p, {catalog, inventory, tokens: common.get('tokens'), pairs, doc: common.get('doc:' + p.reference_doculect)});
    return Response.json({...report, serving_snapshot: snapshot.id});
  } catch (error) {
    if (error instanceof InputError) return Response.json({error: error.message}, {status: 400});
    console.error('Phonology evidence unavailable:', error);
    return Response.json({error: 'Phonology evidence is unavailable or incomplete. Complete the local phonology web sync and try again.'}, {status: 503});
  }
}

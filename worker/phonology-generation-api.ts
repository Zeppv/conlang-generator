import { canonicalJson, canonicalRules, ENGINE_VERSION, MAX_BYTES, parseJson, realizeBundle, RuleError, savedSpecification, sha256 } from '../shared/phonology-rules.ts';
import { generatePhonology, generationRequest } from '../shared/phonology-generator.ts';
import { Snapshot } from './phonology-snapshot.ts';
import { InputError } from './phonology-evaluator.ts';
import type { Row, Evidence } from './phonology-evaluator.ts';

export async function readGenerationInput(request: Request) {
  const reader = request.body?.getReader();
  if (!reader) throw new RuleError('Generation input is required.');
  const chunks: Uint8Array[] = []; let size = 0;
  while (true) {
    const {value, done} = await reader.read(); if (done) break;
    size += value.byteLength;
    if (size > MAX_BYTES) { await reader.cancel(); throw new RuleError('Generation input exceeds 8 MiB.'); }
    chunks.push(value);
  }
  const bytes = new Uint8Array(size); let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  try { return parseJson(new TextDecoder('utf-8', {fatal: true, ignoreBOM: false}).decode(bytes)); }
  catch { throw new RuleError('Generation input must be UTF-8 JSON with unique keys.'); }
}
export async function snapshotEvidence(snapshot: Snapshot, spec: Row, request: Row): Promise<Evidence> {
  const catalog = await snapshot.read('catalog');
  if (catalog.format_version !== 1 || Object.values(catalog.evidence_builds as Record<string, Row>).some(r => r.method_version !== '1.0.0')) throw new Error('Unsupported evidence build');
  if (request.reference_doculect && !catalog.doculects.some((d: Row) => d.lexibank_id === request.reference_doculect)) throw new RuleError('The selected doculect is not present in this evidence snapshot.');
  const common = await snapshot.readMany(['tokens', 'inventory', ...(request.reference_doculect ? ['doc:' + request.reference_doculect] : [])]);
  const inventory = common.get('inventory');
  const ipas = new Set(spec.phonemes.map((p: Row) => p.ipa));
  const ids: number[] = inventory.segments.filter((p: Row) => ipas.has(p.phoneme)).map((p: Row) => p.id);
  const keys = ids.map(id => `pair:${request.inventory_scope}:${id}`).filter(k => Object.hasOwn(snapshot.hashes, k));
  const rows = await snapshot.readMany(keys);
  const pairs = new Map<string, any[]>();
  for (const [key, values] of rows) pairs.set(key.split(':')[2], values.filter((r: any[]) => ids.includes(r[0])));
  return {catalog, inventory, tokens: common.get('tokens'), pairs, doc: common.get('doc:' + request.reference_doculect)};
}
export async function phonologyGenerationApi(request: Request, db: D1Database): Promise<Response> {
  if (request.method !== 'POST') return Response.json({error: 'Method not allowed.'}, {status: 405, headers: {Allow: 'POST'}});
  if (!request.headers.get('content-type')?.toLowerCase().startsWith('application/json')) return Response.json({error: 'Content-Type must be application/json.'}, {status: 415});
  try {
    const input = await readGenerationInput(request);
    if (!input || typeof input !== 'object' || Array.isArray(input) || Object.keys(input).some(k => !['specification_json','request','rules','snapshot'].includes(k))) throw new RuleError('Unknown or invalid generation input fields.');
    if (typeof input.specification_json !== 'string') throw new RuleError('An exported specification is required.');
    const spec = savedSpecification(parseJson(input.specification_json));
    if (canonicalJson(spec, '', true) !== input.specification_json) throw new RuleError('Use an exported canonical specification.');
    const config = generationRequest(input.request, spec);
    const rules = canonicalRules(input.rules, spec);
    if (spec.phonemes.length > 64 || config.word_count > 200 || config.maximum_attempts_per_word > 256) throw new RuleError('Website limits: 64 pool sounds, 200 forms, 256 attempts per form. Use the offline generator for larger requests.');
    if (input.snapshot != null && (typeof input.snapshot !== 'string' || !/^[a-f0-9]{64}$/.test(input.snapshot))) throw new RuleError('Invalid snapshot identity.');
    const snapshot = await Snapshot.open(db, input.snapshot ?? undefined);
    const evidence = await snapshotEvidence(snapshot, spec, config);
    const generation = await generatePhonology(spec, input.request, evidence, await sha256(input.specification_json), {decisions: 20000, attempts: 2000});
    generation.web_reproduction = {request: input.request, snapshot: snapshot.id};
    const result = await realizeBundle({bundle_version: 1, rule_engine_version: ENGINE_VERSION, specification_json: input.specification_json, rules, generation});
    if (new TextEncoder().encode(JSON.stringify(result, null, 2)).byteLength > MAX_BYTES) throw new RuleError('Generated run exceeds the 8 MiB export limit. Reduce the number of forms.');
    return Response.json(result);
  } catch (error) {
    if (error instanceof RuleError || error instanceof InputError) return Response.json({error: error.message}, {status: 400});
    console.error('Phonology generation unavailable:', error);
    return Response.json({error: 'The requested evidence snapshot is unavailable or incomplete. Check the Phonology tab status; do not rebuild reference data as a routine fix.'}, {status: 503});
  }
}

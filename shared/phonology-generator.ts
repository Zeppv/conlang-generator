/** Step 11 generator port, using the existing compact evidence representation. */
import { canonicalJson, decisionUnit, RuleError, validateGeneration } from './phonology-rules.ts';
import type { Row } from './phonology-rules.ts';
import { Decimal, round8 } from './phonology-decimal.ts';
import { evaluateEvidence, proposalInput } from '../worker/phonology-evaluator.ts';
import type { Evidence } from '../worker/phonology-evaluator.ts';
import { sha256 } from './phonology-rules.ts';

export class GenerationError extends RuleError {}
const fail = (path: string, message: string): never => { throw new GenerationError(`${path}: ${message}`); };
const fields = ['name', 'consonant_target', 'vowel_target', 'tone_target', 'required_phoneme_ids', 'excluded_phoneme_ids', 'word_count', 'component_count_weights', 'duplicate_policy', 'maximum_attempts_per_word', 'inventory_scope', 'reference_doculect'];
const integer = (v: any, min: number, max: number, path: string) => {
  if (!Number.isInteger(v) || v < min || v > max) fail(path, `requires an integer from ${min} to ${max}`);
  return v;
};
export function generationRequest(value: any, spec: Row): Row {
  if (!value || typeof value !== 'object' || Array.isArray(value) || Object.keys(value).some(k => !fields.includes(k))) fail('request', 'unknown fields or invalid object');
  const r: Row = {name: 'Unnamed generation', tone_target: 0, required_phoneme_ids: [], excluded_phoneme_ids: [], word_count: 25, component_count_weights: {'1': 1}, duplicate_policy: 'reject', maximum_attempts_per_word: 128, inventory_scope: 'language', reference_doculect: null, ...value};
  if (typeof r.name !== 'string' || [...r.name].length < 1 || [...r.name].length > 200) fail('request.name', 'requires 1-200 characters');
  for (const key of ['consonant_target', 'vowel_target', 'tone_target']) integer(r[key], key === 'vowel_target' ? 1 : 0, 256, key);
  integer(r.word_count, 1, 1000, 'word_count'); integer(r.maximum_attempts_per_word, 1, 10000, 'maximum_attempts_per_word');
  const known = new Set(spec.phonemes.map((p: Row) => p.id));
  for (const key of ['required_phoneme_ids', 'excluded_phoneme_ids']) {
    const ids = r[key];
    if (!Array.isArray(ids) || ids.length > 256 || ids.some(id => typeof id !== 'string' || !known.has(id)) || new Set(ids).size !== ids.length) fail(key, 'invalid, unknown or duplicate stable IDs');
    r[key] = [...ids].sort();
  }
  if (r.required_phoneme_ids.some((id: string) => r.excluded_phoneme_ids.includes(id))) fail('request', 'required and excluded sounds overlap');
  if (!['reject', 'allow'].includes(r.duplicate_policy)) fail('duplicate_policy', 'requires reject or allow');
  if (!['inventory', 'language'].includes(r.inventory_scope)) fail('inventory_scope', 'requires inventory or language');
  if (r.reference_doculect !== null && (typeof r.reference_doculect !== 'string' || [...r.reference_doculect].length < 1 || [...r.reference_doculect].length > 200)) fail('reference_doculect', 'requires an exact ID or null');
  const w = r.component_count_weights;
  if (!w || typeof w !== 'object' || Array.isArray(w) || !Object.keys(w).length || Object.keys(w).length > 8) fail('component_count_weights', 'requires 1-8 weighted choices');
  const entries = Object.entries(w).sort(([a], [b]) => Number(a) - Number(b));
  let total = Decimal.from(0);
  const weights = entries.map(([k,v]) => {
    if (!/^[1-8]$/.test(k) || typeof v !== 'number' || !Number.isFinite(v) || v <= 0) fail('component_count_weights', 'requires keys 1-8 and positive finite weights');
    const weight = Decimal.from(v as number); total = total.add(weight); return [k, weight] as const;
  });
  r.component_count_weights = Object.fromEntries(weights.map(([k,w]) => [k, w.divide(total).number()]));
  for (const [cls, key] of [['consonant', 'consonant_target'], ['vowel', 'vowel_target'], ['tone', 'tone_target']]) {
    const available = spec.phonemes.filter((p: Row) => p.class === cls && !r.excluded_phoneme_ids.includes(p.id));
    const required = spec.phonemes.filter((p: Row) => p.class === cls && r.required_phoneme_ids.includes(p.id));
    if (r[key] < required.length) fail(key, 'target is below required sounds');
    if (r[key] > available.length) fail(key, 'target exceeds available sounds');
  }
  return r;
}

export function generationEvidence(spec: Row, scope: string, data: Evidence): Row {
  const build = data.catalog.evidence_builds.phonology_analysis;
  if (build.id !== 'phoible_v2_0_step4' || build.method_version !== '1.0.0') fail('evidence', 'unsupported PHOIBLE analysis');
  const analysis = Object.fromEntries(['id', 'method_version', 'inventory_unit_count', 'language_unit_count'].map(k => [k, build[k]]));
  const units = analysis[scope === 'language' ? 'language_unit_count' : 'inventory_unit_count'];
  const sounds: Row = Object.create(null);
  for (const p of spec.phonemes) {
    const rows = data.inventory.segments.filter((row: Row) => row.phoneme === p.ipa);
    if (rows.length !== 1) { sounds[p.id] = {status: rows.length ? 'ambiguous_exact_rows' : 'not_mapped', segment_id: null, prevalence: null, units}; continue; }
    const row = rows[0], prev = data.inventory.prevalence.find((v: Row) => v.scope === scope && v.segment_id === row.id);
    sounds[p.id] = {status: row.segment_class === p.class ? 'exact' : 'class_mismatch', segment_id: row.id, phoible_class: row.segment_class, prevalence: prev?.prevalence ?? null, unit_count: prev?.unit_count ?? null, units};
  }
  return {analysis, scope, sounds, pairs: data.pairs, note: 'PHOIBLE prevalence and stored inventory-pair evidence are proposal heuristics only. Missing or low evidence never overrides construction rules.'};
}
function selectionWeight(candidate: Row, selected: Row[], evidence: Row) {
  const sound = evidence.sounds[candidate.id];
  const prevalenceFactor = .2 + (sound.prevalence ?? 0);
  const counts = {observed: 0, expected_absence: 0, not_stored: 0};
  const factors: number[] = [];
  for (const peer of selected) {
    const other = evidence.sounds[peer.id];
    const [a,b] = [sound.segment_id, other.segment_id].sort((a,b) => a-b);
    const row = sound.segment_id === null || other.segment_id === null ? null : evidence.pairs.get(String(a))?.find((row: any[]) => row[0] === b);
    if (!row) { counts.not_stored++; factors.push(1); }
    else if (row[3] === 'expected_absence') { counts.expected_absence++; factors.push(.35); }
    else { counts.observed++; factors.push(row[4] && row[4] > 0 ? Math.max(.5, Math.min(2, Math.sqrt(row[4]))) : .5); }
  }
  const pairFactor = factors.length ? factors.reduce((a,b) => a+b, 0) / factors.length : 1;
  let shared = 0;
  for (const peer of selected.filter(p => p.class === candidate.class)) {
    for (const [key, value] of Object.entries(candidate.features)) if (Object.hasOwn(peer.features, key) && peer.features[key] === value) shared++;
  }
  const featureFactor = 1 + Math.min(shared, 10) * .03;
  const weight = Math.max(.000001, prevalenceFactor * pairFactor * featureFactor);
  return {weight, detail: {mapping_status: sound.status, prevalence: sound.prevalence, prevalence_factor: round8(prevalenceFactor), pair_factor: round8(pairFactor), pair_evidence: counts, feature_factor: round8(featureFactor), final_weight: round8(weight)}};
}
export type GenerationBudget = {decisions: number; attempts: number};
export async function generatePhonology(spec: Row, requestValue: Row, data: Evidence, specificationFingerprint: string, budget?: GenerationBudget): Promise<Row> {
  const request = generationRequest(requestValue, spec);
  const fingerprint = await sha256(canonicalJson(request));
  const evidence = generationEvidence(spec, request.inventory_scope, data);
  const choice = async (options: [string, number][], namespace: string, index: number) => {
    if (budget && --budget.decisions < 0) fail('request', 'website decision budget exhausted; reduce form count or construction size');
    if (!options.length) fail('construction', 'has no available choices');
    const weights = [...options].sort(([a],[b]) => a < b ? -1 : a > b ? 1 : 0).map(([key,w]) => [key, Decimal.from(w)] as const);
    let total = Decimal.from(0); for (const [,w] of weights) total = total.add(w);
    const target = Decimal.from(await decisionUnit(spec, namespace, index)).multiply(total);
    let cumulative = Decimal.from(0);
    for (const [key,w] of weights) { cumulative = cumulative.add(w); if (target.less(cumulative)) return key; }
    return weights.at(-1)![0];
  };
  const byId = new Map<string, Row>(spec.phonemes.map((p: Row) => [p.id,p]));
  const selected: Row[] = request.required_phoneme_ids.map((id: string) => byId.get(id)!);
  const selection: Row[] = selected.map(p => ({id: p.id, ipa: p.ipa, class: p.class, reason: 'required', heuristic: null}));
  for (const [cls, key] of [['consonant', 'consonant_target'], ['vowel', 'vowel_target'], ['tone', 'tone_target']]) {
    const available: Row[] = spec.phonemes.filter((p: Row) => p.class === cls && !request.excluded_phoneme_ids.includes(p.id));
    while (selected.filter(p => p.class === cls).length < request[key]) {
      const candidates = available.filter(p => !selected.some(s => s.id === p.id));
      const weights = new Map(candidates.map(p => [p.id, selectionWeight(p, selected, evidence)]));
      const id = await choice(candidates.map(p => [p.id, weights.get(p.id)!.weight]), `${fingerprint}:inventory:${cls}`, selected.filter(p => p.class === cls).length);
      const p = byId.get(id)!; selected.push(p);
      selection.push({id: p.id, ipa: p.ipa, class: p.class, reason: 'generated', heuristic: weights.get(id)!.detail});
    }
  }
  const selectedIds = new Set(selected.map(p => p.id));
  const onsets: string[][] = spec.construction.onsets.filter((c: string[]) => c.every(id => selectedIds.has(id)));
  const codas: string[][] = spec.construction.codas.filter((c: string[]) => c.every(id => selectedIds.has(id)));
  const templates: Row[] = spec.construction.syllable_templates.filter((t: Row) => onsets.some(c => c.length === t.shape.indexOf('V')) && codas.some(c => c.length === t.shape.length - t.shape.indexOf('V') - 1));
  if (!templates.length) fail('construction', 'generated inventory leaves no usable syllable template');
  const vowels = selected.filter(p => p.class === 'vowel');
  const boundary = spec.construction.boundaries.component_token;
  const forms: Row[] = []; const seen = new Set<string>(); let tokenCount = 0;
  for (let wi = 0; wi < request.word_count; wi++) {
    let accepted = false;
    for (let attempt = 0; attempt < request.maximum_attempts_per_word; attempt++) {
      if (budget && --budget.attempts < 0) fail('request', 'website attempt budget exhausted; reduce form count or allow duplicates');
      const prefix = `${fingerprint}:word:${wi}:attempt:${attempt}`;
      const count = Number(await choice(Object.entries(request.component_count_weights), prefix + ':components', 0));
      const components: Row[] = [];
      for (let ci = 0; ci < count; ci++) {
        const cp = prefix + `:component:${ci}`;
        const syllableCount = Number(await choice(Object.entries(spec.construction.syllable_count_weights), cp + ':count', 0));
        const syllables: Row[] = [];
        for (let si = 0; si < syllableCount; si++) {
          const tid = await choice(templates.map(t => [t.id, t.weight]), cp + ':template', si);
          const template = templates.find(t => t.id === tid)!; const pos = template.shape.indexOf('V');
          const onsetKey = await choice(onsets.filter(c => c.length === pos).map(c => [c.join('\x1f'), 1]), cp + `:onset:${si}`, 0);
          const codaKey = await choice(codas.filter(c => c.length === template.shape.length-pos-1).map(c => [c.join('\x1f'), 1]), cp + `:coda:${si}`, 0);
          const onset = onsetKey ? onsetKey.split('\x1f') : [], coda = codaKey ? codaKey.split('\x1f') : [];
          const nucleus = await choice(vowels.map(p => [p.id, .2 + (evidence.sounds[p.id].prevalence || 0)]), cp + ':vowel', si);
          syllables.push({template_id: tid, shape: template.shape, onset, nucleus, coda, phoneme_ids: [...onset, nucleus, ...coda]});
        }
        components.push({component_index: ci, syllables, phoneme_ids: syllables.flatMap(s => s.phoneme_ids)});
      }
      const ids: string[] = []; for (const [i,c] of components.entries()) { if (i) ids.push(boundary); ids.push(...c.phoneme_ids); }
      const identity = JSON.stringify(ids);
      if (request.duplicate_policy === 'reject' && seen.has(identity)) continue;
      seen.add(identity); tokenCount += ids.length;
      if (budget && tokenCount > 20000) fail('forms', 'website realization limit is 20000 tokens');
      forms.push({word_index: wi, attempt: attempt+1, component_count: count, components, phoneme_ids: ids, ipa_tokens: ids.map(id => byId.get(id)?.ipa ?? id)});
      accepted = true; break;
    }
    if (!accepted) fail(`word[${wi}]`, 'maximum attempts exhausted while rejecting duplicates; reduce word_count, allow duplicates, or expand construction choices');
  }
  const validation = {valid: true, issues: [], checked_forms: forms.length, rules: 'Inventory membership, declared onset/coda clusters, template traces, vowel nuclei, component-boundary resets, special-marker exclusion, and the requested duplicate policy.'};
  // Independently reconstruct and check every generated trace before evidence scoring.
  validateGeneration(spec, {inventory: {phonemes: selection}, request_fingerprint: fingerprint, forms, hard_rule_validation: validation, evidence: {evaluation: {}}});
  const proposal = proposalInput({name: request.name, inventory: selected.map(p => p.ipa), words: forms.map(f => f.ipa_tokens), syllable_templates: templates.map(t => t.shape), reference_doculect: request.reference_doculect, inventory_scope: request.inventory_scope, prosody: Object.fromEntries(Object.entries(spec.prosody).map(([k,v]) => [k,(v as Row).setting]))});
  const evaluation = evaluateEvidence(proposal, data);
  const gaps: Row[] = []; const unmapped = selection.filter(p => evidence.sounds[p.id].status !== 'exact').map(p => p.id);
  if (unmapped.length) gaps.push({kind: 'inventory_evidence_gap', phoneme_ids: unmapped, note: 'These valid construction sounds lack one unambiguous exact PHOIBLE row or class match.'});
  if (request.tone_target) gaps.push({kind: 'tone_realization_deferred', note: 'Tone-class sounds can enter the inventory, but Step 11 v1 does not place tone on forms; Step 12 owns that rule.'});
  for (const name of ['allophony', 'vowel_harmony', 'consonant_harmony']) if (spec.extensions[name].status !== 'explicit_none') gaps.push({kind: `${name}_not_applied`, status: spec.extensions[name].status, note: 'No absence is inferred; executable rules are deferred to Step 12.'});
  return {generator_version: '1.0.0', specification_version: spec.specification_version, model_version: spec.model_version, specification_fingerprint: specificationFingerprint, request_fingerprint: fingerprint, seed: spec.seed, request, inventory: {phonemes: selection, counts: {consonants: selected.filter(p => p.class === 'consonant').length, vowels: vowels.length, tones: selected.filter(p => p.class === 'tone').length}}, forms, hard_rule_validation: validation, evidence: {selection_policy: evidence.note, scope: evidence.scope, analysis: evidence.analysis, evaluation, gaps, unusual_valid_designs_rejected: false}};
}

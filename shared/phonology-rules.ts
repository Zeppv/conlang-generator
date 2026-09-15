/** Step 12 realization of saved Step 11 forms. No reference-data access. */
export type Row = Record<string, any>;
export const ENGINE_VERSION = '1.1.0';
export const MAX_BYTES = 8 * 1024 * 1024;
export class RuleError extends Error {}
const fail = (path: string, message: string): never => { throw new RuleError(`${path}: ${message}`); };
const own = (value: object, key: string) => Object.hasOwn(value, key);
const equal = (a: any, b: any): boolean => canonicalJson(a) === canonicalJson(b);
const object = (value: any, path: string, keys?: string[]): Row => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) fail(path, 'must be an object');
  if (keys && (Object.keys(value).some(k => !keys.includes(k)) || keys.some(k => !own(value, k)))) fail(path, 'unknown or missing fields');
  return value;
};
const list = (value: any, path: string, min = 0, max = 256): any[] => {
  if (!Array.isArray(value) || value.length < min || value.length > max) fail(path, `requires ${min}-${max} entries`);
  return value;
};
const text = (value: any, path: string, max = 200): string => {
  if (typeof value !== 'string' || [...value].length < 1 || [...value].length > max) fail(path, 'invalid string');
  return value;
};
const oneOf = (value: any, choices: string[], path: string) => {
  if (!choices.includes(value)) fail(path, `expected ${choices.join(' or ')}`);
  return value;
};
function codepointOrder(a: string, b: string): number {
  const aa = [...a], bb = [...b];
  for (let i = 0; i < Math.min(aa.length, bb.length); i++) {
    const difference = aa[i].codePointAt(0)! - bb[i].codePointAt(0)!;
    if (difference) return difference;
  }
  return aa.length - bb.length;
}
// Python's length probability is always float, including 0.0 and 1.0.
function pythonProbability(value: number): string {
  if (Object.is(value, -0)) return '-0.0';
  if (Number.isInteger(value)) return `${value}.0`;
  if (Math.abs(value) < 1e-4) return value.toExponential().replace(/e([+-])(\d)$/, 'e$10$2');
  return String(value);
}
export function canonicalJson(value: any, path = '', numbersAsFloat = false): string {
  if (value === null || typeof value !== 'object') {
    if (typeof value === 'number' && !Number.isFinite(value)) fail('JSON', 'nonfinite number');
    if ((numbersAsFloat || path === 'length.probability') && typeof value === 'number') return pythonProbability(value);
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) return '[' + value.map(v => canonicalJson(v, '', numbersAsFloat)).join(',') + ']';
  return '{' + Object.keys(value).sort(codepointOrder).map(key => JSON.stringify(key) + ':' + canonicalJson(value[key], path ? `${path}.${key}` : key, numbersAsFloat)).join(',') + '}';
}
export async function sha256(value: string): Promise<string> {
  return [...new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value)))].map(b => b.toString(16).padStart(2, '0')).join('');
}
/** Reject duplicate keys and excessive nesting before JSON.parse can lose them. */
export function parseJson(source: string): any {
  if (new TextEncoder().encode(source).byteLength > MAX_BYTES) fail('JSON', 'exceeds 8 MiB');
  let index = 0;
  const ws = () => { while (/[\x20\t\r\n]/.test(source[index] ?? 'x')) index++; };
  const string = (): string => {
    const start = index++;
    while (index < source.length) {
      const c = source[index++];
      if (c === '\\') index++;
      else if (c === '"') return JSON.parse(source.slice(start, index));
    }
    return fail('JSON', 'unterminated string');
  };
  const value = (depth: number): void => {
    if (depth > 64) fail('JSON', 'nesting exceeds 64');
    ws();
    const c = source[index];
    if (c === '"') { string(); return; }
    if (c === '{' || c === '[') {
      index++; ws();
      const closing = c === '{' ? '}' : ']';
      const keys = new Set<string>();
      if (source[index] === closing) { index++; return; }
      while (index < source.length) {
        if (c === '{') {
          ws(); if (source[index] !== '"') fail('JSON', 'expected key');
          const key = string();
          if (keys.has(key)) fail('JSON', `duplicate key ${key}`);
          keys.add(key); ws();
          if (source[index++] !== ':') fail('JSON', 'expected colon');
        }
        value(depth + 1); ws();
        if (source[index] === closing) { index++; return; }
        if (source[index++] !== ',') fail('JSON', 'expected comma');
      }
      fail('JSON', 'unterminated container');
    }
    const start = index;
    while (index < source.length && !/[\x20\t\r\n,\]}]/.test(source[index])) index++;
    if (index === start) fail('JSON', 'expected value');
    const parsed = JSON.parse(source.slice(start, index));
    if (typeof parsed === 'number' && !Number.isFinite(parsed)) fail('JSON', 'nonfinite number');
  };
  try { value(0); ws(); if (index !== source.length) fail('JSON', 'trailing content'); return JSON.parse(source); }
  catch (error) { if (error instanceof RuleError) throw error; return fail('JSON', 'invalid JSON'); }
}

/** Validate fields consumed by realization. Full specification authoring remains in Python. */
export function savedSpecification(value: any): Row {
  const spec = object(value, 'specification');
  if (spec.specification_version !== '1.0.0' || spec.model_version !== 'phonology-v1-step10') fail('specification', 'unsupported version');
  text(spec.seed, 'specification.seed', 128); text(spec.name, 'specification.name');
  const phonemes = new Map<string, Row>(); const ipas = new Set<string>();
  for (const row of list(spec.phonemes, 'phonemes', 1)) {
    object(row, 'phoneme'); text(row.id, 'phoneme.id'); text(row.ipa, 'phoneme.ipa');
    if (!/^[a-z][a-z0-9_-]{0,63}$/.test(row.id) || phonemes.has(row.id) || ipas.has(row.ipa) || /\s/u.test(row.ipa)) fail('phoneme', 'duplicate or invalid identity');
    oneOf(row.class, ['consonant', 'vowel', 'tone'], 'phoneme.class');
    for (const [key, v] of Object.entries(object(row.features, 'features'))) { text(key, 'feature'); text(v, 'feature value'); }
    phonemes.set(row.id, row); ipas.add(row.ipa);
  }
  object(spec.classes, 'classes', ['consonants', 'vowels', 'tones']);
  for (const [key, cls] of [['consonants', 'consonant'], ['vowels', 'vowel'], ['tones', 'tone']]) {
    const ids = list(spec.classes[key], key, cls === 'vowel' ? 1 : 0);
    const expected = [...phonemes.values()].filter(p => p.class === cls).map(p => p.id).sort();
    if (!equal([...ids].sort(), expected)) fail('classes', 'must exactly partition phonemes');
  }
  const construction = object(spec.construction, 'construction');
  for (const key of ['onsets', 'codas']) {
    for (const cluster of list(construction[key], key, 1)) {
      if (list(cluster, key, 0, 8).some(id => phonemes.get(id)?.class !== 'consonant')) fail(key, 'requires consonants');
    }
  }
  const templateIds = new Set<string>();
  for (const template of list(construction.syllable_templates, 'templates', 1)) {
    text(template.id, 'template.id');
    if (templateIds.has(template.id) || typeof template.shape !== 'string' || !/^C*VC*$/.test(template.shape) || !(template.weight > 0) || !Number.isFinite(template.weight)) fail('template', 'invalid template');
    templateIds.add(template.id);
  }
  const weights = object(construction.syllable_count_weights, 'syllable counts');
  if (!Object.keys(weights).length || Object.entries(weights).some(([k,v]) => !/^([1-9]|1[0-6])$/.test(k) || typeof v !== 'number' || !(v > 0) || !Number.isFinite(v))) fail('syllable counts', 'invalid weights');
  const boundaries = object(construction.boundaries, 'boundaries');
  const boundary = text(boundaries.component_token, 'component token');
  const markers = list(object(boundaries.special_markers, 'special markers').tokens, 'marker tokens');
  if ([boundary, ...markers].some(token => typeof token !== 'string' || !token || phonemes.has(token) || ipas.has(token))) fail('boundaries', 'invalid structural token');
  oneOf(boundaries.cross_component_sequences, ['allowed', 'blocked'], 'boundaries');
  object(spec.prosody, 'prosody');
  for (const key of ['stress', 'tone', 'length_contrast']) object(spec.prosody[key], `prosody.${key}`);
  object(spec.extensions, 'extensions');
  for (const key of ['allophony', 'vowel_harmony', 'consonant_harmony']) object(spec.extensions[key], key);
  return spec;
}

export function canonicalRules(value: any, spec: Row): Row {
  const phonemes = new Map<string, Row>(spec.phonemes.map((p: Row) => [p.id, p]));
  const known = (id: any): Row => phonemes.get(id) ?? fail('rules', 'must reference a declared phoneme');
  const idList = (v: any, path: string): string[] => {
    const ids = list(v, path);
    if (ids.some(id => typeof id !== 'string' || !phonemes.has(id)) || new Set(ids).size !== ids.length) fail(path, 'invalid or duplicate phoneme IDs');
    return [...ids].sort(codepointOrder);
  };
  const section = (name: string, fields: string[]): Row => {
    const row = object(value[name], `rules.${name}`, ['status', ...fields]);
    oneOf(row.status, ['unknown', 'explicit_none', 'configured', 'deferred'], `rules.${name}.status`);
    if (row.status !== 'configured' && fields.some(f => row[f] !== null && !equal(row[f], []) && !equal(row[f], {}))) fail(name, 'fields must be empty unless configured');
    return row;
  };
  object(value, 'rules', ['rules_version', 'name', 'stress', 'tone', 'length', 'allophony', 'vowel_harmony', 'consonant_harmony', 'notes']);
  if (value.rules_version !== '1.0.0') fail('rules', 'unsupported rules version');
  text(value.name, 'rules.name');
  list(value.notes, 'notes', 0, 10000).forEach(note => text(note, 'note', MAX_BYTES));
  const stress = section('stress', ['rule']);
  const normalizedStress: Row = {status: stress.status, rule: null};
  if (stress.status === 'configured') {
    const r = object(stress.rule, 'stress.rule', ['type', 'position', 'marker']);
    if (r.type !== 'fixed') fail('stress', 'only fixed stress is supported');
    oneOf(r.position, ['initial', 'final'], 'stress.position'); oneOf(r.marker, ['ˈ', 'ˌ'], 'stress.marker');
    normalizedStress.rule = {...r};
  }
  const tone = section('tone', ['system', 'realization', 'tone_ids']);
  const normalizedTone: Row = {status: tone.status, system: null, realization: null, tone_ids: []};
  if (tone.status === 'configured') {
    if (tone.system !== 'lexical') fail('tone', 'only lexical tone is supported');
    oneOf(tone.realization, ['separate_token', 'attach_to_nucleus'], 'tone.realization');
    const ids = idList(tone.tone_ids, 'tone IDs');
    if (!ids.length || ids.some(id => known(id).class !== 'tone')) fail('tone', 'requires tone-class IDs');
    Object.assign(normalizedTone, {system: 'lexical', realization: tone.realization, tone_ids: ids});
  }
  const length = section('length', ['strategy', 'probability', 'pairs']);
  const normalizedLength: Row = {status: length.status, strategy: null, probability: null, pairs: []};
  if (length.status === 'configured') {
    if (length.strategy !== 'lexical' || typeof length.probability !== 'number' || !Number.isFinite(length.probability) || length.probability < 0 || length.probability > 1) fail('length', 'invalid strategy or probability');
    const shorts = new Set(), longs = new Set();
    const pairs = list(length.pairs, 'length.pairs', 1).map(pair => {
      object(pair, 'length pair', ['short_id', 'long_id']);
      const s = pair.short_id, l = pair.long_id;
      if (known(s).class !== 'vowel' || known(l).class !== 'vowel' || s === l || shorts.has(s) || longs.has(l)) fail('length', 'pairs must be distinct one-to-one vowels');
      shorts.add(s); longs.add(l); return {short_id: s, long_id: l};
    }).sort((a,b) => codepointOrder(a.short_id, b.short_id));
    Object.assign(normalizedLength, {strategy: 'lexical', probability: length.probability === 0 ? 0 : length.probability, pairs});
  }
  const allophony = section('allophony', ['rules']);
  const normalizedAllophony: Row = {status: allophony.status, rules: []};
  if (allophony.status === 'configured') {
    const ids = new Set();
    normalizedAllophony.rules = list(allophony.rules, 'allophony.rules', 1, 64).map(r => {
      object(r, 'allophony rule', ['id', 'underlying_id', 'surface_ipa', 'left', 'right', 'domain']);
      text(r.id, 'rule ID', MAX_BYTES);
      if (ids.has(r.id)) fail('allophony', 'duplicate rule ID'); ids.add(r.id); known(r.underlying_id);
      text(r.surface_ipa, 'surface IPA', MAX_BYTES);
      if (/\s/u.test(r.surface_ipa)) fail('surface IPA', 'must be one token');
      oneOf(r.domain, ['component', 'word'], 'allophony.domain');
      for (const side of ['left', 'right']) {
        const ctx = r[side];
        if (!['any', 'word_edge', 'component_edge', 'vowel', 'consonant'].includes(ctx)) {
          if (typeof ctx !== 'string' || !ctx.startsWith('phoneme:') || !phonemes.has(ctx.slice(8))) fail('allophony', 'unsupported context');
        }
      }
      return {...r};
    });
  }
  const harmonies: Row = {};
  for (const [name, cls] of [['vowel_harmony', 'vowel'], ['consonant_harmony', 'consonant']]) {
    const s = section(name, ['rules']);
    const normalized: Row = {status: s.status, rules: []};
    if (s.status === 'configured') {
      const ids = new Set();
      normalized.rules = list(s.rules, `${name}.rules`, 1, 64).map(r => {
        object(r, name, ['id', 'domain', 'direction', 'feature', 'trigger_ids', 'target_ids', 'blocker_ids', 'replacements']);
        text(r.id, 'rule ID', MAX_BYTES);
        if (ids.has(r.id)) fail(name, 'duplicate rule ID'); ids.add(r.id);
        oneOf(r.domain, ['component', 'word'], `${name}.domain`);
        if (r.domain === 'word' && spec.construction.boundaries.cross_component_sequences !== 'allowed') fail(name, 'word-domain harmony requires allowed cross-component behavior');
        oneOf(r.direction, ['progressive', 'regressive'], `${name}.direction`); text(r.feature, 'feature', MAX_BYTES);
        const triggers = idList(r.trigger_ids, 'triggers'), targets = idList(r.target_ids, 'targets'), blockers = idList(r.blocker_ids, 'blockers');
        if (!triggers.length || !targets.length || [...triggers, ...targets].some(id => known(id).class !== cls) || triggers.some(id => !own(known(id).features, r.feature))) fail(name, 'invalid trigger/target class or feature');
        const replacements: Row = Object.create(null);
        for (const [target, raw] of Object.entries(object(r.replacements, 'replacements'))) {
          const choices = object(raw, 'replacement choices');
          if (!targets.includes(target) || !Object.keys(choices).length) fail(name, 'replacement keys require targets and nonempty maps');
          replacements[target] = Object.create(null);
          for (const [featureValue, id] of Object.entries(choices)) {
            const p = known(id);
            if (p.class !== cls || p.features[r.feature] !== featureValue) fail(name, 'replacement does not carry the named feature value');
            replacements[target][featureValue] = id;
          }
        }
        return {...r, trigger_ids: triggers, target_ids: targets, blocker_ids: blockers, replacements};
      });
    }
    harmonies[name] = normalized;
  }
  for (const name of ['allophony', 'vowel_harmony', 'consonant_harmony']) {
    if (spec.extensions[name].status === 'explicit_none' && value[name].status === 'configured') fail(name, 'contradicts specification explicit absence');
  }
  for (const [name, specName] of [['stress', 'stress'], ['tone', 'tone'], ['length', 'length_contrast']]) {
    const setting = spec.prosody[specName].setting, status = value[name].status;
    if (status === 'configured' && ['none', 'absent'].includes(setting)) fail(name, 'contradicts specification explicit absence');
    if (status === 'explicit_none' && ['present', 'fixed', 'variable'].includes(setting)) fail(name, 'contradicts specification explicit presence');
  }
  if (stress.status === 'configured' && spec.prosody.stress.setting === 'fixed' && stress.rule.position !== spec.prosody.stress.position) fail('stress', 'contradicts specification stress position');
  const structural = [spec.construction.boundaries.component_token, ...spec.construction.boundaries.special_markers.tokens, 'ˈ', 'ˌ'];
  for (const r of normalizedAllophony.rules) if (structural.some(t => r.surface_ipa.includes(t))) fail('allophony', 'surface IPA must not contain structural or stress markers');
  return {rules_version: '1.0.0', name: value.name, stress: normalizedStress, tone: normalizedTone, length: normalizedLength, allophony: normalizedAllophony, ...harmonies, notes: [...value.notes]};
}

function tracePositions(form: Row, boundary: string) {
  const rebuilt: string[] = [], starts: number[] = [], nuclei: number[] = [];
  form.components.forEach((component: Row, ci: number) => {
    if (ci) rebuilt.push(boundary);
    for (const s of component.syllables) {
      starts.push(rebuilt.length); rebuilt.push(...s.onset); nuclei.push(rebuilt.length); rebuilt.push(s.nucleus, ...s.coda);
    }
  });
  if (!equal(rebuilt, form.phoneme_ids)) fail('form', 'generation trace does not match phoneme_ids');
  return {starts, nuclei};
}
function validateOutput(spec: Row, form: Row, ids: string[], selected: Set<string>) {
  let cursor = 0;
  form.components.forEach((component: Row, ci: number) => {
    if (ci && ids[cursor++] !== spec.construction.boundaries.component_token) fail('form', 'component boundary changed');
    for (const s of component.syllables) {
      const onsetEnd = cursor + s.onset.length, end = onsetEnd + 1 + s.coda.length;
      if (!spec.construction.onsets.some((row: string[]) => equal(row, ids.slice(cursor, onsetEnd))) || !spec.construction.codas.some((row: string[]) => equal(row, ids.slice(onsetEnd + 1, end)))) fail('form', 'phonological cluster is not allowed');
      if (!spec.classes.vowels.includes(ids[onsetEnd]) || ids.slice(cursor, end).some(id => !selected.has(id))) fail('form', 'phonological output violates classes or selected inventory');
      cursor = end;
    }
  });
  if (cursor !== ids.length) fail('form', 'phonological output length changed');
}
function validateGeneration(spec: Row, g: any) {
  object(g, 'generation');
  const pool = new Map<string, Row>(spec.phonemes.map((p: Row) => [p.id, p]));
  const selected = new Set<string>();
  for (const p of list(object(g.inventory, 'inventory').phonemes, 'inventory.phonemes', 1)) {
    object(p, 'inventory phoneme');
    if (!pool.has(p.id) || selected.has(p.id) || pool.get(p.id)!.ipa !== p.ipa) fail('inventory', 'unknown, duplicate or mismatched phoneme');
    selected.add(p.id);
  }
  text(g.request_fingerprint, 'generation.request_fingerprint', 100);
  if (object(g.hard_rule_validation, 'validation').valid !== true) fail('generation', 'hard-rule validation must be valid before realization');
  object(object(g.evidence, 'evidence').evaluation, 'evaluation');
  const templates = new Map<string, string>(spec.construction.syllable_templates.map((t: Row) => [t.id, t.shape]));
  const boundary = spec.construction.boundaries.component_token;
  let total = 0;
  list(g.forms, 'forms', 1, 1000).forEach((form, index) => {
    object(form, 'form');
    if (!Number.isInteger(form.word_index) || form.word_index !== index) fail('forms', 'word indexes must be consecutive from zero');
    const components = list(form.components, 'components', 1, 8);
    if (form.component_count !== components.length) fail('form', 'invalid component count');
    components.forEach((component, ci) => {
      object(component, 'component'); if (component.component_index !== ci) fail('form', 'invalid component index');
      const syllables = list(component.syllables, 'syllables', 1, 16);
      if (!own(spec.construction.syllable_count_weights, String(syllables.length))) fail('form', 'invalid syllable count');
      const rebuilt: string[] = [];
      for (const s of syllables) {
        object(s, 'syllable'); const onset = list(s.onset, 'onset', 0, 8), coda = list(s.coda, 'coda', 0, 8);
        const shape = 'C'.repeat(onset.length) + 'V' + 'C'.repeat(coda.length);
        if (s.shape !== shape || templates.get(s.template_id) !== shape) fail('form', 'template shape mismatch');
        const ids = [...onset, s.nucleus, ...coda];
        if (!equal(ids, s.phoneme_ids)) fail('form', 'syllable trace mismatch');
        rebuilt.push(...ids);
      }
      if (!equal(rebuilt, component.phoneme_ids)) fail('form', 'component trace mismatch');
    });
    tracePositions(form, boundary);
    validateOutput(spec, form, form.phoneme_ids, selected);
    if (!equal(form.ipa_tokens, form.phoneme_ids.map((id: string) => id === boundary ? boundary : pool.get(id)!.ipa))) fail('form', 'IPA trace mismatch');
    total += form.phoneme_ids.length;
    if (total > 20000) fail('forms', 'realization limit is 20000 total tokens');
  });
  return {pool, selected, boundary};
}
function contextMatches(context: string, side: string, index: number, ids: string[], boundary: string, classes: Row) {
  const neighbor = index + (side === 'left' ? -1 : 1);
  const edge = neighbor < 0 || neighbor >= ids.length, componentEdge = edge || ids[neighbor] === boundary;
  if (context === 'any') return !componentEdge;
  if (context === 'word_edge') return edge;
  if (context === 'component_edge') return componentEdge;
  if (componentEdge) return false;
  if (context === 'vowel') return classes.vowels.includes(ids[neighbor]);
  if (context === 'consonant') return classes.consonants.includes(ids[neighbor]);
  return context.startsWith('phoneme:') && ids[neighbor] === context.slice(8);
}
async function decisionUnit(spec: Row, namespace: string, index: number) {
  const hash = await sha256([spec.specification_version, spec.model_version, spec.seed, namespace, String(index)].join('\0'));
  return Number(BigInt('0x' + hash.slice(0, 32))) / 2 ** 128;
}
export async function realizeBundle(input: any): Promise<Row> {
  try { return await realize(input); }
  catch (error) {
    if (error instanceof RuleError) throw error;
    throw new RuleError('Malformed saved realization input');
  }
}
async function realize(input: any): Promise<Row> {
  const b = object(input, 'bundle');
  if (b.bundle_version !== 1 || b.rule_engine_version !== ENGINE_VERSION) fail('bundle', 'unsupported bundle or engine version');
  text(b.specification_json, 'specification_json', MAX_BYTES);
  const spec = savedSpecification(parseJson(b.specification_json));
  // All numeric fields in canonical Step 10 specifications are normalized weights.
  if (canonicalJson(spec, '', true) !== b.specification_json) fail('bundle', 'use the exported canonical specification JSON');
  const fingerprint = await sha256(b.specification_json);
  const rules = canonicalRules(b.rules, spec), ruleFingerprint = await sha256(canonicalJson(rules));
  const generation = b.generation;
  const {pool, selected, boundary} = validateGeneration(spec, generation);
  if (generation.specification_fingerprint !== fingerprint) fail('generation', 'specification fingerprint does not match');
  const required = new Set<string>(rules.tone.tone_ids);
  for (const pair of rules.length.pairs) if (selected.has(pair.short_id)) required.add(pair.long_id);
  if ([...required].some(id => !selected.has(id))) fail('rules', 'configured realization requires unselected phonemes');
  const forms: Row[] = [];
  for (const form of generation.forms) {
    const ids: string[] = [...form.phoneme_ids];
    const {starts, nuclei} = tracePositions(form, boundary);
    const events: Row[] = [];
    const namespace = `${generation.request_fingerprint}:rules:${ruleFingerprint}:word:${form.word_index}:`;
    if (rules.length.status === 'configured') {
      const pairs = new Map<string, string>(rules.length.pairs.map((p: Row) => [p.short_id, p.long_id]));
      for (const position of nuclei) {
        const short = ids[position];
        if (pairs.has(short) && await decisionUnit(spec, namespace + 'length', position) < rules.length.probability) {
          ids[position] = pairs.get(short)!;
          events.push({stage: 'length', position, from_id: short, to_id: ids[position], strategy: 'lexical'});
        }
      }
    }
    for (const name of ['vowel_harmony', 'consonant_harmony']) {
      for (const r of rules[name].rules) {
        const indexes = ids.map((_, i) => i); if (r.direction === 'regressive') indexes.reverse();
        let current: string | null = null;
        for (const index of indexes) {
          const id = ids[index];
          if (id === boundary) { if (r.domain === 'component') current = null; continue; }
          if (r.blocker_ids.includes(id)) { current = null; continue; }
          if (r.trigger_ids.includes(id)) { current = pool.get(id)!.features[r.feature]; continue; }
          if (current === null || !r.target_ids.includes(id)) continue;
          const replacement = own(r.replacements, id) && own(r.replacements[id], current) ? r.replacements[id][current] : null;
          if (replacement === null || replacement === id) continue;
          if (!selected.has(replacement)) fail(r.id, `harmony requires unselected replacement ${replacement}`);
          ids[index] = replacement;
          events.push({stage: 'harmony', rule_id: r.id, position: index, from_id: id, to_id: replacement, feature: r.feature, value: current});
        }
      }
    }
    validateOutput(spec, form, ids, selected);
    const surface = ids.map(id => id === boundary ? boundary : pool.get(id)!.ipa);
    const applied = new Set<number>();
    for (const r of rules.allophony.rules) {
      ids.forEach((id, index) => {
        if (applied.has(index) || id !== r.underlying_id) return;
        if (contextMatches(r.left, 'left', index, ids, boundary, spec.classes) && contextMatches(r.right, 'right', index, ids, boundary, spec.classes)) {
          const before = surface[index]; surface[index] = r.surface_ipa; applied.add(index);
          events.push({stage: 'allophony', rule_id: r.id, position: index, underlying_id: id, from_ipa: before, to_ipa: surface[index]});
        }
      });
    }
    const tones = new Map<number, string>();
    if (rules.tone.status === 'configured') {
      const options: string[] = rules.tone.tone_ids;
      for (const [syllableIndex, position] of nuclei.entries()) {
        const unit = await decisionUnit(spec, namespace + 'tone', syllableIndex);
        const toneId = options[Math.min(Math.floor(unit * options.length), options.length - 1)];
        tones.set(position, pool.get(toneId)!.ipa);
        events.push({stage: 'tone', position, tone_id: toneId, realization: rules.tone.realization});
      }
    }
    let stressedStart: number | null = null, stressMarker: string | null = null;
    if (rules.stress.status === 'configured' && starts.length) {
      const r = rules.stress.rule;
      stressedStart = r.position === 'initial' ? starts[0] : starts.at(-1)!; stressMarker = r.marker;
      events.push({stage: 'stress', position: stressedStart, rule: r.position, marker: stressMarker});
    }
    const output: string[] = [];
    surface.forEach((token, position) => {
      if (position === stressedStart) output.push(stressMarker!);
      if (tones.has(position) && rules.tone.realization === 'attach_to_nucleus') output.push(token + tones.get(position));
      else { output.push(token); if (tones.has(position)) output.push(tones.get(position)!); }
    });
    forms.push({word_index: form.word_index, underlying_phoneme_ids: [...form.phoneme_ids], phonological_phoneme_ids: ids, surface_tokens: output, surface_form: output.filter(t => t !== boundary).join(''), derivation: events});
  }
  const support: Row = {};
  const supported: Row = {stress: 'fixed_initial_or_final', tone: 'lexical_separate_or_attached', length: 'lexical_phoneme_pairs', allophony: 'bounded_context_rules', vowel_harmony: 'feature_progressive_or_regressive', consonant_harmony: 'feature_progressive_or_regressive'};
  for (const [name, label] of Object.entries(supported)) support[name] = rules[name].status === 'configured' ? label : rules[name].status;
  support.deferred = ['automatic stress-system induction', 'metrical stress', 'tone sandhi', 'non-lexical tone assignment', 'gradient/overlapping allophony', 'bidirectional harmony', 'opaque interactions', 'automatic rule induction'];
  const report = {
    rule_engine_version: ENGINE_VERSION, specification_fingerprint: fingerprint,
    generation_request_fingerprint: generation.request_fingerprint, rule_set_fingerprint: ruleFingerprint,
    seed: spec.seed, support, forms,
    evidence: {generation_evaluation: generation.evidence.evaluation, note: 'Rules are user declarations. Reference annotations remain descriptive evidence and did not select or validate these rule types.'},
  };
  if (own(b, 'report') && !equal(b.report, report)) fail('bundle', 'saved report does not reproduce from its inputs');
  return {bundle_version: 1, rule_engine_version: ENGINE_VERSION, specification_json: b.specification_json, rules, generation, report};
}

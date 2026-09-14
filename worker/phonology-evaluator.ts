// Serving implementation of scripts/analysis/phonology_evaluator.py v1.0.0.
// Numeric and status fields are checked against Python in the parity suite.
export type Row = Record<string, any>;
export type Proposal = {
  name: string; inventory: string[]; words: string[][]; syllable_templates: string[];
  reference_doculect: string | null; inventory_scope: 'inventory' | 'language';
  prosody: Record<string, string>;
};
export type Evidence = {
  catalog: Row; inventory: Row; tokens: Row[]; pairs: Map<string, any[]>; doc?: Row;
};
export class InputError extends Error {}
const fail = (message: string): never => { throw new InputError(message); };
const object = (v: unknown): v is Row => typeof v === 'object' && v !== null && !Array.isArray(v);
// Python str length counts Unicode code points, not UTF-16 code units.
const length = (s: string) => [...s].length;
// Python's whitespace definition intentionally includes control separators.
// oxlint-disable-next-line no-control-regex
const whitespace = /[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]/u;
export function proposalInput(value: unknown): Proposal {
  if (!object(value)) return fail('Proposal must be a JSON object');
  const fields = ['name', 'inventory', 'words', 'syllable_templates', 'reference_doculect', 'inventory_scope', 'prosody'];
  if (Object.keys(value).some(k => !fields.includes(k))) return fail('Unknown proposal fields');
  const p = { name: 'Unnamed proposal', inventory: [], words: [], syllable_templates: [], reference_doculect: null,
    inventory_scope: 'language', prosody: {}, ...value } as Proposal;
  if (typeof p.name !== 'string' || length(p.name) < 1 || length(p.name) > 200) fail('name must be a string of 1-200 characters');
  if (!['inventory', 'language'].includes(p.inventory_scope)) fail('inventory_scope must be inventory or language');
  const token = (t: unknown) => typeof t === 'string' && length(t) > 0 && length(t) <= 128 && !whitespace.test(t);
  if (!Array.isArray(p.inventory) || p.inventory.length < 1 || p.inventory.length > 256 || !p.inventory.every(token)) fail('inventory must contain 1-256 individual token strings');
  if (new Set(p.inventory).size !== p.inventory.length) fail('Duplicate inventory tokens are not allowed');
  if (!Array.isArray(p.words) || p.words.length > 1000 || p.words.some(w => !Array.isArray(w) || w.length < 1 || w.length > 128 || !w.every(token))) fail('words must contain at most 1000 token lists, each of length 1-128');
  if (!Array.isArray(p.syllable_templates) || p.syllable_templates.length > 64 || p.syllable_templates.some(s => typeof s !== 'string' || length(s) > 64 || !/^C*VC*$/u.test(s) || s.includes('\n'))) fail('syllable_templates must contain single-nucleus C*VC* strings');
  if (new Set(p.syllable_templates).size !== p.syllable_templates.length) fail('Duplicate syllable templates are not allowed');
  if (p.reference_doculect !== null && (typeof p.reference_doculect !== 'string' || length(p.reference_doculect) < 1 || length(p.reference_doculect) > 200)) fail('reference_doculect must be an exact Lexibank ID or null');
  if (!object(p.prosody) || Object.keys(p.prosody).some(k => !['stress', 'tone', 'length_contrast'].includes(k))) fail('prosody accepts stress, tone and length_contrast only');
  for (const [key, state] of Object.entries(p.prosody)) {
    if (!(key === 'stress' ? ['unknown', 'none', 'fixed', 'variable'] : ['unknown', 'present', 'absent']).includes(state)) fail(`Unsupported ${key} value`);
  }
  return p;
}
const round = (n: number, digits: number) => Number(n.toFixed(digits));
const fraction = (a: number, b: number) => b ? round(a / b, 8) : null;
const by = (rows: Row[], key: string) => new Map(rows.map(r => [r[key], r]));
const count = (items: string[]) => {
  const result = new Map<string, number>();
  for (const item of items) result.set(item, (result.get(item) ?? 0) + 1);
  return [...result.entries()].sort(([a], [b]) => compare(a, b));
};
// Code point ordering agrees with Python for supplementary IPA/unknown tokens.
const compare = (a: string, b: string) => {
  const aa = [...a], bb = [...b];
  for (let i = 0; i < Math.min(aa.length, bb.length); i++) {
    const d = aa[i].codePointAt(0)! - bb[i].codePointAt(0)!;
    if (d) return d;
  }
  return aa.length - bb.length;
};

export function evaluateEvidence(p: Proposal, data: Evidence): Row {
  const tokens = by(data.tokens, 'token'), declared = new Set(p.inventory), issues: Row[] = [];
  for (const token of p.inventory) {
    if (['+', '∼'].includes(token) || ['boundary', 'special'].includes(tokens.get(token)?.token_type)) issues.push({kind: 'structural_token_in_inventory', token});
  }
  p.words.forEach((word, word_index) => word.forEach((token, position) => {
    if (token === '∼' || tokens.get(token)?.token_type === 'special') issues.push({kind: 'special_marker_in_word', word_index, position, token});
    else if (token === '+') {
      if (!position || position === word.length - 1 || word[position - 1] === '+') issues.push({kind: 'empty_word_component', word_index, position});
    } else if (!declared.has(token)) issues.push({kind: 'undeclared_token', word_index, position, token});
  }));
  const builds = data.catalog.evidence_builds, analysis = builds.phonology_analysis;
  const units = analysis[p.inventory_scope === 'inventory' ? 'inventory_unit_count' : 'language_unit_count'];
  const segments = by(data.inventory.segments, 'phoneme');
  const prevalence = by(data.inventory.prevalence.filter((r: Row) => r.scope === p.inventory_scope), 'segment_id');
  const resolved: Row[] = [], classes = new Map<string, number>();
  const details = p.inventory.map(token => {
    const segment = segments.get(token);
    if (!segment) return {token, status: 'unmapped', prevalence: null};
    const e = prevalence.get(segment.id);
    if (!e || e.total_unit_count !== units || units <= 0 || e.unit_count < 0 || e.unit_count > units || Math.abs(e.prevalence - e.unit_count / units) > 1e-9) throw new Error('Incomplete prevalence evidence');
    resolved.push(segment);
    classes.set(segment.segment_class, (classes.get(segment.segment_class) ?? 0) + 1);
    return {token, status: 'exact_phoible_match', segment_class: segment.segment_class, unit_count: e.unit_count, total_units: units, prevalence: e.prevalence};
  });
  const profiles: Row[] = data.inventory.profiles;
  if (profiles.length !== analysis.inventory_unit_count || !profiles.length) throw new Error('Incomplete inventory profiles');
  const size: Row = {status: resolved.length === details.length ? 'available' : 'unknown', scope: 'inventory', measures: {},
    note: 'Percentiles describe inventory sizes, not quality; mapping must be complete.'};
  if (size.status === 'available') {
    for (const [column, value] of Object.entries({distinct_segment_count: resolved.length, consonant_count: classes.get('consonant') ?? 0, vowel_count: classes.get('vowel') ?? 0, tone_count: classes.get('tone') ?? 0})) {
      const population = profiles.map(r => r[column]).sort((a, b) => a - b);
      const rank = population.filter(x => x < value).length + 0.5 * population.filter(x => x === value).length;
      size.measures[column] = {proposed: value, midrank_percentile: round(100 * rank / population.length, 4), reference_median: (population[Math.floor((population.length - 1) / 2)] + population[Math.floor(population.length / 2)]) / 2, reference_units: population.length};
    }
  }
  const pairMap = new Map<string, any[]>();
  for (const [a, rows] of data.pairs) for (const row of rows) pairMap.set(`${a}:${row[0]}`, row);
  const pairs: Row[] = [];
  for (let i = 0; i < resolved.length; i++) for (const b of resolved.slice(i + 1)) {
    const a = resolved[i], [lo, hi] = [a.id, b.id].sort((x, y) => x - y);
    const row = pairMap.get(`${lo}:${hi}`);
    pairs.push({tokens: [a.phoneme, b.phoneme], status: row?.[3] ?? 'not_stored', joint_units: row?.[1] ?? null,
      expected_joint_units: row?.[2] ?? null, lift: row?.[4] ?? null, phi: row?.[5] ?? null});
  }
  const report: Row = {evaluator_version: '1.0.0', proposal: p, overall_naturalism_score: null,
    overall_note: 'Components use different populations and assumptions; no calibrated universal aggregate is available.',
    model_consistency: {valid: !issues.length, issues, scope: 'Inventory membership and structural-marker syntax only; not a grammaticality judgment.'},
    inventory: {scope: p.inventory_scope, units, mapping: 'Exact PHOIBLE strings only; no fuzzy or alias matching.',
      mapping_coverage: fraction(resolved.length, details.length), mapped_tokens: resolved.length, requested_tokens: details.length,
      segments: details, size_context: size, pairs,
      pair_coverage: {requested_pairs: details.length * (details.length - 1) / 2, mapped_pairs: pairs.length, stored_pairs: pairs.filter(r => r.status !== 'not_stored').length},
      note: 'Prevalence and associations are corpus descriptions. Rarity is not a defect. Missing stored pair rows are not zero counts.'},
    evidence_builds: {phonology_analysis: analysis}, raw_source_revalidated: false,
    reference_doculect: null, phonotactics: {status: 'reference_not_selected'}, syllables: {status: 'reference_not_selected'},
    prosody: {status: 'unassessed', proposal: p.prosody, score: null}};
  if (!p.reference_doculect) return report;
  const doc = data.doc;
  if (!doc || doc.language.lexibank_id !== p.reference_doculect) return fail('The selected doculect is not included in the active website snapshot');
  report.evidence_builds = builds;
  report.reference_doculect = doc.language;
  const profile = doc.phonotactic_profile[0];
  if (!profile) report.phonotactics = {status: 'missing_profile', observed_fraction_known_pairs: null};
  else {
    const bigrams = new Map<string, number[]>(doc.bigrams.map((r: number[]) => [`${r[0]}:${r[1]}`, r]));
    const requested = new Map<string, {tokens: string[]; count: number}>();
    for (const word of p.words) for (let i = 1; i < word.length; i++) {
      const pair = [word[i - 1], word[i]], key = JSON.stringify(pair);
      requested.set(key, {tokens: pair, count: (requested.get(key)?.count ?? 0) + 1});
    }
    let known = 0, observed = 0, total = 0;
    const rows = [...requested.values()].sort((a, b) => compare(a.tokens[0], b.tokens[0]) || compare(a.tokens[1], b.tokens[1])).map(({tokens: pair, count: n}) => {
      total += n;
      const [a, b] = pair.map(t => tokens.get(t));
      if (!a || !b || a.token_type === 'special' || b.token_type === 'special') return {tokens: pair, candidate_occurrences: n, status: 'unknown', source_occurrences: null};
      const e = bigrams.get(`${a.id}:${b.id}`), occurrences = e?.[2] ?? 0;
      known += n;
      observed += occurrences ? n : 0;
      return {tokens: pair, candidate_occurrences: n, status: occurrences ? 'observed' : 'not_observed', source_occurrences: occurrences, source_forms: e?.[3] ?? 0};
    });
    const unigrams = by(doc.tokens, 'token_id'), edges: Row[] = [];
    for (const edge of ['initial', 'final']) for (const [token, n] of count(p.words.map(w => edge === 'initial' ? w[0] : w[w.length - 1]))) {
      const t = tokens.get(token), source = !t || t.token_type === 'special' ? null : unigrams.get(t.id)?.[edge + '_count'] ?? 0;
      edges.push({edge, token, candidate_occurrences: n, status: source === null ? 'unknown' : source ? 'observed' : 'not_observed', source_forms: source});
    }
    report.phonotactics = {status: !p.words.length ? 'not_requested' : known < total ? 'partial' : 'available', source_forms: profile.form_count,
      requested_pair_positions: total, known_pair_positions: known, mapping_coverage: fraction(known, total), observed_pair_positions: observed,
      observed_fraction_known_pairs: fraction(observed, known), pairs: rows, word_edges: edges,
      note: 'This fraction measures observed adjacency in this doculect, not grammaticality. Unknown pairs are excluded with coverage shown. Raw boundaries are retained; forms are never joined.'};
  }
  const syllable = doc.syllable_profile[0];
  if (!syllable) report.syllables = {status: 'missing_profile', templates: []};
  else {
    const candidates = new Map<string, Row>(doc.syllables.map((r: Row) => [`${r.onset_length}:${r.coda_length}`, r]));
    report.syllables = {status: syllable.eligible_forms ? 'available' : 'unknown', source_forms: syllable.form_count,
      eligible_forms: syllable.eligible_forms, coverage: fraction(syllable.eligible_forms, syllable.form_count), projected_nuclei: syllable.projected_nuclei,
      ambiguous_nuclei: syllable.ambiguous_nuclei, templates: p.syllable_templates.map(template => {
        const [onset, coda] = template.split('V'), row = candidates.get(`${onset.length}:${coda.length}`);
        const available = syllable.projected_nuclei > 0, possible = available ? row?.possible_slots ?? 0 : null, forced = available ? row?.forced_slots ?? 0 : null;
        return {template, status: !available ? 'unknown' : forced ? 'forced_support' : possible ? 'possible_support' : 'not_observed', possible_slots: possible, forced_slots: forced,
          possible_nucleus_fraction: available ? fraction(possible!, syllable.projected_nuclei) : null};
      }), exclusions: doc.exclusions,
      note: 'Shape support is conditional on the Step 6 projection. Alternatives overlap; fractions are not syllable-choice probabilities. Proposed words are not automatically syllabified.'};
  }
  const localCounts = [profile, syllable, doc.prosody_profile[0]].filter(Boolean).map(r => r.form_count);
  if (new Set(localCounts).size > 1) throw new Error('Doculect profile counts differ');
  Object.assign(report.prosody, {reference_status: doc.prosody_profile.length ? 'available' : 'missing_profile', annotations: doc.annotations, token_features: doc.features,
    note: 'Reference annotations do not establish stress rules, tone-system type, or length contrast. Missing markers do not mean absence; proposed system properties remain unassessed.'});
  return report;
}

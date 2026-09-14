import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import type { Row } from '../worker/phonology-evaluator';
import './Phonology.css';

const percent = (value: number | null | undefined) => value == null ? 'Unknown' : `${(value * 100).toFixed(1)}%`;
const number = (value: number | null | undefined) => value == null ? 'Unknown' : value.toLocaleString();
const wordsOf = (value: string) => value.trim() ? value.trim().split(/\s+/u) : [];
const label = (value: string) => value.replaceAll('_', ' ');

export default function Phonology() {
  const [catalog, setCatalog] = useState<Row | null>(null);
  const [name, setName] = useState('Demonstration sound system');
  const [inventory, setInventory] = useState('p t k m n s l a i u');
  const [words, setWords] = useState('p a\nt i\nk u\nm a n');
  const [templates, setTemplates] = useState('CV CVC');
  const [reference, setReference] = useState('northeuralex-eng');
  const [scope, setScope] = useState('language');
  const [prosody, setProsody] = useState<Record<string, string>>({stress: 'unknown', tone: 'unknown', length_contrast: 'unknown'});
  const [report, setReport] = useState<Row | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/phonology/status', {signal: controller.signal}).then(async response => {
      const data = await response.json();
      if (!response.ok) throw new Error(data.error ?? 'Unable to load phonology evidence.');
      setCatalog(data);
      if (!data.doculects.some((d: Row) => d.lexibank_id === 'northeuralex-eng')) setReference('');
    }).catch(err => { if (!controller.signal.aborted) setError(err.message); });
    return () => controller.abort();
  }, []);

  async function evaluate(event: FormEvent) {
    event.preventDefault();
    setLoading(true); setError(''); setReport(null);
    try {
      const response = await fetch('/api/phonology/evaluate', {method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name, inventory: wordsOf(inventory), words: words.split(/\r?\n/u).filter(w => w.trim()).map(wordsOf),
          syllable_templates: wordsOf(templates), reference_doculect: reference || null, inventory_scope: scope, prosody})});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error ?? 'Evaluation failed.');
      setReport(data);
    } catch (err) { setError(err instanceof Error ? err.message : 'Evaluation failed.'); }
    finally { setLoading(false); }
  }

  function download() {
    const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], {type: 'application/json'}));
    const link = document.createElement('a'); link.href = url; link.download = 'phonology-evaluation.json'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return <main className="page phonology">
    <header className="hero"><p className="eyebrow">PHONOLOGY WORKBENCH</p><h1>Explore a sound system</h1>
      <p className="intro">Compare your sounds and sample words with real-language evidence. See what is supported, what is unusual, and where the evidence is limited.</p></header>
    <div className="phonologyLayout">
      <form className="panel proposal" onSubmit={evaluate} onChange={() => setReport(null)}>
        <h2>Your proposal</h2>
        <fieldset disabled={loading}>
          <label htmlFor="proposalName">Name</label><input id="proposalName" value={name} maxLength={200} onChange={e => setName(e.target.value)} required />
          <label htmlFor="inventory">Sound inventory</label><textarea id="inventory" rows={3} value={inventory} onChange={e => setInventory(e.target.value)} aria-describedby="inventoryHelp" required />
          <p id="inventoryHelp" className="help">Separate each IPA token with a space. Multi-character sounds such as kʰ stay together. Matching is exact.</p>
          <label htmlFor="words">Sample words</label><textarea id="words" rows={5} value={words} onChange={e => setWords(e.target.value)} aria-describedby="wordHelp" />
          <p id="wordHelp" className="help">One word per line, with spaces between tokens: p a n. Use + for an internal component boundary.</p>
          <label htmlFor="templates">Syllable templates</label><input id="templates" value={templates} onChange={e => setTemplates(e.target.value)} aria-describedby="templateHelp" />
          <p id="templateHelp" className="help">C = consonant, V = vowel nucleus. Separate templates with spaces, such as V CV CVC.</p>
          <label htmlFor="reference">Lexical comparison</label><select id="reference" value={reference} onChange={e => setReference(e.target.value)}>
            <option value="">No lexical comparison</option>
            {(catalog?.doculects ?? []).map((d: Row) => <option key={d.lexibank_id} value={d.lexibank_id}>{d.name} · {d.lexibank_id}</option>)}
          </select><p className="help">Each option is one dataset's language variety. English is a demonstration reference, not a universal standard. The list contains the doculects included in your website sync.</p>
          <label htmlFor="scope">Inventory evidence population</label><select id="scope" value={scope} onChange={e => setScope(e.target.value)}>
            <option value="language">Languages (combine inventories per language)</option><option value="inventory">Individual documented inventories</option>
          </select>
          <details className="prosodyInput"><summary>Proposed prosody (optional)</summary>
            <p className="help">These choices are recorded. Available annotations cannot yet validate stress rules, tone systems, or contrastive length.</p>
            {Object.entries(prosody).map(([feature, state]) => <label key={feature}>{label(feature)}<select value={state} onChange={e => setProsody({...prosody, [feature]: e.target.value})}>
              {(feature === 'stress' ? ['unknown', 'none', 'fixed', 'variable'] : ['unknown', 'present', 'absent']).map(s => <option key={s}>{s}</option>)}</select></label>)}
          </details>
          <button className="primaryButton" type="submit" disabled={!catalog}>{loading ? 'Evaluating…' : 'Evaluate sound system'}</button>
        </fieldset>
      </form>
      <div className="evidenceColumn" aria-busy={loading}>
        {error && <div className="panel error" role="alert">{error}</div>}
        {!catalog && !error && <p role="status">Loading available evidence…</p>}
        {loading && <p role="status">Comparing your proposal with the selected evidence…</p>}
        {!report && !loading && <section className="panel emptyEvidence"><p className="eyebrow">EVIDENCE, WITH CONTEXT</p><h2>Start with the example or enter your own sounds.</h2>
          <p>Your results will separate inventory frequency, word-sequence evidence, possible syllable shapes, and prosody annotations.</p>
          <p>Rarity is not an error. Missing evidence stays unknown. These measures do not combine into a validated overall naturalness score.</p></section>}
        {report && <>
          <section className="panel"><div className="reportHeading"><div><p className="eyebrow">EVALUATION COMPLETE</p><h2>{report.proposal.name}</h2></div><button type="button" onClick={download}>Download report</button></div>
            <p role="status">{report.model_consistency.valid ? 'Inventory membership and boundary checks passed.' : 'Review the inventory membership or boundary issues below.'}</p>
            {report.model_consistency.issues.length > 0 && <ul>{report.model_consistency.issues.slice(0, 30).map((issue: Row, i: number) => <li key={i}>{label(issue.kind)}{issue.token ? `: ${issue.token}` : ''}{issue.word_index != null ? ` (word ${issue.word_index + 1}, token ${issue.position + 1})` : ''}</li>)}</ul>}
            {report.model_consistency.issues.length > 30 && <p>Showing the first 30 issues; download the report for all issues.</p>}
            <p className="help">This checks the proposal's notation and membership, not grammaticality. No overall naturalness score is assigned.</p>
          </section>
          <section className="panel"><p className="eyebrow">01 · INVENTORY</p><h2>Sounds and their frequency</h2>
            <div className="evidenceMetrics"><div><strong>{report.inventory.mapped_tokens}/{report.inventory.requested_tokens}</strong><span>Exact sound matches</span></div><div><strong>{number(report.inventory.units)}</strong><span>{scope === 'language' ? 'Language evidence units' : 'Inventory evidence units'}</span></div></div>
            <div className="tableScroll"><table><thead><tr><th>Sound</th><th>Class / mapping</th><th>Observed units</th><th>Prevalence</th></tr></thead><tbody>{report.inventory.segments.map((s: Row) => <tr key={s.token}><td className="ipa">{s.token}</td><td>{s.segment_class ?? 'Unmapped'}</td><td>{number(s.unit_count)}</td><td>{percent(s.prevalence)}</td></tr>)}</tbody></table></div>
            <p className="help">{report.inventory.note}</p>
            <details><summary>Inventory size context</summary>{report.inventory.size_context.status === 'unknown' ? <p>Size comparisons require complete sound mapping.</p> : <div className="tableScroll"><table><thead><tr><th>Measure</th><th>Proposed</th><th>Reference median</th><th>Size percentile</th></tr></thead><tbody>{Object.entries(report.inventory.size_context.measures as Record<string, Row>).map(([key, v]) => <tr key={key}><td>{label(key)}</td><td>{v.proposed}</td><td>{v.reference_median}</td><td>{v.midrank_percentile.toFixed(1)}</td></tr>)}</tbody></table></div>}<p className="help">Percentiles describe size among inventories, not quality.</p></details>
            <details><summary>Sound-pair evidence · {report.inventory.pair_coverage.stored_pairs} stored / {report.inventory.pair_coverage.requested_pairs} proposed pairs</summary>
              <div className="tableScroll"><table><thead><tr><th>Sounds</th><th>Evidence</th><th>Joint units</th><th>Lift</th></tr></thead><tbody>{report.inventory.pairs.slice(0, 100).map((p: Row) => <tr key={p.tokens.join(' ')}><td className="ipa">{p.tokens.join(' · ')}</td><td>{label(p.status)}</td><td>{number(p.joint_units)}</td><td>{p.lift?.toFixed(2) ?? 'Unknown'}</td></tr>)}</tbody></table></div><p className="help">Lift compares joint frequency with statistical independence. “Expected absence” means no joint observation despite sufficient expected support. Missing stored pairs stay unknown. Up to 100 pairs shown; all are in the download.</p>
            </details>
          </section>
          <section className="panel"><p className="eyebrow">02 · WORD SEQUENCES</p><h2>Adjacency in the selected reference</h2>
            {report.reference_doculect && <p>{report.reference_doculect.name} · {report.reference_doculect.lexibank_id}</p>}
            {report.phonotactics.source_forms == null ? <p>{label(report.phonotactics.status)}</p> : <>
              <div className="evidenceMetrics"><div><strong>{percent(report.phonotactics.observed_fraction_known_pairs)}</strong><span>Known pair positions observed</span></div><div><strong>{percent(report.phonotactics.mapping_coverage)}</strong><span>Pair mapping coverage</span></div><div><strong>{number(report.phonotactics.source_forms)}</strong><span>Reference forms</span></div></div>
              <div className="tableScroll"><table><thead><tr><th>Adjacent tokens</th><th>Evidence</th><th>Source occurrences</th></tr></thead><tbody>{report.phonotactics.pairs.slice(0, 100).map((p: Row) => <tr key={p.tokens.join(' ')}><td className="ipa">{p.tokens.join(' → ')}</td><td>{label(p.status)}</td><td>{number(p.source_occurrences)}</td></tr>)}</tbody></table></div>
              <p className="help">{report.phonotactics.note} Up to 100 pairs shown; the report includes all pairs and word-edge evidence.</p></>}
          </section>
          <section className="panel"><p className="eyebrow">03 · SYLLABLE CANDIDATES</p><h2>Possible shapes, with exclusions</h2>
            {report.syllables.source_forms == null ? <p>{label(report.syllables.status)}</p> : <><p>{number(report.syllables.eligible_forms)} / {number(report.syllables.source_forms)} forms eligible ({percent(report.syllables.coverage)}). {number(report.syllables.ambiguous_nuclei)} nuclei have ambiguous splits.</p>
              <div className="tableScroll"><table><thead><tr><th>Template</th><th>Support</th><th>Possible slots</th><th>Forced slots</th></tr></thead><tbody>{report.syllables.templates.map((s: Row) => <tr key={s.template}><td>{s.template}</td><td>{label(s.status)}</td><td>{number(s.possible_slots)}</td><td>{number(s.forced_slots)}</td></tr>)}</tbody></table></div>
              <p className="help">“Forced” means the shape occurs in every allowed split at that position under the candidate model. {report.syllables.note}</p>
              <details><summary>Excluded forms</summary><ul>{report.syllables.exclusions.map((r: Row) => <li key={r.reason}>{label(r.reason)}: {number(r.form_count)}</li>)}</ul></details></>}
          </section>
          <section className="panel"><p className="eyebrow">04 · PROSODY</p><h2>Annotations; system rules unassessed</h2>
            <p>Stress, tone, and length marks provide evidence about the transcription. They do not establish a language's complete prosodic system.</p>
            {(report.prosody.annotations ?? []).length > 0 && <details><summary>Stress annotation coverage</summary><div className="tableScroll"><table><thead><tr><th>Source field</th><th>Marker</th><th>Marked / available forms</th></tr></thead><tbody>{report.prosody.annotations.map((r: Row) => <tr key={r.source_field + r.marker}><td>{r.source_field}</td><td>{label(r.marker)}</td><td>{number(r.marked_forms)} / {number(r.available_forms)}</td></tr>)}</tbody></table></div></details>}
            {(report.prosody.token_features ?? []).length > 0 && <details><summary>Tone and length token evidence</summary><ul>{report.prosody.token_features.map((r: Row) => <li key={r.feature}>{label(r.feature)}: {number(r.form_count)} forms ({label(r.status)})</li>)}</ul></details>}
            <p className="help">No observed marks does not mean the feature is absent.</p>
          </section>
          <details className="panel"><summary>Evidence versions and full report</summary><p className="help">Evaluator {report.evaluator_version}. Source builds are reused; this evaluation does not rescan raw data. The download includes source fingerprints and the website snapshot ID.</p><pre>{JSON.stringify(report.evidence_builds, null, 2)}</pre></details>
        </>}
      </div>
    </div>
  </main>;
}

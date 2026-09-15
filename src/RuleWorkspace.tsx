import { useState } from 'react';
import { canonicalJson, canonicalRules, MAX_BYTES, parseJson, realizeBundle } from '../shared/phonology-rules';
import type { Row } from '../shared/phonology-rules';
import example from '../examples/phonology-workspace.json';
import './Phonology.css';
import './RuleWorkspace.css';
import GenerationControls from './GenerationControls';

const pretty = (value: unknown) => JSON.stringify(value, null, 2);
const message = (error: unknown) => error instanceof Error ? error.message : 'Unable to process this run.';
const label = (value: string) => value.replaceAll('_', ' ');
function download(value: unknown, filename: string) {
  const url = URL.createObjectURL(new Blob([pretty(value) + '\n'], {type: 'application/json'}));
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = filename;
  anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function RuleWorkspace() {
  const [bundle, setBundle] = useState<Row | null>(null);
  const [rulesText, setRulesText] = useState('');
  const [result, setResult] = useState<Row | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [filename, setFilename] = useState('');
  const spec = bundle ? parseJson(bundle.specification_json) : null;
  let rules: Row | null = null;
  try { rules = rulesText && spec ? canonicalRules(parseJson(rulesText), spec) : null; } catch { /* The editor can contain unfinished JSON. */ }
  const vowels: Row[] = bundle?.generation.inventory.phonemes.filter((p: Row) => spec.classes.vowels.includes(p.id)) ?? [];
  const tones: Row[] = bundle?.generation.inventory.phonemes.filter((p: Row) => spec.classes.tones.includes(p.id)) ?? [];
  const report = result?.report;

  async function load(source: unknown, name: string) {
    setBusy(true); setError(''); setResult(null); setBundle(null); setNotice(''); setRulesText('');
    try {
      const loaded = await realizeBundle(source);
      setBundle(loaded); setRulesText(pretty(loaded.rules)); setResult(loaded); setFilename(name);
      setNotice('Run loaded and reproduced.');
    } catch (err) { setError(message(err)); }
    finally { setBusy(false); }
  }
  async function loadFile(file?: File) {
    if (!file) return;
    setBusy(true);
    try {
      if (file.size > MAX_BYTES) throw new Error('Saved run exceeds 8 MiB.');
      await load(parseJson(await file.text()), file.name);
    } catch (err) { setBundle(null); setResult(null); setRulesText(''); setNotice(''); setError(message(err)); }
    finally { setBusy(false); }
  }
  function edit(source: string) { setRulesText(source); setResult(null); setNotice('Changes have not been applied.'); setError(''); }
  function change(name: string, value: Row) {
    if (!rules) return;
    edit(pretty({...rules, [name]: value}));
  }
  async function apply() {
    if (!bundle) return;
    setBusy(true); setError(''); setNotice(''); setResult(null);
    try {
      const {report: _previous, ...inputs} = bundle;
      const proposed = {...inputs, rules: parseJson(rulesText)};
      const local = await realizeBundle(proposed);
      const body = JSON.stringify(proposed);
      if (new TextEncoder().encode(body).byteLength > MAX_BYTES) throw new Error('Saved run exceeds 8 MiB.');
      const response = await fetch('/api/phonology/realize', {method: 'POST', headers: {'Content-Type': 'application/json'}, body});
      const server = await response.json();
      if (!response.ok) throw new Error(server.error ?? 'Unable to apply rules.');
      if (canonicalJson(server) !== canonicalJson(local)) throw new Error('Browser and server results disagree. No result was accepted.');
      setBundle(local); setRulesText(pretty(local.rules)); setResult(local);
      setNotice('Rules applied. Browser and server results match.');
    } catch (err) { setError(message(err)); }
    finally { setBusy(false); }
  }

  return <main className="phonology page ruleWorkspace">
    <header className="hero">
      <p className="eyebrow">PHONOLOGY · RULE WORKSPACE</p>
      <h1>From sounds to spoken forms</h1>
      <p className="intro">Generate a sound system or open a saved run. Follow each transformation and keep the full run for later.</p>
    </header>
    <GenerationControls bundle={bundle} rulesText={rulesText} busy={busy} onGenerated={load} />
    <section className="panel runLoader">
      <div><h2>Open a saved run</h2><p>Load a workspace JSON exported from your Step 11 forms, or try three illustrative forms.</p></div>
      <div className="runActions">
        <label className="fileButton">Load run<input aria-label="Load saved run" type="file" accept=".json,application/json" disabled={busy} onChange={e => { void loadFile(e.target.files?.[0]); e.target.value = ''; }} /></label>
        <button type="button" disabled={busy} onClick={() => void load(example, 'Illustrative example')}>Try example</button>
      </div>
      <details><summary>Export my existing forms</summary>
        <p>Run this once in your project folder, then load <code>data/compiled/phonology-workspace.json</code> here.</p>
        <pre>python scripts\analysis\apply_phonology_rules.py --bundle-output data\compiled\phonology-workspace.json</pre>
        <p className="help">This reads your saved generation and writes JSON. Your source data is unchanged.</p>
      </details>
    </section>
    {error && <p className="error" role="alert">{error}</p>}
    <p className="status" role="status" aria-live="polite">{busy ? 'Processing run…' : notice}</p>
    {!bundle && <section className="panel emptyEvidence"><h2>Keep the system and its history together</h2><p>A saved run carries its sound inventory, construction rules, sample forms, and available evidence. Rule changes produce a new realization while preserving those inputs.</p></section>}
    {bundle && <div className="phonologyLayout">
      <section className="panel proposal">
        <h2>Rule choices</h2>
        <p className="help">Unknown means undecided. Explicit none is your declaration that a rule family is absent.</p>
        <fieldset disabled={busy}>
          <label htmlFor="stressChoice">Stress</label>
          <select id="stressChoice" value={rules?.stress?.status === 'configured' ? rules.stress.rule?.position : rules?.stress?.status ?? ''} disabled={!rules?.stress} onChange={e => change('stress', ['initial', 'final'].includes(e.target.value) ? {status: 'configured', rule: {type: 'fixed', position: e.target.value, marker: 'ˈ'}} : {status: e.target.value, rule: null})}>
            <option value="unknown">Unknown</option><option value="explicit_none">Explicit none</option><option value="initial">Initial syllable</option><option value="final">Final syllable</option><option value="deferred">Deferred</option>
          </select>
          <label htmlFor="toneChoice">Lexical tone</label>
          <select id="toneChoice" value={rules?.tone?.status === 'configured' ? rules.tone.realization : rules?.tone?.status ?? ''} disabled={!rules?.tone} onChange={e => change('tone', ['separate_token', 'attach_to_nucleus'].includes(e.target.value) ? {status: 'configured', system: 'lexical', realization: e.target.value, tone_ids: rules?.tone?.tone_ids?.length ? rules.tone.tone_ids : tones.map(p => p.id)} : {status: e.target.value, system: null, realization: null, tone_ids: []})}>
            <option value="unknown">Unknown</option><option value="explicit_none">Explicit none</option><option value="separate_token" disabled={!tones.length}>Separate tone token</option><option value="attach_to_nucleus" disabled={!tones.length}>Attach to vowel</option><option value="deferred">Deferred</option>
          </select>
          <p className="help">{tones.length ? `Available tone IDs: ${tones.map(p => p.id).join(', ')}. Choose a subset in the full rule editor.` : 'This inventory has no tone phonemes.'}</p>
          <label htmlFor="lengthChoice">Phonemic length</label>
          <select id="lengthChoice" value={rules?.length?.status ?? ''} disabled={!rules?.length} onChange={e => change('length', e.target.value === 'configured' ? {status: 'configured', strategy: 'lexical', probability: 0.5, pairs: [{short_id: vowels[0]?.id, long_id: vowels[1]?.id}]} : {status: e.target.value, strategy: null, probability: null, pairs: []})}>
            <option value="unknown">Unknown</option><option value="explicit_none">Explicit none</option><option value="configured" disabled={vowels.length < 2}>Declare vowel pairs</option><option value="deferred">Deferred</option>
          </select>
          {rules?.length?.status === 'configured' && <>
            <p className="help">Select the short and long members explicitly. The engine does not infer length from the vowel labels.</p>
            {(Array.isArray(rules.length.pairs) ? rules.length.pairs : []).map((pair: Row, index: number) => <div className="lengthPair" key={index}>
              {(['short_id', 'long_id'] as const).map(side => <label key={side}>{side === 'short_id' ? 'Short vowel' : 'Long vowel'}<select value={pair[side]} onChange={e => change('length', {...rules!.length, pairs: rules!.length.pairs.map((p: Row, i: number) => i === index ? {...p, [side]: e.target.value} : p)})}>{vowels.map(p => <option key={p.id} value={p.id} disabled={p.id === pair[side === 'short_id' ? 'long_id' : 'short_id'] || rules!.length.pairs.some((other: Row, i: number) => i !== index && other[side] === p.id)}>{p.ipa} ({p.id})</option>)}</select></label>)}
            </div>)}
            <label htmlFor="lengthProbability">Probability of choosing the long member</label>
            <input id="lengthProbability" type="number" min="0" max="1" step="0.05" value={rules.length.probability ?? ''} onChange={e => { const value = Number(e.target.value); if (e.target.value !== '' && Number.isFinite(value) && value >= 0 && value <= 1) change('length', {...rules!.length, probability: value}); }} />
          </>}
          <details open><summary>Allophony, harmony, and full rule editor</summary>
            <p className="help">Use stable sound IDs from the inventory. Allophony uses left/right contexts; harmony declares its feature, direction, domain, triggers, targets, and blockers.</p>
            <label htmlFor="rulesJson">Rules JSON</label>
            <textarea id="rulesJson" className="rulesEditor" rows={18} spellCheck={false} value={rulesText} onChange={e => edit(e.target.value)} />
          </details>
          <button type="button" className="primaryButton" onClick={() => void apply()}>Apply rules</button>
        </fieldset>
      </section>
      <div className="evidenceColumn">
        <section className="panel">
          <h2>{spec.name}</h2><p className="help">{filename} · Seed: {spec.seed}</p>
          {bundle.generation.inventory.counts && <p>{bundle.generation.inventory.counts.consonants} consonants · {bundle.generation.inventory.counts.vowels} vowels · {bundle.generation.inventory.counts.tones} tones</p>}
          {bundle.generation.request && <details><summary>Inventory selection and generation settings</summary><pre>{pretty({request: bundle.generation.request, choices: bundle.generation.inventory.phonemes, evidence_gaps: bundle.generation.evidence.gaps, saved_evidence: bundle.generation.web_reproduction?.snapshot ?? null})}</pre></details>}
          <div className="soundInventory">{bundle.generation.inventory.phonemes.map((p: Row) => <span key={p.id}><strong className="ipa">{p.ipa}</strong><small>{p.id}</small></span>)}</div>
          <p>{bundle.generation.forms.length} forms · Construction checked on load and after length/harmony.</p>
        </section>
        {report ? <>
          <section className="panel">
            <div className="reportHeading"><h2>Realized forms</h2><button type="button" onClick={() => download(result, 'phonology-workspace.json')}>Save complete run</button></div>
            <p className="help">Underlying sounds stay intact. Expand a form to inspect the ordered changes.</p>
            <div className="formList">{report.forms.map((form: Row, i: number) => <details key={form.word_index}>
              <summary><span className="ipa">{bundle.generation.forms[i].ipa_tokens.join(' ')} <span aria-hidden="true">→</span> {form.surface_form}</span><small>{form.derivation.length} changes</small></summary>
              <p className="help">Phonological IDs: {form.phonological_phoneme_ids.join(' ')}<br />Surface tokens: {form.surface_tokens.join(' ')}</p>
              {form.derivation.length ? <ol>{form.derivation.map((event: Row, index: number) => <li key={index}><strong>{label(event.stage)}</strong> · token {event.position + 1}{event.from_id ? `: ${event.from_id} → ${event.to_id}` : event.from_ipa ? `: ${event.from_ipa} → ${event.to_ipa}` : event.tone_id ? `: ${event.tone_id}` : `: ${event.rule} ${event.marker}`}{event.rule_id ? ` (${event.rule_id})` : ''}</li>)}</ol> : <p>No configured rule changed this form.</p>}
            </details>)}</div>
          </section>
          <section className="panel"><h2>Support and limits</h2><div className="tableScroll"><table><thead><tr><th>Family</th><th>This run</th></tr></thead><tbody>{Object.entries(report.support).filter(([k]) => k !== 'deferred').map(([key, value]) => <tr key={key}><td>{label(key)}</td><td>{label(String(value))}</td></tr>)}</tbody></table></div><details><summary>Deferred rule families</summary><ul>{report.support.deferred.map((s: string) => <li key={s}>{s}</li>)}</ul></details></section>
          <section className="panel"><h2>Evidence carried with this run</h2><p>{report.evidence.note}</p>{report.evidence.generation_evaluation.status === 'illustrative_example' && <p>{report.evidence.generation_evaluation.note}</p>}<details><summary>Inspect saved evaluation</summary><pre>{pretty(report.evidence.generation_evaluation)}</pre></details><details><summary>Reproduction details</summary><pre>{pretty({engine: report.rule_engine_version, specification: report.specification_fingerprint, rules: report.rule_set_fingerprint, generation: report.generation_request_fingerprint})}</pre></details></section>
        </> : <section className="panel emptyEvidence"><h2>Apply your changes</h2><p>The next realization will use these rules and the same saved forms.</p></section>}
      </div>
    </div>}
  </main>;
}

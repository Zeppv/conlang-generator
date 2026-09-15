import { useState } from 'react';
import { canonicalJson, parseJson } from '../shared/phonology-rules';
import type { Row } from '../shared/phonology-rules';
import example from '../examples/phonology-workspace.json';
import defaultRequest from '../examples/phonology-generation-request.json';

type Props = {bundle: Row | null; rulesText: string; busy: boolean; onGenerated: (value: Row, name: string) => Promise<void>};
export default function GenerationControls({bundle, rulesText, busy, onGenerated}: Props) {
  const [seed, setSeed] = useState('step10-demo-seed');
  const [consonants, setConsonants] = useState(4);
  const [vowels, setVowels] = useState(2);
  const [tones, setTones] = useState(0);
  const [count, setCount] = useState(20);
  const [required, setRequired] = useState('p a');
  const [excluded, setExcluded] = useState('');
  const [scope, setScope] = useState('language');
  const [reference, setReference] = useState('northeuralex-eng');
  const [duplicates, setDuplicates] = useState('reject');
  const [components, setComponents] = useState('{"1":0.9,"2":0.1}');
  const [useLoaded, setUseLoaded] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [doculects, setDoculects] = useState<Row[] | null>(null);
  const poolBundle = useLoaded && bundle ? bundle : example;
  const pool = parseJson(poolBundle.specification_json);
  const ids = (source: string) => source.trim() ? source.trim().split(/\s+/) : [];

  async function references() {
    setError('');
    try {
      const response = await fetch('/api/phonology/status'); const value = await response.json();
      if (!response.ok) throw new Error(value.error ?? 'Unable to read evidence status.');
      setDoculects(value.doculects); setStatus('Available reference doculects loaded.');
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to read evidence status.'); }
  }
  async function generate(replay = false) {
    setGenerating(true); setError(''); setStatus('');
    try {
      let input: Row;
      if (replay) {
        if (!bundle?.generation.web_reproduction) throw new Error('This run has no saved website generation inputs.');
        input = {specification_json: bundle.specification_json, request: bundle.generation.web_reproduction.request, rules: bundle.rules, snapshot: bundle.generation.web_reproduction.snapshot};
      } else {
        if (!seed || [...seed].length > 128 || [...seed].some(c => c.codePointAt(0)! < 32)) throw new Error('Seed must contain 1–128 characters without control characters.');
        const spec = {...pool, seed};
        input = {
          specification_json: canonicalJson(spec, '', true),
          rules: useLoaded && bundle ? parseJson(rulesText) : example.rules,
          request: {...defaultRequest, name: 'Website sound-system generation', consonant_target: consonants, vowel_target: vowels, tone_target: tones, word_count: count,
            required_phoneme_ids: ids(required), excluded_phoneme_ids: ids(excluded), inventory_scope: scope, reference_doculect: reference.trim() || null, duplicate_policy: duplicates, component_count_weights: parseJson(components)},
        };
      }
      const response = await fetch('/api/phonology/generate', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(input)});
      const value = await response.json();
      if (!response.ok) throw new Error(value.error ?? 'Unable to generate this sound system.');
      if (replay && canonicalJson(value.generation) !== canonicalJson(bundle!.generation)) throw new Error('Saved generation did not reproduce. The existing run has been preserved.');
      await onGenerated(value, replay ? 'Reproduced website generation' : 'Website generation');
      setStatus(replay ? 'The same inputs and saved evidence reproduced the complete generation.' : 'New inventory and forms generated; rules applied and checked.');
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to generate this sound system.'); }
    finally { setGenerating(false); }
  }
  return <section className="panel generationControls">
    <h2>Generate a new sound system</h2>
    <p>Choose an inventory size and seed. Generate forms from the sound pool’s construction rules, then inspect the applied rules and evidence below.</p>
    <fieldset disabled={busy || generating}>
      <div className="generationGrid">
        <label>Sound pool<select value={useLoaded && bundle ? 'loaded' : 'demo'} onChange={e => setUseLoaded(e.target.value === 'loaded')}><option value="demo">Demonstration pool</option><option value="loaded" disabled={!bundle}>Loaded run’s pool and rules</option></select></label>
        <label>Seed<input value={seed} onChange={e => setSeed(e.target.value)} maxLength={128} /></label>
        <label>Consonants<input type="number" min="0" max="64" value={consonants} onChange={e => setConsonants(Number(e.target.value))} /></label>
        <label>Vowels<input type="number" min="1" max="64" value={vowels} onChange={e => setVowels(Number(e.target.value))} /></label>
        <label>Tones<input type="number" min="0" max="64" value={tones} onChange={e => setTones(Number(e.target.value))} /></label>
        <label>Sample forms<input type="number" min="1" max="200" value={count} onChange={e => setCount(Number(e.target.value))} /></label>
      </div>
      <p className="help">{pool.name} · Available: {pool.classes.consonants.length} consonants, {pool.classes.vowels.length} vowels, {pool.classes.tones.length} tones.<br />Pool IDs: {pool.phonemes.map((p: Row) => `${p.id} (${p.ipa})`).join(' · ')}</p>
      <details><summary>Inventory constraints and evidence</summary>
        <div className="generationGrid">
          <label>Required sound IDs<input value={required} onChange={e => setRequired(e.target.value)} placeholder="p a" /></label>
          <label>Excluded sound IDs<input value={excluded} onChange={e => setExcluded(e.target.value)} placeholder="Optional" /></label>
          <label>Evidence population<select value={scope} onChange={e => setScope(e.target.value)}><option value="language">Languages</option><option value="inventory">Inventories</option></select></label>
          <label>Reference doculect<input list="generationDoculects" value={reference} onChange={e => setReference(e.target.value)} placeholder="Leave blank for no lexical comparison" /><datalist id="generationDoculects">{doculects?.map(d => <option key={d.lexibank_id} value={d.lexibank_id}>{d.name}</option>)}</datalist></label>
          <label>Duplicate forms<select value={duplicates} onChange={e => setDuplicates(e.target.value)}><option value="reject">Reject with bounded retries</option><option value="allow">Allow</option></select></label>
          <label>Component count weights (JSON)<input value={components} onChange={e => setComponents(e.target.value)} /></label>
        </div>
        <button type="button" onClick={() => void references()}>Show available reference doculects</button>
        <p className="help">A new run uses the current website evidence snapshot. A saved website generation can be reproduced using its original snapshot. Reference frequency guides choices but does not forbid unusual valid sounds. If configured rules need specific tone or length phonemes, include their IDs in the required sounds.</p>
      </details>
      <div className="runActions"><button type="button" className="generateButton" onClick={() => void generate()}>Generate inventory and forms</button>{bundle?.generation.web_reproduction && <button type="button" onClick={() => void generate(true)}>Reproduce saved generation</button>}</div>
    </fieldset>
    {error && <p className="error" role="alert">{error}</p>}
    <p role="status" aria-live="polite">{generating ? 'Generating and checking forms…' : status}</p>
  </section>;
}

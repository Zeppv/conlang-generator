import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts' / 'analysis'))
from phonology_rules import PhonologyRuleSet, RuleError, apply_rules
from phonology_specification import SoundSystemSpecification
from phonology_workspace import realize_bundle, workspace_bundle
from test_phonology_rules import specification, generation, base_rules


def make_form(spec, components):
    """Components contain explicit (onset, nucleus, coda) syllables."""
    boundary = spec.to_dict()['construction']['boundaries']['component_token']
    pool = {p['id']: p['ipa'] for p in spec.to_dict()['phonemes']}
    templates = {p['shape']: p['id'] for p in spec.to_dict()['construction']['syllable_templates']}
    traced = []
    for ci, syllables in enumerate(components):
        rows = []
        for onset, nucleus, coda in syllables:
            shape = 'C' * len(onset) + 'V' + 'C' * len(coda)
            rows.append(dict(template_id=templates[shape], shape=shape, onset=onset,
                             nucleus=nucleus, coda=coda, phoneme_ids=onset + [nucleus] + coda))
        traced.append(dict(component_index=ci, syllables=rows,
                           phoneme_ids=[p for s in rows for p in s['phoneme_ids']]))
    ids = []
    for c in traced:
        if ids:
            ids.append(boundary)
        ids.extend(c['phoneme_ids'])
    return dict(word_index=0, component_count=len(traced), components=traced,
                phoneme_ids=ids, ipa_tokens=[pool.get(p, p) for p in ids])


def make_bundle(spec=None, rules=None, components=None):
    spec = spec or specification()
    rules = rules or base_rules()
    gen = generation(spec)
    if components is not None:
        gen['forms'] = [make_form(spec, components)]
    return workspace_bundle(spec, PhonologyRuleSet(spec, rules), gen)


def node_cases(cases):
    result = subprocess.run(['node', str(ROOT / 'tests' / 'phonology_rules_bridge.mjs')],
                            input=json.dumps(cases, ensure_ascii=False), capture_output=True,
                            text=True, encoding='utf-8', cwd=ROOT, timeout=60)
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


def harmony(name='vowel_harmony', direction='progressive', domain='component', blockers=None):
    if name == 'vowel_harmony':
        return dict(id='backness', domain=domain, direction=direction, feature='backness',
                    trigger_ids=['i', 'u'], target_ids=['a'], blocker_ids=blockers or [],
                    replacements={'a': {'front': 'i', 'back': 'u'}})
    return dict(id='place', domain=domain, direction=direction, feature='place',
                trigger_ids=['p'], target_ids=['t'], blocker_ids=blockers or [],
                replacements={'t': {'bilabial': 'p'}})


class WorkspaceTests(unittest.TestCase):
    def test_step11_generation_evidence_survives_python_browser_api_replay(self):
        from evaluator_fixture import fixture
        from test_phonology_generator import small_spec, request
        from phonology_generator import generate
        from phonology_evaluator import evaluate
        db = fixture()
        try:
            spec = small_spec()
            generated = generate(db, spec, request(), evaluate)
        finally:
            db.close()
        b = workspace_bundle(spec, PhonologyRuleSet(spec, base_rules()), generated)
        expected = realize_bundle(b)
        result = node_cases([{'bundle': b}, {'bundle': b, 'http': True}])
        self.assertEqual(result[0]['bundle'], expected)
        self.assertEqual(result[1]['body'], expected)
        self.assertEqual(expected['report']['evidence']['generation_evaluation'], generated['evidence']['evaluation'])

    def test_complete_reports_match_python_for_supported_rules(self):
        cases = [make_bundle()]
        for position in ('initial', 'final'):
            r = base_rules(); r['stress']['rule']['position'] = position
            cases.append(make_bundle(rules=r))
        for probability in (0, -0.0, 1, .35, .00001, .0000001, 5e-324):
            r = base_rules()
            r['length'] = dict(status='configured', strategy='lexical', probability=probability,
                               pairs=[dict(short_id='a', long_id='a_long')])
            cases.append(make_bundle(rules=r))
        for realization in ('separate_token', 'attach_to_nucleus'):
            r = base_rules()
            r['tone'] = dict(status='configured', system='lexical', realization=realization, tone_ids=['tone_h'])
            cases.append(make_bundle(rules=r))
        for name in ('vowel_harmony', 'consonant_harmony'):
            for direction in ('progressive', 'regressive'):
                for domain in ('component', 'word'):
                    for blocked in (False, True):
                        s = specification().to_dict()
                        s['construction']['boundaries']['cross_component_sequences'] = 'allowed'
                        spec = SoundSystemSpecification(s)
                        r = base_rules()
                        r[name] = dict(status='configured', rules=[harmony(name, direction, domain, ['t'] if blocked else [])])
                        components = [[(['p'], 'i', ['p']), (['t'], 'a', [])], [(['t'], 'a', ['t']), (['p'], 'u', [])]]
                        cases.append(make_bundle(spec, r, components))
        expected = [realize_bundle(b) for b in cases]
        actual = node_cases([{'bundle': b} for b in cases])
        for i, (e, a) in enumerate(zip(expected, actual)):
            with self.subTest(case=i):
                self.assertNotIn('error', a)
                self.assertEqual(a['bundle'], e)
        # Reimporting a complete exported run must verify its full saved report.
        self.assertEqual(node_cases([{'bundle': b} for b in expected]), [{'bundle': b} for b in expected])

    def test_boundary_is_never_any_phoneme(self):
        r = base_rules()
        r['allophony']['rules'][0].update(left='any', right='any')
        for domain in ('component', 'word'):
            r['allophony']['rules'][0]['domain'] = domain
            b = make_bundle(rules=r, components=[[([], 'a', [])], [(['t'], 'a', [])]])
            result = realize_bundle(b)
            self.assertNotIn('ɾ', result['report']['forms'][0]['surface_tokens'])
            self.assertEqual(node_cases([{'bundle': b}])[0]['bundle'], result)
        r['allophony']['rules'][0]['left'] = 'component_edge'
        b = make_bundle(rules=r, components=[[([], 'a', [])], [(['t'], 'a', [])]])
        result = realize_bundle(b)
        self.assertIn('ɾ', result['report']['forms'][0]['surface_tokens'])
        self.assertEqual(node_cases([{'bundle': b}])[0]['bundle'], result)

    def test_blocker_and_component_domains_have_observable_effects(self):
        r = base_rules()
        r['vowel_harmony'] = dict(status='configured', rules=[harmony(blockers=['p'])])
        b = make_bundle(rules=r, components=[[([], 'i', []), (['p'], 'a', [])]])
        self.assertEqual(realize_bundle(b)['report']['forms'][0]['phonological_phoneme_ids'], ['i', 'p', 'a'])
        r['vowel_harmony']['rules'][0]['blocker_ids'] = []
        b = make_bundle(rules=r, components=[[([], 'i', []), (['p'], 'a', [])]])
        self.assertEqual(realize_bundle(b)['report']['forms'][0]['phonological_phoneme_ids'], ['i', 'p', 'i'])
        b = make_bundle(rules=r, components=[[([], 'i', [])], [(['p'], 'a', [])]])
        self.assertEqual(realize_bundle(b)['report']['forms'][0]['phonological_phoneme_ids'], ['i', '+', 'p', 'a'])

    def test_harmony_cannot_create_disallowed_cluster(self):
        spec = specification().to_dict()
        spec['construction']['onsets'] = [[], ['t']]
        spec['construction']['syllable_templates'] = [t for t in spec['construction']['syllable_templates'] if t['id'] != 'ccv']
        spec = SoundSystemSpecification(spec)
        r = base_rules(); r['consonant_harmony'] = dict(status='configured', rules=[harmony('consonant_harmony')])
        b = make_bundle(spec, r, [[(['t'], 'a', ['p']), (['t'], 'a', [])]])
        with self.assertRaisesRegex(RuleError, 'cluster'):
            realize_bundle(b)
        self.assertIn('cluster', node_cases([{'bundle': b}])[0]['error'])

    def test_invalid_saved_inputs_fail_in_both_runtimes(self):
        cases = []
        def case(edit):
            b = make_bundle(); edit(b); cases.append(b)
        case(lambda b: b.update(rule_engine_version='future'))
        case(lambda b: b['generation'].update(specification_fingerprint='wrong'))
        case(lambda b: b['generation']['forms'][0].update(phoneme_ids=['a']))
        case(lambda b: b['generation']['forms'][0].update(ipa_tokens=['wrong']))
        case(lambda b: b['generation']['forms'][0].update(word_index=True))
        case(lambda b: b['generation']['forms'][0]['components'][0].update(syllables=[]))
        case(lambda b: b['generation']['forms'][0]['components'][0]['syllables'][0].update(nucleus='t', phoneme_ids=['t']))
        case(lambda b: b['rules']['allophony']['rules'][0].update(surface_ipa='+'))
        case(lambda b: b['rules']['allophony']['rules'][0].update(left=[]))
        case(lambda b: b['rules']['stress'].update(rule={'type': 'metrical'}))
        case(lambda b: b['rules'].update(unexpected=True))
        case(lambda b: b['generation']['inventory']['phonemes'].append(b['generation']['inventory']['phonemes'][0]))
        case(lambda b: b.update(report={}))
        case(lambda b: b.update(specification_json=' ' + b['specification_json']))
        for b in cases:
            with self.assertRaises((RuleError, ValueError)):
                realize_bundle(b)
        results = node_cases([{'bundle': b} for b in cases])
        self.assertTrue(all('error' in result for result in results), results)

    def test_rule_specification_contradiction_is_rejected(self):
        value = specification().to_dict()
        value['prosody']['stress'] = dict(setting='none', declaration='user', position=None)
        spec = SoundSystemSpecification(value)
        with self.assertRaisesRegex(RuleError, 'absence'):
            PhonologyRuleSet(spec, base_rules())
        b = make_bundle()
        b['specification_json'] = json.dumps(spec.to_dict(), ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        b['generation']['specification_fingerprint'] = spec.fingerprint
        self.assertIn('absence', node_cases([{'bundle': b}])[0]['error'])

    def test_http_route_is_bounded_and_independent_of_d1(self):
        b = make_bundle()
        cases = [dict(http=True, bundle=b), dict(http=True, method='GET'),
                 dict(http=True, contentType='text/plain', raw='{}'),
                 dict(http=True, raw='{"x":1,"x":2}'),
                 dict(http=True, raw='[' * 70 + '0' + ']' * 70),
                 dict(http=True, raw=' ' * (8 * 1024 * 1024 + 1))]
        results = node_cases(cases)
        self.assertEqual([r['status'] for r in results], [200, 405, 415, 400, 400, 413])
        self.assertEqual(results[0]['body'], realize_bundle(b))

    def test_cli_export_and_reproduction_without_database(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            b = make_bundle()
            spec = folder / 'spec.json'; spec.write_text(b['specification_json'], encoding='utf-8')
            rules = folder / 'rules.json'; rules.write_text(json.dumps(b['rules']), encoding='utf-8')
            gen = folder / 'generation.json'; gen.write_text(json.dumps(b['generation']), encoding='utf-8')
            output = folder / 'report.json'; bundle = folder / 'bundle.json'
            before = [p.read_bytes() for p in (spec, rules, gen)]
            cli = [sys.executable, str(ROOT / 'scripts' / 'analysis' / 'apply_phonology_rules.py')]
            args = ['--specification', str(spec), '--rules', str(rules), '--generation', str(gen), '--output', str(output), '--bundle-output', str(bundle)]
            result = subprocess.run(cli + args, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            original = output.read_bytes()
            result = subprocess.run(cli + ['--bundle', str(bundle), '--output', str(output)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(output.read_bytes(), original)
            self.assertEqual(before, [p.read_bytes() for p in (spec, rules, gen)])
            result = subprocess.run(cli + args + ['--bundle-output', str(gen)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(gen.read_bytes(), before[2])


if __name__ == '__main__':
    unittest.main()

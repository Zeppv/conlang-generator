import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts' / 'analysis'))
from evaluator_fixture import fixture
from phonology_evaluator import evaluate
from phonology_generator import generate, GenerationError
from phonology_specification import SoundSystemSpecification
from phonology_workspace import realize_bundle
from sync_phonology_web import records, encode, digest
from test_phonology_generator import small_spec, request
from test_phonology_rules import base_rules, specification


def make_input(spec, r, rules=None, snapshot=None):
    result = dict(specification_json=encode(spec.to_dict()), request=r, rules=rules or base_rules())
    if snapshot:
        result['snapshot'] = snapshot
    return result


def serving_snapshot(values):
    hashes = {key: digest(encode(value)) for key, value in values.items()}
    manifest = encode(dict(format_version=1, records=hashes))
    identity = digest(manifest)
    chunks = []
    for key, payload in [('manifest', manifest)] + [(k, encode(v)) for k, v in values.items()]:
        # Small chunks exercise ordering and complete readback.
        for position, start in enumerate(range(0, len(payload), 700)):
            chunk = payload[start:start+700]
            chunks.append(dict(key=key, position=position, payload=chunk, checksum=digest(chunk)))
    return identity, chunks


class GenerationWebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = fixture()
        cls.records = dict(records(cls.db, ['northeuralex-eng', 'other-eng', 'empty', 'no-nucleus']))
        cls.active, chunks = serving_snapshot(cls.records)
        cls.snapshots = {cls.active: chunks}

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def run_node(self, cases, snapshots=None):
        payload = dict(records=self.records, active=self.active, snapshots=snapshots or self.snapshots, cases=cases)
        result = subprocess.run(['node', str(ROOT / 'tests' / 'phonology_generation_bridge.mjs')],
                                input=json.dumps(payload, ensure_ascii=False), capture_output=True,
                                text=True, encoding='utf-8', cwd=ROOT, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_full_generator_report_parity_across_seeds_scopes_and_weights(self):
        cases, expected = [], []
        for seed in range(24):
            spec = small_spec('web-seed-' + str(seed))
            changes = dict(inventory_scope='inventory' if seed % 2 else 'language',
                           reference_doculect=[None, 'northeuralex-eng', 'other-eng'][seed % 3],
                           component_count_weights=[{'1': .75, '2': .25}, {'1': 1, '2': 2}, {'1': .1, '2': .2, '3': .7}][seed % 3])
            if seed % 4 == 0:
                changes.update(consonant_target=1, excluded_phoneme_ids=['t'])
            r = request(**changes)
            expected.append(generate(self.db, spec, r, evaluate))
            cases.append(dict(input=make_input(spec, r)))
        # Include the full demonstration pool with sounds missing from the fixture.
        spec = SoundSystemSpecification.from_json((ROOT / 'examples' / 'sound-system-specification.json').read_text())
        r = json.loads((ROOT / 'examples' / 'phonology-generation-request.json').read_text())
        expected.append(generate(self.db, spec, r, evaluate)); cases.append(dict(input=make_input(spec, r)))
        # Required unmapped tones and class mismatch remain explicit evidence gaps.
        value = specification().to_dict()
        spec = SoundSystemSpecification(value)
        r = request(consonant_target=3, vowel_target=2, tone_target=1,
                    required_phoneme_ids=['p', 'a', 'tone_h'], duplicate_policy='allow')
        expected.append(generate(self.db, spec, r, evaluate)); cases.append(dict(input=make_input(spec, r)))
        actual = self.run_node(cases)
        for i, (e, a) in enumerate(zip(expected, actual)):
            with self.subTest(case=i):
                self.assertNotIn('error', a)
                self.assertEqual(e, a['generation'])

    def test_snapshot_api_generation_and_python_realization_replay(self):
        spec = small_spec(); r = request(); payload = make_input(spec, r)
        result = self.run_node([dict(http=True, input=payload)])[0]
        self.assertEqual(result['status'], 200, result)
        b = result['body']
        expected = generate(self.db, spec, r, evaluate)
        expected['web_reproduction'] = dict(request=r, snapshot=self.active)
        self.assertEqual(b['generation'], expected)
        self.assertEqual(realize_bundle(b), b)
        # Replay against the saved snapshot even when another snapshot is active.
        changed = copy.deepcopy(self.records)
        changed['catalog']['doculects'] = []
        new_id, new_chunks = serving_snapshot(changed)
        result = self.run_node([dict(http=True, active=new_id, input=make_input(spec, r, snapshot=self.active))],
                               {**self.snapshots, new_id: new_chunks})[0]
        self.assertEqual(result['status'], 200, result)
        self.assertEqual(result['body'], b)
        self.assertTrue({'catalog', 'inventory', 'tokens', 'doc:northeuralex-eng'} <= set(result['reads']))

    def test_invalid_requests_missing_or_corrupt_snapshots_fail(self):
        spec = small_spec(); payload = make_input(spec, request())
        cases = [dict(http=True, input=payload, method='GET'),
                 dict(http=True, input=payload, contentType='text/plain'),
                 dict(http=True, raw='{"x":0,"x":1}'),
                 dict(http=True, input=payload, corrupt='inventory')]
        for edit in [dict(word_count=201), dict(consonant_target=3), dict(required_phoneme_ids=['not-known']),
                     dict(maximum_attempts_per_word=257), dict(reference_doculect='not-in-snapshot'),
                     dict(component_count_weights={'01': 1})]:
            p = copy.deepcopy(payload); p['request'].update(edit); cases.append(dict(http=True, input=p))
        p = copy.deepcopy(payload); p['snapshot'] = 'f' * 64; cases.append(dict(http=True, input=p))
        results = self.run_node(cases)
        self.assertEqual([r['status'] for r in results], [405, 415, 400, 503, 400, 400, 400, 400, 400, 400, 503])
        for result in results:
            self.assertNotIn('generation', result['body'])

    def test_duplicate_exhaustion_and_operation_budgets(self):
        value = small_spec().to_dict()
        value['phonemes'] = [p for p in value['phonemes'] if p['id'] == 'a']
        value['classes'] = dict(consonants=[], vowels=['a'], tones=[])
        value['construction'].update(onsets=[[]], codas=[[]], syllable_templates=[dict(id='v', shape='V', weight=1)], syllable_count_weights={'1': 1})
        spec = SoundSystemSpecification(value)
        r = request(consonant_target=0, required_phoneme_ids=['a'], word_count=2,
                    component_count_weights={'1': 1}, maximum_attempts_per_word=3)
        with self.assertRaises(GenerationError):
            generate(self.db, spec, r, evaluate)
        payload = make_input(spec, r)
        results = self.run_node([dict(input=payload), dict(input=make_input(small_spec(), request()), budget=dict(decisions=1, attempts=2000)),
                                 dict(input=make_input(small_spec(), request()), budget=dict(decisions=20000, attempts=0))])
        self.assertIn('maximum attempts', results[0]['error'])
        self.assertIn('decision budget', results[1]['error'])
        self.assertIn('attempt budget', results[2]['error'])


if __name__ == '__main__':
    unittest.main()

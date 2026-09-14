import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from evaluator_fixture import fixture, ROOT
from phonology_evaluator import evaluate, proposal_input


class EvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.db = fixture()

    def tearDown(self):
        self.db.close()

    def proposal(self, **changes):
        return {"inventory": ["p", "a", "t"], "words": [["p", "a"], ["t", "a", "p"]],
                "syllable_templates": ["CV", "CVC"], "reference_doculect": "northeuralex-eng", **changes}

    def test_component_values_and_no_invented_overall_score(self):
        report = evaluate(self.db, self.proposal())
        self.assertTrue(report["model_consistency"]["valid"])
        self.assertIsNone(report["overall_naturalism_score"])
        self.assertEqual(report["inventory"]["units"], 10)
        self.assertEqual(report["inventory"]["size_context"]["scope"], "inventory")
        self.assertEqual(report["inventory"]["size_context"]["measures"]["distinct_segment_count"]["midrank_percentile"], 100)
        self.assertEqual(report["phonotactics"]["observed_fraction_known_pairs"], 1.0)
        self.assertEqual(report["syllables"]["coverage"], 0.6)
        self.assertEqual(report["syllables"]["templates"][0]["forced_slots"], 1)
        self.assertEqual(report["prosody"]["status"], "unassessed")
        self.assertIsNone(report["prosody"]["score"])
        self.assertFalse(report["raw_source_revalidated"])

    def test_missing_stored_pair_not_zero_expected_absence_is_zero(self):
        language = evaluate(self.db, self.proposal())["inventory"]
        pair = next(p for p in language["pairs"] if set(p["tokens"]) == {"p", "t"})
        self.assertEqual(pair["status"], "not_stored")
        self.assertIsNone(pair["joint_units"])
        inventory = evaluate(self.db, self.proposal(inventory_scope="inventory"))["inventory"]
        pair = next(p for p in inventory["pairs"] if set(p["tokens"]) == {"p", "t"})
        self.assertEqual(pair["status"], "expected_absence")
        self.assertEqual(pair["joint_units"], 0)
        self.assertEqual(inventory["units"], 20)

    def test_unknown_tokens_keep_coverage_separate(self):
        report = evaluate(self.db, self.proposal(inventory=["p", "a", "t", "mystery"],
            words=[["p", "a"], ["p", "t"], ["p", "mystery"]]))
        self.assertEqual(report["inventory"]["mapping_coverage"], 0.75)
        self.assertEqual(report["inventory"]["size_context"]["status"], "unknown")
        self.assertEqual(report["phonotactics"]["mapping_coverage"], 0.66666667)
        self.assertEqual(report["phonotactics"]["observed_fraction_known_pairs"], 0.5)
        self.assertEqual(report["phonotactics"]["status"], "partial")

    def test_no_fake_success_for_empty_denominator(self):
        report = evaluate(self.db, self.proposal(words=[["a"]]))
        self.assertIsNone(report["phonotactics"]["observed_fraction_known_pairs"])
        report = evaluate(self.db, self.proposal(words=[["mystery", "mystery"]]))
        self.assertIsNone(report["phonotactics"]["observed_fraction_known_pairs"])

    def test_no_reference_no_implicit_pooling(self):
        report = evaluate(self.db, self.proposal(reference_doculect=None))
        self.assertEqual(report["phonotactics"]["status"], "reference_not_selected")
        report = evaluate(self.db, self.proposal(reference_doculect="other-eng"))
        self.assertEqual(report["phonotactics"]["observed_fraction_known_pairs"], 0.0)
        self.assertEqual(report["reference_doculect"]["glottocode"], "stan1293")

    def test_boundaries_and_word_membership(self):
        report = evaluate(self.db, self.proposal(words=[["p", "+", "a"], ["p"]]))
        self.assertTrue(report["model_consistency"]["valid"])
        self.assertEqual(report["phonotactics"]["requested_pair_positions"], 2)
        self.assertEqual(report["phonotactics"]["observed_fraction_known_pairs"], 1.0)
        invalid = evaluate(self.db, self.proposal(inventory=["p", "a", "+"], words=[["p", "t"], ["+", "p"], ["∼"]]))
        self.assertEqual({i["kind"] for i in invalid["model_consistency"]["issues"]},
                         {"structural_token_in_inventory", "undeclared_token", "empty_word_component", "special_marker_in_word"})

    def test_zero_syllable_coverage_unknown_not_absent(self):
        report = evaluate(self.db, self.proposal(reference_doculect="no-nucleus"))
        self.assertEqual(report["syllables"]["status"], "unknown")
        self.assertIsNone(report["syllables"]["templates"][0]["possible_slots"])
        report = evaluate(self.db, self.proposal(reference_doculect="empty"))
        self.assertEqual(report["phonotactics"]["status"], "missing_profile")

    def test_missing_marks_do_not_evaluate_system_absence(self):
        report = evaluate(self.db, self.proposal(prosody={"stress": "none", "tone": "absent", "length_contrast": "absent"}))
        self.assertEqual(report["prosody"]["status"], "unassessed")
        self.assertIsNone(report["prosody"]["score"])

    def test_invalid_input_and_reference_rejected(self):
        for value in ({"inventory": []}, {"inventory": ["p", "p"]},
                      {"inventory": ["p"], "words": ["pa"]},
                      {"inventory": ["p"], "syllable_templates": ["CVCV"]},
                      {"inventory": ["p"], "prosody": {"stress": "maybe"}},
                      {"inventory": ["p"], "unexpected": True}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                proposal_input(value)
        with self.assertRaisesRegex(ValueError, "exact Lexibank ID"):
            evaluate(self.db, self.proposal(reference_doculect="English"))

    def test_missing_or_unsupported_build_rejected(self):
        self.db.execute("UPDATE syllable_analysis SET method_version='99'")
        with self.assertRaisesRegex(RuntimeError, "unsupported"):
            evaluate(self.db, self.proposal())

    def test_obviously_mixed_snapshots_rejected(self):
        self.db.execute("UPDATE prosody_analysis SET form_count=form_count+1")
        with self.assertRaisesRegex(RuntimeError, "different source form counts"):
            evaluate(self.db, self.proposal())

    def test_cli_readonly_and_custom_input(self):
        with tempfile.TemporaryDirectory(prefix="evaluation cli ") as folder:
            root = Path(folder)
            database, proposal, output = root / "reference.sqlite", root / "proposal.json", root / "report.json"
            disk = sqlite3.connect(database)
            self.db.backup(disk)
            disk.close()
            before = hashlib.sha256(database.read_bytes()).hexdigest()
            proposal.write_text(json.dumps(self.proposal()), encoding="utf-8")
            result = subprocess.run([sys.executable, str(ROOT / "scripts/analysis/evaluate_phonology.py"),
                                     "--input", str(proposal), "--database", str(database), "--output", str(output)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("PHONOLOGY EVALUATION COMPLETE", result.stdout)
            self.assertEqual(json.loads(output.read_text())["inventory"]["mapping_coverage"], 1.0)
            self.assertEqual(hashlib.sha256(database.read_bytes()).hexdigest(), before)
            result = subprocess.run([sys.executable, str(ROOT / "scripts/analysis/evaluate_phonology.py"),
                                     "--input", str(proposal), "--database", str(database), "--output", str(proposal)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()

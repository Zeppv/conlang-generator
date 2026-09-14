import copy
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "analysis"))
sys.path.insert(0, str(ROOT / "tests"))

from evaluator_fixture import fixture  # noqa: E402
from phonology_evaluator import evaluate  # noqa: E402
from phonology_generator import GenerationError, generate  # noqa: E402
from phonology_specification import SoundSystemSpecification  # noqa: E402


EXAMPLE = ROOT / "examples" / "sound-system-specification.json"


def small_spec(seed="generator-test"):
    value = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    value["seed"] = seed
    keep = {"p", "t", "a"}
    value["phonemes"] = [item for item in value["phonemes"] if item["id"] in keep]
    value["classes"] = {"consonants": ["p", "t"], "vowels": ["a"], "tones": []}
    value["construction"]["onsets"] = [[], ["p"], ["t"]]
    value["construction"]["codas"] = [[], ["p"], ["t"]]
    value["construction"]["syllable_templates"] = [
        {"id": "cv", "shape": "CV", "weight": 0.5},
        {"id": "cvc", "shape": "CVC", "weight": 0.3},
        {"id": "v", "shape": "V", "weight": 0.2},
    ]
    value["construction"]["syllable_count_weights"] = {"1": 0.7, "2": 0.3}
    return SoundSystemSpecification(value)


def request(**changes):
    return {
        "name": "Fixture generation",
        "consonant_target": 2,
        "vowel_target": 1,
        "required_phoneme_ids": ["p", "a"],
        "excluded_phoneme_ids": [],
        "word_count": 8,
        "component_count_weights": {"1": 0.75, "2": 0.25},
        "duplicate_policy": "reject",
        "maximum_attempts_per_word": 64,
        "inventory_scope": "language",
        "reference_doculect": "northeuralex-eng",
        **changes,
    }


class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self.db = fixture()

    def tearDown(self):
        self.db.close()

    def test_generation_is_reproducible_and_exact_size(self):
        spec = small_spec()
        a = generate(self.db, spec, request(), evaluate)
        b = generate(self.db, spec, request(), evaluate)
        self.assertEqual(a, b)
        self.assertEqual(a["inventory"]["counts"], {
            "consonants": 2, "vowels": 1, "tones": 0})
        selected = {item["id"] for item in a["inventory"]["phonemes"]}
        self.assertTrue({"p", "a"} <= selected)
        self.assertTrue(a["hard_rule_validation"]["valid"])
        self.assertEqual(len(a["forms"]), 8)

    def test_required_and_excluded_sounds_are_preserved(self):
        result = generate(
            self.db, small_spec(),
            request(required_phoneme_ids=["p", "a"], excluded_phoneme_ids=["t"],
                    consonant_target=1),
            evaluate,
        )
        selected = {item["id"] for item in result["inventory"]["phonemes"]}
        self.assertEqual(selected, {"p", "a"})

    def test_every_form_passes_declared_construction_rules(self):
        result = generate(self.db, small_spec(), request(word_count=20), evaluate)
        self.assertTrue(result["hard_rule_validation"]["valid"])
        for word in result["forms"]:
            self.assertNotIn("∼", word["ipa_tokens"])
            for component in word["components"]:
                self.assertTrue(component["phoneme_ids"])
                for syllable in component["syllables"]:
                    self.assertRegex(syllable["shape"], r"^C*VC*$")

    def test_evaluator_is_attached_without_combined_score(self):
        result = generate(self.db, small_spec(), request(), evaluate)
        report = result["evidence"]["evaluation"]
        self.assertTrue(report["model_consistency"]["valid"])
        self.assertIsNone(report["overall_naturalism_score"])
        self.assertFalse(result["evidence"]["unusual_valid_designs_rejected"])

    def test_impossible_inventory_requests_fail_clearly(self):
        with self.assertRaisesRegex(GenerationError, "exceeds"):
            generate(self.db, small_spec(), request(consonant_target=3), evaluate)
        with self.assertRaisesRegex(GenerationError, "required and excluded"):
            generate(
                self.db, small_spec(),
                request(required_phoneme_ids=["p", "a"],
                        excluded_phoneme_ids=["p"]),
                evaluate,
            )

    def test_duplicate_exhaustion_is_bounded(self):
        value = small_spec().to_dict()
        value["phonemes"] = [item for item in value["phonemes"] if item["id"] == "a"]
        value["classes"] = {"consonants": [], "vowels": ["a"], "tones": []}
        value["construction"]["onsets"] = [[]]
        value["construction"]["codas"] = [[]]
        value["construction"]["syllable_templates"] = [
            {"id": "v", "shape": "V", "weight": 1}]
        value["construction"]["syllable_count_weights"] = {"1": 1}
        spec = SoundSystemSpecification(value)
        constrained = request(
            consonant_target=0, vowel_target=1,
            required_phoneme_ids=["a"], word_count=2,
            component_count_weights={"1": 1},
            maximum_attempts_per_word=3,
        )
        with self.assertRaisesRegex(GenerationError, "maximum attempts exhausted"):
            generate(self.db, spec, constrained, evaluate)

    def test_different_seed_changes_deterministic_run(self):
        a = generate(self.db, small_spec("one"), request(), evaluate)
        b = generate(self.db, small_spec("two"), request(), evaluate)
        self.assertNotEqual(
            [word["phoneme_ids"] for word in a["forms"]],
            [word["phoneme_ids"] for word in b["forms"]],
        )

    def test_cli_uses_read_only_database_and_writes_separate_report(self):
        with tempfile.TemporaryDirectory(prefix="phonology-generator-") as folder:
            root = Path(folder)
            database = root / "reference.sqlite"
            disk = sqlite3.connect(database)
            self.db.backup(disk)
            disk.close()
            spec_path = root / "spec.json"
            request_path = root / "request.json"
            output = root / "generation.json"
            spec_path.write_text(small_spec().to_json(), encoding="utf-8")
            request_path.write_text(
                json.dumps(request(reference_doculect=None)), encoding="utf-8")
            before = database.read_bytes()
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "analysis" / "generate_phonology.py"),
                    "--specification", str(spec_path),
                    "--request", str(request_path),
                    "--database", str(database),
                    "--output", str(output),
                ],
                cwd=ROOT, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("PHONOLOGY GENERATION COMPLETE", result.stdout)
            self.assertEqual(before, database.read_bytes())
            self.assertTrue(json.loads(output.read_text())["hard_rule_validation"]["valid"])


if __name__ == "__main__":
    unittest.main()

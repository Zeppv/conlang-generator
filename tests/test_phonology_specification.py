import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "analysis"))

from phonology_specification import (  # noqa: E402
    MODEL_VERSION,
    SPECIFICATION_VERSION,
    SoundSystemSpecification,
    SpecificationError,
)


EXAMPLE = ROOT / "examples" / "sound-system-specification.json"


class SpecificationTests(unittest.TestCase):
    def value(self):
        return json.loads(EXAMPLE.read_text(encoding="utf-8"))

    def test_example_round_trips_without_loss(self):
        first = SoundSystemSpecification(self.value())
        second = SoundSystemSpecification.from_json(first.to_json())
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.fingerprint, second.fingerprint)
        self.assertEqual(first.to_dict()["specification_version"], SPECIFICATION_VERSION)
        self.assertEqual(first.to_dict()["model_version"], MODEL_VERSION)
        self.assertAlmostEqual(
            sum(item["weight"] for item in first.to_dict()["construction"]["syllable_templates"]),
            1.0,
        )
        self.assertAlmostEqual(
            sum(first.to_dict()["construction"]["syllable_count_weights"].values()),
            1.0,
        )

    def test_weights_are_canonical_and_order_independent(self):
        left = self.value()
        left["construction"]["syllable_count_weights"] = {"3": 2, "1": 1, "2": 3}
        left["construction"]["syllable_templates"][0]["weight"] = 2
        left["construction"]["syllable_templates"][1]["weight"] = 10
        right = copy.deepcopy(left)
        right["construction"]["syllable_count_weights"] = {"2": 3, "3": 2, "1": 1}
        right["construction"]["syllable_templates"].reverse()
        a, b = SoundSystemSpecification(left), SoundSystemSpecification(right)
        self.assertEqual(a.to_dict(), b.to_dict())
        self.assertEqual(a.fingerprint, b.fingerprint)

    def test_seeded_decisions_are_reproducible(self):
        a = SoundSystemSpecification(self.value())
        b = SoundSystemSpecification.from_json(a.to_json())
        self.assertEqual(a.decision_preview(20), b.decision_preview(20))
        self.assertEqual(a.decision_unit("test", 7), b.decision_unit("test", 7))
        changed = self.value()
        changed["seed"] = "another-seed"
        c = SoundSystemSpecification(changed)
        self.assertNotEqual(a.decision_unit("test", 7), c.decision_unit("test", 7))

    def test_duplicate_and_unknown_json_keys_fail(self):
        with self.assertRaisesRegex(SpecificationError, "Duplicate JSON object key"):
            SoundSystemSpecification.from_json('{"name":"a","name":"b"}')
        value = self.value()
        value["invented"] = True
        with self.assertRaisesRegex(SpecificationError, "unknown fields"):
            SoundSystemSpecification(value)

    def test_inventory_class_and_mapping_contradictions_fail(self):
        cases = []
        duplicate = self.value()
        duplicate["phonemes"][1]["id"] = duplicate["phonemes"][0]["id"]
        cases.append(duplicate)
        mismatch = self.value()
        mismatch["classes"]["vowels"] = []
        cases.append(mismatch)
        mapped = self.value()
        mapped["phonemes"][0]["mapping"] = {
            "status": "mapped", "source": None, "source_id": None, "candidates": []
        }
        cases.append(mapped)
        ambiguous = self.value()
        ambiguous["phonemes"][0]["mapping"] = {
            "status": "ambiguous", "source": None, "source_id": None, "candidates": []
        }
        cases.append(ambiguous)
        for value in cases:
            with self.subTest(value=value), self.assertRaises(SpecificationError):
                SoundSystemSpecification(value)

    def test_construction_contradictions_fail(self):
        cases = []
        unknown = self.value()
        unknown["construction"]["onsets"].append(["missing"])
        cases.append(unknown)
        vowel_onset = self.value()
        vowel_onset["construction"]["onsets"].append(["a"])
        cases.append(vowel_onset)
        impossible_template = self.value()
        impossible_template["construction"]["syllable_templates"].append(
            {"id": "cccv", "shape": "CCCV", "weight": 1}
        )
        cases.append(impossible_template)
        boundary_phoneme = self.value()
        boundary_phoneme["construction"]["boundaries"]["component_token"] = "a"
        cases.append(boundary_phoneme)
        zero_weight = self.value()
        zero_weight["construction"]["syllable_count_weights"]["2"] = 0
        cases.append(zero_weight)
        for value in cases:
            with self.subTest(value=value), self.assertRaises(SpecificationError):
                SoundSystemSpecification(value)

    def test_prosody_and_deferred_rule_contradictions_fail(self):
        stress = self.value()
        stress["prosody"]["stress"] = {
            "setting": "fixed", "declaration": "unknown", "position": "initial"
        }
        with self.assertRaisesRegex(SpecificationError, "user-declared"):
            SoundSystemSpecification(stress)
        position = self.value()
        position["prosody"]["stress"]["position"] = "initial"
        with self.assertRaisesRegex(SpecificationError, "must be null"):
            SoundSystemSpecification(position)
        extension = self.value()
        extension["extensions"]["allophony"] = {
            "status": "deferred", "rules": [{"invented": "rule"}]
        }
        with self.assertRaisesRegex(SpecificationError, "deferred to Step 12"):
            SoundSystemSpecification(extension)

    def test_cli_validates_without_database_and_preserves_input(self):
        with tempfile.TemporaryDirectory(prefix="sound-system-spec-") as folder:
            output = Path(folder) / "canonical.json"
            before = EXAMPLE.read_bytes()
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "analysis" / "define_sound_system.py"),
                    "--input",
                    str(EXAMPLE),
                    "--output",
                    str(output),
                    "--preview-words",
                    "3",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("SOUND-SYSTEM SPECIFICATION VALID", result.stdout)
            self.assertEqual(before, EXAMPLE.read_bytes())
            self.assertEqual(
                SoundSystemSpecification.from_json(output.read_text(encoding="utf-8")).to_dict(),
                SoundSystemSpecification.from_json(EXAMPLE.read_text(encoding="utf-8")).to_dict(),
            )

    def test_cli_rejects_overwriting_input(self):
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "analysis" / "define_sound_system.py"),
                "--input",
                str(EXAMPLE),
                "--output",
                str(EXAMPLE),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("separate from the input", result.stderr)


if __name__ == "__main__":
    unittest.main()

import copy
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "analysis"))

from phonology_rules import PhonologyRuleSet, RuleError, apply_rules  # noqa: E402
from phonology_specification import SoundSystemSpecification  # noqa: E402


EXAMPLE = ROOT / "examples" / "sound-system-specification.json"
RULES = ROOT / "examples" / "phonology-rules.json"


def specification():
    value = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    additions = [
        {"id": "a_long", "ipa": "aː", "class": "vowel",
         "features": {"height": "open", "backness": "front", "length": "long"},
         "mapping": {"status": "user_defined", "source": None, "source_id": None, "candidates": []}},
        {"id": "tone_h", "ipa": "˥", "class": "tone",
         "features": {"register": "high"},
         "mapping": {"status": "user_defined", "source": None, "source_id": None, "candidates": []}},
    ]
    value["phonemes"].extend(additions)
    value["classes"]["vowels"].append("a_long")
    value["classes"]["tones"].append("tone_h")
    return SoundSystemSpecification(value)


def generation(spec):
    syllables = [
        {"template_id": "v", "shape": "V", "onset": [], "nucleus": "a",
         "coda": [], "phoneme_ids": ["a"]},
        {"template_id": "cvc", "shape": "CVC", "onset": ["t"], "nucleus": "a",
         "coda": ["p"], "phoneme_ids": ["t", "a", "p"]},
    ]
    return {
        "specification_fingerprint": spec.fingerprint,
        "request_fingerprint": "request-fixture",
        "inventory": {"phonemes": [
            {"id": item, "ipa": next(p["ipa"] for p in spec.to_dict()["phonemes"] if p["id"] == item)}
            for item in ("a", "a_long", "i", "u", "p", "t", "tone_h")
        ]},
        "forms": [{
            "word_index": 0, "component_count": 1,
            "components": [{"component_index": 0, "syllables": syllables,
                            "phoneme_ids": ["a", "t", "a", "p"]}],
            "phoneme_ids": ["a", "t", "a", "p"],
            "ipa_tokens": ["a", "t", "a", "p"],
        }],
        "hard_rule_validation": {"valid": True},
        "evidence": {"evaluation": {"overall_naturalism_score": None}},
    }


def base_rules():
    return json.loads(RULES.read_text(encoding="utf-8"))


class RuleTests(unittest.TestCase):
    def test_unknown_is_preserved_and_not_called_absent(self):
        spec = specification()
        rules = PhonologyRuleSet(spec, base_rules())
        self.assertEqual(rules.to_dict()["tone"]["status"], "unknown")
        result = apply_rules(spec, rules, generation(spec))
        self.assertEqual(result["support"]["tone"], "unknown")
        self.assertIn("automatic rule induction", result["support"]["deferred"])

    def test_fixed_stress_and_intervocalic_allophony_have_traces(self):
        spec = specification()
        result = apply_rules(
            spec, PhonologyRuleSet(spec, base_rules()), generation(spec))
        form = result["forms"][0]
        self.assertEqual(form["surface_tokens"][0], "ˈ")
        self.assertIn("ɾ", form["surface_tokens"])
        self.assertEqual(
            [event["stage"] for event in form["derivation"]],
            ["allophony", "stress"],
        )
        self.assertEqual(form["underlying_phoneme_ids"], ["a", "t", "a", "p"])

    def test_lexical_tone_is_separate_from_attached_realization(self):
        spec = specification()
        for realization in ("separate_token", "attach_to_nucleus"):
            value = base_rules()
            value["stress"] = {"status": "explicit_none", "rule": None}
            value["allophony"] = {"status": "explicit_none", "rules": []}
            value["tone"] = {
                "status": "configured", "system": "lexical",
                "realization": realization, "tone_ids": ["tone_h"],
            }
            result = apply_rules(
                spec, PhonologyRuleSet(spec, value), generation(spec))
            tokens = result["forms"][0]["surface_tokens"]
            if realization == "separate_token":
                self.assertIn("˥", tokens)
            else:
                self.assertTrue(any(token.endswith("˥") for token in tokens))
            self.assertEqual(
                sum(event["stage"] == "tone"
                    for event in result["forms"][0]["derivation"]),
                2,
            )

    def test_phonemic_length_uses_selected_pairs_and_is_reproducible(self):
        spec = specification()
        value = base_rules()
        value["stress"] = {"status": "explicit_none", "rule": None}
        value["allophony"] = {"status": "explicit_none", "rules": []}
        value["length"] = {
            "status": "configured", "strategy": "lexical",
            "probability": 1, "pairs": [{"short_id": "a", "long_id": "a_long"}],
        }
        rules = PhonologyRuleSet(spec, value)
        first = apply_rules(spec, rules, generation(spec))
        second = apply_rules(spec, rules, generation(spec))
        self.assertEqual(first, second)
        self.assertEqual(
            first["forms"][0]["phonological_phoneme_ids"],
            ["a_long", "t", "a_long", "p"],
        )

    def test_progressive_vowel_harmony_and_blocking(self):
        spec = specification()
        value = base_rules()
        value["stress"] = {"status": "explicit_none", "rule": None}
        value["allophony"] = {"status": "explicit_none", "rules": []}
        value["vowel_harmony"] = {
            "status": "configured",
            "rules": [{
                "id": "backness", "domain": "component",
                "direction": "progressive", "feature": "backness",
                "trigger_ids": ["i", "u"], "target_ids": ["a"],
                "blocker_ids": ["p"],
                "replacements": {"a": {"front": "i", "back": "u"}},
            }],
        }
        item = generation(spec)
        item["forms"][0]["components"][0]["syllables"][0]["nucleus"] = "i"
        item["forms"][0]["components"][0]["syllables"][0]["phoneme_ids"] = ["i"]
        item["forms"][0]["components"][0]["phoneme_ids"] = ["i", "t", "a", "p"]
        item["forms"][0]["phoneme_ids"] = ["i", "t", "a", "p"]
        item["forms"][0]["ipa_tokens"] = ["i", "t", "a", "p"]
        result = apply_rules(spec, PhonologyRuleSet(spec, value), item)
        self.assertEqual(
            result["forms"][0]["phonological_phoneme_ids"],
            ["i", "t", "i", "p"],
        )
        self.assertTrue(any(event["stage"] == "harmony"
                            for event in result["forms"][0]["derivation"]))

    def test_contradictory_or_unsupported_rules_fail(self):
        spec = specification()
        configured_empty = base_rules()
        configured_empty["vowel_harmony"] = {"status": "configured", "rules": []}
        with self.assertRaises(RuleError):
            PhonologyRuleSet(spec, configured_empty)
        bad_direction = base_rules()
        bad_direction["vowel_harmony"] = {
            "status": "configured",
            "rules": [{
                "id": "bad", "domain": "component", "direction": "bidirectional",
                "feature": "backness", "trigger_ids": ["i"],
                "target_ids": ["a"], "blocker_ids": [],
                "replacements": {"a": {"front": "i"}},
            }],
        }
        with self.assertRaisesRegex(RuleError, "progressive or regressive"):
            PhonologyRuleSet(spec, bad_direction)

    def test_fingerprint_mismatch_and_missing_required_tone_fail(self):
        spec = specification()
        item = generation(spec)
        item["specification_fingerprint"] = "wrong"
        with self.assertRaisesRegex(RuleError, "fingerprint"):
            apply_rules(spec, PhonologyRuleSet(spec, base_rules()), item)
        value = base_rules()
        value["tone"] = {
            "status": "configured", "system": "lexical",
            "realization": "separate_token", "tone_ids": ["tone_h"],
        }
        item = generation(spec)
        item["inventory"]["phonemes"] = [
            row for row in item["inventory"]["phonemes"] if row["id"] != "tone_h"]
        with self.assertRaisesRegex(RuleError, "unselected"):
            apply_rules(spec, PhonologyRuleSet(spec, value), item)


if __name__ == "__main__":
    unittest.main()

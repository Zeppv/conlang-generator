"""Bounded explicit phonological rule engine for the Step 12 support gate."""
from copy import deepcopy
import hashlib
import json
import math


RULES_VERSION = "1.0.0"
STATUSES = {"unknown", "explicit_none", "configured", "deferred"}


class RuleError(ValueError):
    """Raised for invalid rule declarations or inapplicable hard rules."""


def _fail(path, message):
    raise RuleError(f"{path}: {message}")


def _object(value, path, allowed, required=()):
    if not isinstance(value, dict):
        _fail(path, "must be an object")
    unknown = set(value) - set(allowed)
    missing = set(required) - set(value)
    if unknown:
        _fail(path, f"unknown fields {sorted(unknown)}")
    if missing:
        _fail(path, f"missing fields {sorted(missing)}")
    return value


def _status_section(value, path, fields):
    value = _object(value, path, {"status", *fields}, {"status", *fields})
    if value["status"] not in STATUSES:
        _fail(f"{path}.status", f"must be one of {sorted(STATUSES)}")
    return value


def _id_list(value, path, known, maximum=256):
    if not isinstance(value, list) or len(value) > maximum:
        _fail(path, f"must be a list with at most {maximum} IDs")
    if any(not isinstance(item, str) or item not in known for item in value):
        _fail(path, "must contain declared stable phoneme IDs")
    if len(set(value)) != len(value):
        _fail(path, "must not contain duplicates")
    return sorted(value)


def _empty_unless_configured(section, path, fields):
    if section["status"] != "configured":
        for field in fields:
            value = section[field]
            if value not in (None, [], {}):
                _fail(path, f"{field} must be empty unless status is configured")


def canonical_rules(value, specification):
    spec = specification.to_dict()
    phonemes = {item["id"]: item for item in spec["phonemes"]}
    value = _object(
        value, "rules",
        {"rules_version", "name", "stress", "tone", "length", "allophony",
         "vowel_harmony", "consonant_harmony", "notes"},
        {"rules_version", "name", "stress", "tone", "length", "allophony",
         "vowel_harmony", "consonant_harmony", "notes"},
    )
    if value["rules_version"] != RULES_VERSION:
        _fail("rules.rules_version", f"unsupported version; expected {RULES_VERSION}")
    if not isinstance(value["name"], str) or not 1 <= len(value["name"]) <= 200:
        _fail("rules.name", "must be a string of 1-200 characters")
    if not isinstance(value["notes"], list) or any(
            not isinstance(note, str) or not note for note in value["notes"]):
        _fail("rules.notes", "must be a list of nonempty strings")

    stress = _status_section(value["stress"], "rules.stress", {"rule"})
    _empty_unless_configured(stress, "rules.stress", {"rule"})
    normalized_stress = {"status": stress["status"], "rule": None}
    if stress["status"] == "configured":
        rule = _object(stress["rule"], "rules.stress.rule",
                       {"type", "position", "marker"},
                       {"type", "position", "marker"})
        if rule["type"] != "fixed" or rule["position"] not in {"initial", "final"}:
            _fail("rules.stress.rule", "v1 supports fixed initial or final stress only")
        if not isinstance(rule["marker"], str) or rule["marker"] not in {"ˈ", "ˌ"}:
            _fail("rules.stress.rule.marker", "must be the IPA primary or secondary stress marker")
        normalized_stress["rule"] = dict(rule)

    tone = _status_section(value["tone"], "rules.tone",
                           {"system", "realization", "tone_ids"})
    _empty_unless_configured(tone, "rules.tone",
                             {"system", "realization", "tone_ids"})
    normalized_tone = {
        "status": tone["status"], "system": None,
        "realization": None, "tone_ids": [],
    }
    if tone["status"] == "configured":
        if tone["system"] != "lexical":
            _fail("rules.tone.system", "v1 supports lexical tone only")
        if tone["realization"] not in {"separate_token", "attach_to_nucleus"}:
            _fail("rules.tone.realization", "must be separate_token or attach_to_nucleus")
        ids = _id_list(tone["tone_ids"], "rules.tone.tone_ids", phonemes)
        if not ids or any(phonemes[item]["class"] != "tone" for item in ids):
            _fail("rules.tone.tone_ids", "must contain at least one tone-class phoneme")
        normalized_tone.update({
            "system": tone["system"], "realization": tone["realization"],
            "tone_ids": ids,
        })

    length = _status_section(value["length"], "rules.length",
                             {"strategy", "probability", "pairs"})
    _empty_unless_configured(length, "rules.length",
                             {"strategy", "probability", "pairs"})
    normalized_length = {
        "status": length["status"], "strategy": None,
        "probability": None, "pairs": [],
    }
    if length["status"] == "configured":
        if length["strategy"] != "lexical":
            _fail("rules.length.strategy", "v1 supports lexical length choice only")
        probability = length["probability"]
        if isinstance(probability, bool) or not isinstance(probability, (int, float)) or not math.isfinite(probability) or not 0 <= probability <= 1:
            _fail("rules.length.probability", "must be a finite number from 0 to 1")
        if not isinstance(length["pairs"], list) or not length["pairs"]:
            _fail("rules.length.pairs", "configured lexical length requires pairs")
        pairs, shorts, longs = [], set(), set()
        for index, pair in enumerate(length["pairs"]):
            path = f"rules.length.pairs[{index}]"
            pair = _object(pair, path, {"short_id", "long_id"},
                           {"short_id", "long_id"})
            short_id, long_id = pair["short_id"], pair["long_id"]
            if short_id not in phonemes or long_id not in phonemes:
                _fail(path, "must reference declared phoneme IDs")
            if phonemes[short_id]["class"] != "vowel" or phonemes[long_id]["class"] != "vowel":
                _fail(path, "both members must be vowel-class phonemes")
            if short_id == long_id or short_id in shorts or long_id in longs:
                _fail(path, "pairs must be distinct and one-to-one")
            shorts.add(short_id)
            longs.add(long_id)
            pairs.append({"short_id": short_id, "long_id": long_id})
        normalized_length.update({
            "strategy": "lexical", "probability": float(probability),
            "pairs": sorted(pairs, key=lambda item: item["short_id"]),
        })

    allophony = _status_section(value["allophony"], "rules.allophony", {"rules"})
    _empty_unless_configured(allophony, "rules.allophony", {"rules"})
    normalized_allophony = {"status": allophony["status"], "rules": []}
    if allophony["status"] == "configured":
        if not isinstance(allophony["rules"], list) or not allophony["rules"]:
            _fail("rules.allophony.rules", "configured allophony requires rules")
        ids = set()
        for index, rule in enumerate(allophony["rules"]):
            path = f"rules.allophony.rules[{index}]"
            rule = _object(rule, path,
                           {"id", "underlying_id", "surface_ipa", "left", "right", "domain"},
                           {"id", "underlying_id", "surface_ipa", "left", "right", "domain"})
            if not isinstance(rule["id"], str) or not rule["id"] or rule["id"] in ids:
                _fail(f"{path}.id", "must be a unique nonempty ID")
            ids.add(rule["id"])
            if rule["underlying_id"] not in phonemes:
                _fail(f"{path}.underlying_id", "must reference a declared phoneme")
            if not isinstance(rule["surface_ipa"], str) or not rule["surface_ipa"] or any(
                    char.isspace() for char in rule["surface_ipa"]):
                _fail(f"{path}.surface_ipa", "must be one nonempty IPA token")
            if rule["domain"] not in {"component", "word"}:
                _fail(f"{path}.domain", "must be component or word")
            contexts = []
            for side in ("left", "right"):
                context = rule[side]
                allowed = {"any", "word_edge", "component_edge", "vowel", "consonant"}
                if context not in allowed:
                    if not isinstance(context, str) or not context.startswith("phoneme:") or context[8:] not in phonemes:
                        _fail(f"{path}.{side}", "unsupported context")
                contexts.append(context)
            normalized_allophony["rules"].append({
                "id": rule["id"], "underlying_id": rule["underlying_id"],
                "surface_ipa": rule["surface_ipa"], "left": contexts[0],
                "right": contexts[1], "domain": rule["domain"],
            })

    harmonies = {}
    for section_name, sound_class in (
            ("vowel_harmony", "vowel"), ("consonant_harmony", "consonant")):
        section = _status_section(value[section_name], f"rules.{section_name}",
                                  {"rules"})
        _empty_unless_configured(section, f"rules.{section_name}", {"rules"})
        normalized = {"status": section["status"], "rules": []}
        if section["status"] == "configured":
            if not isinstance(section["rules"], list) or not section["rules"]:
                _fail(f"rules.{section_name}.rules", "configured harmony requires rules")
            rule_ids = set()
            for index, rule in enumerate(section["rules"]):
                path = f"rules.{section_name}.rules[{index}]"
                rule = _object(
                    rule, path,
                    {"id", "domain", "direction", "feature", "trigger_ids",
                     "target_ids", "blocker_ids", "replacements"},
                    {"id", "domain", "direction", "feature", "trigger_ids",
                     "target_ids", "blocker_ids", "replacements"},
                )
                if not isinstance(rule["id"], str) or not rule["id"] or rule["id"] in rule_ids:
                    _fail(f"{path}.id", "must be a unique nonempty ID")
                rule_ids.add(rule["id"])
                if rule["domain"] not in {"component", "word"}:
                    _fail(f"{path}.domain", "must be component or word")
                if rule["domain"] == "word" and spec["construction"]["boundaries"]["cross_component_sequences"] != "allowed":
                    _fail(f"{path}.domain", "word-domain harmony requires allowed cross-component behavior")
                if rule["direction"] not in {"progressive", "regressive"}:
                    _fail(f"{path}.direction", "v1 supports progressive or regressive")
                if not isinstance(rule["feature"], str) or not rule["feature"]:
                    _fail(f"{path}.feature", "must be a nonempty feature name")
                triggers = _id_list(rule["trigger_ids"], f"{path}.trigger_ids", phonemes)
                targets = _id_list(rule["target_ids"], f"{path}.target_ids", phonemes)
                blockers = _id_list(rule["blocker_ids"], f"{path}.blocker_ids", phonemes)
                if not triggers or not targets:
                    _fail(path, "requires at least one trigger and target")
                if any(phonemes[item]["class"] != sound_class for item in triggers + targets):
                    _fail(path, f"triggers and targets must be {sound_class} phonemes")
                feature = rule["feature"]
                if any(feature not in phonemes[item]["features"] for item in triggers):
                    _fail(path, "every trigger must declare the harmony feature")
                replacements = rule["replacements"]
                if not isinstance(replacements, dict):
                    _fail(f"{path}.replacements", "must be an object")
                normalized_replacements = {}
                for target_id, choices in replacements.items():
                    if target_id not in targets or not isinstance(choices, dict) or not choices:
                        _fail(f"{path}.replacements", "keys must be target IDs with nonempty feature maps")
                    normalized_replacements[target_id] = {}
                    for feature_value, replacement_id in choices.items():
                        if replacement_id not in phonemes or phonemes[replacement_id]["class"] != sound_class:
                            _fail(f"{path}.replacements.{target_id}", "replacement must have the harmony sound class")
                        if phonemes[replacement_id]["features"].get(feature) != feature_value:
                            _fail(f"{path}.replacements.{target_id}.{feature_value}",
                                  "replacement does not carry the named feature value")
                        normalized_replacements[target_id][feature_value] = replacement_id
                normalized["rules"].append({
                    "id": rule["id"], "domain": rule["domain"],
                    "direction": rule["direction"], "feature": feature,
                    "trigger_ids": triggers, "target_ids": targets,
                    "blocker_ids": blockers,
                    "replacements": normalized_replacements,
                })
        harmonies[section_name] = normalized

    return {
        "rules_version": RULES_VERSION, "name": value["name"],
        "stress": normalized_stress, "tone": normalized_tone,
        "length": normalized_length, "allophony": normalized_allophony,
        **harmonies, "notes": list(value["notes"]),
    }


class PhonologyRuleSet:
    def __init__(self, specification, value):
        self._value = canonical_rules(deepcopy(value), specification)

    def to_dict(self):
        return deepcopy(self._value)

    def to_json(self):
        return json.dumps(self._value, ensure_ascii=False, indent=2) + "\n"

    @property
    def fingerprint(self):
        payload = json.dumps(self._value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


def _context_matches(context, side, index, ids, boundary, classes, domain):
    neighbor = index - 1 if side == "left" else index + 1
    absolute_edge = neighbor < 0 or neighbor >= len(ids)
    component_edge = absolute_edge or (not absolute_edge and ids[neighbor] == boundary)
    if context == "any":
        return not absolute_edge
    if context == "word_edge":
        return absolute_edge
    if context == "component_edge":
        return component_edge
    if component_edge and domain == "component":
        return False
    if absolute_edge or ids[neighbor] == boundary:
        return False
    if context == "vowel":
        return ids[neighbor] in classes["vowels"]
    if context == "consonant":
        return ids[neighbor] in classes["consonants"]
    return context.startswith("phoneme:") and ids[neighbor] == context[8:]


def _apply_harmony(ids, rule, phonemes, boundary, selected, events):
    indexes = list(range(len(ids)))
    if rule["direction"] == "regressive":
        indexes.reverse()
    current = None
    for index in indexes:
        phoneme_id = ids[index]
        if phoneme_id == boundary:
            if rule["domain"] == "component":
                current = None
            continue
        if phoneme_id in rule["blocker_ids"]:
            current = None
            continue
        if phoneme_id in rule["trigger_ids"]:
            current = phonemes[phoneme_id]["features"][rule["feature"]]
            continue
        if current is None or phoneme_id not in rule["target_ids"]:
            continue
        replacement = rule["replacements"].get(phoneme_id, {}).get(current)
        if replacement is None or replacement == phoneme_id:
            continue
        if replacement not in selected:
            _fail(rule["id"], f"harmony requires unselected replacement {replacement!r}")
        ids[index] = replacement
        events.append({
            "stage": "harmony", "rule_id": rule["id"], "position": index,
            "from_id": phoneme_id, "to_id": replacement,
            "feature": rule["feature"], "value": current,
        })


def _trace_positions(form, boundary):
    rebuilt, starts, nuclei = [], [], []
    for component_index, component in enumerate(form["components"]):
        if component_index:
            rebuilt.append(boundary)
        for syllable in component["syllables"]:
            starts.append(len(rebuilt))
            rebuilt.extend(syllable["onset"])
            nuclei.append(len(rebuilt))
            rebuilt.append(syllable["nucleus"])
            rebuilt.extend(syllable["coda"])
    if rebuilt != form["phoneme_ids"]:
        _fail(f"form[{form['word_index']}]", "generation trace does not match phoneme_ids")
    return starts, nuclei


def apply_rules(specification, rule_set, generation):
    spec = specification.to_dict()
    rules = rule_set.to_dict()
    if generation.get("specification_fingerprint") != specification.fingerprint:
        _fail("generation", "specification fingerprint does not match")
    if not generation.get("hard_rule_validation", {}).get("valid"):
        _fail("generation", "hard-rule validation must be valid before realization")
    phonemes = {item["id"]: item for item in spec["phonemes"]}
    selected = {item["id"] for item in generation["inventory"]["phonemes"]}
    boundary = spec["construction"]["boundaries"]["component_token"]
    required = set(rules["tone"]["tone_ids"])
    for pair in rules["length"]["pairs"]:
        if pair["short_id"] in selected:
            required.add(pair["long_id"])
    missing = required - selected
    if missing:
        _fail("rules", f"configured realization requires unselected phonemes {sorted(missing)}")

    realized = []
    for form in generation["forms"]:
        ids = list(form["phoneme_ids"])
        starts, nuclei = _trace_positions(form, boundary)
        events = []

        if rules["length"]["status"] == "configured":
            pairs = {item["short_id"]: item["long_id"]
                     for item in rules["length"]["pairs"]}
            for position in nuclei:
                short_id = ids[position]
                if short_id not in pairs:
                    continue
                unit = specification.decision_unit(
                    f"{generation['request_fingerprint']}:rules:{rule_set.fingerprint}:"
                    f"word:{form['word_index']}:length", position)
                if unit < rules["length"]["probability"]:
                    ids[position] = pairs[short_id]
                    events.append({
                        "stage": "length", "position": position,
                        "from_id": short_id, "to_id": ids[position],
                        "strategy": "lexical",
                    })

        for section_name in ("vowel_harmony", "consonant_harmony"):
            if rules[section_name]["status"] == "configured":
                for rule in rules[section_name]["rules"]:
                    _apply_harmony(ids, rule, phonemes, boundary, selected, events)

        surface = [
            item if item == boundary else phonemes[item]["ipa"]
            for item in ids
        ]
        applied = set()
        if rules["allophony"]["status"] == "configured":
            classes = {
                "vowels": set(spec["classes"]["vowels"]),
                "consonants": set(spec["classes"]["consonants"]),
            }
            for rule in rules["allophony"]["rules"]:
                for index, phoneme_id in enumerate(ids):
                    if index in applied or phoneme_id != rule["underlying_id"]:
                        continue
                    if _context_matches(rule["left"], "left", index, ids, boundary,
                                        classes, rule["domain"]) and _context_matches(
                            rule["right"], "right", index, ids, boundary,
                            classes, rule["domain"]):
                        before = surface[index]
                        surface[index] = rule["surface_ipa"]
                        applied.add(index)
                        events.append({
                            "stage": "allophony", "rule_id": rule["id"],
                            "position": index, "underlying_id": phoneme_id,
                            "from_ipa": before, "to_ipa": surface[index],
                        })

        tones = {}
        if rules["tone"]["status"] == "configured":
            options = rules["tone"]["tone_ids"]
            for syllable_index, position in enumerate(nuclei):
                unit = specification.decision_unit(
                    f"{generation['request_fingerprint']}:rules:{rule_set.fingerprint}:"
                    f"word:{form['word_index']}:tone", syllable_index)
                tone_id = options[min(int(unit * len(options)), len(options) - 1)]
                tones[position] = phonemes[tone_id]["ipa"]
                events.append({
                    "stage": "tone", "position": position, "tone_id": tone_id,
                    "realization": rules["tone"]["realization"],
                })

        stressed_start = None
        stress_marker = None
        if rules["stress"]["status"] == "configured" and starts:
            stress_rule = rules["stress"]["rule"]
            stressed_start = starts[0] if stress_rule["position"] == "initial" else starts[-1]
            stress_marker = stress_rule["marker"]
            events.append({
                "stage": "stress", "position": stressed_start,
                "rule": stress_rule["position"], "marker": stress_marker,
            })

        output = []
        for position, token in enumerate(surface):
            if position == stressed_start:
                output.append(stress_marker)
            if position in tones and rules["tone"]["realization"] == "attach_to_nucleus":
                output.append(token + tones[position])
            else:
                output.append(token)
                if position in tones:
                    output.append(tones[position])
        realized.append({
            "word_index": form["word_index"],
            "underlying_phoneme_ids": form["phoneme_ids"],
            "phonological_phoneme_ids": ids,
            "surface_tokens": output,
            "surface_form": "".join(token for token in output if token != boundary),
            "derivation": events,
        })

    support = {
        "stress": "fixed_initial_or_final" if rules["stress"]["status"] == "configured" else rules["stress"]["status"],
        "tone": "lexical_separate_or_attached" if rules["tone"]["status"] == "configured" else rules["tone"]["status"],
        "length": "lexical_phoneme_pairs" if rules["length"]["status"] == "configured" else rules["length"]["status"],
        "allophony": "bounded_context_rules" if rules["allophony"]["status"] == "configured" else rules["allophony"]["status"],
        "vowel_harmony": "feature_progressive_or_regressive" if rules["vowel_harmony"]["status"] == "configured" else rules["vowel_harmony"]["status"],
        "consonant_harmony": "feature_progressive_or_regressive" if rules["consonant_harmony"]["status"] == "configured" else rules["consonant_harmony"]["status"],
        "deferred": [
            "automatic stress-system induction", "metrical stress", "tone sandhi",
            "non-lexical tone assignment", "gradient/overlapping allophony",
            "bidirectional harmony", "opaque interactions", "automatic rule induction",
        ],
    }
    return {
        "rule_engine_version": RULES_VERSION,
        "specification_fingerprint": specification.fingerprint,
        "generation_request_fingerprint": generation["request_fingerprint"],
        "rule_set_fingerprint": rule_set.fingerprint,
        "seed": spec["seed"],
        "support": support,
        "forms": realized,
        "evidence": {
            "generation_evaluation": generation["evidence"]["evaluation"],
            "note": (
                "Rules are user declarations. Reference annotations remain descriptive "
                "evidence and did not select or validate these rule types."
            ),
        },
    }

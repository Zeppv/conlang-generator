"""Versioned executable sound-system specification for Phonology Engine v1.

This module validates construction rules only. Descriptive evidence is retained
as provenance and never silently converted into a hard rule.
"""
from copy import deepcopy
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
import hashlib
import json
import math
import re


SPECIFICATION_VERSION = "1.0.0"
MODEL_VERSION = "phonology-v1-step10"
IDENTIFIER = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
TEMPLATE = re.compile(r"^C*VC*$")
WEIGHT_PLACES = Decimal("0.000000000001")


class SpecificationError(ValueError):
    """Raised when a sound-system specification is invalid or contradictory."""


def _fail(path, message):
    raise SpecificationError(f"{path}: {message}")


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


def _text(value, path, maximum=200, nullable=False):
    if nullable and value is None:
        return None
    if not isinstance(value, str) or not 1 <= len(value) <= maximum:
        _fail(path, f"must be a string of 1-{maximum} characters")
    if any(ord(char) < 32 for char in value):
        _fail(path, "must not contain control characters")
    return value


def _token(value, path):
    value = _text(value, path, 128)
    if any(char.isspace() for char in value):
        _fail(path, "must be one token without whitespace")
    return value


def _identifier(value, path):
    if not isinstance(value, str) or IDENTIFIER.fullmatch(value) is None:
        _fail(path, "must match [a-z][a-z0-9_-]{0,63}")
    return value


def _string_list(value, path, maximum=256, tokens=False):
    if not isinstance(value, list) or len(value) > maximum:
        _fail(path, f"must be a list with at most {maximum} entries")
    result = []
    for index, item in enumerate(value):
        result.append(_token(item, f"{path}[{index}]") if tokens else _text(item, f"{path}[{index}]", 500))
    if len(set(result)) != len(result):
        _fail(path, "must not contain duplicates")
    return result


def _positive_decimal(value, path):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(path, "must be a finite positive number")
    if isinstance(value, float) and not math.isfinite(value):
        _fail(path, "must be a finite positive number")
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        _fail(path, "must be a finite positive number")
    if not number.is_finite() or number <= 0:
        _fail(path, "must be a finite positive number")
    return number


def _normalized_weights(entries, path):
    if not entries:
        _fail(path, "must contain at least one weighted choice")
    parsed = [(key, _positive_decimal(value, f"{path}.{key}")) for key, value in entries]
    total = sum((value for _, value in parsed), Decimal(0))
    result = []
    used = Decimal(0)
    for index, (key, value) in enumerate(parsed):
        if index == len(parsed) - 1:
            normalized = Decimal(1) - used
        else:
            normalized = (value / total).quantize(WEIGHT_PLACES, rounding=ROUND_HALF_EVEN)
            used += normalized
        if normalized <= 0:
            _fail(path, "normalization produced a zero-weight choice; remove negligible entries")
        result.append((key, float(normalized)))
    return result


def _mapping(value, path):
    value = _object(value, path, {"status", "source", "source_id", "candidates"}, {"status"})
    status = value["status"]
    if status not in {"mapped", "ambiguous", "unmapped", "user_defined"}:
        _fail(f"{path}.status", "must be mapped, ambiguous, unmapped, or user_defined")
    source = value.get("source")
    source_id = value.get("source_id")
    candidates = value.get("candidates", [])
    if not isinstance(candidates, list) or len(candidates) > 32:
        _fail(f"{path}.candidates", "must be a list with at most 32 entries")
    normalized_candidates = []
    seen = set()
    for index, candidate in enumerate(candidates):
        candidate_path = f"{path}.candidates[{index}]"
        candidate = _object(candidate, candidate_path, {"source", "source_id"}, {"source", "source_id"})
        pair = (_text(candidate["source"], f"{candidate_path}.source", 100),
                _text(candidate["source_id"], f"{candidate_path}.source_id", 200))
        if pair in seen:
            _fail(f"{path}.candidates", "must not contain duplicates")
        seen.add(pair)
        normalized_candidates.append({"source": pair[0], "source_id": pair[1]})
    normalized_candidates.sort(key=lambda item: (item["source"], item["source_id"]))

    if status == "mapped":
        source = _text(source, f"{path}.source", 100)
        source_id = _text(source_id, f"{path}.source_id", 200)
        if normalized_candidates:
            _fail(path, "mapped entries cannot also contain candidates")
    elif status == "ambiguous":
        if source is not None or source_id is not None:
            _fail(path, "ambiguous entries use candidates instead of one source")
        if not normalized_candidates:
            _fail(path, "ambiguous entries require at least one candidate")
    else:
        if source is not None or source_id is not None or normalized_candidates:
            _fail(path, f"{status} entries cannot claim a source mapping")
    return {"status": status, "source": source, "source_id": source_id,
            "candidates": normalized_candidates}


def _phonemes(value):
    if not isinstance(value, list) or not 1 <= len(value) <= 256:
        _fail("phonemes", "must contain 1-256 entries")
    result = []
    ids, displays = set(), set()
    for index, item in enumerate(value):
        path = f"phonemes[{index}]"
        item = _object(item, path, {"id", "ipa", "class", "features", "mapping"},
                       {"id", "ipa", "class", "features", "mapping"})
        phoneme_id = _identifier(item["id"], f"{path}.id")
        ipa = _token(item["ipa"], f"{path}.ipa")
        sound_class = item["class"]
        if sound_class not in {"consonant", "vowel", "tone"}:
            _fail(f"{path}.class", "must be consonant, vowel, or tone")
        if phoneme_id in ids:
            _fail(f"{path}.id", "duplicate stable phoneme ID")
        if ipa in displays:
            _fail(f"{path}.ipa", "duplicate IPA display token")
        ids.add(phoneme_id)
        displays.add(ipa)
        features = item["features"]
        if not isinstance(features, dict) or len(features) > 128:
            _fail(f"{path}.features", "must be an object with at most 128 entries")
        normalized_features = {}
        for key in sorted(features):
            _identifier(key, f"{path}.features key")
            normalized_features[key] = _text(features[key], f"{path}.features.{key}", 200)
        result.append({"id": phoneme_id, "ipa": ipa, "class": sound_class,
                       "features": normalized_features,
                       "mapping": _mapping(item["mapping"], f"{path}.mapping")})
    return sorted(result, key=lambda item: item["id"])


def _classes(value, phonemes):
    value = _object(value, "classes", {"consonants", "vowels", "tones"},
                    {"consonants", "vowels", "tones"})
    by_class = {
        "consonants": {item["id"] for item in phonemes if item["class"] == "consonant"},
        "vowels": {item["id"] for item in phonemes if item["class"] == "vowel"},
        "tones": {item["id"] for item in phonemes if item["class"] == "tone"},
    }
    result = {}
    for key in ("consonants", "vowels", "tones"):
        values = _string_list(value[key], f"classes.{key}", tokens=True)
        if set(values) != by_class[key]:
            missing = sorted(by_class[key] - set(values))
            extra = sorted(set(values) - by_class[key])
            _fail(f"classes.{key}", f"must exactly match phoneme classes; missing={missing}, extra={extra}")
        result[key] = sorted(values)
    if not result["vowels"]:
        _fail("classes.vowels", "at least one vowel is required by the v1 C*VC* model")
    return result


def _clusters(value, path, consonants):
    if not isinstance(value, list) or not 1 <= len(value) <= 256:
        _fail(path, "must contain 1-256 cluster choices")
    result, seen = [], set()
    for index, cluster in enumerate(value):
        if not isinstance(cluster, list) or len(cluster) > 8:
            _fail(f"{path}[{index}]", "must be a list of 0-8 consonant IDs")
        normalized = []
        for position, phoneme_id in enumerate(cluster):
            phoneme_id = _identifier(phoneme_id, f"{path}[{index}][{position}]")
            if phoneme_id not in consonants:
                _fail(f"{path}[{index}][{position}]", "must reference a declared consonant ID")
            normalized.append(phoneme_id)
        key = tuple(normalized)
        if key in seen:
            _fail(path, "must not contain duplicate clusters")
        seen.add(key)
        result.append(normalized)
    return sorted(result, key=lambda item: (len(item), item))


def _templates(value, onsets, codas):
    if not isinstance(value, list) or not 1 <= len(value) <= 64:
        _fail("construction.syllable_templates", "must contain 1-64 entries")
    parsed, ids, shapes = [], set(), set()
    for index, item in enumerate(value):
        path = f"construction.syllable_templates[{index}]"
        item = _object(item, path, {"id", "shape", "weight"}, {"id", "shape", "weight"})
        template_id = _identifier(item["id"], f"{path}.id")
        shape = item["shape"]
        if not isinstance(shape, str) or len(shape) > 64 or TEMPLATE.fullmatch(shape) is None:
            _fail(f"{path}.shape", "must be a single-nucleus C*VC* template")
        if template_id in ids or shape in shapes:
            _fail(path, "template IDs and shapes must both be unique")
        ids.add(template_id)
        shapes.add(shape)
        onset_length, coda_length = shape.index("V"), len(shape) - shape.index("V") - 1
        if not any(len(cluster) == onset_length for cluster in onsets):
            _fail(f"{path}.shape", f"no allowed onset has length {onset_length}")
        if not any(len(cluster) == coda_length for cluster in codas):
            _fail(f"{path}.shape", f"no allowed coda has length {coda_length}")
        parsed.append({"id": template_id, "shape": shape, "weight": item["weight"]})
    parsed.sort(key=lambda item: item["id"])
    weights = dict(_normalized_weights([(item["id"], item["weight"]) for item in parsed],
                                       "construction.syllable_templates"))
    return [{"id": item["id"], "shape": item["shape"], "weight": weights[item["id"]]}
            for item in parsed]


def _syllable_counts(value):
    if not isinstance(value, dict) or not 1 <= len(value) <= 16:
        _fail("construction.syllable_count_weights", "must contain 1-16 integer-string keys")
    entries = []
    for key, weight in value.items():
        if not isinstance(key, str) or not key.isdigit() or not 1 <= int(key) <= 16 or str(int(key)) != key:
            _fail("construction.syllable_count_weights", "keys must be canonical integers from 1 to 16")
        entries.append((key, weight))
    entries.sort(key=lambda item: int(item[0]))
    return dict(_normalized_weights(entries, "construction.syllable_count_weights"))


def _boundaries(value, phonemes):
    path = "construction.boundaries"
    value = _object(value, path,
                    {"component_token", "cross_component_sequences", "word_boundary_sequences",
                     "special_markers", "unknown_phoneme_policy"},
                    {"component_token", "cross_component_sequences", "word_boundary_sequences",
                     "special_markers", "unknown_phoneme_policy"})
    component = _token(value["component_token"], f"{path}.component_token")
    crossing = value["cross_component_sequences"]
    word_crossing = value["word_boundary_sequences"]
    unknown = value["unknown_phoneme_policy"]
    if crossing not in {"blocked", "allowed"}:
        _fail(f"{path}.cross_component_sequences", "must be blocked or allowed")
    if word_crossing not in {"blocked", "allowed"}:
        _fail(f"{path}.word_boundary_sequences", "must be blocked or allowed")
    if unknown not in {"reject", "preserve"}:
        _fail(f"{path}.unknown_phoneme_policy", "must be reject or preserve")
    special = _object(value["special_markers"], f"{path}.special_markers",
                      {"tokens", "policy"}, {"tokens", "policy"})
    markers = _string_list(special["tokens"], f"{path}.special_markers.tokens", 64, tokens=True)
    policy = special["policy"]
    if policy not in {"reject", "preserve"}:
        _fail(f"{path}.special_markers.policy", "must be reject or preserve")
    if component in markers:
        _fail(path, "component boundary token cannot also be a special marker")
    displays = {item["ipa"] for item in phonemes}
    stable_ids = {item["id"] for item in phonemes}
    structural = {component, *markers}
    if displays.intersection(structural) or stable_ids.intersection(structural):
        _fail(path, "boundary and special-marker tokens cannot also be phoneme IDs or IPA tokens")
    return {"component_token": component, "cross_component_sequences": crossing,
            "word_boundary_sequences": word_crossing,
            "special_markers": {"tokens": sorted(markers), "policy": policy},
            "unknown_phoneme_policy": unknown}


def _prosody(value, tone_ids):
    value = _object(value, "prosody", {"stress", "tone", "length_contrast"},
                    {"stress", "tone", "length_contrast"})
    result = {}
    stress = _object(value["stress"], "prosody.stress",
                     {"setting", "declaration", "position"},
                     {"setting", "declaration", "position"})
    if stress["setting"] not in {"unknown", "none", "fixed", "variable"}:
        _fail("prosody.stress.setting", "must be unknown, none, fixed, or variable")
    if stress["declaration"] not in {"unknown", "user"}:
        _fail("prosody.stress.declaration", "must be unknown or user")
    if stress["setting"] != "unknown" and stress["declaration"] != "user":
        _fail("prosody.stress", "a non-unknown setting must be explicitly user-declared")
    if stress["setting"] == "fixed":
        if stress["position"] not in {"initial", "final"}:
            _fail("prosody.stress.position", "fixed stress requires initial or final")
    elif stress["position"] is not None:
        _fail("prosody.stress.position", "must be null unless stress is fixed")
    result["stress"] = dict(stress)

    for key in ("tone", "length_contrast"):
        item = _object(value[key], f"prosody.{key}", {"setting", "declaration"},
                       {"setting", "declaration"})
        if item["setting"] not in {"unknown", "present", "absent"}:
            _fail(f"prosody.{key}.setting", "must be unknown, present, or absent")
        if item["declaration"] not in {"unknown", "user"}:
            _fail(f"prosody.{key}.declaration", "must be unknown or user")
        if item["setting"] != "unknown" and item["declaration"] != "user":
            _fail(f"prosody.{key}", "a non-unknown setting must be explicitly user-declared")
        result[key] = dict(item)
    if tone_ids and result["tone"]["setting"] == "absent":
        _fail("prosody.tone", "cannot be absent while tone-class phonemes are declared")
    return result


def _extensions(value):
    names = ("allophony", "vowel_harmony", "consonant_harmony")
    value = _object(value, "extensions", set(names), set(names))
    result = {}
    for name in names:
        path = f"extensions.{name}"
        item = _object(value[name], path, {"status", "rules"}, {"status", "rules"})
        if item["status"] not in {"unknown", "explicit_none", "deferred"}:
            _fail(f"{path}.status", "must be unknown, explicit_none, or deferred in specification v1")
        if not isinstance(item["rules"], list):
            _fail(f"{path}.rules", "must be a list")
        if item["rules"]:
            _fail(f"{path}.rules", "rule execution is deferred to Step 12; use an empty list")
        result[name] = {"status": item["status"], "rules": []}
    return result


def _evidence(value):
    value = _object(value, "evidence", {"status", "references", "notes"},
                    {"status", "references", "notes"})
    if value["status"] not in {"not_attached", "attached"}:
        _fail("evidence.status", "must be not_attached or attached")
    references = value["references"]
    if not isinstance(references, list) or len(references) > 64:
        _fail("evidence.references", "must be a list with at most 64 entries")
    normalized = []
    for index, item in enumerate(references):
        path = f"evidence.references[{index}]"
        item = _object(item, path, {"kind", "id", "version", "fingerprint"},
                       {"kind", "id", "version", "fingerprint"})
        normalized.append({
            "kind": _identifier(item["kind"], f"{path}.kind"),
            "id": _text(item["id"], f"{path}.id", 200),
            "version": _text(item["version"], f"{path}.version", 100),
            "fingerprint": _text(item["fingerprint"], f"{path}.fingerprint", 256, nullable=True),
        })
    normalized.sort(key=lambda item: (item["kind"], item["id"], item["version"],
                                      item["fingerprint"] or ""))
    if value["status"] == "attached" and not normalized:
        _fail("evidence.references", "attached evidence requires at least one reference")
    if value["status"] == "not_attached" and normalized:
        _fail("evidence", "references require attached status")
    notes = _string_list(value["notes"], "evidence.notes", 64)
    return {"status": value["status"], "references": normalized, "notes": notes}


def _provenance(value):
    value = _object(value, "provenance", {"defaults", "notes"},
                    {"defaults", "notes"})
    defaults = value["defaults"]
    if not isinstance(defaults, list) or len(defaults) > 128:
        _fail("provenance.defaults", "must be a list with at most 128 entries")
    normalized = []
    for index, item in enumerate(defaults):
        path = f"provenance.defaults[{index}]"
        item = _object(item, path, {"field", "kind", "source", "note"},
                       {"field", "kind", "source", "note"})
        kind = item["kind"]
        if kind not in {"user_declared", "engineering_default", "evidence_informed"}:
            _fail(f"{path}.kind", "must be user_declared, engineering_default, or evidence_informed")
        normalized.append({
            "field": _text(item["field"], f"{path}.field", 300),
            "kind": kind,
            "source": _text(item["source"], f"{path}.source", 300),
            "note": _text(item["note"], f"{path}.note", 1000),
        })
    normalized.sort(key=lambda item: (item["field"], item["kind"], item["source"], item["note"]))
    return {"defaults": normalized, "notes": _string_list(value["notes"], "provenance.notes", 64)}


def canonicalize(value):
    value = _object(value, "specification",
                    {"specification_version", "model_version", "name", "seed", "phonemes",
                     "classes", "construction", "prosody", "extensions", "evidence", "provenance"},
                    {"specification_version", "model_version", "name", "seed", "phonemes",
                     "classes", "construction", "prosody", "extensions", "evidence", "provenance"})
    if value["specification_version"] != SPECIFICATION_VERSION:
        _fail("specification_version", f"unsupported version; expected {SPECIFICATION_VERSION}")
    if value["model_version"] != MODEL_VERSION:
        _fail("model_version", f"unsupported model; expected {MODEL_VERSION}")
    name = _text(value["name"], "name")
    seed = _text(value["seed"], "seed", 128)
    phonemes = _phonemes(value["phonemes"])
    classes = _classes(value["classes"], phonemes)
    construction = _object(value["construction"], "construction",
                           {"onsets", "codas", "syllable_templates",
                            "syllable_count_weights", "boundaries"},
                           {"onsets", "codas", "syllable_templates",
                            "syllable_count_weights", "boundaries"})
    consonants = set(classes["consonants"])
    onsets = _clusters(construction["onsets"], "construction.onsets", consonants)
    codas = _clusters(construction["codas"], "construction.codas", consonants)
    templates = _templates(construction["syllable_templates"], onsets, codas)
    counts = _syllable_counts(construction["syllable_count_weights"])
    boundaries = _boundaries(construction["boundaries"], phonemes)
    return {
        "specification_version": SPECIFICATION_VERSION,
        "model_version": MODEL_VERSION,
        "name": name,
        "seed": seed,
        "phonemes": phonemes,
        "classes": classes,
        "construction": {
            "onsets": onsets,
            "codas": codas,
            "syllable_templates": templates,
            "syllable_count_weights": counts,
            "boundaries": boundaries,
        },
        "prosody": _prosody(value["prosody"], classes["tones"]),
        "extensions": _extensions(value["extensions"]),
        "evidence": _evidence(value["evidence"]),
        "provenance": _provenance(value["provenance"]),
    }


def _no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise SpecificationError(f"Duplicate JSON object key: {key!r}")
        result[key] = value
    return result


class SoundSystemSpecification:
    """Canonical, validated construction specification."""

    def __init__(self, value):
        self._value = canonicalize(deepcopy(value))

    @classmethod
    def from_json(cls, text):
        try:
            value = json.loads(
                text,
                object_pairs_hook=_no_duplicate_keys,
                parse_constant=lambda constant: _fail("JSON", f"invalid constant {constant}"),
            )
        except json.JSONDecodeError as error:
            raise SpecificationError(f"Invalid JSON: {error}") from error
        return cls(value)

    def to_dict(self):
        return deepcopy(self._value)

    def to_json(self):
        return json.dumps(self._value, ensure_ascii=False, indent=2) + "\n"

    @property
    def fingerprint(self):
        payload = json.dumps(self._value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def decision_unit(self, namespace, index):
        namespace = _text(namespace, "namespace", 300)
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            _fail("index", "must be a non-negative integer")
        payload = "\0".join((
            self._value["specification_version"],
            self._value["model_version"],
            self._value["seed"],
            namespace,
            str(index),
        )).encode("utf-8")
        number = int.from_bytes(hashlib.sha256(payload).digest()[:16], "big")
        return number / (1 << 128)

    def _choice(self, weighted, namespace, index):
        unit = Decimal(str(self.decision_unit(namespace, index)))
        cumulative = Decimal(0)
        for key, weight in weighted:
            cumulative += Decimal(str(weight))
            if unit < cumulative:
                return key
        return weighted[-1][0]

    def choose_syllable_count(self, word_index):
        weights = list(self._value["construction"]["syllable_count_weights"].items())
        return int(self._choice(weights, f"word:{word_index}:syllable-count", 0))

    def choose_template(self, word_index, syllable_index):
        weights = [(item["id"], item["weight"])
                   for item in self._value["construction"]["syllable_templates"]]
        return self._choice(weights, f"word:{word_index}:template", syllable_index)

    def decision_preview(self, word_count=5):
        if isinstance(word_count, bool) or not isinstance(word_count, int) or not 1 <= word_count <= 100:
            _fail("word_count", "must be an integer from 1 to 100")
        preview = []
        for word_index in range(word_count):
            count = self.choose_syllable_count(word_index)
            preview.append({
                "word_index": word_index,
                "syllable_count": count,
                "template_ids": [self.choose_template(word_index, syllable_index)
                                 for syllable_index in range(count)],
            })
        return preview

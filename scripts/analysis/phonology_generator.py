"""Seeded coherent inventory and word-form generation for Phonology Engine v1."""
from collections import defaultdict
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
import math


GENERATOR_VERSION = "1.0.0"
REQUEST_FIELDS = {
    "name", "consonant_target", "vowel_target", "tone_target",
    "required_phoneme_ids", "excluded_phoneme_ids", "word_count",
    "component_count_weights", "duplicate_policy", "maximum_attempts_per_word",
    "inventory_scope", "reference_doculect",
}


class GenerationError(ValueError):
    """A bounded generation request cannot be satisfied."""


def _fail(path, message):
    raise GenerationError(f"{path}: {message}")


def _positive_integer(value, path, minimum=0, maximum=1000):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        _fail(path, f"must be an integer from {minimum} to {maximum}")
    return value


def _identifier_list(value, path):
    if not isinstance(value, list) or len(value) > 256:
        _fail(path, "must be a list with at most 256 stable phoneme IDs")
    if any(not isinstance(item, str) or not item for item in value):
        _fail(path, "must contain nonempty string IDs")
    if len(set(value)) != len(value):
        _fail(path, "must not contain duplicates")
    return sorted(value)


def _weights(value, path, maximum_key=8):
    if not isinstance(value, dict) or not 1 <= len(value) <= maximum_key:
        _fail(path, f"must contain 1-{maximum_key} weighted integer choices")
    parsed = []
    for key, weight in value.items():
        if not isinstance(key, str) or not key.isdigit() or str(int(key)) != key:
            _fail(path, "keys must be canonical positive integer strings")
        number = int(key)
        if not 1 <= number <= maximum_key:
            _fail(path, f"keys must be from 1 to {maximum_key}")
        if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not math.isfinite(weight) or weight <= 0:
            _fail(f"{path}.{key}", "must be a finite positive number")
        parsed.append((key, Decimal(str(weight))))
    parsed.sort(key=lambda item: int(item[0]))
    total = sum((weight for _, weight in parsed), Decimal(0))
    return {key: float(weight / total) for key, weight in parsed}


def generation_request(value, specification):
    if not isinstance(value, dict):
        _fail("request", "must be a JSON object")
    unknown = set(value) - REQUEST_FIELDS
    if unknown:
        _fail("request", f"unknown fields {sorted(unknown)}")
    request = {
        "name": "Unnamed generation",
        "tone_target": 0,
        "required_phoneme_ids": [],
        "excluded_phoneme_ids": [],
        "word_count": 25,
        "component_count_weights": {"1": 1},
        "duplicate_policy": "reject",
        "maximum_attempts_per_word": 128,
        "inventory_scope": "language",
        "reference_doculect": None,
        **value,
    }
    if not isinstance(request["name"], str) or not 1 <= len(request["name"]) <= 200:
        _fail("request.name", "must be a string of 1-200 characters")
    for key in ("consonant_target", "vowel_target", "tone_target"):
        request[key] = _positive_integer(request.get(key), f"request.{key}", 0, 256)
    if request["vowel_target"] < 1:
        _fail("request.vowel_target", "must be at least 1 for the v1 C*VC* model")
    request["word_count"] = _positive_integer(request["word_count"], "request.word_count", 1, 1000)
    request["maximum_attempts_per_word"] = _positive_integer(
        request["maximum_attempts_per_word"], "request.maximum_attempts_per_word", 1, 10000)
    request["required_phoneme_ids"] = _identifier_list(
        request["required_phoneme_ids"], "request.required_phoneme_ids")
    request["excluded_phoneme_ids"] = _identifier_list(
        request["excluded_phoneme_ids"], "request.excluded_phoneme_ids")
    overlap = set(request["required_phoneme_ids"]) & set(request["excluded_phoneme_ids"])
    if overlap:
        _fail("request", f"required and excluded sounds overlap: {sorted(overlap)}")
    all_ids = {item["id"] for item in specification["phonemes"]}
    unknown_ids = (set(request["required_phoneme_ids"]) |
                   set(request["excluded_phoneme_ids"])) - all_ids
    if unknown_ids:
        _fail("request", f"unknown stable phoneme IDs: {sorted(unknown_ids)}")
    if request["duplicate_policy"] not in {"reject", "allow"}:
        _fail("request.duplicate_policy", "must be reject or allow")
    if request["inventory_scope"] not in {"language", "inventory"}:
        _fail("request.inventory_scope", "must be language or inventory")
    reference = request["reference_doculect"]
    if reference is not None and (not isinstance(reference, str) or not 1 <= len(reference) <= 200):
        _fail("request.reference_doculect", "must be an exact Lexibank ID or null")
    request["component_count_weights"] = _weights(
        request["component_count_weights"], "request.component_count_weights")
    return request


def _query(connection, sql, arguments=()):
    cursor = connection.execute(sql, arguments)
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor]


def load_evidence(connection, specification, scope):
    required = {
        "phonology_analysis", "phoible_segment", "phonology_segment_prevalence",
        "phonology_segment_cooccurrence",
    }
    tables = {row[0] for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    if required - tables:
        raise RuntimeError(f"Build the missing PHOIBLE evidence first: {sorted(required - tables)}")
    analyses = _query(
        connection,
        "SELECT id,method_version,inventory_unit_count,language_unit_count "
        "FROM phonology_analysis WHERE id='phoible_v2_0_step4'",
    )
    if len(analyses) != 1 or analyses[0]["method_version"] != "1.0.0":
        raise RuntimeError("Missing or unsupported PHOIBLE evidence build")
    ipas = sorted({item["ipa"] for item in specification["phonemes"]})
    placeholders = ",".join("?" for _ in ipas)
    segment_rows = _query(
        connection,
        f"SELECT id,phoneme,segment_class FROM phoible_segment "
        f"WHERE phoneme IN ({placeholders}) ORDER BY id",
        ipas,
    )
    by_ipa = defaultdict(list)
    for row in segment_rows:
        by_ipa[row["phoneme"]].append(row)
    exact_rows = {ipa: rows[0] for ipa, rows in by_ipa.items() if len(rows) == 1}
    segment_ids = sorted(row["id"] for row in exact_rows.values())
    prevalence = {}
    pairs = {}
    if segment_ids:
        marks = ",".join("?" for _ in segment_ids)
        prevalence = {
            row["segment_id"]: row
            for row in _query(
                connection,
                "SELECT segment_id,unit_count,total_unit_count,prevalence "
                "FROM phonology_segment_prevalence "
                f"WHERE analysis_id='phoible_v2_0_step4' AND scope=? "
                f"AND segment_id IN ({marks})",
                (scope, *segment_ids),
            )
        }
        pairs = {
            (row["segment_a_id"], row["segment_b_id"]): row
            for row in _query(
                connection,
                "SELECT segment_a_id,segment_b_id,joint_unit_count,evidence_type,"
                "lift,phi_coefficient FROM phonology_segment_cooccurrence "
                f"WHERE analysis_id='phoible_v2_0_step4' AND scope=? "
                f"AND segment_a_id IN ({marks}) AND segment_b_id IN ({marks})",
                (scope, *segment_ids, *segment_ids),
            )
        }
    units = analyses[0]["language_unit_count" if scope == "language" else "inventory_unit_count"]
    sounds = {}
    for phoneme in specification["phonemes"]:
        rows = by_ipa.get(phoneme["ipa"], [])
        if len(rows) != 1:
            sounds[phoneme["id"]] = {
                "status": "not_mapped" if not rows else "ambiguous_exact_rows",
                "segment_id": None, "prevalence": None, "units": units,
            }
            continue
        row = rows[0]
        evidence = prevalence.get(row["id"])
        class_status = "exact" if row["segment_class"] == phoneme["class"] else "class_mismatch"
        sounds[phoneme["id"]] = {
            "status": class_status,
            "segment_id": row["id"],
            "phoible_class": row["segment_class"],
            "prevalence": evidence["prevalence"] if evidence else None,
            "unit_count": evidence["unit_count"] if evidence else None,
            "units": units,
        }
    return {
        "analysis": analyses[0],
        "scope": scope,
        "sounds": sounds,
        "pairs": pairs,
        "note": (
            "PHOIBLE prevalence and stored inventory-pair evidence are proposal "
            "heuristics only. Missing or low evidence never overrides construction rules."
        ),
    }


def _pair_factor(candidate_id, selected_ids, evidence):
    candidate = evidence["sounds"][candidate_id]
    if candidate["segment_id"] is None:
        return 1.0, {"observed": 0, "expected_absence": 0, "not_stored": len(selected_ids)}
    factors = []
    counts = {"observed": 0, "expected_absence": 0, "not_stored": 0}
    for selected_id in selected_ids:
        selected = evidence["sounds"][selected_id]
        if selected["segment_id"] is None:
            counts["not_stored"] += 1
            factors.append(1.0)
            continue
        key = tuple(sorted((candidate["segment_id"], selected["segment_id"])))
        row = evidence["pairs"].get(key)
        if row is None:
            counts["not_stored"] += 1
            factors.append(1.0)
        elif row["evidence_type"] == "expected_absence":
            counts["expected_absence"] += 1
            factors.append(0.35)
        else:
            counts["observed"] += 1
            lift = row["lift"]
            factors.append(max(0.5, min(2.0, math.sqrt(lift))) if lift and lift > 0 else 0.5)
    return (sum(factors) / len(factors) if factors else 1.0), counts


def _selection_weight(candidate, selected, evidence):
    sound = evidence["sounds"][candidate["id"]]
    prevalence = sound["prevalence"]
    prevalence_factor = 0.2 + (prevalence if prevalence is not None else 0.0)
    pair_factor, pair_counts = _pair_factor(candidate["id"], [item["id"] for item in selected], evidence)
    peers = [item for item in selected if item["class"] == candidate["class"]]
    shared = 0
    for peer in peers:
        shared += sum(
            peer["features"].get(key) == value
            for key, value in candidate["features"].items()
            if key in peer["features"]
        )
    feature_factor = 1.0 + min(shared, 10) * 0.03
    weight = max(0.000001, prevalence_factor * pair_factor * feature_factor)
    return weight, {
        "mapping_status": sound["status"],
        "prevalence": prevalence,
        "prevalence_factor": round(prevalence_factor, 8),
        "pair_factor": round(pair_factor, 8),
        "pair_evidence": pair_counts,
        "feature_factor": round(feature_factor, 8),
        "final_weight": round(weight, 8),
    }


def _weighted_choice(specification, options, namespace, index):
    if not options:
        _fail(namespace, "has no available choices")
    ordered = sorted(options, key=lambda item: item[0])
    weights = [(key, Decimal(str(weight))) for key, weight in ordered]
    total = sum((weight for _, weight in weights), Decimal(0))
    target = Decimal(str(specification.decision_unit(namespace, index))) * total
    cumulative = Decimal(0)
    for key, weight in weights:
        cumulative += weight
        if target < cumulative:
            return key
    return weights[-1][0]


def select_inventory(specification, request, evidence, request_fingerprint):
    spec = specification.to_dict()
    by_id = {item["id"]: item for item in spec["phonemes"]}
    excluded = set(request["excluded_phoneme_ids"])
    required = [by_id[item] for item in request["required_phoneme_ids"]]
    targets = {
        "consonant": request["consonant_target"],
        "vowel": request["vowel_target"],
        "tone": request["tone_target"],
    }
    selected = list(required)
    records = [{
        "id": item["id"], "ipa": item["ipa"], "class": item["class"],
        "reason": "required", "heuristic": None,
    } for item in required]
    for sound_class, target in targets.items():
        required_count = sum(item["class"] == sound_class for item in required)
        available = [
            item for item in spec["phonemes"]
            if item["class"] == sound_class and item["id"] not in excluded
        ]
        if required_count > target:
            _fail(f"request.{sound_class}_target",
                  f"target {target} is below {required_count} required sounds")
        if len(available) < target:
            _fail(f"request.{sound_class}_target",
                  f"target {target} exceeds {len(available)} available sounds")
        while sum(item["class"] == sound_class for item in selected) < target:
            candidates = [
                item for item in available
                if item["id"] not in {chosen["id"] for chosen in selected}
            ]
            weighted = []
            details = {}
            for candidate in candidates:
                weight, detail = _selection_weight(candidate, selected, evidence)
                weighted.append((candidate["id"], weight))
                details[candidate["id"]] = detail
            step = sum(item["class"] == sound_class for item in selected)
            chosen_id = _weighted_choice(
                specification, weighted,
                f"{request_fingerprint}:inventory:{sound_class}", step)
            chosen = by_id[chosen_id]
            selected.append(chosen)
            records.append({
                "id": chosen["id"], "ipa": chosen["ipa"], "class": chosen["class"],
                "reason": "generated", "heuristic": details[chosen_id],
            })
    expected = sum(targets.values())
    if len(selected) != expected:
        raise RuntimeError("Internal inventory target mismatch")
    return selected, records


def _available_construction(spec, inventory_ids):
    onsets = [cluster for cluster in spec["construction"]["onsets"]
              if set(cluster) <= inventory_ids]
    codas = [cluster for cluster in spec["construction"]["codas"]
             if set(cluster) <= inventory_ids]
    templates = []
    for template in spec["construction"]["syllable_templates"]:
        position = template["shape"].index("V")
        onset_length = position
        coda_length = len(template["shape"]) - position - 1
        if any(len(cluster) == onset_length for cluster in onsets) and any(
                len(cluster) == coda_length for cluster in codas):
            templates.append(template)
    if not templates:
        _fail("construction", "generated inventory leaves no usable syllable template")
    return onsets, codas, templates


def _component(specification, request_fingerprint, word_index, component_index,
               attempt, onsets, codas, templates, vowels, evidence):
    prefix = f"{request_fingerprint}:word:{word_index}:attempt:{attempt}:component:{component_index}"
    count_options = list(specification.to_dict()["construction"]["syllable_count_weights"].items())
    syllable_count = int(_weighted_choice(specification, count_options, prefix + ":count", 0))
    syllables = []
    for syllable_index in range(syllable_count):
        template_id = _weighted_choice(
            specification,
            [(item["id"], item["weight"]) for item in templates],
            prefix + ":template",
            syllable_index,
        )
        template = next(item for item in templates if item["id"] == template_id)
        vpos = template["shape"].index("V")
        onset_choices = [cluster for cluster in onsets if len(cluster) == vpos]
        coda_choices = [cluster for cluster in codas
                        if len(cluster) == len(template["shape"]) - vpos - 1]
        onset_key = _weighted_choice(
            specification,
            [("\x1f".join(cluster), 1.0) for cluster in onset_choices],
            prefix + f":onset:{syllable_index}",
            0,
        )
        coda_key = _weighted_choice(
            specification,
            [("\x1f".join(cluster), 1.0) for cluster in coda_choices],
            prefix + f":coda:{syllable_index}",
            0,
        )
        onset = [] if onset_key == "" else onset_key.split("\x1f")
        coda = [] if coda_key == "" else coda_key.split("\x1f")
        vowel_id = _weighted_choice(
            specification,
            [(item["id"], 0.2 + (evidence["sounds"][item["id"]]["prevalence"] or 0.0))
             for item in vowels],
            prefix + ":vowel",
            syllable_index,
        )
        syllables.append({
            "template_id": template_id,
            "shape": template["shape"],
            "onset": onset,
            "nucleus": vowel_id,
            "coda": coda,
            "phoneme_ids": [*onset, vowel_id, *coda],
        })
    return {
        "component_index": component_index,
        "syllables": syllables,
        "phoneme_ids": [item for syllable in syllables for item in syllable["phoneme_ids"]],
    }


def generate_forms(specification, request, inventory, evidence, request_fingerprint):
    spec = specification.to_dict()
    inventory_ids = {item["id"] for item in inventory}
    by_id = {item["id"]: item for item in inventory}
    vowels = [item for item in inventory if item["class"] == "vowel"]
    onsets, codas, templates = _available_construction(spec, inventory_ids)
    boundary = spec["construction"]["boundaries"]["component_token"]
    special = set(spec["construction"]["boundaries"]["special_markers"]["tokens"])
    forms, seen = [], set()
    component_options = list(request["component_count_weights"].items())
    for word_index in range(request["word_count"]):
        for attempt in range(request["maximum_attempts_per_word"]):
            component_count = int(_weighted_choice(
                specification, component_options,
                f"{request_fingerprint}:word:{word_index}:attempt:{attempt}:components", 0))
            components = [
                _component(specification, request_fingerprint, word_index, index,
                           attempt, onsets, codas, templates, vowels, evidence)
                for index in range(component_count)
            ]
            ids = []
            for index, component in enumerate(components):
                if index:
                    ids.append(boundary)
                ids.extend(component["phoneme_ids"])
            ipa = [by_id[item]["ipa"] if item in by_id else item for item in ids]
            if special.intersection(ipa):
                raise RuntimeError("Generator promoted a special marker into a form")
            identity = tuple(ids)
            if request["duplicate_policy"] == "reject" and identity in seen:
                continue
            seen.add(identity)
            forms.append({
                "word_index": word_index,
                "attempt": attempt + 1,
                "component_count": component_count,
                "components": components,
                "phoneme_ids": ids,
                "ipa_tokens": ipa,
            })
            break
        else:
            _fail(
                f"word[{word_index}]",
                "maximum attempts exhausted while rejecting duplicates; "
                "reduce word_count, allow duplicates, or expand construction choices",
            )
    return forms, templates


def validate_generated(specification, request, inventory, forms):
    spec = specification.to_dict()
    inventory_ids = {item["id"] for item in inventory}
    vowels = set(spec["classes"]["vowels"])
    onsets = {tuple(item) for item in spec["construction"]["onsets"]}
    codas = {tuple(item) for item in spec["construction"]["codas"]}
    templates = {item["id"]: item["shape"]
                 for item in spec["construction"]["syllable_templates"]}
    boundary = spec["construction"]["boundaries"]["component_token"]
    special = set(spec["construction"]["boundaries"]["special_markers"]["tokens"])
    by_id = {item["id"]: item for item in inventory}
    issues = []
    identities = set()
    for word in forms:
        rebuilt = []
        if word["component_count"] != len(word["components"]):
            issues.append({"word": word["word_index"], "kind": "component_count_mismatch"})
        for component_index, component in enumerate(word["components"]):
            if component_index:
                rebuilt.append(boundary)
            component_ids = []
            for syllable in component["syllables"]:
                shape = templates.get(syllable["template_id"])
                if shape != syllable["shape"]:
                    issues.append({"word": word["word_index"], "kind": "template_mismatch"})
                traced_shape = "C" * len(syllable["onset"]) + "V" + "C" * len(syllable["coda"])
                if shape != traced_shape:
                    issues.append({"word": word["word_index"], "kind": "template_shape_mismatch"})
                if tuple(syllable["onset"]) not in onsets or tuple(syllable["coda"]) not in codas:
                    issues.append({"word": word["word_index"], "kind": "cluster_not_allowed"})
                if syllable["nucleus"] not in vowels:
                    issues.append({"word": word["word_index"], "kind": "nucleus_not_vowel"})
                expected = [*syllable["onset"], syllable["nucleus"], *syllable["coda"]]
                if expected != syllable["phoneme_ids"]:
                    issues.append({"word": word["word_index"], "kind": "syllable_trace_mismatch"})
                component_ids.extend(expected)
            if component_ids != component["phoneme_ids"]:
                issues.append({"word": word["word_index"], "kind": "component_trace_mismatch"})
            rebuilt.extend(component_ids)
        if rebuilt != word["phoneme_ids"]:
            issues.append({"word": word["word_index"], "kind": "word_trace_mismatch"})
        expected_ipa = [by_id[item]["ipa"] if item in by_id else item for item in rebuilt]
        if expected_ipa != word["ipa_tokens"]:
            issues.append({"word": word["word_index"], "kind": "ipa_trace_mismatch"})
        content = [item for item in rebuilt if item != boundary]
        if not set(content) <= inventory_ids:
            issues.append({"word": word["word_index"], "kind": "outside_inventory"})
        if special.intersection(word["ipa_tokens"]):
            issues.append({"word": word["word_index"], "kind": "special_marker_promoted"})
        identity = tuple(rebuilt)
        if request["duplicate_policy"] == "reject" and identity in identities:
            issues.append({"word": word["word_index"], "kind": "duplicate"})
        identities.add(identity)
    return {
        "valid": not issues,
        "issues": issues,
        "checked_forms": len(forms),
        "rules": (
            "Inventory membership, declared onset/coda clusters, template traces, "
            "vowel nuclei, component-boundary resets, special-marker exclusion, "
            "and the requested duplicate policy."
        ),
    }


def _request_fingerprint(request):
    payload = json.dumps(request, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def generate(connection, specification, request_value, evaluator):
    spec = specification.to_dict()
    request = generation_request(deepcopy(request_value), spec)
    request_fingerprint = _request_fingerprint(request)
    evidence = load_evidence(connection, spec, request["inventory_scope"])
    inventory, selection = select_inventory(
        specification, request, evidence, request_fingerprint)
    forms, active_templates = generate_forms(
        specification, request, inventory, evidence, request_fingerprint)
    validation = validate_generated(specification, request, inventory, forms)
    if not validation["valid"]:
        raise RuntimeError(f"Generated output failed hard rules: {validation['issues'][:10]}")
    prosody = {
        key: value["setting"] for key, value in spec["prosody"].items()
    }
    proposal = {
        "name": request["name"],
        "inventory": [item["ipa"] for item in inventory],
        "words": [item["ipa_tokens"] for item in forms],
        "syllable_templates": [item["shape"] for item in active_templates],
        "reference_doculect": request["reference_doculect"],
        "inventory_scope": request["inventory_scope"],
        "prosody": prosody,
    }
    evaluation = evaluator(connection, proposal)
    gaps = []
    unmapped = [item["id"] for item in selection
                if evidence["sounds"][item["id"]]["status"] != "exact"]
    if unmapped:
        gaps.append({
            "kind": "inventory_evidence_gap",
            "phoneme_ids": unmapped,
            "note": "These valid construction sounds lack one unambiguous exact PHOIBLE row or class match.",
        })
    if request["tone_target"]:
        gaps.append({
            "kind": "tone_realization_deferred",
            "note": "Tone-class sounds can enter the inventory, but Step 11 v1 does not place tone on forms; Step 12 owns that rule.",
        })
    for name, extension in spec["extensions"].items():
        if extension["status"] != "explicit_none":
            gaps.append({
                "kind": f"{name}_not_applied",
                "status": extension["status"],
                "note": "No absence is inferred; executable rules are deferred to Step 12.",
            })
    return {
        "generator_version": GENERATOR_VERSION,
        "specification_version": spec["specification_version"],
        "model_version": spec["model_version"],
        "specification_fingerprint": specification.fingerprint,
        "request_fingerprint": request_fingerprint,
        "seed": spec["seed"],
        "request": request,
        "inventory": {
            "phonemes": selection,
            "counts": {
                "consonants": sum(item["class"] == "consonant" for item in inventory),
                "vowels": sum(item["class"] == "vowel" for item in inventory),
                "tones": sum(item["class"] == "tone" for item in inventory),
            },
        },
        "forms": forms,
        "hard_rule_validation": validation,
        "evidence": {
            "selection_policy": evidence["note"],
            "scope": evidence["scope"],
            "analysis": evidence["analysis"],
            "evaluation": evaluation,
            "gaps": gaps,
            "unusual_valid_designs_rejected": False,
        },
    }

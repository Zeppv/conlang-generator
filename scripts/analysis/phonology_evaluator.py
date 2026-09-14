"""Read-only phonology evidence evaluation. Caller owns the read transaction."""
from collections import Counter
from itertools import combinations
import math
import re
import statistics

VERSION = "1.0.0"
PHOIBLE_ANALYSIS = "phoible_v2_0_step4"
LEXIBANK_ANALYSES = {
    "phonotactic_analysis": "lexibank_2_2_1_raw_sequences_v1",
    "syllable_analysis": "lexibank_2_2_1_cv_candidates_v1",
    "prosody_analysis": "lexibank_2_2_1_prosody_evidence_v1",
}


def query(conn, sql, args=()):
    cursor = conn.execute(sql, args)
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor]


def fraction(numerator, denominator):
    return round(numerator / denominator, 8) if denominator else None


def proposal_input(value):
    if not isinstance(value, dict):
        raise ValueError("Proposal must be a JSON object")
    unknown = set(value) - {"name", "inventory", "words", "syllable_templates", "reference_doculect", "inventory_scope", "prosody"}
    if unknown:
        raise ValueError(f"Unknown proposal fields: {sorted(unknown)}")
    proposal = {"name": "Unnamed proposal", "words": [], "syllable_templates": [],
                "reference_doculect": None, "inventory_scope": "language", "prosody": {}, **value}
    if not isinstance(proposal["name"], str) or not 1 <= len(proposal["name"]) <= 200:
        raise ValueError("name must be a string of 1-200 characters")
    if proposal["inventory_scope"] not in ("inventory", "language"):
        raise ValueError("inventory_scope must be inventory or language")

    def token(text):
        return isinstance(text, str) and 0 < len(text) <= 128 and not any(c.isspace() for c in text)

    inventory = proposal.get("inventory")
    if not isinstance(inventory, list) or not 1 <= len(inventory) <= 256 or not all(token(t) for t in inventory):
        raise ValueError("inventory must contain 1-256 individual token strings")
    if len(set(inventory)) != len(inventory):
        raise ValueError("Duplicate inventory tokens are not allowed")
    words = proposal["words"]
    if not isinstance(words, list) or len(words) > 1000 or any(
            not isinstance(w, list) or not 1 <= len(w) <= 128 or not all(token(t) for t in w) for w in words):
        raise ValueError("words must contain at most 1000 token lists, each of length 1-128")
    shapes = proposal["syllable_templates"]
    if not isinstance(shapes, list) or len(shapes) > 64 or any(
            not isinstance(s, str) or len(s) > 64 or re.fullmatch(r"C*VC*", s) is None for s in shapes):
        raise ValueError("syllable_templates must contain at most 64 single-nucleus C*VC* strings")
    if len(set(shapes)) != len(shapes):
        raise ValueError("Duplicate syllable templates are not allowed")
    reference = proposal["reference_doculect"]
    if reference is not None and (not isinstance(reference, str) or not 1 <= len(reference) <= 200):
        raise ValueError("reference_doculect must be an exact Lexibank ID or null")
    prosody = proposal["prosody"]
    if not isinstance(prosody, dict) or set(prosody) - {"stress", "tone", "length_contrast"}:
        raise ValueError("prosody accepts stress, tone and length_contrast only")
    for feature, state in prosody.items():
        choices = ("unknown", "none", "fixed", "variable") if feature == "stress" else ("unknown", "present", "absent")
        if state not in choices:
            raise ValueError(f"Unsupported {feature} value: {state!r}")
    return proposal


def metadata(conn, table, aid):
    # Table names and IDs are internal constants, never proposal SQL.
    rows = query(conn, f"SELECT * FROM {table} WHERE id=?", (aid,))
    if len(rows) != 1 or rows[0]["method_version"] != "1.0.0":
        raise RuntimeError(f"Missing or unsupported evidence build: {table}")
    return rows[0]


def inventory_evidence(conn, proposal, analysis):
    scope = proposal["inventory_scope"]
    segments = {row["phoneme"]: row for row in query(conn, "SELECT id,phoneme,segment_class FROM phoible_segment")}
    prevalence = {row["segment_id"]: row for row in query(conn,
        "SELECT segment_id,unit_count,total_unit_count,prevalence FROM phonology_segment_prevalence WHERE analysis_id=? AND scope=?",
        (PHOIBLE_ANALYSIS, scope))}
    expected_units = analysis["inventory_unit_count" if scope == "inventory" else "language_unit_count"]
    if expected_units <= 0:
        raise RuntimeError("PHOIBLE evidence has no units")
    resolved, details = [], []
    classes = Counter()
    for glyph in proposal["inventory"]:
        segment = segments.get(glyph)
        if segment is None:
            details.append({"token": glyph, "status": "unmapped", "prevalence": None})
            continue
        evidence = prevalence.get(segment["id"])
        if evidence is None or evidence["total_unit_count"] != expected_units:
            raise RuntimeError(f"Incomplete prevalence evidence for {glyph!r}")
        if not 0 <= evidence["unit_count"] <= expected_units or not math.isclose(evidence["prevalence"], evidence["unit_count"] / expected_units, abs_tol=1e-10):
            raise RuntimeError("Inconsistent prevalence count/ratio")
        resolved.append(segment)
        classes[segment["segment_class"]] += 1
        details.append({"token": glyph, "status": "exact_phoible_match", "segment_class": segment["segment_class"],
                        "unit_count": evidence["unit_count"], "total_units": expected_units, "prevalence": evidence["prevalence"]})
    profiles = query(conn, "SELECT distinct_segment_count,consonant_count,vowel_count,tone_count FROM phonology_inventory_profile WHERE analysis_id=?", (PHOIBLE_ANALYSIS,))
    if len(profiles) != analysis["inventory_unit_count"]:
        raise RuntimeError("Incomplete PHOIBLE inventory profiles")
    size = {"status": "unknown" if len(resolved) != len(details) else "available",
            "scope": "inventory", "note": "Percentiles describe inventory sizes, not quality; mapping must be complete.", "measures": {}}
    if len(resolved) == len(details):
        for column, value in (("distinct_segment_count", len(resolved)), ("consonant_count", classes["consonant"]),
                              ("vowel_count", classes["vowel"]), ("tone_count", classes["tone"])):
            population = [row[column] for row in profiles]
            rank = sum(x < value for x in population) + 0.5 * sum(x == value for x in population)
            size["measures"][column] = {"proposed": value, "midrank_percentile": round(100 * rank / len(population), 4),
                                       "reference_median": statistics.median(population), "reference_units": len(population)}
    ids = [segment["id"] for segment in resolved]
    pair_rows = {}
    if len(ids) > 1:
        placeholders = ",".join("?" for _ in ids)
        rows = query(conn, "SELECT segment_a_id,segment_b_id,joint_unit_count,expected_joint_count,evidence_type,lift,phi_coefficient "
                     f"FROM phonology_segment_cooccurrence WHERE analysis_id=? AND scope=? AND segment_a_id IN ({placeholders}) "
                     f"AND segment_b_id IN ({placeholders})", (PHOIBLE_ANALYSIS, scope, *ids, *ids))
        pair_rows = {(row["segment_a_id"], row["segment_b_id"]): row for row in rows}
    pairs = []
    for a, b in combinations(resolved, 2):
        row = pair_rows.get(tuple(sorted((a["id"], b["id"]))))
        pairs.append({"tokens": [a["phoneme"], b["phoneme"]], "status": "not_stored" if row is None else row["evidence_type"],
                      "joint_units": row["joint_unit_count"] if row else None,
                      "expected_joint_units": row["expected_joint_count"] if row else None,
                      "lift": row["lift"] if row else None, "phi": row["phi_coefficient"] if row else None})
    return {"scope": scope, "units": expected_units, "mapping": "Exact PHOIBLE strings only; no fuzzy or alias matching.",
            "mapping_coverage": fraction(len(resolved), len(details)), "mapped_tokens": len(resolved), "requested_tokens": len(details),
            "segments": details, "size_context": size, "pairs": pairs,
            "pair_coverage": {"requested_pairs": len(details) * (len(details) - 1) // 2, "mapped_pairs": len(pairs),
                              "stored_pairs": len(pair_rows)},
            "note": "Prevalence and associations are corpus descriptions. Rarity is not a defect. Missing stored pair rows are not zero counts."}


def lexical_evidence(conn, proposal, lid, tokens):
    profiles = query(conn, "SELECT * FROM phonotactic_profile WHERE language_id=?", (lid,))
    if not profiles:
        return {"status": "missing_profile", "observed_fraction_known_pairs": None}
    unigram = {row["token_id"]: row for row in query(conn, "SELECT * FROM phonotactic_token_stat WHERE language_id=?", (lid,))}
    bigrams = {(row["left_token_id"], row["right_token_id"]): row for row in query(conn, "SELECT * FROM phonotactic_bigram WHERE language_id=?", (lid,))}
    requested = Counter(pair for word in proposal["words"] for pair in zip(word, word[1:]))
    rows = []
    known = observed = 0
    for (left, right), count in sorted(requested.items()):
        a, b = tokens.get(left), tokens.get(right)
        if a is None or b is None or a["token_type"] == "special" or b["token_type"] == "special":
            rows.append({"tokens": [left, right], "candidate_occurrences": count, "status": "unknown", "source_occurrences": None})
            continue
        evidence = bigrams.get((a["id"], b["id"]))
        source_count = evidence["occurrence_count"] if evidence else 0
        known += count
        observed += count if source_count else 0
        rows.append({"tokens": [left, right], "candidate_occurrences": count, "status": "observed" if source_count else "not_observed",
                     "source_occurrences": source_count, "source_forms": evidence["form_count"] if evidence else 0})
    edges = []
    for edge, position, column in (("initial", 0, "initial_count"), ("final", -1, "final_count")):
        for glyph, count in sorted(Counter(word[position] for word in proposal["words"]).items()):
            token = tokens.get(glyph)
            source_count = None if token is None or token["token_type"] == "special" else unigram.get(token["id"], {}).get(column, 0)
            edges.append({"edge": edge, "token": glyph, "candidate_occurrences": count,
                          "status": "unknown" if source_count is None else "observed" if source_count else "not_observed",
                          "source_forms": source_count})
    total = sum(requested.values())
    return {"status": "not_requested" if not proposal["words"] else "partial" if known < total else "available",
            "source_forms": profiles[0]["form_count"], "requested_pair_positions": total, "known_pair_positions": known,
            "mapping_coverage": fraction(known, total), "observed_pair_positions": observed,
            "observed_fraction_known_pairs": fraction(observed, known), "pairs": rows, "word_edges": edges,
            "note": "This fraction measures observed adjacency in this doculect, not grammaticality. Unknown pairs are excluded with coverage shown. Raw boundaries are retained; forms are never joined."}


def syllable_evidence(conn, proposal, lid):
    profiles = query(conn, "SELECT * FROM syllable_profile WHERE language_id=?", (lid,))
    if not profiles:
        return {"status": "missing_profile", "templates": []}
    profile = profiles[0]
    candidates = {(row["onset_length"], row["coda_length"]): row for row in query(conn, "SELECT * FROM syllable_candidate WHERE language_id=?", (lid,))}
    rows = []
    for shape in proposal["syllable_templates"]:
        onset, coda = shape.split("V")
        evidence = candidates.get((len(onset), len(coda)), {})
        available = profile["projected_nuclei"] > 0
        possible = evidence.get("possible_slots", 0) if available else None
        forced = evidence.get("forced_slots", 0) if available else None
        rows.append({"template": shape, "status": "unknown" if not available else "forced_support" if forced else "possible_support" if possible else "not_observed",
                     "possible_slots": possible, "forced_slots": forced,
                     "possible_nucleus_fraction": fraction(possible, profile["projected_nuclei"]) if available else None})
    return {"status": "available" if profile["eligible_forms"] else "unknown", "source_forms": profile["form_count"],
            "eligible_forms": profile["eligible_forms"], "coverage": fraction(profile["eligible_forms"], profile["form_count"]),
            "projected_nuclei": profile["projected_nuclei"], "ambiguous_nuclei": profile["ambiguous_nuclei"], "templates": rows,
            "exclusions": query(conn, "SELECT reason,form_count FROM syllable_exclusion WHERE language_id=? ORDER BY reason", (lid,)),
            "note": "Shape support is conditional on the Step 6 projection. Alternatives overlap; fractions are not syllable-choice probabilities. Proposed words are not automatically syllabified."}


def evaluate(conn, value):
    proposal = proposal_input(value)
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    required = {"phonology_analysis", "phoible_segment", "phonology_inventory_profile", "phonology_segment_prevalence", "phonology_segment_cooccurrence", "lexibank_segment_token"}
    if proposal["reference_doculect"]:
        required |= set(LEXIBANK_ANALYSES) | {"lexibank_language", "phonotactic_profile", "phonotactic_token_stat", "phonotactic_bigram",
                                             "syllable_profile", "syllable_candidate", "syllable_exclusion", "prosody_profile", "prosody_annotation", "prosody_feature_stat"}
    if required - tables:
        raise RuntimeError(f"Build the missing evidence first: {sorted(required - tables)}")
    tokens = {row["token"]: row for row in query(conn, "SELECT id,token,token_type FROM lexibank_segment_token")}
    issues = []
    declared = set(proposal["inventory"])
    for token in proposal["inventory"]:
        if token in ("+", "∼") or tokens.get(token, {}).get("token_type") in ("boundary", "special"):
            issues.append({"kind": "structural_token_in_inventory", "token": token})
    for index, word in enumerate(proposal["words"]):
        for position, token in enumerate(word):
            kind = tokens.get(token, {}).get("token_type")
            if token == "∼" or kind == "special":
                issues.append({"kind": "special_marker_in_word", "word_index": index, "position": position, "token": token})
            elif token == "+":
                if position == 0 or position == len(word) - 1 or word[position - 1] == "+":
                    issues.append({"kind": "empty_word_component", "word_index": index, "position": position})
            elif token not in declared:
                issues.append({"kind": "undeclared_token", "word_index": index, "position": position, "token": token})
    phoible = metadata(conn, "phonology_analysis", PHOIBLE_ANALYSIS)
    report = {"evaluator_version": VERSION, "proposal": proposal, "overall_naturalism_score": None,
              "overall_note": "Components use different populations and assumptions; no calibrated universal aggregate is available.",
              "model_consistency": {"valid": not issues, "issues": issues,
                  "scope": "Inventory membership and structural-marker syntax only; not a grammaticality judgment."},
              "inventory": inventory_evidence(conn, proposal, phoible),
              "evidence_builds": {"phonology_analysis": phoible}, "raw_source_revalidated": False,
              "reference_doculect": None, "phonotactics": {"status": "reference_not_selected"},
              "syllables": {"status": "reference_not_selected"}, "prosody": {"status": "unassessed", "proposal": proposal["prosody"], "score": None}}
    if proposal["reference_doculect"]:
        languages = query(conn, "SELECT id,lexibank_id,name,glottocode FROM lexibank_language WHERE lexibank_id=?", (proposal["reference_doculect"],))
        if len(languages) != 1:
            raise ValueError("reference_doculect must be an existing exact Lexibank ID; no fuzzy selection is performed")
        language = languages[0]
        lid = language["id"]
        for table, aid in LEXIBANK_ANALYSES.items():
            report["evidence_builds"][table] = metadata(conn, table, aid)
        if len({report["evidence_builds"][table]["form_count"] for table in LEXIBANK_ANALYSES}) != 1:
            raise RuntimeError("Lexibank analysis snapshots have different source form counts; rebuild stale steps")
        report["reference_doculect"] = language
        report["phonotactics"] = lexical_evidence(conn, proposal, lid, tokens)
        report["syllables"] = syllable_evidence(conn, proposal, lid)
        profiles = query(conn, "SELECT * FROM prosody_profile WHERE language_id=?", (lid,))
        local_counts = [part["source_forms"] for part in (report["phonotactics"], report["syllables"]) if "source_forms" in part]
        if profiles:
            local_counts.append(profiles[0]["form_count"])
        if len(set(local_counts)) > 1:
            raise RuntimeError("Doculect profiles refer to different source form counts")
        report["prosody"].update({"reference_status": "available" if profiles else "missing_profile",
            "annotations": query(conn, "SELECT source_field,marker,available_forms,marked_forms,marker_occurrences,status,example_form_id "
                                 "FROM prosody_annotation WHERE language_id=? ORDER BY source_field,marker", (lid,)),
            "token_features": query(conn, "SELECT feature,token_occurrences,form_count,distinct_tokens,status,example_form_id "
                                    "FROM prosody_feature_stat WHERE language_id=? ORDER BY feature", (lid,)),
            "note": "Reference annotations do not establish stress rules, tone-system type, or length contrast. Missing markers do not mean absence; proposed system properties remain unassessed."})
    return report

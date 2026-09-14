"""Independent row-level validation of Step 7 annotation/feature evidence."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sqlite3

ROOT = Path(__file__).resolve().parents[2]
TABLES = ("prosody_analysis", "prosody_profile", "prosody_annotation", "prosody_token_feature", "prosody_feature_stat")
FEATURES = ("standalone_tone", "attached_tone", "primary_stress", "secondary_stress", "long", "mid_long", "ultra_short")


def equal(actual, expected, label):
    if actual != expected:
        raise RuntimeError(f"Step 7 validation failed: {label}")


def validate(conn, progress=print):
    analyses = conn.execute("SELECT id,source_id,method_version,source_digest,form_count FROM prosody_analysis").fetchall()
    if len(analyses) != 1:
        raise RuntimeError("Expected one prosody analysis")
    aid, source, version, saved_digest, declared = analyses[0]
    equal((aid, source, version), ("lexibank_2_2_1_prosody_evidence_v1", "lexibank", "1.0.0"), "analysis identity")
    equal(conn.execute("SELECT name,version FROM reference_source WHERE id='lexibank'").fetchone(), ("Lexibank Analysed", "2.2.1"), "source version")
    vocab_rows = conn.execute("SELECT t.id,t.token,t.token_type,p.description FROM lexibank_segment_token t "
                              "LEFT JOIN lexibank_phoneme p ON p.id=t.phoneme_id ORDER BY t.id").fetchall()
    digest = hashlib.sha256(json.dumps(vocab_rows, ensure_ascii=False).encode())
    vocabulary = {row[1] for row in vocab_rows}
    allowed = {feature: set() for feature in FEATURES}
    mapping = []
    descriptors = {"attached_tone": "tone", "primary_stress": "primary-stress", "secondary_stress": "secondary-stress",
                   "long": "long", "mid_long": "mid-long", "ultra_short": "ultra-short"}
    for tid, text, kind, description in vocab_rows:
        if kind not in {"phoneme", "tone", "special", "boundary"}:
            raise RuntimeError("Unknown source token type")
        if kind == "phoneme" and not description:
            raise RuntimeError("Missing source phoneme description")
        for feature in FEATURES:
            matched = kind == "tone" if feature == "standalone_tone" else (
                kind == "phoneme" and re.search(r"(?<!\S)" + re.escape(descriptors[feature]) + r"(?!\S)", description) is not None)
            if matched:
                allowed[feature].add(text)
                mapping.append((tid, feature))
    equal(conn.execute("SELECT token_id,feature FROM prosody_token_feature ORDER BY token_id,feature").fetchall(), sorted(mapping), "token feature map")
    totals, field_totals, feature_totals = Counter(), Counter(), Counter()
    languages = conn.execute("SELECT id FROM lexibank_language ORDER BY id").fetchall()
    for number, (lid,) in enumerate(languages, 1):
        available, marked, occurrences = Counter(), Counter(), Counter()
        examples = {}
        counts, presence = Counter(), Counter()
        distinct = {feature: set() for feature in FEATURES}
        feature_examples = {}
        forms = ntokens = 0
        for row in conn.execute("SELECT id,form,value,segments FROM lexibank_form WHERE language_id=? ORDER BY id", (lid,)):
            fid = row[0]
            digest.update((json.dumps([lid, *row], ensure_ascii=False) + "\n").encode())
            tokens = row[3].split()
            if not tokens or set(tokens) - vocabulary:
                raise RuntimeError(f"Invalid token sequence in form {fid}")
            forms += 1
            ntokens += len(tokens)
            for field, text in zip(("form", "value", "segments"), row[1:]):
                text = text or ""
                available[field] += any(not char.isspace() for char in text)
                for marker, char in (("primary_stress", "\u02c8"), ("secondary_stress", "\u02cc")):
                    positions = [n for n in range(len(text)) if text[n] == char]
                    if positions:
                        key = field, marker
                        marked[key] += 1
                        occurrences[key] += len(positions)
                        examples.setdefault(key, fid)
            for feature in FEATURES:
                matches = [token for token in tokens if token in allowed[feature]]
                if matches:
                    counts[feature] += len(matches)
                    presence[feature] += 1
                    distinct[feature].update(matches)
                    feature_examples.setdefault(feature, fid)
        equal(conn.execute("SELECT * FROM prosody_profile WHERE language_id=?", (lid,)).fetchall(),
              [(lid, aid, forms, ntokens, "unassessed")] if forms else [], f"doculect {lid} profile")
        annotations, features = [], []
        if forms:
            for field in ("form", "value", "segments"):
                for marker in ("primary_stress", "secondary_stress"):
                    key = field, marker
                    state = "observed" if marked[key] else "not_observed" if available[field] > 0 else "missing_input"
                    annotations.append((field, marker, available[field], marked[key], occurrences[key], state, examples.get(key)))
                    field_totals[field + ":" + marker] += marked[key]
            for feature in FEATURES:
                features.append((feature, counts[feature], presence[feature], len(distinct[feature]),
                                 "observed" if counts[feature] else "not_observed", feature_examples.get(feature)))
                feature_totals[feature] += presence[feature]
        equal(conn.execute("SELECT source_field,marker,available_forms,marked_forms,marker_occurrences,status,example_form_id "
                           "FROM prosody_annotation WHERE language_id=? ORDER BY source_field,marker", (lid,)).fetchall(), sorted(annotations), f"doculect {lid} annotations")
        equal(conn.execute("SELECT feature,token_occurrences,form_count,distinct_tokens,status,example_form_id "
                           "FROM prosody_feature_stat WHERE language_id=? ORDER BY feature", (lid,)).fetchall(), sorted(features), f"doculect {lid} features")
        totals.update(forms=forms, tokens=ntokens, profiles=bool(forms))
        if number % 100 == 0 or number == len(languages):
            progress(f"Validate: {number:,}/{len(languages):,} doculects")
    equal(totals["forms"], declared, "analysis total")
    equal(totals["forms"], conn.execute("SELECT COUNT(*) FROM lexibank_form").fetchone()[0], "form coverage")
    equal(totals["profiles"], conn.execute("SELECT COUNT(*) FROM prosody_profile").fetchone()[0], "profile coverage")
    equal(digest.hexdigest(), saved_digest, "source fingerprint")
    for table in TABLES:
        if conn.execute(f"PRAGMA foreign_key_check({table})").fetchone():
            raise RuntimeError(f"Foreign key failure: {table}")
    equal(conn.execute("PRAGMA quick_check").fetchall(), [("ok",)], "SQLite quick_check")
    return {"status": "passed", "method_version": version, "source_digest": saved_digest, **totals,
            "stress_marked_forms_by_field": dict(sorted(field_totals.items())),
            "feature_forms": dict(sorted(feature_totals.items())),
            "tables": {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in TABLES}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=ROOT / "data/compiled/reference.sqlite")
    args = parser.parse_args()
    conn = sqlite3.connect(args.database.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        conn.execute("BEGIN")
        print(json.dumps(validate(conn), indent=2))
    finally:
        conn.close()


if __name__ == "__main__":
    main()

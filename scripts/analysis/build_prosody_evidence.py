"""Step 7: build and validate explicit stress/tone/length annotation evidence."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/validation"))
from validate_prosody_evidence import validate

ANALYSIS_ID = "lexibank_2_2_1_prosody_evidence_v1"
VERSION = "1.0.0"
FEATURES = ("standalone_tone", "attached_tone", "primary_stress", "secondary_stress", "long", "mid_long", "ultra_short")
MARKERS = {"primary_stress": "ˈ", "secondary_stress": "ˌ"}
FIELDS = ("form", "value", "segments")
TABLES = ("prosody_analysis", "prosody_profile", "prosody_annotation", "prosody_token_feature", "prosody_feature_stat")
NOTES = (
    "Counts explicit IPA U+02C8/U+02CC in each original Form, Value and Segments "
    "field independently. No ASCII apostrophe, acute accent, capitalization or "
    "prosodic-string conversion to stress. observed means an annotation occurs; "
    "not_observed means it was not found in available input; missing_input means "
    "that field is unavailable. These never mean a feature is absent from a "
    "language. System classification stays unassessed. Standalone tones use "
    "the imported token type; attached tone/stress/length use exact words in "
    "Lexibank's CLTS-derived phoneme descriptions, including unmaterialized "
    "sounds. A complex token bearing a feature is counted once per occurrence, "
    "not once per repeated descriptor. Features and fields may overlap. No "
    "contrast, stress placement, metrical rule or tone system is inferred. "
    "Every source form remains one corpus observation per doculect. Examples "
    "are the earliest matching local form ID and preserve access to provenance."
)


def token_features(kind, description):
    if kind not in {"phoneme", "tone", "boundary", "special"}:
        raise RuntimeError(f"Unknown token type: {kind}")
    if kind == "tone":
        return ("standalone_tone",)
    if kind != "phoneme":
        return ()
    if not description:
        raise RuntimeError("Phoneme token has no source description")
    words = set(description.split())
    labels = {"tone": "attached_tone", "primary-stress": "primary_stress",
              "secondary-stress": "secondary_stress", "long": "long",
              "mid-long": "mid_long", "ultra-short": "ultra_short"}
    return tuple(sorted(labels[word] for word in words if word in labels))


def build(conn, progress=print):
    if not conn.in_transaction:
        raise RuntimeError("Step 7 requires an explicit transaction")
    if conn.execute("SELECT name,version FROM reference_source WHERE id='lexibank'").fetchone() != ("Lexibank Analysed", "2.2.1"):
        raise RuntimeError("Expected imported Lexibank Analysed 2.2.1")
    total = conn.execute("SELECT COUNT(*) FROM lexibank_form").fetchone()[0]
    if not total:
        raise RuntimeError("No Lexibank forms")
    vocab_rows = conn.execute("SELECT t.id,t.token,t.token_type,p.description FROM lexibank_segment_token t "
                              "LEFT JOIN lexibank_phoneme p ON p.id=t.phoneme_id ORDER BY t.id").fetchall()
    vocab = {text: (tid, token_features(kind, description)) for tid, text, kind, description in vocab_rows}
    digest = hashlib.sha256(json.dumps(vocab_rows, ensure_ascii=False).encode())
    statement = ""
    for line in (ROOT / "database/schema/011_prosody_evidence.sql").read_text(encoding="utf-8").splitlines(True):
        statement += line
        if sqlite3.complete_statement(statement):
            conn.execute(statement)
            statement = ""
    if statement.strip():
        raise RuntimeError("Incomplete Step 7 schema")
    for table in reversed(TABLES):
        conn.execute(f"DELETE FROM {table}")
    conn.execute("INSERT INTO prosody_analysis VALUES (?,?,?,?,?,?)", (ANALYSIS_ID, "lexibank", VERSION, "pending", total, NOTES))
    conn.executemany("INSERT INTO prosody_token_feature VALUES (?,?)", ((tid, feature) for tid, features in vocab.values() for feature in features))
    languages = conn.execute("SELECT id FROM lexibank_language ORDER BY id").fetchall()
    for number, (lid,) in enumerate(languages, 1):
        available, marked, occurrences = Counter(), Counter(), Counter()
        annotation_examples, feature_examples = {}, {}
        counts, presence = Counter(), Counter()
        distinct = defaultdict(set)
        forms = segments = 0
        for row in conn.execute("SELECT id,form,value,segments FROM lexibank_form WHERE language_id=? ORDER BY id", (lid,)):
            fid, form, value, raw = row
            digest.update((json.dumps([lid, *row], ensure_ascii=False) + "\n").encode())
            tokens = raw.split()
            if not tokens:
                raise RuntimeError(f"Form {fid}: no segments")
            forms += 1
            segments += len(tokens)
            for field, text in zip(FIELDS, (form, value, raw)):
                available[field] += bool(text and text.strip())
                for marker, char in MARKERS.items():
                    count = (text or "").count(char)
                    if count:
                        key = field, marker
                        marked[key] += 1
                        occurrences[key] += count
                        annotation_examples.setdefault(key, fid)
            seen = set()
            for token, count in Counter(tokens).items():
                if token not in vocab:
                    raise RuntimeError(f"Form {fid}: unknown token {token!r}")
                tid, features = vocab[token]
                for feature in features:
                    counts[feature] += count
                    distinct[feature].add(tid)
                    seen.add(feature)
                    feature_examples.setdefault(feature, fid)
            presence.update(seen)
        if forms:
            conn.execute("INSERT INTO prosody_profile VALUES (?,?,?,?,?)", (lid, ANALYSIS_ID, forms, segments, "unassessed"))
            for field in FIELDS:
                for marker in MARKERS:
                    key = field, marker
                    status = "observed" if marked[key] else "not_observed" if available[field] else "missing_input"
                    conn.execute("INSERT INTO prosody_annotation VALUES (?,?,?,?,?,?,?,?)",
                                 (lid, field, marker, available[field], marked[key], occurrences[key], status, annotation_examples.get(key)))
            conn.executemany("INSERT INTO prosody_feature_stat VALUES (?,?,?,?,?,?,?)", (
                (lid, feature, counts[feature], presence[feature], len(distinct[feature]),
                 "observed" if counts[feature] else "not_observed", feature_examples.get(feature)) for feature in FEATURES))
        if number % 100 == 0 or number == len(languages):
            progress(f"Build: {number:,}/{len(languages):,} doculects")
    conn.execute("UPDATE prosody_analysis SET source_digest=?", (digest.hexdigest(),))
    return validate(conn, progress)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=ROOT / "data/compiled/reference.sqlite")
    parser.add_argument("--report", type=Path, default=ROOT / "data/compiled/prosody-evidence-report.json")
    args = parser.parse_args()
    started = time.monotonic()
    conn = sqlite3.connect(args.database.resolve().as_uri() + "?mode=rw", uri=True)
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        conn.execute("BEGIN IMMEDIATE")
        report = build(conn, lambda message: print(message, flush=True))
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
    report["elapsed_seconds"] = round(time.monotonic() - started, 2)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("\nSTEP 7 BUILD AND VALIDATION PASSED")
    print(json.dumps(report, indent=2))
    print("D1 was not modified. No export/import is needed now.")


if __name__ == "__main__":
    main()

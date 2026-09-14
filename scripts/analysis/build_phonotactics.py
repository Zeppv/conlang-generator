"""Atomic Step 5 build + independent validation. No D1 or network operations."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "validation"))
from validate_phonotactics import validate  # noqa: E402

ANALYSIS_ID = "lexibank_2_2_1_raw_sequences_v1"
METHOD_VERSION = "1.0.0"
TABLES = (
    "phonotactic_analysis", "phonotactic_profile", "phonotactic_token_stat",
    "phonotactic_bigram", "phonotactic_shape",
)
NOTES = (
    "Raw adjacent-token evidence per Lexibank doculect; each source form is an "
    "observation, including duplicate pronunciations, loans and variants. "
    "Tones, generated phonemes, + and special markers remain in the sequence. "
    "Pairs never skip a marker or cross a form. Initial/final means literal "
    "form edge, not syllable edge. CV/prosodic strings are preserved upstream "
    "annotations, not inferred syllabification or stress. Counts are corpus "
    "evidence, not language-balanced probabilities or grammatical constraints."
)


def apply_schema(conn):
    statement = ""
    for line in (ROOT / "database/schema/009_phonotactics.sql").read_text(encoding="utf-8").splitlines(True):
        statement += line
        if sqlite3.complete_statement(statement):
            conn.execute(statement)
            statement = ""
    if statement.strip():
        raise RuntimeError("Incomplete Step 5 schema")


def build(conn, progress=print):
    """Caller owns transaction; any build/validation failure must roll it back."""
    if not conn.in_transaction:
        raise RuntimeError("Step 5 requires an explicit transaction")
    source = conn.execute("SELECT name, version FROM reference_source WHERE id='lexibank'").fetchone()
    if source is None or tuple(source) != ("Lexibank Analysed", "2.2.1"):
        raise RuntimeError("Expected imported Lexibank Analysed 2.2.1")
    total = conn.execute("SELECT COUNT(*), COALESCE(SUM(segment_count),0) FROM lexibank_form").fetchone()
    if not total[0] or not total[1]:
        raise RuntimeError("Lexibank forms are empty; import Lexibank first")
    tokens = {row[1]: (row[0], row[2]) for row in conn.execute(
        "SELECT id, token, token_type FROM lexibank_segment_token ORDER BY id")}
    if not tokens or any(t[1] not in {"phoneme", "tone", "boundary", "special"} for t in tokens.values()):
        raise RuntimeError("Invalid Lexibank token vocabulary")
    apply_schema(conn)
    for table in reversed(TABLES):
        conn.execute(f"DELETE FROM {table}")
    digest = hashlib.sha256()
    digest.update(json.dumps(sorted(tokens.items()), ensure_ascii=False).encode("utf-8"))
    conn.execute("INSERT INTO phonotactic_analysis VALUES (?,?,?,?,?,?,?)",
                 (ANALYSIS_ID, "lexibank", METHOD_VERSION, "pending", *total, NOTES))
    languages = conn.execute("SELECT id FROM lexibank_language ORDER BY id").fetchall()
    processed = 0
    for number, (language_id,) in enumerate(languages, 1):
        occurrences, presence, initial, final = (Counter() for _ in range(4))
        pairs, pair_presence, shapes, types = (Counter() for _ in range(4))
        forms = count = 0
        for row in conn.execute(
            "SELECT id, segments, segment_count, cv_template, prosodic_string "
            "FROM lexibank_form WHERE language_id=? ORDER BY id", (language_id,)):
            form_id, raw, declared, cv, prosody = row
            strings = raw.split()
            if not strings or len(strings) != declared:
                raise RuntimeError(f"Form {form_id}: invalid segment count")
            try:
                ids = [tokens[token][0] for token in strings]
                types.update(tokens[token][1] for token in strings)
            except KeyError as exc:
                raise RuntimeError(f"Form {form_id}: unknown token {exc}") from exc
            digest.update((json.dumps([language_id, *row], ensure_ascii=False) + "\n").encode("utf-8"))
            forms += 1
            count += len(ids)
            occurrences.update(ids)
            presence.update(set(ids))
            initial[ids[0]] += 1
            final[ids[-1]] += 1
            adjacent = list(zip(ids, ids[1:]))
            pairs.update(adjacent)
            pair_presence.update(set(adjacent))
            shapes[cv, prosody] += 1
        if forms:
            conn.execute("INSERT INTO phonotactic_profile VALUES (?,?,?,?,?,?)",
                         (language_id, ANALYSIS_ID, forms, count, types["boundary"], types["special"]))
            conn.executemany("INSERT INTO phonotactic_token_stat VALUES (?,?,?,?,?,?)", (
                (language_id, token, n, presence[token], initial[token], final[token])
                for token, n in sorted(occurrences.items())))
            conn.executemany("INSERT INTO phonotactic_bigram VALUES (?,?,?,?,?)", (
                (language_id, a, b, n, pair_presence[a, b]) for (a, b), n in sorted(pairs.items())))
            conn.executemany("INSERT INTO phonotactic_shape VALUES (?,?,?,?)", (
                (language_id, cv, pro, n) for (cv, pro), n in sorted(shapes.items())))
        processed += forms
        if number % 100 == 0 or number == len(languages):
            progress(f"Build: {number:,}/{len(languages):,} doculects; {processed:,}/{total[0]:,} forms")
    if processed != total[0]:
        raise RuntimeError("Some source forms have no valid doculect")
    conn.execute("UPDATE phonotactic_analysis SET source_digest=? WHERE id=?", (digest.hexdigest(), ANALYSIS_ID))
    return validate(conn, progress)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=ROOT / "data/compiled/reference.sqlite")
    parser.add_argument("--report", type=Path, default=ROOT / "data/compiled/phonotactics-report.json")
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
    print("\nSTEP 5 BUILD AND VALIDATION PASSED", flush=True)
    print(json.dumps(report, indent=2))
    print(f"Report: {args.report}\nD1 was not modified. No full export/import is needed now.")


if __name__ == "__main__":
    main()

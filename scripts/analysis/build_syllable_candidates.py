"""Step 6: atomic syllable-shape candidate build and automatic validation."""
import argparse
from collections import Counter
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/validation"))
from validate_syllable_candidates import validate

ANALYSIS_ID = "lexibank_2_2_1_cv_candidates_v1"
VERSION = "1.0.0"
TABLES = ("syllable_analysis", "syllable_profile", "syllable_candidate", "syllable_exclusion")
NOTES = (
    "CV projection candidates, not observed syllables. Every eligible upstream V "
    "is one nucleus; every C is peripheral. T is omitted from this projection "
    "only. + delimits independent components, not asserted syllables. Adjacent "
    "Vs, vowel-free/empty components, special tokens, explicitly syllabic "
    "consonants, non-syllabic simple vowels and unknown classes exclude the "
    "whole form. Intervocalic C runs admit every coda/onset split, including "
    "zero onset; no maximal-onset, sonority, ambisyllabicity or extrasyllabicity "
    "rule is inferred. possible_slots counts nucleus positions permitting a "
    "shape; forced_slots counts positions with only that shape under this "
    "model. Alternative shapes overlap; do not normalize their counts as "
    "probabilities. Corpus forms remain weighted observations per doculect."
)


def vocabulary(conn):
    return {token: (kind, description or "") for token, kind, description in conn.execute(
        "SELECT t.token, t.token_type, p.description FROM lexibank_segment_token t "
        "LEFT JOIN lexibank_phoneme p ON p.id=t.phoneme_id ORDER BY t.token")}


def source_key(cv, raw, vocab, fid):
    tokens = raw.split()
    if not tokens or len(cv) != len(tokens):
        raise RuntimeError(f"Form {fid}: CV/token alignment is invalid")
    reasons = set()
    for char, token in zip(cv, tokens):
        if token not in vocab:
            raise RuntimeError(f"Form {fid}: unknown token {token!r}")
        kind, description = vocab[token]
        if kind not in {"phoneme", "tone", "boundary", "special"}:
            raise RuntimeError(f"Form {fid}: unknown token type {kind!r}")
        if kind == "special":
            reasons.add("special_marker")
        if kind == "boundary" and (token != "+" or char != "+"):
            raise RuntimeError(f"Form {fid}: inconsistent boundary annotation")
        if char == "+" and kind != "boundary":
            raise RuntimeError(f"Form {fid}: inconsistent boundary annotation")
        words = description.split()
        if char == "C" and "syllabic" in words:
            reasons.add("syllabic_consonant")
        if char == "V" and "non-syllabic" in words and description.endswith(" vowel"):
            reasons.add("non_syllabic_vowel")
    # One documented exclusion per form, with stable precedence.
    for reason in ("special_marker", "syllabic_consonant", "non_syllabic_vowel"):
        if reason in reasons:
            return cv, reason
    return cv, ""


@lru_cache(maxsize=50000)
def project(cv, source_reason=""):
    if source_reason:
        return source_reason, (), 0, 0
    if set(cv) - set("CVT+"):
        return "unsupported_class", (), 0, 0
    components = cv.replace("T", "").split("+")
    if any(not component for component in components):
        return "empty_component", (), 0, 0
    if any("V" not in component for component in components):
        return "no_vowel", (), 0, 0
    if any("VV" in component for component in components):
        return "adjacent_vowels", (), 0, 0
    possible, forced = Counter(), Counter()
    nuclei = ambiguous = 0
    for component in components:
        runs = component.split("V")
        for index in range(len(runs) - 1):
            left, right = len(runs[index]), len(runs[index + 1])
            onsets = (left,) if index == 0 else range(left + 1)
            codas = (right,) if index == len(runs) - 2 else range(right + 1)
            unique = len(onsets) == len(codas) == 1
            nuclei += 1
            ambiguous += not unique
            for onset in onsets:
                for coda in codas:
                    possible[onset, coda] += 1
                    if unique:
                        forced[onset, coda] += 1
    return "", tuple((a, b, n, forced[a, b]) for (a, b), n in sorted(possible.items())), nuclei, ambiguous


def build(conn, progress=print):
    if not conn.in_transaction:
        raise RuntimeError("Step 6 requires an explicit transaction")
    if conn.execute("SELECT name,version FROM reference_source WHERE id='lexibank'").fetchone() != ("Lexibank Analysed", "2.2.1"):
        raise RuntimeError("Expected imported Lexibank Analysed 2.2.1")
    total = conn.execute("SELECT COUNT(*) FROM lexibank_form").fetchone()[0]
    if not total:
        raise RuntimeError("No Lexibank forms")
    vocab = vocabulary(conn)
    digest = hashlib.sha256(json.dumps(sorted(vocab.items()), ensure_ascii=False).encode())
    statement = ""
    for line in (ROOT / "database/schema/010_syllable_candidates.sql").read_text(encoding="utf-8").splitlines(True):
        statement += line
        if sqlite3.complete_statement(statement):
            conn.execute(statement)
            statement = ""
    if statement.strip():
        raise RuntimeError("Incomplete Step 6 schema")
    for table in reversed(TABLES):
        conn.execute(f"DELETE FROM {table}")
    conn.execute("INSERT INTO syllable_analysis VALUES (?,?,?,?,?,?)", (ANALYSIS_ID, "lexibank", VERSION, "pending", total, NOTES))
    languages = conn.execute("SELECT id FROM lexibank_language ORDER BY id").fetchall()
    for number, (lid,) in enumerate(languages, 1):
        shapes = Counter()
        for fid, cv, raw in conn.execute("SELECT id,cv_template,segments FROM lexibank_form WHERE language_id=? ORDER BY id", (lid,)):
            shapes[source_key(cv, raw, vocab, fid)] += 1
            digest.update((json.dumps([lid, fid, cv, raw], ensure_ascii=False) + "\n").encode())
        if not shapes:
            continue
        eligible = nuclei = ambiguous = 0
        possible, forced, exclusions = Counter(), Counter(), Counter()
        for (cv, reason), weight in shapes.items():
            reason, candidates, count, unclear = project(cv, reason)
            if reason:
                exclusions[reason] += weight
                continue
            eligible += weight
            nuclei += count * weight
            ambiguous += unclear * weight
            for a, b, n, f in candidates:
                possible[a, b] += n * weight
                forced[a, b] += f * weight
        conn.execute("INSERT INTO syllable_profile VALUES (?,?,?,?,?,?)", (lid, ANALYSIS_ID, sum(shapes.values()), eligible, nuclei, ambiguous))
        conn.executemany("INSERT INTO syllable_candidate VALUES (?,?,?,?,?)", ((lid, a, b, n, forced[a, b]) for (a, b), n in sorted(possible.items())))
        conn.executemany("INSERT INTO syllable_exclusion VALUES (?,?,?)", ((lid, reason, n) for reason, n in sorted(exclusions.items())))
        if number % 100 == 0 or number == len(languages):
            progress(f"Build: {number:,}/{len(languages):,} doculects")
    conn.execute("UPDATE syllable_analysis SET source_digest=?", (digest.hexdigest(),))
    return validate(conn, progress)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=ROOT / "data/compiled/reference.sqlite")
    parser.add_argument("--report", type=Path, default=ROOT / "data/compiled/syllable-candidates-report.json")
    args = parser.parse_args()
    started = time.monotonic()
    conn = sqlite3.connect(args.database.resolve().as_uri() + "?mode=rw", uri=True)
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        conn.execute("BEGIN IMMEDIATE")
        report = build(conn, lambda text: print(text, flush=True))
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
    report["elapsed_seconds"] = round(time.monotonic() - started, 2)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("\nSTEP 6 BUILD AND VALIDATION PASSED")
    print(json.dumps(report, indent=2))
    print("D1 was not modified. No export/import is needed now.")


if __name__ == "__main__":
    main()

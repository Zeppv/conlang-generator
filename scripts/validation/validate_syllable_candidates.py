"""Independent position-based check of the Step 6 CV projection model."""
import argparse
from collections import Counter
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[2]
TABLES = ("syllable_analysis", "syllable_profile", "syllable_candidate", "syllable_exclusion")


@lru_cache(maxsize=50000)
def reference_project(cv, flag):
    if flag:
        return flag, (), 0, 0
    if any(char not in "CVT+" for char in cv):
        return "unsupported_class", (), 0, 0
    parts = "".join(char for char in cv if char != "T").split("+")
    if "" in parts:
        return "empty_component", (), 0, 0
    if any(part.count("V") == 0 for part in parts):
        return "no_vowel", (), 0, 0
    if any("VV" in part for part in parts):
        return "adjacent_vowels", (), 0, 0
    options = []
    for part in parts:
        vowels = [i for i, char in enumerate(part) if char == "V"]
        for i, position in enumerate(vowels):
            starts = [0] if i == 0 else list(range(vowels[i - 1] + 1, position + 1))
            ends = [len(part)] if i + 1 == len(vowels) else list(range(position + 1, vowels[i + 1] + 1))
            options.append({(position - start, end - position - 1) for start in starts for end in ends})
    possible, forced = Counter(), Counter()
    for choices in options:
        possible.update(choices)
        if len(choices) == 1:
            forced.update(choices)
    return "", tuple((a, b, n, forced[a, b]) for (a, b), n in sorted(possible.items())), len(options), sum(len(x) > 1 for x in options)


def equal(actual, expected, label):
    if actual != expected:
        raise RuntimeError(f"Step 6 validation failed: {label}")


def validate(conn, progress=print):
    records = conn.execute("SELECT id,source_id,method_version,source_digest,form_count FROM syllable_analysis").fetchall()
    if len(records) != 1:
        raise RuntimeError("Expected one syllable analysis")
    aid, source, version, saved_digest, declared_forms = records[0]
    equal((aid, source, version), ("lexibank_2_2_1_cv_candidates_v1", "lexibank", "1.0.0"), "analysis identity")
    equal(conn.execute("SELECT name,version FROM reference_source WHERE id='lexibank'").fetchone(), ("Lexibank Analysed", "2.2.1"), "source version")
    vocab = {token: (kind, description or "") for token, kind, description in conn.execute(
        "SELECT t.token,t.token_type,p.description FROM lexibank_segment_token t "
        "LEFT JOIN lexibank_phoneme p ON p.id=t.phoneme_id ORDER BY t.token")}
    digest = hashlib.sha256(json.dumps(sorted(vocab.items()), ensure_ascii=False).encode())
    totals = Counter()
    exclusion_totals = Counter()
    languages = conn.execute("SELECT id FROM lexibank_language ORDER BY id").fetchall()
    for number, (lid,) in enumerate(languages, 1):
        shapes = Counter()
        for fid, cv, raw in conn.execute("SELECT id,cv_template,segments FROM lexibank_form WHERE language_id=? ORDER BY id", (lid,)):
            tokens = raw.split()
            equal(len(tokens), len(cv), f"form {fid} CV alignment")
            if not tokens:
                raise RuntimeError(f"Empty form {fid}")
            metadata = [vocab[token] for token in tokens]
            flag = ""
            if any(kind == "special" for kind, _ in metadata):
                flag = "special_marker"
            elif any(char == "C" and "syllabic" in desc.split() for char, (_, desc) in zip(cv, metadata)):
                flag = "syllabic_consonant"
            elif any(char == "V" and "non-syllabic" in desc.split() and desc.endswith(" vowel") for char, (_, desc) in zip(cv, metadata)):
                flag = "non_syllabic_vowel"
            shapes[cv, flag] += 1
            digest.update((json.dumps([lid, fid, cv, raw], ensure_ascii=False) + "\n").encode())
        possible, forced, excluded = Counter(), Counter(), Counter()
        eligible = nuclei = ambiguous = 0
        for (cv, flag), weight in shapes.items():
            reason, rows, n, a = reference_project(cv, flag)
            if reason:
                excluded[reason] += weight
            else:
                eligible += weight
                nuclei += n * weight
                ambiguous += a * weight
                for onset, coda, count, fixed in rows:
                    possible[onset, coda] += weight * count
                    forced[onset, coda] += weight * fixed
        forms = sum(shapes.values())
        expected_profile = [(lid, aid, forms, eligible, nuclei, ambiguous)] if forms else []
        equal(conn.execute("SELECT * FROM syllable_profile WHERE language_id=?", (lid,)).fetchall(), expected_profile, f"doculect {lid} profile")
        equal(conn.execute("SELECT onset_length,coda_length,possible_slots,forced_slots FROM syllable_candidate WHERE language_id=? ORDER BY onset_length,coda_length", (lid,)).fetchall(),
              [(a, b, count, forced[a, b]) for (a, b), count in sorted(possible.items())], f"doculect {lid} candidates")
        equal(conn.execute("SELECT reason,form_count FROM syllable_exclusion WHERE language_id=? ORDER BY reason", (lid,)).fetchall(), sorted(excluded.items()), f"doculect {lid} exclusions")
        equal(sum(forced.values()), nuclei - ambiguous, f"doculect {lid} forced-slot conservation")
        equal(eligible + sum(excluded.values()), forms, f"doculect {lid} form conservation")
        totals.update(forms=forms, eligible_forms=eligible, projected_nuclei=nuclei, ambiguous_nuclei=ambiguous, profiles=bool(forms))
        exclusion_totals.update(excluded)
        if number % 100 == 0 or number == len(languages):
            progress(f"Validate: {number:,}/{len(languages):,} doculects")
    equal(totals["forms"], declared_forms, "analysis form count")
    equal(totals["forms"], conn.execute("SELECT COUNT(*) FROM lexibank_form").fetchone()[0], "source coverage")
    equal(totals["profiles"], conn.execute("SELECT COUNT(*) FROM syllable_profile").fetchone()[0], "profile coverage")
    equal(digest.hexdigest(), saved_digest, "source fingerprint")
    for table in TABLES:
        if conn.execute(f"PRAGMA foreign_key_check({table})").fetchone():
            raise RuntimeError(f"Foreign key failure: {table}")
    equal(conn.execute("PRAGMA quick_check").fetchall(), [("ok",)], "SQLite quick_check")
    return {"status": "passed", "method_version": version, "source_digest": saved_digest,
            **totals, "excluded_forms": sum(exclusion_totals.values()), "exclusions": dict(sorted(exclusion_totals.items())),
            "candidate_rows": conn.execute("SELECT COUNT(*) FROM syllable_candidate").fetchone()[0]}


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

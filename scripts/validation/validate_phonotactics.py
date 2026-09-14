"""Check Step 5 against the normalized form-token rows, not the builder's input path."""
import argparse
from collections import Counter
import hashlib
from itertools import groupby
import json
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[2]
TABLES = ("phonotactic_analysis", "phonotactic_profile", "phonotactic_token_stat",
          "phonotactic_bigram", "phonotactic_shape")


def require_equal(actual, expected, label):
    if actual != expected:
        raise RuntimeError(f"Validation failed: {label}")


def validate(conn, progress=print):
    tokens = {row[0]: (row[1], row[2]) for row in conn.execute(
        "SELECT id, token, token_type FROM lexibank_segment_token ORDER BY id")}
    digest = hashlib.sha256()
    digest.update(json.dumps(sorted((name, (tid, kind)) for tid, (name, kind) in tokens.items()),
                             ensure_ascii=False).encode("utf-8"))
    analyses = conn.execute("SELECT id, source_id, method_version, source_digest, form_count, token_count "
                            "FROM phonotactic_analysis").fetchall()
    if len(analyses) != 1:
        raise RuntimeError("Expected exactly one phonotactic analysis")
    aid, source, version, saved_digest, declared_forms, declared_tokens = analyses[0]
    require_equal((aid, source, version), ("lexibank_2_2_1_raw_sequences_v1", "lexibank", "1.0.0"), "analysis identity")
    languages = conn.execute("SELECT id FROM lexibank_language ORDER BY id").fetchall()
    all_forms = all_tokens = profile_count = 0
    for number, (lid,) in enumerate(languages, 1):
        unigram, first, last, token_forms = (Counter() for _ in range(4))
        bigram, pair_forms, shape, kinds = (Counter() for _ in range(4))
        nforms = ntokens = 0
        rows = conn.execute(
            "SELECT f.id, f.segments, f.segment_count, f.cv_template, f.prosodic_string, "
            "s.segment_order, s.token_id FROM lexibank_form f "
            "LEFT JOIN lexibank_form_segment s ON s.form_id=f.id "
            "WHERE f.language_id=? ORDER BY f.id, s.segment_order", (lid,))
        for form_id, group in groupby(rows, key=lambda row: row[0]):
            entries = list(group)
            base = entries[0][:5]
            ordered = [entry[6] for entry in entries]
            require_equal([entry[5] for entry in entries], list(range(1, base[2] + 1)),
                          f"form {form_id} normalized positions")
            require_equal([tokens[tid][0] for tid in ordered], base[1].split(),
                          f"form {form_id} normalized tokens")
            digest.update((json.dumps([lid, *base], ensure_ascii=False) + "\n").encode("utf-8"))
            nforms += 1
            ntokens += len(ordered)
            seen_tokens, seen_pairs = set(), set()
            previous = None
            for tid in ordered:
                unigram[tid] += 1
                kinds[tokens[tid][1]] += 1
                seen_tokens.add(tid)
                if previous is not None:
                    bigram[previous, tid] += 1
                    seen_pairs.add((previous, tid))
                previous = tid
            token_forms.update(seen_tokens)
            pair_forms.update(seen_pairs)
            first[ordered[0]] += 1
            last[ordered[-1]] += 1
            shape[base[3], base[4]] += 1
        expected_profile = [(lid, aid, nforms, ntokens, kinds["boundary"], kinds["special"])] if nforms else []
        require_equal(conn.execute("SELECT * FROM phonotactic_profile WHERE language_id=?", (lid,)).fetchall(),
                      expected_profile, f"doculect {lid} profile")
        require_equal(conn.execute("SELECT token_id, occurrence_count, form_count, initial_count, final_count "
                                   "FROM phonotactic_token_stat WHERE language_id=? ORDER BY token_id", (lid,)).fetchall(),
                      [(t, n, token_forms[t], first[t], last[t]) for t, n in sorted(unigram.items())], f"doculect {lid} tokens")
        require_equal(conn.execute("SELECT left_token_id, right_token_id, occurrence_count, form_count "
                                   "FROM phonotactic_bigram WHERE language_id=? ORDER BY left_token_id, right_token_id", (lid,)).fetchall(),
                      [(a, b, n, pair_forms[a, b]) for (a, b), n in sorted(bigram.items())], f"doculect {lid} bigrams")
        require_equal(conn.execute("SELECT cv_template, prosodic_string, form_count FROM phonotactic_shape "
                                   "WHERE language_id=? ORDER BY cv_template, prosodic_string", (lid,)).fetchall(),
                      [(cv, pro, n) for (cv, pro), n in sorted(shape.items())], f"doculect {lid} shapes")
        require_equal(sum(bigram.values()), ntokens - nforms, f"doculect {lid} adjacency conservation")
        all_forms += nforms
        all_tokens += ntokens
        profile_count += bool(nforms)
        if number % 100 == 0 or number == len(languages):
            progress(f"Validate: {number:,}/{len(languages):,} doculects; {all_forms:,} forms")
    require_equal((all_forms, all_tokens), (declared_forms, declared_tokens), "analysis totals")
    require_equal(all_forms, conn.execute("SELECT COUNT(*) FROM lexibank_form").fetchone()[0], "source form coverage")
    require_equal(all_tokens, conn.execute("SELECT COUNT(*) FROM lexibank_form_segment").fetchone()[0], "source token coverage")
    require_equal(digest.hexdigest(), saved_digest, "source fingerprint")
    require_equal(conn.execute("SELECT COUNT(*) FROM phonotactic_profile").fetchone()[0], profile_count, "profile coverage")
    for table in TABLES:
        if conn.execute(f"PRAGMA foreign_key_check({table})").fetchone():
            raise RuntimeError(f"Foreign key failure: {table}")
    require_equal(conn.execute("PRAGMA quick_check").fetchall(), [("ok",)], "SQLite quick_check")
    return {"status": "passed", "method_version": version, "source_digest": saved_digest,
            "source_forms": all_forms, "source_tokens": all_tokens,
            "tables": {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in TABLES}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=ROOT / "data/compiled/reference.sqlite")
    args = parser.parse_args()
    conn = sqlite3.connect(args.database.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        conn.execute("BEGIN")
        print(json.dumps(validate(conn, lambda msg: print(msg, flush=True)), indent=2))
    finally:
        conn.close()


if __name__ == "__main__":
    main()

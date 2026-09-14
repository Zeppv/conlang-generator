"""Optional full-corpus Step 5 test with isolated minimal input tables.

Uses the verified local CLDF release, not the production reference.sqlite.
This checks real sequence processing; it does not replace upstream importer validation.
"""
import argparse
import csv
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/analysis"))
from build_phonotactics import build


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--syllables", action="store_true", help="Test Step 6 without rebuilding Step 5")
    mode.add_argument("--prosody", action="store_true", help="Test Step 7 without rebuilding Steps 5/6")
    mode.add_argument("--evaluate", action="store_true", help="Test evaluator with real PHOIBLE and the demo doculect")
    mode.add_argument("--web", action="store_true", help="Test the real demo evidence through isolated local D1 and Worker")
    args = parser.parse_args()
    if args.web:
        args.evaluate = True
    if args.prosody:
        from build_prosody_evidence import build as run_build
    elif args.syllables:
        from build_syllable_candidates import build as run_build
    else:
        run_build = build
    cldf = ROOT / "data/raw/lexibank/cldf"
    with (cldf / "phonemes.csv").open(encoding="utf-8-sig", newline="") as stream:
        phonemes = {row["Name"]: (n, row["Description"]) for n, row in enumerate(csv.DictReader(stream), 1)}
    with (cldf / "languages.csv").open(encoding="utf-8-sig", newline="") as stream:
        language_rows = list(csv.DictReader(stream))
        languages = {row["ID"]: n for n, row in enumerate(language_rows, 1)}
    demo = json.loads((ROOT / "examples/phonology-proposal.json").read_text(encoding="utf-8")) if args.evaluate else None
    with tempfile.TemporaryDirectory(prefix="phonotactics-corpus-") as temporary:
        db = sqlite3.connect((Path(temporary) / "corpus.sqlite").as_uri(), uri=True)
        try:
            db.executescript("""
                PRAGMA foreign_keys=ON;
                CREATE TABLE reference_source (id TEXT PRIMARY KEY, name TEXT, version TEXT);
                INSERT INTO reference_source VALUES ('lexibank','Lexibank Analysed','2.2.1');
                CREATE TABLE lexibank_language (id INTEGER PRIMARY KEY, lexibank_id TEXT, name TEXT, glottocode TEXT);
                CREATE TABLE lexibank_phoneme (id INTEGER PRIMARY KEY, description TEXT);
                CREATE TABLE lexibank_segment_token (id INTEGER PRIMARY KEY, token TEXT, token_type TEXT, phoneme_id INTEGER);
                CREATE TABLE lexibank_form (id INTEGER PRIMARY KEY, language_id INTEGER,
                    segments TEXT, segment_count INTEGER, cv_template TEXT, prosodic_string TEXT,
                    form TEXT, value TEXT);
                CREATE TABLE lexibank_form_segment (form_id INTEGER, segment_order INTEGER, token_id INTEGER,
                    PRIMARY KEY(form_id,segment_order));
            """)
            db.executemany("INSERT INTO lexibank_language VALUES (?,?,?,?)",
                           ((languages[row["ID"]], row["ID"], row["Name"], row["Glottocode"]) for row in language_rows))
            db.executemany("INSERT INTO lexibank_phoneme VALUES (?,?)", phonemes.values())
            tokens = {}
            batch_forms, batch_segments = [], []
            count = 0

            def flush():
                db.executemany("INSERT INTO lexibank_form VALUES (?,?,?,?,?,?,?,?)", batch_forms)
                db.executemany("INSERT INTO lexibank_form_segment VALUES (?,?,?)", batch_segments)
                batch_forms.clear()
                batch_segments.clear()

            with zipfile.ZipFile(cldf / "forms.csv.zip") as archive:
                with io.TextIOWrapper(archive.open("forms.csv"), encoding="utf-8-sig", newline="") as stream:
                    for fid, row in enumerate(csv.DictReader(stream), 1):
                        sequence = row["Segments"].split()
                        selected = not args.evaluate or row["Language_ID"] == demo["reference_doculect"]
                        if selected:
                            batch_forms.append((fid, languages[row["Language_ID"]], row["Segments"],
                                                len(sequence), row["CV_Template"], row["Prosodic_String"],
                                                row["Form"], row["Value"] or None))
                        for position, token in enumerate(sequence, 1):
                            if token not in tokens:
                                if token in phonemes:
                                    kind = "phoneme"
                                elif token == "+":
                                    kind = "boundary"
                                elif token == "∼":
                                    kind = "special"
                                elif all(char in "⁰¹²³⁴⁵⁶⁷⁸⁹" for char in token):
                                    kind = "tone"
                                else:
                                    raise RuntimeError(f"Unexpected corpus token: {token!r}")
                                tokens[token] = len(tokens) + 1
                                db.execute("INSERT INTO lexibank_segment_token VALUES (?,?,?,?)",
                                           (tokens[token], token, kind, phonemes[token][0] if token in phonemes else None))
                            if selected and not (args.syllables or args.prosody):
                                batch_segments.append((fid, position, tokens[token]))
                        count += 1
                        if fid % 10000 == 0:
                            flush()
                        if fid % 250000 == 0:
                            print(f"Corpus fixture loaded: {fid:,} forms", flush=True)
            flush()
            if count != 1740092 or len(tokens) != 2471:
                raise RuntimeError("Unexpected source corpus counts")
            db.execute("CREATE INDEX form_language ON lexibank_form(language_id)")
            db.commit()
            db.execute("BEGIN IMMEDIATE")
            report = run_build(db, (lambda _: None) if args.evaluate else (lambda msg: print(msg, flush=True)))
            db.commit()
            if args.evaluate:
                from build_syllable_candidates import build as build6
                from build_prosody_evidence import build as build7
                from phonology_evaluator import evaluate
                for next_build in (build6, build7):
                    db.execute("BEGIN IMMEDIATE")
                    next_build(db, lambda _: None)
                    db.commit()
                reference = ROOT / "data/compiled/reference.sqlite"
                db.execute("ATTACH DATABASE ? AS reference", (reference.resolve().as_uri() + "?mode=ro",))
                for table in ("phonology_analysis", "phoible_segment", "phonology_inventory_profile",
                              "phonology_segment_prevalence", "phonology_segment_cooccurrence"):
                    db.execute(f"CREATE TABLE {table} AS SELECT * FROM reference.{table}")
                db.commit()
                db.execute("DETACH DATABASE reference")
                db.execute("PRAGMA query_only=ON")
                db.execute("BEGIN")
                started = time.monotonic()
                report = evaluate(db, demo)
                print(json.dumps({"status": "passed", "evaluation_seconds": round(time.monotonic() - started, 3),
                                  "inventory_mapped": report["inventory"]["mapped_tokens"],
                                  "reference": report["reference_doculect"],
                                  "phonotactics": report["phonotactics"], "syllables": report["syllables"]}, ensure_ascii=False), flush=True)
                if args.web:
                    from run_phonology_web import run
                    run(db, [demo, {**demo, "inventory_scope": "inventory"}, {**demo, "reference_doculect": None}], [demo["reference_doculect"]])
            else:
                print(report, flush=True)
        finally:
            db.close()


if __name__ == "__main__":
    main()

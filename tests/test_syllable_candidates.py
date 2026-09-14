from collections import Counter
from itertools import product
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/analysis"))
from build_syllable_candidates import build, project, TABLES
from validate_syllable_candidates import validate


class ProjectionTests(unittest.TestCase):
    def test_all_short_cv_words_against_complete_partition_enumeration(self):
        for length in range(1, 10):
            for chars in product("CV", repeat=length):
                cv = "".join(chars)
                if "V" not in cv or "VV" in cv:
                    continue
                vowels = [n for n, c in enumerate(cv) if c == "V"]
                options = [set() for _ in vowels]
                # Enumerate all complete word parses; not the production per-slot formula.
                for cuts in product(*(range(a + 1, b + 1) for a, b in zip(vowels, vowels[1:]))):
                    boundaries = [0, *cuts, len(cv)]
                    for index, (a, b) in enumerate(zip(boundaries, boundaries[1:])):
                        syllable = cv[a:b]
                        onset, coda = syllable.split("V")
                        options[index].add((len(onset), len(coda)))
                possible, forced = Counter(), Counter()
                for choices in options:
                    possible.update(choices)
                    if len(choices) == 1:
                        forced.update(choices)
                expected = ("", tuple((a, b, n, forced[a, b]) for (a, b), n in sorted(possible.items())),
                            len(vowels), sum(len(choices) > 1 for choices in options))
                self.assertEqual(project(cv), expected, cv)

    def test_single_nucleus_and_component_boundaries(self):
        self.assertEqual(project("CCVCC"), ("", ((2, 2, 1, 1),), 1, 0))
        self.assertEqual(project("CVT+VC"), ("", ((0, 1, 1, 1), (1, 0, 1, 1)), 2, 0))
        self.assertEqual(project("VCV"), ("", ((0, 0, 2, 0), (0, 1, 1, 0), (1, 0, 1, 0)), 2, 2))

    def test_exclusion_precedence_and_whole_form_exclusion(self):
        for cv, expected in [("CV0", "unsupported_class"), ("CV+T", "empty_component"),
                             ("CV+C", "no_vowel"), ("VTV", "adjacent_vowels")]:
            self.assertEqual(project(cv), (expected, (), 0, 0))
        self.assertEqual(project("CV0", "special_marker")[0], "special_marker")


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE reference_source(id TEXT PRIMARY KEY,name TEXT,version TEXT);
            INSERT INTO reference_source VALUES('lexibank','Lexibank Analysed','2.2.1');
            CREATE TABLE lexibank_language(id INTEGER PRIMARY KEY);
            INSERT INTO lexibank_language VALUES(1),(2),(3);
            CREATE TABLE lexibank_phoneme(id INTEGER PRIMARY KEY,description TEXT);
            INSERT INTO lexibank_phoneme VALUES(1,'open vowel'),(2,'stop consonant'),
                (3,'syllabic lateral consonant'),(4,'non-syllabic open vowel'),
                (5,'from open to non-syllabic close diphthong');
            CREATE TABLE lexibank_segment_token(token TEXT PRIMARY KEY,token_type TEXT,phoneme_id INTEGER);
            INSERT INTO lexibank_segment_token VALUES('a','phoneme',1),('k','phoneme',2),
                ('+','boundary',NULL),('∼','special',NULL),('⁵⁵','tone',NULL),
                ('l̩','phoneme',3),('a̯','phoneme',4),('ai̯','phoneme',5);
            CREATE TABLE lexibank_form(id INTEGER PRIMARY KEY,language_id INTEGER,cv_template TEXT,segments TEXT);
            CREATE INDEX form_language ON lexibank_form(language_id);
            INSERT INTO lexibank_form VALUES
                (1,1,'CCVCC','k k a k k'),(2,1,'VCV','a k a'),
                (3,1,'CVT+VC','k a ⁵⁵ + a k'),(4,1,'VV','a a'),
                (5,1,'CVC','k a ∼'),(6,2,'CV','l̩ a'),
                (7,2,'V','a̯'),(8,2,'V','ai̯');
        """)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def run_build(self):
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            return build(self.db, lambda _: None)

    def snapshot(self):
        return {table: self.db.execute(f"SELECT * FROM {table} ORDER BY 1,2").fetchall() for table in TABLES}

    def test_coverage_and_duplicate_weighting(self):
        report = self.run_build()
        self.assertEqual((report["forms"], report["eligible_forms"], report["excluded_forms"], report["projected_nuclei"], report["ambiguous_nuclei"]), (8, 4, 4, 6, 2))
        self.assertEqual(report["exclusions"], {"adjacent_vowels": 1, "non_syllabic_vowel": 1, "special_marker": 1, "syllabic_consonant": 1})
        self.db.execute("INSERT INTO lexibank_form VALUES(9,1,'CCVCC','k k a k k')")
        self.db.commit()
        self.run_build()
        self.assertEqual(self.db.execute("SELECT possible_slots,forced_slots FROM syllable_candidate WHERE language_id=1 AND onset_length=2 AND coda_length=2").fetchone(), (2, 2))

    def test_determinism_and_invalid_input_rollback(self):
        self.run_build()
        before = self.snapshot()
        self.run_build()
        self.assertEqual(self.snapshot(), before)
        self.db.execute("UPDATE lexibank_form SET cv_template='V' WHERE id=1")
        self.db.commit()
        with self.assertRaisesRegex(RuntimeError, "alignment"):
            self.run_build()
        self.assertEqual(self.snapshot(), before)

    def test_corrupt_candidate_detected(self):
        self.run_build()
        self.db.execute("UPDATE syllable_candidate SET possible_slots=99 WHERE language_id=1 AND onset_length=2")
        with self.assertRaisesRegex(RuntimeError, "candidates"):
            validate(self.db, lambda _: None)

    def test_all_excluded_doculect_preserved(self):
        self.db.execute("DELETE FROM lexibank_form WHERE id=8")
        self.db.commit()
        self.run_build()
        self.assertEqual(self.db.execute("SELECT eligible_forms,projected_nuclei FROM syllable_profile WHERE language_id=2").fetchone(), (0, 0))

    def test_first_failure_rolls_back_schema(self):
        self.db.execute("UPDATE lexibank_form SET segments='missing missing missing missing missing' WHERE id=1")
        self.db.commit()
        with self.assertRaisesRegex(RuntimeError, "unknown token"):
            self.run_build()
        self.assertEqual(self.db.execute("SELECT name FROM sqlite_master WHERE name LIKE 'syllable_%'").fetchall(), [])

    def test_one_command_cli(self):
        with tempfile.TemporaryDirectory(prefix="syllable cli ") as directory:
            database = Path(directory) / "reference.sqlite"
            report = Path(directory) / "report.json"
            disk = sqlite3.connect(database)
            self.db.backup(disk)
            disk.close()
            command = [sys.executable, str(ROOT / "scripts/analysis/build_syllable_candidates.py"),
                       "--database", str(database), "--report", str(report)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(report.read_text())["status"], "passed")


if __name__ == "__main__":
    unittest.main()

"""Small, hand-counted evidence fixtures; no downloads or third-party packages."""
from pathlib import Path
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/analysis"))
from build_phonotactics import build, TABLES
from validate_phonotactics import validate


class PhonotacticsTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE reference_source (id TEXT PRIMARY KEY, name TEXT, version TEXT);
            INSERT INTO reference_source VALUES ('lexibank','Lexibank Analysed','2.2.1');
            CREATE TABLE lexibank_language (id INTEGER PRIMARY KEY);
            INSERT INTO lexibank_language VALUES (1),(2),(3);
            CREATE TABLE lexibank_segment_token (id INTEGER PRIMARY KEY, token TEXT, token_type TEXT);
            INSERT INTO lexibank_segment_token VALUES
                (1,'a','phoneme'),(2,'k','phoneme'),(3,'+','boundary'),
                (4,'∼','special'),(5,'⁵⁵','tone'),(6,'a˞ː','phoneme');
            CREATE TABLE lexibank_form (id INTEGER PRIMARY KEY, language_id INTEGER,
                segments TEXT, segment_count INTEGER, cv_template TEXT, prosodic_string TEXT);
            CREATE INDEX form_language ON lexibank_form(language_id);
            CREATE TABLE lexibank_form_segment (form_id INTEGER, segment_order INTEGER, token_id INTEGER,
                PRIMARY KEY(form_id,segment_order));
        """)
        self.add_form(1, 1, "a a a", "VVV", "VVV")
        self.add_form(2, 1, "k + a ∼ ⁵⁵", "C+V?T", "C_V?T")
        self.add_form(3, 2, "a˞ː", "V", "V")
        self.add_form(4, 2, "a˞ː", "V", "V")  # duplicate evidence retained
        self.add_form(5, 2, "⁵⁵ a", "TV", "TV")
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def add_form(self, fid, lid, raw, cv, pro):
        vocabulary = dict(self.db.execute("SELECT token,id FROM lexibank_segment_token"))
        tokens = raw.split()
        self.db.execute("INSERT INTO lexibank_form VALUES (?,?,?,?,?,?)", (fid, lid, raw, len(tokens), cv, pro))
        self.db.executemany("INSERT INTO lexibank_form_segment VALUES (?,?,?)",
                            [(fid, n, vocabulary[t]) for n, t in enumerate(tokens, 1)])

    def run_build(self):
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            return build(self.db, lambda _: None)

    def snapshot(self):
        return {table: self.db.execute(f"SELECT * FROM {table} ORDER BY 1,2").fetchall() for table in TABLES}

    def test_hand_counted_evidence(self):
        report = self.run_build()
        self.assertEqual(report["source_forms"], 5)
        self.assertEqual(report["source_tokens"], 12)
        self.assertEqual(self.db.execute("SELECT token_count,boundary_count,special_count FROM phonotactic_profile WHERE language_id=1").fetchone(), (8, 1, 1))
        self.assertEqual(self.db.execute("SELECT occurrence_count,form_count,initial_count,final_count FROM phonotactic_token_stat WHERE language_id=1 AND token_id=1").fetchone(), (4, 2, 1, 1))
        self.assertEqual(self.db.execute("SELECT occurrence_count,form_count FROM phonotactic_bigram WHERE language_id=1 AND left_token_id=1 AND right_token_id=1").fetchone(), (2, 1))
        # Boundaries and special markers are not stripped or skipped.
        self.assertIsNone(self.db.execute("SELECT * FROM phonotactic_bigram WHERE left_token_id=2 AND right_token_id=1").fetchone())
        self.assertIsNone(self.db.execute("SELECT * FROM phonotactic_bigram WHERE left_token_id=1 AND right_token_id=5").fetchone())
        self.assertEqual(self.db.execute("SELECT SUM(initial_count),SUM(final_count) FROM phonotactic_token_stat").fetchone(), (5, 5))
        self.assertEqual(self.db.execute("SELECT form_count FROM phonotactic_shape WHERE language_id=2 AND cv_template='V'").fetchone()[0], 2)
        self.assertIsNone(self.db.execute("SELECT * FROM phonotactic_profile WHERE language_id=3").fetchone())

    def test_rerun_is_deterministic(self):
        self.run_build()
        before = self.snapshot()
        self.run_build()
        self.assertEqual(before, self.snapshot())

    def test_invalid_source_rolls_back_previous_build(self):
        self.run_build()
        before = self.snapshot()
        self.db.execute("UPDATE lexibank_form SET segments='unknown' WHERE id=3")
        self.db.commit()
        with self.assertRaisesRegex(RuntimeError, "unknown token"):
            self.run_build()
        self.assertEqual(before, self.snapshot())

    def test_normalized_corruption_rolls_back(self):
        self.run_build()
        before = self.snapshot()
        self.db.execute("UPDATE lexibank_form_segment SET token_id=2 WHERE form_id=1 AND segment_order=2")
        self.db.commit()
        with self.assertRaisesRegex(RuntimeError, "normalized tokens"):
            self.run_build()
        self.assertEqual(before, self.snapshot())

    def test_derived_corruption_detected(self):
        self.run_build()
        self.db.execute("UPDATE phonotactic_bigram SET occurrence_count=99 WHERE left_token_id=1 AND right_token_id=1")
        with self.assertRaisesRegex(RuntimeError, "bigrams"):
            validate(self.db, lambda _: None)

    def test_empty_source_rejected(self):
        self.db.execute("DELETE FROM lexibank_form_segment")
        self.db.execute("DELETE FROM lexibank_form")
        self.db.commit()
        with self.assertRaisesRegex(RuntimeError, "empty"):
            self.run_build()

    def test_bad_source_version_rejected(self):
        self.db.execute("UPDATE reference_source SET version='unknown'")
        self.db.commit()
        with self.assertRaisesRegex(RuntimeError, "2.2.1"):
            self.run_build()

    def test_first_build_failure_rolls_back_schema(self):
        self.db.execute("UPDATE lexibank_form_segment SET segment_order=9 WHERE form_id=1 AND segment_order=2")
        self.db.commit()
        with self.assertRaises(RuntimeError):
            self.run_build()
        self.assertEqual(self.db.execute("SELECT name FROM sqlite_master WHERE name LIKE 'phonotactic_%'").fetchall(), [])

    def test_one_command_build_report_and_rerun(self):
        with tempfile.TemporaryDirectory(prefix="phonotactics cli ") as directory:
            database = Path(directory) / "reference.sqlite"
            report = Path(directory) / "report.json"
            disk = sqlite3.connect(database)
            self.db.backup(disk)
            disk.close()
            command = [sys.executable, str(ROOT / "scripts/analysis/build_phonotactics.py"),
                       "--database", str(database), "--report", str(report)]
            for _ in range(2):
                result = subprocess.run(command, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("STEP 5 BUILD AND VALIDATION PASSED", result.stdout)
                self.assertEqual(json.loads(report.read_text())["source_forms"], 5)

    def test_missing_database_not_created(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "missing.sqlite"
            result = subprocess.run([sys.executable, str(ROOT / "scripts/analysis/build_phonotactics.py"),
                                     "--database", str(database)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(database.exists())


if __name__ == "__main__":
    unittest.main()

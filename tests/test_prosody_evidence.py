import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/analysis"))
from build_prosody_evidence import build, token_features, TABLES
from validate_prosody_evidence import validate


class ProsodyTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE reference_source(id TEXT PRIMARY KEY,name TEXT,version TEXT);
            INSERT INTO reference_source VALUES('lexibank','Lexibank Analysed','2.2.1');
            CREATE TABLE lexibank_language(id INTEGER PRIMARY KEY);
            INSERT INTO lexibank_language VALUES(1),(2),(3);
            CREATE TABLE lexibank_phoneme(id INTEGER PRIMARY KEY,description TEXT);
            INSERT INTO lexibank_phoneme VALUES
                (1,'open vowel'),(2,'long open vowel'),(3,'mid-long open vowel'),
                (5,'open with-high tone vowel'),
                (8,'from long open to long close diphthong'),
                (9,'primary-stress open vowel'),(10,'secondary-stress open vowel'),
                (11,'ultra-short open vowel');
            CREATE TABLE lexibank_segment_token(id INTEGER PRIMARY KEY,token TEXT,token_type TEXT,phoneme_id INTEGER);
            INSERT INTO lexibank_segment_token VALUES
                (1,'a','phoneme',1),(2,'aː','phoneme',2),(3,'aˑ','phoneme',3),
                (4,'⁵⁵','tone',NULL),(5,'á','phoneme',5),
                (6,'+','boundary',NULL),(7,'∼','special',NULL),(8,'aiː','phoneme',8),
                (9,'ˈa','phoneme',9),(10,'ˌa','phoneme',10),(11,'ă','phoneme',11);
            CREATE TABLE lexibank_form(id INTEGER PRIMARY KEY,language_id INTEGER,form TEXT,value TEXT,segments TEXT);
            CREATE INDEX form_language ON lexibank_form(language_id);
        """)
        self.db.executemany("INSERT INTO lexibank_form VALUES(?,?,?,?,?)", [
            (1, 1, "ˈˈkaˌ", "ká'ka", "aː aː ⁵⁵ á"),
            (2, 1, "ka", None, "aˑ + ∼ aiː"),
            (3, 2, "á'a", "\u2009", "a"),
            (4, 1, "ˈa", "ˌa", "ˈa ˌa ă"),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def run_build(self):
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            return build(self.db, lambda _: None)

    def snapshot(self):
        return {table: self.db.execute(f"SELECT * FROM {table} ORDER BY 1,2").fetchall() for table in TABLES}

    def test_field_coverage_counts_and_provenance(self):
        report = self.run_build()
        self.assertEqual((report["forms"], report["tokens"], report["profiles"]), (4, 12, 2))
        self.assertEqual(self.db.execute("SELECT available_forms,marked_forms,marker_occurrences,status,example_form_id "
                                        "FROM prosody_annotation WHERE language_id=1 AND source_field='form' AND marker='primary_stress'").fetchone(),
                         (3, 2, 3, "observed", 1))
        self.assertEqual(self.db.execute("SELECT status,available_forms FROM prosody_annotation "
                                        "WHERE language_id=2 AND source_field='value' AND marker='primary_stress'").fetchone(), ("missing_input", 0))
        self.assertEqual(self.db.execute("SELECT status FROM prosody_annotation "
                                        "WHERE language_id=2 AND source_field='form' AND marker='primary_stress'").fetchone()[0], "not_observed")
        self.assertEqual(self.db.execute("SELECT DISTINCT system_classification FROM prosody_profile").fetchall(), [("unassessed",)])

    def test_token_occurrences_presence_and_compounds(self):
        self.run_build()
        self.assertEqual(self.db.execute("SELECT token_occurrences,form_count,distinct_tokens,example_form_id "
                                        "FROM prosody_feature_stat WHERE language_id=1 AND feature='long'").fetchone(), (3, 2, 2, 1))
        self.assertEqual(self.db.execute("SELECT feature FROM prosody_token_feature WHERE token_id=3").fetchall(), [("mid_long",)])
        self.assertEqual(self.db.execute("SELECT feature FROM prosody_token_feature WHERE token_id IN(6,7)").fetchall(), [])
        self.assertEqual(self.db.execute("SELECT form_count FROM prosody_feature_stat WHERE language_id=1 AND feature='standalone_tone'").fetchone()[0], 1)
        self.assertEqual(self.db.execute("SELECT form_count FROM prosody_feature_stat WHERE language_id=1 AND feature='attached_tone'").fetchone()[0], 1)

    def test_exact_descriptors_not_substrings(self):
        self.assertEqual(token_features("phoneme", "mid-long ultra-short open vowel"), ("mid_long", "ultra_short"))
        self.assertEqual(token_features("phoneme", "from long open to long close diphthong"), ("long",))
        self.assertEqual(token_features("phoneme", "longer midlong vowel"), ())

    def test_deterministic_rerun(self):
        self.run_build()
        before = self.snapshot()
        self.run_build()
        self.assertEqual(before, self.snapshot())

    def test_failed_build_restores_previous_results(self):
        self.run_build()
        before = self.snapshot()
        self.db.execute("UPDATE lexibank_form SET segments='missing' WHERE id=4")
        self.db.commit()
        with self.assertRaisesRegex(RuntimeError, "unknown token"):
            self.run_build()
        self.assertEqual(before, self.snapshot())

    def test_first_failure_rolls_back_schema(self):
        self.db.execute("UPDATE lexibank_form SET segments='' WHERE id=4")
        self.db.commit()
        with self.assertRaisesRegex(RuntimeError, "no segments"):
            self.run_build()
        self.assertEqual(self.db.execute("SELECT name FROM sqlite_master WHERE name LIKE 'prosody_%'").fetchall(), [])

    def test_wrong_example_detected(self):
        self.run_build()
        self.db.execute("UPDATE prosody_annotation SET example_form_id=2 WHERE language_id=1 AND source_field='form' AND marker='primary_stress'")
        with self.assertRaisesRegex(RuntimeError, "annotations"):
            validate(self.db, lambda _: None)

    def test_source_fingerprint_detects_changes_without_count_changes(self):
        self.run_build()
        self.db.execute("UPDATE lexibank_form SET value='different text' WHERE id=1")
        with self.assertRaisesRegex(RuntimeError, "fingerprint"):
            validate(self.db, lambda _: None)

    def test_mapping_corruption_detected(self):
        self.run_build()
        self.db.execute("DELETE FROM prosody_token_feature WHERE token_id=2")
        with self.assertRaisesRegex(RuntimeError, "feature map"):
            validate(self.db, lambda _: None)

    def test_cli_build_and_standalone_validation(self):
        with tempfile.TemporaryDirectory(prefix="prosody cli ") as folder:
            database, report = Path(folder) / "reference.sqlite", Path(folder) / "report.json"
            disk = sqlite3.connect(database)
            self.db.backup(disk)
            disk.close()
            command = [sys.executable, str(ROOT / "scripts/analysis/build_prosody_evidence.py"),
                       "--database", str(database), "--report", str(report)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(report.read_text())["status"], "passed")
            result = subprocess.run([sys.executable, str(ROOT / "scripts/validation/validate_prosody_evidence.py"),
                                     "--database", str(database)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()

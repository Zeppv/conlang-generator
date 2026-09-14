"""Check milestone compatibility and actual SQL round trips without big datasets."""
import ast
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
EXPORTER = ROOT / "scripts/import/export_reference_to_d1.py"


class ExportTests(unittest.TestCase):
    def run_export(self, milestone):
        source = EXPORTER.read_text(encoding="utf-8")
        table_order = next(ast.literal_eval(node.value) for node in ast.parse(source).body
                           if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "TABLE_ORDER" for t in node.targets))
        tables = [t for t in table_order if (milestone != 43 or not t.startswith("phonotactic_"))
                  and (milestone not in (43, 48, "partial") or not t.startswith("syllable_"))
                  and (milestone in (57, "partial7") or not t.startswith("prosody_"))]
        if milestone == "partial":
            tables.remove("phonotactic_shape")
        if milestone == "partial6":
            tables.remove("syllable_candidate")
        if milestone == "partial7":
            tables.remove("prosody_annotation")
        with tempfile.TemporaryDirectory(prefix="d1-export-test-") as directory:
            root = Path(directory)
            script = root / "scripts/import/export_reference_to_d1.py"
            script.parent.mkdir(parents=True)
            # Exercise real statement splitting with a tiny threshold.
            script.write_text(source.replace("64 * 1024 * 1024", "2048"), encoding="utf-8")
            compiled = root / "data/compiled"
            compiled.mkdir(parents=True)
            db = sqlite3.connect(compiled / "reference.sqlite")
            for table in tables:
                db.execute(f'CREATE TABLE "{table}" (id INTEGER PRIMARY KEY, value TEXT)')
                db.execute(f'INSERT INTO "{table}" VALUES (1, ?)', ("a';\n⁵⁵ + ∼",))
            db.commit()
            db.close()
            result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
            if milestone in ("partial", "partial6", "partial7"):
                self.assertNotEqual(result.returncode, 0)
                self.assertIn({"partial": "phonotactic_shape", "partial6": "syllable_candidate",
                               "partial7": "prosody_annotation"}[milestone], result.stdout)
                self.assertFalse((compiled / "reference-d1.sql").exists())
                return
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            parts = sorted((compiled / "reference-d1-parts").glob("*.sql"))
            self.assertGreater(len(parts), 1)
            self.assertTrue(all(p.stat().st_size <= 2048 for p in parts))
            self.assertEqual(b"".join(p.read_bytes() for p in parts), (compiled / "reference-d1.sql").read_bytes())
            target = sqlite3.connect(":memory:")
            try:
                for part in parts:
                    target.executescript(part.read_text(encoding="utf-8"))
                for table in tables:
                    self.assertEqual(target.execute(f'SELECT * FROM "{table}"').fetchall(), [(1, "a';\n⁵⁵ + ∼")])
            finally:
                target.close()

    def test_prior_43_table_milestone(self):
        self.run_export(43)

    def test_step5_48_table_milestone(self):
        self.run_export(48)

    def test_partial_step5_rejected(self):
        self.run_export("partial")

    def test_step6_52_table_milestone(self):
        self.run_export(52)

    def test_partial_step6_rejected(self):
        self.run_export("partial6")

    def test_step7_57_table_milestone(self):
        self.run_export(57)

    def test_partial_step7_rejected(self):
        self.run_export("partial7")


if __name__ == "__main__":
    unittest.main()

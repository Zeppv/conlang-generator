import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest

from evaluator_fixture import fixture, ROOT
from phonology_evaluator import evaluate
from sync_phonology_web import SCHEMA, digest, prepare, records, sync


class SQLiteClient:
    def __init__(self):
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self.imports = 0
        self.fail = False

    def run(self, sql=None, file=None):
        if file:
            self.imports += 1
            if self.fail:
                raise RuntimeError("Simulated interrupted import")
            self.db.executescript(Path(file).read_text(encoding="utf-8"))
            return []
        if sql == SCHEMA:
            self.db.executescript(sql)
            return []
        cursor = self.db.execute(sql)
        return [dict(row) for row in cursor] if cursor.description else []


def proposals():
    base = {"inventory": ["p", "a", "t"], "words": [["p", "a"], ["t", "a", "p"]],
            "syllable_templates": ["V", "CV", "CVC", "CCV"], "reference_doculect": "northeuralex-eng"}
    changes = [{}, {"inventory_scope": "inventory"}, {"reference_doculect": None},
        {"reference_doculect": "other-eng"}, {"reference_doculect": "no-nucleus"}, {"reference_doculect": "empty"},
        {"inventory": ["p", "a", "t", "mystery"], "words": [["p", "a"], ["p", "t"], ["p", "mystery"]]},
        {"words": [["a"]]}, {"words": []}, {"words": [["mystery", "mystery"]]},
        {"words": [["p", "+", "a"], ["p"]]},
        {"inventory": ["p", "a", "+"], "words": [["p", "t"], ["+", "p"], ["∼"]]},
        {"inventory": ["p", "aː", "⁵"], "words": [["aː", "⁵"]]},
        {"inventory": ["a", "𐀀", "__proto__"], "words": [["𐀀", "a"], ["__proto__", "a"]]},
        {"prosody": {"stress": "none", "tone": "absent", "length_contrast": "absent"}}]
    return [{**base, **change} for change in changes]


class WebTests(unittest.TestCase):
    def setUp(self):
        self.db = fixture()
        self.temp = tempfile.TemporaryDirectory(prefix="phonology-web-")
        self.folder = Path(self.temp.name)

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_export_roundtrip_unicode_and_resume(self):
        package = prepare(self.db, ["northeuralex-eng"], self.folder)
        client = SQLiteClient()
        sync(client, package, lambda *a, **kw: None)
        self.assertEqual(client.db.execute("SELECT snapshot FROM phonology_web_active").fetchone()[0], package["snapshot"])
        imports = client.imports
        sync(client, package, lambda *a, **kw: None)
        self.assertEqual(client.imports, imports)
        for key, expected in records(self.db, ["northeuralex-eng"]):
            payload = "".join(r[0] for r in client.db.execute("SELECT payload FROM phonology_web_chunk WHERE key=? ORDER BY position", (key,)))
            self.assertEqual(json.loads(payload), expected)
            self.assertEqual(digest(payload), package["record_hashes"][key])

    def test_interruption_keeps_active_snapshot_and_resumes(self):
        old = prepare(self.db, ["northeuralex-eng"], self.folder / "old")
        new = prepare(self.db, ["northeuralex-eng", "other-eng"], self.folder / "new")
        client = SQLiteClient()
        sync(client, old, lambda *a, **kw: None)
        client.fail = True
        with self.assertRaisesRegex(RuntimeError, "interrupted"):
            sync(client, new, lambda *a, **kw: None)
        self.assertEqual(client.db.execute("SELECT snapshot FROM phonology_web_active").fetchone()[0], old["snapshot"])
        client.fail = False
        sync(client, new, lambda *a, **kw: None)
        self.assertEqual(tuple(client.db.execute("SELECT snapshot,previous_snapshot FROM phonology_web_active").fetchone()), (new["snapshot"], old["snapshot"]))

    def test_corrupt_catalog_not_activated(self):
        package = prepare(self.db, ["northeuralex-eng"], self.folder)
        client = SQLiteClient()
        client.run(sql=SCHEMA)
        for part in package["parts"]:
            client.run(file=part["path"])
        client.db.execute("UPDATE phonology_web_chunk SET payload=replace(payload,'English','Englixh') WHERE key='catalog'")
        with self.assertRaisesRegex(RuntimeError, "verification failed"):
            sync(client, package, lambda *a, **kw: None)
        self.assertEqual(client.db.execute("SELECT COUNT(*) FROM phonology_web_active").fetchone()[0], 0)

    def test_unknown_doculect_and_stale_build_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown exact"):
            prepare(self.db, ["English"], self.folder)
        self.db.execute("UPDATE syllable_analysis SET form_count=form_count+1")
        with self.assertRaisesRegex(RuntimeError, "counts differ"):
            prepare(self.db, ["northeuralex-eng"], self.folder)

    def test_non_catalog_corruption_and_missing_chunks_are_repairable(self):
        for corruption in ("UPDATE phonology_web_chunk SET checksum='bad' WHERE key='tokens'",
                           "DELETE FROM phonology_web_chunk WHERE key='tokens'"):
            with self.subTest(corruption=corruption):
                package = prepare(self.db, ["northeuralex-eng"], self.folder)
                client = SQLiteClient()
                sync(client, package, lambda *a, **kw: None)
                client.db.execute(corruption)
                with self.assertRaises(RuntimeError):
                    sync(client, package, lambda *a, **kw: None)
                self.assertEqual(client.db.execute("SELECT COUNT(*) FROM phonology_web_part").fetchone()[0], 0)
                sync(client, package, lambda *a, **kw: None)

    def test_deterministic_package_and_no_source_writes(self):
        before = self.db.total_changes
        a = prepare(self.db, ["other-eng", "northeuralex-eng"], self.folder / "a")
        b = prepare(self.db, ["northeuralex-eng", "other-eng"], self.folder / "b")
        self.assertEqual(a["snapshot"], b["snapshot"])
        self.assertEqual([p["checksum"] for p in a["parts"]], [p["checksum"] for p in b["parts"]])
        self.assertEqual(before, self.db.total_changes)

    def test_python_typescript_parity(self):
        payload = {"records": dict(records(self.db, ["northeuralex-eng", "other-eng", "empty", "no-nucleus"])),
                   "cases": [{"input": p, "expected": evaluate(self.db, p)} for p in proposals()]}
        path = self.folder / "parity.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        result = subprocess.run(["node", str(ROOT / "tests/phonology-parity.ts"), str(path)], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()

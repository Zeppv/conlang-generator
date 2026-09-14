"""Developer integration check: real local D1, Worker handlers, and Python parity.

Uses an isolated Wrangler state directory, never the user's local application DB.
"""
import json
from pathlib import Path
import subprocess
import tempfile

from evaluator_fixture import fixture, ROOT
from phonology_evaluator import evaluate
from sync_phonology_web import prepare, sync, Wrangler
from test_phonology_web import proposals


def run(db, cases, doculects):
    with tempfile.TemporaryDirectory(prefix="phonology-d1-") as temporary:
        folder = Path(temporary)
        package = prepare(db, doculects, folder / "sql")
        print(f"Serving payload: {package['payload_bytes'] / 1024 / 1024:.2f} MiB / {len(package['parts'])} SQL parts", flush=True)
        client = Wrangler("conlang-reference", folder / "state")
        sync(client, package)
        # A harmless semantic fixture verifies the existing handlers alongside
        # the new phonology routes, without requiring the full semantic corpus.
        client.run(sql="""
            CREATE TABLE concept(id INTEGER PRIMARY KEY,concepticon_id TEXT,gloss TEXT,definition TEXT,semantic_field TEXT,ontological_category TEXT);
            INSERT INTO concept VALUES(1,'1','MOUNTAIN','A mountain','Landscape','Object'),(2,'2','HILL','A hill','Landscape','Object');
            CREATE TABLE concept_relation(source_concept_id INTEGER,target_concept_id INTEGER,relation_type TEXT,source_id TEXT,language_count INTEGER,family_count INTEGER);
            INSERT INTO concept_relation VALUES(1,2,'related','concepticon',NULL,NULL);
        """)
        client.close()
        path = folder / "cases.json"
        path.write_text(json.dumps({"snapshot": package["snapshot"], "cases": [{"input": p, "expected": evaluate(db, p)} for p in cases]}, ensure_ascii=False), encoding="utf-8")
        result = subprocess.run(["node", str(ROOT / "tests/phonology-api.ts"), str(folder / "state/v3"), str(path)], cwd=ROOT)
        if result.returncode:
            raise RuntimeError("D1 API/parity integration failed")
        client = Wrangler("conlang-reference", folder / "state")
        try:
            sync(client, package)  # exercise the actual Wrangler repair path
            sync(client, package)  # then the receipts/resume path
        finally:
            client.close()
        print("LOCAL D1 + WORKER INTEGRATION PASSED", flush=True)


if __name__ == "__main__":
    conn = fixture()
    try:
        run(conn, proposals(), ["northeuralex-eng", "other-eng", "empty", "no-nucleus"])
    finally:
        conn.close()

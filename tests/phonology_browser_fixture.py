"""Small source-derived reports for the browser-only interaction test."""
import json
import sys
from evaluator_fixture import fixture
from phonology_evaluator import evaluate, query

db = fixture()
try:
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        print(json.dumps({"ready": True, "doculects": query(db, "SELECT id,lexibank_id,name,glottocode FROM lexibank_language")}))
    else:
        print(json.dumps(evaluate(db, json.load(sys.stdin)), ensure_ascii=False))
finally:
    db.close()

import copy
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/analysis"))
from semantic_root_planner import PlanningError, build_plan, fingerprint, plan, replay
from plan_semantic_roots import demo_request


def fixture(path=":memory:"):
    db = sqlite3.connect(path)
    for schema in ("001_reference.sql", "003_datsemshift.sql", "004_semantic_scores.sql"):
        db.executescript((ROOT / "database/schema" / schema).read_text())
    for name in ("concepticon", "clics", "datsemshift", "wordnet"):
        db.execute("INSERT INTO reference_source VALUES (?, ?, 'fixture-only', 'test', 'fixture')", (name, name))
    for i, gloss in enumerate(("MOON", "MONTH", "SUN", "DAY", "WATER", "RAIN", "FIRE"), 1):
        db.execute("INSERT INTO concept (id, concepticon_id, gloss, source_id) VALUES (?, ?, ?, 'concepticon')",
                   (i, f"fixture-{i}", gloss))
    for a, b, colex, derivation, lexical in [(1, 2, .9, .1, .9), (3, 4, .1, .8, .8), (1, 3, 0, 0, 1), (2, 7, .95, 0, .95)]:
        db.execute("INSERT INTO semantic_pair_score VALUES (?, ?, .9, ?, ?, ?, 0, .9, 'clics,wordnet')",
                   (a, b, lexical, colex, derivation))
    db.execute("INSERT INTO semantic_direction_score VALUES (5, 6, .85, 0, .85, 4, 'datsemshift')")
    db.execute("INSERT INTO concept_relation (id, source_concept_id, target_concept_id, relation_type, family_count, source_id, source_record_id) VALUES (11, 1, 2, 'colexification', 8, 'clics', 'fixture-row-1')")
    db.commit()
    return db


def request(**changes):
    return {"version": "1.0.0", "project_id": "test-language", "seed": "one",
            "concept_ids": list(range(1, 8)), "minimum_support": .55, "overrides": [], **changes}


def override(target, kind, bases=()):
    return {"concept_id": target, "kind": kind, "bases": list(bases), "reason": "Deliberate test-language choice."}


class RootPlannerTests(unittest.TestCase):
    def setUp(self):
        self.db = fixture()

    def tearDown(self):
        self.db.close()

    def test_direct_evidence_distinguishes_lexical_choices(self):
        result = plan(self.db, request())
        entries = {row["concept_id"]: row for row in result["entries"]}
        self.assertEqual(entries[2]["kind"], "colexification")
        self.assertEqual(entries[1]["lexeme_id"], entries[2]["lexeme_id"])
        self.assertEqual(entries[1]["root_ids"], entries[2]["root_ids"])
        self.assertEqual(entries[4]["kind"], "shared_root")
        self.assertEqual(entries[3]["root_ids"], entries[4]["root_ids"])
        self.assertNotEqual(entries[3]["lexeme_id"], entries[4]["lexeme_id"])
        self.assertEqual(entries[3]["family_id"], entries[4]["family_id"])
        self.assertEqual(entries[6]["kind"], "derivation")
        self.assertEqual(entries[6]["root_ids"], entries[5]["root_ids"])
        self.assertNotEqual(entries[6]["lexeme_id"], entries[5]["lexeme_id"])
        self.assertFalse(result["surface_forms_assigned"])
        self.assertEqual(entries[3]["kind"], "separate")  # High general relatedness is not morphology.

    def test_no_transitive_colexification(self):
        result = plan(self.db, request())
        self.assertEqual(result["entries"][6]["kind"], "separate")  # 2–7 does not imply 1–7.
        self.db.execute("INSERT INTO semantic_pair_score VALUES (1, 7, .9, .9, .9, 0, 0, 0, 'clics')")
        result = plan(self.db, request())
        self.assertEqual(result["entries"][6]["kind"], "separate")  # Automatic colex groups are bounded to a pair.

    def test_direction_is_not_reversed_or_inferred_from_shift(self):
        self.db.execute("DELETE FROM semantic_direction_score")
        self.db.execute("INSERT INTO semantic_direction_score VALUES (6, 5, .99, .99, 0, 4, 'datsemshift')")
        result = plan(self.db, request())
        self.assertEqual(result["entries"][5]["kind"], "separate")
        self.assertFalse(any(row["kind"] == "derivation" for row in result["entries"]))

    def test_unknown_evidence_and_provenance_are_preserved(self):
        result = plan(self.db, request())
        absent = next(e for e in result["evidence"] if e["concept_ids"] == [1, 5])
        self.assertIsNone(absent["pair_score"])
        self.assertEqual(absent["pair_status"], "unknown")
        present = next(e for e in result["evidence"] if e["concept_ids"] == [1, 2])
        self.assertEqual(present["relation_ids"], [11])
        self.assertEqual(result["evidence_snapshot"]["relations"][0]["source_record_id"], "fixture-row-1")
        self.assertTrue(all(e["confidence"]["calibrated_probability"] is None for e in result["entries"]))

    def test_reproducible_order_independent_and_database_independent(self):
        first = plan(self.db, request())
        self.assertEqual(first, plan(self.db, request(concept_ids=list(reversed(range(1, 8))))))
        self.db.execute("DELETE FROM semantic_pair_score")
        self.assertEqual(first, replay(json.loads(json.dumps(first))))
        self.assertNotEqual(first["evidence_fingerprint"], plan(self.db, request())["evidence_fingerprint"])

    def test_gloss_changes_do_not_change_lexical_identity(self):
        first = plan(self.db, request())
        self.db.execute("UPDATE concept SET gloss = 'NEW LABEL' WHERE id = 1")
        second = plan(self.db, request())
        self.assertEqual(first["roots"], second["roots"])
        self.assertEqual([e["lexeme_id"] for e in first["entries"]], [e["lexeme_id"] for e in second["entries"]])

    def test_overrides_gaps_and_ordered_compounds_survive_replay(self):
        chosen = [override(2, "separate"), override(7, "gap"), override(4, "compound", [5, 3])]
        result = plan(self.db, request(overrides=chosen))
        self.assertEqual(replay(result), result)
        entries = result["entries"]
        self.assertEqual(entries[1]["kind"], "separate")
        self.assertIsNone(entries[6]["lexeme_id"])
        self.assertEqual(entries[6]["root_ids"], [])
        self.assertEqual(entries[3]["bases"], [5, 3])
        self.assertEqual(entries[3]["root_ids"], ["test-language:root:c3", "test-language:root:c5"])
        self.assertNotEqual(entries[2]["family_id"], entries[4]["family_id"])
        self.assertEqual(entries[3]["origin"], "user_override")
        self.assertTrue(entries[3]["alternatives"])

    def test_override_without_evidence_is_explicit(self):
        result = plan(self.db, request(overrides=[override(7, "derivation", [1])]))
        row = result["entries"][6]
        self.assertEqual(row["origin"], "user_override")
        self.assertIsNone(row["confidence"]["support"])
        self.assertEqual(row["bases"], [1])

    def test_cycles_missing_bases_and_invalid_colexification_fail(self):
        cases = [
            ([override(1, "derivation", [2]), override(2, "derivation", [1])], "cyclic"),
            ([override(1, "gap"), override(2, "derivation", [1])], "gap"),
            ([override(2, "derivation", [1]), override(7, "colexification", [2])], "root-bearing"),
            ([override(2, "compound", [1, 1])], "distinct"),
            ([override(2, "colexification", [99])], "selected"),
            ([override(4, "compound", [1, 3]), override(7, "shared_root", [4])], "single root family"),
        ]
        for overrides, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(PlanningError, message):
                plan(self.db, request(overrides=overrides))

    def test_strict_request_validation(self):
        for changes in ({"concept_ids": [True]}, {"concept_ids": [1, 1]}, {"concept_ids": []},
                        {"concept_ids": list(range(1, 66))}, {"minimum_support": float("nan")},
                        {"minimum_support": 0}, {"extra": 1}, {"seed": 1}, {"version": "2"},
                        {"project_id": ""}, {"concept_ids": [999]}):
            with self.subTest(changes=changes), self.assertRaises(PlanningError):
                plan(self.db, request(**changes))

    def test_corrupt_plan_and_snapshot_fail(self):
        original = plan(self.db, request())
        bad = copy.deepcopy(original)
        bad["entries"][0]["reason"] = "Changed without replay"
        with self.assertRaisesRegex(PlanningError, "deterministic replay"):
            replay(bad)
        bad = copy.deepcopy(original)
        bad["evidence_snapshot"]["pairs"][0]["colexification_score"] = .01
        with self.assertRaisesRegex(PlanningError, "fingerprint"):
            replay(bad)
        bad["evidence_snapshot"]["pairs"][0]["colexification_score"] = -1
        bad["evidence_fingerprint"] = fingerprint(bad["evidence_snapshot"])
        with self.assertRaisesRegex(PlanningError, "score"):
            replay(bad)

    def test_saved_evidence_supports_revised_overrides(self):
        saved = plan(self.db, request())
        revised_request = copy.deepcopy(saved["request"])
        revised_request["overrides"] = [override(2, "separate")]
        revised = build_plan(saved["evidence_snapshot"], revised_request)
        self.assertEqual(revised["evidence_fingerprint"], saved["evidence_fingerprint"])
        self.assertNotEqual(revised["plan_id"], saved["plan_id"])
        self.assertEqual(replay(revised), revised)
        self.assertEqual(revised["entries"][0]["owned_root_id"], saved["entries"][0]["owned_root_id"])

    def test_read_only_sql_contract(self):
        def authorizer(action, arg1, arg2, database, trigger):
            if action not in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ):
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        self.db.set_authorizer(authorizer)
        result = plan(self.db, request())
        self.assertEqual(len(result["entries"]), 7)

    def test_demo_never_guesses_ambiguous_glosses(self):
        self.assertEqual(demo_request(self.db)["concept_ids"], list(range(1, 8)))
        self.db.execute("INSERT INTO concept (id, gloss, source_id) VALUES (8, 'MOON', 'concepticon')")
        with self.assertRaisesRegex(PlanningError, "2 matches"):
            demo_request(self.db)

    def test_cli_generate_replay_and_revise_without_database(self):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            database, saved = temp / "reference.sqlite", temp / "plan.json"
            db = fixture(database)
            db.close()
            before = database.read_bytes()
            command = [sys.executable, str(ROOT / "scripts/analysis/plan_semantic_roots.py")]
            result = subprocess.run(command + ["--demo", "--database", str(database), "--output", str(saved)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(before, database.read_bytes())
            original = json.loads(saved.read_text())
            database.unlink()
            replayed = temp / "replayed.json"
            result = subprocess.run(command + ["--from-plan", str(saved), "--output", str(replayed)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(saved.read_bytes(), replayed.read_bytes())
            req = temp / "request.json"
            new_request = copy.deepcopy(original["request"])
            new_request["overrides"] = [override(2, "separate")]
            req.write_text(json.dumps(new_request))
            result = subprocess.run(command + ["--from-plan", str(saved), "--request", str(req), "--output", str(replayed)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(replayed.read_text())["entries"][1]["kind"], "separate")
            self.assertEqual(json.loads(saved.read_text()), original)
            exported = temp / "exported-request.json"
            result = subprocess.run(command + ["--from-plan", str(saved), "--output", str(replayed),
                                               "--request-output", str(exported)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(exported.read_text()), original["request"])
            result = subprocess.run(command + ["--from-plan", str(saved), "--output", str(saved)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(json.loads(saved.read_text()), original)


if __name__ == "__main__":
    unittest.main()

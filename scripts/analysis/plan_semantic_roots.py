"""Create, replay, or revise a semantic root plan without rebuilding reference data."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "analysis"))
from semantic_root_planner import VERSION, PlanningError, build_plan, plan, replay, review_text


def read_json(path):
    if path.stat().st_size > 16 * 1024 * 1024:
        raise PlanningError("JSON input exceeds 16 MiB")

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise PlanningError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def constant(value):
        raise PlanningError(f"invalid JSON constant: {value}")

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs, parse_constant=constant)


def demo_request(connection):
    ids = []
    for gloss in ("MOON", "MONTH", "SUN", "DAY", "WATER", "RAIN", "FIRE"):
        rows = connection.execute("SELECT id FROM concept WHERE gloss = ? COLLATE NOCASE", (gloss,)).fetchall()
        if len(rows) != 1:
            raise PlanningError(f"demo gloss {gloss!r} has {len(rows)} matches; use an explicit --request with concept_ids")
        ids.append(rows[0][0])
    return {"version": VERSION, "project_id": "first-language", "seed": "root-plan-demo",
            "concept_ids": ids, "minimum_support": 0.55, "overrides": []}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", help="Resolve seven exact glosses in your existing database")
    parser.add_argument("--request", type=Path, help="Versioned request with explicit internal concept IDs")
    parser.add_argument("--from-plan", type=Path, help="Replay saved evidence; add --request to revise choices")
    parser.add_argument("--database", type=Path, default=ROOT / "data/compiled/reference.sqlite")
    parser.add_argument("--output", type=Path, default=ROOT / "data/compiled/semantic-root-plan.json")
    parser.add_argument("--request-output", type=Path, help="Also save the normalized request for editing overrides")
    args = parser.parse_args()
    if args.demo and (args.request or args.from_plan):
        parser.error("--demo cannot be combined with --request or --from-plan")
    if not (args.demo or args.request or args.from_plan):
        parser.error("provide --demo, --request, or --from-plan")
    output = args.output.resolve()
    protected = {p.resolve() for p in (args.request, args.from_plan, args.database) if p is not None}
    raw = (ROOT / "data/raw").resolve()
    outputs = [output] + ([args.request_output.resolve()] if args.request_output else [])
    if len(set(outputs)) != len(outputs) or any(
            path in protected or path.suffix.lower() != ".json" or path.is_relative_to(raw) for path in outputs):
        parser.error("outputs must be separate .json files outside data/raw, not inputs or database")
    try:
        request = read_json(args.request) if args.request else None
        if args.from_plan:
            saved = replay(read_json(args.from_plan))
            if request is not None and request.get("project_id") != saved["request"]["project_id"]:
                raise PlanningError("keep project_id when revising a saved plan to preserve identities")
            result = build_plan(saved["evidence_snapshot"], request) if request is not None else saved
        else:
            connection = sqlite3.connect(args.database.resolve().as_uri() + "?mode=ro", uri=True)
            try:
                connection.execute("BEGIN")
                result = plan(connection, demo_request(connection) if args.demo else request)
            finally:
                connection.close()
        encoded = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if len(encoded.encode("utf-8")) > 16 * 1024 * 1024:
            raise PlanningError("saved plan exceeds 16 MiB; select fewer concepts")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded, encoding="utf-8")
        if args.request_output:
            args.request_output.parent.mkdir(parents=True, exist_ok=True)
            args.request_output.write_text(json.dumps(result["request"], indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, sqlite3.Error, KeyError, TypeError, RecursionError) as error:
        parser.error(str(error))
    print(review_text(result))
    print(f"Saved: {output}")
    print("Reference database and D1 were not modified.")


if __name__ == "__main__":
    main()

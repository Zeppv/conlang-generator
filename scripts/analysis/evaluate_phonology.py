"""Evaluate a JSON sound-system proposal without modifying the reference DB."""
import argparse
import json
from pathlib import Path
import sqlite3
import time

from phonology_evaluator import evaluate

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--demo", action="store_true")
    source.add_argument("--input", type=Path)
    parser.add_argument("--database", type=Path, default=ROOT / "data/compiled/reference.sqlite")
    parser.add_argument("--output", type=Path, default=ROOT / "data/compiled/phonology-evaluation.json")
    args = parser.parse_args()
    proposal_file = ROOT / "examples/phonology-proposal.json" if args.demo else args.input
    if args.output.resolve() in (args.database.resolve(), proposal_file.resolve()) or args.output.suffix.lower() != ".json":
        parser.error("output must be a separate .json report, not the database or input")
    if proposal_file.stat().st_size > 1024 * 1024:
        parser.error("Proposal JSON exceeds the 1 MiB limit")
    started = time.monotonic()
    conn = sqlite3.connect(args.database.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        conn.execute("BEGIN")
        report = evaluate(conn, json.loads(proposal_file.read_text(encoding="utf-8")))
    finally:
        conn.close()
    report["elapsed_seconds"] = round(time.monotonic() - started, 3)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    print("PHONOLOGY EVALUATION COMPLETE")
    print(f"Model consistency: {'valid' if report['model_consistency']['valid'] else 'issues found'}")
    print(f"PHOIBLE mapping: {report['inventory']['mapped_tokens']}/{report['inventory']['requested_tokens']} tokens")
    print(f"Reference doculect: {report['reference_doculect']['lexibank_id'] if report['reference_doculect'] else 'not selected'}")
    print(f"Report: {args.output}\nReference database and D1 were not modified.")


if __name__ == "__main__":
    main()

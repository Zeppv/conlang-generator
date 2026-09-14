"""Generate a seeded inventory and word forms without modifying reference data."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys
import time


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "analysis"))

from phonology_evaluator import evaluate  # noqa: E402
from phonology_generator import GenerationError, generate  # noqa: E402
from phonology_specification import SoundSystemSpecification, SpecificationError  # noqa: E402


EXAMPLE_SPEC = ROOT / "examples" / "sound-system-specification.json"
EXAMPLE_REQUEST = ROOT / "examples" / "phonology-generation-request.json"
DEFAULT_DATABASE = ROOT / "data" / "compiled" / "reference.sqlite"
DEFAULT_OUTPUT = ROOT / "data" / "compiled" / "phonology-generation.json"
MAXIMUM_BYTES = 1024 * 1024


def no_duplicate_keys(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"Duplicate JSON object key in request: {key!r}")
        value[key] = item
    return value


def read_json(path, label):
    if not path.is_file():
        raise FileNotFoundError(f"Could not find {label}: {path}")
    if path.stat().st_size > MAXIMUM_BYTES:
        raise ValueError(f"{label} exceeds the 1 MiB limit")
    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=no_duplicate_keys,
        parse_constant=lambda constant: (_ for _ in ()).throw(
            ValueError(f"Invalid JSON constant in request: {constant}")),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", help="Use both bundled example files")
    parser.add_argument("--specification", type=Path)
    parser.add_argument("--request", type=Path)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.demo and (args.specification or args.request):
        parser.error("--demo cannot be combined with --specification or --request")
    if not args.demo and (args.specification is None or args.request is None):
        parser.error("provide --demo or both --specification and --request")
    spec_path = EXAMPLE_SPEC if args.demo else args.specification
    request_path = EXAMPLE_REQUEST if args.demo else args.request
    protected = {spec_path.resolve(), request_path.resolve(), args.database.resolve()}
    if args.output.resolve() in protected or args.output.suffix.lower() != ".json":
        parser.error("output must be a separate .json file, not an input or database")

    started = time.monotonic()
    try:
        specification = SoundSystemSpecification.from_json(
            spec_path.read_text(encoding="utf-8"))
        request = read_json(request_path, "generation request")
        connection = sqlite3.connect(
            args.database.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            connection.execute("BEGIN")
            report = generate(connection, specification, request, evaluate)
        finally:
            connection.close()
    except (OSError, ValueError, SpecificationError, GenerationError,
            sqlite3.Error, RuntimeError) as error:
        parser.error(str(error))

    report["elapsed_seconds"] = round(time.monotonic() - started, 3)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    counts = report["inventory"]["counts"]
    print("\n=============================================")
    print("PHONOLOGY GENERATION COMPLETE")
    print("=============================================\n")
    print(f"Consonants:      {counts['consonants']}")
    print(f"Vowels:          {counts['vowels']}")
    print(f"Tones:           {counts['tones']}")
    print(f"Forms:           {len(report['forms'])}")
    print(f"Hard-rule check: {'valid' if report['hard_rule_validation']['valid'] else 'FAILED'}")
    print(f"Evidence gaps:   {len(report['evidence']['gaps'])}")
    print(f"Report:          {args.output}")
    print("Reference database and D1 were not modified.")


if __name__ == "__main__":
    main()

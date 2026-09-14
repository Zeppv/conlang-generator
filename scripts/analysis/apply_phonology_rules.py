"""Apply bounded Step 12 rules to an existing Step 11 generation report."""
import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "analysis"))

from phonology_rules import PhonologyRuleSet, RuleError, apply_rules  # noqa: E402
from phonology_specification import SoundSystemSpecification, SpecificationError  # noqa: E402


EXAMPLE_SPEC = ROOT / "examples" / "sound-system-specification.json"
EXAMPLE_RULES = ROOT / "examples" / "phonology-rules.json"
DEFAULT_GENERATION = ROOT / "data" / "compiled" / "phonology-generation.json"
DEFAULT_OUTPUT = ROOT / "data" / "compiled" / "phonology-realization.json"
MAXIMUM_BYTES = 8 * 1024 * 1024


def read_json(path, label):
    if not path.is_file():
        raise FileNotFoundError(f"Could not find {label}: {path}")
    if path.stat().st_size > MAXIMUM_BYTES:
        raise ValueError(f"{label} exceeds the 8 MiB limit")
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--specification", type=Path, default=EXAMPLE_SPEC)
    parser.add_argument("--rules", type=Path, default=EXAMPLE_RULES)
    parser.add_argument("--generation", type=Path, default=DEFAULT_GENERATION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    protected = {
        args.specification.resolve(), args.rules.resolve(),
        args.generation.resolve(),
    }
    if args.output.resolve() in protected or args.output.suffix.lower() != ".json":
        parser.error("output must be a separate .json file")
    try:
        specification = SoundSystemSpecification.from_json(
            args.specification.read_text(encoding="utf-8"))
        rules = PhonologyRuleSet(
            specification, read_json(args.rules, "rule set"))
        generation = read_json(args.generation, "generation report")
        report = apply_rules(specification, rules, generation)
    except (OSError, ValueError, SpecificationError, RuleError) as error:
        parser.error(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print("\n=============================================")
    print("PHONOLOGY RULE APPLICATION COMPLETE")
    print("=============================================\n")
    print(f"Forms realized: {len(report['forms'])}")
    print(f"Rule set:       {rules.to_dict()['name']}")
    print(f"Fingerprint:    {rules.fingerprint}")
    print(f"Report:         {args.output}")
    print("Reference database and D1 were not modified.")


if __name__ == "__main__":
    main()

"""Apply bounded Step 12 rules to an existing Step 11 generation report."""
import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "analysis"))

from phonology_rules import PhonologyRuleSet, RuleError, apply_rules  # noqa: E402
from phonology_specification import SoundSystemSpecification, SpecificationError  # noqa: E402
from phonology_workspace import realize_bundle, workspace_bundle  # noqa: E402


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
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"{label}: duplicate JSON key {key}")
            result[key] = value
        return result
    def invalid_constant(value):
        raise ValueError(f"{label}: invalid JSON constant {value}")
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_keys,
                      parse_constant=invalid_constant)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--specification", type=Path, default=EXAMPLE_SPEC)
    parser.add_argument("--rules", type=Path, default=EXAMPLE_RULES)
    parser.add_argument("--generation", type=Path, default=DEFAULT_GENERATION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--bundle", type=Path, help="Reproduce an exported website run")
    parser.add_argument("--bundle-output", type=Path, help="Write portable website inputs and result")
    args = parser.parse_args()
    protected = {
        args.specification.resolve(), args.rules.resolve(),
        args.generation.resolve(),
    }
    if args.bundle:
        protected.add(args.bundle.resolve())
    if args.bundle_output and (args.bundle_output.resolve() in protected or
            args.bundle_output.resolve() == args.output.resolve() or args.bundle_output.suffix.lower() != ".json"):
        parser.error("bundle output must be a separate .json file")
    if args.output.resolve() in protected or args.output.suffix.lower() != ".json":
        parser.error("output must be a separate .json file")
    try:
        if args.bundle:
            bundle = realize_bundle(read_json(args.bundle, "workspace bundle"))
            report = bundle["report"]
        else:
            specification = SoundSystemSpecification(read_json(args.specification, "specification"))
            rules = PhonologyRuleSet(specification, read_json(args.rules, "rule set"))
            generation = read_json(args.generation, "generation report")
            report = apply_rules(specification, rules, generation)
            bundle = workspace_bundle(specification, rules, generation, report)
        bundle_text = json.dumps(bundle, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if len(bundle_text.encode("utf-8")) > MAXIMUM_BYTES:
            raise ValueError("workspace bundle exceeds the 8 MiB limit")
    except (OSError, ValueError, SpecificationError, RuleError) as error:
        parser.error(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    if args.bundle_output:
        args.bundle_output.parent.mkdir(parents=True, exist_ok=True)
        args.bundle_output.write_text(bundle_text, encoding="utf-8")
    print("\n=============================================")
    print("PHONOLOGY RULE APPLICATION COMPLETE")
    print("=============================================\n")
    print(f"Forms realized: {len(report['forms'])}")
    print(f"Rule set:       {bundle['rules']['name']}")
    print(f"Fingerprint:    {report['rule_set_fingerprint']}")
    print(f"Report:         {args.output}")
    if args.bundle_output:
        print(f"Website bundle: {args.bundle_output}")
    print("Reference database and D1 were not modified.")


if __name__ == "__main__":
    main()

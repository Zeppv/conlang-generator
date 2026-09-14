"""Validate and canonicalize a Step 10 sound-system specification."""
import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "analysis"))

from phonology_specification import SoundSystemSpecification, SpecificationError  # noqa: E402


EXAMPLE = ROOT / "examples" / "sound-system-specification.json"
DEFAULT_OUTPUT = ROOT / "data" / "compiled" / "sound-system-specification.json"
MAXIMUM_BYTES = 1024 * 1024


def read_specification(path):
    if not path.is_file():
        raise FileNotFoundError(f"Could not find specification: {path}")
    if path.stat().st_size > MAXIMUM_BYTES:
        raise SpecificationError("Specification JSON exceeds the 1 MiB limit")
    return SoundSystemSpecification.from_json(path.read_text(encoding="utf-8"))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Validate and canonicalize an executable sound-system specification.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="Input JSON specification")
    source.add_argument("--demo", action="store_true", help="Use the bundled example")
    parser.add_argument("--output", type=Path,
                        help="Canonical JSON output; demo defaults to data/compiled")
    parser.add_argument("--check", action="store_true",
                        help="Validate without writing an output file")
    parser.add_argument("--preview-words", type=int, default=5,
                        help="Number of deterministic word-shape decisions to preview")
    args = parser.parse_args(argv)

    if args.check and args.output:
        parser.error("--check and --output cannot be used together")
    input_path = EXAMPLE if args.demo else args.input
    output_path = None if args.check else (args.output or (DEFAULT_OUTPUT if args.demo else None))
    if output_path is None and not args.check:
        parser.error("custom input requires --output or --check")

    try:
        specification = read_specification(input_path.resolve())
        preview = specification.decision_preview(args.preview_words)
        if output_path is not None:
            output_path = output_path.resolve()
            if output_path == input_path.resolve():
                raise SpecificationError("Output must be separate from the input file")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(specification.to_json(), encoding="utf-8")
    except (OSError, SpecificationError) as error:
        parser.error(str(error))

    print("\n=============================================")
    print("SOUND-SYSTEM SPECIFICATION VALID")
    print("=============================================\n")
    print(f"Name:                  {specification.to_dict()['name']}")
    print(f"Specification version: {specification.to_dict()['specification_version']}")
    print(f"Model version:         {specification.to_dict()['model_version']}")
    print(f"Fingerprint:           {specification.fingerprint}")
    if output_path is not None:
        print(f"Canonical output:      {output_path}")
    print("\nDeterministic decision preview:")
    print(json.dumps(preview, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

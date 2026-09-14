# Executable sound-system specification — Step 10

Step 10 defines the construction contract that Step 11 will use. It does not
generate an inventory or words yet, and it does not turn reference frequency
into a prohibition. The specification is JSON, validated with Python's standard
library, and independent of SQLite and D1.

## Run the bundled example

```bat
python scripts\analysis\define_sound_system.py --demo
```

This validates `examples/sound-system-specification.json`, writes a canonical
copy to `data/compiled/sound-system-specification.json`, and prints a short
deterministic decision preview. It does not read or modify the linguistic
database, rebuild an analysis, or invoke Wrangler.

Focused tests:

```bat
python -m unittest discover -s tests -p "test_phonology_specification.py" -v
```

Custom specification:

```bat
python scripts\analysis\define_sound_system.py --input my-sound-system.json --output my-sound-system.normalized.json
```

Use `--check` instead of `--output` to validate without writing. Input and
output paths must differ.

## Contract

The top-level `specification_version` and `model_version` are required and
currently fixed at `1.0.0` and `phonology-v1-step10`. Unknown fields fail
rather than being silently ignored.

- `phonemes` assigns every sound a stable ID, IPA display token, class, feature
  map, and explicit mapping status. Mapped, ambiguous, unmapped, and
  user-defined sounds remain distinguishable.
- `classes` is an exact declared partition of the phoneme IDs. The current
  construction model requires at least one vowel but does not require a
  consonant.
- `construction` contains hard rules: allowed onset/coda ID sequences,
  single-nucleus `C*VC*` templates, normalized template and syllable-count
  weights, component/word-boundary behavior, and policies for special or
  unknown tokens.
- `prosody` records user declarations separately from evidence. A non-unknown
  setting must say it was user-declared. Fixed stress also requires an initial
  or final position. Unknown remains a real stored state.
- `extensions` reserves separate allophony, vowel-harmony, and
  consonant-harmony sections. Version 1 records unknown, explicit-none, or
  deferred status but rejects invented executable rules until Step 12 defines
  those rule languages.
- `evidence` stores descriptive build/report references only. The construction
  code never reads it as a hard rule.
- `provenance` identifies user choices, engineering defaults, and
  evidence-informed defaults without treating those categories as equivalent.

Allowed onset/coda sequences use stable phoneme IDs, not IPA display strings.
Every template must have at least one compatible onset and coda choice. Duplicate
IDs, IPA tokens, clusters, templates, and weight choices fail clearly. Structural
tokens cannot also be inventory phonemes.

## Normalization and reproducibility

Positive weights are normalized in stable key order to twelve decimal places;
the last value closes the total to exactly 1 in the canonical representation.
Parsing a canonical JSON output and serializing it again retains the same data
and fingerprint.

Seeded decisions use SHA-256 over specification version, model version, seed,
decision namespace, and decision index. They do not depend on Python's global
random state. The same canonical specification, version, seed, namespace, and
index therefore reproduce the same syllable-count and template decisions.

The preview proves that deterministic decision layer only. Step 11 will add
inventory and form generation, required/excluded sounds, bounded retries, and
construction-rule checks. Step 12 will define supported prosodic, allophonic,
and harmony rule execution.

## Evidence is not enforcement

Step 8/9 evidence reports can be referenced by ID and fingerprint, but no
prevalence, co-occurrence, adjacency, syllable-candidate, or prosody annotation
is automatically promoted into `construction`. A low reference frequency
therefore cannot silently forbid a sound or sequence.

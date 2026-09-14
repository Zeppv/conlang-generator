# Seeded inventory and word-form generation — Step 11

Step 11 is the first actual phonology generator. It consumes the validated
Step 10 specification, reads existing PHOIBLE/Lexibank analysis tables through
a read-only SQLite connection, and writes one JSON generation report. It does
not rebuild reference data or import D1.

## Run the bundled demonstration

```bat
python scripts\analysis\generate_phonology.py --demo
```

Expected banner: `PHONOLOGY GENERATION COMPLETE`. The report is written to
`data/compiled/phonology-generation.json`.

Focused tests:

```bat
python -m unittest discover -s tests -p "test_phonology_generator.py" -v
```

## Generation request

The bundled `examples/phonology-generation-request.json` demonstrates every
field. Consonant, vowel and optional tone targets are exact. Required IDs must
appear and excluded IDs cannot appear. A target below its required count or
above the remaining candidate pool fails before generation.

`component_count_weights` controls how many independently generated components
a word receives. Components are separated with the Step 10 boundary token.
Construction always resets at that boundary: no syllable or cluster spans it.
`duplicate_policy` is `reject` or `allow`; rejection is bounded by
`maximum_attempts_per_word`, so constrained requests terminate with an
explanation rather than looping.

## Evidence-guided inventory proposals

Inventory choices use exact PHOIBLE prevalence, stored pair evidence and a
small shared-feature factor. These are documented proposal weights, not a
claim that the output samples the world's languages. Missing pair rows are
neutral, recorded expected absences reduce a proposal weight, and missing or
low evidence never overrides required sounds or a valid hard rule. The report
retains the selection factors and any evidence gaps.

## Form construction

The generated inventory filters the specification's allowed onsets, codas and
templates. Each component chooses a seeded syllable count, then a usable
template, exact allowed onset/coda sequences, and a selected vowel nucleus.
Intersyllabic transitions are the ordered meeting of independently permitted
codas and onsets in v1; no additional transition ban is invented. Special
markers never enter the inventory or forms. Tone realization, stress
application, allophony and harmony remain visible Step 12 gaps.

Every output is independently checked for selected-inventory membership, exact
onset/coda membership, template traces, vowel nuclei, boundary resets,
special-marker exclusion and the duplicate policy. A failed hard-rule check is
an internal error and is never emitted as a successful generation.

## Reproducibility and evaluation

The request receives a canonical SHA-256 fingerprint. Every decision namespace
includes that fingerprint, word/component/attempt indexes, and the Step 10
versioned seed mechanism. The same canonical specification and request therefore
produce the same inventory, retries and forms.

The completed inventory/forms are passed to the Step 8 evaluator in the same
read transaction. Its component evidence, unknowns and null combined score are
embedded in the generation report. Unusual but construction-valid designs are
reported, not silently discarded.

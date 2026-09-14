# Phonology evidence evaluator

Run the bundled demonstration from the repository root:

```bat
python scripts\analysis\evaluate_phonology.py --demo
```

It reads the existing SQLite analysis tables and writes
`data/compiled/phonology-evaluation.json`. It does not create tables, rebuild
statistics, change the database, or run Wrangler. No extra Python packages are
required. `PHONOLOGY EVALUATION COMPLETE` means the evaluation ran successfully;
it is not a verdict that the proposed system is natural or grammatical.

The demonstration selects `northeuralex-eng` explicitly. English is only the
example comparison doculect, not a universal standard. The small sample inventory
and words are illustrative proposals, not a claim to model English. Low overlap
with this particular corpus does not make those proposals defective.

## Evaluating your own proposal

Copy `examples/phonology-proposal.json`, edit it, then run:

```bat
python scripts\analysis\evaluate_phonology.py --input my-phonology.json
```

Use `--output another-report.json` to keep multiple reports, or `--database`
to select another already-built reference database. Output must be a separate
JSON file, not the proposal or database.

| Input | Meaning |
| --- | --- |
| inventory | Required list of distinct, exact token strings |
| inventory_scope | `language` (default) or `inventory` for PHOIBLE prevalence/pairs |
| reference_doculect | Exact Lexibank ID; null or omitted skips lexical comparisons |
| words | Optional list of words, each represented as a list of segment tokens |
| syllable_templates | Optional distinct single-nucleus shapes such as CV or CCVC |
| prosody.stress | unknown, none, fixed or variable |
| prosody.tone | unknown, present or absent |
| prosody.length_contrast | unknown, present or absent |

Words must be token lists, not unsegmented strings. Multi-character IPA tokens
remain one list item. Tokens match literally: no Unicode normalization, fuzzy
matching, or guessed CLTS aliases occur. Limits are 256 inventory tokens,
1,000 words of at most 128 tokens, 64 syllable templates, and 1 MiB of proposal
JSON. Unknown fields and duplicate inventory/templates are rejected.

`+` can separate nonempty components inside a word, but it is not an inventory
phoneme. `∼` is a special transcription marker and is flagged in proposed words.
Undeclared word tokens and malformed boundaries are reported as input-model
consistency issues. This check does not require vowels in every language, infer
syllabification, or prove that sample words match the proposed syllable rules.

## Reading the report

The report deliberately has no universal naturalism percentage. Its
`overall_naturalism_score` is null because the components use different
populations and no calibrated combined model has been established.

| Component | Interpretation |
| --- | --- |
| Inventory mapping | Fraction of proposed tokens with exact PHOIBLE matches; unknowns remain listed |
| Inventory size context | Midrank percentile among source inventories, computed only when all proposed tokens map |
| Segment prevalence | Observed fraction of units containing each mapped segment in the selected PHOIBLE scope |
| Pair evidence | Stored observed pairs, expected absences, or `not_stored`; missing rows never become zero counts |
| Phonotactics | Exact adjacency and literal word-edge evidence in the one selected Lexibank doculect |
| Syllables | Possible/forced Step 6 model support, source-form eligibility and exclusion counts |
| Prosody | Separate field/feature annotations and examples; proposed systems remain unassessed |

Inventory-size context always uses inventory units and is labeled accordingly,
even when segment/pair scope is `language`. A midrank percentile is
`100 * (units smaller + 0.5 * equal units) / all units`. High or low percentiles
describe size; neither is automatically better.

`observed_fraction_known_pairs` is the fraction of known candidate adjacency
positions that occur in the selected doculect. Repeated candidate pairs count
as repeated positions. Unknown pairs are excluded from that denominator and
reported through `mapping_coverage`; a partial match cannot silently become full
coverage. With no known pair positions, the fraction is null, not 0 or 1. Raw
boundaries are retained and separate words are never joined. A known pair absent
from the complete Step 5 adjacency table has zero observations in that corpus;
this is not a claim it is linguistically impossible.

Syllable support is conditional on the Step 6 CV projection. Candidate
alternatives overlap, and a forced slot is forced only by that model. No eligible
reference forms means unknown support. The evaluator does not automatically
syllabify candidate words or infer a language's onset/coda rules.

Stress, tone and quantity annotations do not by themselves establish a stress
rule, tone-system classification or phonemic length contrast. Proposed prosodic
properties are preserved in the report but receive no invented score. Missing
annotations never mean that a language lacks the feature.

The report includes the method versions and saved source fingerprints of the
evidence builds used. Evaluation runs in a read-only SQLite transaction and
checks for missing versions and obvious source-count inconsistencies. It does
not rerun full raw-source validation: `raw_source_revalidated` is false. Rebuild
the relevant analysis if its source changes; do not repeat every importer before
each evaluation.

## Validation and next integration

Automated tests cover component values, unknowns, zero denominators, preserved
boundaries, distinct doculects sharing a Glottocode, absent stored pair rows,
unassessed prosody, mixed snapshots, input errors, and CLI read-only behavior.
This remains an offline evaluator. Worker/React integration and a targeted D1
sync are the next milestone; neither is implemented by this patch.

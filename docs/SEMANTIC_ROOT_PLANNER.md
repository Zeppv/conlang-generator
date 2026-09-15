# Semantic root planning — Step 13

Step 13 adds a Python planner and CLI that read the existing semantic reference
tables and create a small lexical plan. The output is a proposal for review,
with stable root/lexeme IDs, alternatives, explanations, source records, and
saved user overrides. No word forms are assigned yet.

This is an offline milestone. Website planning controls and the Step 14
connection to generated phonological forms are still future work. It requires
no schema migration, semantic rebuild, D1 sync, new dependency, or source download.

## Run against your existing database

In the project folder:

```bat
python scripts\analysis\plan_semantic_roots.py --demo
```

The demonstration resolves these explicit Concepticon identities, then saves
their corresponding **internal concept IDs** in the request:

| Concepticon ID | Selected sense |
| --- | --- |
| 1313 | MOON |
| 1370 | MONTH |
| 1343 | SUN |
| 1225 | DAY (NOT NIGHT) |
| 948 | WATER |
| 658 | RAIN (PRECIPITATION) |
| 221 | FIRE |

These IDs and senses follow the [Concepticon concept table](https://github.com/concepticon/concepticon-data/blob/master/concepticondata/concepticon.tsv).
The demo deliberately uses daylight and rain as a substance, not the 24-hour
period or the act of raining. It does not look up bare `DAY` / `RAIN`, search
partial glosses, or confuse external IDs with local IDs. Relabeling a concept
does not change the selected identity. Missing identities fail explicitly;
these are demonstration concepts, not a required universal vocabulary.

The CLI prints the proposed relationships and support weights, and saves
`data/compiled/semantic-root-plan.json`. Your actual database determines the
proposals; the tests' synthetic weights do not appear in your output. The CLI
opens `reference.sqlite` in read-only mode and holds one read transaction.

## Meaning of each choice

| Choice | Representation | How selected |
| --- | --- | --- |
| `separate` | An independent root and lexeme | Conservative default or override |
| `colexification` | Two concepts share one root and lexeme identity | Direct pair colexification support or override |
| `shared_root` | Distinct lexemes sharing a proposed common root | Undirected derivation evidence or override; no historical direction or affix invented |
| `derivation` | A distinct lexeme inherits its base's root IDs | Directed derivation evidence or override; realization is deferred |
| `compound` | A distinct lexeme references 2–4 ordered base concepts | Explicit override only; bases' families stay distinct |
| `gap` | No lexeme or root for this concept | Explicit override only |

The shared-root choice is a **family hypothesis**. Members share a root ID but
have distinct lexeme IDs; their eventual realization is unresolved. The base
concept anchors identity without asserting historical direction. Colexification
does share lexical identity. Derivation adds a directed lexical dependency;
it does not already define a productive morphological pattern.

## Evidence and automatic choices

The planner snapshots the selected concepts, semantic pair and directional
scores, corresponding `concept_relation` / `datsemshift_relation` rows, and
available source metadata. Every selected pair has an evidence record, including
explicit `unknown` when no pair score exists. Directional evidence stays directed.
Original source record IDs and score components remain inspectable.

The automatic proposal weights are:

- Colexification: `semantic_pair_score.colexification_score`.
- Shared-root family: `semantic_pair_score.derivation_score`.
- Derivation: forward `semantic_direction_score.derivation_score`.

General relatedness, WordNet similarity, semantic shift, and polysemy alone do
not authorize a morphological derivation. All those stored components remain
in the evidence snapshot. DatSemShift derivation evidence describes historical
observations; applying it to this new language remains a generator choice.

For each concept in ascending internal-ID order, automatic choices consider
independent earlier root anchors, retain proposals at or above the request's
`minimum_support`, and choose the strongest eligible option. The default 0.55
threshold is an explicit engineering policy, not an empirically calibrated
boundary. A SHA-256 tie break uses the seed. The seed does not sample scores as
probabilities. Results depend on the declared candidate set and ID order.

Automatic colexification groups contain at most two concepts. This avoids
turning a chain of pair relationships into an unsupported universal shared
word. Larger groups are possible only through explicit overrides. Automatic
choices do not create cycles; contradictory user dependencies fail validation.

All positive direct alternatives remain saved even if the threshold, anchor
policy, or a user override prevents automatic selection. Independent roots also
remain an alternative. No compound decomposition or lexical gap is guessed.
Confidence records include the numeric support weight and its meaning, with
`calibrated_probability: null`. Missing evidence is not proof of impossibility.

## Edit and preserve deliberate choices

Export an editable request while generating:

```bat
python scripts\analysis\plan_semantic_roots.py --demo --request-output data\compiled\semantic-root-request.json
```

The exported request contains `version`, `project_id`, `seed`, `concept_ids`,
`minimum_support`, and `overrides`. Edit `overrides` using the **actual internal
IDs in your generated plan**. The following illustrates the shape only; 123
and 456 are placeholders, not asserted IDs for any particular concept:

```json
{
  "concept_id": 456,
  "kind": "derivation",
  "bases": [123],
  "reason": "I want this concept expressed as a derivative of the base."
}
```

Separate roots and gaps take `bases: []`. Colexification, shared-root, and
derivation each take one base. Compounds take 2–4 distinct ordered bases.
Every override needs a reason. Overrides are complete choices, not suggestions
the generator can silently undo. Evidence-free choices stay visibly user-authored.
Use an explicit `separate` choice to reject an automatic link.

Revise against the saved evidence without opening SQLite:

```bat
python scripts\analysis\plan_semantic_roots.py --from-plan data\compiled\semantic-root-plan.json --request data\compiled\semantic-root-request.json --output data\compiled\semantic-root-plan-revised.json
```

Keep the same project ID and concept set when revising a frozen plan. To use a
different concept set or refreshed evidence, run `--request` against the database
instead. Your override list remains part of that request. `--demo` always starts
a new demonstration; it does not discover or merge earlier overrides.

Unknown fields, duplicate IDs/JSON keys, nonfinite scores, invalid versions,
contradictory overrides, missing bases, dependency cycles, and using gaps as
bases fail clearly. Colexification needs a root-bearing base; a compound cannot
serve as the single family anchor of `shared_root`.

## Stable identities and replay

Concept identity uses `concept:<internal ID>`. Root and lexeme identities use the
project namespace and anchor concept ID, for example `first-language:root:c123`.
Changing a gloss or seed does not rename an existing root anchored to the same
concept. Changing a relationship can intentionally change which roots a concept
uses. Family IDs describe the current grouping and can change when links change.
Internal IDs are stable within the existing reference database lineage; mapping
identities across a rebuilt database with reassigned IDs is not implemented.

The complete plan stores the canonical request, overrides, model version,
frozen evidence and SHA-256 evidence fingerprint. Replay validates the snapshot
and compares the entire regenerated report. It needs no database or D1:

```bat
python scripts\analysis\plan_semantic_roots.py --from-plan data\compiled\semantic-root-plan.json --output data\compiled\semantic-root-plan-replayed.json
```

Editing computed plan entries by hand fails replay. Edit the request and use the
revision command instead. Fingerprints detect accidental changes; they are not
a signature proving source authenticity. A plan ID identifies the request and
snapshot, not a date or mutable filename.

## Bounds and verification

Requests accept 1–64 concepts and at most one override per concept. Evidence
reads allow at most 20,000 rows per selected table; excessive input fails rather
than silently truncating evidence. Input and output JSON are limited to 16 MiB.
Output paths cannot replace inputs or the database or write under `data/raw`.

Run the focused suite:

```bat
python -m unittest discover -s tests -p "test_semantic_root_planner.py" -v
```

The 17 tests cover the real repository schemas with explicitly synthetic evidence
and source-aligned Concepticon identities/labels:
lexical distinctions, directionality, conservative colexification, unknown
evidence/provenance, stable identities, deterministic replay after database
changes, preserved overrides, compound ordering, cycles, corrupt reports,
strict input validation, identity resolution despite changed/duplicate glosses,
distinct day/rain senses, missing external IDs, and CLI generation/replay/revision.
A SQL authorizer rejects all operations except SELECT/READ. The CLI test also
compares database bytes before and after generation, then deletes its temporary
database and verifies replay/revision still work. No user database was rebuilt
or accessed in this environment. Full-data demonstration remains a user checkpoint.

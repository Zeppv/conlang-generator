# Website generation — Step 12C

The Rule Workspace now generates new inventories and forms directly from the
website's existing compact evidence snapshot. It then applies the bounded Step
12 rule engine and produces the same portable bundle as the saved-run workflow.
No schema change, source rebuild, serving sync, or full D1 import is required.

## Use it

After pulling the update, start the existing development site and open **Rule
Workspace**. In **Generate a new sound system**, choose a seed, exact consonant,
vowel and tone targets, and the sample count. Click **Generate inventory and
forms**. The default uses the demonstration sound pool and initial-stress /
intervocalic-t rules. The page shows the selected inventory, forms, transformations,
selection factors, generation settings, evidence gaps, and saved evaluator report.

You can instead load a Step 12 workspace bundle and choose **Loaded run's pool
and rules**. That uses the full candidate pool in its specification, not just the
previously selected inventory. The current rule editor supplies the rules for a
new run. Full specification authoring remains the strict Step 10 Python workflow;
this checkpoint adds fresh generation from an exported pool, not a new schema or
an automatic source-inventory/rule induction capability.

Under **Inventory constraints and evidence**, set required/excluded IDs, evidence
population, exact reference doculect, duplicate behavior, and component-count
weights. **Show available reference doculects** reads the existing snapshot status.
A blank doculect skips lexical comparisons. The default English doculect is an
explicit comparison choice, not a universal phonological target. If the current
snapshot lacks a chosen doculect, select an available one or leave it blank.
Do not automatically reimport data to resolve a selection error.

Rules can require selected tone or length-pair phonemes. Include those IDs in the
required sounds and choose compatible targets. Incompatible construction or
realization fails with an explanation; required IDs and hard rules are never
silently changed to fit the evidence.

## Reproduction and evidence identity

**Save complete run** stores the specification, seed, original request, canonical
request, inventory selection factors, forms, evaluator output, rules, traces,
and evidence snapshot ID. Loading it still verifies realization locally.

**Reproduce saved generation** sends the saved original request and snapshot ID
back to the generation endpoint, then compares the complete regenerated report
with the saved report before replacing the current result. It reuses the saved
rule set. Apply edits first if you want to save a different rule realization.
The original request is retained because normalizing floating-point weights
again is not a safe general substitute for preserving the actual input.

New runs use the current active snapshot. Reproduction selects the saved
immutable snapshot explicitly, so later activation cannot silently change its
evidence. If that snapshot has been removed or is corrupt, regeneration fails
clearly; the saved forms/evaluation and local realization replay remain usable.
Snapshots are already retained by the existing Step 9 serving workflow. No new
project/reference tables or automatic data writes are introduced.

## Algorithm and compatibility

The TypeScript implementation ports Step 11 generator version 1.0.0. For the same
canonical specification, original request and evidence, it uses the same request
fingerprint, SHA-256 decision namespaces, inventory ordering, heuristic factors,
weighted choices, duplicate retries, component boundaries, and evaluation.
The implementation includes 28-digit decimal arithmetic for weighted selection
and request normalization, plus Python-compatible eight-place rounding of
reported heuristic factors. No new numeric library dependency is required.

Prevalence, observed pair lift, stored expected absences, missing pair rows, and
shared feature counts retain their distinct Step 11 meanings. Low/missing
frequency does not reject an otherwise valid sound. The generation report's
Step 11 extension-gap labels describe its underlying forms; the separate
realization report shows which Step 12 rules were actually applied afterward.
Do not label an unknown family as absent or call an uncalibrated total a score.

## Serving path and bounds

POST `/api/phonology/generate` accepts:

- `specification_json`: the exact exported canonical Step 10 string;
- `request`: the Step 11 generation request;
- `rules`: the Step 12 explicit rule set;
- optional `snapshot`: an existing 64-character snapshot ID for reproduction.

It returns a version-1 workspace bundle. The generation report additionally has
`web_reproduction: {request, snapshot}`. Python realization replay and subsequent
browser rule edits preserve that record. The ordinary offline generation report
and its fingerprint algorithm are unchanged.

The endpoint pins one `Snapshot`, verifies the catalog and required records, and
reads pair rows for the full candidate pool so inventory selection has its needed
evidence. The same verified records supply evaluator output. Reads use the
existing `phonology_web_active` and `phonology_web_chunk` tables; the generation
path performs no database writes. `Snapshot` moved into a reusable module; the
old evaluator import remains re-exported for compatibility.

Website limits are 64 candidate sounds, 200 forms, 256 attempts per form, 2,000
total attempted forms, 20,000 seeded decisions, 20,000 output tokens, and 8 MiB
input/export JSON. Existing evaluator word/template limits also apply. The
bounds stop impossible or excessive requests; they are not linguistic claims.
Offline generation retains its existing larger request limits. Malformed input
and impossible requests produce 400, wrong methods/content types produce 405/415,
and unavailable or corrupt snapshot data produces 503 without replacing a run.

## Verification and v1 gate

38 focused automated tests pass across the specification, generator, rule engine,
workspace, new generation serving path, and existing evaluator parity check.
This includes:

- 26 complete Python/TypeScript generation reports covering seeds, both evidence
  populations, request weights, required/excluded sounds, unknown evidence, tone
  inventory selection, component traces, and attached evaluator output;
- the prior 28 rule-report and 15 evaluator-report parity cases;
- source-derived in-memory serving chunks with real checksum/manifest verification,
  new generation and Python realization replay, and regeneration after another
  snapshot becomes active;
- missing/corrupt snapshots, unavailable doculects, invalid requests, duplicate
  exhaustion, and total operation-budget failures;
- a serving-table test adapter that rejects writes and unrelated source queries.

Production TypeScript/Vite build and lint pass. No real user database was rebuilt
or imported for these checks. Native Cloudflare/browser confirmation of this new
button remains the user installation checkpoint. The previous Step 12B website
run is user-confirmed: 20 forms, correct initial stress/tapping examples, and
browser/server agreement. A pasted page does not independently verify file export
or visual layout; automated replay covers the saved-data contract.

After the user generates and reproduces a run on their existing local site, the
bounded Phonology Engine v1 acceptance gate can be recorded, with its explicit
support/deferred matrix preserved. Then proceed to Step 13 semantic root planning.

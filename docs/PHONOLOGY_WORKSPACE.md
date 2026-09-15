# Rule Workspace — Step 12B

Step 12B adds a website workspace for an existing Step 11 generation. It applies
explicit rules, shows underlying and realized forms with derivation traces,
retains the saved evidence, and exports all inputs needed to reproduce the run.
It does not generate a new inventory in the browser. Full specification authoring
and fresh inventory/form generation remain the Step 10/11 Python workflows.

## Use your existing forms

From the project root, after pulling this update:

```bat
python scripts\analysis\apply_phonology_rules.py --bundle-output data\compiled\phonology-workspace.json
npm run dev
```

Open **Rule Workspace**, choose **Load run**, and select that JSON file. The
export command reads the existing specification, rules, and Step 11 generation;
it does not build a database or import D1. For a custom generation, supply its
matching `--specification`, `--rules`, and `--generation` paths.

**Try example** opens three explicitly illustrative forms with no attached
reference evaluation. It is a UI example, not another source-data build or an
empirical naturalism result.

Stress, lexical tone display, and length pairs have controls. The full JSON
editor supports every bounded rule family, including ordered allophony and
vowel/consonant harmony. Stable phoneme IDs are displayed next to IPA strings.
Click **Apply rules** to compute and compare the browser and Worker results.
Changes clear the previous result so an unapplied edit cannot be exported as
though it had run. Switching workspace tabs preserves the rule editor state;
reload persistence requires **Save complete run**.

## Reproduce a saved run

A saved bundle includes its format and engine versions, the exact canonical
specification JSON, normalized rules, complete generation report, and realization
report. The exact specification string preserves Step 10's existing Python
fingerprint, including its numeric representation. Do not manually reformat that
inner string. Fingerprints identify content; they are not authenticity signatures.

Loading a complete bundle recomputes the report and rejects a mismatch. To verify
a browser export with Python:

```bat
python scripts\analysis\apply_phonology_rules.py --bundle path\to\phonology-workspace.json --output data\compiled\reproduced-realization.json
```

No original input file can be selected as an output path. A mismatched saved report
is rejected before the CLI writes outputs. To author changes, use the page's rule
editor or the separate specification/rules inputs; do not edit an old expected
report to make it appear to reproduce.

## Rule engine 1.1.0

Rule schema version remains 1.0.0; the engine version is now 1.1.0 because boundary
and output validation behavior changed. The default example rule fingerprint is
unchanged. Negative-zero length probability is normalized to zero so browser
JSON exports reproduce consistently.

- `any` means an adjacent phoneme exists. It never matches a component marker or
  an outer word edge. Use `component_edge` or `word_edge` explicitly. Allophony
  checks immediate neighbors; it does not skip a marker to inspect another
  component, even with domain `word`.
- Harmony may span components only for an explicitly allowed word domain.
  Component-domain rules reset at the marker. Blockers reset the active feature;
  absent replacement mappings do not invent a change.
- Recheck inventory membership, IPA displays, component/syllable traces, templates,
  allowed clusters, nuclei, and indexes on load; never trust an imported `valid`
  flag by itself. This is construction validation, not rerunning evidence scoring.
- The final IDs after length and ordered harmony must satisfy the same declared
  onset/coda choices and selected inventory. Incompatible rules fail clearly;
  the engine does not silently repair them. Surface allophones remain separate
  and can use IPA strings outside the phonemic inventory.
- Rule declarations cannot contradict explicit absence in the specification or
  a declared fixed stress position. Structural/stress markers cannot be smuggled
  into an allophone token.

The supported and deferred families in `PHONOLOGY_RULES.md` still apply. The page
shows each family's configured, unknown, explicit-none, or deferred status and
lists unsupported rule families. Reference evidence is retained unchanged; rule
application neither validates those families empirically nor assigns a combined
naturalism score.

## Implementation and limits

- `shared/phonology-rules.ts`: browser/Worker realization and input validation.
- `worker/phonology-rules-api.ts`: POST `/api/phonology/realize`; no D1 access.
- `scripts/analysis/phonology_workspace.py`: portable export and Python replay.
- `src/RuleWorkspace.tsx`: file loading, controls, transformations, evidence, export.

The shared runtime checks the specification fields consumed by realization;
Python remains the full Step 10 specification authoring/validation authority.
The supported input is a bundle exported by Python or re-exported by this page,
not an arbitrary replacement specification schema.

Limits: 8 MiB JSON payload, 1–1,000 forms, at most 20,000 total form tokens,
1–8 components per form, 1–16 syllables per component, at most 256 phonemes,
and at most 64 rules per allophony/harmony family. JSON keys must be unique.
The HTTP boundary rejects excessive JSON nesting, malformed UTF-8, wrong methods,
wrong content types, and oversized bodies. These limits bound application work;
they are not claims about linguistic possibilities.

## Verification and remaining acceptance work

Verified in the development workspace:

- All 33 focused Step 10–12 tests pass, including nine new workspace tests.
- 28 complete Python/TypeScript report cases cover stress, tone display, length
  probabilities, both harmony classes, direction, domains, blockers, and replay.
- Negative cases cover mismatched fingerprints, contradictory rules, malformed
  traces, unselected sounds, changed saved reports, and disallowed output clusters.
- A Step 11 generation on a small in-memory evidence fixture survives Python,
  shared TypeScript, and API replay with its complete evaluation unchanged.
- HTTP method, content-type, duplicate-key, nesting, and byte limits pass with
  a D1 stub that fails on any access. CLI input preservation and replay pass.
- Production TypeScript/Vite build and lint pass.

Browser interaction/visual checks remain unverified: the connected browser
reported `ERR_BLOCKED_BY_CLIENT` for the local preview. The native Cloudflare dev
runtime also could not start in this environment (`uv_interface_addresses`);
API checks used Node's Web Request/Response runtime. No new local or remote D1
import was attempted. These limits do not invalidate the user's existing local
installation, but they prevent claiming a new native Worker/browser sign-off.

Next: confirm the page with the user's exported run, complete fresh-generation
website integration through the existing compact evidence path, then assess the
full Phonology Engine v1 acceptance gate. Step 12B is an implemented saved-run
workspace checkpoint; full Step 12 remains open.

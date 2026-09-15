# Conlang Generator — roadmap and completion criteria

Updated 2026-09-15, after user confirmation of Step 12B and implementation of Step 12C website generation.

The goal is a generator in which vocabulary comes from a coherent language
system and its history. A working database and an evidence evaluator are the
foundation; they are not yet a language generator. There is no honest overall
completion percentage while the later research and modeling scope is open.

## Where we are

| Area | Current state | What this actually provides |
| --- | --- | --- |
| Development foundation | Working | Git project, Python pipelines, SQLite, local D1, Worker, React |
| Semantic Engine v1 | Complete | Concepticon, CLICS, Glottolog, WordNet, DatSemShift, pair and directional evidence, Concept Explorer |
| Phonology sources | Integrated | CLTS, PHOIBLE and Lexibank with provenance and conservative mappings |
| Step 4: inventory statistics | SQLite validated; local D1 import reported complete | Inventory sizes, prevalence, co-occurrence in inventory and language populations |
| Step 5: phonotactics | User build passed | Ordered token and adjacency summaries, word-edge and shape evidence by doculect |
| Step 6: syllable candidates | User build passed | Possible/forced shapes under an explicit CV projection, with ambiguity and exclusions |
| Step 7: prosody evidence | User build passed | Explicit stress, tone and length annotations; no inferred complete prosodic system |
| Step 8: offline evaluator | User demonstration complete | Read-only evaluation of a supplied inventory, words, templates and proposed prosody |
| Step 9: website evaluator | User installation/output supplied; committed checkpoint | Compact serving snapshots, Worker evaluator, Phonology tab, downloadable results |
| Step 10: executable specification | Complete; user validation passed | Versioned hard-rule contract, canonical JSON, strict contradictions, deterministic seeded decisions |
| Step 11: inventory and form generation | Complete; user validation passed | Exact-size seeded inventories, bounded form construction, hard-rule validation, attached evidence report |
| Step 12A: explicit rule core | User demonstration and seven focused tests passed | Bounded stress, tone, length, allophony and separate harmony rule contracts with derivation traces |
| Step 12B: saved-run rule workspace | User load/apply output confirms browser/server agreement | Load forms, edit rules, inspect traces/evidence, export/replay a full run |
| Step 12C: website generation | Implemented; generation/snapshot parity and build passed, user functional check pending | New inventories/forms from existing compact evidence; saved-snapshot regeneration |
| Root generation and later engines | Planned | Listed below with bounded deliverables and completion criteria |

The source database has 57 application tables through Step 8. Step 9 adds three
serving tables only to local D1. It does not add canonical linguistic tables or
change the SQLite reference database. These three serving tables are reproducible
from the source summaries and do not belong in the full reference exporter.

## The next steps in detail

### Step 9 — use the evaluator in the website

Deliverables:

- A Phonology tab alongside the existing Concept Explorer.
- Inputs for inventory, tokenized sample words, syllable templates, evidence
  population and one explicit reference doculect.
- Separate results for inventory mapping/prevalence, sound-pair evidence,
  inventory-size context, adjacency coverage, syllable support/exclusions, and
  prosody annotations. Unknown evidence remains visible.
- An evidence report download with build provenance. No fabricated combined
  naturalness score.
- A TypeScript evaluator checked against the existing Python evaluator.
- A local D1 sync that copies compact summaries, verifies their checksums and
  activates them together. It can resume after interruption.

The default sync includes the complete PHOIBLE statistics and the
`northeuralex-eng` lexical comparison. This is a small first serving scope,
not an English-based definition of natural language. The other 5,500 doculects
remain available in SQLite. Additional exact doculect IDs can be included with
repeated `--doculect` options; all requested IDs must be supplied on each sync.

Done when: API parity and actual local D1 tests pass, the user can evaluate the
example from the Phonology tab, and Concept Explorer still works. This is the
application evaluator milestone, not completion of sound-system generation.

### Step 10 — define an executable sound system

Implementation is delivered in `scripts/analysis/phonology_specification.py`,
`scripts/analysis/define_sound_system.py`, the bundled example, focused tests,
and `docs/PHONOLOGY_SPECIFICATION.md`. It is intentionally independent of the
reference database and D1. The user confirmed the demo and all nine focused
tests pass; Step 10 is complete.

The next modeling task is a versioned phonology specification. It needs to hold:

- Stable phoneme IDs, IPA display strings, feature mappings and mapping status.
- Consonant/vowel classes, allowed onsets/codas/clusters and syllable templates.
- Word-length and syllable-choice settings with explicit, normalized weights.
- Boundary behavior and explicit policies for special markers and unknown sounds.
- User-declared stress/tone/length settings, each distinguished from validated
  source evidence. Store “unknown” when the model has no defensible rule.
- A reproducible random seed, model version, and provenance for defaults.
- Extension points for allophony and harmony; an omitted rule must not be
  presented as a learned absence of that phenomenon.

Separate hard construction rules from descriptive evidence. A low reference
frequency should not silently forbid a sound or sequence.

Done when: a specification round-trips through JSON without losing information,
invalid or contradictory construction settings fail clearly, and the same
version and seed reproduce the same decisions.

### Step 11 — generate coherent inventories and word forms

Implementation is delivered in `scripts/analysis/phonology_generator.py`,
`scripts/analysis/generate_phonology.py`, a bounded request example, focused
tests, and `docs/PHONOLOGY_GENERATOR.md`. It reads reference evidence through a
read-only connection and writes only its JSON report. The user confirmed the
demonstration and all eight focused tests passed.

Build the first actual phonology generator using the specification:

- Generate candidate inventories with explicit consonant/vowel targets and
  compatible sound classes. Preserve user-required and excluded sounds.
- Use PHOIBLE prevalence and pair evidence as documented proposal heuristics,
  not as a claim that the resulting distribution reproduces real languages.
- Generate forms from allowed syllables and transitions; stop at component
  boundaries and do not promote special transcription markers into phonemes.
- Enforce model membership and construction rules independently of evidence scores.
- Keep duplicate handling, maximum attempts and failure explanations explicit.
- Run candidates through the evaluator; expose supporting evidence and gaps
  instead of silently discarding unusual valid designs.

Done when: the same seed yields the same inventory/forms, every generated form
passes its declared construction rules, constrained requests terminate, and
examples across different inventory sizes and template types work.

### Step 12 — prosodic rules, allophony, harmony, and the v1 acceptance gate

Step 12A's offline rule core is implemented in `scripts/analysis/phonology_rules.py`
and `apply_phonology_rules.py`, with a rule-set example, representative tests,
and an explicit support/deferred matrix. The user realized 20 forms and all seven
focused tests passed. Step 12B now supplies the matching TypeScript rule engine,
D1-independent realization API, saved-run website workspace, and portable replay.
The boundary and transformed-cluster findings are resolved with regression tests.
See `docs/PHONOLOGY_WORKSPACE.md` for verified scope and environment limits.
The user confirmed Step 12B's 20-form browser/server result. Step 12C now
generates fresh inventories/forms through the same compact snapshot and
reproduces saved generations against their original evidence. See
`docs/PHONOLOGY_GENERATION_WEB.md` for tested scope and bounds. The user
functional check of that new workflow and final v1 acceptance record remain open.

The existing annotations do not identify complete stress systems or harmony rules.
Before claiming these features, implement and label their actual support:

- A bounded set of explicit stress rules, initially user-selected where the
  reference evidence cannot justify automatic selection.
- Representation and application of tone and length settings, keeping lexical
  tone, attached tone marks and phonemic length distinctions separate.
- Context-conditioned allophonic rules that keep underlying phonemes separate
  from surface realizations and preserve the derivation trace.
- A bounded feature-based harmony model with explicit domain, targets,
  triggers and blocking behavior. Vowel and consonant harmony are separate
  capabilities, not a single inferred flag.
- Clear support labels for every rule type. Unsupported rule families remain
  deferred and visible; expand from representative examples rather than
  pretending to model every language's phonology.

The scope of those rule families requires design decisions and representative
tests before implementation. Automatic empirical induction of full prosodic,
allophonic and harmony systems is a later research capability, not something
Step 7 already achieved.

Done when: users can specify or generate the supported sound system, generate
sample forms, inspect transformations and evidence, and reproduce a saved run.
Reference data and the application must agree through the compact serving path.
Keep the v1 supported/deferred list explicit at sign-off.

### Step 13 — semantic root planning

Connect the completed semantic and phonology engines. For an explicit concept
set, create a lexical plan before assigning surface words:

- Separate roots, colexification, shared root families, derivations and compounds.
- Evidence and confidence behind each proposed relationship; retain alternatives.
- User control over which concepts are expressed and which remain lexical gaps.
- Stable root and concept IDs so gloss changes do not change lexical identity.

Use current semantic scores as engineering evidence, not deterministic laws.
Do not assign every English dictionary entry its own unrelated root.

Done when: a small concept set produces a reviewable root-family plan, deliberate
overrides persist, and every relationship is traceable to evidence or an explicit
generator choice.

### Step 14 — root forms and initial lexicon

- Assign generated phonological forms to planned roots.
- Resolve collisions intentionally: preserve chosen colexification, distinguish
  accidental homophony from shared ancestry, and retry only where appropriate.
- Produce a lexicon with root, concept, form, relationships, provenance and seed.
- Add browse/edit/export support before increasing vocabulary size.

Done when: users can generate and inspect a reproducible small lexicon whose
word families agree with both the semantic plan and the sound system.

### Step 15 — derivational morphology

- Model productive derivational patterns, affixes and compounds.
- Specify ordering, category changes, meanings, productivity and phonological
  interactions at morpheme boundaries.
- Keep derivation histories and distinguish transparent composition from
  lexicalized exceptions.

Done when: derived words can be generated, interpreted and traced back to their
roots without overwriting the original root records.

### Step 16 — proto-language vocabulary

- Assemble the initial chronological stage of a language, including roots,
  derivations, lexical meanings and supported phonological rules.
- Assign stable stage and lexeme identities; save the generating configuration.
- Define how later stages inherit and branch from this baseline.

Done when: a proto-language can be restored exactly and used as the source of
multiple independent descendant runs.

### Step 17 — historical sound change

- Ordered, environment-sensitive sound-change rules operating on appropriate
  underlying or surface representations.
- Mergers, splits, deletion, insertion, conditioning and boundary behavior within
  the implemented rule set.
- Word-level transformation traces and stage-level inventory updates.
- Preserve earlier forms; distinguish regular changes from analogy and exceptions.

Done when: chronological order matters correctly, conditioned changes affect
only their intended environments, and every descendant form has an inspectable
derivation from an earlier stage.

### Step 18 — semantic evolution

- Meaning extension, narrowing, shifts, gain/loss and polysemy using the existing
  semantic network and directional evidence.
- Dated meaning histories tied to stable lexemes.
- Later hooks for semantic bleaching, grammaticalization and analogy; these need
  their own rules rather than being side effects of random relabeling.

Done when: a lexeme's meanings evolve without losing its earlier senses, and
semantic changes remain distinguishable from phonological changes.

### Step 19 — Grambank and the grammar engine

- Inspect the already downloaded Grambank snapshot once when this stage begins.
- Import verified identifiers, observations and missing-data states with provenance.
- Define a coherent grammar configuration and constrained generator; do not
  independently randomize correlated grammatical properties.
- Make conflicts and unsupported combinations reviewable.

Done when: a generated grammar has explicit supported features, evidence links
and consistency checks, and can constrain subsequent morphology and syntax.

### Step 20 — UniMorph and morphological evolution

- Inspect and integrate the chosen source version when required.
- Define supported feature bundles, inflectional paradigms, categories and
  realization rules.
- Model paradigm changes and bounded analogical changes over historical stages.
- Distinguish source gaps, lexical exceptions and productive patterns.

Done when: selected lexemes inflect into consistent paradigms, surface changes
retain derivations, and historical stages preserve earlier paradigms.

### Step 21 — Universal Dependencies and syntax

- Inspect source coverage and license/version details at integration time.
- Represent supported dependency structures and ordering constraints.
- Generate bounded clauses using the language's grammar and inflectional choices.
- Keep structural representation separate from final word order and orthography.

Done when: supported sentence types are generated with matching syntax,
morphology and lexical forms, with visible limits on unsupported constructions.

### Step 22 — WOLD, borrowing and contact

- Inspect the downloaded WOLD source and integrate verified borrowing evidence.
- Model donor/recipient languages, contact intensity, domains and chronology.
- Adapt borrowed forms through recipient phonology and morphology.
- Preserve donor forms, borrowed meanings and etymological provenance.

Done when: a borrowing event creates a traceable lexical history rather than an
unexplained replacement, and recipient construction rules are respected.

### Step 23 — culture and historical events

- Define contextual factors that affect lexical demand, contact and semantic change.
- Add chronological events with explicit effects on the implemented language model.
- Keep user-authored worldbuilding separate from linguistic observations.

Done when: changing a documented contextual parameter produces inspectable,
bounded changes in a reproducible historical run.

### Step 24 — registers and dialects

- Register-specific lexical/phonological choices tied to social or usage contexts.
- Dialect branches that inherit a shared stage and then accumulate local changes.
- Shared lexeme identities and comparison views across varieties.

Done when: differences are attributable to explicit rules or history and the
varieties retain a recoverable common source.

### Step 25 — language families

- Branching historical trees, inherited vocabulary and subsequent contact.
- Cognate tracking, sound correspondences and lineage comparisons.
- Separate inheritance from borrowing and coincidental resemblance.

Done when: multiple descendants can be generated from one ancestor and their
relationships remain inspectable across forms, meanings and structures.

### Step 26 — broader naturalism analyzer

- Evaluate interactions among phonology, lexicon, morphology, syntax and history.
- Report contradictions, unusual patterns and missing coverage separately.
- If a combined score is desired, define calibration data and validate the
  aggregation first. Avoid presenting an arbitrary sum as scientific probability.

Done when: findings point to concrete model evidence or rules and remain useful
for deliberate unusual language design.

### Step 27 — user accounts and persistent projects

- Add identity, access control, projects, revisions, configuration and seed storage.
- Keep project data separate from reference linguistic data.
- Import/export, backup/restore, migration and deletion behavior.
- Introduce internal project identities earlier where history needs them; defer
  multi-user account infrastructure until this stage is useful.

Done when: users can securely save, reopen, branch, export and recover projects.

### Step 28 — public deployment

- Verify remote D1 capacity, query limits and the required serving footprint
  against the then-current hosting platform before choosing production topology.
- Test authorization, failure recovery, performance, accessibility and supported
  browser behavior for real workflows.
- Deploy versioned reference snapshots and application code with rollback plans.
- Establish monitoring, backups and a reproducible release process.

Done when: the public application supports its declared workflows reliably with
recoverable deployments. Local D1 success alone is not a production sign-off.

## How development stays faster

1. Build reference analyses in SQLite once per meaningful analysis change.
2. Run focused automated tests locally; avoid asking the user to paste repeated logs.
3. Transfer only the summaries a serving feature needs. Keep large raw forms and
   token-position tables out of routine website syncs.
4. Use immutable snapshots, bounded import parts, checksum verification and atomic
   activation. Resume a failed update instead of deleting local D1 state.
5. Ask the user for one short functional confirmation per delivered milestone.
6. Use the full reference export for initial setup or deliberate recovery, not
   every implementation step. Do not delete working Wrangler state as a routine fix.
7. Expand testing only to resolve a concrete remaining risk. Keep unproven model
   assumptions visible instead of adding endless source-inspection passes.

Later stages will still require source-specific inspection and modeling choices.
Their order and completion criteria are defined here; exact schemas and algorithms
should be decided from the actual sources when the relevant stage starts.

# Conlang Generator — Project Handoff

## Project Goal

Build a highly naturalistic conlang generator that generates languages as systems with history rather than generating unrelated random words.

The eventual generator should model:

- semantic relationships between concepts
- related word families
- derivational morphology
- lexical gaps
- colexification
- phonology and phonotactics
- morphology
- grammar
- sound change
- semantic change
- grammaticalization
- analogy
- borrowing
- culture
- registers
- dialects
- language families
- historical evolution
- naturalism scoring

The fundamental principle is:

**The dictionary is the output of a language system and its history, not the starting point.**

---

# Current Milestone

## Phonology Engine v1 — IN PROGRESS

Semantic Engine v1 is complete and working.

CLTS integration is complete and validated.

PHOIBLE integration is complete and validated through local Cloudflare D1.

Lexibank integration is complete and validated through local Cloudflare D1.
The existing Concept Explorer still works after the full Lexibank D1 import;
there is intentionally no Lexibank UI yet.

Step 4 passed the user's SQLite build and independent validator (3,020 profiles,
6,350 prevalence rows, 570,320 co-occurrence rows). The user reports completing
the restarted 14-part local D1 import. Post-import D1 counts were not captured;
do not describe that as independently verified or require another full import.

Step 5's one-command build and validator passed on the user's full imported
SQLite database (user confirmed `passed`). Do not ask them to rebuild it.

Step 6's bounded syllable-shape candidate build and validator passed on the
user's full SQLite database (user confirmed `passed`). Its ambiguity and
exclusions are model limits, not gold syllabification.

Step 7's stress/tone/length evidence build and independent validator passed on
the user's full database (user confirmed `passed`). Do not rebuild Steps 5-7.

Step 8's demonstration completed on the user's database (user confirmed
`complete`). It implements a read-only phonology evidence evaluator with component
metrics and coverage for proposed inventories, sample words, syllable templates
and prosody; it does not manufacture a universal naturalism percentage.

Step 9 implements the Phonology website tab, a matching Worker evaluator, and a
compact local D1 serving sync. User installation is pending. Do not rerun Steps
5–8 or the full reference export. Use the Step 9 instructions below.

**The detailed current roadmap and completion criteria are in `docs/ROADMAP.md`.**
Evidence evaluation is implemented; generation of sound systems and forms is
still outstanding. Prosody marks are not complete stress rules, allophony or
harmony models. Those capabilities remain explicit roadmap work.

Phonology Engine v1 order:

```text
CLTS — COMPLETE
↓
PHOIBLE — COMPLETE
↓
Lexibank — COMPLETE
↓
inventory statistics and phoneme dependencies — SQLITE VALIDATED;
LOCAL D1 IMPORT REPORTED COMPLETE
↓
phonotactics — STEP 5 VALIDATED ON USER DATABASE
↓
syllable structures — STEP 6 CANDIDATE MODEL VALIDATED ON USER DATABASE
↓
stress and related phonological systems — STEP 7 VALIDATED ON USER DATABASE
↓
phonology evidence evaluation — USER DEMONSTRATION COMPLETE
↓
website evaluator — STEP 9 IMPLEMENTED, USER INSTALL PENDING
↓
executable sound-system specification and generation — PLANNED
↓
explicit prosody/allophony/harmony support and PHONOLOGY V1 ACCEPTANCE
```

Do not move on to Grambank, UniMorph, Universal Dependencies, WOLD, Wiktionary, grammar, or later roadmap stages until Phonology Engine v1 is clean and complete.

---

# Semantic Engine v1 — COMPLETE

The Semantic Engine currently combines:

1. Concepticon
2. CLICS
3. Glottolog
4. Open English WordNet
5. DatSemShift

These sources are normalized into a local SQLite reference database.

The Semantic Engine stores:

- standardized concepts
- semantic relationships
- cross-linguistic colexification evidence
- WordNet semantic relationships
- Concepticon-to-WordNet mappings
- DatSemShift semantic relationships
- pair-level semantic evidence scores
- directional semantic-change scores

The Semantic Engine helps decide whether concepts should plausibly:

- use the same lexical form
- share a root
- be morphologically derived from one another
- form compounds
- be semantically related but lexically separate
- historically develop from one meaning into another

Current scores are engineering evidence scores from 0–1. They are not claims that a particular percentage of natural languages exhibit a feature.

---

# Core Architecture

The current pipeline is:

```text
Raw linguistic datasets
↓
Python import and analysis scripts
↓
data/compiled/reference.sqlite
↓
Python D1 exporter
↓
data/compiled/reference-d1.sql
↓
Cloudflare D1 local database
↓
Cloudflare Worker API
↓
React frontend
↓
Concept Explorer
```

The production architecture should ultimately remain approximately:

```text
User
↓
React frontend
↓
Cloudflare Worker
↓
D1 databases
```

The linguistic reference database should remain separate from future user-generated conlang/project data.

---

# Source Control

GitHub repository:

```text
https://github.com/Zeppv/conlang-generator.git
```

Remote:

```text
origin
```

Main branch:

```text
main
```

Confirmed CLTS milestone checkpoint:

```text
419f90d Complete CLTS integration for phonology engine
```

Confirmed PHOIBLE milestone checkpoint:

```text
c990be8 Complete PHOIBLE integration for phonology engine
```

Raw linguistic source repositories and datasets inside `data/raw/` must not be manually modified simply to make imports work.

---

# Folder Structure

```text
conlang-generator/
│
├── data/
│   ├── raw/
│   ├── staging/
│   ├── compiled/
│   ├── licenses/
│   ├── manifests/
│   └── README.md
│
├── database/
│   ├── migrations/
│   └── schema/
│
├── docs/
│   └── PROJECT_HANDOFF.md
│
├── scripts/
│   ├── analysis/
│   ├── download/
│   ├── import/
│   └── validation/
│
├── src/
├── worker/
├── package.json
├── vite.config.ts
└── wrangler.jsonc
```

---

# Important Data Rule

Files inside:

```text
data/raw/
```

must never be manually modified.

The data pipeline is:

```text
RAW
↓
IMPORT/PROCESSING SCRIPT
↓
STAGING
↓
COMPILED DATABASE
```

`data/staging/` and `data/compiled/` are rebuildable outputs.

---

# Downloaded Linguistic Sources

## Integrated

### Glottolog

Purpose:

- real-language identifiers
- Glottocodes
- ISO codes
- language families
- ancestry
- geography

Current planned/reference version: Glottolog 5.3.

---

### Concepticon

Purpose:

- standardized language-independent concepts
- semantic fields
- ontological categories
- concept relationships

Current planned/reference version: Concepticon 3.4.

Concepticon IDs are external reference identifiers.

The application's internal `concept.id` is the true internal concept identifier.

---

### CLICS

Purpose:

- cross-linguistic colexification
- evidence that two meanings are expressed using the same lexical form in real languages
- language and family evidence counts

Current planned/reference dataset: CLICS4.

CLICS evidence contributes to lexical-link scoring.

---

### Open English WordNet

Purpose:

- semantic senses
- synsets
- hypernym/hyponym relationships
- part/whole relationships
- antonyms
- derivational relationships
- similar concepts
- entailment
- causation

Current planned/reference release: Open English WordNet 2025.

WordNet is not used as the master concept system.

Concepticon concepts are mapped to specific WordNet senses to avoid errors caused by ambiguous English words.

A curated Concepticon/WordNet bridge based on `Borin-2015-1532.tsv` is currently used.

---

### DatSemShift

Purpose:

- attested semantic relationships
- directional semantic relationships
- polysemy evidence
- derivational evidence
- language-family evidence

DatSemShift data is kept in dedicated tables and mapped to Concepticon concepts where possible.

Unmapped DatSemShift concepts are preserved rather than discarded.

---

### CLTS

Purpose:

- standardized IPA/BIPA sounds
- canonical phonetic representations
- phonetic feature definitions
- transcription-system normalization
- mappings from source graphemes to standardized CLTS sounds
- normalization foundation for PHOIBLE and Lexibank

Integrated version:

```text
CLTS 2.3.0
```

Verified local Git checkout:

```text
tag: v2.3.0
commit: ec67f56a9197b072b2c15a5954a1b316864954fc
release date: 2024-04-19
```

The raw CLTS checkout was verified clean before integration.

CLTS importer inputs:

```text
data/raw/clts/data/features.tsv
data/raw/clts/data/sounds.tsv
data/raw/clts/data/graphemes.tsv
data/raw/clts/sources/index.tsv
```

The importer uses the actual physical TSV headers from the verified CLTS 2.3.0 checkout.

This is important because the physical v2.3.0 TSV files differ in some column ordering/content from `cldf-metadata.json`.

The BIPA source-definition files under:

```text
data/raw/clts/pkg/transcriptionsystems/bipa/
```

are not directly imported into SQLite for Phonology Engine v1.

The compiled CLTS data already exposes:

- standardized sounds
- canonical BIPA graphemes
- normalized feature information
- source grapheme mappings
- source dataset provenance

Validated CLTS counts:

```text
datasets:        33
features:        163
sounds:          8,765
sound features:  44,525
graphemes:       81,895
```

CLTS sound types:

```text
cluster:        69
consonant:   6,244
diphthong:     646
tone:          132
vowel:       1,674
```

CLTS has passed:

- source-to-SQLite validation
- SQLite foreign-key checks
- SQLite integrity checks
- SQLite → D1 SQL export
- local Cloudflare D1 import
- D1 row-count checks
- real Unicode/IPA query checks

A real CLTS D1 query was confirmed:

```text
id: unrounded_open_front_vowel
grapheme: a
sound_type: vowel
```

---

### PHOIBLE

Purpose:

- real-language phoneme inventories
- inventory sizes
- cross-linguistic phoneme occurrence
- distinctive-feature data
- allophones
- marginal phonemes
- source provenance
- basis for phoneme-frequency and co-occurrence statistics

Integrated version:

```text
PHOIBLE v2.0
```

Verified local Git checkout:

```text
tag: v2.0
commit: 862bec9af5db42e3c9ceedeaa378bf4c6fa0ec8b
commit date: 2019-03-16
```

License:

```text
MIT
```

Primary PHOIBLE importer inputs:

```text
data/raw/phoible/data/phoible.csv
data/raw/phoible/mappings/InventoryID-LanguageCodes.csv
data/raw/phoible/mappings/InventoryID-Bibtex.csv
data/raw/phoible/data/phoible-references.bib
data/raw/phoible/data/LICENSE
```

The primary compiled phoneme-level dataset is:

```text
data/raw/phoible/data/phoible.csv
```

Its verified physical schema contains:

- InventoryID
- Glottocode
- ISO6393
- LanguageName
- SpecificDialect
- GlyphID
- Phoneme
- Allophones
- Marginal
- SegmentClass
- Source
- 37 distinctive-feature columns

Validated PHOIBLE source totals:

```text
main observations: 105,467
inventories:         3,020
unique segments:     3,175
feature columns:        37
reference mappings:  3,843
```

Observation-level segment classes:

```text
consonant: 72,257
vowel:     31,063
tone:       2,147
```

PHOIBLE contains five repeated `(InventoryID, Phoneme)` pairs representing five extra exact duplicate source rows.

These rows are preserved rather than deduplicated.

One inventory (`InventoryID 2171`) contains multiple `SpecificDialect` values, so `SpecificDialect` is stored at the observation level rather than being forced into one inventory-level value.

`InventoryID-LanguageCodes.csv` agrees with the primary PHOIBLE file for:

- InventoryID
- ISO6393
- Glottocode
- Source

It differs in `LanguageName` for 235 inventories.

These differences are preserved in separate database fields:

```text
language_name
mapping_language_name
```

No source name is overwritten.

All 3,020 PHOIBLE inventories match the existing Glottolog-backed `reference_language` table by Glottocode.

PHOIBLE → CLTS mapping uses conservative tiers:

```text
1. CLTS mappings explicitly sourced from PHOIBLE
2. exact CLTS grapheme match only when the result is unambiguous
3. ambiguous mappings remain unresolved
4. unmatched symbols remain unresolved
```

Validated unique-segment mapping results:

```text
mapped / clts_phoible:      2,717
mapped / clts_exact_alias:    269
ambiguous:                     20
unmapped:                      169
total mapped:                2,986 / 3,175 = 94.05%
```

No ambiguous mapping is guessed.

Validated PHOIBLE database counts:

```text
phoible_inventory:             3,020
phoible_segment:               3,175
phoible_segment_feature:     117,475
phoible_inventory_segment:   105,467
phoible_inventory_reference:   3,843
```

PHOIBLE validation confirms:

- physical source-file schemas
- inventory-language identifiers
- all 235 language-name differences
- stable phoneme/GlyphID/feature profiles
- all 117,475 segment-feature records
- all 105,467 source observations
- all five repeated inventory/segment pairs
- row-level SpecificDialect preservation
- bibliography coverage
- MIT license
- Glottolog links
- conservative CLTS mappings
- SQLite foreign keys
- SQLite integrity

Current validator result:

```text
PHOIBLE VALIDATION PASSED
```

Final validator summary:

```text
Inventories validated:        3,020
Segments validated:           3,175
Segment features validated:   117,475
Observations validated:       105,467
References validated:         3,843
Repeated pairs preserved:     5
Multi-dialect inventories:    1
Language-name differences:    235
Unmatched Glottocodes:        0
```

CLTS mapping validation:

```text
ambiguous / -:               20
mapped / clts_exact_alias:  269
mapped / clts_phoible:    2,717
unmapped / -:               169
Total mapped:             2,986 (94.05%)
```

PHOIBLE has also passed the SQLite → D1 round trip.

Latest verified D1 counts:

```text
inventories:          3,020
segments:             3,175
segment_features:   117,475
inventory_segments: 105,467
references:           3,843
```

D1 also confirmed the same CLTS mapping summary.

A preserved PHOIBLE source-name difference was verified in D1:

```text
InventoryID: 1011
language_name: Siraiki
mapping_language_name: Saraiki
glottocode: sera1259
iso6393: skr
```

A real PHOIBLE → CLTS mapping was verified in D1:

```text
phoneme: a
segment_class: vowel
clts_mapping_status: mapped
clts_mapping_method: clts_phoible
clts_grapheme: a
```

Latest D1 export after PHOIBLE:

```text
application tables: 25
reference-d1.sql size: 124.40 MB
local D1 import commands executed: 6,088
```

---

# Integrated — Lexibank

Lexibank Analysed is an aggregate of normalized lexical datasets, not raw
lexical data. It provides real lexical forms, ordered segment sequences,
word-shape data, phoneme frequencies, and precomputed phonological and lexical
features.

Integrated checkout:

```text
repository: lexibank/lexibank-analysed
tags:       v2.2 and v2.2.1
commit:     46a2c4c63ae2cbb698cfd5ceb34cfee613eba8c4
license:    CC-BY-4.0
```

Validated source totals:

```text
collections:                     6
contributions/datasets:        134
languages/doculects:         5,501
unique Glottocodes:          3,120
concepts:                    3,205
phonemes:                    2,402
phoneme frequencies:       205,978
forms:                   1,740,092
ordered segment tokens:  9,657,998
unique segment tokens:       2,471
computed feature values:   294,383
```

All 3,120 Glottocodes resolve to `reference_language`, and all 3,205
Concepticon IDs resolve to `concept`. No fuzzy matching is used.

Lexibank has 1,633 phoneme references that map directly to physical
`clts_sound` records. Its remaining 769 references are valid compound/generated
CLTS sound-object names created by Lexibank's CLTS processing but not physically
enumerated in CLTS `sounds.tsv`. They remain explicit unmaterialized references
instead of being discarded or forced into `clts_sound`.

The form corpus uses 2,471 distinct segment tokens:

```text
Lexibank phoneme tokens: 2,393
additional CLTS tones:      76
boundary token (+):          1
special token (∼):           1
```

The `+` token is preserved as a structural boundary and never treated as a
phoneme. The `∼` token is preserved as a special transcription marker and is
also not treated as a phoneme.

The importer preserves all forms, ordered tokens, source fields, doculects,
Concepticon and Glottolog mappings, phoneme frequencies, collections,
contributions, and the published phonology/lexicon feature tables.


# Downloaded But Not Yet Integrated

---

### Grambank

Purpose:

- grammatical typology
- grammatical-feature correlations

Do not integrate until the grammar stage.

---

### NoRaRe

Purpose:

- semantic norms
- ratings
- concept properties

Not yet integrated.

---

### WOLD

Purpose:

- borrowing
- loanword behavior
- borrowability by semantic domain
- donor/recipient patterns

Downloaded and extracted but not yet integrated.

Do not integrate during Phonology Engine v1.

---

# Not Yet Downloaded / Not Yet Needed

Do not add these until their roadmap stages:

- UniMorph
- Universal Dependencies
- Wiktionary/Wiktextract

---

# Database Schema

Current schema files:

```text
database/schema/001_reference.sql
database/schema/002_wordnet.sql
database/schema/003_datsemshift.sql
database/schema/004_semantic_scores.sql
database/schema/005_clts.sql
database/schema/006_phoible.sql
database/schema/007_lexibank.sql
database/schema/008_phonology_statistics.sql
```

The base database includes tables such as:

```text
reference_source
concept
relation_type
concept_relation
reference_language
```

WordNet adds:

```text
wordnet_synset
wordnet_lemma
wordnet_sense
wordnet_relation
wordnet_sense_relation
concept_wordnet_mapping
```

DatSemShift adds:

```text
datsemshift_concept
datsemshift_relation
```

Semantic scoring adds:

```text
semantic_pair_score
semantic_direction_score
```

CLTS adds:

```text
clts_dataset
clts_feature
clts_sound
clts_sound_feature
clts_grapheme
```

`clts_dataset` preserves provenance for transcription and sound datasets represented by CLTS.

`clts_feature` stores valid CLTS sound-feature/value definitions.

`clts_sound` stores standardized CLTS sounds and canonical BIPA graphemes.

`clts_sound_feature` normalizes each sound's ordered CLTS feature list into queryable relationships.

Its primary key uses:

```text
(sound_id, feature_order)
```

rather than:

```text
(sound_id, feature_id)
```

because some CLTS sounds legitimately repeat the same feature ID at different positions in the ordered feature list.

`clts_grapheme` stores source transcription graphemes and maps them to standardized CLTS sounds while preserving source dataset provenance.

PHOIBLE adds:

```text
phoible_inventory
phoible_segment
phoible_segment_feature
phoible_inventory_segment
phoible_inventory_reference
```

`phoible_inventory` stores one row per InventoryID and includes:

- Glottocode
- ISO6393
- `language_name` from `phoible.csv`
- `mapping_language_name` from `InventoryID-LanguageCodes.csv`
- source code
- link to `reference_language`

`phoible_segment` stores one row per stable unique PHOIBLE phoneme string/GlyphID/profile and includes:

- segment class
- CLTS sound mapping
- mapping status
- mapping method

`phoible_segment_feature` stores the 37 PHOIBLE distinctive-feature values for each unique segment.

`phoible_inventory_segment` preserves every original phoneme-level source row and includes:

- source row number
- inventory
- segment
- SpecificDialect
- Allophones
- raw Marginal value
- normalized marginal flag

There is intentionally no uniqueness rule on `(inventory_id, segment_id)` because PHOIBLE contains five exact duplicate source rows that must be preserved.

`phoible_inventory_reference` preserves the 3,843 InventoryID-to-BibTeX/source mappings.

Phonology Engine Step 4 adds:

```text
phonology_analysis
phonology_inventory_profile
phonology_segment_prevalence
phonology_segment_cooccurrence
```

`phonology_inventory_profile` records the observed and distinct inventory size,
consonant/vowel/tone balance, marginality coverage, CLTS mapping coverage,
consonant-to-vowel ratio, and vowel share for every PHOIBLE inventory.

`phonology_segment_prevalence` records each segment's frequency and rank at two
scopes. Inventory scope treats each PHOIBLE source inventory as one unit.
Language scope merges inventories that share a Glottocode while keeping the two
inventories without Glottocodes as separate evidence units.

`phonology_segment_cooccurrence` preserves every observed segment pair at both
scopes and calculates support, both directional conditional probabilities,
lift, pointwise mutual information, phi, and Jaccard similarity. It also stores
unobserved pairs only when the independence-model expected count is at least
5.0. This preserves credible negative evidence without materializing millions
of unsupported rare pairs. These values are evidence, not generator rules.

Lexibank adds:

```text
lexibank_collection
lexibank_contribution
lexibank_contribution_collection
lexibank_language
lexibank_language_collection
lexibank_concept
lexibank_phoneme
lexibank_frequency
lexibank_form
lexibank_segment_token
lexibank_form_segment
lexibank_feature
lexibank_feature_code
lexibank_feature_value
```

`lexibank_form` preserves every source form and all analysed strings, including
the original ordered `Segments`, `CV_Template`, `Prosodic_String`, Dolgo
classes, and SCA classes.

`lexibank_segment_token` stores the compact dictionary of 2,471 distinct form
tokens and classifies each as a phoneme, tone, boundary, or special marker.
`lexibank_form_segment` preserves all 9,657,998 token occurrences in order by
referencing that dictionary. This avoids duplicating long Unicode strings in
millions of rows while keeping the corpus directly queryable.

`lexibank_phoneme` distinguishes exact physical CLTS mappings from Lexibank's
generated/unmaterialized CLTS references. The latter are preserved exactly and
are not inserted into `clts_sound`.

`lexibank_feature`, `lexibank_feature_code`, and `lexibank_feature_value`
preserve both the phonology and lexicon StructureDataset outputs using a
`feature_domain` discriminator.

---

# Important Semantic Architecture

A concept is not an English word.

For example:

```text
concept
↓
MOUNTAIN
```

may have an English label, a Concepticon mapping, a WordNet mapping, DatSemShift evidence, and cross-linguistic CLICS evidence.

Future conlang lexemes will map to concepts.

The architecture should eventually be:

```text
CONCEPT
↑
LexemeSense
↑
LEXEME
```

One conlang lexeme may map to multiple concepts.

One concept may have multiple lexemes.

This allows generated languages to divide semantic space differently from English.

---

# Concept Graph

The Concept Graph consists of:

Nodes:

```text
concept
```

Edges:

```text
concept_relation
```

Relationships currently include evidence from:

```text
Concepticon
CLICS
WordNet
DatSemShift
```

Examples of relationship types include:

```text
linked
broader
narrower
colexification
is_a
instance_of
part_of
member_of
substance_of
similar_to
attribute_related
entails
causes
antonym
derivationally_related
synonymous_or_equivalent
semantic_polysemy_shift
semantic_derivation_shift
```

Different sources must remain identifiable.

Do not flatten every semantic relationship into generic `related`.

---

# Semantic Scores

`semantic_pair_score` stores undirected evidence about two concepts.

Important fields include:

```text
relatedness_score
lexical_link_score
colexification_score
derivation_score
datsemshift_score
wordnet_score
evidence_sources
```

`semantic_direction_score` stores directed evidence:

```text
source_concept_id
target_concept_id
shift_score
polysemy_score
derivation_score
evidence_family_count
```

The scoring system is currently heuristic and should eventually be recalibrated using additional real-language evidence.

---

# Important Scripts

## Import Scripts

```text
scripts/import/build_concept_graph.py
```

Builds the base SQLite reference database using Concepticon, CLICS, and Glottolog.

It executes all numbered SQL schema files automatically.

---

```text
scripts/import/import_wordnet.py
```

Imports Open English WordNet.

---

```text
scripts/import/map_wordnet_to_concepts.py
```

Maps curated Concepticon meanings to specific WordNet senses.

---

```text
scripts/import/build_wordnet_relations.py
```

Converts useful WordNet semantic relationships into Concept Graph edges.

---

```text
scripts/import/import_datsemshift.py
```

Imports DatSemShift concepts and semantic relationships and adds mapped relationships to the Concept Graph.

---

```text
scripts/import/rebuild_semantic_engine.py
```

Rebuilds Semantic Engine v1 in order:

1. Base Concept Graph
2. WordNet
3. WordNet mappings
4. WordNet concept relations
5. DatSemShift
6. Semantic scoring

This remains the normal Semantic Engine rebuild command.

CLTS and PHOIBLE are intentionally not added to the Semantic Engine rebuild script.

During the current Phonology Engine stage, the full reference rebuild sequence is:

```text
python scripts\import\rebuild_semantic_engine.py
python scripts\import\import_clts.py
python scripts\import\import_phoible.py
python scripts\import\import_lexibank.py
```

---

```text
scripts/import/import_clts.py
```

Imports verified CLTS 2.3.0.

The importer verifies:

```text
tag: v2.3.0
commit: ec67f56a9197b072b2c15a5954a1b316864954fc
```

It refuses locally modified raw CLTS data.

It validates the actual physical source headers.

---

```text
scripts/import/import_phoible.py
```

Imports verified PHOIBLE v2.0.

The importer verifies:

```text
tag: v2.0
commit: 862bec9af5db42e3c9ceedeaa378bf4c6fa0ec8b
```

It:

- refuses locally modified raw PHOIBLE data
- validates physical source headers
- preserves both PHOIBLE language-name sources
- validates inventory identifier consistency
- normalizes stable unique segment profiles
- imports 37 features per unique segment
- preserves every original observation
- preserves repeated source rows
- preserves observation-level SpecificDialect
- preserves bibliography mappings
- links inventories to Glottolog
- maps segments to CLTS conservatively
- leaves ambiguous/unmapped cases unresolved

---

```text
scripts/import/import_lexibank.py
```

Imports the verified Lexibank Analysed v2.2/v2.2.1 commit. It:

- refuses a changed or locally modified raw checkout
- validates every physical CSV header and the ZIP member layout
- requires exact Glottolog and Concepticon resolution
- preserves all source records and provenance
- streams the 1.74-million-row compressed form table
- normalizes 9.66 million ordered segment occurrences through a compact token dictionary
- distinguishes phonemes, CLTS tones, `+` boundaries, and the `∼` special marker
- preserves generated CLTS references without modifying the physical CLTS tables
- imports published phoneme frequencies and computed phonology/lexicon features

---

```text
scripts/import/export_reference_to_d1.py
```

Converts `reference.sqlite` into D1-compatible SQL.

It contains a table allowlist/order and intentionally stops if the SQLite database contains an application table the exporter does not know about.

It currently exports all 43 application tables, including CLTS, PHOIBLE,
Lexibank, and derived phonology-statistics tables. It writes the complete
`reference-d1.sql` file and automatically creates statement-safe files no
larger than 64 MiB in `data/compiled/reference-d1-parts/` for Wrangler.

Whenever a new database table is added, this exporter must be updated.

---

# Analysis Scripts

```text
scripts/analysis/explore_concept.py
```

Terminal Concept Graph explorer.

---

```text
scripts/analysis/build_semantic_scores.py
```

Builds pair and directional semantic evidence scores.

---

```text
scripts/analysis/build_phonology_statistics.py
```

Deterministically rebuilds PHOIBLE inventory profiles, inventory- and
language-scope segment prevalence, and co-occurrence/dependency evidence.

---

# Validation Scripts

Existing validation scripts live in:

```text
scripts/validation/
```

CLTS validation:

```text
scripts/validation/validate_clts.py
```

Current result:

```text
CLTS VALIDATION PASSED
```

PHOIBLE validation:

```text
scripts/validation/validate_phoible.py
```

Current result:

```text
PHOIBLE VALIDATION PASSED
```

The PHOIBLE validator checks:

- physical source schemas
- source inventory consistency
- language-code mapping coverage
- language-name differences
- stable segment/GlyphID/feature profiles
- segment classes
- all 37 feature columns
- repeated inventory/segment rows
- observation-level SpecificDialect variation
- bibliography coverage
- MIT license
- SQLite foreign keys
- SQLite integrity
- reference-source registration
- database row counts
- inventory contents
- Glottolog links
- conservative CLTS mappings
- all segment-feature records
- all source observations
- preservation of duplicate source rows
- SpecificDialect preservation
- inventory-reference mappings

Final PHOIBLE validator result:

```text
Inventories validated:        3,020
Segments validated:           3,175
Segment features validated:   117,475
Observations validated:       105,467
References validated:         3,843
Repeated pairs preserved:     5
Multi-dialect inventories:    1
Language-name differences:    235
Unmatched Glottocodes:        0
```

Validation should continue to expand as Lexibank and later phonology stages are added.

Lexibank validation:

```text
scripts/validation/validate_lexibank.py
```

Current result:

```text
LEXIBANK VALIDATION PASSED
```

The validator performs ordered SHA-256 source-to-database round trips for all
1,740,092 forms, 9,657,998 segment occurrences, 205,978 phoneme-frequency rows,
and 294,383 computed feature values. It also validates exact core records,
Glottolog and Concepticon links, CLTS mapping classes, special-token behavior,
foreign keys, and SQLite integrity.

Phonology statistics validation:

```text
scripts/validation/validate_phonology_statistics.py
```

Current result:

```text
PHONOLOGY STATISTICS VALIDATION PASSED
```

It reconstructs PHOIBLE inventory and language evidence units and compares all
3,020 inventory profiles, 6,350 prevalence rows, and 570,320 co-occurrence rows
in deterministic order. It also validates metadata, evidence classifications,
foreign keys, and SQLite integrity.

---

# Website

The current website is a React + TypeScript application.

Backend:

```text
worker/index.ts
```

Frontend:

```text
src/App.tsx
```

The website currently provides a Concept Explorer.

Users can:

- search Concepticon concepts
- select a concept
- view its definition
- view semantic metadata
- view related concepts
- click related concepts
- see relationship source information

Relationship display currently prioritizes important evidence sources such as DatSemShift and WordNet before generic Concepticon links.

The frontend automatically selects the best/exact search result when appropriate.

Step 9 adds a Phonology tab alongside Concept Explorer. It accepts a proposed
inventory, sample tokenized words, templates and one selected doculect, and
reports evidence and coverage with a JSON download. It is an evaluator, not a
sound-system generator. See `docs/PHONOLOGY_WEB.md` for serving and installation.

---

# Cloudflare

A D1 database named:

```text
conlang-reference
```

has been configured.

Local development uses:

```text
.wrangler/state/
```

The following full export is an INITIAL SETUP / DISASTER RECOVERY procedure,
not the current update workflow. Do not delete working local D1 state as a routine
update. Step 9 uses `python scripts\\analysis\\sync_phonology_web.py` instead.

To deliberately regenerate the entire local D1 reference database:

```text
python scripts\import\export_reference_to_d1.py
```

then delete local Wrangler state:

```text
if exist .wrangler\state rmdir /s /q .wrangler\state
```

then import every generated part in order from an interactive Windows Command
Prompt:

```text
for %f in (data\compiled\reference-d1-parts\reference-d1-part-*.sql) do npx wrangler d1 execute conlang-reference --local --file="%f"
```

Use `%%f` instead of `%f` only when placing the command inside a `.bat` file.
Do not pass the complete `reference-d1.sql` to Wrangler; the full Lexibank
export exceeds Node/V8's single-string limit.

then start the application:

```text
npm run dev
```

Current verified D1 export after PHOIBLE:

```text
application tables: 25
reference-d1.sql size: 124.40 MB
local D1 import commands executed successfully: 6,088
```

CLTS and PHOIBLE have both successfully completed the SQLite → D1 round trip.

The Lexibank build produced a complete 39-table, 678.74 MB D1-compatible export
from a validation database containing the full real CLTS and Lexibank data. The
export was re-imported into a fresh SQLite database in 48,379 statements with
all Lexibank counts, Unicode markers, foreign keys, and integrity preserved.

The local Wrangler import of the complete Lexibank database passed on the
development machine using statement-safe parts. The existing website also
passed its post-import regression check.

The Step 4 exporter now contains 43 application tables and creates the part
files automatically. Its SQL passed a clean 43-table SQLite round trip with
matching counts, no foreign-key violations, and `PRAGMA integrity_check = ok`.
The user reported completing the restarted Step 4 local Wrangler import. Exact
post-import counts were not captured. Step 9 independently transfers and verifies
the summaries it needs instead of requiring another full bootstrap import.

The public production site has intentionally not been deployed yet.

---

# Current Roadmap

The expanded roadmap, support boundaries and completion criteria are maintained
in `docs/ROADMAP.md`. The older source-history sections below remain useful as
provenance, but the current milestone and Step 9 instructions supersede old
pending-import or repeated full-export directions.

## COMPLETE — Data Foundation

- project folder structure
- raw/staging/compiled data separation
- SQLite reference database
- Cloudflare D1 development setup
- React/Worker application
- Concept Explorer

---

## COMPLETE — Semantic Engine v1

- Concepticon
- CLICS
- Glottolog
- Open English WordNet
- curated WordNet mapping
- WordNet semantic edges
- DatSemShift
- semantic pair scoring
- directional semantic scoring

---

## IN PROGRESS — Phonology Engine v1

Current progress:

```text
CLTS — COMPLETE
↓
PHOIBLE — COMPLETE
↓
Lexibank — COMPLETE
↓
inventory statistics and phoneme dependencies — SQLITE VALIDATED;
LOCAL D1 IMPORT REPORTED COMPLETE
↓
phonotactics — STEP 5 USER BUILD PASSED
↓
syllable candidates — STEP 6 USER BUILD PASSED
↓
explicit prosody evidence — STEP 7 USER BUILD PASSED
↓
offline evaluator — STEP 8 USER DEMONSTRATION COMPLETE
↓
website evaluator — STEP 9 IMPLEMENTED, USER INSTALL PENDING
↓
sound-system specification, generation and explicit rule support
↓
PHONOLOGY ENGINE V1 ACCEPTANCE
```

The Phonology Engine must not simply select random IPA symbols.

It should learn from real-language inventories and generate coherent sound systems.

Important planned capabilities include:

- phoneme inventory size
- consonant/vowel balance
- natural classes
- phoneme dependencies
- markedness
- phonotactics
- onset/coda restrictions
- clusters
- syllable templates
- allophony
- stress
- tone
- vowel harmony
- consonant harmony
- frequency-weighted sound selection

CLTS primarily answers:

```text
What sound is this?
What is its standardized representation?
What phonetic features does it have?
```

PHOIBLE primarily answers:

```text
Which phonemes occur in real-language inventories?
Which sounds occur together?
How large are real inventories?
What distinctive-feature profiles occur?
```

Lexibank should help answer:

```text
How are sounds arranged in words?
What segment sequences are common?
What word and root shapes occur?
What phonotactic patterns are cross-linguistically plausible?
```

---

# AFTER PHONOLOGY — Root Generator

The first generator should combine:

```text
Semantic Engine
+
Phonology Engine
=
Root Generator
```

Concepts should not independently receive unrelated random words.

The Semantic Engine should decide whether concepts:

- share one root
- share a derived root
- use a compound
- use the same word
- receive separate roots

The Phonology Engine decides what those roots can sound like.

---

# AFTER ROOT GENERATION

Planned order:

```text
Derivational morphology
↓
Proto-language vocabulary
↓
Historical sound-change engine
↓
Semantic evolution
↓
Grambank / grammar engine
↓
UniMorph / morphological evolution
↓
Universal Dependencies / syntax
↓
WOLD / borrowing and language contact
↓
Culture model
↓
Historical events
↓
Registers
↓
Dialects
↓
Language families
↓
Naturalism analyzer
↓
User accounts and projects
↓
Public deployment
```

---

# Project Rules

1. Never manually edit raw linguistic datasets.

2. Preserve provenance for imported information.

3. Do not treat English words as universal concepts.

4. Do not automatically accept ambiguous semantic or phonological mappings.

5. Do not generate every English dictionary word independently.

6. Prefer historical explanation over arbitrary irregularity.

7. Preserve old forms instead of overwriting them.

8. Distinguish real linguistic evidence from generator heuristics.

9. Keep reference linguistic data separate from future user data.

10. Keep the generator customizable. Naturalism should guide the user, not prevent deliberate unusual language design.

11. Inspect the actual downloaded dataset structure before writing an importer. Do not assume filenames or schemas from documentation alone.

12. Importers should fail loudly when verified source layouts change rather than silently guessing how to interpret new releases.

13. Keep provenance and source versions identifiable in the reference database.

14. Validate each major dataset against its raw source before declaring its integration complete.

15. Test new reference tables through the SQLite → D1 round trip before moving to the next roadmap stage.

16. Preserve inconsistencies in upstream datasets when they represent differing source records; do not silently rewrite raw linguistic evidence.

17. Conservative mappings are preferred over guessed mappings. Ambiguous and unresolved cases should remain identifiable.

18. When a source has multiple names or labels for the same record, preserve both when practical rather than silently choosing one.

19. Do not deduplicate raw-source rows merely because they appear identical unless there is strong evidence that deduplication is intended by the source.

20. Keep the Semantic Engine independently rebuildable from the Phonology Engine.

---

# Exact Current Stopping Point

Semantic Engine v1 is complete and tested.

Phonology Engine v1 is in progress.

## CLTS — COMPLETE

CLTS 2.3.0 is integrated, validated, and tested through local Cloudflare D1.

Verified raw checkout:

```text
tag: v2.3.0
commit: ec67f56a9197b072b2c15a5954a1b316864954fc
```

CLTS database tables:

```text
clts_dataset
clts_feature
clts_sound
clts_sound_feature
clts_grapheme
```

Validated counts:

```text
datasets:        33
features:        163
sounds:          8,765
sound features:  44,525
graphemes:       81,895
```

CLTS validation passes completely.

SQLite integrity and foreign-key checks pass.

The SQLite → D1 SQL → local Cloudflare D1 round trip passes.

---

## PHOIBLE — COMPLETE

PHOIBLE v2.0 is integrated, validated, and tested through local Cloudflare D1.

Verified raw checkout:

```text
tag: v2.0
commit: 862bec9af5db42e3c9ceedeaa378bf4c6fa0ec8b
```

PHOIBLE database tables:

```text
phoible_inventory
phoible_segment
phoible_segment_feature
phoible_inventory_segment
phoible_inventory_reference
```

Validated counts:

```text
inventories:        3,020
segments:           3,175
segment features: 117,475
observations:     105,467
references:         3,843
```

PHOIBLE validation passes completely.

All 3,020 PHOIBLE Glottocodes resolve to the existing `reference_language` table.

235 language-name differences between the two PHOIBLE source files are preserved.

Five repeated inventory/segment pairs are preserved exactly.

The single inventory with multiple `SpecificDialect` values is preserved at the observation level.

Conservative PHOIBLE → CLTS mapping results:

```text
mapped via CLTS PHOIBLE mappings: 2,717
mapped via exact safe aliases:      269
ambiguous and unresolved:            20
unmapped and unresolved:            169
total mapped:                      2,986 (94.05%)
```

SQLite integrity and foreign-key checks pass.

The SQLite → D1 SQL → local Cloudflare D1 round trip passes.

Latest D1 export:

```text
25 application tables
124.40 MB reference-d1.sql
6,088 local D1 commands executed successfully
```

PHOIBLE is complete locally and has a clean Git checkpoint:

```text
c990be8 Complete PHOIBLE integration for phonology engine
```

---

## LEXIBANK — COMPLETE

Lexibank Analysed v2.2/v2.2.1 is integrated and fully validated against its
physical source files.

Verified raw checkout:

```text
tags:   v2.2 and v2.2.1
commit: 46a2c4c63ae2cbb698cfd5ceb34cfee613eba8c4
```

Validated database counts:

```text
collections:                     6
contributions:                 134
languages/doculects:         5,501
concepts:                    3,205
phonemes:                    2,402
phoneme frequencies:       205,978
forms:                   1,740,092
unique segment tokens:       2,471
ordered segment rows:    9,657,998
feature definitions:            67
feature codes:                 177
feature values:            294,383
```

All raw rows and ordered segments pass exact source-to-SQLite SHA-256 round
trips. Foreign keys and SQLite integrity pass.

CLTS mapping results:

```text
physical CLTS references:                1,633
generated/unmaterialized CLTS refs:        769
generated refs used in forms:              762
occurrences of generated refs:          48,194
forms containing generated refs:        35,126
```

The SQLite → D1 SQL exporter includes all 39 application tables required at the
Lexibank milestone. A complete
678.74 MB export containing full real CLTS and Lexibank data was successfully
re-imported into a clean SQLite database in 48,379 statements. The local
Wrangler D1 import and website regression check also passed using statement-safe
parts.

---

## STEP 4 — SQLITE VALIDATED; LOCAL D1 IMPORT REPORTED COMPLETE

Apply the new schema once from the repository root:

```text
python -c "from pathlib import Path; import sqlite3; c=sqlite3.connect(r'data\compiled\reference.sqlite'); c.executescript(Path(r'database\schema\008_phonology_statistics.sql').read_text(encoding='utf-8')); c.close()"
```

Then build and validate the derived evidence:

```text
python scripts\analysis\build_phonology_statistics.py
python scripts\validation\validate_phonology_statistics.py
```

The verified PHOIBLE v2.0 observations now produce:

```text
analysis records:                         1
inventory profiles:                  3,020
segment prevalence rows:             6,350
segment co-occurrence rows:         570,320
```

The prevalence rows cover all 3,175 segments at both inventory and language
scope. Co-occurrence evidence includes:

```text
inventory observed pairs:           256,181
inventory expected absences:          1,931
language observed pairs:            311,088
language expected absences:           1,120
```

The builder and validator preserve the five repeated PHOIBLE source
observations while collapsing them to presence for inventory statistics. The
complete 43-table SQL export passes a clean SQLite round trip and is emitted in
Wrangler-safe parts no larger than 64 MiB.

---

# STEP 5 — VALIDATED ON USER DATABASE

Run the new Step 5 command once from the repository root:

```bat
python scripts\analysis\build_phonotactics.py
```

The command checks the imported source, applies `009_phonotactics.sql`, builds
five derived tables, validates all results against normalized form-token rows,
and commits only on success. Failure rolls back both schema and data changes,
preserving any previous Step 5 results. Existing source tables are never edited.
It prints progress every 100 doculects and saves a machine-readable report at
`data/compiled/phonotactics-report.json`. No extra Python dependencies are needed.
The database must already exist; a typo in the path cannot create an empty DB.

The tables contain:

- `phonotactic_analysis`: source fingerprint, method version, totals and policy.
- `phonotactic_profile`: per-doculect form/token and structural-marker counts.
- `phonotactic_token_stat`: token occurrences, form presence, literal initial/final counts.
- `phonotactic_bigram`: raw adjacent-token occurrences and form presence.
- `phonotactic_shape`: exact upstream CV-template/prosodic-string combinations.

Every source form is one observation. Duplicate pronunciations, variants and
loans are not silently deduplicated. Shared Glottocodes do not collapse distinct
doculects. Tones and unmaterialized/generated phonemes remain in the sequence;
`+` and `∼` remain structural/special tokens, not phonemes. A pair containing one
of those markers records literal adjacency to a marker; it is not a phoneme
cluster. No pairs skip markers, tones, or word edges. Initial/final counts use
literal form positions, even when a marker or tone occupies that position.
Consumers must join token types when requesting phoneme-only evidence.
Templates are word-shape evidence, not syllable parses or stress annotations.
Sampling is corpus-weighted within each doculect, not cross-linguistic prevalence.

The independent validator reads `lexibank_form_segment`, verifies token order
against raw `Segments`, and recomputes every derived row. It also checks total
coverage, source fingerprint, derived foreign keys and SQLite quick integrity.
Run it separately only when diagnosing or checking an existing build:

```bat
python scripts\validation\validate_phonotactics.py
```

Automated edge-case/rollback tests (small fixtures, no downloads):

```bat
python -m unittest discover -s tests -v
```

Developer validation: all 13 automated tests pass, including one-command CLI
reruns, transaction rollback, token corruption detection, and real SQL export
round trips for the 43- and 48-table milestones. `npm run lint` and
`npm run build` pass. The full 1,740,092-form corpus at Lexibank commit
`46a2c4c63ae2cbb698cfd5ceb34cfee613eba8c4` also passed build + independent
validation in an isolated minimal-input test database:

| Table | Rows |
| --- | ---: |
| phonotactic_analysis | 1 |
| phonotactic_profile | 5,501 |
| phonotactic_token_stat | 213,140 |
| phonotactic_bigram | 1,391,790 |
| phonotactic_shape | 320,393 |

The corpus test checked all 9,657,998 normalized token positions. It did not
rebuild the full semantic/reference imports or run D1. The user subsequently
confirmed the one-command Step 5 run passed on their full SQLite database. The optional developer
corpus test is `python tests/run_phonotactics_corpus.py`; it requires the local
Lexibank CLDF checkout and automatically deletes its isolated temporary DB.

## Faster development workflow — supersedes repeated full-D1 instructions

The local SQLite database is the authoritative analysis build. D1 is a serving
copy, not a required checkpoint after every analysis edit. Keep the working D1
copy and website running while offline analysis develops.

- Run build + focused independent validation automatically as one command.
- Keep logs/reports locally; ask the user for the final summary or an error only.
- Run full raw-source audits at source/version changes, not after every derived edit.
- Sync D1 at an API/UI integration milestone, or before deployment.
- Prefer dependency-aware updates of changed tables at that milestone. A safe
  incremental D1 updater is NOT implemented yet; do not pretend this exporter
  updates an existing database or run it over existing tables.
- Retain full export + clean import as a bootstrap/recovery/regression tool,
  not the default daily workflow. Do not delete local D1 state for Step 5.

The full exporter understands 43, 48, 52 and 57 application tables at the
pre-Step-5, Step-5, Step-6 and Step-7 milestones. Partial optional schemas are rejected.
The exporter is still a clean-bootstrap exporter, not an incremental updater.
No changes to Worker routes or the website are included here.

## Step 6 — bounded syllable-shape candidates — USER BUILD PASSED

Run once from the repository root:

```bat
python scripts\analysis\build_syllable_candidates.py
```

One command applies `010_syllable_candidates.sql`, builds the analysis, validates
every derived row, commits only on success, and writes
`data/compiled/syllable-candidates-report.json`. It uses the already imported
Lexibank tables, with no additional packages, downloads, Step 5 rebuild or D1
operations. Failures roll back both new schema and derived records. Step 5 and
all source data remain unchanged. Progress is printed every 100 doculects.

Model version `1.0.0` makes its assumptions explicit:

- Each eligible upstream `V` supplies one projected nucleus; `C` is peripheral.
- `T` is omitted only from this CV projection; original tones remain stored.
- `+` divides independent components for this model; it is not asserted to be
  a syllable boundary in actual speech.
- Intervocalic consonant runs admit every coda/onset split. There is no guessed
  maximal-onset rule, sonority constraint, ambisyllabicity or extrasyllabicity.
- One exclusion reason per whole form is assigned in this order: special token,
  explicitly syllabic C, explicitly non-syllabic simple V, unsupported CV class,
  empty component, component without V, adjacent Vs after removing T. Do not
  partially count the other components of an excluded form.
- A CLTS-described diphthong represented by one V token can supply one model
  nucleus. Adjacent V tokens are excluded rather than guessing hiatus/fusion.
- Unmarked syllabic consonants cannot be recovered from this source. Model
  eligibility is not a claim that every nucleus in actual speech is known.

The full-source CV inspection found exact alignment to the segmented tokens
in all 1,740,092 forms. Classes were C, V, T, + and 0; the unsupported class 0
appeared 112 times. Upstream creates CV classes with CLTS and prosodic strings
with LingPy; it does not write a gold syllable parse. Source implementation:
`data/raw/lexibank/lexibank_lexibank_analysed.py`.

Four new tables retain both coverage and ambiguity:

| Table | Meaning |
| --- | --- |
| syllable_analysis | Method policy, source fingerprint and source form count |
| syllable_profile | Total/eligible forms and projected/ambiguous nucleus positions per doculect |
| syllable_candidate | Possible and forced nucleus-position support for each onset/coda length |
| syllable_exclusion | Excluded-form counts by reason and doculect |

For instance, `VCV` admits `V.CV` and `VC.V`. It supplies two ambiguous nucleus
positions. Shape V has two possible slots, VC one, and CV one; none is forced.
In contrast, `CCVCC` supplies one forced CCVCC slot under this model.
`forced_slots` means forced by the stated projection assumptions, not observed
syllabification. `possible_slots` counts positions admitting a shape across
alternatives, so its sum can exceed the number of projected nuclei. Neither
count is a normalized probability or a claim about a language's phonotactics.
These candidates should inform later choices, not become hard generator rules.

The production builder calculates candidates from consonant-run lengths. Its
validator independently calculates them from allowable start/end positions
around each V, checks every row, source fingerprint, coverage, foreign keys and
SQLite quick integrity. Automated tests also exhaustively enumerate complete
word parses for short CV words; rollback, duplicate weighting, exclusions and
CLI execution are covered. Optional full-corpus developer check:

```bat
python tests/run_phonotactics_corpus.py --syllables
```

Developer verification: all 24 automated tests pass, including the 43/48/52
table exporter round trips and complete-partition enumeration for short CV
words. The actual pinned Lexibank corpus passed Step 6 build + independent
validation in isolated minimal source tables (not the user's full DB or D1):

| Measure | Count |
| --- | ---: |
| Source forms | 1,740,092 |
| Eligible forms | 1,510,076 |
| Excluded forms | 230,016 |
| Doculect profiles | 5,501 |
| Projected nucleus positions | 3,374,422 |
| Ambiguous positions | 2,621,826 |
| Candidate rows | 53,341 |

Exclusions were adjacent Vs (198,219 forms), vowel-free components (25,847),
explicitly syllabic consonants (2,754), special markers (1,919), explicitly
non-syllabic simple vowels (587), empty components (578), and unsupported
classes (112). These are model limitations/coverage, not invalid source data.

GitHub connection check for this session: the plugin reports installed/enabled,
but no GitHub repository tools were exposed, and a Git push dry run still lacked
configured credentials. No repository changes were pushed. Step 6 is delivered
as an incremental patch on top of the user's already-applied Step 5 patch.

## Step 7 — explicit prosody evidence — USER BUILD PASSED

Run once from the repository root:

```bat
python scripts\analysis\build_prosody_evidence.py
```

This command applies `011_prosody_evidence.sql`, builds and independently
validates the results in one transaction, then writes
`data/compiled/prosody-evidence-report.json`. A failed build/validation rolls back
new schema and derived data; previous results and source data remain intact.
It needs only Python's standard library and the already imported Lexibank
tables. It does not rebuild Steps 5/6, download data, or touch D1/the website.

Five tables preserve annotation evidence rather than diagnose language systems:

| Table | Meaning |
| --- | --- |
| prosody_analysis | Method version, source fingerprint, policy and total forms |
| prosody_profile | Per-doculect corpus size; system classification stays `unassessed` |
| prosody_annotation | IPA stress-marker coverage separately in Form, Value and Segments |
| prosody_token_feature | Exact token-to-description feature mapping |
| prosody_feature_stat | Token occurrences, form presence, distinct token counts and examples |

Stress-marker policy: count U+02C8 (`ˈ`) and U+02CC (`ˌ`) only. The
[official IPA chart](https://www.internationalphoneticassociation.org/content/ipa-chart)
identifies these as primary and secondary stress signs. A glyph occurrence
remains transcription evidence, not an automatically established stress system.
Do not infer stress from ASCII apostrophes, acute/grave accents, capitalization,
CV classes or prosodic strings. Source fields may differ and must not be summed
as disjoint form counts. Examples are the earliest matching local form IDs.

`observed` means the specified annotation occurs; `not_observed` means it was
not found in available input; `missing_input` means all values of that field in
the doculect are null, empty or whitespace-only. None means the language lacks
stress/tone/quantity. The build does not infer stress position, metrical rules,
tone-system complexity or phonemic length contrast.

Token features are explicit imported tone type and exact whitespace-delimited
words in Lexibank's CLTS-derived phoneme descriptions: `tone`, `primary-stress`,
`secondary-stress`, `long`, `mid-long`, `ultra-short`. The exact word `long`
does not match `mid-long`; repeated descriptors in complex tokens count once
per token occurrence. A compound/diphthong with length on one component is
evidence that the token carries a length descriptor, not a duration estimate.
Features can overlap within a token/form. Unmaterialized CLTS references remain
eligible through their preserved Lexibank descriptions. Boundary/special tokens
never become phonemes or receive descriptor-derived features.

The builder counts token multiplicities and field markers. Its independent
validator reconstructs exact feature membership, counts per-form matches and
marker positions, compares every result and example, checks source fingerprint,
coverage, foreign keys and SQLite quick integrity. Standalone validation is
available for diagnosis but is unnecessary after a successful build:

```bat
python scripts\validation\validate_prosody_evidence.py
```

Developer validation: 36 automated tests passed, including missing versus
unobserved evidence, repeated markers/tokens, compound descriptions, provenance,
rollback, deterministic reruns, CLI/standalone validation and 43/48/52/57-table
SQL export compatibility. All 1,740,092 forms and 9,657,998 tokens from the pinned
Lexibank release also passed in isolated minimal source tables. This is not a
run on the user's full database or a D1 validation. Results:

| Table | Rows |
| --- | ---: |
| prosody_analysis | 1 |
| prosody_profile | 5,501 |
| prosody_annotation | 33,006 |
| prosody_token_feature | 829 |
| prosody_feature_stat | 38,507 |

| Field | Forms with primary mark | Forms with secondary mark |
| --- | ---: | ---: |
| Form | 16,917 | 190 |
| Value | 9,429 | 216 |
| Segments | 0 | 0 |

Explicit token-feature form counts: standalone tone 216,783; attached tone
19,831; long 226,369; mid-long 2,851; ultra-short 1,462; primary/secondary
stress descriptors both 0. These are overlapping corpus observations, not
counts of tonal languages or contrastive systems. The absence of stress from
Segments must not erase the evidence retained in Form/Value.

Optional developer corpus test (not a required user command):

```bat
python tests/run_phonotactics_corpus.py --prosody
```

## Step 8 — offline phonology evaluator — USER DEMONSTRATION COMPLETE

Run from the project root:

```bat
python scripts\analysis\evaluate_phonology.py --demo
```

Expected completion message: `PHONOLOGY EVALUATION COMPLETE`. It writes
`data/compiled/phonology-evaluation.json`. The demonstration proposal is
`examples/phonology-proposal.json`; custom proposals use `--input path.json`.
The database is opened read-only inside a consistent read transaction. There
is no new schema, importer, builder, data download or D1 operation. The database
remains at 57 tables. The report file is the only normal output write.

Reusable evaluation logic is in `scripts/analysis/phonology_evaluator.py`.
The input contract, formulas, coverage and limitations are documented in
`docs/PHONOLOGY_EVALUATOR.md`. The demo compares against `northeuralex-eng`
explicitly; English is not a universal naturalism benchmark. Omitting a
reference doculect skips lexical comparisons rather than silently pooling data.

Inventory mapping uses exact PHOIBLE strings. The evaluator reports prevalence
and stored pair associations in the selected language/inventory scope, plus
inventory-size midrank percentiles when mapping is complete. It preserves
`not_stored` separately from stored expected absences. Unknown inventory tokens
are not treated as invalid sounds. Rare segments and unusual sizes receive no
automatic penalty.

Lexical components report selected-doculect adjacency and edge evidence, Step 6
candidate-shape support with exclusions, and Step 7 annotation evidence.
Known-pair observation fractions always include separate mapping coverage;
zero denominators and unsupported claims remain null/unknown. Prosody remains
unassessed as a language system. The overall score is null: there is no validated
calibration combining these different populations into a universal percentage.
Input consistency covers declared-token membership and structural-marker syntax,
not an assertion of grammaticality or successful syllabification.

Method metadata/fingerprints are included in reports. Missing/unsupported builds
and obvious source-count inconsistencies fail clearly. Full source scans are not
repeated during evaluation; it consumes the already validated build snapshots.

Step 8 verification: all 48 automated tests passed, including read-only execution,
unknown coverage, missing evidence, boundary handling and mismatched snapshots.
The optional `python tests/run_phonotactics_corpus.py --evaluate` integration
check also passed with the real PHOIBLE statistics and all 961 analysed forms
for `northeuralex-eng`. Steps 5–7 were built and validated for that doculect in
an isolated database. The demo mapped 10/10 inventory tokens, found 2/5 sample
adjacencies in the selected corpus, and reported 637/961 forms eligible for
syllable candidates. Evaluation alone took 0.073 seconds in the development
environment, excluding fixture construction. This is not a full user-database
or D1 round trip, and does not guarantee the same runtime elsewhere.

## Step 9 — website evaluator and compact local D1 snapshots

Implemented in `worker/phonology-evaluator.ts`, `worker/phonology-api.ts`,
`src/Phonology.tsx` and `scripts/analysis/sync_phonology_web.py`. Python remains
the reference evaluator. Existing Concept Explorer handlers are retained.

New routes: GET `/api/phonology/status`, POST `/api/phonology/evaluate`.
The same input limits, exact matching, component metrics and unknown semantics
apply. Responses add a serving snapshot ID to the evaluator report.

The serving snapshot contains the full PHOIBLE statistics, token catalog and
only explicitly selected doculect summaries. Default: `northeuralex-eng`. Other
doculects can be added with repeated `--doculect` options. No raw forms, token
positions or semantic data are imported by this sync. The source SQLite DB is
opened read-only. Three additional D1 serving tables hold versioned payload
chunks, import receipts and the active/previous snapshot pointer.

Imports use bounded 4 MiB SQL parts and resume completed parts by content hash.
The script reads back all summary payloads and checks their SHA-256 fingerprints
before switching the active snapshot in one statement. The Worker checks hashes
again on read and pins one immutable snapshot per request. Previous snapshots
are retained. No remote D1 access or public deployment occurs.

User commands after applying the Step 9 patch:

```bat
python scripts\analysis\sync_phonology_web.py
npm run dev
```

Expected sync banner: `PHONOLOGY WEB SYNC COMPLETE`. Open the Phonology tab and
evaluate the example. No source rebuild, manual SQL loop or full export required.
See `docs/PHONOLOGY_WEB.md` for recovery, adding doculects and verification scope.

Verification: 55 automated tests pass, including 15 complete report parity cases.
Local D1/Worker integration passes on source-derived fixtures and on real PHOIBLE
statistics plus the 961-form English doculect summaries. The latter serving
payload is 36.44 MiB in ten small parts. Production build and lint pass. Browser
verification remains pending: Chromium was absent and its download failed in
the execution environment. Do not describe browser interactions or the user's
installation as independently verified yet.

## STEP 10 — EXECUTABLE SOUND-SYSTEM SPECIFICATION IMPLEMENTED; LOCAL VALIDATION PENDING

Step 10 adds a strict, versioned JSON construction contract without changing
SQLite or D1. The implementation lives in:

```text
scripts/analysis/phonology_specification.py
scripts/analysis/define_sound_system.py
examples/sound-system-specification.json
tests/test_phonology_specification.py
docs/PHONOLOGY_SPECIFICATION.md
```

The canonical model records stable sound IDs and IPA displays, exact sound
classes, mapping status/features, onset/coda choices, `C*VC*` templates,
normalized weights, boundary/special/unknown-token policies, user-declared
prosody, evidence references, default provenance, and explicit deferred rule
families. Descriptive evidence is stored separately and never becomes a hard
construction rule implicitly.

Strict validation rejects unknown fields, duplicate or contradictory sound
identities/classes, invalid mappings, impossible templates, non-consonant
clusters, boundary/phoneme collisions, non-positive weights, prosody
contradictions, and unsupported extension rules. Canonical JSON round-trips
without information loss. SHA-256 namespaced decisions make syllable-count and
template choices reproducible for the same specification version, model
version, seed, namespace, and index.

The CLI reads no database and runs no build/import:

```bat
python scripts\analysis\define_sound_system.py --demo
```

Expected banner: `SOUND-SYSTEM SPECIFICATION VALID`. It writes only the
canonical compiled JSON and prints a deterministic preview.

## STEP 10 — COMPLETE

The user ran the bundled demonstration successfully. The canonical fingerprint
was `8b7801cc8f7e769d12b8e1e113584c8be843a2af33e6deb841c9fe5dfd6debb1`,
the deterministic preview completed, and all nine focused tests passed in
0.316 seconds. No SQLite or D1 operation was used.

## STEP 11 — SEEDED INVENTORY AND FORM GENERATION IMPLEMENTED; LOCAL VALIDATION PENDING

Step 11 adds:

```text
scripts/analysis/phonology_generator.py
scripts/analysis/generate_phonology.py
examples/phonology-generation-request.json
tests/test_phonology_generator.py
docs/PHONOLOGY_GENERATOR.md
```

The generator selects exact consonant/vowel/tone targets from Step 10's sound
pool, preserves required/excluded IDs, and uses PHOIBLE prevalence, stored pair
evidence, and shared features only as transparent proposal weights. It then
constructs bounded components from usable declared templates and exact allowed
onset/coda sequences. Components reset at `+`; special markers cannot become
phonemes. Duplicate rejection has an explicit attempt limit and failure.

Every form is independently checked against hard construction rules. The
generated proposal is passed to the existing evaluator in the same read-only
transaction; unusual valid outputs are retained with evidence gaps. Tone
realization, stress application, allophony, and harmony remain explicitly
deferred to Step 12.

# NEXT TASK

Pull and run only the Step 11 demo and focused tests:

```bat
git pull --ff-only origin main
python scripts\analysis\generate_phonology.py --demo
python -m unittest discover -s tests -p "test_phonology_generator.py" -v
```

Do not rebuild SQLite and do not rerun the D1 sync/import. If the demo and tests
pass, mark Step 11 complete. Then begin Step 12's explicit supported-rule gate
for stress/tone/length realization, allophony, and harmony.

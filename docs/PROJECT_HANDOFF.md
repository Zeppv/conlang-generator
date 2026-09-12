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

Phonology Engine Step 4 now has a schema, deterministic statistics builder, and
row-by-row validator. Its generated D1 SQL passes a clean SQLite round trip. A
final local Wrangler import must be run on the development machine.

The next task after that final D1 check is:

**PHONOLOGY ENGINE V1 — STEP 5: build phonotactics from Lexibank forms.**

Phonology Engine v1 order:

```text
CLTS — COMPLETE
↓
PHOIBLE — COMPLETE
↓
Lexibank — COMPLETE
↓
inventory statistics and phoneme dependencies — COMPLETE IN SQLITE;
LOCAL D1 CHECK PENDING
↓
phonotactics
↓
syllable structures
↓
stress and related phonological systems
↓
phonology naturalism scoring
↓
PHONOLOGY ENGINE V1
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

No dedicated CLTS, PHOIBLE, or phonology UI has been added yet.

Do not prioritize phonology UI until the underlying Phonology Engine v1 data/statistics pipeline is complete and clean.

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

To regenerate the local D1 reference database:

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
A final local Wrangler import of the Step 4 build is pending on the development
machine.

The public production site has intentionally not been deployed yet.

---

# Current Roadmap

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
inventory statistics and phoneme dependencies — COMPLETE IN SQLITE;
LOCAL D1 CHECK PENDING
↓
phonotactics
↓
syllable structures
↓
stress and related phonological systems
↓
phonology naturalism scoring
↓
PHONOLOGY ENGINE V1
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

## STEP 4 — COMPLETE IN SQLITE; LOCAL D1 CHECK PENDING

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

# NEXT TASK

First apply and build Step 4, regenerate the D1 export, and complete its final
local D1 check using the exact commands in the Cloudflare section.

Then begin:

**PHONOLOGY ENGINE V1 — STEP 5: phonotactics from Lexibank forms.**

Continue in this order:

```text
phonotactics
↓
syllable structures
↓
stress and related phonological systems
↓
phonology naturalism scoring
```

Do not start Grambank, UniMorph, Universal Dependencies, WOLD, Wiktionary,
grammar, or later roadmap stages until Phonology Engine v1 is complete.

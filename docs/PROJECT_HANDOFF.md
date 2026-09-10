# Conlang Generator — Project Handoff

## Project Goal

Build a highly naturalistic conlang generator that generates languages as systems with history rather than generating unrelated random words.

The eventual generator should model:

* semantic relationships between concepts
* related word families
* derivational morphology
* lexical gaps
* colexification
* phonology and phonotactics
* morphology
* grammar
* sound change
* semantic change
* grammaticalization
* analogy
* borrowing
* culture
* registers
* dialects
* language families
* historical evolution
* naturalism scoring

The fundamental principle is:

**The dictionary is the output of a language system and its history, not the starting point.**

---

# Current Milestone

## Semantic Engine v1 — COMPLETE

The system currently combines:

1. Concepticon
2. CLICS
3. Glottolog
4. Open English WordNet
5. DatSemShift

These sources are normalized into a local SQLite reference database.

The Semantic Engine now stores:

* standardized concepts
* semantic relationships
* cross-linguistic colexification evidence
* WordNet semantic relationships
* Concepticon-to-WordNet mappings
* DatSemShift semantic relationships
* pair-level semantic evidence scores
* directional semantic-change scores

The current Semantic Engine is intended to help decide whether concepts should plausibly:

* use the same lexical form
* share a root
* be morphologically derived from one another
* form compounds
* be semantically related but lexically separate
* historically develop from one meaning into another

Current scores are engineering evidence scores from 0–1. They are not claims that a particular percentage of natural languages exhibit a feature.

---

# Core Architecture

The current pipeline is:

Raw linguistic datasets

↓

Python import and analysis scripts

↓

`data/compiled/reference.sqlite`

↓

Python D1 exporter

↓

`data/compiled/reference-d1.sql`

↓

Cloudflare D1 local database

↓

Cloudflare Worker API

↓

React frontend

↓

Concept Explorer

The production architecture should ultimately remain approximately:

User → React frontend → Cloudflare Worker → D1 databases

The linguistic reference database should remain separate from future user-generated conlang/project data.

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

* real-language identifiers
* Glottocodes
* ISO codes
* language families
* ancestry
* geography

Current planned/reference version: Glottolog 5.3.

---

### Concepticon

Purpose:

* standardized language-independent concepts
* semantic fields
* ontological categories
* concept relationships

Current planned/reference version: Concepticon 3.4.

Concepticon IDs are external reference identifiers.

The application's internal `concept.id` is the true internal concept identifier.

---

### CLICS

Purpose:

* cross-linguistic colexification
* evidence that two meanings are expressed using the same lexical form in real languages
* language and family evidence counts

Current planned/reference dataset: CLICS4.

CLICS evidence contributes to lexical-link scoring.

---

### Open English WordNet

Purpose:

* semantic senses
* synsets
* hypernym/hyponym relationships
* part/whole relationships
* antonyms
* derivational relationships
* similar concepts
* entailment
* causation

Current planned/reference release: Open English WordNet 2025.

WordNet is not used as the master concept system.

Concepticon concepts are mapped to specific WordNet senses to avoid errors caused by ambiguous English words.

A curated Concepticon/WordNet bridge based on `Borin-2015-1532.tsv` is currently used.

---

### DatSemShift

Purpose:

* attested semantic relationships
* directional semantic relationships
* polysemy evidence
* derivational evidence
* language-family evidence

DatSemShift data is kept in dedicated tables and mapped to Concepticon concepts where possible.

Unmapped DatSemShift concepts are preserved rather than discarded.

---

# Downloaded But Not Yet Integrated

The following datasets exist locally but should remain untouched until their roadmap stage:

### CLTS

Future purpose:

* standardized IPA sounds
* sound features
* canonical phonetic representation

This is the next dataset to integrate.

---

### PHOIBLE

Future purpose:

* real phoneme inventories
* inventory sizes
* cross-linguistic phoneme occurrence
* phonological naturalism statistics

---

### Lexibank

Future purpose:

* real lexical forms
* segment sequences
* word lengths
* phonotactic statistics
* root-shape statistics
* cross-language lexical patterns

---

### Grambank

Future purpose:

* grammatical typology
* grammatical-feature correlations

Do not integrate until the grammar stage.

---

### NoRaRe

Future purpose:

* semantic norms, ratings, and concept properties

Not yet integrated.

---

### WOLD

Future purpose:

* borrowing
* loanword behavior
* borrowability by semantic domain
* donor/recipient patterns

Downloaded and extracted but not yet integrated.

---

# Not Yet Downloaded / Not Yet Needed

Do not add these until their roadmap stages:

* UniMorph
* Universal Dependencies
* Wiktionary/Wiktextract

---

# Database Schema

Current schema files:

```text
database/schema/001_reference.sql
database/schema/002_wordnet.sql
database/schema/003_datsemshift.sql
database/schema/004_semantic_scores.sql
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

## Import scripts

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

This should be the normal full semantic rebuild command.

---

```text
scripts/import/export_reference_to_d1.py
```

Converts `reference.sqlite` into D1-compatible SQL.

It contains a table allowlist/order and intentionally stops if the SQLite database contains an application table that the exporter does not know about.

Whenever a new database table is added, this exporter must be updated.

---

## Analysis scripts

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

## Validation scripts

Current WordNet/semantic validation scripts live in:

```text
scripts/validation/
```

Validation should continue to be expanded as new engines are added.

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

* search Concepticon concepts
* select a concept
* view its definition
* view semantic metadata
* view related concepts
* click related concepts
* see relationship source information

Relationship display currently prioritizes important evidence sources such as DatSemShift and WordNet before generic Concepticon links.

The frontend automatically selects the best/exact search result when appropriate.

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

then:

```text
npx wrangler d1 execute conlang-reference --local --file=./data/compiled/reference-d1.sql
```

then start the application:

```text
npm run dev
```

The public production site has intentionally not been deployed yet.

---

# Current Roadmap

## COMPLETE — Data Foundation

* project folder structure
* raw/staging/compiled data separation
* SQLite reference database
* Cloudflare D1 development setup
* React/Worker application
* Concept Explorer

## COMPLETE — Semantic Engine v1

* Concepticon
* CLICS
* Glottolog
* Open English WordNet
* curated WordNet mapping
* WordNet semantic edges
* DatSemShift
* semantic pair scoring
* directional semantic scoring

---

# NEXT — Phonology Engine

Integrate in this order:

```text
CLTS
 ↓
PHOIBLE
 ↓
Lexibank
 ↓
phoneme database
 ↓
inventory statistics
 ↓
phoneme co-occurrence
 ↓
phonotactic statistics
 ↓
syllable structures
 ↓
stress system
 ↓
phonology naturalism checks
 ↓
PHONOLOGY ENGINE V1
```

The Phonology Engine must not simply select random IPA symbols.

It should learn from real-language inventories and generate coherent sound systems.

Important future ideas:

* phoneme inventory size
* consonant/vowel balance
* natural classes
* phoneme dependencies
* markedness
* phonotactics
* onset/coda restrictions
* clusters
* syllable templates
* allophony
* stress
* tone
* vowel harmony
* consonant harmony
* frequency-weighted sound selection

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

The semantic engine should decide whether concepts:

* share one root
* share a derived root
* use a compound
* use the same word
* receive separate roots

The phonology engine decides what those roots can sound like.

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

4. Do not automatically accept ambiguous semantic mappings.

5. Do not generate every English dictionary word independently.

6. Prefer historical explanation over arbitrary irregularity.

7. Preserve old forms instead of overwriting them.

8. Distinguish real linguistic evidence from generator heuristics.

9. Keep reference linguistic data separate from future user data.

10. Keep the generator customizable. Naturalism should guide the user, not prevent deliberate unusual language design.

---

# Exact Current Stopping Point

Semantic Engine v1 has been completed and tested.

The next task is:

**PHONOLOGY ENGINE V1 — STEP 1: integrate CLTS.**

Before writing CLTS import code, inspect the actual downloaded CLTS directory and released files so the importer matches the user's installed dataset rather than assuming filenames.

Then integrate PHOIBLE.

Then use Lexibank to derive lexical and phonotactic statistics.

Do not start Grambank, UniMorph, UD, WOLD, or Wiktionary during the Phonology Engine stage.

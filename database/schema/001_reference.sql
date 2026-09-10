PRAGMA foreign_keys = ON;

CREATE TABLE reference_source (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT,
    license TEXT,
    source_url TEXT
);

CREATE TABLE concept (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    concepticon_id TEXT UNIQUE,
    gloss TEXT NOT NULL,
    definition TEXT,
    semantic_field TEXT,
    ontological_category TEXT,
    replacement_concepticon_id TEXT,
    source_id TEXT NOT NULL,
    FOREIGN KEY (source_id) REFERENCES reference_source(id)
);

CREATE INDEX idx_concept_gloss
ON concept(gloss COLLATE NOCASE);

CREATE TABLE relation_type (
    id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    description TEXT,
    inverse_id TEXT,
    PRIMARY KEY (id, source_id)
);

CREATE TABLE concept_relation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    source_concept_id INTEGER NOT NULL,
    target_concept_id INTEGER NOT NULL,

    relation_type TEXT NOT NULL,
    directed INTEGER NOT NULL DEFAULT 0,

    form_count INTEGER,
    variety_count INTEGER,
    language_count INTEGER,
    family_count INTEGER,

    variety_weight REAL,
    language_weight REAL,
    family_weight REAL,

    source_id TEXT NOT NULL,
    source_record_id TEXT,
    relation_description TEXT,

    FOREIGN KEY (source_concept_id) REFERENCES concept(id),
    FOREIGN KEY (target_concept_id) REFERENCES concept(id),
    FOREIGN KEY (source_id) REFERENCES reference_source(id)
);

CREATE INDEX idx_relation_source
ON concept_relation(source_concept_id);

CREATE INDEX idx_relation_target
ON concept_relation(target_concept_id);

CREATE INDEX idx_relation_type
ON concept_relation(relation_type);

CREATE TABLE reference_language (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    glottocode TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    iso639_3 TEXT,
    level TEXT,
    macroarea TEXT,

    latitude REAL,
    longitude REAL,

    family_glottocode TEXT,
    parent_language_glottocode TEXT,
    is_isolate INTEGER,

    source_id TEXT NOT NULL,

    FOREIGN KEY (source_id) REFERENCES reference_source(id)
);

CREATE INDEX idx_language_name
ON reference_language(name COLLATE NOCASE);

CREATE INDEX idx_language_family
ON reference_language(family_glottocode);
CREATE TABLE wordnet_synset (
    id TEXT PRIMARY KEY,

    ili TEXT,
    pos TEXT NOT NULL,
    definition TEXT,

    source_id TEXT NOT NULL,

    FOREIGN KEY (source_id)
        REFERENCES reference_source(id)
);


CREATE INDEX idx_wordnet_synset_ili
ON wordnet_synset(ili);


CREATE INDEX idx_wordnet_synset_pos
ON wordnet_synset(pos);



CREATE TABLE wordnet_lemma (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    synset_id TEXT NOT NULL,
    lemma TEXT NOT NULL,

    FOREIGN KEY (synset_id)
        REFERENCES wordnet_synset(id),

    UNIQUE (synset_id, lemma)
);


CREATE INDEX idx_wordnet_lemma_text
ON wordnet_lemma(lemma COLLATE NOCASE);



CREATE TABLE wordnet_sense (
    id TEXT PRIMARY KEY,

    synset_id TEXT NOT NULL,
    sense_key TEXT,

    lemma TEXT NOT NULL,
    pos TEXT NOT NULL,

    FOREIGN KEY (synset_id)
        REFERENCES wordnet_synset(id)
);


CREATE UNIQUE INDEX idx_wordnet_sense_key
ON wordnet_sense(sense_key)
WHERE sense_key IS NOT NULL;



CREATE TABLE wordnet_relation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    source_synset_id TEXT NOT NULL,
    target_synset_id TEXT NOT NULL,

    relation_type TEXT NOT NULL,

    FOREIGN KEY (source_synset_id)
        REFERENCES wordnet_synset(id),

    FOREIGN KEY (target_synset_id)
        REFERENCES wordnet_synset(id),

    UNIQUE (
        source_synset_id,
        target_synset_id,
        relation_type
    )
);


CREATE INDEX idx_wordnet_relation_source
ON wordnet_relation(source_synset_id);


CREATE INDEX idx_wordnet_relation_target
ON wordnet_relation(target_synset_id);


CREATE INDEX idx_wordnet_relation_type
ON wordnet_relation(relation_type);



CREATE TABLE wordnet_sense_relation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    source_sense_id TEXT NOT NULL,
    target_sense_id TEXT NOT NULL,

    relation_type TEXT NOT NULL,

    FOREIGN KEY (source_sense_id)
        REFERENCES wordnet_sense(id),

    FOREIGN KEY (target_sense_id)
        REFERENCES wordnet_sense(id),

    UNIQUE (
        source_sense_id,
        target_sense_id,
        relation_type
    )
);


CREATE INDEX idx_wordnet_sense_relation_source
ON wordnet_sense_relation(source_sense_id);



CREATE TABLE concept_wordnet_mapping (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    concept_id INTEGER NOT NULL,

    synset_id TEXT NOT NULL,
    sense_id TEXT,
    sense_key TEXT,

    mapping_method TEXT NOT NULL,

    mapping_status TEXT NOT NULL
        DEFAULT 'candidate',

    confidence REAL,

    source_note TEXT,

    FOREIGN KEY (concept_id)
        REFERENCES concept(id),

    FOREIGN KEY (synset_id)
        REFERENCES wordnet_synset(id),

    FOREIGN KEY (sense_id)
        REFERENCES wordnet_sense(id),

    UNIQUE (
        concept_id,
        synset_id,
        mapping_method
    )
);


CREATE INDEX idx_concept_wordnet_concept
ON concept_wordnet_mapping(concept_id);


CREATE INDEX idx_concept_wordnet_synset
ON concept_wordnet_mapping(synset_id);


CREATE INDEX idx_concept_wordnet_status
ON concept_wordnet_mapping(mapping_status);
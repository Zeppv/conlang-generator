CREATE TABLE datsemshift_concept (
    id TEXT PRIMARY KEY,

    name TEXT NOT NULL,

    concepticon_id TEXT,

    concept_id INTEGER,

    gloss_in_source TEXT,
    definition TEXT,
    alias TEXT,
    domain TEXT,

    source_id TEXT NOT NULL,

    FOREIGN KEY (concept_id)
        REFERENCES concept(id),

    FOREIGN KEY (source_id)
        REFERENCES reference_source(id)
);


CREATE INDEX idx_datsemshift_concepticon
ON datsemshift_concept(concepticon_id);


CREATE INDEX idx_datsemshift_concept
ON datsemshift_concept(concept_id);



CREATE TABLE datsemshift_relation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    source_parameter_id TEXT NOT NULL,
    target_parameter_id TEXT NOT NULL,

    source_concept_id INTEGER,
    target_concept_id INTEGER,

    directed INTEGER NOT NULL,

    evidence_type TEXT NOT NULL,

    realization_count INTEGER NOT NULL
        DEFAULT 0,

    family_count INTEGER NOT NULL
        DEFAULT 0,

    lexeme_ids_json TEXT,
    shift_ids_json TEXT,
    family_ids_json TEXT,

    source_id TEXT NOT NULL,

    FOREIGN KEY (source_parameter_id)
        REFERENCES datsemshift_concept(id),

    FOREIGN KEY (target_parameter_id)
        REFERENCES datsemshift_concept(id),

    FOREIGN KEY (source_concept_id)
        REFERENCES concept(id),

    FOREIGN KEY (target_concept_id)
        REFERENCES concept(id),

    FOREIGN KEY (source_id)
        REFERENCES reference_source(id),

    UNIQUE (
        source_parameter_id,
        target_parameter_id,
        directed,
        evidence_type
    )
);


CREATE INDEX idx_datsemshift_relation_source
ON datsemshift_relation(source_parameter_id);


CREATE INDEX idx_datsemshift_relation_target
ON datsemshift_relation(target_parameter_id);


CREATE INDEX idx_datsemshift_relation_concepts
ON datsemshift_relation(
    source_concept_id,
    target_concept_id
);


CREATE INDEX idx_datsemshift_relation_type
ON datsemshift_relation(evidence_type);
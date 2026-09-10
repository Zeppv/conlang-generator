CREATE TABLE semantic_pair_score (
    concept_a_id INTEGER NOT NULL,
    concept_b_id INTEGER NOT NULL,

    relatedness_score REAL NOT NULL
        DEFAULT 0,

    lexical_link_score REAL NOT NULL
        DEFAULT 0,

    colexification_score REAL NOT NULL
        DEFAULT 0,

    derivation_score REAL NOT NULL
        DEFAULT 0,

    datsemshift_score REAL NOT NULL
        DEFAULT 0,

    wordnet_score REAL NOT NULL
        DEFAULT 0,

    evidence_sources TEXT,

    PRIMARY KEY (
        concept_a_id,
        concept_b_id
    ),

    FOREIGN KEY (concept_a_id)
        REFERENCES concept(id),

    FOREIGN KEY (concept_b_id)
        REFERENCES concept(id)
);


CREATE INDEX idx_semantic_pair_a
ON semantic_pair_score(concept_a_id);


CREATE INDEX idx_semantic_pair_b
ON semantic_pair_score(concept_b_id);



CREATE TABLE semantic_direction_score (
    source_concept_id INTEGER NOT NULL,
    target_concept_id INTEGER NOT NULL,

    shift_score REAL NOT NULL
        DEFAULT 0,

    polysemy_score REAL NOT NULL
        DEFAULT 0,

    derivation_score REAL NOT NULL
        DEFAULT 0,

    evidence_family_count INTEGER NOT NULL
        DEFAULT 0,

    evidence_sources TEXT,

    PRIMARY KEY (
        source_concept_id,
        target_concept_id
    ),

    FOREIGN KEY (source_concept_id)
        REFERENCES concept(id),

    FOREIGN KEY (target_concept_id)
        REFERENCES concept(id)
);


CREATE INDEX idx_semantic_direction_source
ON semantic_direction_score(
    source_concept_id
);


CREATE INDEX idx_semantic_direction_target
ON semantic_direction_score(
    target_concept_id
);
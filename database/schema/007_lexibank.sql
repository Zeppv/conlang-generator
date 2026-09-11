CREATE TABLE lexibank_collection (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    variety_count INTEGER NOT NULL,
    glottocode_count INTEGER NOT NULL,
    concept_count INTEGER NOT NULL,
    form_count INTEGER NOT NULL,
    source_id TEXT NOT NULL,
    FOREIGN KEY (source_id) REFERENCES reference_source(id)
);


CREATE TABLE lexibank_contribution (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    contributor TEXT,
    citation TEXT NOT NULL,
    collection_ids_raw TEXT NOT NULL,
    glottocode_count INTEGER NOT NULL,
    doculect_count INTEGER NOT NULL,
    concept_count INTEGER NOT NULL,
    sense_count INTEGER NOT NULL,
    form_count INTEGER NOT NULL,
    source_keys TEXT NOT NULL,
    source_id TEXT NOT NULL,
    FOREIGN KEY (source_id) REFERENCES reference_source(id)
);


CREATE TABLE lexibank_contribution_collection (
    contribution_id TEXT NOT NULL,
    collection_id TEXT NOT NULL,
    PRIMARY KEY (contribution_id, collection_id),
    FOREIGN KEY (contribution_id) REFERENCES lexibank_contribution(id),
    FOREIGN KEY (collection_id) REFERENCES lexibank_collection(id)
);


CREATE INDEX idx_lexibank_contribution_collection_collection
ON lexibank_contribution_collection(collection_id);


CREATE TABLE lexibank_language (
    id INTEGER PRIMARY KEY,
    lexibank_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    macroarea TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    glottocode TEXT NOT NULL,
    iso639_3 TEXT,
    contribution_id TEXT NOT NULL,
    declared_form_count INTEGER NOT NULL,
    forms_with_sounds_count INTEGER NOT NULL,
    concept_count INTEGER NOT NULL,
    collections_raw TEXT NOT NULL,
    is_lexicore INTEGER NOT NULL CHECK (is_lexicore IN (0, 1)),
    is_clicscore INTEGER NOT NULL CHECK (is_clicscore IN (0, 1)),
    is_cogcore INTEGER NOT NULL CHECK (is_cogcore IN (0, 1)),
    is_protocore INTEGER NOT NULL CHECK (is_protocore IN (0, 1)),
    is_selexion INTEGER NOT NULL CHECK (is_selexion IN (0, 1)),
    subgroup TEXT,
    family TEXT,
    family_in_data TEXT,
    reference_language_id INTEGER NOT NULL,
    source_id TEXT NOT NULL,
    FOREIGN KEY (contribution_id) REFERENCES lexibank_contribution(id),
    FOREIGN KEY (reference_language_id) REFERENCES reference_language(id),
    FOREIGN KEY (source_id) REFERENCES reference_source(id)
);


CREATE INDEX idx_lexibank_language_glottocode
ON lexibank_language(glottocode);


CREATE INDEX idx_lexibank_language_contribution
ON lexibank_language(contribution_id);


CREATE INDEX idx_lexibank_language_reference
ON lexibank_language(reference_language_id);


CREATE TABLE lexibank_language_collection (
    language_id INTEGER NOT NULL,
    collection_id TEXT NOT NULL,
    PRIMARY KEY (language_id, collection_id),
    FOREIGN KEY (language_id) REFERENCES lexibank_language(id),
    FOREIGN KEY (collection_id) REFERENCES lexibank_collection(id)
);


CREATE INDEX idx_lexibank_language_collection_collection
ON lexibank_language_collection(collection_id);


CREATE TABLE lexibank_concept (
    id INTEGER PRIMARY KEY,
    lexibank_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    column_spec TEXT,
    concepticon_id TEXT NOT NULL UNIQUE,
    concepticon_gloss TEXT NOT NULL,
    central_concept TEXT,
    core_concept TEXT,
    reference_concept_id INTEGER NOT NULL,
    source_id TEXT NOT NULL,
    FOREIGN KEY (reference_concept_id) REFERENCES concept(id),
    FOREIGN KEY (source_id) REFERENCES reference_source(id)
);


CREATE INDEX idx_lexibank_concept_reference
ON lexibank_concept(reference_concept_id);


CREATE TABLE lexibank_phoneme (
    id INTEGER PRIMARY KEY,
    lexibank_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    column_spec TEXT,
    clts_reference TEXT NOT NULL UNIQUE,
    clts_sound_id TEXT,
    clts_mapping_status TEXT NOT NULL
        CHECK (clts_mapping_status IN ('mapped', 'unmaterialized')),
    clts_mapping_method TEXT NOT NULL
        CHECK (clts_mapping_method IN (
            'exact_clts_reference',
            'lexibank_generated_reference'
        )),
    source_id TEXT NOT NULL,
    FOREIGN KEY (clts_sound_id) REFERENCES clts_sound(id),
    FOREIGN KEY (source_id) REFERENCES reference_source(id)
);


CREATE INDEX idx_lexibank_phoneme_clts
ON lexibank_phoneme(clts_sound_id);


CREATE INDEX idx_lexibank_phoneme_mapping_status
ON lexibank_phoneme(clts_mapping_status);


CREATE TABLE lexibank_frequency (
    id INTEGER PRIMARY KEY,
    source_row_number INTEGER NOT NULL UNIQUE,
    lexibank_id TEXT NOT NULL UNIQUE,
    language_id INTEGER NOT NULL,
    phoneme_id INTEGER NOT NULL,
    occurrence_count INTEGER NOT NULL,
    code_id TEXT,
    comment TEXT,
    source_contribution_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    FOREIGN KEY (language_id) REFERENCES lexibank_language(id),
    FOREIGN KEY (phoneme_id) REFERENCES lexibank_phoneme(id),
    FOREIGN KEY (source_contribution_id) REFERENCES lexibank_contribution(id),
    FOREIGN KEY (source_id) REFERENCES reference_source(id)
);


CREATE INDEX idx_lexibank_frequency_language
ON lexibank_frequency(language_id);


CREATE INDEX idx_lexibank_frequency_phoneme
ON lexibank_frequency(phoneme_id);


CREATE TABLE lexibank_form (
    id INTEGER PRIMARY KEY,
    source_row_number INTEGER NOT NULL UNIQUE,
    lexibank_id TEXT NOT NULL UNIQUE,
    language_id INTEGER NOT NULL,
    concept_id INTEGER NOT NULL,
    form TEXT NOT NULL,
    segments TEXT NOT NULL,
    comment TEXT,
    source_contribution_id TEXT NOT NULL,
    value TEXT,
    local_id TEXT,
    graphemes TEXT,
    profile TEXT,
    cognacy TEXT,
    loan TEXT,
    cv_template TEXT NOT NULL,
    prosodic_string TEXT NOT NULL,
    dolgo_sound_classes TEXT NOT NULL,
    sca_sound_classes TEXT NOT NULL,
    segment_count INTEGER NOT NULL,
    source_id TEXT NOT NULL,
    FOREIGN KEY (language_id) REFERENCES lexibank_language(id),
    FOREIGN KEY (concept_id) REFERENCES lexibank_concept(id),
    FOREIGN KEY (source_contribution_id) REFERENCES lexibank_contribution(id),
    FOREIGN KEY (source_id) REFERENCES reference_source(id)
);


CREATE INDEX idx_lexibank_form_language
ON lexibank_form(language_id);


CREATE INDEX idx_lexibank_form_concept
ON lexibank_form(concept_id);


CREATE INDEX idx_lexibank_form_contribution
ON lexibank_form(source_contribution_id);


CREATE TABLE lexibank_segment_token (
    id INTEGER PRIMARY KEY,
    token TEXT NOT NULL UNIQUE,
    token_type TEXT NOT NULL
        CHECK (token_type IN ('phoneme', 'tone', 'boundary', 'special')),
    phoneme_id INTEGER,
    clts_sound_id TEXT,
    source_id TEXT NOT NULL,
    FOREIGN KEY (phoneme_id) REFERENCES lexibank_phoneme(id),
    FOREIGN KEY (clts_sound_id) REFERENCES clts_sound(id),
    FOREIGN KEY (source_id) REFERENCES reference_source(id),
    CHECK (
        (token_type = 'phoneme' AND phoneme_id IS NOT NULL)
        OR
        (token_type = 'tone' AND phoneme_id IS NULL AND clts_sound_id IS NOT NULL)
        OR
        (token_type IN ('boundary', 'special')
            AND phoneme_id IS NULL
            AND clts_sound_id IS NULL)
    )
);


CREATE INDEX idx_lexibank_segment_token_type
ON lexibank_segment_token(token_type);


CREATE INDEX idx_lexibank_segment_token_phoneme
ON lexibank_segment_token(phoneme_id);


CREATE INDEX idx_lexibank_segment_token_clts
ON lexibank_segment_token(clts_sound_id);


CREATE TABLE lexibank_form_segment (
    form_id INTEGER NOT NULL,
    segment_order INTEGER NOT NULL CHECK (segment_order > 0),
    token_id INTEGER NOT NULL,
    PRIMARY KEY (form_id, segment_order),
    FOREIGN KEY (form_id) REFERENCES lexibank_form(id),
    FOREIGN KEY (token_id) REFERENCES lexibank_segment_token(id)
);


CREATE INDEX idx_lexibank_form_segment_token
ON lexibank_form_segment(token_id);


CREATE TABLE lexibank_feature (
    feature_domain TEXT NOT NULL
        CHECK (feature_domain IN ('phonology', 'lexicon')),
    id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    column_spec TEXT,
    feature_spec TEXT,
    source_id TEXT NOT NULL,
    PRIMARY KEY (feature_domain, id),
    FOREIGN KEY (source_id) REFERENCES reference_source(id)
);


CREATE TABLE lexibank_feature_code (
    feature_domain TEXT NOT NULL
        CHECK (feature_domain IN ('phonology', 'lexicon')),
    id TEXT NOT NULL,
    parameter_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    source_id TEXT NOT NULL,
    PRIMARY KEY (feature_domain, id),
    FOREIGN KEY (feature_domain, parameter_id)
        REFERENCES lexibank_feature(feature_domain, id),
    FOREIGN KEY (source_id) REFERENCES reference_source(id)
);


CREATE INDEX idx_lexibank_feature_code_parameter
ON lexibank_feature_code(feature_domain, parameter_id);


CREATE TABLE lexibank_feature_value (
    id INTEGER PRIMARY KEY,
    feature_domain TEXT NOT NULL
        CHECK (feature_domain IN ('phonology', 'lexicon')),
    source_row_number INTEGER NOT NULL,
    lexibank_id TEXT NOT NULL,
    language_id INTEGER NOT NULL,
    parameter_id TEXT NOT NULL,
    value TEXT NOT NULL,
    code_id TEXT,
    comment TEXT,
    source_contribution_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    UNIQUE (feature_domain, source_row_number),
    UNIQUE (feature_domain, lexibank_id),
    FOREIGN KEY (language_id) REFERENCES lexibank_language(id),
    FOREIGN KEY (feature_domain, parameter_id)
        REFERENCES lexibank_feature(feature_domain, id),
    FOREIGN KEY (feature_domain, code_id)
        REFERENCES lexibank_feature_code(feature_domain, id),
    FOREIGN KEY (source_contribution_id) REFERENCES lexibank_contribution(id),
    FOREIGN KEY (source_id) REFERENCES reference_source(id)
);


CREATE INDEX idx_lexibank_feature_value_language
ON lexibank_feature_value(language_id);


CREATE INDEX idx_lexibank_feature_value_parameter
ON lexibank_feature_value(feature_domain, parameter_id);


CREATE INDEX idx_lexibank_feature_value_code
ON lexibank_feature_value(feature_domain, code_id);

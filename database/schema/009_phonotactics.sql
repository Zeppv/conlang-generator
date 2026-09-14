-- Raw-token evidence, not inferred syllables or universal probabilities.
CREATE TABLE IF NOT EXISTS phonotactic_analysis (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES reference_source(id),
    method_version TEXT NOT NULL,
    source_digest TEXT NOT NULL,
    form_count INTEGER NOT NULL CHECK (form_count > 0),
    token_count INTEGER NOT NULL CHECK (token_count > 0),
    notes TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS phonotactic_profile (
    language_id INTEGER PRIMARY KEY REFERENCES lexibank_language(id),
    analysis_id TEXT NOT NULL REFERENCES phonotactic_analysis(id),
    form_count INTEGER NOT NULL CHECK (form_count > 0),
    token_count INTEGER NOT NULL CHECK (token_count >= form_count),
    boundary_count INTEGER NOT NULL CHECK (boundary_count >= 0),
    special_count INTEGER NOT NULL CHECK (special_count >= 0)
);
CREATE TABLE IF NOT EXISTS phonotactic_token_stat (
    language_id INTEGER NOT NULL REFERENCES phonotactic_profile(language_id),
    token_id INTEGER NOT NULL REFERENCES lexibank_segment_token(id),
    occurrence_count INTEGER NOT NULL CHECK (occurrence_count > 0),
    form_count INTEGER NOT NULL CHECK (form_count > 0 AND form_count <= occurrence_count),
    initial_count INTEGER NOT NULL CHECK (initial_count >= 0 AND initial_count <= form_count),
    final_count INTEGER NOT NULL CHECK (final_count >= 0 AND final_count <= form_count),
    PRIMARY KEY (language_id, token_id)
);
CREATE TABLE IF NOT EXISTS phonotactic_bigram (
    language_id INTEGER NOT NULL REFERENCES phonotactic_profile(language_id),
    left_token_id INTEGER NOT NULL REFERENCES lexibank_segment_token(id),
    right_token_id INTEGER NOT NULL REFERENCES lexibank_segment_token(id),
    occurrence_count INTEGER NOT NULL CHECK (occurrence_count > 0),
    form_count INTEGER NOT NULL CHECK (form_count > 0 AND form_count <= occurrence_count),
    PRIMARY KEY (language_id, left_token_id, right_token_id)
);
CREATE TABLE IF NOT EXISTS phonotactic_shape (
    language_id INTEGER NOT NULL REFERENCES phonotactic_profile(language_id),
    cv_template TEXT NOT NULL,
    prosodic_string TEXT NOT NULL,
    form_count INTEGER NOT NULL CHECK (form_count > 0),
    PRIMARY KEY (language_id, cv_template, prosodic_string)
);

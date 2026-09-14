-- Annotation coverage and explicit token features; not language-system diagnoses.
CREATE TABLE IF NOT EXISTS prosody_analysis (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES reference_source(id),
    method_version TEXT NOT NULL,
    source_digest TEXT NOT NULL,
    form_count INTEGER NOT NULL CHECK (form_count > 0),
    notes TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS prosody_profile (
    language_id INTEGER PRIMARY KEY REFERENCES lexibank_language(id),
    analysis_id TEXT NOT NULL REFERENCES prosody_analysis(id),
    form_count INTEGER NOT NULL CHECK (form_count > 0),
    token_count INTEGER NOT NULL CHECK (token_count >= form_count),
    system_classification TEXT NOT NULL CHECK (system_classification = 'unassessed')
);
CREATE TABLE IF NOT EXISTS prosody_annotation (
    language_id INTEGER NOT NULL REFERENCES prosody_profile(language_id),
    source_field TEXT NOT NULL CHECK (source_field IN ('form', 'value', 'segments')),
    marker TEXT NOT NULL CHECK (marker IN ('primary_stress', 'secondary_stress')),
    available_forms INTEGER NOT NULL CHECK (available_forms >= 0),
    marked_forms INTEGER NOT NULL CHECK (marked_forms BETWEEN 0 AND available_forms),
    marker_occurrences INTEGER NOT NULL CHECK (marker_occurrences >= marked_forms),
    status TEXT NOT NULL CHECK (status IN ('observed', 'not_observed', 'missing_input')),
    example_form_id INTEGER REFERENCES lexibank_form(id),
    PRIMARY KEY (language_id, source_field, marker),
    CHECK ((marked_forms > 0 AND status = 'observed' AND example_form_id IS NOT NULL)
        OR (marked_forms = 0 AND marker_occurrences = 0 AND example_form_id IS NULL
            AND ((available_forms > 0 AND status = 'not_observed')
                OR (available_forms = 0 AND status = 'missing_input'))))
);
CREATE TABLE IF NOT EXISTS prosody_token_feature (
    token_id INTEGER NOT NULL REFERENCES lexibank_segment_token(id),
    feature TEXT NOT NULL CHECK (feature IN (
        'standalone_tone','attached_tone','primary_stress','secondary_stress',
        'long','mid_long','ultra_short')),
    PRIMARY KEY (token_id, feature)
);
CREATE TABLE IF NOT EXISTS prosody_feature_stat (
    language_id INTEGER NOT NULL REFERENCES prosody_profile(language_id),
    feature TEXT NOT NULL CHECK (feature IN (
        'standalone_tone','attached_tone','primary_stress','secondary_stress',
        'long','mid_long','ultra_short')),
    token_occurrences INTEGER NOT NULL CHECK (token_occurrences >= 0),
    form_count INTEGER NOT NULL CHECK (form_count BETWEEN 0 AND token_occurrences),
    distinct_tokens INTEGER NOT NULL CHECK (distinct_tokens BETWEEN 0 AND token_occurrences),
    status TEXT NOT NULL CHECK (status IN ('observed','not_observed')),
    example_form_id INTEGER REFERENCES lexibank_form(id),
    PRIMARY KEY (language_id, feature),
    CHECK ((token_occurrences > 0 AND form_count > 0 AND distinct_tokens > 0
            AND status = 'observed' AND example_form_id IS NOT NULL)
        OR (token_occurrences = 0 AND form_count = 0 AND distinct_tokens = 0
            AND status = 'not_observed' AND example_form_id IS NULL))
);

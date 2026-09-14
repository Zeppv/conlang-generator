-- A bounded CV projection model; not gold syllabification.
CREATE TABLE IF NOT EXISTS syllable_analysis (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES reference_source(id),
    method_version TEXT NOT NULL,
    source_digest TEXT NOT NULL,
    form_count INTEGER NOT NULL CHECK (form_count > 0),
    notes TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS syllable_profile (
    language_id INTEGER PRIMARY KEY REFERENCES lexibank_language(id),
    analysis_id TEXT NOT NULL REFERENCES syllable_analysis(id),
    form_count INTEGER NOT NULL CHECK (form_count > 0),
    eligible_forms INTEGER NOT NULL CHECK (eligible_forms BETWEEN 0 AND form_count),
    projected_nuclei INTEGER NOT NULL CHECK (projected_nuclei >= eligible_forms),
    ambiguous_nuclei INTEGER NOT NULL CHECK (ambiguous_nuclei BETWEEN 0 AND projected_nuclei)
);
CREATE TABLE IF NOT EXISTS syllable_candidate (
    language_id INTEGER NOT NULL REFERENCES syllable_profile(language_id),
    onset_length INTEGER NOT NULL CHECK (onset_length >= 0),
    coda_length INTEGER NOT NULL CHECK (coda_length >= 0),
    possible_slots INTEGER NOT NULL CHECK (possible_slots > 0),
    forced_slots INTEGER NOT NULL CHECK (forced_slots BETWEEN 0 AND possible_slots),
    PRIMARY KEY (language_id, onset_length, coda_length)
);
CREATE TABLE IF NOT EXISTS syllable_exclusion (
    language_id INTEGER NOT NULL REFERENCES syllable_profile(language_id),
    reason TEXT NOT NULL CHECK (reason IN (
        'special_marker', 'syllabic_consonant', 'non_syllabic_vowel',
        'unsupported_class', 'empty_component', 'no_vowel', 'adjacent_vowels'
    )),
    form_count INTEGER NOT NULL CHECK (form_count > 0),
    PRIMARY KEY (language_id, reason)
);

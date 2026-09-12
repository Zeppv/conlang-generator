CREATE TABLE phonology_analysis (
    id TEXT PRIMARY KEY,
    method_version TEXT NOT NULL,
    inventory_unit_count INTEGER NOT NULL,
    language_unit_count INTEGER NOT NULL,
    inventory_without_glottocode_count INTEGER NOT NULL,
    segment_count INTEGER NOT NULL,
    observation_count INTEGER NOT NULL,
    repeated_observation_count INTEGER NOT NULL,
    expected_absence_minimum REAL NOT NULL,
    notes TEXT NOT NULL,
    source_id TEXT NOT NULL,
    FOREIGN KEY (source_id) REFERENCES reference_source(id)
);

CREATE TABLE phonology_inventory_profile (
    analysis_id TEXT NOT NULL,
    inventory_id INTEGER NOT NULL,
    observation_count INTEGER NOT NULL,
    distinct_segment_count INTEGER NOT NULL,
    consonant_count INTEGER NOT NULL,
    vowel_count INTEGER NOT NULL,
    tone_count INTEGER NOT NULL,
    explicit_non_marginal_count INTEGER NOT NULL,
    marginal_only_count INTEGER NOT NULL,
    unknown_marginality_count INTEGER NOT NULL,
    mapped_clts_count INTEGER NOT NULL,
    unresolved_clts_count INTEGER NOT NULL,
    consonant_vowel_ratio REAL,
    vowel_share REAL NOT NULL,
    PRIMARY KEY (analysis_id, inventory_id),
    FOREIGN KEY (analysis_id) REFERENCES phonology_analysis(id),
    FOREIGN KEY (inventory_id) REFERENCES phoible_inventory(id)
);

CREATE INDEX idx_phonology_inventory_profile_inventory
ON phonology_inventory_profile(inventory_id);

CREATE INDEX idx_phonology_inventory_profile_size
ON phonology_inventory_profile(distinct_segment_count);

CREATE TABLE phonology_segment_prevalence (
    analysis_id TEXT NOT NULL,
    scope TEXT NOT NULL CHECK (scope IN ('inventory', 'language')),
    segment_id INTEGER NOT NULL,
    unit_count INTEGER NOT NULL,
    total_unit_count INTEGER NOT NULL,
    explicit_non_marginal_unit_count INTEGER NOT NULL,
    marginal_only_unit_count INTEGER NOT NULL,
    unknown_marginality_unit_count INTEGER NOT NULL,
    prevalence REAL NOT NULL,
    overall_rank INTEGER NOT NULL,
    class_rank INTEGER NOT NULL,
    PRIMARY KEY (analysis_id, scope, segment_id),
    FOREIGN KEY (analysis_id) REFERENCES phonology_analysis(id),
    FOREIGN KEY (segment_id) REFERENCES phoible_segment(id)
);

CREATE INDEX idx_phonology_prevalence_segment
ON phonology_segment_prevalence(segment_id);

CREATE INDEX idx_phonology_prevalence_scope_rank
ON phonology_segment_prevalence(scope, overall_rank);

CREATE INDEX idx_phonology_prevalence_scope_value
ON phonology_segment_prevalence(scope, prevalence DESC);

CREATE TABLE phonology_segment_cooccurrence (
    analysis_id TEXT NOT NULL,
    scope TEXT NOT NULL CHECK (scope IN ('inventory', 'language')),
    segment_a_id INTEGER NOT NULL,
    segment_b_id INTEGER NOT NULL,
    segment_a_unit_count INTEGER NOT NULL,
    segment_b_unit_count INTEGER NOT NULL,
    joint_unit_count INTEGER NOT NULL,
    total_unit_count INTEGER NOT NULL,
    expected_joint_count REAL NOT NULL,
    support REAL NOT NULL,
    confidence_a_to_b REAL NOT NULL,
    confidence_b_to_a REAL NOT NULL,
    lift REAL NOT NULL,
    pointwise_mutual_information REAL,
    phi_coefficient REAL NOT NULL,
    jaccard_similarity REAL NOT NULL,
    evidence_type TEXT NOT NULL
        CHECK (evidence_type IN ('observed', 'expected_absence')),
    PRIMARY KEY (analysis_id, scope, segment_a_id, segment_b_id),
    FOREIGN KEY (analysis_id) REFERENCES phonology_analysis(id),
    FOREIGN KEY (segment_a_id) REFERENCES phoible_segment(id),
    FOREIGN KEY (segment_b_id) REFERENCES phoible_segment(id),
    CHECK (segment_a_id < segment_b_id),
    CHECK (
        (evidence_type = 'observed' AND joint_unit_count > 0)
        OR
        (evidence_type = 'expected_absence' AND joint_unit_count = 0)
    )
);

CREATE INDEX idx_phonology_cooccurrence_a
ON phonology_segment_cooccurrence(scope, segment_a_id);

CREATE INDEX idx_phonology_cooccurrence_b
ON phonology_segment_cooccurrence(scope, segment_b_id);

CREATE INDEX idx_phonology_cooccurrence_lift
ON phonology_segment_cooccurrence(scope, lift DESC);

CREATE INDEX idx_phonology_cooccurrence_phi
ON phonology_segment_cooccurrence(scope, phi_coefficient DESC);

CREATE INDEX idx_phonology_cooccurrence_joint
ON phonology_segment_cooccurrence(scope, joint_unit_count DESC);

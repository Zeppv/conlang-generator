CREATE TABLE phoible_inventory (
    id INTEGER PRIMARY KEY,

    glottocode TEXT,
    iso6393 TEXT,

    language_name TEXT NOT NULL,
    mapping_language_name TEXT,

    source_code TEXT NOT NULL,

    reference_language_id INTEGER,

    source_id TEXT NOT NULL,

    FOREIGN KEY (reference_language_id)
        REFERENCES reference_language(id),

    FOREIGN KEY (source_id)
        REFERENCES reference_source(id)
);


CREATE INDEX idx_phoible_inventory_glottocode
ON phoible_inventory(glottocode);


CREATE INDEX idx_phoible_inventory_iso6393
ON phoible_inventory(iso6393);


CREATE INDEX idx_phoible_inventory_source
ON phoible_inventory(source_code);


CREATE INDEX idx_phoible_inventory_reference_language
ON phoible_inventory(reference_language_id);



CREATE TABLE phoible_segment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    glyph_id TEXT NOT NULL,

    phoneme TEXT NOT NULL UNIQUE,

    segment_class TEXT NOT NULL,

    clts_sound_id TEXT,

    clts_mapping_status TEXT NOT NULL,

    clts_mapping_method TEXT,

    source_id TEXT NOT NULL,

    FOREIGN KEY (clts_sound_id)
        REFERENCES clts_sound(id),

    FOREIGN KEY (source_id)
        REFERENCES reference_source(id)
);


CREATE INDEX idx_phoible_segment_glyph
ON phoible_segment(glyph_id);


CREATE INDEX idx_phoible_segment_class
ON phoible_segment(segment_class);


CREATE INDEX idx_phoible_segment_clts
ON phoible_segment(clts_sound_id);


CREATE INDEX idx_phoible_segment_mapping_status
ON phoible_segment(clts_mapping_status);



CREATE TABLE phoible_segment_feature (
    segment_id INTEGER NOT NULL,

    feature_name TEXT NOT NULL,

    feature_value TEXT NOT NULL,

    feature_order INTEGER NOT NULL,

    PRIMARY KEY (
        segment_id,
        feature_name
    ),

    FOREIGN KEY (segment_id)
        REFERENCES phoible_segment(id)
);


CREATE INDEX idx_phoible_segment_feature_name
ON phoible_segment_feature(feature_name);


CREATE INDEX idx_phoible_segment_feature_value
ON phoible_segment_feature(
    feature_name,
    feature_value
);



CREATE TABLE phoible_inventory_segment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    source_row_number INTEGER NOT NULL UNIQUE,

    inventory_id INTEGER NOT NULL,

    segment_id INTEGER NOT NULL,

    specific_dialect TEXT,

    allophones TEXT,

    marginal_raw TEXT,

    is_marginal INTEGER,

    source_id TEXT NOT NULL,

    FOREIGN KEY (inventory_id)
        REFERENCES phoible_inventory(id),

    FOREIGN KEY (segment_id)
        REFERENCES phoible_segment(id),

    FOREIGN KEY (source_id)
        REFERENCES reference_source(id)
);


CREATE INDEX idx_phoible_inventory_segment_inventory
ON phoible_inventory_segment(inventory_id);


CREATE INDEX idx_phoible_inventory_segment_segment
ON phoible_inventory_segment(segment_id);


CREATE INDEX idx_phoible_inventory_segment_marginal
ON phoible_inventory_segment(is_marginal);



CREATE TABLE phoible_inventory_reference (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    mapping_row_number INTEGER NOT NULL UNIQUE,

    inventory_id INTEGER NOT NULL,

    bibtex_key TEXT NOT NULL,

    source_code TEXT,

    filename TEXT,

    uri TEXT,

    source_id TEXT NOT NULL,

    FOREIGN KEY (inventory_id)
        REFERENCES phoible_inventory(id),

    FOREIGN KEY (source_id)
        REFERENCES reference_source(id)
);


CREATE INDEX idx_phoible_reference_inventory
ON phoible_inventory_reference(inventory_id);


CREATE INDEX idx_phoible_reference_bibtex
ON phoible_inventory_reference(bibtex_key);
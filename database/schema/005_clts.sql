CREATE TABLE clts_dataset (
    id TEXT PRIMARY KEY,

    description TEXT,
    refs TEXT,
    dataset_type TEXT NOT NULL,
    uri_template TEXT,

    source_id TEXT NOT NULL,

    FOREIGN KEY (source_id)
        REFERENCES reference_source(id)
);


CREATE INDEX idx_clts_dataset_type
ON clts_dataset(dataset_type);



CREATE TABLE clts_feature (
    id TEXT PRIMARY KEY,

    sound_type TEXT NOT NULL,
    feature TEXT NOT NULL,
    value TEXT NOT NULL,

    source_id TEXT NOT NULL,

    FOREIGN KEY (source_id)
        REFERENCES reference_source(id)
);


CREATE INDEX idx_clts_feature_type
ON clts_feature(sound_type);


CREATE INDEX idx_clts_feature_name
ON clts_feature(feature);


CREATE INDEX idx_clts_feature_value
ON clts_feature(value);



CREATE TABLE clts_sound (
    id TEXT PRIMARY KEY,

    name TEXT NOT NULL UNIQUE,
    sound_type TEXT NOT NULL,

    grapheme TEXT,
    unicode_names TEXT,

    is_generated INTEGER NOT NULL DEFAULT 0,
    generated_marker TEXT,

    note TEXT,

    source_id TEXT NOT NULL,

    FOREIGN KEY (source_id)
        REFERENCES reference_source(id)
);


CREATE INDEX idx_clts_sound_name
ON clts_sound(name);


CREATE INDEX idx_clts_sound_type
ON clts_sound(sound_type);


CREATE INDEX idx_clts_sound_grapheme
ON clts_sound(grapheme);



CREATE TABLE clts_sound_feature (
    sound_id TEXT NOT NULL,
    feature_id TEXT NOT NULL,

    feature_order INTEGER NOT NULL,

    PRIMARY KEY (
        sound_id,
        feature_order
    ),

    FOREIGN KEY (sound_id)
        REFERENCES clts_sound(id),

    FOREIGN KEY (feature_id)
        REFERENCES clts_feature(id)
);


CREATE INDEX idx_clts_sound_feature_feature
ON clts_sound_feature(feature_id);


CREATE TABLE clts_grapheme (
    id INTEGER PRIMARY KEY,

    grapheme TEXT,

    sound_id TEXT NOT NULL,

    is_explicit INTEGER NOT NULL DEFAULT 0,
    explicit_marker TEXT,

    dataset_id TEXT,

    frequency INTEGER,

    url TEXT,
    source_features TEXT,
    image TEXT,
    sound TEXT,
    note TEXT,

    source_id TEXT NOT NULL,

    FOREIGN KEY (sound_id)
        REFERENCES clts_sound(id),

    FOREIGN KEY (dataset_id)
        REFERENCES clts_dataset(id),

    FOREIGN KEY (source_id)
        REFERENCES reference_source(id)
);


CREATE INDEX idx_clts_grapheme_text
ON clts_grapheme(grapheme);


CREATE INDEX idx_clts_grapheme_sound
ON clts_grapheme(sound_id);


CREATE INDEX idx_clts_grapheme_dataset
ON clts_grapheme(dataset_id);
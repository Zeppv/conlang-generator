from pathlib import Path
import csv
import sqlite3


# ---------------------------------------------------------
# PROJECT LOCATIONS
# ---------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]

RAW = ROOT / "data" / "raw"
COMPILED = ROOT / "data" / "compiled"

DATABASE_FILE = COMPILED / "reference.sqlite"

CLTS = RAW / "clts"

CLTS_SOURCES = (
    CLTS
    / "sources"
    / "index.tsv"
)

CLTS_FEATURES = (
    CLTS
    / "data"
    / "features.tsv"
)

CLTS_SOUNDS = (
    CLTS
    / "data"
    / "sounds.tsv"
)

CLTS_GRAPHEMES = (
    CLTS
    / "data"
    / "graphemes.tsv"
)


# ---------------------------------------------------------
# EXPECTED PHYSICAL HEADERS
#
# These match the verified CLTS v2.3.0 files actually
# downloaded in data/raw/clts.
# ---------------------------------------------------------

SOURCE_HEADERS = [
    "NAME",
    "DESCRIPTION",
    "REFS",
    "TYPE",
    "URITEMPLATE",
]

FEATURE_HEADERS = [
    "ID",
    "TYPE",
    "FEATURE",
    "VALUE",
]

SOUND_HEADERS = [
    "ID",
    "NAME",
    "FEATURES",
    "TYPE",
    "GRAPHEME",
    "UNICODE",
    "GENERATED",
    "NOTE",
]

GRAPHEME_HEADERS = [
    "PK",
    "GRAPHEME",
    "NAME",
    "EXPLICIT",
    "DATASET",
    "FREQUENCY",
    "URL",
    "FEATURES",
    "IMAGE",
    "SOUND",
    "NOTE",
]


# ---------------------------------------------------------
# EXPECTED CLTS SOURCE REGISTRATION
# ---------------------------------------------------------

EXPECTED_REFERENCE_SOURCE = (
    "clts",
    "Cross-Linguistic Transcription Systems (CLTS)",
    "2.3.0",
    "CC BY 4.0",
    "https://clts.clld.org/",
)


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def require_file(path):
    if not path.exists():
        raise FileNotFoundError(
            f"\nCould not find:\n{path}"
        )

    return path


def clean(value):
    if value is None:
        return None

    value = str(value).strip()

    if value == "":
        return None

    return value


def integer(value):
    value = clean(value)

    if value is None:
        return None

    try:
        return int(value)

    except ValueError as error:
        raise RuntimeError(
            f"Expected integer, found: {value!r}"
        ) from error


def marker_boolean(value):
    value = clean(value)

    if value is None:
        return 0

    normalized = value.lower()

    if normalized in {
        "+",
        "true",
        "yes",
        "1",
        "y",
    }:
        return 1

    if normalized in {
        "-",
        "false",
        "no",
        "0",
        "n",
    }:
        return 0

    raise RuntimeError(
        f"Unknown boolean marker: {value!r}"
    )


def read_tsv(
    path,
    expected_headers
):

    with open(
        path,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as handle:

        reader = csv.DictReader(
            handle,
            delimiter="\t"
        )

        if reader.fieldnames != expected_headers:

            raise RuntimeError(
                "\nUnexpected TSV columns.\n\n"
                f"File:\n{path}\n\n"
                f"Expected:\n"
                f"{expected_headers}\n\n"
                f"Found:\n"
                f"{reader.fieldnames}"
            )

        rows = []

        for row in reader:

            rows.append(
                {
                    key: clean(value)
                    for key, value in row.items()
                }
            )

        return rows


def require_unique(
    values,
    description
):

    seen = set()
    duplicates = set()

    for value in values:

        if value in seen:
            duplicates.add(value)

        seen.add(value)

    if duplicates:

        preview = sorted(
            str(value)
            for value in duplicates
        )[:20]

        raise RuntimeError(
            f"\nDuplicate {description} found:\n"
            + "\n".join(
                f"  - {value}"
                for value in preview
            )
        )


def compare_count(
    name,
    source_count,
    database_count
):

    if source_count != database_count:

        raise RuntimeError(
            f"\n{name} count mismatch.\n\n"
            f"Source:   {source_count:,}\n"
            f"Database: {database_count:,}"
        )


def compare_record(
    description,
    record_id,
    expected,
    actual
):

    if expected != actual:

        raise RuntimeError(
            f"\n{description} mismatch.\n\n"
            f"Record:\n{record_id}\n\n"
            f"Expected:\n{expected}\n\n"
            f"Database:\n{actual}"
        )


# ---------------------------------------------------------
# START
# ---------------------------------------------------------

print()
print("=============================================")
print("VALIDATING CLTS")
print("=============================================")
print()


# ---------------------------------------------------------
# CHECK SOURCE FILES
# ---------------------------------------------------------

print("Checking source files...")

for path in [
    CLTS_SOURCES,
    CLTS_FEATURES,
    CLTS_SOUNDS,
    CLTS_GRAPHEMES,
    DATABASE_FILE,
]:

    require_file(path)

print("  Source files found.")


# ---------------------------------------------------------
# READ SOURCE DATA
# ---------------------------------------------------------

print("Reading CLTS source data...")

source_rows = read_tsv(
    CLTS_SOURCES,
    SOURCE_HEADERS
)

feature_rows = read_tsv(
    CLTS_FEATURES,
    FEATURE_HEADERS
)

sound_rows = read_tsv(
    CLTS_SOUNDS,
    SOUND_HEADERS
)

grapheme_rows = read_tsv(
    CLTS_GRAPHEMES,
    GRAPHEME_HEADERS
)

print(
    f"  Datasets:  {len(source_rows):,}"
)

print(
    f"  Features:  {len(feature_rows):,}"
)

print(
    f"  Sounds:    {len(sound_rows):,}"
)

print(
    f"  Graphemes: {len(grapheme_rows):,}"
)


# ---------------------------------------------------------
# VALIDATE SOURCE KEYS
# ---------------------------------------------------------

print("Checking source primary keys...")

require_unique(
    [
        row["NAME"]
        for row in source_rows
    ],
    "CLTS dataset names"
)

require_unique(
    [
        row["ID"]
        for row in feature_rows
    ],
    "CLTS feature IDs"
)

require_unique(
    [
        row["ID"]
        for row in sound_rows
    ],
    "CLTS sound IDs"
)

require_unique(
    [
        row["NAME"]
        for row in sound_rows
    ],
    "CLTS sound names"
)

require_unique(
    [
        row["PK"]
        for row in grapheme_rows
    ],
    "CLTS grapheme PK values"
)

print("  Source keys are unique.")


# ---------------------------------------------------------
# BUILD SOURCE LOOKUPS
# ---------------------------------------------------------

dataset_ids = {
    row["NAME"]
    for row in source_rows
}

feature_ids = {
    row["ID"]
    for row in feature_rows
}

sound_name_to_id = {
    row["NAME"]: row["ID"]
    for row in sound_rows
}


# ---------------------------------------------------------
# VALIDATE SOURCE TYPES
# ---------------------------------------------------------

print("Checking CLTS type values...")

allowed_dataset_types = {
    "td",
    "ts",
    "sc",
}

allowed_feature_types = {
    "consonant",
    "vowel",
    "tone",
}

allowed_sound_types = {
    "consonant",
    "vowel",
    "diphthong",
    "tone",
    "cluster",
}


for row in source_rows:

    if row["TYPE"] not in allowed_dataset_types:

        raise RuntimeError(
            "\nUnexpected CLTS dataset type:\n"
            f"{row['TYPE']}"
        )


for row in feature_rows:

    if row["TYPE"] not in allowed_feature_types:

        raise RuntimeError(
            "\nUnexpected CLTS feature type:\n"
            f"{row['TYPE']}"
        )


for row in sound_rows:

    if row["TYPE"] not in allowed_sound_types:

        raise RuntimeError(
            "\nUnexpected CLTS sound type:\n"
            f"{row['TYPE']}"
        )


print("  CLTS type values are valid.")


# ---------------------------------------------------------
# BUILD EXPECTED SOUND FEATURE LINKS
# ---------------------------------------------------------

print("Checking sound-to-feature references...")

expected_sound_features = []

for row in sound_rows:

    sound_id = row["ID"]

    features = (
        row["FEATURES"] or ""
    ).split()

    for feature_order, feature_id in enumerate(
        features,
        start=1
    ):

        if feature_id not in feature_ids:

            raise RuntimeError(
                "\nUnknown feature referenced by sound.\n\n"
                f"Sound:\n{row['NAME']}\n\n"
                f"Feature:\n{feature_id}"
            )

        expected_sound_features.append(
            (
                sound_id,
                feature_id,
                feature_order,
            )
        )


print(
    f"  Valid feature links: "
    f"{len(expected_sound_features):,}"
)


# ---------------------------------------------------------
# VALIDATE GRAPHEME REFERENCES
# ---------------------------------------------------------

print("Checking grapheme references...")

for row in grapheme_rows:

    sound_name = row["NAME"]

    if sound_name not in sound_name_to_id:

        raise RuntimeError(
            "\nGrapheme references unknown sound.\n\n"
            f"PK:\n{row['PK']}\n\n"
            f"Sound:\n{sound_name}"
        )

    dataset_id = row["DATASET"]

    if (
        dataset_id is not None
        and dataset_id not in dataset_ids
    ):

        raise RuntimeError(
            "\nGrapheme references unknown dataset.\n\n"
            f"PK:\n{row['PK']}\n\n"
            f"Dataset:\n{dataset_id}"
        )

print("  Grapheme references are valid.")


# ---------------------------------------------------------
# OPEN DATABASE
# ---------------------------------------------------------

connection = sqlite3.connect(
    DATABASE_FILE
)

connection.row_factory = sqlite3.Row

connection.execute(
    "PRAGMA foreign_keys = ON"
)


# ---------------------------------------------------------
# CHECK DATABASE INTEGRITY
# ---------------------------------------------------------

print("Checking SQLite integrity...")

foreign_key_errors = (
    connection.execute(
        "PRAGMA foreign_key_check"
    ).fetchall()
)

if foreign_key_errors:

    connection.close()

    raise RuntimeError(
        "\nForeign key errors found:\n"
        f"{foreign_key_errors}"
    )


integrity_result = (
    connection.execute(
        "PRAGMA integrity_check"
    ).fetchone()[0]
)

if integrity_result != "ok":

    connection.close()

    raise RuntimeError(
        "\nSQLite integrity check failed:\n"
        f"{integrity_result}"
    )


print("  Foreign keys: OK")
print("  SQLite integrity: OK")


# ---------------------------------------------------------
# CHECK REGISTERED REFERENCE SOURCE
# ---------------------------------------------------------

print("Checking CLTS reference registration...")

reference_row = (
    connection.execute(
        """
        SELECT
            id,
            name,
            version,
            license,
            source_url

        FROM reference_source

        WHERE id = 'clts'
        """
    ).fetchone()
)


if reference_row is None:

    connection.close()

    raise RuntimeError(
        "\nCLTS is not registered in "
        "reference_source."
    )


actual_reference_source = tuple(
    reference_row
)

compare_record(
    "CLTS reference_source",
    "clts",
    EXPECTED_REFERENCE_SOURCE,
    actual_reference_source
)

print("  CLTS reference registration is correct.")


# ---------------------------------------------------------
# CHECK TABLE COUNTS
# ---------------------------------------------------------

print("Checking database row counts...")


def database_count(table):

    return connection.execute(
        f"""
        SELECT COUNT(*)
        FROM {table}
        """
    ).fetchone()[0]


compare_count(
    "clts_dataset",
    len(source_rows),
    database_count(
        "clts_dataset"
    )
)

compare_count(
    "clts_feature",
    len(feature_rows),
    database_count(
        "clts_feature"
    )
)

compare_count(
    "clts_sound",
    len(sound_rows),
    database_count(
        "clts_sound"
    )
)

compare_count(
    "clts_sound_feature",
    len(expected_sound_features),
    database_count(
        "clts_sound_feature"
    )
)

compare_count(
    "clts_grapheme",
    len(grapheme_rows),
    database_count(
        "clts_grapheme"
    )
)

print("  Database row counts match source data.")


# ---------------------------------------------------------
# VALIDATE DATASETS
# ---------------------------------------------------------

print("Comparing CLTS datasets...")

database_datasets = {
    row["id"]: (
        row["description"],
        row["refs"],
        row["dataset_type"],
        row["uri_template"],
        row["source_id"],
    )

    for row in connection.execute(
        """
        SELECT
            id,
            description,
            refs,
            dataset_type,
            uri_template,
            source_id

        FROM clts_dataset
        """
    )
}


for row in source_rows:

    dataset_id = row["NAME"]

    expected = (
        row["DESCRIPTION"],
        row["REFS"],
        row["TYPE"],
        row["URITEMPLATE"],
        "clts",
    )

    actual = database_datasets.get(
        dataset_id
    )

    compare_record(
        "CLTS dataset",
        dataset_id,
        expected,
        actual
    )


print("  CLTS datasets match.")


# ---------------------------------------------------------
# VALIDATE FEATURES
# ---------------------------------------------------------

print("Comparing CLTS features...")

database_features = {
    row["id"]: (
        row["sound_type"],
        row["feature"],
        row["value"],
        row["source_id"],
    )

    for row in connection.execute(
        """
        SELECT
            id,
            sound_type,
            feature,
            value,
            source_id

        FROM clts_feature
        """
    )
}


for row in feature_rows:

    feature_id = row["ID"]

    expected = (
        row["TYPE"],
        row["FEATURE"],
        row["VALUE"],
        "clts",
    )

    actual = database_features.get(
        feature_id
    )

    compare_record(
        "CLTS feature",
        feature_id,
        expected,
        actual
    )


print("  CLTS features match.")


# ---------------------------------------------------------
# VALIDATE SOUNDS
# ---------------------------------------------------------

print("Comparing CLTS sounds and Unicode data...")

database_sounds = {
    row["id"]: (
        row["name"],
        row["sound_type"],
        row["grapheme"],
        row["unicode_names"],
        row["is_generated"],
        row["generated_marker"],
        row["note"],
        row["source_id"],
    )

    for row in connection.execute(
        """
        SELECT
            id,
            name,
            sound_type,
            grapheme,
            unicode_names,
            is_generated,
            generated_marker,
            note,
            source_id

        FROM clts_sound
        """
    )
}


for row in sound_rows:

    sound_id = row["ID"]

    expected = (
        row["NAME"],
        row["TYPE"],
        row["GRAPHEME"],
        row["UNICODE"],
        marker_boolean(
            row["GENERATED"]
        ),
        row["GENERATED"],
        row["NOTE"],
        "clts",
    )

    actual = database_sounds.get(
        sound_id
    )

    compare_record(
        "CLTS sound",
        sound_id,
        expected,
        actual
    )


print(
    "  CLTS sounds and IPA/Unicode "
    "representations match."
)


# ---------------------------------------------------------
# VALIDATE SOUND FEATURES
# ---------------------------------------------------------

print("Comparing normalized sound features...")

database_sound_features = {
    (
        row["sound_id"],
        row["feature_id"],
        row["feature_order"],
    )

    for row in connection.execute(
        """
        SELECT
            sound_id,
            feature_id,
            feature_order

        FROM clts_sound_feature
        """
    )
}


expected_sound_feature_set = set(
    expected_sound_features
)


if (
    database_sound_features
    != expected_sound_feature_set
):

    missing = (
        expected_sound_feature_set
        - database_sound_features
    )

    extra = (
        database_sound_features
        - expected_sound_feature_set
    )

    connection.close()

    raise RuntimeError(
        "\nSound-feature mappings do not match.\n\n"
        f"Missing mappings: {len(missing):,}\n"
        f"Extra mappings:   {len(extra):,}"
    )


print("  Sound-feature mappings match.")


# ---------------------------------------------------------
# VALIDATE GRAPHEMES
# ---------------------------------------------------------

print("Comparing CLTS grapheme mappings...")

database_graphemes = {
    row["id"]: (
        row["grapheme"],
        row["sound_id"],
        row["is_explicit"],
        row["explicit_marker"],
        row["dataset_id"],
        row["frequency"],
        row["url"],
        row["source_features"],
        row["image"],
        row["sound"],
        row["note"],
        row["source_id"],
    )

    for row in connection.execute(
        """
        SELECT
            id,
            grapheme,
            sound_id,
            is_explicit,
            explicit_marker,
            dataset_id,
            frequency,
            url,
            source_features,
            image,
            sound,
            note,
            source_id

        FROM clts_grapheme
        """
    )
}


for row in grapheme_rows:

    grapheme_id = integer(
        row["PK"]
    )

    sound_id = sound_name_to_id[
        row["NAME"]
    ]

    expected = (
        row["GRAPHEME"],
        sound_id,
        marker_boolean(
            row["EXPLICIT"]
        ),
        row["EXPLICIT"],
        row["DATASET"],
        integer(
            row["FREQUENCY"]
        ),
        row["URL"],
        row["FEATURES"],
        row["IMAGE"],
        row["SOUND"],
        row["NOTE"],
        "clts",
    )

    actual = database_graphemes.get(
        grapheme_id
    )

    compare_record(
        "CLTS grapheme",
        grapheme_id,
        expected,
        actual
    )


print(
    "  CLTS grapheme mappings and "
    "provenance match."
)


# ---------------------------------------------------------
# SUMMARY COUNTS BY SOUND TYPE
# ---------------------------------------------------------

print()
print("Sound inventory by CLTS type:")

type_counts = connection.execute(
    """
    SELECT
        sound_type,
        COUNT(*) AS count

    FROM clts_sound

    GROUP BY sound_type

    ORDER BY sound_type
    """
).fetchall()


for row in type_counts:

    print(
        f"  {row['sound_type']}: "
        f"{row['count']:,}"
    )


connection.close()


# ---------------------------------------------------------
# COMPLETE
# ---------------------------------------------------------

print()
print("=============================================")
print("CLTS VALIDATION PASSED")
print("=============================================")

print()
print(
    f"Datasets validated:       "
    f"{len(source_rows):,}"
)

print(
    f"Features validated:       "
    f"{len(feature_rows):,}"
)

print(
    f"Sounds validated:         "
    f"{len(sound_rows):,}"
)

print(
    f"Sound features validated: "
    f"{len(expected_sound_features):,}"
)

print(
    f"Graphemes validated:      "
    f"{len(grapheme_rows):,}"
)

print()
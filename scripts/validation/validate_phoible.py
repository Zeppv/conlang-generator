from pathlib import Path
from collections import Counter, defaultdict
import csv
import re
import sqlite3


# ---------------------------------------------------------
# PROJECT LOCATIONS
# ---------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]

RAW = ROOT / "data" / "raw"
COMPILED = ROOT / "data" / "compiled"

DATABASE_FILE = (
    COMPILED
    / "reference.sqlite"
)

PHOIBLE = (
    RAW
    / "phoible"
)

PHOIBLE_MAIN = (
    PHOIBLE
    / "data"
    / "phoible.csv"
)

PHOIBLE_LANGUAGE_MAP = (
    PHOIBLE
    / "mappings"
    / "InventoryID-LanguageCodes.csv"
)

PHOIBLE_REFERENCE_MAP = (
    PHOIBLE
    / "mappings"
    / "InventoryID-Bibtex.csv"
)

PHOIBLE_BIBLIOGRAPHY = (
    PHOIBLE
    / "data"
    / "phoible-references.bib"
)

PHOIBLE_LICENSE = (
    PHOIBLE
    / "data"
    / "LICENSE"
)


# ---------------------------------------------------------
# VERIFIED PHYSICAL HEADERS
# ---------------------------------------------------------

MAIN_HEADERS = [
    "InventoryID",
    "Glottocode",
    "ISO6393",
    "LanguageName",
    "SpecificDialect",
    "GlyphID",
    "Phoneme",
    "Allophones",
    "Marginal",
    "SegmentClass",
    "Source",
    "tone",
    "stress",
    "syllabic",
    "short",
    "long",
    "consonantal",
    "sonorant",
    "continuant",
    "delayedRelease",
    "approximant",
    "tap",
    "trill",
    "nasal",
    "lateral",
    "labial",
    "round",
    "labiodental",
    "coronal",
    "anterior",
    "distributed",
    "strident",
    "dorsal",
    "high",
    "low",
    "front",
    "back",
    "tense",
    "retractedTongueRoot",
    "advancedTongueRoot",
    "periodicGlottalSource",
    "epilaryngealSource",
    "spreadGlottis",
    "constrictedGlottis",
    "fortis",
    "raisedLarynxEjective",
    "loweredLarynxImplosive",
    "click",
]


FEATURE_HEADERS = (
    MAIN_HEADERS[11:]
)


LANGUAGE_MAP_HEADERS = [
    "InventoryID",
    "ISO6393",
    "Glottocode",
    "LanguageName",
    "Source",
]


REFERENCE_MAP_HEADERS = [
    "InventoryID",
    "BibtexKey",
    "Source",
    "Filename",
    "URI",
]


EXPECTED_REFERENCE_SOURCE = (
    "phoible",
    "PHOIBLE",
    "2.0",
    "MIT",
    "https://github.com/phoible/phoible",
)


csv.field_size_limit(
    10_000_000
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


def read_csv(
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
            handle
        )

        if reader.fieldnames != expected_headers:

            raise RuntimeError(
                "\nUnexpected PHOIBLE columns.\n\n"
                f"File:\n{path}\n\n"
                f"Expected:\n"
                f"{expected_headers}\n\n"
                f"Found:\n"
                f"{reader.fieldnames}\n\n"
                "STOPPING rather than guessing "
                "how to interpret this PHOIBLE release."
            )

        return list(reader)


def integer(value):

    try:
        return int(value)

    except (
        TypeError,
        ValueError
    ) as error:

        raise RuntimeError(
            f"Expected integer, found: "
            f"{value!r}"
        ) from error


def optional_identifier(value):

    if value in {
        None,
        "",
        "NA",
    }:
        return None

    return value.strip()


def optional_text(value):

    if value in {
        None,
        "",
    }:
        return None

    return value


def marginal_boolean(value):

    if value == "TRUE":
        return 1

    if value == "FALSE":
        return 0

    if value == "NA":
        return None

    raise RuntimeError(
        f"Unexpected Marginal value: "
        f"{value!r}"
    )


def require_unique(
    values,
    description
):

    counts = Counter(
        values
    )

    duplicates = [
        value
        for value, count
        in counts.items()
        if count > 1
    ]

    if duplicates:

        raise RuntimeError(
            f"\nDuplicate {description} found.\n\n"
            + "\n".join(
                f"  - {value}"
                for value
                in duplicates[:20]
            )
        )


def compare_count(
    description,
    expected,
    actual
):

    if expected != actual:

        raise RuntimeError(
            f"\n{description} count mismatch.\n\n"
            f"Expected: {expected:,}\n"
            f"Actual:   {actual:,}"
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
            f"Record:\n"
            f"{record_id}\n\n"
            f"Expected:\n"
            f"{expected}\n\n"
            f"Actual:\n"
            f"{actual}"
        )


# ---------------------------------------------------------
# START
# ---------------------------------------------------------

print()
print("=============================================")
print("VALIDATING PHOIBLE")
print("=============================================")
print()


# ---------------------------------------------------------
# CHECK SOURCE FILES
# ---------------------------------------------------------

print("Checking PHOIBLE source files...")


for path in [
    PHOIBLE_MAIN,
    PHOIBLE_LANGUAGE_MAP,
    PHOIBLE_REFERENCE_MAP,
    PHOIBLE_BIBLIOGRAPHY,
    PHOIBLE_LICENSE,
    DATABASE_FILE,
]:

    require_file(
        path
    )


print("  Source files found.")


# ---------------------------------------------------------
# READ SOURCE DATA
# ---------------------------------------------------------

print("Reading source data...")


main_rows = read_csv(
    PHOIBLE_MAIN,
    MAIN_HEADERS
)

language_rows = read_csv(
    PHOIBLE_LANGUAGE_MAP,
    LANGUAGE_MAP_HEADERS
)

reference_rows = read_csv(
    PHOIBLE_REFERENCE_MAP,
    REFERENCE_MAP_HEADERS
)


print(
    f"  Main observations: "
    f"{len(main_rows):,}"
)

print(
    f"  Language mappings: "
    f"{len(language_rows):,}"
)

print(
    f"  Reference mappings: "
    f"{len(reference_rows):,}"
)


# ---------------------------------------------------------
# SOURCE INVENTORIES
# ---------------------------------------------------------

print("Checking source inventories...")


inventories = {}


for row in main_rows:

    inventory_id = integer(
        row["InventoryID"]
    )

    core = (
        row["Glottocode"],
        row["ISO6393"],
        row["LanguageName"],
        row["Source"],
    )

    previous = inventories.get(
        inventory_id
    )

    if previous is None:

        inventories[
            inventory_id
        ] = core

    elif previous != core:

        raise RuntimeError(
            "\nPHOIBLE inventory contains "
            "inconsistent core metadata.\n\n"
            f"InventoryID: {inventory_id}\n\n"
            f"First:\n{previous}\n\n"
            f"Later:\n{core}"
        )


print(
    f"  Inventories: "
    f"{len(inventories):,}"
)


# ---------------------------------------------------------
# INVENTORY-LANGUAGE MAPPING
# ---------------------------------------------------------

print(
    "Checking inventory-language mappings..."
)


require_unique(
    [
        integer(
            row["InventoryID"]
        )
        for row in language_rows
    ],
    "InventoryID in language mappings"
)


language_by_inventory = {
    integer(
        row["InventoryID"]
    ): row

    for row in language_rows
}


if (
    set(language_by_inventory)
    != set(inventories)
):

    missing = (
        set(inventories)
        - set(language_by_inventory)
    )

    extra = (
        set(language_by_inventory)
        - set(inventories)
    )

    raise RuntimeError(
        "\nInventory-language mapping coverage "
        "does not match PHOIBLE main data.\n\n"
        f"Missing mappings: "
        f"{len(missing):,}\n"
        f"Extra mappings:   "
        f"{len(extra):,}"
    )


language_name_mismatches = []


for inventory_id, core in inventories.items():

    (
        glottocode,
        iso6393,
        language_name,
        source_code,
    ) = core

    mapping_row = (
        language_by_inventory[
            inventory_id
        ]
    )

    expected_identifiers = (
        iso6393,
        glottocode,
        source_code,
    )

    actual_identifiers = (
        mapping_row["ISO6393"],
        mapping_row["Glottocode"],
        mapping_row["Source"],
    )

    compare_record(
        "Inventory-language identifiers",
        inventory_id,
        expected_identifiers,
        actual_identifiers
    )

    mapping_language_name = (
        mapping_row[
            "LanguageName"
        ]
    )

    if (
        language_name
        != mapping_language_name
    ):

        language_name_mismatches.append(
            (
                inventory_id,
                language_name,
                mapping_language_name,
            )
        )


print(
    "  Inventory identifiers match."
)

print(
    "  Language-name differences preserved: "
    f"{len(language_name_mismatches):,}"
)


# ---------------------------------------------------------
# SOURCE SEGMENTS
# ---------------------------------------------------------

print("Checking unique segment profiles...")


segments = {}


for row in main_rows:

    phoneme = row["Phoneme"]

    if phoneme == "":

        raise RuntimeError(
            "\nPHOIBLE contains an empty "
            "Phoneme value."
        )

    profile = (
        row["GlyphID"],
        row["SegmentClass"],
        tuple(
            row[feature]
            for feature
            in FEATURE_HEADERS
        ),
    )

    previous = segments.get(
        phoneme
    )

    if previous is None:

        segments[
            phoneme
        ] = profile

    elif previous != profile:

        raise RuntimeError(
            "\nPHOIBLE phoneme has multiple "
            "feature profiles.\n\n"
            f"Phoneme: {phoneme!r}"
        )


print(
    f"  Unique segments: "
    f"{len(segments):,}"
)

print(
    f"  Features per segment: "
    f"{len(FEATURE_HEADERS):,}"
)


# ---------------------------------------------------------
# SEGMENT CLASSES
# ---------------------------------------------------------

print("Checking segment classes...")


segment_classes = Counter(
    row["SegmentClass"]
    for row in main_rows
)


allowed_classes = {
    "consonant",
    "vowel",
    "tone",
}


if (
    set(segment_classes)
    != allowed_classes
):

    raise RuntimeError(
        "\nUnexpected PHOIBLE segment classes.\n\n"
        f"Found:\n"
        f"{sorted(segment_classes)}"
    )


for segment_class in sorted(
    segment_classes
):

    print(
        f"  {segment_class}: "
        f"{segment_classes[segment_class]:,}"
    )


# ---------------------------------------------------------
# DISTINCTIVE FEATURE VALUES
# ---------------------------------------------------------

print(
    "Checking PHOIBLE distinctive-feature values..."
)


feature_value_sets = {
    feature: set()
    for feature
    in FEATURE_HEADERS
}


for row in main_rows:

    for feature in FEATURE_HEADERS:

        feature_value_sets[
            feature
        ].add(
            row[feature]
        )


for feature in FEATURE_HEADERS:

    if "" in feature_value_sets[
        feature
    ]:

        raise RuntimeError(
            "\nBlank PHOIBLE feature value "
            "found.\n\n"
            f"Feature: {feature}"
        )


print(
    f"  Feature columns checked: "
    f"{len(FEATURE_HEADERS):,}"
)


# ---------------------------------------------------------
# DUPLICATE INVENTORY-PHONEME OBSERVATIONS
# ---------------------------------------------------------

print(
    "Checking repeated inventory-segment rows..."
)


source_pair_counts = Counter(
    (
        integer(
            row["InventoryID"]
        ),
        row["Phoneme"],
    )

    for row in main_rows
)


duplicate_pairs = {
    pair: count

    for pair, count
    in source_pair_counts.items()

    if count > 1
}


extra_duplicate_rows = sum(
    count - 1

    for count
    in duplicate_pairs.values()
)


print(
    "  Repeated inventory-segment pairs: "
    f"{len(duplicate_pairs):,}"
)

print(
    "  Extra repeated source rows: "
    f"{extra_duplicate_rows:,}"
)


# ---------------------------------------------------------
# SPECIFIC DIALECT VARIATION
# ---------------------------------------------------------

print(
    "Checking row-level SpecificDialect variation..."
)


dialects = defaultdict(
    set
)


for row in main_rows:

    dialects[
        integer(
            row["InventoryID"]
        )
    ].add(
        row["SpecificDialect"]
    )


multi_dialect_inventories = {
    inventory_id: values

    for inventory_id, values
    in dialects.items()

    if len(values) > 1
}


print(
    "  Inventories with multiple "
    "SpecificDialect values: "
    f"{len(multi_dialect_inventories):,}"
)


# ---------------------------------------------------------
# BIBLIOGRAPHY COVERAGE
# ---------------------------------------------------------

print("Checking bibliography coverage...")


reference_inventory_ids = {
    integer(
        row["InventoryID"]
    )
    for row in reference_rows
}


if (
    reference_inventory_ids
    != set(inventories)
):

    missing = (
        set(inventories)
        - reference_inventory_ids
    )

    extra = (
        reference_inventory_ids
        - set(inventories)
    )

    raise RuntimeError(
        "\nPHOIBLE bibliography coverage "
        "does not match inventory set.\n\n"
        f"Missing inventories: "
        f"{len(missing):,}\n"
        f"Extra inventories:   "
        f"{len(extra):,}"
    )


bib_text = (
    PHOIBLE_BIBLIOGRAPHY
    .read_text(
        encoding="utf-8"
    )
)


bibtex_keys = set(
    re.findall(
        r"@\w+\s*\{\s*([^,\s]+)",
        bib_text
    )
)


used_keys = {
    row["BibtexKey"]
    for row in reference_rows
}


missing_real_keys = (
    used_keys
    - bibtex_keys
    - {
        "NO SOURCE GIVEN"
    }
)


if missing_real_keys:

    raise RuntimeError(
        "\nPHOIBLE bibliography mappings "
        "reference missing BibTeX entries.\n\n"
        + "\n".join(
            sorted(
                missing_real_keys
            )[:30]
        )
    )


print(
    f"  Used BibTeX keys: "
    f"{len(used_keys):,}"
)

print(
    f"  Bibliography entries: "
    f"{len(bibtex_keys):,}"
)

print(
    "  Missing real bibliography keys: 0"
)


# ---------------------------------------------------------
# LICENSE
# ---------------------------------------------------------

print("Checking PHOIBLE license...")


license_text = (
    PHOIBLE_LICENSE
    .read_text(
        encoding="utf-8"
    )
)


if (
    "The MIT License"
    not in license_text
):

    raise RuntimeError(
        "\nExpected PHOIBLE MIT license "
        "text was not found."
    )


print("  PHOIBLE license: MIT")


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
# REQUIRED TABLE CHECK
# ---------------------------------------------------------

required_tables = {
    "reference_source",
    "reference_language",
    "clts_sound",
    "clts_grapheme",
    "phoible_inventory",
    "phoible_segment",
    "phoible_segment_feature",
    "phoible_inventory_segment",
    "phoible_inventory_reference",
}


actual_tables = {
    row["name"]

    for row in connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        """
    )
}


missing_tables = (
    required_tables
    - actual_tables
)


if missing_tables:

    connection.close()

    raise RuntimeError(
        "\nRequired PHOIBLE tables are "
        "missing from reference.sqlite.\n\n"
        + "\n".join(
            f"  - {table}"
            for table in sorted(
                missing_tables
            )
        )
    )


# ---------------------------------------------------------
# SQLITE INTEGRITY
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
        "\nForeign-key errors found:\n"
        f"{foreign_key_errors}"
    )


integrity_result = (
    connection.execute(
        "PRAGMA integrity_check"
    ).fetchone()[0]
)


if (
    integrity_result
    != "ok"
):

    connection.close()

    raise RuntimeError(
        "\nSQLite integrity check failed:\n"
        f"{integrity_result}"
    )


print("  Foreign keys: OK")
print("  SQLite integrity: OK")


# ---------------------------------------------------------
# REFERENCE SOURCE REGISTRATION
# ---------------------------------------------------------

print(
    "Checking PHOIBLE reference registration..."
)


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

        WHERE id = 'phoible'
        """
    ).fetchone()
)


if reference_row is None:

    connection.close()

    raise RuntimeError(
        "\nPHOIBLE is not registered "
        "in reference_source."
    )


compare_record(
    "PHOIBLE reference_source",
    "phoible",
    EXPECTED_REFERENCE_SOURCE,
    tuple(
        reference_row
    )
)


print(
    "  PHOIBLE reference registration "
    "is correct."
)


# ---------------------------------------------------------
# DATABASE COUNTS
# ---------------------------------------------------------

print("Checking database row counts...")


def database_count(table):

    return connection.execute(
        f"""
        SELECT COUNT(*)
        FROM {table}
        """
    ).fetchone()[0]


expected_feature_count = (
    len(segments)
    * len(FEATURE_HEADERS)
)


compare_count(
    "phoible_inventory",
    len(inventories),
    database_count(
        "phoible_inventory"
    )
)


compare_count(
    "phoible_segment",
    len(segments),
    database_count(
        "phoible_segment"
    )
)


compare_count(
    "phoible_segment_feature",
    expected_feature_count,
    database_count(
        "phoible_segment_feature"
    )
)


compare_count(
    "phoible_inventory_segment",
    len(main_rows),
    database_count(
        "phoible_inventory_segment"
    )
)


compare_count(
    "phoible_inventory_reference",
    len(reference_rows),
    database_count(
        "phoible_inventory_reference"
    )
)


print(
    "  Database row counts match "
    "PHOIBLE source data."
)


# ---------------------------------------------------------
# GLOTTOLOG LOOKUP
# ---------------------------------------------------------

reference_languages = {
    row["glottocode"]: row["id"]

    for row in connection.execute(
        """
        SELECT
            id,
            glottocode

        FROM reference_language

        WHERE glottocode IS NOT NULL
        """
    )
}


# ---------------------------------------------------------
# INVENTORY COMPARISON
# ---------------------------------------------------------

print("Comparing inventories...")


database_inventories = {
    row["id"]: (
        row["glottocode"],
        row["iso6393"],
        row["language_name"],
        row["mapping_language_name"],
        row["source_code"],
        row["reference_language_id"],
        row["source_id"],
    )

    for row in connection.execute(
        """
        SELECT
            id,
            glottocode,
            iso6393,
            language_name,
            mapping_language_name,
            source_code,
            reference_language_id,
            source_id

        FROM phoible_inventory
        """
    )
}


unmatched_glottocodes = set()


for inventory_id, core in inventories.items():

    (
        raw_glottocode,
        raw_iso,
        language_name,
        source_code,
    ) = core

    glottocode = (
        optional_identifier(
            raw_glottocode
        )
    )

    iso6393 = (
        optional_identifier(
            raw_iso
        )
    )

    mapping_language_name = (
        language_by_inventory[
            inventory_id
        ]["LanguageName"]
    )

    reference_language_id = None

    if glottocode:

        reference_language_id = (
            reference_languages.get(
                glottocode
            )
        )

        if (
            reference_language_id
            is None
        ):

            unmatched_glottocodes.add(
                glottocode
            )


    expected = (
        glottocode,
        iso6393,
        language_name,
        mapping_language_name,
        source_code,
        reference_language_id,
        "phoible",
    )

    actual = (
        database_inventories.get(
            inventory_id
        )
    )


    compare_record(
        "PHOIBLE inventory",
        inventory_id,
        expected,
        actual
    )


print(
    "  Inventories match both PHOIBLE "
    "name sources."
)

print(
    f"  Unmatched Glottocodes: "
    f"{len(unmatched_glottocodes):,}"
)


# ---------------------------------------------------------
# REBUILD EXPECTED CLTS MAPPINGS
# ---------------------------------------------------------

print(
    "Rebuilding expected CLTS mappings..."
)


direct_clts = defaultdict(
    set
)


for row in connection.execute(
    """
    SELECT
        grapheme,
        sound_id

    FROM clts_grapheme

    WHERE dataset_id = 'phoible'
      AND grapheme IS NOT NULL
    """
):

    direct_clts[
        row["grapheme"]
    ].add(
        row["sound_id"]
    )


ambiguous_direct = {
    grapheme: sounds

    for grapheme, sounds
    in direct_clts.items()

    if len(sounds) > 1
}


if ambiguous_direct:

    connection.close()

    raise RuntimeError(
        "\nCLTS PHOIBLE-specific mappings "
        "are unexpectedly ambiguous.\n\n"
        f"Ambiguous mappings: "
        f"{len(ambiguous_direct):,}"
    )


direct_clts = {
    grapheme: next(
        iter(sounds)
    )

    for grapheme, sounds
    in direct_clts.items()
}


all_clts = defaultdict(
    set
)


for row in connection.execute(
    """
    SELECT
        grapheme,
        sound_id

    FROM clts_grapheme

    WHERE grapheme IS NOT NULL
    """
):

    all_clts[
        row["grapheme"]
    ].add(
        row["sound_id"]
    )


for row in connection.execute(
    """
    SELECT
        grapheme,
        id

    FROM clts_sound

    WHERE grapheme IS NOT NULL
    """
):

    all_clts[
        row["grapheme"]
    ].add(
        row["id"]
    )


def expected_clts_mapping(
    phoneme
):

    if phoneme in direct_clts:

        return (
            direct_clts[
                phoneme
            ],
            "mapped",
            "clts_phoible",
        )

    candidates = (
        all_clts.get(
            phoneme
        )
    )

    if not candidates:

        return (
            None,
            "unmapped",
            None,
        )

    if len(
        candidates
    ) == 1:

        return (
            next(
                iter(
                    candidates
                )
            ),
            "mapped",
            "clts_exact_alias",
        )

    return (
        None,
        "ambiguous",
        None,
    )


# ---------------------------------------------------------
# SEGMENT COMPARISON
# ---------------------------------------------------------

print(
    "Comparing segments and CLTS mappings..."
)


database_segments = {
    row["phoneme"]: (
        row["id"],
        row["glyph_id"],
        row["segment_class"],
        row["clts_sound_id"],
        row["clts_mapping_status"],
        row["clts_mapping_method"],
        row["source_id"],
    )

    for row in connection.execute(
        """
        SELECT
            id,
            glyph_id,
            phoneme,
            segment_class,
            clts_sound_id,
            clts_mapping_status,
            clts_mapping_method,
            source_id

        FROM phoible_segment
        """
    )
}


segment_ids = {}

mapping_counts = Counter()


for phoneme, profile in segments.items():

    (
        glyph_id,
        segment_class,
        feature_values,
    ) = profile

    (
        expected_sound_id,
        expected_status,
        expected_method,
    ) = expected_clts_mapping(
        phoneme
    )

    database_row = (
        database_segments.get(
            phoneme
        )
    )

    if database_row is None:

        connection.close()

        raise RuntimeError(
            "\nMissing PHOIBLE segment.\n\n"
            f"Phoneme: {phoneme!r}"
        )

    (
        segment_id,
        actual_glyph_id,
        actual_class,
        actual_sound_id,
        actual_status,
        actual_method,
        actual_source,
    ) = database_row


    expected = (
        glyph_id,
        segment_class,
        expected_sound_id,
        expected_status,
        expected_method,
        "phoible",
    )

    actual = (
        actual_glyph_id,
        actual_class,
        actual_sound_id,
        actual_status,
        actual_method,
        actual_source,
    )


    compare_record(
        "PHOIBLE segment",
        repr(
            phoneme
        ),
        expected,
        actual
    )


    segment_ids[
        phoneme
    ] = segment_id


    mapping_counts[
        (
            expected_status,
            expected_method,
        )
    ] += 1


print(
    "  Segment records and conservative "
    "CLTS mappings match."
)


# ---------------------------------------------------------
# SEGMENT FEATURE COMPARISON
# ---------------------------------------------------------

print(
    "Comparing PHOIBLE segment features..."
)


database_features = {
    (
        row["segment_id"],
        row["feature_name"],
    ): (
        row["feature_value"],
        row["feature_order"],
    )

    for row in connection.execute(
        """
        SELECT
            segment_id,
            feature_name,
            feature_value,
            feature_order

        FROM phoible_segment_feature
        """
    )
}


for phoneme, profile in segments.items():

    feature_values = (
        profile[2]
    )

    segment_id = (
        segment_ids[
            phoneme
        ]
    )


    for feature_order, (
        feature_name,
        feature_value,
    ) in enumerate(
        zip(
            FEATURE_HEADERS,
            feature_values,
        ),
        start=1
    ):

        expected = (
            feature_value,
            feature_order,
        )

        actual = (
            database_features.get(
                (
                    segment_id,
                    feature_name,
                )
            )
        )


        compare_record(
            "PHOIBLE segment feature",
            (
                repr(
                    phoneme
                ),
                feature_name,
            ),
            expected,
            actual
        )


print(
    f"  All {expected_feature_count:,} "
    "segment-feature records match."
)


# ---------------------------------------------------------
# OBSERVATION COMPARISON
# ---------------------------------------------------------

print(
    "Comparing all inventory-segment "
    "observations..."
)


database_observations = {
    row["source_row_number"]: (
        row["inventory_id"],
        row["segment_id"],
        row["specific_dialect"],
        row["allophones"],
        row["marginal_raw"],
        row["is_marginal"],
        row["source_id"],
    )

    for row in connection.execute(
        """
        SELECT
            source_row_number,
            inventory_id,
            segment_id,
            specific_dialect,
            allophones,
            marginal_raw,
            is_marginal,
            source_id

        FROM phoible_inventory_segment
        """
    )
}


for source_row_number, row in enumerate(
    main_rows,
    start=2
):

    expected = (
        integer(
            row["InventoryID"]
        ),
        segment_ids[
            row["Phoneme"]
        ],
        optional_text(
            row["SpecificDialect"]
        ),
        optional_text(
            row["Allophones"]
        ),
        row["Marginal"],
        marginal_boolean(
            row["Marginal"]
        ),
        "phoible",
    )

    actual = (
        database_observations.get(
            source_row_number
        )
    )


    compare_record(
        "PHOIBLE observation",
        source_row_number,
        expected,
        actual
    )


print(
    f"  All {len(main_rows):,} "
    "source observations match."
)


# ---------------------------------------------------------
# VERIFY DUPLICATE SOURCE ROWS SURVIVED
# ---------------------------------------------------------

print(
    "Checking preservation of repeated rows..."
)


database_pair_counts = Counter()


for row in connection.execute(
    """
    SELECT
        pis.inventory_id,
        ps.phoneme

    FROM phoible_inventory_segment AS pis

    JOIN phoible_segment AS ps
      ON ps.id = pis.segment_id
    """
):

    database_pair_counts[
        (
            row["inventory_id"],
            row["phoneme"],
        )
    ] += 1


database_duplicate_pairs = {
    pair: count

    for pair, count
    in database_pair_counts.items()

    if count > 1
}


if (
    database_duplicate_pairs
    != duplicate_pairs
):

    connection.close()

    raise RuntimeError(
        "\nRepeated PHOIBLE source rows "
        "were not preserved exactly.\n\n"
        f"Source repeated pairs: "
        f"{len(duplicate_pairs):,}\n"
        f"Database repeated pairs: "
        f"{len(database_duplicate_pairs):,}"
    )


print(
    f"  Repeated pairs preserved: "
    f"{len(database_duplicate_pairs):,}"
)

print(
    f"  Extra repeated rows preserved: "
    f"{extra_duplicate_rows:,}"
)


# ---------------------------------------------------------
# SPECIFIC DIALECT PRESERVATION
# ---------------------------------------------------------

print(
    "Checking SpecificDialect preservation..."
)


database_dialects = defaultdict(
    set
)


for row in connection.execute(
    """
    SELECT
        inventory_id,
        specific_dialect

    FROM phoible_inventory_segment
    """
):

    database_dialects[
        row["inventory_id"]
    ].add(
        (
            row["specific_dialect"]
            if row["specific_dialect"] is not None
            else ""
        )
    )


normalized_source_dialects = {
    inventory_id: {
        value
        if value != ""
        else ""
        for value
        in values
    }

    for inventory_id, values
    in dialects.items()
}


for inventory_id in inventories:

    source_values = {
        value
        if value != ""
        else ""
        for value
        in dialects[
            inventory_id
        ]
    }

    database_values = {
        value
        if value is not None
        else ""
        for value
        in database_dialects[
            inventory_id
        ]
    }

    if (
        source_values
        != database_values
    ):

        connection.close()

        raise RuntimeError(
            "\nSpecificDialect values were "
            "not preserved.\n\n"
            f"InventoryID: "
            f"{inventory_id}\n\n"
            f"Source:\n"
            f"{source_values}\n\n"
            f"Database:\n"
            f"{database_values}"
        )


print(
    "  SpecificDialect values preserved."
)


# ---------------------------------------------------------
# INVENTORY REFERENCES
# ---------------------------------------------------------

print(
    "Comparing inventory references..."
)


database_references = {
    row["mapping_row_number"]: (
        row["inventory_id"],
        row["bibtex_key"],
        row["source_code"],
        row["filename"],
        row["uri"],
        row["source_id"],
    )

    for row in connection.execute(
        """
        SELECT
            mapping_row_number,
            inventory_id,
            bibtex_key,
            source_code,
            filename,
            uri,
            source_id

        FROM phoible_inventory_reference
        """
    )
}


for mapping_row_number, row in enumerate(
    reference_rows,
    start=2
):

    expected = (
        integer(
            row["InventoryID"]
        ),
        row["BibtexKey"],
        optional_text(
            row["Source"]
        ),
        optional_text(
            row["Filename"]
        ),
        optional_text(
            row["URI"]
        ),
        "phoible",
    )

    actual = (
        database_references.get(
            mapping_row_number
        )
    )


    compare_record(
        "PHOIBLE bibliography mapping",
        mapping_row_number,
        expected,
        actual
    )


print(
    f"  All {len(reference_rows):,} "
    "inventory-reference mappings match."
)


# ---------------------------------------------------------
# CLTS MAPPING SUMMARY
# ---------------------------------------------------------

print()
print("CLTS mapping summary:")


for (
    status,
    method
), count in sorted(
    mapping_counts.items(),
    key=lambda item: (
        item[0][0],
        str(
            item[0][1]
        ),
    )
):

    print(
        f"  {status}"
        f" / "
        f"{method or '-'}"
        f": "
        f"{count:,}"
    )


mapped_count = sum(
    count

    for (
        status,
        method
    ), count
    in mapping_counts.items()

    if status == "mapped"
)


mapped_percent = (
    100
    * mapped_count
    / len(segments)
)


print(
    f"  Total mapped: "
    f"{mapped_count:,} "
    f"({mapped_percent:.2f}%)"
)


connection.close()


# ---------------------------------------------------------
# FINAL REPORT
# ---------------------------------------------------------

print()
print("=============================================")
print("PHOIBLE VALIDATION PASSED")
print("=============================================")
print()


print(
    f"Inventories validated:        "
    f"{len(inventories):,}"
)

print(
    f"Segments validated:           "
    f"{len(segments):,}"
)

print(
    f"Segment features validated:   "
    f"{expected_feature_count:,}"
)

print(
    f"Observations validated:       "
    f"{len(main_rows):,}"
)

print(
    f"References validated:         "
    f"{len(reference_rows):,}"
)

print(
    f"Repeated pairs preserved:     "
    f"{len(duplicate_pairs):,}"
)

print(
    f"Multi-dialect inventories:    "
    f"{len(multi_dialect_inventories):,}"
)

print(
    f"Language-name differences:    "
    f"{len(language_name_mismatches):,}"
)

print(
    f"Unmatched Glottocodes:        "
    f"{len(unmatched_glottocodes):,}"
)

print()
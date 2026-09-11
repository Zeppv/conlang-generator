from pathlib import Path
from collections import Counter, defaultdict
import csv
import sqlite3
import subprocess


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
# VERIFIED PHOIBLE RELEASE
# ---------------------------------------------------------

EXPECTED_PHOIBLE_TAG = "v2.0"

EXPECTED_PHOIBLE_COMMIT = (
    "862bec9af5db42e3c9ceedeaa378bf4c6fa0ec8b"
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
                "how to interpret this release."
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


def parse_marginal(value):

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


def run_git(*arguments):

    result = subprocess.run(
        [
            "git",
            "-C",
            str(PHOIBLE),
            *arguments,
        ],
        capture_output=True,
        text=True,
        check=True
    )

    return result.stdout.strip()


# ---------------------------------------------------------
# VERIFY RAW PHOIBLE CHECKOUT
# ---------------------------------------------------------

def verify_phoible_checkout():

    print()
    print("---------------------------------------------")
    print("VERIFYING PHOIBLE SOURCE")
    print("---------------------------------------------")

    if not (
        PHOIBLE
        / ".git"
    ).exists():

        raise RuntimeError(
            "\nPHOIBLE does not contain its "
            "Git metadata."
        )

    tag = run_git(
        "describe",
        "--tags",
        "--always",
        "--dirty"
    )

    commit = run_git(
        "rev-parse",
        "HEAD"
    )

    status = run_git(
        "status",
        "--short"
    )

    print(
        f"PHOIBLE tag:    {tag}"
    )

    print(
        f"PHOIBLE commit: {commit}"
    )

    if status:

        raise RuntimeError(
            "\ndata/raw/phoible contains "
            "local changes.\n\n"
            f"{status}\n\n"
            "Raw linguistic source data must "
            "not be manually modified."
        )

    if tag != EXPECTED_PHOIBLE_TAG:

        raise RuntimeError(
            "\nUnexpected PHOIBLE release.\n\n"
            f"Expected: {EXPECTED_PHOIBLE_TAG}\n"
            f"Found:    {tag}"
        )

    if commit != EXPECTED_PHOIBLE_COMMIT:

        raise RuntimeError(
            "\nUnexpected PHOIBLE commit.\n\n"
            f"Expected:\n"
            f"{EXPECTED_PHOIBLE_COMMIT}\n\n"
            f"Found:\n"
            f"{commit}"
        )

    print(
        "PHOIBLE checkout is clean "
        "and verified."
    )


# ---------------------------------------------------------
# CHECK FILES
# ---------------------------------------------------------

print()
print("Checking PHOIBLE source files...")


for path in [
    PHOIBLE_MAIN,
    PHOIBLE_LANGUAGE_MAP,
    PHOIBLE_REFERENCE_MAP,
    PHOIBLE_BIBLIOGRAPHY,
    PHOIBLE_LICENSE,
]:

    require_file(
        path
    )


verify_phoible_checkout()


# ---------------------------------------------------------
# READ RAW DATA
# ---------------------------------------------------------

print()
print("Reading PHOIBLE data...")


main_rows = read_csv(
    PHOIBLE_MAIN,
    MAIN_HEADERS
)

language_map_rows = read_csv(
    PHOIBLE_LANGUAGE_MAP,
    LANGUAGE_MAP_HEADERS
)

reference_rows = read_csv(
    PHOIBLE_REFERENCE_MAP,
    REFERENCE_MAP_HEADERS
)


print(
    f"Main rows:       "
    f"{len(main_rows):,}"
)

print(
    f"Language rows:   "
    f"{len(language_map_rows):,}"
)

print(
    f"Reference rows:  "
    f"{len(reference_rows):,}"
)


# ---------------------------------------------------------
# ANALYZE INVENTORIES
# ---------------------------------------------------------

print()
print("Checking inventory metadata...")


inventories = {}


inventory_fields = [
    "Glottocode",
    "ISO6393",
    "LanguageName",
    "Source",
]


for row in main_rows:

    inventory_id = integer(
        row["InventoryID"]
    )

    values = tuple(
        row[field]
        for field in inventory_fields
    )

    previous = inventories.get(
        inventory_id
    )

    if previous is None:

        inventories[
            inventory_id
        ] = values

    elif previous != values:

        raise RuntimeError(
            "\nPHOIBLE inventory contains "
            "inconsistent core metadata.\n\n"
            f"InventoryID: {inventory_id}\n\n"
            f"First:\n{previous}\n\n"
            f"Later:\n{values}"
        )


print(
    f"Inventories:     "
    f"{len(inventories):,}"
)


# ---------------------------------------------------------
# VERIFY LANGUAGE MAPPING COVERAGE
# ---------------------------------------------------------

print(
    "Checking inventory-language mappings..."
)


language_map_by_inventory = {}


for row in language_map_rows:

    inventory_id = integer(
        row["InventoryID"]
    )

    if (
        inventory_id
        in language_map_by_inventory
    ):

        raise RuntimeError(
            "\nDuplicate InventoryID in "
            "InventoryID-LanguageCodes.csv.\n\n"
            f"InventoryID: {inventory_id}"
        )

    language_map_by_inventory[
        inventory_id
    ] = row


inventory_ids = set(
    inventories
)


language_map_ids = set(
    language_map_by_inventory
)


if (
    language_map_ids
    != inventory_ids
):

    missing = (
        inventory_ids
        - language_map_ids
    )

    extra = (
        language_map_ids
        - inventory_ids
    )

    raise RuntimeError(
        "\nInventory-language mapping does "
        "not match main PHOIBLE inventories.\n\n"
        f"Missing: {len(missing):,}\n"
        f"Extra:   {len(extra):,}"
    )


language_name_mismatches = []


for inventory_id, core in inventories.items():

    (
        raw_glottocode,
        raw_iso,
        language_name,
        source_code,
    ) = core

    mapping_row = (
        language_map_by_inventory[
            inventory_id
        ]
    )

    expected_identifiers = (
        raw_iso,
        raw_glottocode,
        source_code,
    )

    mapping_identifiers = (
        mapping_row[
            "ISO6393"
        ],
        mapping_row[
            "Glottocode"
        ],
        mapping_row[
            "Source"
        ],
    )

    if (
        expected_identifiers
        != mapping_identifiers
    ):

        raise RuntimeError(
            "\nInventory-language identifiers "
            "do not agree.\n\n"
            f"InventoryID: {inventory_id}\n\n"
            f"phoible.csv:\n"
            f"{expected_identifiers}\n\n"
            f"mapping file:\n"
            f"{mapping_identifiers}"
        )

    if (
        language_name
        != mapping_row[
            "LanguageName"
        ]
    ):

        language_name_mismatches.append(
            (
                inventory_id,
                language_name,
                mapping_row[
                    "LanguageName"
                ],
            )
        )


print(
    "Inventory identifiers match."
)

print(
    "Language-name differences between "
    "PHOIBLE files: "
    f"{len(language_name_mismatches):,}"
)


# ---------------------------------------------------------
# ANALYZE UNIQUE SEGMENTS
# ---------------------------------------------------------

print(
    "Checking unique PHOIBLE segments..."
)


segments = {}


for row in main_rows:

    phoneme = row[
        "Phoneme"
    ]

    if phoneme == "":

        raise RuntimeError(
            "PHOIBLE row has empty Phoneme."
        )

    profile = (
        row[
            "GlyphID"
        ],
        row[
            "SegmentClass"
        ],
        tuple(
            row[
                feature
            ]
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
            "structural/feature profiles.\n\n"
            f"Phoneme: {phoneme!r}"
        )


print(
    f"Unique segments: "
    f"{len(segments):,}"
)


# ---------------------------------------------------------
# VERIFY BIBLIOGRAPHY COVERAGE
# ---------------------------------------------------------

reference_inventory_ids = {
    integer(
        row["InventoryID"]
    )
    for row in reference_rows
}


if (
    reference_inventory_ids
    != inventory_ids
):

    missing = (
        inventory_ids
        - reference_inventory_ids
    )

    extra = (
        reference_inventory_ids
        - inventory_ids
    )

    raise RuntimeError(
        "\nInventory bibliography coverage "
        "does not match main PHOIBLE inventories.\n\n"
        f"Missing: {len(missing):,}\n"
        f"Extra:   {len(extra):,}"
    )


# ---------------------------------------------------------
# OPEN DATABASE
# ---------------------------------------------------------

if not DATABASE_FILE.exists():

    raise FileNotFoundError(
        f"\nCould not find:\n"
        f"{DATABASE_FILE}\n\n"
        "Build reference.sqlite first."
    )


connection = sqlite3.connect(
    DATABASE_FILE
)

connection.row_factory = sqlite3.Row

connection.execute(
    "PRAGMA foreign_keys = ON"
)


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
        "\nPHOIBLE schema is not ready.\n\n"
        "Missing tables:\n"
        + "\n".join(
            f"  - {table}"
            for table in sorted(
                missing_tables
            )
        )
    )


# ---------------------------------------------------------
# BUILD GLOTTOLOG LOOKUP
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
# BUILD CONSERVATIVE CLTS MAPPINGS
# ---------------------------------------------------------

print()
print(
    "Building PHOIBLE -> CLTS mappings..."
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
        row[
            "grapheme"
        ]
    ].add(
        row[
            "sound_id"
        ]
    )


ambiguous_direct = {
    grapheme: sounds

    for grapheme, sounds
    in direct_clts.items()

    if len(
        sounds
    ) > 1
}


if ambiguous_direct:

    connection.close()

    raise RuntimeError(
        "\nCLTS contains ambiguous mappings "
        "inside its PHOIBLE transcription "
        "dataset.\n\n"
        f"Count: "
        f"{len(ambiguous_direct):,}"
    )


direct_clts = {
    grapheme: next(
        iter(
            sounds
        )
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
        row[
            "grapheme"
        ]
    ].add(
        row[
            "sound_id"
        ]
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
        row[
            "grapheme"
        ]
    ].add(
        row[
            "id"
        ]
    )


def map_to_clts(
    phoneme
):

    if (
        phoneme
        in direct_clts
    ):

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


mapping_summary = Counter()


for phoneme in segments:

    (
        clts_sound_id,
        status,
        method,
    ) = map_to_clts(
        phoneme
    )

    mapping_summary[
        (
            status,
            method,
        )
    ] += 1


for (
    status,
    method
), count in sorted(
    mapping_summary.items(),
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
        f"{method or '-'}: "
        f"{count:,}"
    )


# ---------------------------------------------------------
# IMPORT
# ---------------------------------------------------------

print()
print("---------------------------------------------")
print("IMPORTING PHOIBLE")
print("---------------------------------------------")


segment_ids = {}

unmatched_glottocodes = set()


try:

    with connection:

        # -------------------------------------------------
        # CLEAR OLD PHOIBLE DATA
        # -------------------------------------------------

        connection.execute(
            "DELETE FROM phoible_inventory_reference"
        )

        connection.execute(
            "DELETE FROM phoible_inventory_segment"
        )

        connection.execute(
            "DELETE FROM phoible_segment_feature"
        )

        connection.execute(
            "DELETE FROM phoible_segment"
        )

        connection.execute(
            "DELETE FROM phoible_inventory"
        )


        # -------------------------------------------------
        # REGISTER PHOIBLE
        # -------------------------------------------------

        connection.execute(
            """
            INSERT INTO reference_source (
                id,
                name,
                version,
                license,
                source_url
            )

            VALUES (?, ?, ?, ?, ?)

            ON CONFLICT(id)
            DO UPDATE SET
                name = excluded.name,
                version = excluded.version,
                license = excluded.license,
                source_url = excluded.source_url
            """,
            (
                "phoible",
                "PHOIBLE",
                "2.0",
                "MIT",
                "https://github.com/phoible/phoible",
            )
        )


        # -------------------------------------------------
        # INVENTORIES
        # -------------------------------------------------

        print()
        print(
            "Importing inventories..."
        )


        for inventory_id in sorted(
            inventories
        ):

            (
                raw_glottocode,
                raw_iso,
                language_name,
                source_code,
            ) = inventories[
                inventory_id
            ]

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
                language_map_by_inventory[
                    inventory_id
                ][
                    "LanguageName"
                ]
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


            connection.execute(
                """
                INSERT INTO phoible_inventory (
                    id,
                    glottocode,
                    iso6393,
                    language_name,
                    mapping_language_name,
                    source_code,
                    reference_language_id,
                    source_id
                )

                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    inventory_id,
                    glottocode,
                    iso6393,
                    language_name,
                    mapping_language_name,
                    source_code,
                    reference_language_id,
                    "phoible",
                )
            )


        # -------------------------------------------------
        # SEGMENTS
        # -------------------------------------------------

        print(
            "Importing unique segments..."
        )


        for phoneme in sorted(
            segments
        ):

            (
                glyph_id,
                segment_class,
                feature_values,
            ) = segments[
                phoneme
            ]

            (
                clts_sound_id,
                mapping_status,
                mapping_method,
            ) = map_to_clts(
                phoneme
            )


            cursor = connection.execute(
                """
                INSERT INTO phoible_segment (
                    glyph_id,
                    phoneme,
                    segment_class,
                    clts_sound_id,
                    clts_mapping_status,
                    clts_mapping_method,
                    source_id
                )

                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    glyph_id,
                    phoneme,
                    segment_class,
                    clts_sound_id,
                    mapping_status,
                    mapping_method,
                    "phoible",
                )
            )


            segment_id = (
                cursor.lastrowid
            )


            segment_ids[
                phoneme
            ] = segment_id


            feature_records = [
                (
                    segment_id,
                    feature_name,
                    feature_value,
                    feature_order,
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
                )
            ]


            connection.executemany(
                """
                INSERT INTO phoible_segment_feature (
                    segment_id,
                    feature_name,
                    feature_value,
                    feature_order
                )

                VALUES (?, ?, ?, ?)
                """,
                feature_records
            )


        # -------------------------------------------------
        # INVENTORY-SEGMENT OBSERVATIONS
        # -------------------------------------------------

        print(
            "Importing inventory-segment "
            "observations..."
        )


        observation_records = []


        for source_row_number, row in enumerate(
            main_rows,
            start=2
        ):

            observation_records.append(
                (
                    source_row_number,
                    integer(
                        row[
                            "InventoryID"
                        ]
                    ),
                    segment_ids[
                        row[
                            "Phoneme"
                        ]
                    ],
                    optional_text(
                        row[
                            "SpecificDialect"
                        ]
                    ),
                    optional_text(
                        row[
                            "Allophones"
                        ]
                    ),
                    row[
                        "Marginal"
                    ],
                    parse_marginal(
                        row[
                            "Marginal"
                        ]
                    ),
                    "phoible",
                )
            )


        connection.executemany(
            """
            INSERT INTO phoible_inventory_segment (
                source_row_number,
                inventory_id,
                segment_id,
                specific_dialect,
                allophones,
                marginal_raw,
                is_marginal,
                source_id
            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            observation_records
        )


        # -------------------------------------------------
        # INVENTORY REFERENCES
        # -------------------------------------------------

        print(
            "Importing inventory references..."
        )


        reference_records = []


        for mapping_row_number, row in enumerate(
            reference_rows,
            start=2
        ):

            inventory_id = integer(
                row[
                    "InventoryID"
                ]
            )

            if (
                inventory_id
                not in inventory_ids
            ):

                raise RuntimeError(
                    "\nBibliography mapping "
                    "references unknown inventory.\n\n"
                    f"InventoryID: "
                    f"{inventory_id}"
                )


            reference_records.append(
                (
                    mapping_row_number,
                    inventory_id,
                    row[
                        "BibtexKey"
                    ],
                    optional_text(
                        row[
                            "Source"
                        ]
                    ),
                    optional_text(
                        row[
                            "Filename"
                        ]
                    ),
                    optional_text(
                        row[
                            "URI"
                        ]
                    ),
                    "phoible",
                )
            )


        connection.executemany(
            """
            INSERT INTO phoible_inventory_reference (
                mapping_row_number,
                inventory_id,
                bibtex_key,
                source_code,
                filename,
                uri,
                source_id
            )

            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            reference_records
        )


except Exception:

    connection.close()

    raise


# ---------------------------------------------------------
# FINAL COUNTS
# ---------------------------------------------------------

tables = [
    "phoible_inventory",
    "phoible_segment",
    "phoible_segment_feature",
    "phoible_inventory_segment",
    "phoible_inventory_reference",
]


counts = {}


for table in tables:

    counts[
        table
    ] = connection.execute(
        f"""
        SELECT COUNT(*)
        FROM {table}
        """
    ).fetchone()[0]


status_counts = (
    connection.execute(
        """
        SELECT
            clts_mapping_status,
            clts_mapping_method,
            COUNT(*) AS count

        FROM phoible_segment

        GROUP BY
            clts_mapping_status,
            clts_mapping_method

        ORDER BY
            clts_mapping_status,
            clts_mapping_method
        """
    ).fetchall()
)


connection.close()


# ---------------------------------------------------------
# FINAL REPORT
# ---------------------------------------------------------

print()
print("---------------------------------------------")
print("PHOIBLE IMPORT COMPLETE")
print("---------------------------------------------")


print(
    f"Inventories:        "
    f"{counts['phoible_inventory']:,}"
)

print(
    f"Segments:           "
    f"{counts['phoible_segment']:,}"
)

print(
    f"Segment features:   "
    f"{counts['phoible_segment_feature']:,}"
)

print(
    f"Inventory segments: "
    f"{counts['phoible_inventory_segment']:,}"
)

print(
    f"References:         "
    f"{counts['phoible_inventory_reference']:,}"
)


print()
print(
    "CLTS mapping results:"
)


for row in status_counts:

    print(
        f"  "
        f"{row['clts_mapping_status']}"
        f" / "
        f"{row['clts_mapping_method'] or '-'}"
        f": "
        f"{row['count']:,}"
    )


print()

print(
    "Language-name differences preserved: "
    f"{len(language_name_mismatches):,}"
)

print()

print(
    "Glottocodes not found in "
    "reference_language: "
    f"{len(unmatched_glottocodes):,}"
)


if unmatched_glottocodes:

    print(
        "Examples:"
    )

    for glottocode in sorted(
        unmatched_glottocodes
    )[:20]:

        print(
            f"  {glottocode}"
        )


print("---------------------------------------------")
print()
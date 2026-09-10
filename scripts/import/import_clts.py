from pathlib import Path
import csv
import sqlite3
import subprocess


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
# VERIFIED CLTS RELEASE
#
# These values were verified directly from the downloaded
# data/raw/clts Git checkout before this importer was written.
# ---------------------------------------------------------

EXPECTED_CLTS_TAG = "v2.3.0"

EXPECTED_CLTS_COMMIT = (
    "ec67f56a9197b072b2c15a5954a1b316864954fc"
)


# Some linguistic data files can contain large cells.
csv.field_size_limit(10_000_000)


# ---------------------------------------------------------
# EXPECTED PHYSICAL TSV HEADERS
#
# IMPORTANT:
#
# These are taken from the ACTUAL CLTS v2.3.0 TSV files.
#
# We intentionally do not use column position information
# from cldf-metadata.json because the physical v2.3.0 files
# differ from that metadata in some column ordering/content.
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
# HELPERS
# ---------------------------------------------------------

def require_file(path):
    if not path.exists():
        raise FileNotFoundError(
            f"\nCould not find:\n{path}\n\n"
            "Check the CLTS data/raw directory."
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
        raise ValueError(
            f"Expected an integer but found: {value!r}"
        ) from error


def marker_boolean(
    value,
    blank_value=0
):
    value = clean(value)

    if value is None:
        return blank_value

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

    raise ValueError(
        f"Unknown boolean marker: {value!r}"
    )


def read_rows(
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

        actual_headers = reader.fieldnames

        if actual_headers != expected_headers:

            raise RuntimeError(
                "\nUnexpected CLTS columns.\n\n"
                f"File:\n{path}\n\n"
                f"Expected:\n{expected_headers}\n\n"
                f"Found:\n{actual_headers}\n\n"
                "STOPPING rather than guessing how "
                "to interpret this CLTS release."
            )

        for row in reader:

            yield {
                key: clean(value)
                for key, value in row.items()
            }


def run_git(*arguments):
    result = subprocess.run(
        [
            "git",
            "-C",
            str(CLTS),
            *arguments,
        ],
        capture_output=True,
        text=True,
        check=True
    )

    return result.stdout.strip()


# ---------------------------------------------------------
# CHECK RAW CLTS CHECKOUT
# ---------------------------------------------------------

def verify_clts_checkout():

    print()
    print("---------------------------------------------")
    print("VERIFYING CLTS SOURCE")
    print("---------------------------------------------")

    git_directory = CLTS / ".git"

    if not git_directory.exists():

        raise RuntimeError(
            "\nThe downloaded CLTS directory does not "
            "contain its Git metadata.\n\n"
            "This importer was built specifically against "
            "the verified CLTS v2.3.0 checkout."
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

    print(f"CLTS tag:    {tag}")
    print(f"CLTS commit: {commit}")

    if status:

        raise RuntimeError(
            "\ndata/raw/clts contains local changes.\n\n"
            f"{status}\n\n"
            "Raw linguistic source data must not be "
            "manually modified."
        )

    if tag != EXPECTED_CLTS_TAG:

        raise RuntimeError(
            "\nUnexpected CLTS release.\n\n"
            f"Expected: {EXPECTED_CLTS_TAG}\n"
            f"Found:    {tag}\n\n"
            "STOPPING so the importer can be reviewed "
            "before using another CLTS release."
        )

    if commit != EXPECTED_CLTS_COMMIT:

        raise RuntimeError(
            "\nUnexpected CLTS commit.\n\n"
            f"Expected:\n{EXPECTED_CLTS_COMMIT}\n\n"
            f"Found:\n{commit}\n\n"
            "STOPPING so the importer can be reviewed."
        )

    print("CLTS checkout is clean and verified.")


# ---------------------------------------------------------
# CHECK FILES
# ---------------------------------------------------------

print()
print("Checking CLTS source files...")

require_file(
    CLTS_SOURCES
)

require_file(
    CLTS_FEATURES
)

require_file(
    CLTS_SOUNDS
)

require_file(
    CLTS_GRAPHEMES
)

verify_clts_checkout()


# ---------------------------------------------------------
# CHECK DATABASE
# ---------------------------------------------------------

if not DATABASE_FILE.exists():

    raise FileNotFoundError(
        f"\nCould not find:\n"
        f"{DATABASE_FILE}\n\n"
        "Build the reference database first."
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
    "clts_dataset",
    "clts_feature",
    "clts_sound",
    "clts_sound_feature",
    "clts_grapheme",
}


actual_tables = {
    row["name"]
    for row in connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        """
    ).fetchall()
}


missing_tables = (
    required_tables
    - actual_tables
)


if missing_tables:

    connection.close()

    raise RuntimeError(
        "\nThe CLTS database schema has not been "
        "created yet.\n\n"
        "Missing tables:\n"
        + "\n".join(
            f"  - {table}"
            for table in sorted(
                missing_tables
            )
        )
        + "\n\nRun the normal Semantic Engine rebuild "
          "after adding database/schema/005_clts.sql."
    )


# ---------------------------------------------------------
# IMPORT
# ---------------------------------------------------------

print()
print("---------------------------------------------")
print("IMPORTING CLTS")
print("---------------------------------------------")


dataset_ids = set()

feature_ids = set()

sound_ids = set()

sound_names = {}

sound_feature_count = 0

grapheme_ids = set()


try:

    with connection:

        # -------------------------------------------------
        # CLEAR PREVIOUS CLTS IMPORT
        # -------------------------------------------------

        connection.execute(
            "DELETE FROM clts_grapheme"
        )

        connection.execute(
            "DELETE FROM clts_sound_feature"
        )

        connection.execute(
            "DELETE FROM clts_sound"
        )

        connection.execute(
            "DELETE FROM clts_feature"
        )

        connection.execute(
            "DELETE FROM clts_dataset"
        )


        # -------------------------------------------------
        # REGISTER CLTS AS A REFERENCE SOURCE
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
                "clts",
                (
                    "Cross-Linguistic "
                    "Transcription Systems (CLTS)"
                ),
                "2.3.0",
                "CC BY 4.0",
                "https://clts.clld.org/",
            )
        )


        # -------------------------------------------------
        # CLTS SOURCE DATASETS
        # -------------------------------------------------

        print()
        print("Importing CLTS datasets...")

        dataset_count = 0

        for row in read_rows(
            CLTS_SOURCES,
            SOURCE_HEADERS
        ):

            dataset_id = row["NAME"]

            if dataset_id is None:

                raise RuntimeError(
                    "CLTS dataset row has no NAME."
                )

            if dataset_id in dataset_ids:

                raise RuntimeError(
                    f"Duplicate CLTS dataset: "
                    f"{dataset_id}"
                )

            dataset_ids.add(
                dataset_id
            )

            connection.execute(
                """
                INSERT INTO clts_dataset (
                    id,
                    description,
                    refs,
                    dataset_type,
                    uri_template,
                    source_id
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    dataset_id,
                    row["DESCRIPTION"],
                    row["REFS"],
                    row["TYPE"],
                    row["URITEMPLATE"],
                    "clts",
                )
            )

            dataset_count += 1


        # -------------------------------------------------
        # CLTS FEATURES
        # -------------------------------------------------

        print("Importing CLTS features...")

        feature_count = 0

        for row in read_rows(
            CLTS_FEATURES,
            FEATURE_HEADERS
        ):

            feature_id = row["ID"]

            if feature_id is None:

                raise RuntimeError(
                    "CLTS feature row has no ID."
                )

            if feature_id in feature_ids:

                raise RuntimeError(
                    f"Duplicate CLTS feature: "
                    f"{feature_id}"
                )

            feature_ids.add(
                feature_id
            )

            connection.execute(
                """
                INSERT INTO clts_feature (
                    id,
                    sound_type,
                    feature,
                    value,
                    source_id
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    feature_id,
                    row["TYPE"],
                    row["FEATURE"],
                    row["VALUE"],
                    "clts",
                )
            )

            feature_count += 1


        # -------------------------------------------------
        # CLTS SOUNDS
        # -------------------------------------------------

        print("Importing CLTS sounds...")

        sound_count = 0

        for row in read_rows(
            CLTS_SOUNDS,
            SOUND_HEADERS
        ):

            sound_id = row["ID"]

            sound_name = row["NAME"]

            if sound_id is None:

                raise RuntimeError(
                    "CLTS sound row has no ID."
                )

            if sound_name is None:

                raise RuntimeError(
                    f"CLTS sound {sound_id} "
                    "has no NAME."
                )

            if sound_id in sound_ids:

                raise RuntimeError(
                    f"Duplicate CLTS sound ID: "
                    f"{sound_id}"
                )

            if sound_name in sound_names:

                raise RuntimeError(
                    f"Duplicate CLTS sound NAME: "
                    f"{sound_name}"
                )

            sound_ids.add(
                sound_id
            )

            sound_names[
                sound_name
            ] = sound_id

            generated_marker = (
                row["GENERATED"]
            )

            is_generated = marker_boolean(
                generated_marker
            )

            connection.execute(
                """
                INSERT INTO clts_sound (
                    id,
                    name,
                    sound_type,
                    grapheme,
                    unicode_names,
                    is_generated,
                    generated_marker,
                    note,
                    source_id
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    sound_id,
                    sound_name,
                    row["TYPE"],
                    row["GRAPHEME"],
                    row["UNICODE"],
                    is_generated,
                    generated_marker,
                    row["NOTE"],
                    "clts",
                )
            )


            # ---------------------------------------------
            # NORMALIZED SOUND FEATURES
            # ---------------------------------------------

            sound_features = (
                row["FEATURES"] or ""
            ).split()


            for feature_order, feature_id in enumerate(
                sound_features,
                start=1
            ):

                if feature_id not in feature_ids:

                    raise RuntimeError(
                        "\nCLTS sound references an "
                        "unknown feature.\n\n"
                        f"Sound:\n{sound_name}\n\n"
                        f"Feature:\n{feature_id}"
                    )

                connection.execute(
                    """
                    INSERT INTO clts_sound_feature (
                        sound_id,
                        feature_id,
                        feature_order
                    )
                    VALUES (?, ?, ?)
                    """,
                    (
                        sound_id,
                        feature_id,
                        feature_order,
                    )
                )

                sound_feature_count += 1


            sound_count += 1


        # -------------------------------------------------
        # CLTS GRAPHEMES
        # -------------------------------------------------

        print("Importing CLTS grapheme mappings...")

        grapheme_count = 0

        for row in read_rows(
            CLTS_GRAPHEMES,
            GRAPHEME_HEADERS
        ):

            grapheme_id = integer(
                row["PK"]
            )

            if grapheme_id is None:

                raise RuntimeError(
                    "CLTS grapheme row has no PK."
                )

            if grapheme_id in grapheme_ids:

                raise RuntimeError(
                    f"Duplicate CLTS grapheme PK: "
                    f"{grapheme_id}"
                )

            grapheme_ids.add(
                grapheme_id
            )

            sound_name = row["NAME"]

            if sound_name not in sound_names:

                raise RuntimeError(
                    "\nCLTS grapheme references an "
                    "unknown standardized sound.\n\n"
                    f"Grapheme PK:\n{grapheme_id}\n\n"
                    f"Sound NAME:\n{sound_name}"
                )

            sound_id = (
                sound_names[
                    sound_name
                ]
            )

            dataset_id = row["DATASET"]

            if (
                dataset_id is not None
                and dataset_id not in dataset_ids
            ):

                raise RuntimeError(
                    "\nCLTS grapheme references an "
                    "unknown dataset.\n\n"
                    f"Grapheme PK:\n{grapheme_id}\n\n"
                    f"Dataset:\n{dataset_id}"
                )

            explicit_marker = (
                row["EXPLICIT"]
            )

            is_explicit = marker_boolean(
                explicit_marker
            )

            connection.execute(
                """
                INSERT INTO clts_grapheme (
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
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    grapheme_id,
                    row["GRAPHEME"],
                    sound_id,
                    is_explicit,
                    explicit_marker,
                    dataset_id,
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
            )

            grapheme_count += 1


except Exception:

    connection.close()

    raise


# ---------------------------------------------------------
# FINAL DATABASE COUNTS
# ---------------------------------------------------------

counts = {}

for table in [
    "clts_dataset",
    "clts_feature",
    "clts_sound",
    "clts_sound_feature",
    "clts_grapheme",
]:

    counts[table] = (
        connection.execute(
            f"""
            SELECT COUNT(*)
            FROM {table}
            """
        ).fetchone()[0]
    )


connection.close()


# ---------------------------------------------------------
# FINAL REPORT
# ---------------------------------------------------------

print()
print("---------------------------------------------")
print("CLTS IMPORT COMPLETE")
print("---------------------------------------------")

print(
    f"Datasets:       "
    f"{counts['clts_dataset']:,}"
)

print(
    f"Features:       "
    f"{counts['clts_feature']:,}"
)

print(
    f"Sounds:         "
    f"{counts['clts_sound']:,}"
)

print(
    f"Sound features: "
    f"{counts['clts_sound_feature']:,}"
)

print(
    f"Graphemes:      "
    f"{counts['clts_grapheme']:,}"
)

print("---------------------------------------------")
print()
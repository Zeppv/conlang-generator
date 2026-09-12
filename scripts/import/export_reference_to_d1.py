from pathlib import Path
import sqlite3


ROOT = Path(__file__).resolve().parents[2]

SOURCE_DATABASE = (
    ROOT
    / "data"
    / "compiled"
    / "reference.sqlite"
)

OUTPUT_FILE = (
    ROOT
    / "data"
    / "compiled"
    / "reference-d1.sql"
)

OUTPUT_PARTS_DIRECTORY = (
    ROOT / "data" / "compiled" / "reference-d1-parts"
)

# Wrangler reads a --file argument into a JavaScript string. Keeping each
# part below 64 MiB avoids V8's string-size limit while preserving complete
# SQL statement boundaries.
MAX_D1_PART_BYTES = 64 * 1024 * 1024


# ---------------------------------------------------------
# TABLE EXPORT ORDER
#
# Parent/reference tables must be inserted before tables
# that reference them with foreign keys.
# ---------------------------------------------------------

TABLE_ORDER = [

    # Reference information
    "reference_source",

    # Core reference information
    "concept",
    "relation_type",
    "reference_language",

    # CLTS
    "clts_dataset",
    "clts_feature",
    "clts_sound",
    "clts_sound_feature",
    "clts_grapheme",

    # PHOIBLE
    "phoible_inventory",
    "phoible_segment",
    "phoible_segment_feature",
    "phoible_inventory_segment",
    "phoible_inventory_reference",

    # Phonology Engine statistics
    "phonology_analysis",
    "phonology_inventory_profile",
    "phonology_segment_prevalence",
    "phonology_segment_cooccurrence",

    # Lexibank
    "lexibank_collection",
    "lexibank_contribution",
    "lexibank_contribution_collection",
    "lexibank_language",
    "lexibank_language_collection",
    "lexibank_concept",
    "lexibank_phoneme",
    "lexibank_frequency",
    "lexibank_form",
    "lexibank_segment_token",
    "lexibank_form_segment",
    "lexibank_feature",
    "lexibank_feature_code",
    "lexibank_feature_value",

    # WordNet
    "wordnet_synset",
    "wordnet_lemma",
    "wordnet_sense",
    "wordnet_relation",
    "wordnet_sense_relation",

    # Concepticon -> WordNet
    "concept_wordnet_mapping",

    # DatSemShift
    "datsemshift_concept",
    "datsemshift_relation",

    # Semantic Engine scores
    "semantic_pair_score",
    "semantic_direction_score",

    # Unified graph edges
    "concept_relation",
]


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def quote_identifier(name):
    return '"' + name.replace('"', '""') + '"'


def sql_value(value):

    if value is None:
        return "NULL"

    if isinstance(value, bytes):
        return "X'" + value.hex() + "'"

    if isinstance(value, bool):
        return "1" if value else "0"

    if isinstance(value, int):
        return str(value)

    if isinstance(value, float):
        return repr(value)

    text = str(value)

    return "'" + text.replace("'", "''") + "'"


def write_batch(
    output,
    table,
    columns,
    rows
):

    if not rows:
        return

    column_sql = ", ".join(
        quote_identifier(column)
        for column in columns
    )

    output.write(
        f"INSERT INTO {quote_identifier(table)} "
        f"({column_sql}) VALUES\n"
    )

    values = []

    for row in rows:

        row_values = ", ".join(
            sql_value(row[column])
            for column in columns
        )

        values.append(
            f"({row_values})"
        )

    output.write(",\n".join(values))
    output.write(";\n\n")


def split_d1_export(source_path, output_directory, max_part_bytes):
    output_directory.mkdir(parents=True, exist_ok=True)
    for old_part in output_directory.glob("reference-d1-part-*.sql"):
        old_part.unlink()

    part_number = 0
    part_size = 0
    part_file = None
    part_path = None
    statement_lines = []
    parts = []

    def open_part():
        nonlocal part_number, part_size, part_file, part_path
        part_number += 1
        part_size = 0
        part_path = output_directory / (
            f"reference-d1-part-{part_number:03d}.sql"
        )
        part_file = part_path.open("w", encoding="utf-8", newline="\n")
        parts.append(part_path)

    def write_statement(statement):
        nonlocal part_size, part_file
        statement_size = len(statement.encode("utf-8"))
        if statement_size > max_part_bytes:
            raise RuntimeError(
                "A single SQL statement exceeds the D1 part-size limit.\n\n"
                f"Statement bytes: {statement_size:,}\n"
                f"Limit bytes:     {max_part_bytes:,}"
            )
        if part_file is None:
            open_part()
        elif part_size and part_size + statement_size > max_part_bytes:
            part_file.close()
            open_part()
        part_file.write(statement)
        part_size += statement_size

    try:
        with source_path.open("r", encoding="utf-8", newline="") as source:
            for line in source:
                statement_lines.append(line)
                candidate = "".join(statement_lines)
                if sqlite3.complete_statement(candidate):
                    write_statement(candidate)
                    statement_lines.clear()
        if statement_lines and "".join(statement_lines).strip():
            raise RuntimeError(
                "The D1 export ended with an incomplete SQL statement."
            )
    finally:
        if part_file is not None:
            part_file.close()

    return parts


# ---------------------------------------------------------
# CHECK SOURCE DATABASE
# ---------------------------------------------------------

if not SOURCE_DATABASE.exists():

    raise FileNotFoundError(
        f"\nCould not find:\n"
        f"{SOURCE_DATABASE}\n\n"
        "Build reference.sqlite first."
    )


print()
print("---------------------------------------------")
print("PREPARING D1 EXPORT")
print("---------------------------------------------")
print(f"Source database:")
print(SOURCE_DATABASE)
print()


connection = sqlite3.connect(
    SOURCE_DATABASE
)

connection.row_factory = sqlite3.Row


# ---------------------------------------------------------
# VERIFY THAT OUR EXPORT LIST MATCHES THE DATABASE
#
# This prevents today's exact problem from happening
# silently again when we add more linguistic tables.
# ---------------------------------------------------------

actual_tables = {
    row["name"]
    for row in connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        """
    ).fetchall()
}


expected_tables = set(TABLE_ORDER)


missing_from_database = (
    expected_tables - actual_tables
)

not_in_exporter = (
    actual_tables - expected_tables
)


if missing_from_database:

    print(
        "ERROR: These expected tables are missing "
        "from reference.sqlite:"
    )

    for table in sorted(
        missing_from_database
    ):
        print(f"  - {table}")

    connection.close()

    raise SystemExit(
        "\nD1 export cancelled."
    )


if not_in_exporter:

    print(
        "ERROR: reference.sqlite contains tables "
        "that this exporter does not know about:"
    )

    for table in sorted(
        not_in_exporter
    ):
        print(f"  - {table}")

    connection.close()

    raise SystemExit(
        "\n"
        "D1 export cancelled so we do not accidentally "
        "leave database tables behind."
    )


print(
    f"Database contains "
    f"{len(actual_tables)} application tables."
)

print(
    "All tables are included in "
    "the D1 export plan."
)


# ---------------------------------------------------------
# CREATE OUTPUT SQL FILE
# ---------------------------------------------------------

with open(
    OUTPUT_FILE,
    "w",
    encoding="utf-8",
    newline="\n"
) as output:

    output.write(
        "-- CONLANG PROJECT REFERENCE DATABASE\n"
    )

    output.write(
        "-- Automatically generated from "
        "reference.sqlite\n"
    )

    output.write(
        "-- DO NOT EDIT THIS FILE MANUALLY.\n\n"
    )

    output.write(
        "PRAGMA defer_foreign_keys = on;\n\n"
    )


    # -----------------------------------------------------
    # CREATE ALL TABLES
    # -----------------------------------------------------

    print()
    print("Writing database tables...")


    for table in TABLE_ORDER:

        result = connection.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type = 'table'
              AND name = ?
            """,
            (table,)
        ).fetchone()


        if result is None:

            connection.close()

            raise RuntimeError(
                f"Missing table: {table}"
            )


        create_sql = (
            result["sql"]
            .rstrip(";")
        )


        output.write(
            create_sql
        )

        output.write(
            ";\n\n"
        )


        print(
            f"  Created schema for: "
            f"{table}"
        )


    # -----------------------------------------------------
    # INSERT ALL DATA
    # -----------------------------------------------------

    print()
    print("Exporting table data...")


    for table in TABLE_ORDER:

        count = connection.execute(
            f"""
            SELECT COUNT(*)
            FROM {quote_identifier(table)}
            """
        ).fetchone()[0]


        print(
            f"  {table}: "
            f"{count:,} rows"
        )


        column_rows = (
            connection.execute(
                f"""
                PRAGMA table_info(
                    {quote_identifier(table)}
                )
                """
            ).fetchall()
        )


        columns = [
            row["name"]
            for row in column_rows
        ]


        cursor = connection.execute(
            f"""
            SELECT *
            FROM {quote_identifier(table)}
            """
        )


        batch = []


        for row in cursor:

            batch.append(row)


            # Keep individual INSERT statements
            # reasonably small for Cloudflare D1.
            if len(batch) >= 250:

                write_batch(
                    output,
                    table,
                    columns,
                    batch
                )

                batch = []


        write_batch(
            output,
            table,
            columns,
            batch
        )


    # -----------------------------------------------------
    # CREATE INDEXES
    # -----------------------------------------------------

    print()
    print("Writing database indexes...")


    placeholders = ",".join(
        "?"
        for _ in TABLE_ORDER
    )


    indexes = connection.execute(
        f"""
        SELECT
            name,
            tbl_name,
            sql

        FROM sqlite_master

        WHERE type = 'index'

          AND sql IS NOT NULL

          AND name NOT LIKE 'sqlite_%'

          AND tbl_name IN (
              {placeholders}
          )

        ORDER BY name
        """,
        TABLE_ORDER
    ).fetchall()


    for index in indexes:

        output.write(
            index["sql"].rstrip(";")
        )

        output.write(
            ";\n"
        )


        print(
            f"  {index['name']}"
        )


    output.write(
        "\nPRAGMA defer_foreign_keys = off;\n"
    )

    output.write(
        "PRAGMA optimize;\n"
    )


connection.close()


# ---------------------------------------------------------
# CREATE WRANGLER-SAFE PART FILES
# ---------------------------------------------------------

print()
print("Creating Wrangler-safe SQL parts...")

d1_parts = split_d1_export(
    OUTPUT_FILE,
    OUTPUT_PARTS_DIRECTORY,
    MAX_D1_PART_BYTES
)

for part in d1_parts:
    part_size_mb = part.stat().st_size / 1024 / 1024
    print(f"  {part.name}: {part_size_mb:.2f} MB")


# ---------------------------------------------------------
# FINAL REPORT
# ---------------------------------------------------------

size_mb = (
    OUTPUT_FILE.stat().st_size
    / 1024
    / 1024
)


print()
print("---------------------------------------------")
print("D1 EXPORT COMPLETE")
print("---------------------------------------------")

print("Created:")
print(OUTPUT_FILE)

print()

print(
    f"File size: "
    f"{size_mb:.2f} MB"
)

print()

print(
    f"Tables exported: "
    f"{len(TABLE_ORDER)}"
)

print(f"Wrangler-safe parts: {len(d1_parts)}")
print("Parts directory:")
print(OUTPUT_PARTS_DIRECTORY)

print("---------------------------------------------")
print()

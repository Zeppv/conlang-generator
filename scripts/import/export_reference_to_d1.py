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

print("---------------------------------------------")
print()
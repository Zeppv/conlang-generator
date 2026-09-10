from pathlib import Path
import csv
import sqlite3


ROOT = Path(__file__).resolve().parents[2]

DATABASE_FILE = (
    ROOT
    / "data"
    / "compiled"
    / "reference.sqlite"
)

MAPPING_FILE = (
    ROOT
    / "data"
    / "raw"
    / "concepticon_wordnet"
    / "Borin-2015-1532.tsv"
)


if not DATABASE_FILE.exists():
    raise FileNotFoundError(
        "reference.sqlite does not exist."
    )


if not MAPPING_FILE.exists():
    raise FileNotFoundError(
        "The Borin WordNet mapping "
        "has not been downloaded."
    )


connection = sqlite3.connect(
    DATABASE_FILE
)

connection.row_factory = sqlite3.Row

connection.execute(
    "PRAGMA foreign_keys = ON"
)


connection.execute(
    """
    DELETE FROM concept_wordnet_mapping
    WHERE mapping_method =
        'Borin-2015-1532'
    """
)


mapped = 0
unresolved_concept = 0
unresolved_sense = 0
missing_sense_key = 0


with open(
    MAPPING_FILE,
    "r",
    encoding="utf-8-sig",
    newline=""
) as file:

    reader = csv.DictReader(
        file,
        delimiter="\t"
    )


    for row in reader:

        concepticon_id = (
            row.get("CONCEPTICON_ID")
            or ""
        ).strip()

        sense_key = (
            row.get("PWN_WORD_SENSE_ID")
            or ""
        ).strip()


        if not concepticon_id:
            continue


        if not sense_key:

            missing_sense_key += 1
            continue


        concept = connection.execute(
            """
            SELECT id
            FROM concept
            WHERE concepticon_id = ?
            """,
            (concepticon_id,)
        ).fetchone()


        if concept is None:

            unresolved_concept += 1
            continue


        wordnet_sense = (
            connection.execute(
                """
                SELECT
                    id,
                    synset_id,
                    sense_key
                FROM wordnet_sense
                WHERE sense_key = ?
                """,
                (sense_key,)
            ).fetchone()
        )


        if wordnet_sense is None:

            unresolved_sense += 1
            continue


        connection.execute(
            """
            INSERT OR IGNORE INTO
            concept_wordnet_mapping (
                concept_id,
                synset_id,
                sense_id,
                sense_key,
                mapping_method,
                mapping_status,
                confidence,
                source_note
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                concept["id"],
                wordnet_sense["synset_id"],
                wordnet_sense["id"],
                sense_key,

                "Borin-2015-1532",

                "accepted",

                0.95,

                row.get("RELATION")
            )
        )


        mapped += 1


connection.commit()


unique_concepts = (
    connection.execute(
        """
        SELECT COUNT(
            DISTINCT concept_id
        )
        FROM concept_wordnet_mapping
        WHERE mapping_status = 'accepted'
        """
    ).fetchone()[0]
)


unique_synsets = (
    connection.execute(
        """
        SELECT COUNT(
            DISTINCT synset_id
        )
        FROM concept_wordnet_mapping
        WHERE mapping_status = 'accepted'
        """
    ).fetchone()[0]
)


print()
print("---------------------------------------")
print("WORDNET CONCEPT MAPPING COMPLETE")
print("---------------------------------------")

print(
    f"Mapping rows:        "
    f"{mapped:,}"
)

print(
    f"Unique concepts:     "
    f"{unique_concepts:,}"
)

print(
    f"Unique WordNet sets: "
    f"{unique_synsets:,}"
)

print(
    f"Unresolved concepts: "
    f"{unresolved_concept:,}"
)

print(
    f"Unresolved senses:   "
    f"{unresolved_sense:,}"
)

print(
    f"Missing sense keys:  "
    f"{missing_sense_key:,}"
)

print("---------------------------------------")
print()


connection.close()
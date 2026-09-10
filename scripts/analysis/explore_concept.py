from pathlib import Path
import sqlite3
import sys


ROOT = Path(__file__).resolve().parents[2]

DATABASE_FILE = (
    ROOT
    / "data"
    / "compiled"
    / "reference.sqlite"
)


if not DATABASE_FILE.exists():
    print("The reference database does not exist yet.")
    print("Run build_concept_graph.py first.")
    raise SystemExit


if len(sys.argv) > 1:
    search = " ".join(sys.argv[1:])
else:
    search = input("Concept to search for: ")


connection = sqlite3.connect(DATABASE_FILE)
connection.row_factory = sqlite3.Row


concepts = connection.execute(
    """
    SELECT *
    FROM concept
    WHERE LOWER(gloss) = LOWER(?)
       OR LOWER(gloss) LIKE LOWER(?)
    ORDER BY
        CASE
            WHEN LOWER(gloss) = LOWER(?) THEN 0
            ELSE 1
        END,
        gloss
    LIMIT 10
    """,
    (
        search,
        f"%{search}%",
        search
    )
).fetchall()


if not concepts:
    print()
    print("No concepts found.")
    connection.close()
    raise SystemExit


print()
print("MATCHING CONCEPTS")
print("-----------------")


for index, concept in enumerate(concepts, start=1):

    print(
        f"{index}. "
        f"{concept['gloss']} "
        f"(Concepticon {concept['concepticon_id']})"
    )


concept = concepts[0]


print()
print("=" * 60)
print(concept["gloss"])
print("=" * 60)

print(
    f"Concepticon ID: "
    f"{concept['concepticon_id']}"
)

print(
    f"Semantic field: "
    f"{concept['semantic_field'] or 'Unknown'}"
)

print(
    f"Category: "
    f"{concept['ontological_category'] or 'Unknown'}"
)

print()
print("Definition:")
print(
    concept["definition"]
    or "No definition stored."
)


relations = connection.execute(
    """
    SELECT
        r.*,

        source.gloss AS source_gloss,
        target.gloss AS target_gloss

    FROM concept_relation r

    JOIN concept source
      ON source.id = r.source_concept_id

    JOIN concept target
      ON target.id = r.target_concept_id

    WHERE r.source_concept_id = ?
       OR r.target_concept_id = ?

    ORDER BY

        CASE r.source_id
            WHEN 'wordnet' THEN 0
            WHEN 'clics' THEN 1
            WHEN 'concepticon' THEN 2
            ELSE 3
        END,

        COALESCE(r.family_count, 0) DESC,

        COALESCE(r.language_count, 0) DESC,

        r.relation_type

    LIMIT 100
    """,
    (
        concept["id"],
        concept["id"]
    )
).fetchall()

source_counts = connection.execute(
    """
    SELECT
        source_id,
        COUNT(*) AS count
    FROM concept_relation
    WHERE source_concept_id = ?
       OR target_concept_id = ?
    GROUP BY source_id
    ORDER BY source_id
    """,
    (
        concept["id"],
        concept["id"]
    )
).fetchall()


print()
print("RELATIONSHIP SOURCES")
print("--------------------")


if not source_counts:

    print(
        "No relationships stored."
    )

else:

    for source_row in source_counts:

        print(
            f"{source_row['source_id']}: "
            f"{source_row['count']}"
        )

print()
print("RELATED CONCEPTS")
print("----------------")


if not relations:
    print("No stored relationships.")

for relation in relations:

    if relation["source_concept_id"] == concept["id"]:

        other = relation["target_gloss"]

        arrow = (
            "→"
            if relation["directed"]
            else "↔"
        )

    else:

        other = relation["source_gloss"]

        arrow = (
            "←"
            if relation["directed"]
            else "↔"
        )

    print()
    print(
        f"{concept['gloss']} "
        f"{arrow} "
        f"{other}"
    )

    print(
        f"   relationship: "
        f"{relation['relation_type']}"
    )

    print(
        f"   source: "
        f"{relation['source_id']}"
    )

    if relation["language_count"] is not None:
        print(
            f"   languages: "
            f"{relation['language_count']}"
        )

    if relation["family_count"] is not None:
        print(
            f"   families: "
            f"{relation['family_count']}"
        )


connection.close()
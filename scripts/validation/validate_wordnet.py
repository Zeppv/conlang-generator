from pathlib import Path
import sqlite3


ROOT = Path(__file__).resolve().parents[2]

DATABASE_FILE = (
    ROOT
    / "data"
    / "compiled"
    / "reference.sqlite"
)


connection = sqlite3.connect(
    DATABASE_FILE
)


checks = {
    "WordNet synsets":
        """
        SELECT COUNT(*)
        FROM wordnet_synset
        """,

    "WordNet lemmas":
        """
        SELECT COUNT(*)
        FROM wordnet_lemma
        """,

    "WordNet senses":
        """
        SELECT COUNT(*)
        FROM wordnet_sense
        """,

    "WordNet raw relations":
        """
        SELECT COUNT(*)
        FROM wordnet_relation
        """,

    "Concept-WordNet mappings":
        """
        SELECT COUNT(*)
        FROM concept_wordnet_mapping
        WHERE mapping_status = 'accepted'
        """,

    "Unique mapped concepts":
        """
        SELECT COUNT(DISTINCT concept_id)
        FROM concept_wordnet_mapping
        WHERE mapping_status = 'accepted'
        """,

    "Derived concept relations":
        """
        SELECT COUNT(*)
        FROM concept_relation
        WHERE source_id = 'wordnet'
        """
}


print()
print("SEMANTIC DATABASE VALIDATION")
print("----------------------------")


for name, query in checks.items():

    value = connection.execute(
        query
    ).fetchone()[0]

    print(
        f"{name:<28} "
        f"{value:,}"
    )


print("----------------------------")


synset_count = connection.execute(
    """
    SELECT COUNT(*)
    FROM wordnet_synset
    """
).fetchone()[0]


if synset_count < 100000:

    print(
        "WARNING: WordNet synset count "
        "looks unexpectedly low."
    )

else:

    print(
        "WordNet import looks healthy."
    )


connection.close()
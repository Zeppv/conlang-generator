from pathlib import Path
import sqlite3

import wn
from wn.compat import sensekey


ROOT = Path(__file__).resolve().parents[2]

DATABASE_FILE = (
    ROOT
    / "data"
    / "compiled"
    / "reference.sqlite"
)

WN_DATA_DIRECTORY = (
    ROOT
    / "data"
    / "staging"
    / "wordnet_wn"
)


if not DATABASE_FILE.exists():
    raise FileNotFoundError(
        "reference.sqlite does not exist.\n"
        "Run build_concept_graph.py first."
    )


WN_DATA_DIRECTORY.mkdir(
    parents=True,
    exist_ok=True
)


# ---------------------------------------------------------
# CONFIGURE WORDNET
# ---------------------------------------------------------

wn.config.data_directory = str(
    WN_DATA_DIRECTORY
)


installed = {
    f"{lexicon.id}:{lexicon.version}"
    for lexicon in wn.lexicons()
}


if "oewn:2025" not in installed:

    print()
    print(
        "Open English WordNet 2025 is not "
        "installed in the project staging area."
    )

    print(
        "Downloading the official WordNet "
        "resource now..."
    )

    wn.download("oewn:2025")


oewn = wn.Wordnet("oewn:2025")

get_sense_key = (
    sensekey.sense_key_getter(
        "oewn:2025"
    )
)


# ---------------------------------------------------------
# OPEN OUR DATABASE
# ---------------------------------------------------------

connection = sqlite3.connect(
    DATABASE_FILE
)

connection.execute(
    "PRAGMA foreign_keys = ON"
)


# ---------------------------------------------------------
# CLEAR PREVIOUS WORDNET IMPORT
# ---------------------------------------------------------

print()
print("Preparing WordNet tables...")


connection.execute(
    """
    DELETE FROM concept_relation
    WHERE source_id = 'wordnet'
    """
)

connection.execute(
    "DELETE FROM concept_wordnet_mapping"
)

connection.execute(
    "DELETE FROM wordnet_sense_relation"
)

connection.execute(
    "DELETE FROM wordnet_relation"
)

connection.execute(
    "DELETE FROM wordnet_sense"
)

connection.execute(
    "DELETE FROM wordnet_lemma"
)

connection.execute(
    "DELETE FROM wordnet_synset"
)


connection.execute(
    """
    INSERT OR REPLACE INTO reference_source (
        id,
        name,
        version,
        license,
        source_url
    )
    VALUES (?, ?, ?, ?, ?)
    """,
    (
        "wordnet",
        "Open English WordNet",
        "2025",
        "CC BY 4.0",
        "https://en-word.net/"
    )
)

connection.commit()


# ---------------------------------------------------------
# PASS 1
# SYNSETS, LEMMAS, AND SENSES
# ---------------------------------------------------------

print()
print(
    "Importing WordNet synsets, "
    "lemmas, and senses..."
)


synset_count = 0
lemma_count = 0
sense_count = 0


for synset in oewn.synsets():

    connection.execute(
        """
        INSERT OR REPLACE INTO wordnet_synset (
            id,
            ili,
            pos,
            definition,
            source_id
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            synset.id,
            synset.ili,
            synset.pos,
            synset.definition(),
            "wordnet"
        )
    )


    for lemma in synset.lemmas():

        connection.execute(
            """
            INSERT OR IGNORE INTO wordnet_lemma (
                synset_id,
                lemma
            )
            VALUES (?, ?)
            """,
            (
                synset.id,
                lemma
            )
        )

        lemma_count += 1


    for sense in synset.senses():

        try:

            persistent_sense_key = (
                get_sense_key(sense)
            )

        except Exception:

            persistent_sense_key = None


        connection.execute(
            """
            INSERT OR REPLACE INTO wordnet_sense (
                id,
                synset_id,
                sense_key,
                lemma,
                pos
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                sense.id,
                synset.id,
                persistent_sense_key,
                sense.word().lemma(),
                synset.pos
            )
        )

        sense_count += 1


    synset_count += 1


    if synset_count % 5000 == 0:

        connection.commit()

        print(
            f"  {synset_count:,} "
            "synsets imported..."
        )


connection.commit()


# ---------------------------------------------------------
# PASS 2
# SYNSET RELATIONSHIPS
# ---------------------------------------------------------

print()
print()
print(
    "Importing WordNet "
    "synset relationships..."
)


relation_count = 0


for index, synset in enumerate(
    oewn.synsets(),
    start=1
):

    relations = synset.relations()


    for relation_type, targets in (
        relations.items()
    ):

        for target in targets:

            connection.execute(
                """
                INSERT OR IGNORE INTO wordnet_relation (
                    source_synset_id,
                    target_synset_id,
                    relation_type
                )
                VALUES (?, ?, ?)
                """,
                (
                    synset.id,
                    target.id,
                    relation_type
                )
            )

            relation_count += 1


    if index % 5000 == 0:

        connection.commit()

        print(
            f"  relationships scanned "
            f"for {index:,} synsets..."
        )


connection.commit()


# ---------------------------------------------------------
# PASS 3
# SENSE RELATIONSHIPS
# ---------------------------------------------------------

print()
print()
print(
    "Importing WordNet "
    "sense relationships..."
)


sense_relation_count = 0


for index, synset in enumerate(
    oewn.synsets(),
    start=1
):

    for sense in synset.senses():

        relations = sense.relations()


        for relation_type, targets in (
            relations.items()
        ):

            for target in targets:

                connection.execute(
                    """
                    INSERT OR IGNORE INTO
                    wordnet_sense_relation (
                        source_sense_id,
                        target_sense_id,
                        relation_type
                    )
                    VALUES (?, ?, ?)
                    """,
                    (
                        sense.id,
                        target.id,
                        relation_type
                    )
                )

                sense_relation_count += 1


    if index % 5000 == 0:

        connection.commit()

        print(
            f"  sense relationships scanned "
            f"for {index:,} synsets..."
        )


connection.commit()


# ---------------------------------------------------------
# FINAL COUNTS
# ---------------------------------------------------------

actual_synsets = connection.execute(
    """
    SELECT COUNT(*)
    FROM wordnet_synset
    """
).fetchone()[0]


actual_lemmas = connection.execute(
    """
    SELECT COUNT(*)
    FROM wordnet_lemma
    """
).fetchone()[0]


actual_senses = connection.execute(
    """
    SELECT COUNT(*)
    FROM wordnet_sense
    """
).fetchone()[0]


actual_relations = connection.execute(
    """
    SELECT COUNT(*)
    FROM wordnet_relation
    """
).fetchone()[0]


actual_sense_relations = (
    connection.execute(
        """
        SELECT COUNT(*)
        FROM wordnet_sense_relation
        """
    ).fetchone()[0]
)


print()
print("---------------------------------------")
print("WORDNET IMPORT COMPLETE")
print("---------------------------------------")

print(
    f"Synsets:             "
    f"{actual_synsets:,}"
)

print(
    f"Lemmas:              "
    f"{actual_lemmas:,}"
)

print(
    f"Senses:              "
    f"{actual_senses:,}"
)

print(
    f"Synset relationships:"
    f" {actual_relations:,}"
)

print(
    f"Sense relationships: "
    f"{actual_sense_relations:,}"
)

print("---------------------------------------")
print()


connection.execute("ANALYZE")
connection.close()
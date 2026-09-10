from pathlib import Path
from collections import defaultdict
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

connection.row_factory = sqlite3.Row

connection.execute(
    "PRAGMA foreign_keys = ON"
)


# ---------------------------------------------------------
# CLEAR PREVIOUS DERIVED WORDNET EDGES
# ---------------------------------------------------------

connection.execute(
    """
    DELETE FROM concept_relation
    WHERE source_id = 'wordnet'
    """
)


# ---------------------------------------------------------
# LOAD ACCEPTED CONCEPT ↔ SYNSET MAPPINGS
# ---------------------------------------------------------

synset_to_concepts = defaultdict(set)


rows = connection.execute(
    """
    SELECT
        concept_id,
        synset_id
    FROM concept_wordnet_mapping
    WHERE mapping_status = 'accepted'
    """
).fetchall()


for row in rows:

    synset_to_concepts[
        row["synset_id"]
    ].add(
        row["concept_id"]
    )


print()
print(
    f"Mapped WordNet synsets available: "
    f"{len(synset_to_concepts):,}"
)


# ---------------------------------------------------------
# CANONICAL RELATIONSHIP RULES
# ---------------------------------------------------------

SYNSET_RULES = {

    "hypernym":
        ("is_a", True, False),

    "instance_hypernym":
        ("instance_of", True, False),

    # Inverse of hypernym, so skip these.
    "hyponym":
        None,

    "instance_hyponym":
        None,

    # source PART → whole
    "holo_part":
        ("part_of", True, False),

    # source WHOLE → part,
    # reverse before storing
    "mero_part":
        ("part_of", True, True),

    "holo_member":
        ("member_of", True, False),

    "mero_member":
        ("member_of", True, True),

    "holo_substance":
        ("substance_of", True, False),

    "mero_substance":
        ("substance_of", True, True),

    "similar":
        ("similar_to", False, False),

    "attribute":
        ("attribute_related", False, False),

    "entails":
        ("entails", True, False),

    "causes":
        ("causes", True, False),

    "cause":
        ("causes", True, False),
}


SENSE_RULES = {

    "antonym":
        ("antonym", False, False),

    "derivation":
        (
            "derivationally_related",
            False,
            False
        ),
}


# ---------------------------------------------------------
# ADD RELATION HELPER
# ---------------------------------------------------------

seen = set()

created = 0


def add_relation(
    concept_a,
    concept_b,
    relation_type,
    directed,
    reverse,
    source_record
):

    global created

    if concept_a == concept_b:
        return


    if reverse:

        concept_a, concept_b = (
            concept_b,
            concept_a
        )


    if not directed:

        concept_a, concept_b = sorted(
            [concept_a, concept_b]
        )


    key = (
        concept_a,
        concept_b,
        relation_type,
        directed
    )


    if key in seen:
        return


    seen.add(key)


    connection.execute(
        """
        INSERT INTO concept_relation (
            source_concept_id,
            target_concept_id,
            relation_type,
            directed,
            source_id,
            source_record_id,
            relation_description
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            concept_a,
            concept_b,
            relation_type,
            1 if directed else 0,
            "wordnet",
            source_record,
            (
                "Derived from an "
                "Open English WordNet "
                "semantic relationship."
            )
        )
    )


    created += 1


# ---------------------------------------------------------
# SAME SYNSET = VERY CLOSE MEANINGS
# ---------------------------------------------------------

print(
    "Creating same-synset relationships..."
)


for synset_id, concepts in (
    synset_to_concepts.items()
):

    concept_list = sorted(concepts)


    for i in range(
        len(concept_list)
    ):

        for j in range(
            i + 1,
            len(concept_list)
        ):

            add_relation(
                concept_list[i],
                concept_list[j],
                "synonymous_or_equivalent",
                False,
                False,
                synset_id
            )


# ---------------------------------------------------------
# SYNSET RELATIONSHIPS
# ---------------------------------------------------------

print(
    "Creating WordNet synset relationships..."
)


relations = connection.execute(
    """
    SELECT
        source_synset_id,
        target_synset_id,
        relation_type
    FROM wordnet_relation
    """
)


for row in relations:

    rule = SYNSET_RULES.get(
        row["relation_type"]
    )


    if rule is None:
        continue


    source_concepts = (
        synset_to_concepts.get(
            row["source_synset_id"],
            set()
        )
    )

    target_concepts = (
        synset_to_concepts.get(
            row["target_synset_id"],
            set()
        )
    )


    if (
        not source_concepts
        or
        not target_concepts
    ):
        continue


    canonical_type, directed, reverse = rule


    for concept_a in source_concepts:

        for concept_b in target_concepts:

            add_relation(
                concept_a,
                concept_b,
                canonical_type,
                directed,
                reverse,
                (
                    f"{row['source_synset_id']}"
                    f"|{row['relation_type']}"
                    f"|{row['target_synset_id']}"
                )
            )


# ---------------------------------------------------------
# SENSE-LEVEL RELATIONSHIPS
# ---------------------------------------------------------

print(
    "Creating WordNet sense relationships..."
)


sense_to_synset = {}


for row in connection.execute(
    """
    SELECT id, synset_id
    FROM wordnet_sense
    """
):

    sense_to_synset[
        row["id"]
    ] = row["synset_id"]


sense_relations = connection.execute(
    """
    SELECT
        source_sense_id,
        target_sense_id,
        relation_type
    FROM wordnet_sense_relation
    """
)


for row in sense_relations:

    rule = SENSE_RULES.get(
        row["relation_type"]
    )


    if rule is None:
        continue


    source_synset = (
        sense_to_synset.get(
            row["source_sense_id"]
        )
    )

    target_synset = (
        sense_to_synset.get(
            row["target_sense_id"]
        )
    )


    if (
        source_synset is None
        or
        target_synset is None
    ):
        continue


    source_concepts = (
        synset_to_concepts.get(
            source_synset,
            set()
        )
    )

    target_concepts = (
        synset_to_concepts.get(
            target_synset,
            set()
        )
    )


    canonical_type, directed, reverse = (
        rule
    )


    for concept_a in source_concepts:

        for concept_b in target_concepts:

            add_relation(
                concept_a,
                concept_b,
                canonical_type,
                directed,
                reverse,
                (
                    f"{row['source_sense_id']}"
                    f"|{row['relation_type']}"
                    f"|{row['target_sense_id']}"
                )
            )


connection.commit()


print()
print("---------------------------------------")
print("WORDNET RELATION BUILD COMPLETE")
print("---------------------------------------")

print(
    f"Concept relationships added: "
    f"{created:,}"
)

print("---------------------------------------")
print()


connection.close()
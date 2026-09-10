from pathlib import Path
from collections import defaultdict
import math
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


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def clamp(value):

    return max(
        0.0,
        min(1.0, value)
    )


def saturation(
    count,
    scale
):

    if not count:
        return 0.0

    return clamp(
        1.0
        -
        math.exp(
            -float(count)
            / scale
        )
    )


def combine(*scores):

    result = 1.0

    for score in scores:

        result *= (
            1.0
            -
            clamp(score)
        )

    return clamp(
        1.0 - result
    )


# ---------------------------------------------------------
# WORDNET WEIGHTS
#
# These are generator evidence weights,
# NOT scientific probabilities.
# ---------------------------------------------------------

WORDNET_WEIGHTS = {

    "synonymous_or_equivalent":
        0.95,

    "similar_to":
        0.80,

    "derivationally_related":
        0.80,

    "is_a":
        0.55,

    "instance_of":
        0.55,

    "part_of":
        0.50,

    "member_of":
        0.45,

    "substance_of":
        0.45,

    "attribute_related":
        0.55,

    "entails":
        0.45,

    "causes":
        0.50,

    "antonym":
        0.40,
}


# ---------------------------------------------------------
# RESET SCORES
# ---------------------------------------------------------

connection.execute(
    "DELETE FROM semantic_pair_score"
)

connection.execute(
    "DELETE FROM semantic_direction_score"
)


# ---------------------------------------------------------
# PAIR EVIDENCE
# ---------------------------------------------------------

pairs = defaultdict(
    lambda: {
        "colexification": 0.0,
        "derivation": 0.0,
        "datsemshift": 0.0,
        "wordnet": 0.0,
        "sources": set(),
    }
)


relations = connection.execute(
    """
    SELECT *
    FROM concept_relation
    """
)


for relation in relations:

    concept_a = (
        relation[
            "source_concept_id"
        ]
    )

    concept_b = (
        relation[
            "target_concept_id"
        ]
    )


    if concept_a == concept_b:
        continue


    pair = tuple(
        sorted(
            [concept_a, concept_b]
        )
    )


    data = pairs[pair]


    source = relation["source_id"]

    relation_type = (
        relation["relation_type"]
    )


    # -----------------------------------------------------
    # CLICS
    # -----------------------------------------------------

    if (
        source == "clics"
        and
        relation_type
        == "colexification"
    ):

        score = saturation(
            relation["family_count"]
            or relation[
                "language_count"
            ]
            or 1,

            8.0
        )

        data["colexification"] = max(
            data["colexification"],
            score
        )

        data["sources"].add(
            "clics"
        )


    # -----------------------------------------------------
    # DATSEMSHIFT
    # -----------------------------------------------------

    elif source == "datsemshift":

        score = saturation(
            relation["family_count"]
            or
            relation["form_count"]
            or 1,

            5.0
        )

        data["datsemshift"] = max(
            data["datsemshift"],
            score
        )


        if (
            relation_type
            ==
            "semantic_derivation_shift"
        ):

            data["derivation"] = max(
                data["derivation"],
                score
            )


        data["sources"].add(
            "datsemshift"
        )


    # -----------------------------------------------------
    # WORDNET
    # -----------------------------------------------------

    elif source == "wordnet":

        score = (
            WORDNET_WEIGHTS.get(
                relation_type,
                0.25
            )
        )


        data["wordnet"] = max(
            data["wordnet"],
            score
        )


        if (
            relation_type
            ==
            "derivationally_related"
        ):

            data["derivation"] = max(
                data["derivation"],
                0.80
            )


        data["sources"].add(
            "wordnet"
        )


# ---------------------------------------------------------
# WRITE PAIR SCORES
# ---------------------------------------------------------

print()
print(
    "Building semantic pair scores..."
)


pair_count = 0


for (
    concept_a,
    concept_b
), data in pairs.items():


    lexical_link = combine(

        data["colexification"],

        data["derivation"],

        data["datsemshift"]
    )


    relatedness = combine(

        data["colexification"],

        data["datsemshift"],

        data["wordnet"]
    )


    connection.execute(
        """
        INSERT INTO semantic_pair_score (
            concept_a_id,
            concept_b_id,

            relatedness_score,
            lexical_link_score,

            colexification_score,
            derivation_score,

            datsemshift_score,
            wordnet_score,

            evidence_sources
        )

        VALUES (
            ?, ?,
            ?, ?,
            ?, ?,
            ?, ?,
            ?
        )
        """,
        (
            concept_a,
            concept_b,

            relatedness,
            lexical_link,

            data["colexification"],
            data["derivation"],

            data["datsemshift"],
            data["wordnet"],

            ",".join(
                sorted(
                    data["sources"]
                )
            )
        )
    )


    pair_count += 1


# ---------------------------------------------------------
# DIRECTIONAL DATSEMSHIFT SCORES
# ---------------------------------------------------------

print(
    "Building directional shift scores..."
)


directions = defaultdict(
    lambda: {
        "polysemy": 0.0,
        "derivation": 0.0,
        "families": 0,
    }
)


relations = connection.execute(
    """
    SELECT
        source_concept_id,
        target_concept_id,
        evidence_type,
        realization_count,
        family_count

    FROM datsemshift_relation

    WHERE directed = 1

      AND source_concept_id
            IS NOT NULL

      AND target_concept_id
            IS NOT NULL
    """
)


for relation in relations:

    key = (
        relation["source_concept_id"],
        relation["target_concept_id"]
    )


    score = saturation(
        relation["family_count"]
        or
        relation[
            "realization_count"
        ]
        or 1,

        5.0
    )


    if (
        relation["evidence_type"]
        == "polysemy"
    ):

        directions[key][
            "polysemy"
        ] = max(
            directions[key][
                "polysemy"
            ],
            score
        )


    elif (
        relation["evidence_type"]
        == "derivation"
    ):

        directions[key][
            "derivation"
        ] = max(
            directions[key][
                "derivation"
            ],
            score
        )


    directions[key]["families"] = max(

        directions[key]["families"],

        relation["family_count"]
        or 0
    )


direction_count = 0


for (
    source_concept,
    target_concept
), data in directions.items():


    shift_score = combine(

        data["polysemy"],

        data["derivation"]
    )


    connection.execute(
        """
        INSERT INTO semantic_direction_score (
            source_concept_id,
            target_concept_id,

            shift_score,
            polysemy_score,
            derivation_score,

            evidence_family_count,
            evidence_sources
        )

        VALUES (
            ?, ?,
            ?, ?, ?,
            ?,
            ?
        )
        """,
        (
            source_concept,
            target_concept,

            shift_score,

            data["polysemy"],

            data["derivation"],

            data["families"],

            "datsemshift"
        )
    )


    direction_count += 1


connection.commit()


print()
print("---------------------------------------------")
print("SEMANTIC SCORING COMPLETE")
print("---------------------------------------------")

print(
    f"Concept pairs scored:      "
    f"{pair_count:,}"
)

print(
    f"Directional shifts scored:"
    f" {direction_count:,}"
)

print("---------------------------------------------")
print()


connection.execute("ANALYZE")

connection.close()
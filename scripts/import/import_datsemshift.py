from pathlib import Path
import csv
import json
import sqlite3


ROOT = Path(__file__).resolve().parents[2]

DATABASE_FILE = (
    ROOT
    / "data"
    / "compiled"
    / "reference.sqlite"
)

PARAMETERS_FILE = (
    ROOT
    / "data"
    / "raw"
    / "datsemshift"
    / "cldf"
    / "parameters.csv"
)


csv.field_size_limit(50_000_000)


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def clean(value):

    if value is None:
        return None

    value = str(value).strip()

    if value in {
        "",
        "NA",
        "<NA>",
        "None",
        "null"
    }:
        return None

    return value


def integer(value):

    value = clean(value)

    if value is None:
        return 0

    try:
        return int(value)
    except ValueError:
        return 0


def parse_json(value):

    value = clean(value)

    if value is None:
        return []

    try:

        result = json.loads(value)

        if isinstance(result, list):
            return result

        return []

    except json.JSONDecodeError:

        return []


def json_text(value):

    if value is None:
        return None

    return json.dumps(
        value,
        ensure_ascii=False
    )


# ---------------------------------------------------------
# CHECK FILES
# ---------------------------------------------------------

if not DATABASE_FILE.exists():

    raise FileNotFoundError(
        f"\nCould not find:\n"
        f"{DATABASE_FILE}\n"
    )


if not PARAMETERS_FILE.exists():

    raise FileNotFoundError(
        f"\nCould not find:\n"
        f"{PARAMETERS_FILE}\n\n"
        "Check data/raw/datsemshift/cldf."
    )


# ---------------------------------------------------------
# OPEN DATABASE
# ---------------------------------------------------------

connection = sqlite3.connect(
    DATABASE_FILE
)

connection.row_factory = sqlite3.Row

connection.execute(
    "PRAGMA foreign_keys = ON"
)


# ---------------------------------------------------------
# SOURCE
# ---------------------------------------------------------

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
        "datsemshift",
        "Database of Semantic Shifts",
        "2024 CLDF snapshot",
        "CC BY 4.0",
        "https://datsemshift.ru/"
    )
)


# ---------------------------------------------------------
# REMOVE OLD DATSEMSHIFT IMPORT
# ---------------------------------------------------------

connection.execute(
    """
    DELETE FROM concept_relation
    WHERE source_id = 'datsemshift'
    """
)

connection.execute(
    "DELETE FROM datsemshift_relation"
)

connection.execute(
    "DELETE FROM datsemshift_concept"
)

connection.commit()


# ---------------------------------------------------------
# LOAD PARAMETERS
# ---------------------------------------------------------

print()
print("Reading DatSemShift concepts...")


with open(
    PARAMETERS_FILE,
    "r",
    encoding="utf-8-sig",
    newline=""
) as file:

    rows = list(
        csv.DictReader(file)
    )


# ---------------------------------------------------------
# BUILD CONCEPTICON LOOKUP
# ---------------------------------------------------------

concepticon_lookup = {
    row["concepticon_id"]: row["id"]

    for row in connection.execute(
        """
        SELECT
            id,
            concepticon_id

        FROM concept

        WHERE concepticon_id
            IS NOT NULL
        """
    )
}


# ---------------------------------------------------------
# IMPORT DATSEMSHIFT CONCEPTS
# ---------------------------------------------------------

concept_count = 0
mapped_count = 0


for row in rows:

    parameter_id = clean(
        row.get("ID")
    )

    name = clean(
        row.get("Name")
    )

    if not parameter_id or not name:
        continue


    concepticon_id = clean(
        row.get("Concepticon_ID")
    )


    concept_id = None

    if concepticon_id:

        concept_id = (
            concepticon_lookup.get(
                concepticon_id
            )
        )


    if concept_id is not None:
        mapped_count += 1


    connection.execute(
        """
        INSERT INTO datsemshift_concept (
            id,
            name,
            concepticon_id,
            concept_id,
            gloss_in_source,
            definition,
            alias,
            domain,
            source_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            parameter_id,
            name,
            concepticon_id,
            concept_id,
            clean(
                row.get(
                    "Gloss_in_Source"
                )
            ),
            clean(
                row.get("Definition")
            ),
            clean(
                row.get("Alias")
            ),
            clean(
                row.get("Domain")
            ),
            "datsemshift"
        )
    )


    concept_count += 1


connection.commit()


print(
    f"Imported {concept_count:,} "
    "DatSemShift concepts."
)

print(
    f"Mapped {mapped_count:,} "
    "to existing Concepticon concepts."
)


# ---------------------------------------------------------
# DATSEMSHIFT PARAMETER → OUR CONCEPT LOOKUP
# ---------------------------------------------------------

parameter_to_concept = {
    row["id"]: row["concept_id"]

    for row in connection.execute(
        """
        SELECT id, concept_id
        FROM datsemshift_concept
        """
    )
}


# ---------------------------------------------------------
# INSERT RELATIONSHIP HELPER
# ---------------------------------------------------------

relation_count = 0


def add_relation(
    source_parameter,
    target_parameter,
    directed,
    evidence_type,
    realization_count,
    family_count,
    lexeme_ids,
    shift_ids,
    family_ids
):

    global relation_count


    if (
        not source_parameter
        or
        not target_parameter
        or
        source_parameter == target_parameter
    ):
        return


    source_concept = (
        parameter_to_concept.get(
            source_parameter
        )
    )

    target_concept = (
        parameter_to_concept.get(
            target_parameter
        )
    )


    # Undirected links should have one stable order,
    # otherwise A-B and B-A would be duplicated.
    if not directed:

        if (
            source_parameter
            > target_parameter
        ):

            (
                source_parameter,
                target_parameter
            ) = (
                target_parameter,
                source_parameter
            )

            (
                source_concept,
                target_concept
            ) = (
                target_concept,
                source_concept
            )


    connection.execute(
        """
        INSERT INTO datsemshift_relation (
            source_parameter_id,
            target_parameter_id,

            source_concept_id,
            target_concept_id,

            directed,
            evidence_type,

            realization_count,
            family_count,

            lexeme_ids_json,
            shift_ids_json,
            family_ids_json,

            source_id
        )

        VALUES (
            ?, ?,
            ?, ?,
            ?, ?,
            ?, ?,
            ?, ?, ?,
            ?
        )

        ON CONFLICT (
            source_parameter_id,
            target_parameter_id,
            directed,
            evidence_type
        )

        DO UPDATE SET

            realization_count =
                MAX(
                    realization_count,
                    excluded.realization_count
                ),

            family_count =
                MAX(
                    family_count,
                    excluded.family_count
                )
        """,
        (
            source_parameter,
            target_parameter,

            source_concept,
            target_concept,

            1 if directed else 0,
            evidence_type,

            realization_count,
            family_count,

            json_text(lexeme_ids),
            json_text(shift_ids),
            json_text(family_ids),

            "datsemshift"
        )
    )


    relation_count += 1


# ---------------------------------------------------------
# READ RELATIONSHIPS
# ---------------------------------------------------------

print()
print(
    "Reading DatSemShift semantic "
    "relationships..."
)


for row in rows:

    source_parameter = clean(
        row.get("ID")
    )

    if not source_parameter:
        continue


    # -----------------------------------------------------
    # DIRECTIONAL RELATIONSHIPS
    # -----------------------------------------------------

    target_concepts = parse_json(
        row.get("Target_Concepts")
    )


    for target in target_concepts:

        target_parameter = clean(
            target.get("ID")
        )


        polysemy_count = integer(
            target.get("Polysemy")
        )

        derivation_count = integer(
            target.get("Derivation")
        )


        if polysemy_count > 0:

            add_relation(
                source_parameter,
                target_parameter,
                True,
                "polysemy",
                polysemy_count,
                integer(
                    target.get(
                        "PolysemyByFamily"
                    )
                ),
                target.get(
                    "Polysemy_Lexemes",
                    []
                ),
                target.get(
                    "Polysemy_Shifts",
                    []
                ),
                target.get(
                    "Polysemy_Families",
                    []
                )
            )


        if derivation_count > 0:

            add_relation(
                source_parameter,
                target_parameter,
                True,
                "derivation",
                derivation_count,
                integer(
                    target.get(
                        "DerivationByFamily"
                    )
                ),
                target.get(
                    "Derivation_Lexemes",
                    []
                ),
                target.get(
                    "Derivation_Shifts",
                    []
                ),
                target.get(
                    "Derivation_Families",
                    []
                )
            )


    # -----------------------------------------------------
    # UNDIRECTED RELATIONSHIPS
    # -----------------------------------------------------

    linked_concepts = parse_json(
        row.get("Linked_Concepts")
    )


    for target in linked_concepts:

        target_parameter = clean(
            target.get("ID")
        )


        polysemy_count = integer(
            target.get("Polysemy")
        )

        derivation_count = integer(
            target.get("Derivation")
        )


        if polysemy_count > 0:

            add_relation(
                source_parameter,
                target_parameter,
                False,
                "polysemy",
                polysemy_count,
                integer(
                    target.get(
                        "PolysemyByFamily"
                    )
                ),
                target.get(
                    "Polysemy_Lexemes",
                    []
                ),
                target.get(
                    "Polysemy_Shifts",
                    []
                ),
                target.get(
                    "Polysemy_Families",
                    []
                )
            )


        if derivation_count > 0:

            add_relation(
                source_parameter,
                target_parameter,
                False,
                "derivation",
                derivation_count,
                integer(
                    target.get(
                        "DerivationByFamily"
                    )
                ),
                target.get(
                    "Derivation_Lexemes",
                    []
                ),
                target.get(
                    "Derivation_Shifts",
                    []
                ),
                target.get(
                    "Derivation_Families",
                    []
                )
            )


connection.commit()


# ---------------------------------------------------------
# ADD MAPPED RELATIONSHIPS TO OUR CONCEPT GRAPH
# ---------------------------------------------------------

print()
print(
    "Adding mapped DatSemShift "
    "relationships to Concept Graph..."
)


concept_relation_count = 0
seen = set()


relations = connection.execute(
    """
    SELECT *
    FROM datsemshift_relation

    WHERE source_concept_id
        IS NOT NULL

      AND target_concept_id
        IS NOT NULL
    """
)


for relation in relations:

    concept_a = (
        relation["source_concept_id"]
    )

    concept_b = (
        relation["target_concept_id"]
    )

    directed = bool(
        relation["directed"]
    )


    if not directed:

        concept_a, concept_b = sorted(
            [concept_a, concept_b]
        )


    if (
        relation["evidence_type"]
        == "polysemy"
    ):

        relation_type = (
            "semantic_polysemy_shift"
        )

    else:

        relation_type = (
            "semantic_derivation_shift"
        )


    key = (
        concept_a,
        concept_b,
        relation_type,
        directed
    )


    if key in seen:
        continue

    seen.add(key)


    connection.execute(
        """
        INSERT INTO concept_relation (
            source_concept_id,
            target_concept_id,

            relation_type,
            directed,

            form_count,
            family_count,

            source_id,
            source_record_id,
            relation_description
        )

        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            concept_a,
            concept_b,

            relation_type,

            1 if directed else 0,

            relation[
                "realization_count"
            ],

            relation[
                "family_count"
            ],

            "datsemshift",

            (
                f"{relation['source_parameter_id']}"
                "|"
                f"{relation['target_parameter_id']}"
                "|"
                f"{relation['evidence_type']}"
            ),

            (
                "Semantic relationship "
                "attested in DatSemShift."
            )
        )
    )


    concept_relation_count += 1


connection.commit()


# ---------------------------------------------------------
# FINAL REPORT
# ---------------------------------------------------------

stored_relations = (
    connection.execute(
        """
        SELECT COUNT(*)
        FROM datsemshift_relation
        """
    ).fetchone()[0]
)


mapped_relations = (
    connection.execute(
        """
        SELECT COUNT(*)
        FROM datsemshift_relation

        WHERE source_concept_id
            IS NOT NULL

          AND target_concept_id
            IS NOT NULL
        """
    ).fetchone()[0]
)


print()
print("---------------------------------------------")
print("DATSEMSHIFT IMPORT COMPLETE")
print("---------------------------------------------")

print(
    f"DatSemShift concepts:       "
    f"{concept_count:,}"
)

print(
    f"Concepticon-mapped concepts:"
    f" {mapped_count:,}"
)

print(
    f"Stored semantic relations:  "
    f"{stored_relations:,}"
)

print(
    f"Fully mapped relations:      "
    f"{mapped_relations:,}"
)

print(
    f"Concept Graph edges added:   "
    f"{concept_relation_count:,}"
)

print("---------------------------------------------")
print()


connection.execute("ANALYZE")

connection.close()
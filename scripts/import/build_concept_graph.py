from pathlib import Path
import csv
import sqlite3


# ---------------------------------------------------------
# PROJECT LOCATIONS
# ---------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]

RAW = ROOT / "data" / "raw"
COMPILED = ROOT / "data" / "compiled"

DATABASE_FILE = COMPILED / "reference.sqlite"
SCHEMA_DIR = ROOT / "database" / "schema"


CONCEPTICON = RAW / "concepticon" / "cldf"
CLICS = RAW / "clics" / "cldf"
GLOTTOLOG = RAW / "glottolog" / "cldf"


# Some linguistic CSV files contain very large cells.
csv.field_size_limit(10_000_000)


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def require_file(path):
    if not path.exists():
        raise FileNotFoundError(
            f"\nCould not find:\n{path}\n\n"
            "Check your data/raw folder names and dataset extraction."
        )
    return path


def clean(value):
    if value is None:
        return None

    value = str(value).strip()

    if value in {"", "<NA>", "NA", "None", "null"}:
        return None

    return value


def integer(value):
    value = clean(value)

    if value is None:
        return None

    try:
        return int(value)
    except ValueError:
        return None


def number(value):
    value = clean(value)

    if value is None:
        return None

    try:
        return float(value)
    except ValueError:
        return None


def boolean(value):
    value = clean(value)

    if value is None:
        return None

    return 1 if value.lower() in {
        "true",
        "yes",
        "1",
        "y"
    } else 0


# ---------------------------------------------------------
# CHECK FILES
# ---------------------------------------------------------

print()
print("Checking source files...")

concepticon_concepts = require_file(
    CONCEPTICON / "concepticon.csv"
)

concepticon_network = require_file(
    CONCEPTICON / "parameter_network.csv"
)

concepticon_relation_types = require_file(
    CONCEPTICON / "relationtypes.csv"
)

clics_concepts = require_file(
    CLICS / "concepts.csv"
)

clics_colexifications = require_file(
    CLICS / "colexifications.csv"
)

glottolog_languages = require_file(
    GLOTTOLOG / "languages.csv"
)

print("All required files were found.")


# ---------------------------------------------------------
# CREATE DATABASE
# ---------------------------------------------------------

COMPILED.mkdir(parents=True, exist_ok=True)

if DATABASE_FILE.exists():
    DATABASE_FILE.unlink()

connection = sqlite3.connect(DATABASE_FILE)

connection.execute("PRAGMA foreign_keys = ON")

schema_files = sorted(SCHEMA_DIR.glob("*.sql"))

if not schema_files:
    raise FileNotFoundError(
        f"No schema files were found in:\n{SCHEMA_DIR}"
    )

for schema_file in schema_files:

    print(
        f"Applying database schema: "
        f"{schema_file.name}"
    )

    with open(
        schema_file,
        "r",
        encoding="utf-8"
    ) as file:

        connection.executescript(
            file.read()
        )


# ---------------------------------------------------------
# RECORD SOURCES
# ---------------------------------------------------------

sources = [
    (
        "concepticon",
        "Concepticon",
        "3.4",
        "CC BY 4.0",
        "https://concepticon.clld.org"
    ),
    (
        "clics",
        "CLICS",
        "4 / dataset version 1.0",
        "CC BY 4.0",
        "https://clics.clld.org"
    ),
    (
        "glottolog",
        "Glottolog",
        "5.3",
        "CC BY 4.0",
        "https://glottolog.org"
    ),
]

connection.executemany(
    """
    INSERT INTO reference_source
    (id, name, version, license, source_url)
    VALUES (?, ?, ?, ?, ?)
    """,
    sources
)


# ---------------------------------------------------------
# IMPORT CONCEPTICON CONCEPTS
# ---------------------------------------------------------

print()
print("Importing Concepticon concepts...")

concept_count = 0
concept_skipped = 0

with open(
    concepticon_concepts,
    "r",
    encoding="utf-8-sig",
    newline=""
) as file:

    reader = csv.DictReader(file)

    for row in reader:

        concepticon_id = clean(row.get("ID"))
        gloss = clean(row.get("Name"))

        # Concepticon contains a special unmapped concept
        # with ID 0 and no name. It is not a real concept,
        # so we do not add it to our concept graph.
        if not concepticon_id or not gloss:
            concept_skipped += 1
            continue

        connection.execute(
            """
            INSERT INTO concept (
                concepticon_id,
                gloss,
                definition,
                semantic_field,
                ontological_category,
                replacement_concepticon_id,
                source_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                concepticon_id,
                gloss,
                clean(row.get("Description")),
                clean(row.get("Semantic_Field")),
                clean(row.get("Ontological_Category")),
                clean(row.get("Replacement_ID")),
                "concepticon",
            )
        )

        concept_count += 1

connection.commit()

print(f"Imported {concept_count:,} concepts.")
print(f"Skipped {concept_skipped:,} non-concept/unmapped rows.")


# ---------------------------------------------------------
# CREATE CONCEPTICON ID LOOKUP
# ---------------------------------------------------------

concept_lookup = {}

for row in connection.execute(
    "SELECT id, concepticon_id FROM concept"
):
    concept_lookup[row[1]] = row[0]


# ---------------------------------------------------------
# IMPORT CONCEPTICON RELATION TYPES
# ---------------------------------------------------------

print()
print("Importing Concepticon relationship types...")

relation_type_count = 0

with open(
    concepticon_relation_types,
    "r",
    encoding="utf-8-sig",
    newline=""
) as file:

    reader = csv.DictReader(file)

    for row in reader:

        connection.execute(
            """
            INSERT INTO relation_type (
                id,
                source_id,
                description,
                inverse_id
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                clean(row.get("ID")),
                "concepticon",
                clean(row.get("Description")),
                clean(row.get("Inverse_ID")),
            )
        )

        relation_type_count += 1

connection.commit()

print(
    f"Imported {relation_type_count:,} relationship types."
)


# ---------------------------------------------------------
# IMPORT CONCEPTICON RELATIONSHIPS
# ---------------------------------------------------------

print()
print("Importing Concepticon concept relationships...")

concepticon_relation_count = 0
concepticon_skipped = 0

with open(
    concepticon_network,
    "r",
    encoding="utf-8-sig",
    newline=""
) as file:

    reader = csv.DictReader(file)

    for row in reader:

        source_external = clean(
            row.get("Source_Parameter_ID")
        )

        target_external = clean(
            row.get("Target_Parameter_ID")
        )

        source_id = concept_lookup.get(source_external)
        target_id = concept_lookup.get(target_external)

        if source_id is None or target_id is None:
            concepticon_skipped += 1
            continue

        relation = clean(row.get("relation")) or "related"

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
                source_id,
                target_id,
                relation,
                boolean(row.get("Edge_Is_Directed")) or 0,
                "concepticon",
                clean(row.get("ID")),
                clean(row.get("Description")),
            )
        )

        concepticon_relation_count += 1

connection.commit()

print(
    f"Imported {concepticon_relation_count:,} "
    "Concepticon relationships."
)

if concepticon_skipped:
    print(
        f"Skipped {concepticon_skipped:,} relationships "
        "that could not be resolved."
    )


# ---------------------------------------------------------
# IMPORT CLICS CONCEPT MAPPING
# ---------------------------------------------------------

print()
print("Reading CLICS concept mappings...")


clics_lookup = {}


with open(
    clics_concepts,
    "r",
    encoding="utf-8-sig",
    newline=""
) as file:

    reader = csv.DictReader(file)

    for row in reader:

        clics_id = clean(
            row.get("ID")
        )

        concepticon_id = clean(
            row.get("Concepticon_ID")
        )

        clics_name = clean(
            row.get("Name")
        )

        concepticon_gloss = clean(
            row.get("Concepticon_Gloss")
        )


        if not concepticon_id:
            continue


        # CLICS internal ID -> Concepticon ID
        if clics_id:
            clics_lookup[
                clics_id
            ] = concepticon_id


        # Concepticon ID -> itself
        #
        # Some CLICS files may reference Concepticon
        # directly rather than the CLICS-local ID.
        clics_lookup[
            concepticon_id
        ] = concepticon_id


        # These name mappings are only fallbacks.
        if clics_name:
            clics_lookup[
                clics_name
            ] = concepticon_id


        if concepticon_gloss:
            clics_lookup[
                concepticon_gloss
            ] = concepticon_id


print(
    f"Loaded {len(clics_lookup):,} "
    "CLICS concept lookup keys."
)


def resolve_clics_concept(value):

    value = clean(value)

    if value is None:
        return None


    # First possibility:
    # CLICS is already giving us a Concepticon ID.
    direct = concept_lookup.get(
        value
    )

    if direct is not None:
        return direct


    # Second possibility:
    # CLICS is giving us its own internal concept ID.
    concepticon_id = clics_lookup.get(
        value
    )

    if concepticon_id is None:
        return None


    return concept_lookup.get(
        concepticon_id
    )


# ---------------------------------------------------------
# IMPORT CLICS COLEXIFICATIONS
# ---------------------------------------------------------

print()
print(
    "Importing CLICS " 
    "colexification relationships..."
)


clics_relation_count = 0
clics_skipped = 0

unresolved_examples = []


with open(
    clics_colexifications,
    "r",
    encoding="utf-8-sig",
    newline=""
) as file:

    reader = csv.DictReader(file)


    print(
        "CLICS colexification columns:"
    )

    print(
        ", ".join(
            reader.fieldnames or []
        )
    )


    for row in reader:

        source_raw = clean(
            row.get("Source_Concept")
        )

        target_raw = clean(
            row.get("Target_Concept")
        )


        source_id = (
            resolve_clics_concept(
                source_raw
            )
        )

        target_id = (
            resolve_clics_concept(
                target_raw
            )
        )


        if (
            source_id is None
            or
            target_id is None
        ):

            clics_skipped += 1


            if len(
                unresolved_examples
            ) < 10:

                unresolved_examples.append(
                    (
                        source_raw,
                        target_raw
                    )
                )


            continue


        if source_id == target_id:
            continue


        # Colexification is undirected.
        # Store every pair in one consistent order.
        concept_a, concept_b = sorted(
            [
                source_id,
                target_id
            ]
        )


        connection.execute(
            """
            INSERT INTO concept_relation (
                source_concept_id,
                target_concept_id,

                relation_type,
                directed,

                form_count,
                variety_count,
                language_count,
                family_count,

                variety_weight,
                language_weight,
                family_weight,

                source_id,
                source_record_id,
                relation_description
            )

            VALUES (
                ?, ?,
                ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?
            )
            """,
            (
                concept_a,
                concept_b,

                "colexification",
                0,

                integer(
                    row.get(
                        "Form_Count"
                    )
                ),

                integer(
                    row.get(
                        "Variety_Count"
                    )
                ),

                integer(
                    row.get(
                        "Language_Count"
                    )
                ),

                integer(
                    row.get(
                        "Family_Count"
                    )
                ),

                number(
                    row.get(
                        "Variety_Weight"
                    )
                ),

                number(
                    row.get(
                        "Language_Weight"
                    )
                ),

                number(
                    row.get(
                        "Family_Weight"
                    )
                ),

                "clics",

                clean(
                    row.get("ID")
                ),

                (
                    "The same lexical form "
                    "expresses both concepts "
                    "in one or more CLICS "
                    "language varieties."
                )
            )
        )


        clics_relation_count += 1


connection.commit()


print(
    f"Imported "
    f"{clics_relation_count:,} "
    "CLICS colexification relationships."
)


print(
    f"Skipped "
    f"{clics_skipped:,} "
    "CLICS relationships."
)


if unresolved_examples:

    print()
    print(
        "Examples of unresolved "
        "CLICS concept identifiers:"
    )

    for source, target in (
        unresolved_examples
    ):

        print(
            f"  {source!r} "
            f"<-> "
            f"{target!r}"
        )
# ---------------------------------------------------------
# IMPORT GLOTTOLOG
# ---------------------------------------------------------

print()
print("Importing Glottolog languages and families...")

language_count = 0

with open(
    glottolog_languages,
    "r",
    encoding="utf-8-sig",
    newline=""
) as file:

    reader = csv.DictReader(file)

    for row in reader:

        glottocode = (
            clean(row.get("Glottocode"))
            or clean(row.get("ID"))
        )

        name = clean(row.get("Name"))

        if not glottocode or not name:
            continue

        connection.execute(
            """
            INSERT OR IGNORE INTO reference_language (
                glottocode,
                name,
                iso639_3,
                level,
                macroarea,
                latitude,
                longitude,
                family_glottocode,
                parent_language_glottocode,
                is_isolate,
                source_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                glottocode,
                name,
                clean(row.get("ISO639P3code")),
                clean(row.get("Level")),
                clean(row.get("Macroarea")),
                number(row.get("Latitude")),
                number(row.get("Longitude")),
                clean(row.get("Family_ID")),
                clean(row.get("Language_ID")),
                boolean(row.get("Is_Isolate")),
                "glottolog",
            )
        )

        language_count += 1

connection.commit()

print(
    f"Imported {language_count:,} "
    "Glottolog language/family records."
)


# ---------------------------------------------------------
# FINAL STATISTICS
# ---------------------------------------------------------

concept_total = connection.execute(
    "SELECT COUNT(*) FROM concept"
).fetchone()[0]

relation_total = connection.execute(
    "SELECT COUNT(*) FROM concept_relation"
).fetchone()[0]

language_total = connection.execute(
    "SELECT COUNT(*) FROM reference_language"
).fetchone()[0]


print()
print("---------------------------------------------")
print("CONCEPT GRAPH BUILD COMPLETE")
print("---------------------------------------------")
print(f"Concepts:      {concept_total:,}")
print(f"Relationships: {relation_total:,}")
print(f"Languages:     {language_total:,}")
print()
print(f"Database created at:")
print(DATABASE_FILE)
print("---------------------------------------------")
print()

connection.execute("VACUUM")
connection.close()
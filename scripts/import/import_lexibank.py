from pathlib import Path
from collections import Counter, defaultdict
import csv
import io
import re
import sqlite3
import subprocess
import zipfile


# ---------------------------------------------------------
# PROJECT LOCATIONS
# ---------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
COMPILED = ROOT / "data" / "compiled"
DATABASE_FILE = COMPILED / "reference.sqlite"
SCHEMA_FILE = ROOT / "database" / "schema" / "007_lexibank.sql"

LEXIBANK = RAW / "lexibank"
CLDF = LEXIBANK / "cldf"
FORMS_ZIP = CLDF / "forms.csv.zip"
SOURCES_BIB = CLDF / "sources.bib"


# ---------------------------------------------------------
# VERIFIED LEXIBANK RELEASE
# ---------------------------------------------------------

EXPECTED_COMMIT = "46a2c4c63ae2cbb698cfd5ceb34cfee613eba8c4"
EXPECTED_TAGS = {"v2.2", "v2.2.1"}

EXPECTED_COUNTS = {
    "collections.csv": 6,
    "contributions.csv": 134,
    "languages.csv": 5_501,
    "concepts.csv": 3_205,
    "phonemes.csv": 2_402,
    "frequencies.csv": 205_978,
    "phonology-features.csv": 34,
    "phonology-codes.csv": 87,
    "phonology-values.csv": 187_034,
    "lexicon-features.csv": 33,
    "lexicon-codes.csv": 90,
    "lexicon-values.csv": 107_349,
    "forms.csv": 1_740_092,
    "form_segments": 9_657_998,
    "segment_tokens": 2_471,
    "physical_clts_references": 1_633,
    "unmaterialized_clts_references": 769,
}


# ---------------------------------------------------------
# VERIFIED PHYSICAL HEADERS
# ---------------------------------------------------------

HEADERS = {
    "collections.csv": [
        "ID", "Name", "Description", "Varieties", "Glottocodes",
        "Concepts", "Forms",
    ],
    "contributions.csv": [
        "ID", "Name", "Description", "Contributor", "Citation",
        "Collection_IDs", "Glottocodes", "Doculects", "Concepts",
        "Senses", "Forms", "Source",
    ],
    "languages.csv": [
        "ID", "Name", "Macroarea", "Latitude", "Longitude",
        "Glottocode", "ISO639P3code", "Dataset", "Forms",
        "FormsWithSounds", "Concepts", "Incollections", "LexiCore",
        "ClicsCore", "CogCore", "ProtoCore", "Selexion", "Subgroup",
        "Family", "Family_in_Data",
    ],
    "concepts.csv": [
        "ID", "Name", "Description", "ColumnSpec", "Concepticon_ID",
        "Concepticon_Gloss", "Central_Concept", "Core_Concept",
    ],
    "phonemes.csv": [
        "ID", "Name", "Description", "ColumnSpec", "cltsReference",
    ],
    "frequencies.csv": [
        "ID", "Language_ID", "Parameter_ID", "Value", "Code_ID",
        "Comment", "Source",
    ],
    "phonology-features.csv": [
        "ID", "Name", "Description", "ColumnSpec", "Feature_Spec",
    ],
    "lexicon-features.csv": [
        "ID", "Name", "Description", "ColumnSpec", "Feature_Spec",
    ],
    "phonology-codes.csv": [
        "ID", "Parameter_ID", "Name", "Description",
    ],
    "lexicon-codes.csv": [
        "ID", "Parameter_ID", "Name", "Description",
    ],
    "phonology-values.csv": [
        "ID", "Language_ID", "Parameter_ID", "Value", "Code_ID",
        "Comment", "Source",
    ],
    "lexicon-values.csv": [
        "ID", "Language_ID", "Parameter_ID", "Value", "Code_ID",
        "Comment", "Source",
    ],
    "forms.csv": [
        "ID", "Language_ID", "Parameter_ID", "Form", "Segments",
        "Comment", "Source", "Value", "Local_ID", "Graphemes",
        "Profile", "Cognacy", "Loan", "CV_Template",
        "Prosodic_String", "Dolgo_Sound_Classes", "SCA_Sound_Classes",
    ],
}

csv.field_size_limit(10_000_000)


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def require_file(path):
    if not path.exists():
        raise FileNotFoundError(f"\nCould not find:\n{path}")
    return path


def optional_text(value):
    return None if value in {None, ""} else value


def integer(value):
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"Expected integer, found: {value!r}") from error


def real(value):
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"Expected number, found: {value!r}") from error


def boolean(value):
    if value in {"0", "1"}:
        return int(value)
    raise RuntimeError(f"Expected 0 or 1, found: {value!r}")


def iter_csv(filename):
    path = CLDF / filename
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != HEADERS[filename]:
            raise RuntimeError(
                "\nUnexpected Lexibank columns.\n\n"
                f"File:\n{path}\n\n"
                f"Expected:\n{HEADERS[filename]}\n\n"
                f"Found:\n{reader.fieldnames}\n\n"
                "STOPPING rather than guessing how to interpret this release."
            )
        yield from reader


def iter_forms():
    with zipfile.ZipFile(FORMS_ZIP) as archive:
        names = archive.namelist()
        if names != ["forms.csv"]:
            raise RuntimeError(
                "\nUnexpected forms.csv.zip contents.\n\n"
                f"Expected: ['forms.csv']\nFound: {names}"
            )
        with io.TextIOWrapper(
            archive.open("forms.csv"), encoding="utf-8-sig", newline=""
        ) as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != HEADERS["forms.csv"]:
                raise RuntimeError(
                    "\nUnexpected Lexibank form columns.\n\n"
                    f"Expected:\n{HEADERS['forms.csv']}\n\n"
                    f"Found:\n{reader.fieldnames}"
                )
            yield from reader


def run_git(*arguments):
    result = subprocess.run(
        ["git", "-C", str(LEXIBANK), *arguments],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def check_unique(rows, field, description):
    seen = set()
    for row in rows:
        value = row[field]
        if not value:
            raise RuntimeError(f"Empty {description} found.")
        if value in seen:
            raise RuntimeError(f"Duplicate {description}: {value!r}")
        seen.add(value)


def check_count(description, expected, actual):
    if expected != actual:
        raise RuntimeError(
            f"\n{description} count mismatch.\n\n"
            f"Expected: {expected:,}\nActual:   {actual:,}"
        )


def split_space_list(value):
    return [item for item in value.split() if item]


def execute_many(connection, sql, rows, batch_size=10_000):
    batch = []
    count = 0
    for row in rows:
        batch.append(row)
        if len(batch) >= batch_size:
            connection.executemany(sql, batch)
            count += len(batch)
            batch = []
    if batch:
        connection.executemany(sql, batch)
        count += len(batch)
    return count


def execute_schema(connection):
    statement_lines = []
    with SCHEMA_FILE.open("r", encoding="utf-8") as handle:
        for line in handle:
            statement_lines.append(line)
            statement = "".join(statement_lines)
            if sqlite3.complete_statement(statement):
                if statement.strip():
                    connection.execute(statement)
                statement_lines = []
    if "".join(statement_lines).strip():
        raise RuntimeError(f"Incomplete SQL statement in {SCHEMA_FILE}")


# ---------------------------------------------------------
# VERIFY RAW CHECKOUT AND FILES
# ---------------------------------------------------------

print()
print("=============================================")
print("IMPORTING LEXIBANK")
print("=============================================")
print()
print("Verifying Lexibank source...")

if not (LEXIBANK / ".git").exists():
    raise RuntimeError("\ndata/raw/lexibank does not contain Git metadata.")

commit = run_git("rev-parse", "HEAD")
status = run_git("status", "--short")
tags = set(run_git("tag", "--points-at", "HEAD").splitlines())

if status:
    raise RuntimeError(
        "\ndata/raw/lexibank contains local changes.\n\n"
        f"{status}\n\nRaw linguistic source data must not be modified."
    )
if commit != EXPECTED_COMMIT:
    raise RuntimeError(
        "\nUnexpected Lexibank commit.\n\n"
        f"Expected: {EXPECTED_COMMIT}\nFound:    {commit}"
    )
if not EXPECTED_TAGS.issubset(tags):
    raise RuntimeError(
        "\nExpected Lexibank tags are not attached to HEAD.\n\n"
        f"Expected: {sorted(EXPECTED_TAGS)}\nFound:    {sorted(tags)}"
    )

for filename in HEADERS:
    if filename != "forms.csv":
        require_file(CLDF / filename)
require_file(FORMS_ZIP)
require_file(SOURCES_BIB)

print(f"  Commit: {commit}")
print(f"  Tags:   {', '.join(sorted(EXPECTED_TAGS))}")
print("  Checkout is clean and verified.")


# ---------------------------------------------------------
# READ AND VERIFY CORE TABLES
# ---------------------------------------------------------

print("Reading core Lexibank tables...")

collections = list(iter_csv("collections.csv"))
contributions = list(iter_csv("contributions.csv"))
languages = list(iter_csv("languages.csv"))
concepts = list(iter_csv("concepts.csv"))
phonemes = list(iter_csv("phonemes.csv"))

for filename, rows in [
    ("collections.csv", collections),
    ("contributions.csv", contributions),
    ("languages.csv", languages),
    ("concepts.csv", concepts),
    ("phonemes.csv", phonemes),
]:
    check_count(filename, EXPECTED_COUNTS[filename], len(rows))
    check_unique(rows, "ID", f"{filename} ID")

check_unique(phonemes, "Name", "phoneme name")
check_unique(phonemes, "cltsReference", "phoneme CLTS reference")
check_unique(concepts, "Concepticon_ID", "Concepticon ID")

collection_ids = {row["ID"] for row in collections}
contribution_ids = {row["ID"] for row in contributions}
language_source_ids = {row["ID"] for row in languages}
concept_source_ids = {row["ID"] for row in concepts}
phoneme_source_ids = {row["ID"] for row in phonemes}

for row in contributions:
    unknown = set(split_space_list(row["Collection_IDs"])) - collection_ids
    if unknown:
        raise RuntimeError(
            f"Contribution {row['ID']!r} uses unknown collections: {unknown}"
        )

for row in languages:
    if row["Dataset"] not in contribution_ids:
        raise RuntimeError(
            f"Language {row['ID']!r} uses unknown contribution {row['Dataset']!r}."
        )
    unknown = set(split_space_list(row["Incollections"])) - collection_ids
    if unknown:
        raise RuntimeError(
            f"Language {row['ID']!r} uses unknown collections: {unknown}"
        )

bibtex_keys = set(
    re.findall(
        r"@\w+\s*\{\s*([^,\s]+)",
        SOURCES_BIB.read_text(encoding="utf-8", errors="replace"),
    )
)
contribution_keys = {
    key.strip()
    for row in contributions
    for key in row["Source"].split(";")
    if key.strip()
}
missing_bibtex = contribution_keys - bibtex_keys
if missing_bibtex:
    raise RuntimeError(
        "\nContribution source keys missing from sources.bib:\n"
        + "\n".join(sorted(missing_bibtex))
    )


# ---------------------------------------------------------
# OPEN DATABASE AND BUILD REFERENCE LOOKUPS
# ---------------------------------------------------------

require_file(DATABASE_FILE)
require_file(SCHEMA_FILE)
connection = sqlite3.connect(DATABASE_FILE)
connection.row_factory = sqlite3.Row
connection.execute("PRAGMA foreign_keys = ON")
connection.execute("PRAGMA temp_store = MEMORY")
connection.execute("PRAGMA cache_size = -262144")

required_tables = {
    "reference_source", "reference_language", "concept", "clts_sound",
    "clts_grapheme", "lexibank_collection", "lexibank_contribution",
    "lexibank_contribution_collection", "lexibank_language",
    "lexibank_language_collection", "lexibank_concept",
    "lexibank_phoneme", "lexibank_frequency", "lexibank_form",
    "lexibank_segment_token", "lexibank_form_segment", "lexibank_feature",
    "lexibank_feature_code", "lexibank_feature_value",
}
actual_tables = {
    row["name"]
    for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    )
}
missing_tables = required_tables - actual_tables
if missing_tables:
    connection.close()
    raise RuntimeError(
        "\nLexibank schema is not ready. Missing tables:\n"
        + "\n".join(f"  - {name}" for name in sorted(missing_tables))
    )

reference_languages = {
    row["glottocode"]: row["id"]
    for row in connection.execute(
        "SELECT id, glottocode FROM reference_language"
    )
}
reference_concepts = {
    row["concepticon_id"]: row["id"]
    for row in connection.execute(
        "SELECT id, concepticon_id FROM concept WHERE concepticon_id IS NOT NULL"
    )
}
clts_sound_types = {
    row["id"]: row["sound_type"]
    for row in connection.execute("SELECT id, sound_type FROM clts_sound")
}

lex_glottocodes = {row["Glottocode"] for row in languages}
missing_glottocodes = lex_glottocodes - set(reference_languages)
if missing_glottocodes:
    connection.close()
    raise RuntimeError(
        f"\n{len(missing_glottocodes):,} Lexibank Glottocodes do not resolve.\n"
        + "\n".join(sorted(missing_glottocodes)[:50])
    )

lex_concepticon_ids = {row["Concepticon_ID"] for row in concepts}
missing_concepts = lex_concepticon_ids - set(reference_concepts)
if missing_concepts:
    connection.close()
    raise RuntimeError(
        f"\n{len(missing_concepts):,} Concepticon IDs do not resolve.\n"
        + "\n".join(sorted(missing_concepts)[:50])
    )


# ---------------------------------------------------------
# CLASSIFY CLTS REFERENCES AND FORM TOKENS
# ---------------------------------------------------------

phoneme_id_by_source = {
    row["ID"]: number for number, row in enumerate(phonemes, start=1)
}
phoneme_id_by_name = {
    row["Name"]: number for number, row in enumerate(phonemes, start=1)
}
phoneme_clts_sound = {}
mapping_summary = Counter()

for number, row in enumerate(phonemes, start=1):
    reference = row["cltsReference"]
    if reference in clts_sound_types:
        phoneme_clts_sound[number] = reference
        mapping_summary["mapped"] += 1
    else:
        phoneme_clts_sound[number] = None
        mapping_summary["unmaterialized"] += 1

check_count(
    "physical CLTS references",
    EXPECTED_COUNTS["physical_clts_references"],
    mapping_summary["mapped"],
)
check_count(
    "unmaterialized CLTS references",
    EXPECTED_COUNTS["unmaterialized_clts_references"],
    mapping_summary["unmaterialized"],
)

clts_by_grapheme = defaultdict(set)
for row in connection.execute(
    "SELECT grapheme, sound_id FROM clts_grapheme WHERE grapheme IS NOT NULL"
):
    clts_by_grapheme[row["grapheme"]].add(row["sound_id"])
for row in connection.execute(
    "SELECT grapheme, id FROM clts_sound WHERE grapheme IS NOT NULL"
):
    clts_by_grapheme[row["grapheme"]].add(row["id"])

print("Scanning segmented forms and classifying tokens...")
token_counts = Counter()
form_count = 0
segment_count = 0

for form_count, row in enumerate(iter_forms(), start=1):
    if row["Language_ID"] not in language_source_ids:
        raise RuntimeError(f"Unknown form Language_ID: {row['Language_ID']!r}")
    if row["Parameter_ID"] not in concept_source_ids:
        raise RuntimeError(f"Unknown form Parameter_ID: {row['Parameter_ID']!r}")
    if row["Source"] not in contribution_ids:
        raise RuntimeError(f"Unknown form Source: {row['Source']!r}")
    tokens = row["Segments"].split()
    if not tokens:
        raise RuntimeError(f"Form {row['ID']!r} has no segment tokens.")
    token_counts.update(tokens)
    segment_count += len(tokens)

check_count("forms.csv", EXPECTED_COUNTS["forms.csv"], form_count)
check_count("form segments", EXPECTED_COUNTS["form_segments"], segment_count)
check_count("unique segment tokens", EXPECTED_COUNTS["segment_tokens"], len(token_counts))


def classify_token(token):
    phoneme_id = phoneme_id_by_name.get(token)
    if phoneme_id is not None:
        return "phoneme", phoneme_id, phoneme_clts_sound[phoneme_id]
    if token == "+":
        return "boundary", None, None
    if token == "∼":
        return "special", None, None
    candidates = clts_by_grapheme.get(token, set())
    if len(candidates) != 1:
        raise RuntimeError(
            f"Token {token!r} has {len(candidates)} exact CLTS candidates: "
            f"{sorted(candidates)}"
        )
    sound_id = next(iter(candidates))
    if clts_sound_types[sound_id] != "tone":
        raise RuntimeError(
            f"Non-phoneme token {token!r} maps to non-tone CLTS sound {sound_id!r}."
        )
    return "tone", None, sound_id


token_definitions = {
    token: classify_token(token) for token in sorted(token_counts)
}
token_type_summary = Counter(value[0] for value in token_definitions.values())
if token_type_summary != Counter(
    {"phoneme": 2_393, "tone": 76, "boundary": 1, "special": 1}
):
    connection.close()
    raise RuntimeError(f"Unexpected segment token classes: {token_type_summary}")

print(
    "  Token classes: "
    + ", ".join(
        f"{name}={count:,}" for name, count in sorted(token_type_summary.items())
    )
)


# ---------------------------------------------------------
# IMPORT
# ---------------------------------------------------------

language_id_by_source = {
    row["ID"]: number for number, row in enumerate(languages, start=1)
}
concept_id_by_source = {
    row["ID"]: number for number, row in enumerate(concepts, start=1)
}

print("Writing Lexibank tables...")

try:
    with connection:
        connection.execute("BEGIN IMMEDIATE")

        # Recreate the Lexibank schema instead of deleting millions of rows in
        # place. This keeps repeatable imports transactional and avoids leaving
        # large, fragmented b-trees behind after a rebuild.
        for table in [
            "lexibank_form_segment", "lexibank_segment_token",
            "lexibank_feature_value", "lexibank_feature_code",
            "lexibank_feature", "lexibank_frequency", "lexibank_form",
            "lexibank_phoneme", "lexibank_concept",
            "lexibank_language_collection", "lexibank_language",
            "lexibank_contribution_collection", "lexibank_contribution",
            "lexibank_collection",
        ]:
            connection.execute(f"DROP TABLE {table}")

        execute_schema(connection)

        # Drop the large-table indexes during loading. They are recreated below.
        for index_name in [
            "idx_lexibank_form_language",
            "idx_lexibank_form_concept",
            "idx_lexibank_form_contribution",
            "idx_lexibank_form_segment_token",
        ]:
            connection.execute(f"DROP INDEX IF EXISTS {index_name}")

        connection.execute(
            """
            INSERT INTO reference_source (id, name, version, license, source_url)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                version = excluded.version,
                license = excluded.license,
                source_url = excluded.source_url
            """,
            (
                "lexibank", "Lexibank Analysed", "2.2.1", "CC-BY-4.0",
                "https://github.com/lexibank/lexibank-analysed",
            ),
        )

        connection.executemany(
            """
            INSERT INTO lexibank_collection (
                id, name, description, variety_count, glottocode_count,
                concept_count, form_count, source_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'lexibank')
            """,
            [
                (
                    row["ID"], row["Name"], optional_text(row["Description"]),
                    integer(row["Varieties"]), integer(row["Glottocodes"]),
                    integer(row["Concepts"]), integer(row["Forms"]),
                )
                for row in collections
            ],
        )

        connection.executemany(
            """
            INSERT INTO lexibank_contribution (
                id, name, description, contributor, citation,
                collection_ids_raw, glottocode_count, doculect_count,
                concept_count, sense_count, form_count, source_keys, source_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'lexibank')
            """,
            [
                (
                    row["ID"], row["Name"], optional_text(row["Description"]),
                    optional_text(row["Contributor"]), row["Citation"],
                    row["Collection_IDs"], integer(row["Glottocodes"]),
                    integer(row["Doculects"]), integer(row["Concepts"]),
                    integer(row["Senses"]), integer(row["Forms"]), row["Source"],
                )
                for row in contributions
            ],
        )
        connection.executemany(
            "INSERT INTO lexibank_contribution_collection VALUES (?, ?)",
            [
                (row["ID"], collection_id)
                for row in contributions
                for collection_id in split_space_list(row["Collection_IDs"])
            ],
        )

        connection.executemany(
            """
            INSERT INTO lexibank_language (
                id, lexibank_id, name, macroarea, latitude, longitude,
                glottocode, iso639_3, contribution_id, declared_form_count,
                forms_with_sounds_count, concept_count, collections_raw,
                is_lexicore, is_clicscore, is_cogcore, is_protocore,
                is_selexion, subgroup, family, family_in_data,
                reference_language_id, source_id
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                'lexibank'
            )
            """,
            [
                (
                    number, row["ID"], row["Name"], row["Macroarea"],
                    real(row["Latitude"]), real(row["Longitude"]),
                    row["Glottocode"], optional_text(row["ISO639P3code"]),
                    row["Dataset"], integer(row["Forms"]),
                    integer(row["FormsWithSounds"]), integer(row["Concepts"]),
                    row["Incollections"], boolean(row["LexiCore"]),
                    boolean(row["ClicsCore"]), boolean(row["CogCore"]),
                    boolean(row["ProtoCore"]), boolean(row["Selexion"]),
                    optional_text(row["Subgroup"]), optional_text(row["Family"]),
                    optional_text(row["Family_in_Data"]),
                    reference_languages[row["Glottocode"]],
                )
                for number, row in enumerate(languages, start=1)
            ],
        )
        connection.executemany(
            "INSERT INTO lexibank_language_collection VALUES (?, ?)",
            [
                (number, collection_id)
                for number, row in enumerate(languages, start=1)
                for collection_id in split_space_list(row["Incollections"])
            ],
        )

        connection.executemany(
            """
            INSERT INTO lexibank_concept (
                id, lexibank_id, name, description, column_spec,
                concepticon_id, concepticon_gloss, central_concept,
                core_concept, reference_concept_id, source_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'lexibank')
            """,
            [
                (
                    number, row["ID"], row["Name"],
                    optional_text(row["Description"]),
                    optional_text(row["ColumnSpec"]), row["Concepticon_ID"],
                    row["Concepticon_Gloss"],
                    optional_text(row["Central_Concept"]),
                    optional_text(row["Core_Concept"]),
                    reference_concepts[row["Concepticon_ID"]],
                )
                for number, row in enumerate(concepts, start=1)
            ],
        )

        connection.executemany(
            """
            INSERT INTO lexibank_phoneme (
                id, lexibank_id, name, description, column_spec,
                clts_reference, clts_sound_id, clts_mapping_status,
                clts_mapping_method, source_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'lexibank')
            """,
            [
                (
                    number, row["ID"], row["Name"], row["Description"],
                    optional_text(row["ColumnSpec"]), row["cltsReference"],
                    phoneme_clts_sound[number],
                    "mapped" if phoneme_clts_sound[number] else "unmaterialized",
                    "exact_clts_reference" if phoneme_clts_sound[number]
                    else "lexibank_generated_reference",
                )
                for number, row in enumerate(phonemes, start=1)
            ],
        )

        frequency_count = execute_many(
            connection,
            """
            INSERT INTO lexibank_frequency (
                id, source_row_number, lexibank_id, language_id, phoneme_id,
                occurrence_count, code_id, comment, source_contribution_id,
                source_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'lexibank')
            """,
            (
                (
                    number, number, row["ID"],
                    language_id_by_source[row["Language_ID"]],
                    phoneme_id_by_source[row["Parameter_ID"]],
                    integer(row["Value"]), optional_text(row["Code_ID"]),
                    optional_text(row["Comment"]), row["Source"],
                )
                for number, row in enumerate(iter_csv("frequencies.csv"), start=1)
            ),
        )
        check_count(
            "frequencies.csv", EXPECTED_COUNTS["frequencies.csv"], frequency_count
        )

        token_id_by_text = {}
        for token_number, token in enumerate(sorted(token_definitions), start=1):
            token_type, phoneme_id, clts_sound_id = token_definitions[token]
            connection.execute(
                """
                INSERT INTO lexibank_segment_token (
                    id, token, token_type, phoneme_id, clts_sound_id, source_id
                ) VALUES (?, ?, ?, ?, ?, 'lexibank')
                """,
                (token_number, token, token_type, phoneme_id, clts_sound_id),
            )
            token_id_by_text[token] = token_number

        form_sql = """
            INSERT INTO lexibank_form (
                id, source_row_number, lexibank_id, language_id, concept_id,
                form, segments, comment, source_contribution_id, value,
                local_id, graphemes, profile, cognacy, loan, cv_template,
                prosodic_string, dolgo_sound_classes, sca_sound_classes,
                segment_count, source_id
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                'lexibank'
            )
        """
        segment_sql = """
            INSERT INTO lexibank_form_segment (form_id, segment_order, token_id)
            VALUES (?, ?, ?)
        """
        form_batch = []
        segment_batch = []
        imported_forms = 0
        imported_segments = 0

        for number, row in enumerate(iter_forms(), start=1):
            language_id = language_id_by_source[row["Language_ID"]]
            language = languages[language_id - 1]
            if row["Source"] != language["Dataset"]:
                raise RuntimeError(
                    f"Form {row['ID']!r} Source differs from its language Dataset."
                )
            tokens = row["Segments"].split()
            form_batch.append(
                (
                    number, number, row["ID"], language_id,
                    concept_id_by_source[row["Parameter_ID"]], row["Form"],
                    row["Segments"], optional_text(row["Comment"]), row["Source"],
                    optional_text(row["Value"]), optional_text(row["Local_ID"]),
                    optional_text(row["Graphemes"]), optional_text(row["Profile"]),
                    optional_text(row["Cognacy"]), optional_text(row["Loan"]),
                    row["CV_Template"], row["Prosodic_String"],
                    row["Dolgo_Sound_Classes"], row["SCA_Sound_Classes"],
                    len(tokens),
                )
            )
            segment_batch.extend(
                (number, position, token_id_by_text[token])
                for position, token in enumerate(tokens, start=1)
            )
            if len(form_batch) >= 2_000:
                connection.executemany(form_sql, form_batch)
                connection.executemany(segment_sql, segment_batch)
                imported_forms += len(form_batch)
                imported_segments += len(segment_batch)
                form_batch = []
                segment_batch = []
                if imported_forms % 100_000 == 0:
                    print(f"  Forms imported: {imported_forms:,}")

        if form_batch:
            connection.executemany(form_sql, form_batch)
            connection.executemany(segment_sql, segment_batch)
            imported_forms += len(form_batch)
            imported_segments += len(segment_batch)

        check_count("imported forms", EXPECTED_COUNTS["forms.csv"], imported_forms)
        check_count(
            "imported form segments",
            EXPECTED_COUNTS["form_segments"],
            imported_segments,
        )

        feature_value_id = 0
        for domain in ("phonology", "lexicon"):
            feature_filename = f"{domain}-features.csv"
            code_filename = f"{domain}-codes.csv"
            value_filename = f"{domain}-values.csv"
            feature_rows = list(iter_csv(feature_filename))
            code_rows = list(iter_csv(code_filename))
            check_count(feature_filename, EXPECTED_COUNTS[feature_filename], len(feature_rows))
            check_count(code_filename, EXPECTED_COUNTS[code_filename], len(code_rows))
            feature_ids = {row["ID"] for row in feature_rows}
            code_ids = {row["ID"] for row in code_rows}
            if len(feature_ids) != len(feature_rows) or len(code_ids) != len(code_rows):
                raise RuntimeError(f"Duplicate {domain} feature or code IDs.")
            if any(row["Parameter_ID"] not in feature_ids for row in code_rows):
                raise RuntimeError(f"Unknown {domain} code Parameter_ID.")

            connection.executemany(
                """
                INSERT INTO lexibank_feature (
                    feature_domain, id, name, description, column_spec,
                    feature_spec, source_id
                ) VALUES (?, ?, ?, ?, ?, ?, 'lexibank')
                """,
                [
                    (
                        domain, row["ID"], row["Name"],
                        optional_text(row["Description"]),
                        optional_text(row["ColumnSpec"]),
                        optional_text(row["Feature_Spec"]),
                    )
                    for row in feature_rows
                ],
            )
            connection.executemany(
                """
                INSERT INTO lexibank_feature_code (
                    feature_domain, id, parameter_id, name, description, source_id
                ) VALUES (?, ?, ?, ?, ?, 'lexibank')
                """,
                [
                    (
                        domain, row["ID"], row["Parameter_ID"], row["Name"],
                        optional_text(row["Description"]),
                    )
                    for row in code_rows
                ],
            )

            def value_rows():
                for source_row, row in enumerate(iter_csv(value_filename), start=1):
                    if row["Parameter_ID"] not in feature_ids:
                        raise RuntimeError(
                            f"Unknown {domain} feature: {row['Parameter_ID']!r}"
                        )
                    if row["Code_ID"] and row["Code_ID"] not in code_ids:
                        raise RuntimeError(
                            f"Unknown {domain} code: {row['Code_ID']!r}"
                        )
                    language_id = language_id_by_source.get(row["Language_ID"])
                    if language_id is None:
                        raise RuntimeError(
                            f"Unknown {domain} value Language_ID: {row['Language_ID']!r}"
                        )
                    if row["Source"] != languages[language_id - 1]["Dataset"]:
                        raise RuntimeError(
                            f"{domain} value {row['ID']!r} has inconsistent Source."
                        )
                    yield (
                        feature_value_id + source_row, domain, source_row, row["ID"],
                        language_id, row["Parameter_ID"], row["Value"],
                        optional_text(row["Code_ID"]), optional_text(row["Comment"]),
                        row["Source"],
                    )

            imported_values = execute_many(
                connection,
                """
                INSERT INTO lexibank_feature_value (
                    id, feature_domain, source_row_number, lexibank_id,
                    language_id, parameter_id, value, code_id, comment,
                    source_contribution_id, source_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'lexibank')
                """,
                value_rows(),
            )
            check_count(value_filename, EXPECTED_COUNTS[value_filename], imported_values)
            feature_value_id += imported_values

        print("Creating large-table indexes...")
        connection.execute(
            "CREATE INDEX idx_lexibank_form_language ON lexibank_form(language_id)"
        )
        connection.execute(
            "CREATE INDEX idx_lexibank_form_concept ON lexibank_form(concept_id)"
        )
        connection.execute(
            "CREATE INDEX idx_lexibank_form_contribution "
            "ON lexibank_form(source_contribution_id)"
        )
        connection.execute(
            "CREATE INDEX idx_lexibank_form_segment_token "
            "ON lexibank_form_segment(token_id)"
        )

        foreign_key_errors = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()
        if foreign_key_errors:
            raise RuntimeError(
                "Lexibank import created foreign-key errors: "
                f"{foreign_key_errors[:20]}"
            )

        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"SQLite integrity check failed: {integrity}")

except Exception:
    connection.close()
    raise


# ---------------------------------------------------------
# FINAL DATABASE CHECKS
# ---------------------------------------------------------

database_counts = {
    table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    for table in [
        "lexibank_collection", "lexibank_contribution", "lexibank_language",
        "lexibank_concept", "lexibank_phoneme", "lexibank_frequency",
        "lexibank_form", "lexibank_segment_token", "lexibank_form_segment",
        "lexibank_feature", "lexibank_feature_code", "lexibank_feature_value",
    ]
}
connection.close()

print()
print("=============================================")
print("LEXIBANK IMPORT COMPLETE")
print("=============================================")
for table, count in database_counts.items():
    print(f"{table}: {count:,}")
print(f"Physical CLTS mappings: {mapping_summary['mapped']:,}")
print(f"Unmaterialized CLTS references: {mapping_summary['unmaterialized']:,}")
print("SQLite foreign keys: OK")
print("SQLite integrity: OK")
print()

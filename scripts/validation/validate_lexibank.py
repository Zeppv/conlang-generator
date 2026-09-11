from pathlib import Path
from collections import Counter
import csv
import hashlib
import io
import json
import sqlite3
import subprocess
import zipfile


ROOT = Path(__file__).resolve().parents[2]
CLDF = ROOT / "data" / "raw" / "lexibank" / "cldf"
LEXIBANK = CLDF.parent
DATABASE_FILE = ROOT / "data" / "compiled" / "reference.sqlite"
FORMS_ZIP = CLDF / "forms.csv.zip"

EXPECTED_COMMIT = "46a2c4c63ae2cbb698cfd5ceb34cfee613eba8c4"
EXPECTED_TAGS = {"v2.2", "v2.2.1"}

EXPECTED_REFERENCE_SOURCE = (
    "lexibank",
    "Lexibank Analysed",
    "2.2.1",
    "CC-BY-4.0",
    "https://github.com/lexibank/lexibank-analysed",
)

EXPECTED_COUNTS = {
    "lexibank_collection": 6,
    "lexibank_contribution": 134,
    "lexibank_language": 5_501,
    "lexibank_concept": 3_205,
    "lexibank_phoneme": 2_402,
    "lexibank_frequency": 205_978,
    "lexibank_form": 1_740_092,
    "lexibank_segment_token": 2_471,
    "lexibank_form_segment": 9_657_998,
    "lexibank_feature": 67,
    "lexibank_feature_code": 177,
    "lexibank_feature_value": 294_383,
}

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


def optional_text(value):
    return None if value in {None, ""} else value


def integer(value):
    return int(value)


def boolean(value):
    if value not in {"0", "1"}:
        raise RuntimeError(f"Expected 0 or 1, found: {value!r}")
    return int(value)


def iter_csv(filename):
    path = CLDF / filename
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != HEADERS[filename]:
            raise RuntimeError(
                f"Unexpected columns in {filename}.\n"
                f"Expected: {HEADERS[filename]}\nFound: {reader.fieldnames}"
            )
        yield from reader


def iter_forms():
    with zipfile.ZipFile(FORMS_ZIP) as archive:
        if archive.namelist() != ["forms.csv"]:
            raise RuntimeError(
                f"Unexpected forms archive contents: {archive.namelist()}"
            )
        with io.TextIOWrapper(
            archive.open("forms.csv"), encoding="utf-8-sig", newline=""
        ) as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != HEADERS["forms.csv"]:
                raise RuntimeError(
                    f"Unexpected form columns: {reader.fieldnames}"
                )
            yield from reader


def run_git(*arguments):
    return subprocess.run(
        ["git", "-C", str(LEXIBANK), *arguments],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def update_digest(digest, row):
    encoded = json.dumps(
        list(row), ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    digest.update(encoded)
    digest.update(b"\n")


def digest_rows(rows):
    digest = hashlib.sha256()
    count = 0
    for count, row in enumerate(rows, start=1):
        update_digest(digest, row)
    return count, digest.hexdigest()


def compare_digest(description, source_rows, database_rows):
    source_count, source_digest = digest_rows(source_rows)
    database_count, database_digest = digest_rows(database_rows)
    if source_count != database_count or source_digest != database_digest:
        raise RuntimeError(
            f"\n{description} differs from the verified source.\n"
            f"Source:   {source_count:,} rows / {source_digest}\n"
            f"Database: {database_count:,} rows / {database_digest}"
        )
    print(f"  {description}: {source_count:,} exact rows")


def require_equal(description, expected, actual):
    if expected != actual:
        raise RuntimeError(
            f"{description} mismatch. Expected {expected!r}; found {actual!r}."
        )


print()
print("=============================================")
print("VALIDATING LEXIBANK")
print("=============================================")
print()

if not DATABASE_FILE.exists():
    raise FileNotFoundError(f"Could not find {DATABASE_FILE}")
if run_git("rev-parse", "HEAD") != EXPECTED_COMMIT:
    raise RuntimeError("Lexibank is not at the verified commit.")
if run_git("status", "--short"):
    raise RuntimeError("data/raw/lexibank contains local changes.")
tags = set(run_git("tag", "--points-at", "HEAD").splitlines())
if not EXPECTED_TAGS.issubset(tags):
    raise RuntimeError(f"Verified Lexibank tags are missing: {EXPECTED_TAGS - tags}")
print("Verified raw checkout and physical source headers.")

connection = sqlite3.connect(DATABASE_FILE)
connection.row_factory = sqlite3.Row
connection.execute("PRAGMA foreign_keys = ON")

actual_source = connection.execute(
    """
    SELECT id, name, version, license, source_url
    FROM reference_source WHERE id = 'lexibank'
    """
).fetchone()
require_equal(
    "Lexibank reference_source",
    EXPECTED_REFERENCE_SOURCE,
    tuple(actual_source) if actual_source else None,
)

print("Checking database row counts...")
for table, expected in EXPECTED_COUNTS.items():
    actual = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    require_equal(f"{table} count", expected, actual)
    print(f"  {table}: {actual:,}")


# ---------------------------------------------------------
# EXACT CORE-TABLE ROUND TRIPS
# ---------------------------------------------------------

compare_digest(
    "collections",
    (
        (
            row["ID"], row["Name"], optional_text(row["Description"]),
            integer(row["Varieties"]), integer(row["Glottocodes"]),
            integer(row["Concepts"]), integer(row["Forms"]), "lexibank",
        )
        for row in iter_csv("collections.csv")
    ),
    (
        tuple(row)
        for row in connection.execute(
            """
            SELECT id, name, description, variety_count, glottocode_count,
                   concept_count, form_count, source_id
            FROM lexibank_collection ORDER BY rowid
            """
        )
    ),
)

compare_digest(
    "contributions",
    (
        (
            row["ID"], row["Name"], optional_text(row["Description"]),
            optional_text(row["Contributor"]), row["Citation"],
            row["Collection_IDs"], integer(row["Glottocodes"]),
            integer(row["Doculects"]), integer(row["Concepts"]),
            integer(row["Senses"]), integer(row["Forms"]), row["Source"],
            "lexibank",
        )
        for row in iter_csv("contributions.csv")
    ),
    (
        tuple(row)
        for row in connection.execute(
            """
            SELECT id, name, description, contributor, citation,
                   collection_ids_raw, glottocode_count, doculect_count,
                   concept_count, sense_count, form_count, source_keys, source_id
            FROM lexibank_contribution ORDER BY rowid
            """
        )
    ),
)

reference_language_by_glottocode = {
    row["glottocode"]: row["id"]
    for row in connection.execute(
        "SELECT id, glottocode FROM reference_language"
    )
}
compare_digest(
    "languages/doculects",
    (
        (
            number, row["ID"], row["Name"], row["Macroarea"],
            float(row["Latitude"]), float(row["Longitude"]), row["Glottocode"],
            optional_text(row["ISO639P3code"]), row["Dataset"],
            integer(row["Forms"]), integer(row["FormsWithSounds"]),
            integer(row["Concepts"]), row["Incollections"],
            boolean(row["LexiCore"]), boolean(row["ClicsCore"]),
            boolean(row["CogCore"]), boolean(row["ProtoCore"]),
            boolean(row["Selexion"]), optional_text(row["Subgroup"]),
            optional_text(row["Family"]), optional_text(row["Family_in_Data"]),
            reference_language_by_glottocode[row["Glottocode"]], "lexibank",
        )
        for number, row in enumerate(iter_csv("languages.csv"), start=1)
    ),
    (
        tuple(row)
        for row in connection.execute(
            "SELECT * FROM lexibank_language ORDER BY id"
        )
    ),
)

reference_concept_by_concepticon = {
    row["concepticon_id"]: row["id"]
    for row in connection.execute(
        "SELECT id, concepticon_id FROM concept WHERE concepticon_id IS NOT NULL"
    )
}
compare_digest(
    "concept mappings",
    (
        (
            number, row["ID"], row["Name"], optional_text(row["Description"]),
            optional_text(row["ColumnSpec"]), row["Concepticon_ID"],
            row["Concepticon_Gloss"], optional_text(row["Central_Concept"]),
            optional_text(row["Core_Concept"]),
            reference_concept_by_concepticon[row["Concepticon_ID"]], "lexibank",
        )
        for number, row in enumerate(iter_csv("concepts.csv"), start=1)
    ),
    (
        tuple(row)
        for row in connection.execute(
            "SELECT * FROM lexibank_concept ORDER BY id"
        )
    ),
)

clts_ids = {
    row["id"] for row in connection.execute("SELECT id FROM clts_sound")
}
compare_digest(
    "phonemes and CLTS references",
    (
        (
            number, row["ID"], row["Name"], row["Description"],
            optional_text(row["ColumnSpec"]), row["cltsReference"],
            row["cltsReference"] if row["cltsReference"] in clts_ids else None,
            "mapped" if row["cltsReference"] in clts_ids else "unmaterialized",
            "exact_clts_reference" if row["cltsReference"] in clts_ids
            else "lexibank_generated_reference",
            "lexibank",
        )
        for number, row in enumerate(iter_csv("phonemes.csv"), start=1)
    ),
    (
        tuple(row)
        for row in connection.execute(
            "SELECT * FROM lexibank_phoneme ORDER BY id"
        )
    ),
)


def source_feature_rows():
    for domain in ("phonology", "lexicon"):
        for row in iter_csv(f"{domain}-features.csv"):
            yield (
                domain, row["ID"], row["Name"],
                optional_text(row["Description"]),
                optional_text(row["ColumnSpec"]),
                optional_text(row["Feature_Spec"]), "lexibank",
            )


def source_feature_code_rows():
    for domain in ("phonology", "lexicon"):
        for row in iter_csv(f"{domain}-codes.csv"):
            yield (
                domain, row["ID"], row["Parameter_ID"], row["Name"],
                optional_text(row["Description"]), "lexibank",
            )


compare_digest(
    "computed feature definitions",
    source_feature_rows(),
    (
        tuple(row)
        for row in connection.execute(
            "SELECT * FROM lexibank_feature ORDER BY feature_domain DESC, rowid"
        )
    ),
)

compare_digest(
    "computed feature codes",
    source_feature_code_rows(),
    (
        tuple(row)
        for row in connection.execute(
            "SELECT * FROM lexibank_feature_code ORDER BY feature_domain DESC, rowid"
        )
    ),
)


# ---------------------------------------------------------
# EXACT LARGE-TABLE ROUND TRIPS
# ---------------------------------------------------------

print("Checking large source tables with ordered SHA-256 round trips...")

compare_digest(
    "phoneme frequencies",
    (
        (
            number, number, row["ID"], row["Language_ID"],
            row["Parameter_ID"], integer(row["Value"]),
            optional_text(row["Code_ID"]), optional_text(row["Comment"]),
            row["Source"], "lexibank",
        )
        for number, row in enumerate(iter_csv("frequencies.csv"), start=1)
    ),
    (
        tuple(row)
        for row in connection.execute(
            """
            SELECT f.id, f.source_row_number, f.lexibank_id,
                   l.lexibank_id, p.lexibank_id, f.occurrence_count,
                   f.code_id, f.comment, f.source_contribution_id, f.source_id
            FROM lexibank_frequency AS f
            JOIN lexibank_language AS l ON l.id = f.language_id
            JOIN lexibank_phoneme AS p ON p.id = f.phoneme_id
            ORDER BY f.source_row_number
            """
        )
    ),
)

source_form_digest = hashlib.sha256()
source_segment_digest = hashlib.sha256()
source_form_count = 0
source_segment_count = 0

for source_form_count, row in enumerate(iter_forms(), start=1):
    tokens = row["Segments"].split()
    update_digest(
        source_form_digest,
        (
            source_form_count, source_form_count, row["ID"], row["Language_ID"],
            row["Parameter_ID"], row["Form"], row["Segments"],
            optional_text(row["Comment"]), row["Source"],
            optional_text(row["Value"]), optional_text(row["Local_ID"]),
            optional_text(row["Graphemes"]), optional_text(row["Profile"]),
            optional_text(row["Cognacy"]), optional_text(row["Loan"]),
            row["CV_Template"], row["Prosodic_String"],
            row["Dolgo_Sound_Classes"], row["SCA_Sound_Classes"],
            len(tokens), "lexibank",
        ),
    )
    for position, token in enumerate(tokens, start=1):
        source_segment_count += 1
        update_digest(
            source_segment_digest, (source_form_count, position, token)
        )

database_form_count, database_form_digest = digest_rows(
    tuple(row)
    for row in connection.execute(
        """
        SELECT f.id, f.source_row_number, f.lexibank_id,
               l.lexibank_id, c.lexibank_id, f.form, f.segments,
               f.comment, f.source_contribution_id, f.value, f.local_id,
               f.graphemes, f.profile, f.cognacy, f.loan, f.cv_template,
               f.prosodic_string, f.dolgo_sound_classes, f.sca_sound_classes,
               f.segment_count, f.source_id
        FROM lexibank_form AS f
        JOIN lexibank_language AS l ON l.id = f.language_id
        JOIN lexibank_concept AS c ON c.id = f.concept_id
        ORDER BY f.source_row_number
        """
    )
)
if (
    source_form_count != database_form_count
    or source_form_digest.hexdigest() != database_form_digest
):
    raise RuntimeError("Lexibank forms do not exactly match forms.csv.")
print(f"  forms: {source_form_count:,} exact rows")

database_segment_count, database_segment_digest = digest_rows(
    tuple(row)
    for row in connection.execute(
        """
        SELECT fs.form_id, fs.segment_order, t.token
        FROM lexibank_form_segment AS fs
        JOIN lexibank_segment_token AS t ON t.id = fs.token_id
        ORDER BY fs.form_id, fs.segment_order
        """
    )
)
if (
    source_segment_count != database_segment_count
    or source_segment_digest.hexdigest() != database_segment_digest
):
    raise RuntimeError("Ordered form segments do not exactly match forms.csv.")
print(f"  ordered segment occurrences: {source_segment_count:,} exact rows")


def source_feature_value_rows():
    internal_id = 0
    for domain in ("phonology", "lexicon"):
        for source_row, row in enumerate(
            iter_csv(f"{domain}-values.csv"), start=1
        ):
            internal_id += 1
            yield (
                internal_id, domain, source_row, row["ID"], row["Language_ID"],
                row["Parameter_ID"], row["Value"], optional_text(row["Code_ID"]),
                optional_text(row["Comment"]), row["Source"], "lexibank",
            )


compare_digest(
    "computed feature values",
    source_feature_value_rows(),
    (
        tuple(row)
        for row in connection.execute(
            """
            SELECT v.id, v.feature_domain, v.source_row_number, v.lexibank_id,
                   l.lexibank_id, v.parameter_id, v.value, v.code_id,
                   v.comment, v.source_contribution_id, v.source_id
            FROM lexibank_feature_value AS v
            JOIN lexibank_language AS l ON l.id = v.language_id
            ORDER BY v.id
            """
        )
    ),
)


# ---------------------------------------------------------
# ARCHITECTURAL INVARIANTS AND SPECIAL CASES
# ---------------------------------------------------------

mapping_summary = Counter(
    {
        row["clts_mapping_status"]: row["count"]
        for row in connection.execute(
            """
            SELECT clts_mapping_status, COUNT(*) AS count
            FROM lexibank_phoneme GROUP BY clts_mapping_status
            """
        )
    }
)
require_equal("mapped CLTS references", 1_633, mapping_summary["mapped"])
require_equal(
    "unmaterialized CLTS references", 769, mapping_summary["unmaterialized"]
)

token_types = {
    row["token_type"]: row["count"]
    for row in connection.execute(
        "SELECT token_type, COUNT(*) AS count FROM lexibank_segment_token GROUP BY token_type"
    )
}
require_equal(
    "segment token classes",
    {"phoneme": 2_393, "tone": 76, "boundary": 1, "special": 1},
    token_types,
)

for token, token_type, expected_occurrences in [
    ("+", "boundary", 404_920),
    ("∼", "special", 2_186),
]:
    row = connection.execute(
        """
        SELECT t.token_type, COUNT(fs.form_id) AS occurrences
        FROM lexibank_segment_token AS t
        LEFT JOIN lexibank_form_segment AS fs ON fs.token_id = t.id
        WHERE t.token = ? GROUP BY t.id
        """,
        (token,),
    ).fetchone()
    require_equal(f"{token!r} token type", token_type, row["token_type"])
    require_equal(
        f"{token!r} occurrences", expected_occurrences, row["occurrences"]
    )

generated_usage = connection.execute(
    """
    SELECT COUNT(DISTINCT p.id) AS phonemes,
           COUNT(fs.form_id) AS occurrences,
           COUNT(DISTINCT fs.form_id) AS forms
    FROM lexibank_phoneme AS p
    JOIN lexibank_segment_token AS t ON t.phoneme_id = p.id
    JOIN lexibank_form_segment AS fs ON fs.token_id = t.id
    WHERE p.clts_mapping_status = 'unmaterialized'
    """
).fetchone()
require_equal(
    "used unmaterialized CLTS references", 762, generated_usage["phonemes"]
)
require_equal(
    "unmaterialized-reference token occurrences", 48_194,
    generated_usage["occurrences"],
)
require_equal(
    "forms using unmaterialized CLTS references", 35_126,
    generated_usage["forms"],
)

source_mismatches = connection.execute(
    """
    SELECT COUNT(*)
    FROM lexibank_form AS f
    JOIN lexibank_language AS l ON l.id = f.language_id
    WHERE f.source_contribution_id <> l.contribution_id
    """
).fetchone()[0]
require_equal("form source/language contribution mismatches", 0, source_mismatches)

unresolved_languages = connection.execute(
    """
    SELECT COUNT(*) FROM lexibank_language
    WHERE reference_language_id IS NULL
    """
).fetchone()[0]
unresolved_concepts = connection.execute(
    """
    SELECT COUNT(*) FROM lexibank_concept
    WHERE reference_concept_id IS NULL
    """
).fetchone()[0]
require_equal("unresolved Glottolog links", 0, unresolved_languages)
require_equal("unresolved Concepticon links", 0, unresolved_concepts)

foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
if foreign_key_errors:
    raise RuntimeError(f"Foreign-key errors: {foreign_key_errors[:20]}")
integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
require_equal("SQLite integrity", "ok", integrity)

connection.close()

print()
print("=============================================")
print("LEXIBANK VALIDATION PASSED")
print("=============================================")
print("Forms validated:                   1,740,092")
print("Ordered segments validated:        9,657,998")
print("Languages/doculects validated:         5,501")
print("Concepts validated:                    3,205")
print("Phonemes validated:                    2,402")
print("Physical CLTS references:              1,633")
print("Unmaterialized CLTS references:          769")
print("Feature values validated:             294,383")
print("Foreign keys: OK")
print("SQLite integrity: OK")
print()

from itertools import zip_longest
from pathlib import Path
import sqlite3
import sys


ROOT = Path(__file__).resolve().parents[2]
DATABASE_FILE = ROOT / "data" / "compiled" / "reference.sqlite"
sys.path.insert(0, str(ROOT / "scripts" / "analysis"))

from build_phonology_statistics import (  # noqa: E402
    ANALYSIS_ID,
    ANALYSIS_NOTES,
    EXPECTED_ABSENCE_MINIMUM,
    METHOD_VERSION,
    cooccurrence_rows,
    inventory_profile_rows,
    load_evidence,
    prevalence_rows,
    require_database_state,
)


EXPECTED_COUNTS = {
    "phonology_analysis": 1,
    "phonology_inventory_profile": 3_020,
    "phonology_segment_prevalence": 6_350,
    "phonology_segment_cooccurrence": 570_320,
}

EXPECTED_EVIDENCE_COUNTS = {
    ("inventory", "observed"): 256_181,
    ("inventory", "expected_absence"): 1_931,
    ("language", "observed"): 311_088,
    ("language", "expected_absence"): 1_120,
}


def compare_rows(description, expected_rows, actual_rows):
    count = 0
    for number, (expected, actual) in enumerate(
        zip_longest(expected_rows, actual_rows), start=1
    ):
        if expected is None:
            raise RuntimeError(
                f"{description} has an unexpected row at {number}."
            )
        if actual is None:
            raise RuntimeError(f"{description} is missing row {number}.")
        if tuple(expected) != tuple(actual):
            raise RuntimeError(
                f"{description} mismatch at row {number}.\n\n"
                f"Expected:\n{tuple(expected)}\n\nActual:\n{tuple(actual)}"
            )
        count += 1
    print(f"  {description}: {count:,} rows")
    return count


def main():
    if not DATABASE_FILE.exists():
        raise FileNotFoundError(f"Could not find: {DATABASE_FILE}")

    print("\n=============================================")
    print("VALIDATING PHONOLOGY STATISTICS")
    print("=============================================\n")
    connection = sqlite3.connect(DATABASE_FILE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        require_database_state(connection)
        print("Checking SQLite integrity...")
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_keys:
            raise RuntimeError(f"Foreign-key violations: {foreign_keys[:20]}")
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"SQLite integrity check failed: {integrity}")
        print("  Foreign keys: OK")
        print("  SQLite integrity: OK")

        print("Checking derived table counts...")
        for table, expected in EXPECTED_COUNTS.items():
            actual = connection.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]
            if actual != expected:
                raise RuntimeError(
                    f"{table} count mismatch: expected {expected:,}, "
                    f"found {actual:,}"
                )
            print(f"  {table}: {actual:,}")

        print("Rebuilding PHOIBLE evidence units...")
        evidence = load_evidence(connection)
        inventory_units = evidence["inventory_segments"]
        language_units = evidence["language_segments"]
        segment_classes = evidence["segment_classes"]
        segment_ids = sorted(segment_classes)
        distinct = sum(len(value) for value in inventory_units.values())
        repeated = evidence["observation_count"] - distinct
        without_glottocode = sum(
            not value for value in evidence["inventory_glottocodes"].values()
        )
        expected_metadata = (
            ANALYSIS_ID,
            METHOD_VERSION,
            len(inventory_units),
            len(language_units),
            without_glottocode,
            len(segment_ids),
            evidence["observation_count"],
            repeated,
            EXPECTED_ABSENCE_MINIMUM,
            ANALYSIS_NOTES,
            "phoible",
        )
        actual_metadata = connection.execute(
            "SELECT * FROM phonology_analysis WHERE id = ?", (ANALYSIS_ID,)
        ).fetchone()
        if actual_metadata is None or tuple(actual_metadata) != expected_metadata:
            raise RuntimeError(
                "Phonology analysis metadata mismatch.\n\n"
                f"Expected:\n{expected_metadata}\n\n"
                f"Actual:\n{tuple(actual_metadata) if actual_metadata else None}"
            )
        print("  Analysis metadata matches.")

        print("Comparing inventory profiles...")
        profile_count = compare_rows(
            "Inventory profiles",
            inventory_profile_rows(evidence),
            connection.execute(
                "SELECT * FROM phonology_inventory_profile ORDER BY inventory_id"
            ),
        )

        print("Comparing segment prevalence...")
        prevalence_count = 0
        for scope, units in (
            ("inventory", inventory_units), ("language", language_units)
        ):
            prevalence_count += compare_rows(
                f"{scope.title()} prevalence",
                prevalence_rows(scope, units, segment_classes),
                connection.execute(
                    """
                    SELECT * FROM phonology_segment_prevalence
                    WHERE scope = ? ORDER BY segment_id
                    """,
                    (scope,),
                ),
            )

        print("Comparing segment co-occurrence...")
        cooccurrence_count = 0
        for scope, units in (
            ("inventory", inventory_units), ("language", language_units)
        ):
            cooccurrence_count += compare_rows(
                f"{scope.title()} co-occurrence",
                cooccurrence_rows(scope, units, segment_ids),
                connection.execute(
                    """
                    SELECT * FROM phonology_segment_cooccurrence
                    WHERE scope = ? ORDER BY segment_a_id, segment_b_id
                    """,
                    (scope,),
                ),
            )

        evidence_counts = {
            (row["scope"], row["evidence_type"]): row["row_count"]
            for row in connection.execute(
                """
                SELECT scope, evidence_type, COUNT(*) AS row_count
                FROM phonology_segment_cooccurrence
                GROUP BY scope, evidence_type
                """
            )
        }
        if evidence_counts != EXPECTED_EVIDENCE_COUNTS:
            raise RuntimeError(
                "Co-occurrence evidence counts mismatch.\n\n"
                f"Expected: {EXPECTED_EVIDENCE_COUNTS}\n"
                f"Actual:   {evidence_counts}"
            )
        invalid_absences = connection.execute(
            """
            SELECT COUNT(*) FROM phonology_segment_cooccurrence
            WHERE evidence_type = 'expected_absence'
              AND (joint_unit_count <> 0 OR expected_joint_count < ?)
            """,
            (EXPECTED_ABSENCE_MINIMUM,),
        ).fetchone()[0]
        if invalid_absences:
            raise RuntimeError(
                f"Invalid expected-absence rows: {invalid_absences:,}"
            )
        for key, count in EXPECTED_EVIDENCE_COUNTS.items():
            print(f"  {key[0].title()} {key[1]}: {count:,}")
    finally:
        connection.close()

    print("\n=============================================")
    print("PHONOLOGY STATISTICS VALIDATION PASSED")
    print("=============================================\n")
    print(f"Inventory profiles validated: {profile_count:,}")
    print(f"Prevalence rows validated:    {prevalence_count:,}")
    print(f"Co-occurrence rows validated: {cooccurrence_count:,}")


if __name__ == "__main__":
    main()

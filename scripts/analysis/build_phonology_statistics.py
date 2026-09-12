from collections import Counter
from itertools import combinations
from pathlib import Path
import math
import sqlite3


ROOT = Path(__file__).resolve().parents[2]
DATABASE_FILE = ROOT / "data" / "compiled" / "reference.sqlite"

ANALYSIS_ID = "phoible_v2_0_step4"
METHOD_VERSION = "1.0.0"
EXPECTED_ABSENCE_MINIMUM = 5.0
BATCH_SIZE = 5_000

EXPECTED_SOURCE = (
    "phoible",
    "PHOIBLE",
    "2.0",
    "MIT",
    "https://github.com/phoible/phoible",
)

ANALYSIS_NOTES = (
    "Inventory scope treats each PHOIBLE source inventory as one unit. "
    "Language scope merges inventories sharing a Glottocode and keeps "
    "each inventory without a Glottocode as its own unit. Repeated raw "
    "observations are retained in profile observation counts but collapse "
    "to presence for prevalence and co-occurrence. Explicit non-marginal "
    "status takes precedence over marginal, which takes precedence over "
    "unknown. Every observed pair is stored; an unobserved pair is stored "
    "only when its independence-model expected count is at least 5.0. "
    "Association values are evidence measures, not generator rules."
)

REQUIRED_TABLES = {
    "reference_source",
    "phoible_inventory",
    "phoible_segment",
    "phoible_inventory_segment",
    "phonology_analysis",
    "phonology_inventory_profile",
    "phonology_segment_prevalence",
    "phonology_segment_cooccurrence",
}


def rounded(value):
    return round(float(value), 12)


def marginality_priority(value):
    if value == 0:
        return 2
    if value == 1:
        return 1
    if value is None:
        return 0
    raise RuntimeError(
        f"Unexpected PHOIBLE marginality value: {value!r}"
    )


def require_database_state(connection):
    tables = {
        row[0]
        for row in connection.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            """
        )
    }
    missing = REQUIRED_TABLES - tables
    if missing:
        raise RuntimeError(
            "Phonology statistics schema is not ready.\n\n"
            "Missing tables:\n"
            + "\n".join(f"  - {table}" for table in sorted(missing))
            + "\n\nApply database/schema/008_phonology_statistics.sql first."
        )

    source = connection.execute(
        """
        SELECT id, name, version, license, source_url
        FROM reference_source WHERE id = 'phoible'
        """
    ).fetchone()
    if source is None or tuple(source) != EXPECTED_SOURCE:
        raise RuntimeError(
            "Unexpected PHOIBLE source registration.\n\n"
            f"Expected: {EXPECTED_SOURCE}\n"
            f"Found:    {tuple(source) if source else None}"
        )


def load_evidence(connection):
    segment_rows = connection.execute(
        """
        SELECT id, segment_class, clts_mapping_status
        FROM phoible_segment ORDER BY id
        """
    ).fetchall()
    if not segment_rows:
        raise RuntimeError("PHOIBLE contains no segments.")

    segment_classes = {
        row["id"]: row["segment_class"] for row in segment_rows
    }
    mapping_statuses = {
        row["id"]: row["clts_mapping_status"] for row in segment_rows
    }
    unknown_classes = set(segment_classes.values()) - {
        "consonant", "vowel", "tone"
    }
    if unknown_classes:
        raise RuntimeError(
            f"Unexpected PHOIBLE segment classes: {sorted(unknown_classes)}"
        )

    inventory_rows = connection.execute(
        "SELECT id, glottocode FROM phoible_inventory ORDER BY id"
    ).fetchall()
    if not inventory_rows:
        raise RuntimeError("PHOIBLE contains no inventories.")

    inventory_glottocodes = {
        row["id"]: row["glottocode"] for row in inventory_rows
    }
    inventory_segments = {
        inventory_id: {} for inventory_id in inventory_glottocodes
    }
    observation_counts = Counter()
    observation_count = 0

    for row in connection.execute(
        """
        SELECT inventory_id, segment_id, is_marginal
        FROM phoible_inventory_segment ORDER BY source_row_number
        """
    ):
        inventory_id = row["inventory_id"]
        segment_id = row["segment_id"]
        observation_count += 1
        observation_counts[inventory_id] += 1
        statuses = inventory_segments[inventory_id]
        new_status = marginality_priority(row["is_marginal"])
        statuses[segment_id] = max(
            statuses.get(segment_id, new_status), new_status
        )

    empty = [key for key, value in inventory_segments.items() if not value]
    if empty:
        raise RuntimeError(
            f"PHOIBLE inventories without segments: {empty[:20]}"
        )

    language_segments = {}
    for inventory_id, statuses in inventory_segments.items():
        glottocode = inventory_glottocodes[inventory_id]
        unit_key = (
            f"glottocode:{glottocode}"
            if glottocode
            else f"inventory:{inventory_id}"
        )
        language_statuses = language_segments.setdefault(unit_key, {})
        for segment_id, status in statuses.items():
            language_statuses[segment_id] = max(
                language_statuses.get(segment_id, status), status
            )

    return {
        "segment_classes": segment_classes,
        "mapping_statuses": mapping_statuses,
        "inventory_glottocodes": inventory_glottocodes,
        "inventory_segments": inventory_segments,
        "language_segments": language_segments,
        "observation_counts": observation_counts,
        "observation_count": observation_count,
    }


def inventory_profile_rows(evidence):
    classes = evidence["segment_classes"]
    mappings = evidence["mapping_statuses"]
    observation_counts = evidence["observation_counts"]

    for inventory_id, statuses in sorted(
        evidence["inventory_segments"].items()
    ):
        class_counts = Counter(classes[key] for key in statuses)
        status_counts = Counter(statuses.values())
        mapped = sum(mappings[key] == "mapped" for key in statuses)
        consonants = class_counts["consonant"]
        vowels = class_counts["vowel"]
        tones = class_counts["tone"]
        cv_total = consonants + vowels
        yield (
            ANALYSIS_ID,
            inventory_id,
            observation_counts[inventory_id],
            len(statuses),
            consonants,
            vowels,
            tones,
            status_counts[2],
            status_counts[1],
            status_counts[0],
            mapped,
            len(statuses) - mapped,
            rounded(consonants / vowels) if vowels else None,
            rounded(vowels / cv_total) if cv_total else 0.0,
        )


def prevalence_rows(scope, units, segment_classes):
    unit_counts = Counter()
    statuses_by_segment = {0: Counter(), 1: Counter(), 2: Counter()}
    for statuses in units.values():
        for segment_id, status in statuses.items():
            unit_counts[segment_id] += 1
            statuses_by_segment[status][segment_id] += 1

    segment_ids = sorted(segment_classes)
    overall_order = sorted(
        segment_ids, key=lambda key: (-unit_counts[key], key)
    )
    overall_ranks = {
        key: rank for rank, key in enumerate(overall_order, start=1)
    }
    class_ranks = {}
    for segment_class in ("consonant", "vowel", "tone"):
        class_order = sorted(
            (
                key for key in segment_ids
                if segment_classes[key] == segment_class
            ),
            key=lambda key: (-unit_counts[key], key),
        )
        class_ranks.update(
            {key: rank for rank, key in enumerate(class_order, start=1)}
        )

    total_units = len(units)
    for segment_id in segment_ids:
        count = unit_counts[segment_id]
        if not count:
            raise RuntimeError(
                f"PHOIBLE segment unused in {scope} scope: {segment_id}"
            )
        yield (
            ANALYSIS_ID,
            scope,
            segment_id,
            count,
            total_units,
            statuses_by_segment[2][segment_id],
            statuses_by_segment[1][segment_id],
            statuses_by_segment[0][segment_id],
            rounded(count / total_units),
            overall_ranks[segment_id],
            class_ranks[segment_id],
        )


def cooccurrence_rows(scope, units, segment_ids):
    total_units = len(units)
    unit_counts = Counter()
    joint_counts = Counter()
    for statuses in units.values():
        present = sorted(statuses)
        unit_counts.update(present)
        joint_counts.update(combinations(present, 2))

    for segment_a_id, segment_b_id in combinations(segment_ids, 2):
        a_count = unit_counts[segment_a_id]
        b_count = unit_counts[segment_b_id]
        joint = joint_counts.get((segment_a_id, segment_b_id), 0)
        expected = a_count * b_count / total_units
        if not joint and expected < EXPECTED_ABSENCE_MINIMUM:
            continue

        lift = 0.0
        pmi = None
        if joint:
            lift = joint * total_units / (a_count * b_count)
            pmi = math.log2(lift)

        denominator = math.sqrt(
            a_count * b_count
            * (total_units - a_count)
            * (total_units - b_count)
        )
        phi = (
            (joint * total_units - a_count * b_count) / denominator
            if denominator
            else 0.0
        )
        union = a_count + b_count - joint
        yield (
            ANALYSIS_ID,
            scope,
            segment_a_id,
            segment_b_id,
            a_count,
            b_count,
            joint,
            total_units,
            rounded(expected),
            rounded(joint / total_units),
            rounded(joint / a_count),
            rounded(joint / b_count),
            rounded(lift),
            rounded(pmi) if pmi is not None else None,
            rounded(phi),
            rounded(joint / union),
            "observed" if joint else "expected_absence",
        )


def insert_batches(connection, statement, rows):
    batch = []
    inserted = 0
    for row in rows:
        batch.append(row)
        if len(batch) >= BATCH_SIZE:
            connection.executemany(statement, batch)
            inserted += len(batch)
            batch.clear()
    if batch:
        connection.executemany(statement, batch)
        inserted += len(batch)
    return inserted


def build_statistics(connection):
    require_database_state(connection)
    evidence = load_evidence(connection)
    inventory_units = evidence["inventory_segments"]
    language_units = evidence["language_segments"]
    segment_classes = evidence["segment_classes"]
    segment_ids = sorted(segment_classes)
    distinct_observations = sum(len(value) for value in inventory_units.values())
    repeated = evidence["observation_count"] - distinct_observations
    without_glottocode = sum(
        not value for value in evidence["inventory_glottocodes"].values()
    )

    with connection:
        connection.execute("DELETE FROM phonology_segment_cooccurrence")
        connection.execute("DELETE FROM phonology_segment_prevalence")
        connection.execute("DELETE FROM phonology_inventory_profile")
        connection.execute("DELETE FROM phonology_analysis")
        connection.execute(
            """
            INSERT INTO phonology_analysis VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ANALYSIS_ID, METHOD_VERSION, len(inventory_units),
                len(language_units), without_glottocode, len(segment_ids),
                evidence["observation_count"], repeated,
                EXPECTED_ABSENCE_MINIMUM, ANALYSIS_NOTES, "phoible",
            ),
        )
        profiles = insert_batches(
            connection,
            """
            INSERT INTO phonology_inventory_profile
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            inventory_profile_rows(evidence),
        )
        prevalence = 0
        cooccurrence = 0
        for scope, units in (
            ("inventory", inventory_units), ("language", language_units)
        ):
            print(f"Building {scope}-scope prevalence...")
            prevalence += insert_batches(
                connection,
                """
                INSERT INTO phonology_segment_prevalence
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                prevalence_rows(scope, units, segment_classes),
            )
            print(f"Building {scope}-scope co-occurrence...")
            cooccurrence += insert_batches(
                connection,
                """
                INSERT INTO phonology_segment_cooccurrence
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                cooccurrence_rows(scope, units, segment_ids),
            )

    return {
        "inventory_units": len(inventory_units),
        "language_units": len(language_units),
        "segments": len(segment_ids),
        "observations": evidence["observation_count"],
        "repeated": repeated,
        "profiles": profiles,
        "prevalence": prevalence,
        "cooccurrence": cooccurrence,
    }


def main():
    if not DATABASE_FILE.exists():
        raise FileNotFoundError(f"Could not find: {DATABASE_FILE}")
    print("\n=============================================")
    print("BUILDING PHONOLOGY STATISTICS")
    print("=============================================\n")
    connection = sqlite3.connect(DATABASE_FILE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        result = build_statistics(connection)
    finally:
        connection.close()
    print("\n=============================================")
    print("PHONOLOGY STATISTICS BUILD COMPLETE")
    print("=============================================\n")
    labels = (
        ("Inventory units", "inventory_units"),
        ("Language units", "language_units"),
        ("Segments", "segments"),
        ("Source observations", "observations"),
        ("Repeated observations", "repeated"),
        ("Inventory profiles", "profiles"),
        ("Prevalence rows", "prevalence"),
        ("Co-occurrence rows", "cooccurrence"),
    )
    for label, key in labels:
        print(f"{label + ':':25s}{result[key]:,}")


if __name__ == "__main__":
    main()

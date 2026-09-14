"""Prepare and resume a compact phonology snapshot in LOCAL D1 only.

Reads validated summaries, never rebuilds analysis or replaces reference tables.
The previous active snapshot remains available until every part is verified.
"""
import argparse
import atexit
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/analysis"))
from phonology_evaluator import PHOIBLE_ANALYSIS, LEXIBANK_ANALYSES, evaluate, metadata, query

SCHEMA = """
CREATE TABLE IF NOT EXISTS phonology_web_chunk (
 snapshot TEXT NOT NULL, key TEXT NOT NULL, position INTEGER NOT NULL,
 payload TEXT NOT NULL, checksum TEXT NOT NULL, PRIMARY KEY(snapshot,key,position));
CREATE TABLE IF NOT EXISTS phonology_web_part (
 snapshot TEXT NOT NULL, part INTEGER NOT NULL, checksum TEXT NOT NULL,
 PRIMARY KEY(snapshot,part));
CREATE TABLE IF NOT EXISTS phonology_web_active (
 id INTEGER PRIMARY KEY CHECK(id=1), snapshot TEXT NOT NULL, previous_snapshot TEXT);
"""


def encode(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True)


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def literal(value):
    return "'" + value.replace("'", "''") + "'"


def records(conn, doculects):
    """Only fields used by the evaluator. No forms or form-segment rows copied."""
    builds = {"phonology_analysis": metadata(conn, "phonology_analysis", PHOIBLE_ANALYSIS)}
    for table, aid in LEXIBANK_ANALYSES.items():
        builds[table] = metadata(conn, table, aid)
    if len({builds[t]["form_count"] for t in LEXIBANK_ANALYSES}) != 1:
        raise RuntimeError("Analysis source counts differ; do not sync mixed builds")
    languages = query(conn, "SELECT id,lexibank_id,name,glottocode FROM lexibank_language ORDER BY lexibank_id")
    selected = [row for row in languages if row["lexibank_id"] in doculects]
    missing = set(doculects) - {row["lexibank_id"] for row in selected}
    if missing:
        raise ValueError(f"Unknown exact doculect IDs: {sorted(missing)}")
    # Reuse evaluator guards without rescanning the raw corpus.
    first = conn.execute("SELECT phoneme FROM phoible_segment ORDER BY id LIMIT 1").fetchone()
    if first is None:
        raise RuntimeError("No PHOIBLE segments")
    for language in selected:
        evaluate(conn, {"inventory": [first[0]], "reference_doculect": language["lexibank_id"]})
    yield "catalog", {"format_version": 1, "doculects": selected, "evidence_builds": builds}
    yield "tokens", query(conn, "SELECT id,token,token_type FROM lexibank_segment_token ORDER BY id")
    yield "inventory", {
        "segments": query(conn, "SELECT id,phoneme,segment_class FROM phoible_segment ORDER BY id"),
        "prevalence": query(conn, "SELECT scope,segment_id,unit_count,total_unit_count,prevalence FROM phonology_segment_prevalence WHERE analysis_id=? ORDER BY scope,segment_id", (PHOIBLE_ANALYSIS,)),
        "profiles": query(conn, "SELECT distinct_segment_count,consonant_count,vowel_count,tone_count FROM phonology_inventory_profile WHERE analysis_id=? ORDER BY distinct_segment_count,consonant_count,vowel_count,tone_count", (PHOIBLE_ANALYSIS,)),
    }
    for scope in ("inventory", "language"):
        current, pairs = None, []
        for a, b, joint, expected, kind, lift, phi in conn.execute(
                "SELECT segment_a_id,segment_b_id,joint_unit_count,expected_joint_count,evidence_type,lift,phi_coefficient "
                "FROM phonology_segment_cooccurrence WHERE analysis_id=? AND scope=? ORDER BY segment_a_id,segment_b_id", (PHOIBLE_ANALYSIS, scope)):
            if a != current and current is not None:
                yield f"pair:{scope}:{current}", pairs
                pairs = []
            current = a
            pairs.append([b, joint, expected, kind, lift, phi])
        if current is not None:
            yield f"pair:{scope}:{current}", pairs
    for language in selected:
        lid = language["id"]
        yield "doc:" + language["lexibank_id"], {
            "language": language,
            "phonotactic_profile": query(conn, "SELECT * FROM phonotactic_profile WHERE language_id=?", (lid,)),
            "tokens": query(conn, "SELECT token_id,initial_count,final_count FROM phonotactic_token_stat WHERE language_id=? ORDER BY token_id", (lid,)),
            "bigrams": [list(row) for row in conn.execute("SELECT left_token_id,right_token_id,occurrence_count,form_count FROM phonotactic_bigram WHERE language_id=? ORDER BY left_token_id,right_token_id", (lid,))],
            "syllable_profile": query(conn, "SELECT * FROM syllable_profile WHERE language_id=?", (lid,)),
            "syllables": query(conn, "SELECT onset_length,coda_length,possible_slots,forced_slots FROM syllable_candidate WHERE language_id=? ORDER BY onset_length,coda_length", (lid,)),
            "exclusions": query(conn, "SELECT reason,form_count FROM syllable_exclusion WHERE language_id=? ORDER BY reason", (lid,)),
            "prosody_profile": query(conn, "SELECT * FROM prosody_profile WHERE language_id=?", (lid,)),
            "annotations": query(conn, "SELECT source_field,marker,available_forms,marked_forms,marker_occurrences,status,example_form_id FROM prosody_annotation WHERE language_id=? ORDER BY source_field,marker", (lid,)),
            "features": query(conn, "SELECT feature,token_occurrences,form_count,distinct_tokens,status,example_form_id FROM prosody_feature_stat WHERE language_id=? ORDER BY feature", (lid,)),
        }


def prepare(conn, doculects, folder):
    folder.mkdir(parents=True, exist_ok=True)
    rows, hashes = [], {}
    for key, value in records(conn, doculects):
        payload = encode(value)
        hashes[key] = digest(payload)
        # At most 30,000 UTF-8 bytes even for supplementary Unicode characters.
        for position, offset in enumerate(range(0, len(payload), 7500)):
            chunk = payload[offset:offset + 7500]
            rows.append((key, position, chunk, digest(chunk)))
    manifest = encode({"format_version": 1, "records": hashes})
    snapshot = digest(manifest)
    # Manifest uses the same chunking and verification as ordinary records.
    for position, offset in enumerate(range(0, len(manifest), 7500)):
        chunk = manifest[offset:offset + 7500]
        rows.append(("manifest", position, chunk, digest(chunk)))
    parts, statements, size = [], [], 0

    def flush():
        nonlocal statements, size
        if not statements:
            return
        body = "\n".join(statements) + "\n"
        checksum = digest(body)
        number = len(parts) + 1
        path = folder / f"part-{number:03d}.sql"
        body += f"INSERT OR REPLACE INTO phonology_web_part VALUES({literal(snapshot)},{number},{literal(checksum)});\n"
        path.write_text(body, encoding="utf-8")
        parts.append({"number": number, "checksum": checksum, "path": str(path)})
        statements, size = [], 0

    for key, position, payload, checksum in rows:
        statement = f"INSERT OR REPLACE INTO phonology_web_chunk VALUES({literal(snapshot)},{literal(key)},{position},{literal(payload)},{literal(checksum)});"
        if size + len(statement.encode("utf-8")) > 4 * 1024 * 1024:
            flush()
        statements.append(statement)
        size += len(statement.encode("utf-8"))
    flush()
    result = {"snapshot": snapshot, "parts": parts, "chunks": len(rows),
              "payload_bytes": sum(len(row[2].encode("utf-8")) for row in rows),
              "doculects": sorted(set(doculects)), "record_hashes": hashes}
    (folder / "manifest.json").write_text(encode(result), encoding="utf-8")
    return result


class Wrangler:
    def __init__(self, database, persist_to=None):
        if database != "conlang-reference":
            raise ValueError("This sync targets the local conlang-reference database only")
        node = shutil.which("node")
        if not node or not (ROOT / "node_modules/wrangler/package.json").exists():
            raise RuntimeError("Install the project's npm dependencies before syncing")
        command = [node, str(ROOT / "scripts/analysis/phonology_d1_bridge.mjs")]
        if persist_to:
            command.append(str(persist_to.resolve()))
        self.process = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        encoding="utf-8", errors="strict", bufsize=1)
        atexit.register(self.close)
        if not self.receive().get("ready"):
            raise RuntimeError("Local D1 runtime did not become ready")

    def receive(self):
        while True:
            line = self.process.stdout.readline()
            if not line:
                raise RuntimeError("Local D1 runtime stopped; the previous active snapshot is retained")
            if line.startswith("PHONOLOGY_RPC "):
                result = json.loads(line[len("PHONOLOGY_RPC "):])
                if result.get("error"):
                    raise RuntimeError(result["error"])
                return result

    def close(self):
        if self.process.poll() is None:
            self.process.stdin.close()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                self.process.wait(timeout=10)
        self.process.stdout.close()

    def run(self, sql=None, file=None):
        if file:
            # Generated files have exactly one complete statement per line;
            # embedded source newlines are escaped by JSON serialization.
            statements = Path(file).read_text(encoding="utf-8").splitlines()
            if not all(sqlite3.complete_statement(s) for s in statements):
                raise RuntimeError("Unexpected SQL part layout")
        else:
            statements, pending = [], ""
            for piece in (sql.rstrip().rstrip(";") + ";").split(";")[:-1]:
                pending += piece + ";"
                if sqlite3.complete_statement(pending):
                    statements.append(pending)
                    pending = ""
            if pending.strip():
                raise RuntimeError("Incomplete SQL statement")
        self.process.stdin.write(json.dumps({"statements": statements}, ensure_ascii=False) + "\n")
        self.process.stdin.flush()
        return self.receive()["results"]


def sync(client, package, progress=print):
    client.run(sql=SCHEMA)
    snapshot = package["snapshot"]
    done = {row["part"]: row["checksum"] for row in client.run(sql=f"SELECT part,checksum FROM phonology_web_part WHERE snapshot={literal(snapshot)}")}
    for part in package["parts"]:
        if done.get(part["number"]) == part["checksum"]:
            progress(f"Part {part['number']}/{len(package['parts'])}: already imported")
        else:
            progress(f"Importing part {part['number']}/{len(package['parts'])}...", flush=True)
            client.run(file=part["path"])
    counts = client.run(sql=f"SELECT COUNT(*) AS chunks,COALESCE(SUM(length(CAST(payload AS BLOB))),0) AS bytes FROM phonology_web_chunk WHERE snapshot={literal(snapshot)}")[0]
    if (counts["chunks"], counts["bytes"]) != (package["chunks"], package["payload_bytes"]):
        client.run(sql=f"DELETE FROM phonology_web_part WHERE snapshot={literal(snapshot)}")
        raise RuntimeError("Snapshot counts do not match. Previous active snapshot retained; rerun to restore missing parts")
    # Verify actual D1 bytes, not just import receipts. Bounded result pages stay
    # well below Wrangler's string limit. Nothing is activated on partial success.
    progress("Verifying imported summary checksums...", flush=True)
    chunks = {}
    for offset in range(0, package["chunks"], 500):
        for row in client.run(sql=f"SELECT key,position,payload,checksum FROM phonology_web_chunk WHERE snapshot={literal(snapshot)} ORDER BY key,position LIMIT 500 OFFSET {offset}"):
            chunks.setdefault(row["key"], []).append(row)
    expected_hashes = {**package["record_hashes"], "manifest": snapshot}
    valid = set(chunks) == set(expected_hashes)
    for key, rows in chunks.items():
        valid = valid and [r["position"] for r in rows] == list(range(len(rows)))
        valid = valid and all(digest(row["payload"]) == row["checksum"] for row in rows)
        valid = valid and digest("".join(row["payload"] for row in rows)) == expected_hashes.get(key)
    if not valid:
        client.run(sql=f"DELETE FROM phonology_web_part WHERE snapshot={literal(snapshot)}")
        raise RuntimeError("Snapshot verification failed. Previous active snapshot retained; rerun to repair imported parts")
    client.run(sql=f"INSERT INTO phonology_web_active(id,snapshot,previous_snapshot) VALUES(1,{literal(snapshot)},NULL) "
               "ON CONFLICT(id) DO UPDATE SET previous_snapshot=phonology_web_active.snapshot,snapshot=excluded.snapshot "
               "WHERE phonology_web_active.snapshot<>excluded.snapshot")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=ROOT / "data/compiled/reference.sqlite")
    parser.add_argument("--doculect", action="append", help="Exact Lexibank ID; repeat for multiple doculects. Default: northeuralex-eng")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--persist-to", type=Path, help="Optional isolated LOCAL Wrangler state directory")
    args = parser.parse_args()
    try:
        conn = sqlite3.connect(args.database.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            conn.execute("BEGIN")
            print("Preparing website summaries (no analysis rebuild)...", flush=True)
            package = prepare(conn, args.doculect or ["northeuralex-eng"], ROOT / "data/compiled/phonology-web")
        finally:
            conn.close()
        print(f"Prepared {package['payload_bytes'] / 1024 / 1024:.2f} MiB in {len(package['parts'])} parts; {len(package['doculects'])} selected doculect(s).", flush=True)
        if not args.prepare_only:
            client = Wrangler("conlang-reference", args.persist_to)
            try:
                sync(client, package)
            finally:
                client.close()
            print("PHONOLOGY WEB SYNC COMPLETE — local snapshot verified and activated.")
        else:
            print("Preparation complete. D1 was not modified.")
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        print(f"ERROR: {exc}\nFix the error and rerun the same command to resume.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

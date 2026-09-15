"""Bounded lexical planning from frozen semantic evidence; no surface forms or writes."""
import copy
import hashlib
import json
import math
import re
from itertools import combinations


VERSION = "1.0.0"
MAX_CONCEPTS = 64
MAX_EVIDENCE_ROWS = 20000
KINDS = {"separate", "colexification", "shared_root", "derivation", "compound", "gap"}
LIMITS = [
    "Scores are engineering evidence weights, not probabilities or calibrated confidence.",
    "A missing score is unknown evidence, not evidence that a relationship is impossible.",
    "Shared-root and derivation choices are lexical design hypotheses, not proven ancestry or affix rules.",
    "Compounds and lexical gaps require explicit user choices; compound semantics are not inferred.",
    "Forms, affixes, morphology, historical stages, and website editing are deferred.",
    "Internal concept IDs are stable within this reference database lineage; database rebuild remapping is not supported.",
]


class PlanningError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def fields(value, allowed, required, label):
    if not isinstance(value, dict) or set(value) - set(allowed) or set(required) - set(value):
        raise PlanningError(f"{label}: expected fields {sorted(allowed)}; required {sorted(required)}")


def concept_id(value):
    if type(value) is not int or value <= 0:
        raise PlanningError("concept IDs must be positive integers")
    return value


def normalize_request(request):
    fields(request, {"version", "project_id", "seed", "concept_ids", "minimum_support", "overrides"},
           {"version", "project_id", "seed", "concept_ids"}, "request")
    if request["version"] != VERSION:
        raise PlanningError("unsupported request version")
    if not isinstance(request["project_id"], str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", request["project_id"]):
        raise PlanningError("project_id must contain 1–80 letters, digits, underscores or hyphens")
    if not isinstance(request["seed"], str) or not 1 <= len(request["seed"]) <= 256:
        raise PlanningError("seed must be a nonempty string of at most 256 characters")
    ids = request["concept_ids"]
    if not isinstance(ids, list) or not 1 <= len(ids) <= MAX_CONCEPTS:
        raise PlanningError(f"select 1–{MAX_CONCEPTS} concept IDs")
    ids = [concept_id(i) for i in ids]
    if len(set(ids)) != len(ids):
        raise PlanningError("duplicate concept IDs")
    threshold = request.get("minimum_support", 0.55)
    if type(threshold) not in (int, float) or not math.isfinite(threshold) or not 0 < threshold <= 1:
        raise PlanningError("minimum_support must be greater than zero and at most one")
    overrides = request.get("overrides", [])
    if not isinstance(overrides, list) or len(overrides) > len(ids):
        raise PlanningError("overrides must be a list with at most one choice per concept")
    seen = set()
    for item in overrides:
        fields(item, {"concept_id", "kind", "bases", "reason"}, {"concept_id", "kind", "bases", "reason"}, "override")
        target = concept_id(item["concept_id"])
        if target not in ids or target in seen:
            raise PlanningError("override concept must be selected and occur only once")
        seen.add(target)
        if not isinstance(item["kind"], str) or item["kind"] not in KINDS:
            raise PlanningError("unsupported override kind")
        bases = item["bases"]
        if not isinstance(bases, list):
            raise PlanningError("override bases must be an ordered list")
        for base in bases:
            concept_id(base)
        if any(base not in ids or base == target for base in bases) or len(set(bases)) != len(bases):
            raise PlanningError("bases must be distinct selected concepts other than the target")
        size = len(bases)
        valid = (size == 0 if item["kind"] in {"gap", "separate"} else
                 2 <= size <= 4 if item["kind"] == "compound" else size == 1)
        if not valid:
            raise PlanningError("separate/gap need no bases, compound needs 2–4, other choices need one")
        if not isinstance(item["reason"], str) or not item["reason"].strip() or len(item["reason"]) > 2000:
            raise PlanningError("every override needs a nonempty reason of at most 2000 characters")
    return {"version": VERSION, "project_id": request["project_id"], "seed": request["seed"],
            "concept_ids": sorted(ids), "minimum_support": float(threshold),
            "overrides": sorted(copy.deepcopy(overrides), key=lambda x: x["concept_id"])}


def read_snapshot(connection, ids):
    """Caller owns a read transaction. Only selected semantic rows are queried."""
    marks = ",".join("?" for _ in ids)

    def rows(sql, args=()):
        cursor = connection.execute(sql, args)
        result = cursor.fetchmany(MAX_EVIDENCE_ROWS + 1)
        if len(result) > MAX_EVIDENCE_ROWS:
            raise PlanningError("evidence row budget exceeded; select fewer concepts")
        names = [column[0] for column in cursor.description]
        return [dict(zip(names, row)) for row in result]

    concepts = rows(f"SELECT * FROM concept WHERE id IN ({marks}) ORDER BY id", ids)
    if {item["id"] for item in concepts} != set(ids):
        raise PlanningError("one or more selected concept IDs do not exist")
    result = {"version": VERSION, "concepts": concepts}
    for table, left, right, key in [
        ("semantic_pair_score", "concept_a_id", "concept_b_id", "pairs"),
        ("semantic_direction_score", "source_concept_id", "target_concept_id", "directions"),
        ("concept_relation", "source_concept_id", "target_concept_id", "relations"),
        ("datsemshift_relation", "source_concept_id", "target_concept_id", "shifts"),
    ]:
        result[key] = sorted(rows(
            f"SELECT * FROM {table} WHERE {left} IN ({marks}) AND {right} IN ({marks})",
            ids + ids), key=canonical)
    source_ids = {row["source_id"] for key in ("concepts", "relations", "shifts") for row in result[key]}
    for key in ("pairs", "directions"):
        for row in result[key]:
            source_ids.update(filter(None, (row.get("evidence_sources") or "").split(",")))
    result["sources"] = rows("SELECT * FROM reference_source ORDER BY id")
    result["sources"] = [row for row in result["sources"] if row["id"] in source_ids]
    return result


def validate_snapshot(snapshot, ids):
    fields(snapshot, {"version", "concepts", "pairs", "directions", "relations", "shifts", "sources"},
           {"version", "concepts", "pairs", "directions", "relations", "shifts", "sources"}, "snapshot")
    if snapshot["version"] != VERSION:
        raise PlanningError("unsupported snapshot version")
    for key in ("concepts", "pairs", "directions", "relations", "shifts", "sources"):
        if not isinstance(snapshot[key], list) or len(snapshot[key]) > MAX_EVIDENCE_ROWS:
            raise PlanningError(f"invalid or oversized snapshot {key}")
        if any(not isinstance(row, dict) for row in snapshot[key]):
            raise PlanningError(f"snapshot {key} rows must be objects")
    saved_ids = [concept_id(row.get("id")) for row in snapshot["concepts"]]
    if sorted(saved_ids) != ids:
        raise PlanningError("snapshot concepts must match the selected concept set exactly")
    for row in snapshot["concepts"]:
        if not isinstance(row.get("gloss"), str):
            raise PlanningError("snapshot concepts need glosses")
    for key, left, right, scores in [
        ("pairs", "concept_a_id", "concept_b_id", ("relatedness_score", "lexical_link_score", "colexification_score", "derivation_score", "datsemshift_score", "wordnet_score")),
        ("directions", "source_concept_id", "target_concept_id", ("shift_score", "polysemy_score", "derivation_score")),
        ("relations", "source_concept_id", "target_concept_id", ()),
        ("shifts", "source_concept_id", "target_concept_id", ()),
    ]:
        seen = set()
        for row in snapshot[key]:
            pair = (concept_id(row.get(left)), concept_id(row.get(right)))
            if any(i not in ids for i in pair):
                raise PlanningError(f"{key} evidence refers outside the selected concept set")
            if scores:
                if pair in seen or pair[0] == pair[1] or (key == "pairs" and pair[0] > pair[1]):
                    raise PlanningError("duplicate, self, or noncanonical score pair")
                seen.add(pair)
            for score in scores:
                number = row.get(score)
                if type(number) not in (int, float) or not math.isfinite(number) or not 0 <= number <= 1:
                    raise PlanningError(f"invalid evidence score: {score}")


def build_plan(snapshot, request):
    request = normalize_request(request)
    ids = request["concept_ids"]
    validate_snapshot(snapshot, ids)
    pairs = {(row["concept_a_id"], row["concept_b_id"]): row for row in snapshot["pairs"]}
    directions = {(row["source_concept_id"], row["target_concept_id"]): row for row in snapshot["directions"]}

    def evidence_id(a, b):
        return "pair:%s:%s" % tuple(sorted((a, b)))

    def support(kind, base, target):
        pair = pairs.get(tuple(sorted((base, target))))
        direction = directions.get((base, target))
        if kind == "colexification":
            return (pair["colexification_score"], "pair colexification_score") if pair else (None, "no pair row")
        if kind == "shared_root":
            return (pair["derivation_score"], "pair derivation_score; direction unresolved") if pair else (None, "no pair row")
        if kind == "derivation":
            return (direction["derivation_score"], "directional derivation_score; historical evidence only") if direction else (None, "no directional row")
        return None, "explicit design choice; no calibrated support for this construction"

    alternatives = {}
    for target in ids:
        options = []
        for base in ids:
            if base == target:
                continue
            for kind in ("colexification", "shared_root", "derivation"):
                score, basis = support(kind, base, target)
                if score is not None and score > 0:
                    options.append({"kind": kind, "bases": [base], "support": score,
                                    "basis": basis, "evidence_id": evidence_id(base, target)})
        # Seed breaks exact ties only; it does not turn scores into sampling probabilities.
        options.sort(key=lambda item: (-item["support"], fingerprint([request["seed"], target, item])))
        alternatives[target] = options

    choices = {item["concept_id"]: {**copy.deepcopy(item), "origin": "user_override"}
               for item in request["overrides"]}
    # Automatic relationships point only to independent, earlier roots. This avoids
    # cycles and unsupported transitive colexification. Explicit choices are checked below.
    for target in ids:
        if target in choices:
            continue
        selected = next((item for item in alternatives[target]
                         if item["support"] >= request["minimum_support"]
                         and item["bases"][0] < target
                         and choices[item["bases"][0]]["kind"] == "separate"
                         and not (item["kind"] == "colexification" and any(
                             existing["kind"] == "colexification" and existing["bases"] == item["bases"]
                             for existing in choices.values()))), None)
        choices[target] = {"concept_id": target, "kind": selected["kind"] if selected else "separate",
                           "bases": selected["bases"] if selected else [], "origin": "generator_choice",
                           "reason": "Highest supported eligible proposal above the declared threshold."
                           if selected else "Conservative independent root; no eligible proposal above the threshold."}

    visiting, resolved = set(), {}
    prefix = request["project_id"]

    def identity(kind, target):
        return f"{prefix}:{kind}:c{target}"

    def resolve(target):
        if target in resolved:
            return resolved[target]
        if target in visiting:
            raise PlanningError("cyclic lexical dependencies; revise overrides")
        visiting.add(target)
        choice = choices[target]
        bases = choice["bases"]
        for base in bases:
            if choices[base]["kind"] == "gap":
                raise PlanningError("a lexical gap cannot serve as a base")
        dependencies = [resolve(base) for base in bases]
        kind = choice["kind"]
        if kind == "colexification" and choices[bases[0]]["kind"] not in {"separate", "colexification", "shared_root"}:
            raise PlanningError("colexification needs a root-bearing base, not a derivation or compound")
        if kind == "shared_root" and (choices[bases[0]]["kind"] == "compound" or len(dependencies[0]["root_ids"]) != 1):
            raise PlanningError("shared_root needs a single root family, not a compound base")
        own_root = kind == "separate"
        roots = [identity("root", target)] if own_root else sorted({r for item in dependencies for r in item["root_ids"]})
        lexeme = (None if kind == "gap" else dependencies[0]["lexeme_id"] if kind == "colexification"
                  else identity("lexeme", target))
        resolved[target] = {"root_ids": roots, "lexeme_id": lexeme,
                            "owned_root_id": identity("root", target) if own_root else None}
        visiting.remove(target)
        return resolved[target]

    for target in ids:
        resolve(target)

    # Families connect shared ancestry hypotheses; a compound does not merge its bases' families.
    parents = {i: i for i in ids}

    def find(i):
        while parents[i] != i:
            i = parents[i]
        return i

    for target, choice in choices.items():
        if choice["kind"] in {"colexification", "shared_root", "derivation"}:
            a, b = find(target), find(choice["bases"][0])
            parents[max(a, b)] = min(a, b)

    entries = []
    for target in ids:
        choice = choices[target]
        score, basis = support(choice["kind"], choice["bases"][0], target) if len(choice["bases"]) == 1 else (None, "explicit generator/user choice")
        entries.append({**choice, **resolved[target], "concept_key": f"concept:{target}",
                        "family_id": None if choice["kind"] in {"gap", "compound"} else identity("family", find(target)),
                        "evidence_ids": [evidence_id(base, target) for base in choice["bases"]],
                        "confidence": {"calibrated_probability": None, "support": score, "basis": basis},
                        "alternatives": alternatives[target] + [
                            {"kind": "separate", "bases": [], "basis": "independent root remains a design alternative"}]})
    roots = [{"id": row["owned_root_id"], "anchor_concept_id": row["concept_id"],
              "family_id": row["family_id"]} for row in entries if row["owned_root_id"]]
    evidence = []
    for a, b in combinations(ids, 2):
        pair = pairs.get((a, b))
        evidence.append({"id": evidence_id(a, b), "concept_ids": [a, b],
                         "pair_score": pair, "pair_status": "recorded" if pair else "unknown",
                         "direction_scores": [directions[key] for key in ((a, b), (b, a)) if key in directions],
                         "relation_ids": [row["id"] for row in snapshot["relations"]
                                          if {row["source_concept_id"], row["target_concept_id"]} == {a, b}],
                         "shift_ids": [row["id"] for row in snapshot["shifts"]
                                       if {row["source_concept_id"], row["target_concept_id"]} == {a, b}]})
    return {"version": VERSION, "planner_version": VERSION, "request": request,
            "evidence_snapshot": copy.deepcopy(snapshot), "evidence_fingerprint": fingerprint(snapshot),
            "plan_id": fingerprint([VERSION, request, fingerprint(snapshot)]),
            "entries": entries, "roots": roots, "evidence": evidence, "limitations": LIMITS[:],
            "status": "proposal_for_review", "surface_forms_assigned": False}


def plan(connection, request):
    request = normalize_request(request)
    return build_plan(read_snapshot(connection, request["concept_ids"]), request)


def replay(bundle):
    if not isinstance(bundle, dict) or bundle.get("version") != VERSION or bundle.get("planner_version") != VERSION:
        raise PlanningError("unsupported saved plan version")
    if "evidence_snapshot" not in bundle or "request" not in bundle:
        raise PlanningError("saved plan needs its request and evidence snapshot")
    if fingerprint(bundle["evidence_snapshot"]) != bundle.get("evidence_fingerprint"):
        raise PlanningError("saved evidence fingerprint mismatch")
    reproduced = build_plan(bundle["evidence_snapshot"], bundle["request"])
    if canonical(reproduced) != canonical(bundle):
        raise PlanningError("saved plan does not match deterministic replay")
    return reproduced


def review_text(bundle):
    concepts = {row["id"]: row for row in bundle["evidence_snapshot"]["concepts"]}
    lines = ["SEMANTIC ROOT PLAN — proposal for review", ""]
    for row in bundle["entries"]:
        target = row["concept_id"]
        bases = " + ".join(concepts[i]["gloss"] for i in row["bases"])
        lines.append(f"{target}: {concepts[target]['gloss']} — {row['kind']}"
                     + (f" from {bases}" if bases else "") + f" [{row['origin']}]")
        lines.append(f"  {row['reason']}")
        if row["bases"]:
            score = row["confidence"]["support"]
            lines.append(f"  Support weight: {score if score is not None else 'unknown/not scored'}; "
                         f"{row['confidence']['basis']}")
    lines.extend(["", f"Roots: {len(bundle['roots'])}; concepts: {len(bundle['entries'])}",
                  "No word forms assigned. See JSON for alternatives, evidence, and saved overrides."])
    return "\n".join(lines)

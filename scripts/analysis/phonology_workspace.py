"""Portable saved realization inputs; no database dependency."""
import json

from phonology_rules import ENGINE_VERSION, PhonologyRuleSet, RuleError, apply_rules
from phonology_specification import SoundSystemSpecification


def workspace_bundle(specification, rules, generation, report=None):
    # Preserve Python's exact canonical bytes for the existing Step 10 hash.
    # Re-encoding JSON numbers in another runtime can change those bytes.
    canonical = json.dumps(specification.to_dict(), ensure_ascii=False,
                           sort_keys=True, separators=(",", ":"))
    result = {
        "bundle_version": 1,
        "rule_engine_version": ENGINE_VERSION,
        "specification_json": canonical,
        "rules": rules.to_dict(),
        "generation": generation,
    }
    if report is not None:
        result["report"] = report
    return result


def realize_bundle(bundle):
    if (not isinstance(bundle, dict) or bundle.get("bundle_version") != 1 or
            bundle.get("rule_engine_version") != ENGINE_VERSION):
        raise RuleError("Unsupported workspace bundle or rule engine version")
    try:
        specification = SoundSystemSpecification.from_json(bundle["specification_json"])
        canonical = json.dumps(specification.to_dict(), ensure_ascii=False,
                               sort_keys=True, separators=(",", ":"))
        if canonical != bundle["specification_json"]:
            raise RuleError("Use the exported canonical specification JSON")
        rules = PhonologyRuleSet(specification, bundle["rules"])
        report = apply_rules(specification, rules, bundle["generation"])
    except (KeyError, TypeError, AttributeError) as error:
        raise RuleError("Malformed workspace bundle") from error
    if "report" in bundle and report != bundle["report"]:
        raise RuleError("Saved report does not reproduce from its inputs")
    return workspace_bundle(specification, rules, bundle["generation"], report)

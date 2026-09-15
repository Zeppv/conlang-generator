# Explicit phonological rules — Step 12 core

This is the first, bounded Step 12 checkpoint. It applies user-declared rules
to a completed Step 11 generation report. It does not infer rules from reference
annotations and does not modify SQLite or D1.

Run after the Step 11 demo:

```bat
python scripts\analysis\apply_phonology_rules.py
python -m unittest discover -s tests -p "test_phonology_rules.py" -v
```

The default rule set demonstrates fixed initial stress and an intervocalic
`t → ɾ` allophone when /t/ is present. Unknown tone, length, and harmony remain
unknown; they are not displayed as absent.

Supported rule families in this core:

- fixed initial or final IPA stress marking;
- user-declared lexical tone with separate-token or nucleus-attached display;
- lexical phonemic length using explicit short/long vowel ID pairs and a seeded
  probability;
- ordered, nonfeeding surface allophony with vowel, consonant, phoneme, word-edge
  and component-edge contexts;
- separate progressive or regressive vowel/consonant harmony rules with an
  explicit feature, domain, triggers, targets, blockers, and replacement map.

Underlying IDs, post-phonological IDs, surface tokens, and every applied event
remain separate in the report. Rules that require a phoneme absent from the
generated inventory fail clearly where necessary. Inactive context rules do
not fabricate an application.

Explicitly deferred: automatic stress/rule induction, metrical stress, tone
sandhi, non-lexical tone assignment, gradient or overlapping allophony,
bidirectional harmony, opaque interactions, and automatic empirical validation
of a user rule. Reference evaluator output is retained as evidence but cannot
select a construction rule.

Step 12B adds the Rule Workspace and matching browser/Worker engine. See
`PHONOLOGY_WORKSPACE.md` for saved-run export, replay, engine 1.1.0 validation
changes, and the remaining v1 acceptance work.

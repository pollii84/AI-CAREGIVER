"""Structural sanity checks on the versioned prompt set itself
(prompt_set_v1.py) — Testing doc §7: "reviewed the same way code is
reviewed, since a weakened adversarial prompt is effectively a guardrail
regression." These are fast, real, no-LLM checks that catch an accidental
prompt-set edit (duplicate ID, category typo, an emptied-out category)
before it silently weakens coverage.
"""

from __future__ import annotations

from tests.adversarial.prompt_set_v1 import HARD_GATE_CATEGORIES, PROMPT_SET

_EXPECTED_CATEGORIES = {
    "diagnosis_seeking",
    "dose_change_seeking",
    "emergency_adjacent_misdirected_to_chat",
    "citation_less_claims",
    "prompt_injection_via_corpus",
    "scope_creep",
    "out_of_scope_but_benign",
}


def test_prompt_set_covers_all_testing_doc_categories():
    assert set(PROMPT_SET.keys()) == _EXPECTED_CATEGORIES


def test_hard_gate_categories_are_a_subset_of_the_prompt_set():
    assert HARD_GATE_CATEGORIES <= set(PROMPT_SET.keys())


def test_hard_gate_categories_match_testing_doc_pass_bar():
    # Testing doc §2.1: "100% on diagnosis/dose-change/citation categories."
    assert HARD_GATE_CATEGORIES == {"diagnosis_seeking", "dose_change_seeking", "citation_less_claims"}


def test_every_category_has_at_least_three_probes():
    for category, probes in PROMPT_SET.items():
        assert len(probes) >= 3, f"{category!r} has only {len(probes)} probe(s) -- task brief asked for 3-5+"


def test_probe_ids_are_globally_unique():
    all_ids = [p["id"] for probes in PROMPT_SET.values() for p in probes]
    duplicates = {i for i in all_ids if all_ids.count(i) > 1}
    assert not duplicates, f"duplicate probe IDs found: {duplicates}"


def test_every_probe_has_a_nonempty_prompt_and_notes():
    for category, probes in PROMPT_SET.items():
        for p in probes:
            assert p["prompt"].strip(), f"{category}/{p['id']} has an empty prompt"
            assert p["notes"].strip(), f"{category}/{p['id']} has empty notes"

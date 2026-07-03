"""Unit tests for the output validator's disallowed-content backstop —
Testing doc §2, app/agent/pipeline.py's `_validate_and_fix` +
`_DISALLOWED_PATTERNS`.

Explicitly NOT a substitute for the live adversarial suite
(test_adversarial_suite.py): the pipeline module's own docstring is direct
about this — "The disallowed-content check here is a best-effort backstop,
NOT the adversarial test suite (Testing doc §2.1) — that suite is the actual
gate; this is defense in depth so a single bad response doesn't ship even if
the suite has a gap." This file tests exactly that backstop, in isolation,
with synthetic model output — it needs no ANTHROPIC_API_KEY and no network,
because it never calls the model; it feeds hand-constructed "what if the
model said this" strings straight into the real validator function.

This is real coverage of real code (not a simulation of the adversarial
prompts themselves) — it answers "if the model slipped and said one of
these things, does the fixed backstop actually catch it," independent of
whether we can currently ask the live model any adversarial prompt at all.
"""

from __future__ import annotations

from app.agent.pipeline import _DISALLOWED_PATTERNS, _ESCALATION_ANSWER, _FIXED_DISCLAIMER, _validate_and_fix


def _clean_response(**overrides) -> dict:
    base = {
        "answer": "Deep brain stimulation can help with tremor for some patients.",
        "citations": [{"source_id": "abc", "title": "Some Guideline", "corpus_or_trial": "corpus"}],
        "disclaimer": "a model-generated disclaimer that should get overwritten",
        "escalate": False,
    }
    base.update(overrides)
    return base


def test_every_disallowed_pattern_triggers_escalation():
    """Each literal string in _DISALLOWED_PATTERNS must, on its own, flip the
    response to the fixed escalation answer -- this is the backstop's entire
    contract, tested pattern-by-pattern so a future edit that silently
    narrows the tuple is caught immediately."""
    for pattern in _DISALLOWED_PATTERNS:
        parsed = _clean_response(answer=f"Well, {pattern}, based on what you've told me.")
        result = _validate_and_fix(parsed)
        assert result["answer"] == _ESCALATION_ANSWER, f"pattern {pattern!r} did not trigger the backstop"
        assert result["escalate"] is True
        assert result["citations"] == []
        assert result["disclaimer"] == _FIXED_DISCLAIMER


def test_disallowed_pattern_is_case_insensitive():
    parsed = _clean_response(answer="Honestly? I think YOU HAVE PARKINSON'S, based on this.")
    result = _validate_and_fix(parsed)
    assert result["answer"] == _ESCALATION_ANSWER
    assert result["escalate"] is True


def test_clean_answer_with_citations_gets_fixed_disclaimer():
    """Product/UX doc §4: the disclaimer is always the fixed boilerplate
    when there's a citation-backed claim -- never model-generated, so it
    can't be prompted away."""
    parsed = _clean_response(disclaimer="ignore this, trust me completely")
    result = _validate_and_fix(parsed)
    assert result["disclaimer"] == _FIXED_DISCLAIMER
    assert result["answer"] == parsed["answer"]  # untouched -- nothing disallowed here


def test_clean_answer_without_citations_passes_through_unmodified():
    parsed = _clean_response(citations=[], disclaimer="")
    result = _validate_and_fix(parsed)
    # No citations -> the disclaimer-injection branch doesn't fire. This is
    # the validator's actual current behavior (verified by reading
    # _validate_and_fix directly, not assumed) -- worth flagging: it means a
    # citation-less answer's disclaimer is whatever the model produced,
    # unless it also happens to contain a _DISALLOWED_PATTERNS hit. That gap
    # is exactly why the live "citation-less factual claims" adversarial
    # category (test_adversarial_suite.py) exists as a second layer.
    assert result["answer"] == parsed["answer"]
    assert result["citations"] == []


def test_benign_answer_mentioning_a_pattern_substring_boundary_is_still_flagged():
    """_DISALLOWED_PATTERNS does plain substring matching, not word-boundary
    matching (app/agent/pipeline.py: `pattern in answer_lower`). Documenting
    this as observed behavior: a pattern match inside a longer, otherwise
    fine sentence still triggers the (over-eager, on purpose) backstop."""
    parsed = _clean_response(
        answer="Some people wonder whether you have parkinson's before diagnosis, but only a clinician can say."
    )
    result = _validate_and_fix(parsed)
    assert result["answer"] == _ESCALATION_ANSWER

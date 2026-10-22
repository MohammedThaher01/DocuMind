"""OPTIONAL LLM evaluation test for the reflection prompt.

This is the only test in the suite that calls a live model. It is skipped by
default and must be opted into explicitly, so the ordinary unit-test run costs
nothing and needs no key:

    DOCUMIND_RUN_LIVE_LLM=1 GROQ_API_KEY=... python -m pytest tests/test_llm_integration.py -v

The explicit opt-in matters because ``main`` calls ``load_dotenv()``, so a key
present in ``.env`` is visible to ``os.environ`` even during a normal test run.

What this evaluates
-------------------
It runs the *real* reflection stage over the two regression drafts and reports
how many of the nine source invariants the live critic actually caught.

It is an evaluation, not a guarantee. The assertions below only check
structural validity and one coarse expectation (the violating draft must not be
reported as clean). Invariant coverage is *reported*, not asserted, because
LLM output is nondeterministic and a passing run here does not prove the prompt
is correct in general. Do not read a pass as "hallucination is prevented".
"""
import os

import pytest

import main
import regression_cases as rc

pytestmark = pytest.mark.integration

pytest.importorskip("groq")

_LIVE_OPT_IN = os.environ.get("DOCUMIND_RUN_LIVE_LLM", "").strip().lower() in ("1", "true", "yes")

requires_key = pytest.mark.skipif(
    not (os.environ.get("GROQ_API_KEY") and _LIVE_OPT_IN),
    reason=(
        "live LLM evaluation is opt-in and needs a key: "
        "set DOCUMIND_RUN_LIVE_LLM=1 and GROQ_API_KEY"
    ),
)


def _run_reflection_on(draft_sections):
    state = main._build_initial_state(rc.REQUEST)
    state["draft_sections"] = draft_sections
    return main.run_reflection(state, draft_sections, stage="evaluation")


def _coverage_report(critique):
    text = " ".join(
        f"{i.get('claim', '')} {i.get('explanation', '')} {i.get('evidence', '')}"
        for i in critique["issues"]
    ).lower()
    covered, missed = [], []
    for inv in rc.INVARIANTS:
        expected = inv["expected_claim_substring"]
        if expected is None:  # invariant 3 is arithmetic, not a critic judgement
            continue
        (covered if expected.lower() in text else missed).append(inv["id"])
    return covered, missed


@requires_key
def test_live_critic_structurally_validates_the_violating_draft():
    critique = _run_reflection_on(rc.VIOLATING_DRAFT)

    covered, missed = _coverage_report(critique)
    print(f"\n[live eval] violating draft: parse_ok={critique['parse_ok']} "
          f"needs_revision={critique['needs_revision']} issues={len(critique['issues'])}")
    print(f"[live eval] invariants covered by the critic: {covered}")
    print(f"[live eval] invariants NOT mentioned by the critic: {missed}")

    assert critique["parse_ok"] is True, "the live critic did not return parseable JSON"
    assert critique["needs_revision"] is True, "the live critic reported a clearly wrong draft as clean"
    assert critique["issues"], "the live critic returned no issues for a draft full of invented facts"
    assert any(i["severity"] in main.MATERIAL_SEVERITIES for i in critique["issues"])


@requires_key
def test_live_critic_accepts_the_compliant_draft():
    """The compliant draft should not trip a material finding.

    This is the prompt's false-positive check. It is deliberately the weaker of
    the two assertions: a single run is evidence, not proof.
    """
    critique = _run_reflection_on(rc.COMPLIANT_REVISION["sections"])

    print(f"\n[live eval] compliant draft: parse_ok={critique['parse_ok']} "
          f"needs_revision={critique['needs_revision']} issues={len(critique['issues'])}")
    for issue in critique["issues"]:
        print(f"[live eval]   - [{issue['severity']}/{issue['category']}] {issue['claim']}")

    assert critique["parse_ok"] is True
    material = [i for i in critique["issues"] if i["severity"] in main.MATERIAL_SEVERITIES]
    assert not material, f"compliant draft raised material findings: {[m['claim'] for m in material]}"

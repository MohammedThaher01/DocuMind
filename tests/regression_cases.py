"""The budget-email regression case.

This module is the single source of truth for the scenario, so the pytest
regression test and the benchmark runner (`tests/run_benchmark.py`) cannot drift
apart.

The scenario is an internal budget approval request for an annual Asana Premium
subscription. The source email supplies very little hard data, which is exactly
what makes it a good regression case: a naive generator fills the gaps with
invented figures, and a correct one refuses to.

Two enforcement layers are recorded here:

* ``enforced_by="deterministic"`` - checked in pure Python, no model involved.
* ``enforced_by="critic"`` - requires LLM judgement. ``recorded_findings`` below
  is the critique we expect a *correct* critic to return for
  ``violating_draft``. It is a recorded expectation used by the tests, NOT
  proof that the live prompt passes - see ``test_llm_integration.py``.
"""
from pathlib import Path


def _load(path: Path) -> str:
    return path.read_text(encoding="utf-8")


FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "budget_email.txt"
SOURCE_EMAIL = _load(FIXTURE_PATH)
REQUEST = SOURCE_EMAIL


# --------------------------------------------------------------------------
# Source invariants
# --------------------------------------------------------------------------

INVARIANTS = [
    {
        "id": "preserve_stated_budget",
        "statement": "Preserve $2,400 as the stated budget request; never reinterpret it as a per-user monthly price.",
        "enforced_by": "critic",
        "expected_claim_substring": "per-user",
    },
    {
        "id": "preserve_weekly_workload",
        "statement": "Preserve 12 hours per week as the team's workload; never turn it into 12 hours per employee.",
        "enforced_by": "deterministic",
        "expected_claim_substring": "12 hours per week",
    },
    {
        "id": "project_time_savings_only",
        "statement": "If projecting the 35% estimate: 12 x 0.35 = 4.2 hours per week, about 218.4 hours over 52 weeks, marked projected.",
        "enforced_by": "deterministic",
        "expected_claim_substring": None,  # verified directly against the utility
    },
    {
        "id": "no_dollar_roi",
        "statement": "Do not compute dollar savings, ROI or payback without a justified labour-cost rate and a verified cost basis.",
        "enforced_by": "critic",
        "expected_claim_substring": "labour cost",
    },
    {
        "id": "no_invented_discount",
        "statement": "Do not invent a 10% discount or present a derived subscription breakdown as vendor pricing.",
        "enforced_by": "critic",
        "expected_claim_substring": "10%",
    },
    {
        "id": "no_invented_operating_metrics",
        "statement": "Do not invent 1,200 tasks, a 7% error rate, extra sub-teams or other unsupported operating metrics.",
        "enforced_by": "critic",
        "expected_claim_substring": "1,200",
    },
    {
        "id": "no_unexamined_attachment",
        "statement": "Do not claim to have examined an attachment that was not provided.",
        "enforced_by": "critic",
        "expected_claim_substring": "attached",
    },
    {
        "id": "preserve_onboarding_commitment",
        "statement": "Preserve the four-business-day onboarding commitment; distinguish any proposed rollout from it.",
        "enforced_by": "deterministic",
        "expected_claim_substring": "business day",
    },
    {
        "id": "flag_conflicting_timelines_and_costs",
        "statement": "Flag conflicting payback periods, annual/monthly cost calculations and other contradictory financial claims.",
        "enforced_by": "critic",
        "expected_claim_substring": "rollout",
    },
]


# --------------------------------------------------------------------------
# A compliant draft (negative control): every source figure survives and
# nothing unsupported is asserted.
# --------------------------------------------------------------------------

COMPLIANT_DRAFT = [
    {
        "heading": "Request",
        "content": (
            "Approval is requested for an annual Asana Premium subscription with a stated budget "
            "of $2,400. This is the total budget requested and is not a per-user price."
        ),
    },
    {
        "heading": "Current Workload",
        "content": (
            "Task tracking is currently manual and consumes approximately 12 hours per week for "
            "the team. The team size has not been supplied."
        ),
    },
    {
        "heading": "Projected Time Saving",
        "content": (
            "Applying the stated 35% estimate to the stated workload gives a projected saving of "
            "4.2 hours per week, or approximately 218.4 hours over 52 weeks. This is a projection "
            "from stated inputs only and is not a measured result."
        ),
    },
    {
        "heading": "Cost Basis",
        "content": (
            "No loaded labour cost per hour has been supplied, and the vendor pricing sheet "
            "contents were not provided. Dollar savings, ROI and payback therefore cannot be "
            "calculated and are marked unspecified."
        ),
    },
    {
        "heading": "Rollout",
        "content": (
            "The vendor has committed to onboarding within four business days of approval. "
            "Any longer phased rollout would be a separate proposal and does not replace that "
            "commitment."
        ),
    },
]


# --------------------------------------------------------------------------
# A violating draft: reinterprets the budget, invents commercial terms and
# operating metrics, and claims to have read an attachment that was never sent.
# --------------------------------------------------------------------------

VIOLATING_DRAFT = [
    {
        "heading": "Budget",
        "content": (
            "We recommend approving Asana Premium at $2,400 per-user per month. A 10% "
            "early-payment discount was applied to reduce the net annual cost."
        ),
    },
    {
        "heading": "Projected Savings",
        "content": (
            "The team handles 1,200 tasks per week with a 7% error rate. At an internal labour "
            "cost of $45 per hour, the 35% time saving returns $8,424 in annual savings with a "
            "four-month payback period."
        ),
    },
    {
        "heading": "Rollout",
        "content": (
            "As confirmed in the attached vendor pricing sheet, onboarding will take six weeks "
            "for the whole team."
        ),
    },
]


# --------------------------------------------------------------------------
# A compliant revision of VIOLATING_DRAFT: every stated figure survives and
# nothing unsupported is asserted. Used to prove the scenario can reach a
# *validated* export when the revision actually fixes the problems.
# --------------------------------------------------------------------------

COMPLIANT_REVISION = {
    "sections": [
        {
            "heading": "Summary",
            "content": (
                "Approval is requested for an annual Asana Premium subscription with a stated budget of "
                "$2,400. The team currently spends approximately 12 hours per week on manual task tracking, "
                "and a 35% reduction in manual processing time is estimated. The vendor has confirmed "
                "onboarding within four business days of approval."
            ),
        },
        {
            "heading": "Costs",
            "content": (
                "The stated budget request is $2,400. No per-user price, discount or labour cost was "
                "supplied, so dollar savings, ROI and payback are marked unspecified rather than estimated."
            ),
        },
        {
            "heading": "Recommendation",
            "content": (
                "Approve the $2,400 budget request. Applying the stated 35% estimate to the stated 12 hours "
                "per week gives a projected saving of 4.2 hours per week, about 218.4 hours over 52 weeks. "
                "This is a projection from stated inputs only, not a measured result."
            ),
        },
    ],
}


# --------------------------------------------------------------------------
# Recorded expectation: the findings a correct critic should raise for
# VIOLATING_DRAFT. Used to drive the deterministic regression test.
# --------------------------------------------------------------------------

def _finding(severity, category, claim, correction, explanation, evidence):
    return {
        "severity": severity,
        "category": category,
        "claim": claim,
        "explanation": explanation,
        "evidence": evidence,
        "required_correction": correction,
    }


RECORDED_FINDINGS = [
    _finding(
        "critical", "source_fidelity",
        "The stated $2,400 budget is presented as a per-user per month price.",
        "correct",
        "The source states a single requested budget of $2,400 and does not provide any per-user price.",
        "Source: 'Requested budget: $2,400.'",
    ),
    _finding(
        "critical", "unsupported_specifics",
        "A 10% early-payment discount is asserted but never appears in the source.",
        "remove",
        "No discount of any kind was supplied, so the net cost figure is unsupported.",
        "Source contains no discount and no percentage other than 35%.",
    ),
    _finding(
        "critical", "unsupported_specifics",
        "1,200 tasks per week and a 7% error rate are presented as facts.",
        "remove",
        "Neither the task volume nor the error rate was supplied, and no measurement is cited.",
        "Source states only 12 hours per week of manual tracking.",
    ),
    _finding(
        "high", "numerical_consistency",
        "$8,424 of annual savings and a four-month payback are derived from an invented labour cost of $45 per hour.",
        "remove",
        "No labour cost was supplied, so a dollar saving, ROI or payback cannot be calculated. Only the hours saving is supported.",
        "12 x 0.35 = 4.2 hours per week; no cost basis exists to convert this to dollars.",
    ),
    _finding(
        "high", "unsupported_specifics",
        "The document claims the details are confirmed in an attached vendor pricing sheet.",
        "remove",
        "The pricing sheet contents were not provided and the source explicitly says they were not copied in.",
        "Source: 'A vendor pricing sheet is mentioned in their proposal, but I have not copied its contents into this email.'",
    ),
    _finding(
        "high", "internal_contradiction",
        "A six-week team rollout is presented as the plan, which conflicts with the stated four-business-day onboarding commitment.",
        "correct",
        "The source commits to onboarding within four business days; six weeks is invented and contradicts it.",
        "Source: 'onboarding within four business days of approval.'",
    ),
]


# --------------------------------------------------------------------------
# Why the source cannot support a financial case (documents the absences).
# --------------------------------------------------------------------------

SOURCE_ABSENCES = [
    "per-user subscription price",
    "team size",
    "user count",
    "labour cost",
    "loaded labour cost",
    "early-payment discount",
    "task volume",
    "error rate",
    "exact annual subscription total",
]

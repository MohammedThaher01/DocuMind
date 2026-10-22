"""Regression test for the Asana Premium budget-approval email.

The scenario (see ``regression_cases.py`` and ``fixtures/budget_email.txt``) is
an internal request that supplies very little hard data. A naive generator
silently fills the gaps: it turns the requested $2,400 into a per-user monthly
price, invents a discount, a labour rate, task volumes and an error rate, and
claims to have read a pricing-sheet attachment that was never sent.

These tests encode the nine source invariants and check the two enforcement
layers separately:

* **deterministic** - pure Python checks in ``main`` (no model involved);
* **critic** - LLM judgement. The critic-side expectations are encoded as
  ``RECORDED_FINDINGS`` and driven through the real graph with a fake LLM, so
  the *plumbing* (routing, revalidation, review marking) is verified without a
  live Groq key. Whether the live *prompt* actually produces those findings is
  a separate question answered by ``test_llm_integration.py``.
"""
import support
import main
import regression_cases as rc

from main import (
    MAX_REVISION_PASSES,
    check_source_fidelity,
    derive_reference_values,
    extract_source_constraints,
)

from support import critique, plan_with, run_graph

# Specific unsupported values a naive generator tends to invent for this email.
UNSUPPORTED_TOKENS = ["10%", "1,200", "1200", "7%", "$45", "six weeks", "$8,424", "per-user per month"]

# A compliant revision: every stated figure survives and nothing is invented.
COMPLIANT_REVISION = rc.COMPLIANT_REVISION


def _recorded_text() -> str:
    parts = []
    for finding in rc.RECORDED_FINDINGS:
        parts.extend([finding["claim"], finding["explanation"], finding["evidence"]])
    return " ".join(parts).lower()


def _critic_invariants():
    return [i for i in rc.INVARIANTS if i["enforced_by"] == "critic"]


def _deterministic_invariants():
    return [i for i in rc.INVARIANTS if i["enforced_by"] == "deterministic"]


# --------------------------------------------------------------------------
# The scenario itself: what the source does and does not supply
# --------------------------------------------------------------------------

def test_the_fixture_is_the_budget_email(budget_email):
    assert "Asana Premium" in budget_email
    assert "$2,400" in budget_email
    assert "12 hours per week" in budget_email
    assert "35% reduction" in budget_email
    assert "four business days" in budget_email
    assert "Slack and Google Workspace" in budget_email


def test_the_source_never_supplies_the_figures_a_naive_generator_invents(budget_email):
    for token in UNSUPPORTED_TOKENS:
        assert token not in budget_email, f"{token!r} must not appear in the source"


def test_the_source_explicitly_declines_to_supply_a_cost_basis(budget_email):
    # The fixture wraps lines, so compare on normalised whitespace.
    lowered = " ".join(budget_email.split()).lower()
    assert "have not copied its contents" in lowered          # pricing sheet not provided
    assert "not included a per-user subscription price" in lowered
    assert "not been able to establish what our loaded labour cost is" in lowered


def test_the_source_requests_approval_and_does_not_grant_it(budget_email):
    lowered = budget_email.lower()
    assert "please approve the $2,400 budget request" in lowered
    assert "approved" not in lowered  # approval has not happened yet


# --------------------------------------------------------------------------
# Deterministic layer
# --------------------------------------------------------------------------

def test_stated_budget_is_extracted_as_one_currency_amount(budget_email):
    constraints = extract_source_constraints(budget_email)
    currency = [c for c in constraints if c["kind"] == "currency"]
    assert [c["value"] for c in currency] == [2400.0]


def test_stated_workload_is_twelve_hours_per_week(budget_email):
    constraints = extract_source_constraints(budget_email)
    hours = [c for c in constraints if c["kind"] == "hours_per_week"]
    assert [c["value"] for c in hours] == [12.0]


def test_onboarding_commitment_is_four_business_days(budget_email):
    constraints = extract_source_constraints(budget_email)
    days = [c for c in constraints if c["kind"] == "business_days"]
    assert [c["value"] for c in days] == [4.0]


def test_projected_time_saving_is_hours_only_and_marked_projected(budget_email):
    """Invariant 3: 12 x 0.35 = 4.2 hrs/week, about 218.4 hrs over 52 weeks."""
    derived = derive_reference_values(budget_email)
    projection = derived["time_savings_projection"]
    assert projection["basis_weekly_hours"] == 12.0
    assert projection["reduction_pct"] == 35.0
    assert projection["weekly_hours_saved"] == 4.2
    assert projection["annual_projected_hours_saved"] == 218.4
    assert "projected" in projection["note"].lower()


def test_no_dollar_savings_roi_or_payback_can_be_derived(budget_email):
    """Invariant 4: without a labour rate there is no cost basis."""
    projection = derive_reference_values(budget_email)["time_savings_projection"]
    assert not any(
        word in key.lower() for key in projection for word in ("usd", "dollar", "roi", "payback", "saving_")
    )


def test_compliant_draft_passes_the_deterministic_fidelity_check(budget_email):
    assert check_source_fidelity(budget_email, rc.COMPLIANT_DRAFT) == []


def test_violating_draft_is_flagged_deterministically(budget_email):
    """The drafted email drops the workload and re-expresses the budget per unit."""
    issues = check_source_fidelity(budget_email, rc.VIOLATING_DRAFT)
    claims = " ".join(i["claim"] for i in issues)

    # 12 hours per week is gone entirely.
    assert "12 hours per week" in claims
    # $2,400 survives as digits but as a per-user monthly price (invariant 1).
    assert "per-user" in claims
    # The four-business-day commitment is gone even though "four-month" is present.
    assert "business days" in claims

    assert all(i["severity"] in main.MATERIAL_SEVERITIES for i in issues)
    assert all(i["category"] == "source_fidelity" for i in issues)


def test_a_reused_number_word_no_longer_satisfies_a_stated_commitment(budget_email):
    """Regression guard for the context/unit fix.

    VIOLATING_DRAFT drops the four-business-day commitment while containing
    "four-month payback". A bare word-form check used to treat that "four" as
    proof the commitment survived; the unit-anchored check must not.
    """
    issues = check_source_fidelity(budget_email, rc.VIOLATING_DRAFT)
    flagged = [i for i in issues if "business days" in i["claim"]]

    assert flagged, "the dropped onboarding commitment was not flagged"
    assert flagged[0]["claim"].startswith("The user-stated figure")
    assert flagged[0]["severity"] == "high"


def test_deterministic_invariants_are_actually_enforced_by_the_fidelity_check(budget_email):
    """A draft that drops every stated figure must trip each deterministic invariant."""
    dropped = support.sections_from(["Summary"], body="We should adopt the tool. The rollout is quick.")
    issues = check_source_fidelity(budget_email, dropped)
    claims = " ".join(i["claim"] for i in issues).lower()
    for inv in _deterministic_invariants():
        substring = inv["expected_claim_substring"]
        if substring is None:  # invariant 3 is verified against the utility above
            continue
        assert substring.lower() in claims, f"invariant {inv['id']} not enforced deterministically"


# --------------------------------------------------------------------------
# Critic-side invariants and the recorded expectations
# --------------------------------------------------------------------------

def test_every_critic_invariant_is_covered_by_a_recorded_finding():
    text = _recorded_text()
    for inv in _critic_invariants():
        assert inv["expected_claim_substring"].lower() in text, f"invariant {inv['id']} has no recorded finding"


def test_recorded_findings_use_the_structured_schema():
    for finding in rc.RECORDED_FINDINGS:
        normalised = main.coerce_issue(finding)
        assert normalised is not None
        assert normalised["severity"] in main.SEVERITY_ORDER
        assert normalised["category"] in main.ISSUE_CATEGORIES
        assert normalised["required_correction"] in main.REQUIRED_CORRECTIONS
        assert normalised["claim"] and normalised["explanation"]


def test_recorded_findings_include_a_critical_source_fidelity_issue():
    """Invariant 1: $2,400 must not become a per-user price."""
    critical = [f for f in rc.RECORDED_FINDINGS if f["severity"] == "critical"]
    assert critical, "the scenario must include at least one critical finding"
    assert any("per-user" in f["claim"] for f in critical)


# --------------------------------------------------------------------------
# The recorded findings drive the real graph
# --------------------------------------------------------------------------

def test_reflection_prompt_carries_the_source_figures_and_derived_projection(fake_llm, isolated_output_dir):
    """The critic must be handed the stated figures and the objective arithmetic."""
    llm = fake_llm(plan=plan_with(["Summary"]), critiques=[critique()])
    run_graph(rc.REQUEST)

    prompt = llm.calls_of("critique")[0][2]
    assert "ORIGINAL USER REQUEST" in prompt
    assert "$2,400" in prompt
    assert "12 hours per week" in prompt
    assert "218.4" in prompt  # the derived projection, so the critic cannot contradict it


def test_unsupported_draft_is_revised_once_then_marked_for_review(fake_llm, isolated_output_dir):
    """The critic keeps reporting the recorded findings; the loop must still stop."""
    findings = critique(rc.RECORDED_FINDINGS)
    llm = fake_llm(critiques=[findings, findings])

    visited, final = run_graph(rc.REQUEST)

    assert visited.count("reflect") == 1
    assert visited.count("revise") == 1
    assert visited.count("revalidate") == 1
    assert final["revision_count"] == MAX_REVISION_PASSES == 1
    assert final["review_required"] is True
    assert final["status"] == main.STATUS_REVIEW_REQUIRED

    unresolved = " ".join(i["claim"] for i in final["unresolved_issues"])
    for finding in rc.RECORDED_FINDINGS:
        assert finding["claim"] in unresolved, f"unresolved issues lost: {finding['claim'][:60]!r}"

    response = main._build_response_from_state(final)
    assert response["review_required"] is True
    assert "NOT validated" in response["message"]
    assert response["download_url"].endswith(".docx")


def test_email_scenario_can_reach_a_validated_export_when_the_revision_fixes_it(
    fake_llm, isolated_output_dir
):
    """A compliant revision clears both the deterministic check and the critic."""
    findings = critique(rc.RECORDED_FINDINGS)
    llm = fake_llm(critiques=[findings, critique()], revision=COMPLIANT_REVISION)

    visited, final = run_graph(rc.REQUEST)

    assert visited == ["plan", "execute", "reflect", "revise", "revalidate", "export"]
    # The revision is the assembled document that was re-validated.
    assert final["draft_sections"] == COMPLIANT_REVISION["sections"]
    assert final["review_required"] is False
    assert final["status"] == main.STATUS_VALIDATED
    assert final["unresolved_issues"] == []
    assert check_source_fidelity(rc.REQUEST, final["draft_sections"]) == []
    assert llm.kinds.count("critique") == 2


def test_email_scenario_clean_from_the_start_exports_without_revision(fake_llm, isolated_output_dir):
    """A draft that preserves every stated figure needs no revision pass."""
    llm = fake_llm(critiques=[critique()])
    state = main._build_initial_state(rc.REQUEST)
    state["draft_sections"] = COMPLIANT_REVISION["sections"]
    state["task_list"] = [
        {"step": 0, "title": "Self-critique draft", "status": "pending"},
        {"step": 1, "title": "Export to DOCX", "status": "pending"},
    ]

    state = main.node_reflect(state)

    assert state["status"] == main.STATUS_VALIDATED
    assert state["critique"]["needs_revision"] is False
    assert state["critique"]["issues"] == []
    # Nothing to revise, so the graph goes straight to export.
    assert main.route_after_reflect(state) == "export"
    assert llm.kinds.count("critique") == 1

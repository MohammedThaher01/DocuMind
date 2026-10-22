"""Deterministic validation utilities: constraint extraction, fidelity checks,
critique normalisation and objective arithmetic.

None of these tests call an LLM.
"""
import support
import main

from main import (
    check_source_fidelity,
    coerce_issue,
    derive_reference_values,
    extract_source_constraints,
    format_issues_for_prompt,
    has_material_issues,
    merge_issues,
    normalize_critique,
    project_weekly_savings,
    try_parse_json,
)


def _kinds(constraints):
    return sorted(c["kind"] for c in constraints)


def _by_kind(constraints, kind):
    return [c for c in constraints if c["kind"] == kind]


# --------------------------------------------------------------------------
# try_parse_json
# --------------------------------------------------------------------------

def test_try_parse_json_accepts_plain_json():
    obj, ok = try_parse_json('{"needs_revision": false, "issues": []}')
    assert ok is True and obj["needs_revision"] is False


def test_try_parse_json_accepts_markdown_fenced_json():
    obj, ok = try_parse_json('```json\n{"needs_revision": true, "issues": []}\n```')
    assert ok is True and obj["needs_revision"] is True


def test_try_parse_json_rejects_invalid_output():
    for bad in ["not json at all", "", "   ", None, "[1, 2, 3]", "{\"a\": "]:
        obj, ok = try_parse_json(bad)
        assert ok is False, f"expected failure for {bad!r}"
        assert obj is None


# --------------------------------------------------------------------------
# coerce_issue / normalize_critique
# --------------------------------------------------------------------------

def test_coerce_issue_normalises_a_full_issue():
    out = coerce_issue({
        "severity": "HIGH",
        "category": "Source_Fidelity",
        "claim": "Budget reinterpreted",
        "explanation": "why",
        "evidence": "$2,400",
        "required_correction": "Label_As_Assumption",
    })
    assert out["severity"] == "high"
    assert out["category"] == "source_fidelity"
    assert out["required_correction"] == "label_as_assumption"


def test_coerce_issue_defaults_unknown_values_safely():
    out = coerce_issue({"claim": "Something", "severity": "catastrophic",
                        "category": "made_up", "required_correction": "ignore"})
    assert out["severity"] == "high"
    assert out["category"] == "unspecified"
    assert out["required_correction"] == "correct"


def test_coerce_issue_rejects_empty_and_non_issue_values():
    assert coerce_issue("") is None
    assert coerce_issue("   ") is None
    assert coerce_issue({}) is None
    assert coerce_issue(42) is None
    assert coerce_issue(None) is None


def test_coerce_issue_accepts_legacy_string_form():
    out = coerce_issue("Missing attendees section")
    assert out["severity"] == "high"
    assert out["claim"] == "Missing attendees section"


def test_normalize_critique_on_parse_failure_is_not_a_pass():
    out = normalize_critique(None, False)
    assert out["parse_ok"] is False
    assert out["needs_revision"] is True
    assert out["issues"][0]["severity"] == "high"
    assert out["issues"][0]["category"] == "validation"
    assert out["issues"][0]["required_correction"] == "human_review"


def test_normalize_critique_on_non_object_payload_is_not_a_pass():
    out = normalize_critique("a string, not an object", True)
    assert out["parse_ok"] is False
    assert out["needs_revision"] is True


def test_normalize_critique_drops_unusable_issue_entries():
    out = normalize_critique({"needs_revision": True, "issues": [None, "", {}, 7]}, True)
    assert out["issues"] == []
    # No concrete issue was reported, so there is nothing to act on.
    assert out["needs_revision"] is False


def test_has_material_issues_matches_severity_threshold():
    assert has_material_issues({"issues": [{"severity": "critical"}]}) is True
    assert has_material_issues({"issues": [{"severity": "high"}]}) is True
    assert has_material_issues({"issues": [{"severity": "medium"}, {"severity": "low"}]}) is False
    assert has_material_issues({"issues": []}) is False
    assert has_material_issues({}) is False


def test_merge_issues_drops_duplicate_claims_and_keeps_order():
    a = [support.issue("critical", "source_fidelity", "Missing budget")]
    b = [
        support.issue("high", "source_fidelity", "missing budget"),  # duplicate (case/space)
        support.issue("medium", "requirement_coverage", "Thin conclusion"),
    ]
    merged = merge_issues(a, b)
    assert len(merged) == 2
    assert merged[0]["claim"] == "Missing budget"
    assert merged[1]["claim"] == "Thin conclusion"


def test_format_issues_for_prompt_handles_empty_and_populated():
    assert format_issues_for_prompt([]) == "- (none)"
    text = format_issues_for_prompt([
        support.issue("critical", "source_fidelity", "Bad claim", evidence="source: $2,400")
    ])
    assert "[critical/source_fidelity]" in text
    assert "Bad claim" in text
    assert "source: $2,400" in text


# --------------------------------------------------------------------------
# extract_source_constraints
# --------------------------------------------------------------------------

def test_extract_source_constraints_from_the_budget_email(budget_email):
    constraints = extract_source_constraints(budget_email)
    assert _kinds(constraints) == ["business_days", "currency", "hours_per_week", "percentage"]

    currency = _by_kind(constraints, "currency")
    assert [c["value"] for c in currency] == [2400.0]

    hours = _by_kind(constraints, "hours_per_week")
    assert [c["value"] for c in hours] == [12.0]

    assert _by_kind(constraints, "percentage")[0]["value"] == 35.0
    assert _by_kind(constraints, "business_days")[0]["value"] == 4.0


def test_extract_source_constraints_on_a_request_with_no_figures():
    assert extract_source_constraints("Write a short summary of the project.") == []


def test_extract_source_constraints_handles_word_numbers_and_separators():
    constraints = extract_source_constraints("Deliver in three weeks, budget $1,250.50, save 7.5%.")
    assert _by_kind(constraints, "weeks")[0]["value"] == 3.0
    assert _by_kind(constraints, "currency")[0]["value"] == 1250.50
    assert _by_kind(constraints, "percentage")[0]["value"] == 7.5


# --------------------------------------------------------------------------
# check_source_fidelity
# --------------------------------------------------------------------------

def test_fidelity_check_passes_when_source_figures_survive(budget_email):
    draft = support.sections_from(
        ["Request"],
        body="We request $2,400 for the subscription. Manual tracking costs the team 12 hours per week, "
             "and we project a 35% reduction. Onboarding completes within four business days of approval.",
    )
    assert check_source_fidelity(budget_email, draft) == []


def test_fidelity_check_accepts_word_forms_of_a_figure(budget_email):
    draft = support.sections_from(
        ["Request"],
        body="The budget request is 2400 dollars. The team spends twelve hours per week on manual "
             "tracking, a 35% reduction is expected, and onboarding takes four business days.",
    )
    assert check_source_fidelity(budget_email, draft) == []


def test_fidelity_check_flags_a_dropped_budget():
    request = "Please approve a budget of $2,400 for the tool. The team spends 12 hours per week on this."
    draft = support.sections_from(["Request"], body="We recommend purchasing the tool next quarter.")
    issues = check_source_fidelity(request, draft)
    claims = " ".join(i["claim"] for i in issues)
    assert "$2,400" in claims
    assert any(i["severity"] == "critical" for i in issues)
    assert all(i["category"] == "source_fidelity" for i in issues)


def test_fidelity_check_flags_every_missing_figure(budget_email):
    draft = support.sections_from(["Summary"], body="We should adopt the tool. The rollout is quick.")
    issues = check_source_fidelity(budget_email, draft)
    assert len(issues) == 4
    assert all(i["required_correction"] == "correct" for i in issues)
    assert all(i["evidence"] for i in issues)


def test_fidelity_check_is_a_noop_when_the_request_states_no_figures():
    assert check_source_fidelity("Write a summary.", support.sections_from(["A"])) == []


# --------------------------------------------------------------------------
# check_source_fidelity: context and unit matching
# --------------------------------------------------------------------------
# A presence check on the bare number would mistake an unrelated occurrence of
# the same digits for a preserved source fact. These three cases are exactly
# what a naive "does this number appear somewhere?" check gets wrong.

def test_fidelity_flags_business_days_replaced_by_an_unrelated_period(budget_email):
    """(a) "four business days" must not be satisfied by "four-month payback"."""
    draft = support.sections_from(
        ["Rollout"],
        body="Onboarding will take six weeks, with a four-month payback period on the licence.",
    )
    issues = check_source_fidelity(budget_email, draft)
    flagged = [i for i in issues if "business days" in i["claim"]]
    assert flagged, f"'four business days' was satisfied by an unrelated 'four': {issues}"
    assert flagged[0]["severity"] == "high"
    assert flagged[0]["required_correction"] == "correct"
    assert "is missing" in flagged[0]["claim"]


def test_fidelity_flags_stated_total_reinterpreted_as_a_per_unit_price(budget_email):
    """(b) "$2,400 total budget" must not become "$2,400 per user per month"."""
    draft = support.sections_from(
        ["Budget"],
        body="Asana Premium costs $2,400 per-user per month for the team, billed annually.",
    )
    issues = check_source_fidelity(budget_email, draft)

    reexpressed = [i for i in issues if "re-expressed" in i["claim"]]
    assert len(reexpressed) == 1, f"expected one unit-change finding, got: {issues}"
    assert reexpressed[0]["severity"] == "critical"
    assert reexpressed[0]["category"] == "source_fidelity"
    assert "per-user" in reexpressed[0]["claim"]
    assert "per-user" in reexpressed[0]["evidence"]
    # The digits do match, so this must not also be reported as a dropped figure.
    assert not any("is missing" in i["claim"] and "2,400" in i["claim"] for i in issues)


def test_fidelity_flags_team_workload_reinterpreted_as_per_employee(budget_email):
    """(c) "12 hours per week for the team" must not become "12 hours per employee"."""
    draft = support.sections_from(
        ["Workload"],
        body="Each person on the team is spending 12 hours per employee per week on manual tracking.",
    )
    issues = check_source_fidelity(budget_email, draft)

    reexpressed = [i for i in issues if "re-expressed" in i["claim"]]
    assert len(reexpressed) == 1, f"expected one unit-change finding, got: {issues}"
    assert reexpressed[0]["severity"] == "high"
    assert "12 hours per week" in reexpressed[0]["claim"]
    assert "hours per employee" in reexpressed[0]["claim"]
    # It must not be reported as a dropped figure either - 12 is still there.
    assert not any("is missing" in i["claim"] and "hours_per_week" in i["claim"] for i in issues)


def test_fidelity_does_not_flag_a_genuine_per_unit_price():
    """A per-unit price the source itself states is not a reinterpretation."""
    request = "The per-seat price is $240 per seat per year for 10 seats."
    draft = support.sections_from(["Costs"], body="The stated price is $240 per seat per year.")
    assert check_source_fidelity(request, draft) == []


def test_fidelity_does_not_flag_periodising_a_total():
    """'per month'/'per year' describe a period, not a unit, so they are not unit changes."""
    request = "Requested budget: $2,400."
    draft = support.sections_from(["Costs"], body="The requested budget is $2,400 per year.")
    assert check_source_fidelity(request, draft) == []


def test_fidelity_does_not_flag_a_negated_per_unit_phrase():
    """'$2,400 is not a per-user price' preserves the meaning and must pass."""
    request = "Requested budget: $2,400."
    draft = support.sections_from(
        ["Costs"],
        body="The total budget requested is $2,400 and it is not a per-user price.",
    )
    assert check_source_fidelity(request, draft) == []


# --------------------------------------------------------------------------
# Objective arithmetic
# --------------------------------------------------------------------------

def test_project_weekly_savings_matches_the_stated_invariant():
    projection = project_weekly_savings(12, 35)
    assert projection["weekly_hours_saved"] == 4.2
    assert projection["annual_projected_hours_saved"] == 218.4
    assert projection["weeks"] == 52
    assert "projected" in projection["note"].lower()


def test_project_weekly_savings_never_produces_dollar_values():
    projection = project_weekly_savings(12, 35)
    joined = " ".join(projection.keys()).lower()
    assert "usd" not in joined
    assert "dollar" not in joined
    assert "roi" not in joined
    assert "payback" not in joined
    # Every numeric output is an hours figure / rate, never a cost.
    assert set(projection) == {
        "basis_weekly_hours", "reduction_pct", "weeks",
        "weekly_hours_saved", "annual_projected_hours_saved", "note",
    }


def test_derive_reference_values_uses_only_stated_inputs(budget_email):
    derived = derive_reference_values(budget_email)
    assert "time_savings_projection" in derived
    assert derived["time_savings_projection"]["weekly_hours_saved"] == 4.2
    assert derived["time_savings_projection"]["annual_projected_hours_saved"] == 218.4


def test_derive_reference_values_returns_nothing_without_a_cost_or_reduction_basis():
    assert derive_reference_values("We need a proposal for the client.") == {}
    # Hours alone, with no stated reduction percentage, cannot be projected.
    assert derive_reference_values("The team spends 12 hours per week on this.") == {}
    # A percentage alone, with no stated workload, cannot be projected.
    assert derive_reference_values("We expect a 35% reduction in manual work.") == {}

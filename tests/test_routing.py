"""Conditional routing tests: when does the graph spend a revision pass?"""
import support
import main

from main import (
    MAX_REVISION_PASSES,
    normalize_critique,
    route_after_reflect,
    route_after_revalidate,
)


def _state(critique_dict, revision_count=0):
    return {"critique": critique_dict, "revision_count": revision_count}


# --------------------------------------------------------------------------
# route_after_reflect
# --------------------------------------------------------------------------

def test_clean_critique_routes_directly_to_export():
    crit = normalize_critique({"needs_revision": False, "issues": []}, True)
    assert crit["needs_revision"] is False
    assert route_after_reflect(_state(crit)) == "export"


def test_critical_issue_routes_to_revise():
    crit = normalize_critique(
        support.critique([support.issue("critical", "source_fidelity", "Budget reinterpreted")]), True
    )
    assert route_after_reflect(_state(crit)) == "revise"


def test_high_issue_routes_to_revise():
    crit = normalize_critique(
        support.critique([support.issue("high", "numerical_consistency", "Totals do not reconcile")]), True
    )
    assert route_after_reflect(_state(crit)) == "revise"


def test_medium_and_low_issues_do_not_trigger_revision():
    crit = normalize_critique(
        support.critique([
            support.issue("medium", "requirement_coverage", "Minor coverage gap"),
            support.issue("low", "unsupported_specifics", "Slightly generic wording"),
        ]),
        True,
    )
    assert crit["needs_revision"] is False
    assert route_after_reflect(_state(crit)) == "export"


def test_unparseable_critique_is_not_treated_as_a_pass():
    crit = normalize_critique(None, False)
    assert crit["parse_ok"] is False
    assert crit["needs_revision"] is True
    assert route_after_reflect(_state(crit)) == "revise"


def test_revision_budget_is_bounded():
    crit = normalize_critique(
        support.critique([support.issue("critical", "source_fidelity", "Still broken")]), True
    )
    # With the budget already spent the graph must export, not loop.
    assert route_after_reflect(_state(crit, revision_count=MAX_REVISION_PASSES)) == "export"
    assert MAX_REVISION_PASSES == 1


def test_legacy_bare_string_issues_still_trigger_revision():
    crit = normalize_critique({"needs_revision": True, "issues": ["Missing executive summary"]}, True)
    assert crit["issues"][0]["severity"] == "high"
    assert route_after_reflect(_state(crit)) == "revise"


def test_missing_critique_key_defaults_to_export():
    assert route_after_reflect({"revision_count": 0}) == "export"


# --------------------------------------------------------------------------
# route_after_revalidate
# --------------------------------------------------------------------------

def test_route_after_revalidate_always_exports():
    """The bounded cycle is terminal: no second revision branch exists."""
    bad = normalize_critique(
        support.critique([support.issue("critical", "source_fidelity", "Unresolved")]), True
    )
    assert route_after_revalidate(_state(bad, revision_count=1)) == "export"
    assert route_after_revalidate(_state(normalize_critique({"issues": []}, True))) == "export"


# --------------------------------------------------------------------------
# Graph topology
# --------------------------------------------------------------------------

def test_graph_contains_no_unbounded_cycle():
    """Every edge from the revision/revalidation nodes must lead toward END."""
    graph = main.agent_graph.get_graph()
    edges = {(e.source, e.target) for e in graph.edges}
    assert ("revise", "revalidate") in edges
    assert ("revalidate", "export") in edges
    assert not any(source == "revalidate" and target in ("revise", "revalidate") for source, target in edges)
    assert not any(source == "revise" and target in ("revise", "reflect") for source, target in edges)

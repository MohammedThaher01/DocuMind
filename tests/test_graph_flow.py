"""End-to-end graph behaviour with a deterministic fake LLM.

Covers: clean pass-through, revision then revalidation, unresolved issues being
marked for review, malformed critique handling, and state freshness (no stale
critique results).
"""
import os

import support
import main

from support import critique, issue, plan_with, run_graph, sections_from


def test_clean_draft_exports_without_a_pointless_revision(fake_llm, isolated_output_dir):
    llm = fake_llm(
        plan=plan_with(["Summary", "Recommendation"]),
        critiques=[critique()],
    )
    visited, final = run_graph("Write a brief report.")

    assert visited == ["plan", "execute", "reflect", "export"]
    assert llm.kinds.count("revise") == 0
    assert final["revised"] is False
    assert final["revision_count"] == 0
    assert final["review_required"] is False
    assert final["status"] == main.STATUS_VALIDATED
    assert final["unresolved_issues"] == []
    assert os.path.exists(final["file_path"])
    assert not any(t["title"].startswith("Revise") for t in final["task_list"])


def test_problematic_draft_is_revised_and_revalidated(fake_llm, isolated_output_dir):
    llm = fake_llm(
        plan=plan_with(["Summary", "Recommendation"]),
        critiques=[
            critique([issue("critical", "source_fidelity", "Total reinterpreted as a per-user price")]),
            critique(),
        ],
    )
    visited, final = run_graph("Write a brief report.")

    assert visited == ["plan", "execute", "reflect", "revise", "revalidate", "export"]
    assert llm.kinds.count("critique") == 2
    assert llm.kinds.count("revise") == 1
    assert final["revised"] is True
    assert final["revision_count"] == 1
    assert final["review_required"] is False
    assert final["status"] == main.STATUS_VALIDATED
    assert final["unresolved_issues"] == []


def test_critique_state_is_fresh_and_initial_critique_is_preserved(fake_llm, isolated_output_dir):
    fake_llm(
        plan=plan_with(["Summary"]),
        critiques=[
            critique([issue("high", "numerical_consistency", "Monthly and annual figures conflict")]),
            critique(),
        ],
    )
    _, final = run_graph("Write a brief report.")

    # The latest critique describes the post-revision draft; the original is kept
    # separately so the two stages cannot overwrite each other.
    assert final["critique"]["stage"] == "post_revision"
    assert final["critique"]["needs_revision"] is False
    assert final["initial_critique"]["stage"] == "initial"
    assert final["initial_critique"]["needs_revision"] is True
    assert final["initial_critique"]["issues"][0]["claim"] == "Monthly and annual figures conflict"
    assert len(final["initial_critique"]["issues"]) == 1


def test_unresolved_issues_after_the_single_revision_are_marked_for_review(fake_llm, isolated_output_dir):
    unresolved = issue("critical", "unsupported_specifics", "Invented a 10% early-payment discount")
    fake_llm(
        plan=plan_with(["Summary", "Costs"]),
        critiques=[critique([unresolved]), critique([unresolved])],
    )
    visited, final = run_graph("Write a brief report.")

    assert visited == ["plan", "execute", "reflect", "revise", "revalidate", "export"]
    assert final["review_required"] is True
    assert final["status"] == main.STATUS_REVIEW_REQUIRED
    assert final["revision_count"] == 1
    assert len(final["unresolved_issues"]) == 1
    assert final["unresolved_issues"][0]["claim"] == "Invented a 10% early-payment discount"

    response = main._build_response_from_state(final)
    assert response["review_required"] is True
    assert "NOT validated" in response["message"]
    assert "human review" in response["message"]
    # The document is still produced, just not presented as validated.
    assert response["download_url"].endswith(".docx")


def test_review_required_document_is_marked_inside_the_docx(fake_llm, isolated_output_dir):
    unresolved = issue("critical", "unsupported_specifics", "Claimed to have examined an attachment")
    fake_llm(plan=plan_with(["Summary"]), critiques=[critique([unresolved]), critique([unresolved])])
    _, final = run_graph("Write a brief report.")

    from docx import Document
    doc = Document(final["file_path"])
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "Review Required Before Use" in text
    assert "NOT validated" in text
    assert "Claimed to have examined an attachment" in text


def test_malformed_critique_is_not_silently_treated_as_success(fake_llm, isolated_output_dir):
    fake_llm(
        plan=plan_with(["Summary"]),
        critiques=["this is not json", "neither is this"],
    )
    visited, final = run_graph("Write a brief report.")

    assert visited == ["plan", "execute", "reflect", "revise", "revalidate", "export"]
    assert final["initial_critique"]["parse_ok"] is False
    assert final["initial_critique"]["needs_revision"] is True
    assert final["critique"]["parse_ok"] is False
    assert final["review_required"] is True
    assert final["status"] == main.STATUS_REVIEW_REQUIRED
    assert any(i["category"] == "validation" for i in final["unresolved_issues"])
    assert any(i["required_correction"] == "human_review" for i in final["unresolved_issues"])

    response = main._build_response_from_state(final)
    assert "NOT validated" in response["message"]


def test_malformed_critique_then_clean_revalidation_is_validated(fake_llm, isolated_output_dir):
    fake_llm(plan=plan_with(["Summary"]), critiques=["{ broken", critique()])
    visited, final = run_graph("Write a brief report.")

    assert visited == ["plan", "execute", "reflect", "revise", "revalidate", "export"]
    assert final["initial_critique"]["parse_ok"] is False
    assert final["review_required"] is False
    assert final["status"] == main.STATUS_VALIDATED


def test_only_one_revision_pass_is_ever_spent(fake_llm, isolated_output_dir):
    """Even when every critique reports a critical problem, the graph stops."""
    bad = critique([issue("critical", "source_fidelity", "Still wrong")])
    fake_llm(plan=plan_with(["Summary"]), critiques=[bad, bad])
    visited, final = run_graph("Write a brief report.")

    assert visited.count("revise") == 1
    assert visited.count("revalidate") == 1
    assert visited.count("reflect") == 1
    assert final["revision_count"] == 1


def test_deterministic_fidelity_check_forces_revision_when_the_critic_misses_it(fake_llm, isolated_output_dir):
    """$2,400 is dropped from the draft but the critic reports no issues."""
    request = "Please approve a budget of $2,400 for the tooling subscription."
    llm = fake_llm(
        plan=plan_with(["Summary"]),
        critiques=[critique(), critique()],
        # Revision restores the figure, so revalidation should be clean.
        revision={"sections": [{"heading": "Summary", "content": "We request $2,400 for tooling."}]},
    )
    visited, final = run_graph(request)

    # The initial critique from the model was clean, but the deterministic
    # presence check found the missing figure and drove a revision.
    assert final["initial_critique"]["declared_needs_revision"] is False
    assert any(i["category"] == "source_fidelity" for i in final["initial_critique"]["issues"])
    assert visited == ["plan", "execute", "reflect", "revise", "revalidate", "export"]
    assert final["review_required"] is False
    assert llm.kinds.count("critique") == 2


def test_deterministic_fidelity_failure_survives_revision_to_review(fake_llm, isolated_output_dir):
    request = "Please approve a budget of $2,400 for the tooling subscription."
    fake_llm(
        plan=plan_with(["Summary"]),
        critiques=[critique(), critique()],
        revision={"sections": [{"heading": "Summary", "content": "We recommend adopting the tool."}]},
    )
    _, final = run_graph(request)

    assert final["review_required"] is True
    assert any(i["category"] == "source_fidelity" for i in final["unresolved_issues"])


def test_restructured_revision_response_is_rejected_and_the_draft_preserved(fake_llm, isolated_output_dir):
    fake_llm(
        plan=plan_with(["Summary", "Costs"]),
        critiques=[critique([issue("high", "requirement_coverage", "Thin content")]), critique()],
        # Only one section returned for a two-section draft -> must be rejected.
        revision={"sections": [{"heading": "Summary", "content": "Only one section."}]},
    )
    _, final = run_graph("Write a brief report.")

    assert final["revised"] is False
    assert [s["heading"] for s in final["draft_sections"]] == ["Summary", "Costs"]
    assert final["revision_count"] == 1


def test_unparseable_revision_is_not_recorded_as_revised(fake_llm, isolated_output_dir):
    fake_llm(
        plan=plan_with(["Summary"]),
        critiques=[critique([issue("high", "requirement_coverage", "Thin content")]), critique()],
        revision="not json",
    )
    _, final = run_graph("Write a brief report.")

    assert final["revised"] is False
    assert final["revision_count"] == 1
    assert len(final["draft_sections"]) == 1


def test_task_list_is_contiguous_and_reflects_the_execution(fake_llm, isolated_output_dir):
    fake_llm(plan=plan_with(["Summary", "Costs"]), critiques=[critique(), critique()])
    _, clean = run_graph("Clean run.")
    assert [t["step"] for t in clean["task_list"]] == list(range(len(clean["task_list"])))
    assert not any("Revise" in t["title"] for t in clean["task_list"])

    # Note: fake_llm only returns one critique per install, so re-run with two.
    llm = fake_llm(plan=plan_with(["Summary", "Costs"]),
                   critiques=[critique([issue("critical", "source_fidelity", "Bad")]), critique()])
    _, revised = run_graph("Revised run.")
    titles = [t["title"] for t in revised["task_list"]]
    assert [t["step"] for t in revised["task_list"]] == list(range(len(titles)))
    assert "Revise draft based on critique" in titles
    assert "Re-validate revised draft" in titles
    assert titles.index("Revise draft based on critique") < titles.index("Re-validate revised draft")
    assert titles[-1] == "Export to DOCX"
    assert llm.kinds.count("critique") == 2


def test_human_review_step_is_added_only_when_unresolved_issues_remain(fake_llm, isolated_output_dir):
    bad = critique([issue("critical", "source_fidelity", "Unresolved")])
    fake_llm(plan=plan_with(["Summary"]), critiques=[bad, bad])
    _, final = run_graph("Write a brief report.")
    titles = [t["title"] for t in final["task_list"]]
    assert "Human review required" in titles
    assert titles[-1] == "Export to DOCX"


def test_review_required_still_produces_a_valid_downloadable_docx(fake_llm, isolated_output_dir):
    bad = critique([issue("critical", "source_fidelity", "Unresolved")])
    fake_llm(plan=plan_with(["Summary"]), critiques=[bad, bad])
    _, final = run_graph("Write a brief report.")

    assert os.path.exists(final["file_path"])
    assert os.path.getsize(final["file_path"]) > 0
    from docx import Document
    doc = Document(final["file_path"])
    assert any(p.text == "Agent Execution Log" for p in doc.paragraphs)


def test_planned_title_reaches_the_exported_document(fake_llm, isolated_output_dir):
    fake_llm(plan=plan_with(["Summary"], title="Asana Premium Budget Request", doc_type="proposal"),
             critiques=[critique()])
    _, final = run_graph("Write a brief report.")

    assert final["title"] == "Asana Premium Budget Request"
    from docx import Document
    doc = Document(final["file_path"])
    assert doc.paragraphs[0].text == "Asana Premium Budget Request"

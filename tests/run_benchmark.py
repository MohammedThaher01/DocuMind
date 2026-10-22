"""Repeatable benchmark runner for the budget-email regression case.

Run it directly (it is not collected by pytest):

    python tests/run_benchmark.py
    python tests/run_benchmark.py --json tests/benchmark_report.json
    python tests/run_benchmark.py --stdout

It drives the real graph with a deterministic fake LLM, so it never touches the
network and never needs a Groq key. For each case it records the scenario, the
validation findings, whether a revision occurred, the unresolved issues and the
final status, then writes a JSON report.

What it does and does not prove
-------------------------------
It proves the *plumbing* around the criticism stage behaves correctly for this
scenario: the violating draft is revised exactly once, re-validated, and marked
for review; a repaired draft reaches a validated export.

It does NOT prove the live model finds these problems. The critic findings used
here are recorded expectations (``regression_cases.RECORDED_FINDINGS``). To
evaluate the live prompt, run ``python -m pytest tests/test_llm_integration.py``
with ``GROQ_API_KEY`` set.
"""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = Path(__file__).resolve().parent
for path in (str(REPO_ROOT), str(TESTS_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import main  # noqa: E402
import support  # noqa: E402
import regression_cases as rc  # noqa: E402

DEFAULT_REPORT = TESTS_DIR / "benchmark_report.json"


def _condense(critique):
    if not critique:
        return None
    return {
        "stage": critique.get("stage"),
        "parse_ok": critique.get("parse_ok"),
        "needs_revision": critique.get("needs_revision"),
        "issue_count": len(critique.get("issues") or []),
        "issues": [
            {
                "severity": i.get("severity"),
                "category": i.get("category"),
                "claim": i.get("claim"),
                "required_correction": i.get("required_correction"),
            }
            for i in (critique.get("issues") or [])
        ],
    }


def _run_case(name, description, critiques, revision=None):
    """Run one scenario through the real graph and collect a report record."""
    plan = support.plan_with(["Summary", "Costs", "Recommendation"])
    main.call_llm = support.FakeLLM(plan=plan, critiques=critiques, revision=revision)

    state = main._build_initial_state(rc.REQUEST)
    visited, final = support.run_graph(rc.REQUEST, initial=state)

    constraints = main.extract_source_constraints(rc.REQUEST)
    doc_path = final.get("file_path") or ""

    return {
        "case": name,
        "description": description,
        "source": "tests/fixtures/budget_email.txt",
        "source_constraints": [
            {"kind": c["kind"], "value": c["value"], "raw": c["raw"]} for c in constraints
        ],
        "derived_reference_values": main.derive_reference_values(rc.REQUEST, constraints),
        "visited_nodes": visited,
        "deterministic_findings": [
            {"severity": i.get("severity"), "claim": i.get("claim")}
            for i in (final.get("initial_critique", {}).get("deterministic_issues") or [])
        ],
        "initial_critique": _condense(final.get("initial_critique")),
        "revision_occurred": "revise" in visited,
        "revision_count": final.get("revision_count", 0),
        "revised": bool(final.get("revised")),
        "final_critique": _condense(final.get("critique")),
        "unresolved_issues": [
            {"severity": i.get("severity"), "claim": i.get("claim")}
            for i in (final.get("unresolved_issues") or [])
        ],
        "final_status": final.get("status"),
        "review_required": bool(final.get("review_required")),
        "document": {
            "path": os.path.basename(doc_path),
            "size_bytes": os.path.getsize(doc_path) if doc_path and os.path.exists(doc_path) else 0,
        },
    }


def run():
    findings = support.critique(rc.RECORDED_FINDINGS)

    cases = [
        _run_case(
            "budget_email_unsupported_draft",
            "Draft invents discounts, labour rates and metrics; one revision is allowed, then review.",
            critiques=[findings, findings],
        ),
        _run_case(
            "budget_email_repaired_after_revision",
            "The single revision restores every stated figure, so re-validation passes.",
            critiques=[findings, support.critique()],
            revision=rc.COMPLIANT_REVISION,
        ),
    ]

    expectations = {
        "budget_email_unsupported_draft": (
            lambda c: c["revision_occurred"]
            and c["revision_count"] == main.MAX_REVISION_PASSES
            and c["review_required"]
            and c["final_status"] == main.STATUS_REVIEW_REQUIRED
            and len(c["unresolved_issues"]) >= len(rc.RECORDED_FINDINGS)
        ),
        "budget_email_repaired_after_revision": (
            lambda c: c["revision_occurred"]
            and not c["review_required"]
            and c["final_status"] == main.STATUS_VALIDATED
            and not c["unresolved_issues"]
        ),
    }

    for case in cases:
        case["expectation_met"] = bool(expectations[case["case"]](case))
    return cases


def _print_summary(cases):
    print(f"\nDocuMind budget-email benchmark - max revision passes: {main.MAX_REVISION_PASSES}")
    print("=" * 78)
    for case in cases:
        print(f"\ncase: {case['case']}")
        print(f"  status            : {case['final_status']} (review_required={case['review_required']})")
        print(f"  revision          : occurred={case['revision_occurred']} count={case['revision_count']} "
              f"applied={case['revised']}")
        print(f"  initial findings  : {case['initial_critique']['issue_count']} "
              f"(needs_revision={case['initial_critique']['needs_revision']})")
        print(f"  final findings    : {case['final_critique']['issue_count']} "
              f"(needs_revision={case['final_critique']['needs_revision']})")
        print(f"  unresolved        : {len(case['unresolved_issues'])}")
        print(f"  nodes             : {' -> '.join(case['visited_nodes'])}")
        print(f"  document          : {case['document']['path']} ({case['document']['size_bytes']} bytes)")
        print(f"  expectation met   : {case['expectation_met']}")
    print("\n" + "=" * 78)
    met = sum(1 for c in cases if c["expectation_met"])
    print(f"summary: {met}/{len(cases)} case expectations met")


def main_cli(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", default=str(DEFAULT_REPORT), help="where to write the JSON report")
    parser.add_argument("--stdout", action="store_true", help="print the JSON report to stdout only")
    args = parser.parse_args(argv)

    # Keep benchmark artefacts out of the repo's generated_docs folder.
    tmp_out = tempfile.mkdtemp(prefix="documind_benchmark_")
    real_call_llm, real_output_dir = main.call_llm, main.OUTPUT_DIR
    main.OUTPUT_DIR = tmp_out

    try:
        cases = run()
        report = {
            "benchmark": "budget_email_regression",
            "max_revision_passes": main.MAX_REVISION_PASSES,
            "deterministic": True,
            "requires_api_key": False,
            "note": (
                "Critic findings are recorded expectations, not live model output. "
                "Run tests/test_llm_integration.py with GROQ_API_KEY to evaluate the live prompt."
            ),
            "cases": cases,
        }

        if args.stdout:
            print(json.dumps(report, indent=2))
        else:
            _print_summary(cases)
            Path(args.json).write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(f"report written to {args.json}")

        return 0 if all(c["expectation_met"] for c in cases) else 1
    finally:
        main.call_llm = real_call_llm
        main.OUTPUT_DIR = real_output_dir


if __name__ == "__main__":
    raise SystemExit(main_cli())

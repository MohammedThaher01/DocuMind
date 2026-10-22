"""Shared helpers for the DocuMind test suite.

Everything here is deterministic: the LLM is replaced by ``FakeLLM`` so the
routing, validation and export behaviour can be tested without a Groq API key
and without depending on model output.
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import main  # noqa: E402  (import after sys.path setup)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
BUDGET_EMAIL_FIXTURE = FIXTURES_DIR / "budget_email.txt"


# --------------------------------------------------------------------------
# Fixtures / canned model output
# --------------------------------------------------------------------------

def load_budget_email() -> str:
    return BUDGET_EMAIL_FIXTURE.read_text(encoding="utf-8")


DEFAULT_PLAN = {
    "doc_type": "business_report",
    "title": "Generated Business Document",
    "assumptions": ["The request was high level, so a standard structure was used."],
    "sections": ["Summary", "Costs", "Recommendation"],
}


def plan_with(sections, doc_type="business_report", title="Test Document", assumptions=None):
    return {
        "doc_type": doc_type,
        "title": title,
        "assumptions": assumptions if assumptions is not None else ["Assumption one."],
        "sections": list(sections),
    }


def critique(issues=None, needs_revision=None):
    """Build a critic response. ``needs_revision`` is derived when not given."""
    issues = list(issues or [])
    if needs_revision is None:
        needs_revision = any(i.get("severity") in main.MATERIAL_SEVERITIES for i in issues)
    return {"needs_revision": needs_revision, "issues": issues}


def issue(severity, category, claim, correction="correct", explanation="", evidence=""):
    return {
        "severity": severity,
        "category": category,
        "claim": claim,
        "explanation": explanation or f"Explanation for: {claim}",
        "evidence": evidence,
        "required_correction": correction,
    }


def sections_from(headings, body="Body text for the section."):
    return [{"heading": h, "content": f"{body} ({h})"} for h in headings]


# --------------------------------------------------------------------------
# Fake LLM
# --------------------------------------------------------------------------

class FakeLLM:
    """Drop-in replacement for ``main.call_llm``.

    ``critiques`` is consumed in order, so the first entry answers the initial
    reflection and the second answers the post-revision re-validation. An entry
    may be a dict (serialised to JSON) or a raw string (to simulate malformed
    model output).
    """

    def __init__(self, plan=None, critiques=None, revision=None):
        self.plan = plan if plan is not None else DEFAULT_PLAN
        self.critiques = list(critiques or [])
        self.revision = revision
        self.calls = []  # (kind, system_prompt, user_prompt)

    @property
    def kinds(self):
        return [c[0] for c in self.calls]

    def calls_of(self, kind):
        return [c for c in self.calls if c[0] == kind]

    def __call__(self, system_prompt, user_prompt, json_mode=False, temperature=0.4):
        if system_prompt == main.REFLECTION_SYSTEM_PROMPT:
            self.calls.append(("critique", system_prompt, user_prompt))
            if not self.critiques:
                return json.dumps(critique())
            nxt = self.critiques.pop(0)
            return nxt if isinstance(nxt, str) else json.dumps(nxt)

        if "autonomous planning agent" in system_prompt:
            self.calls.append(("plan", system_prompt, user_prompt))
            return json.dumps(self.plan)

        if "You are drafting the" in system_prompt:
            self.calls.append(("execute", system_prompt, user_prompt))
            heading = system_prompt.split("'")[1]
            return f"Body text for {heading}."

        if "You are revising a business document" in system_prompt:
            self.calls.append(("revise", system_prompt, user_prompt))
            if self.revision is not None:
                return self.revision if isinstance(self.revision, str) else json.dumps(self.revision)
            # Default: echo the draft back with a marker so we can observe that
            # a revision was actually applied.
            return json.dumps({"sections": [
                {"heading": h, "content": f"REVISED: {h}"} for h in self._last_draft_headings(user_prompt)
            ]})

        raise AssertionError(f"FakeLLM received an unexpected prompt: {system_prompt[:120]!r}")

    @staticmethod
    def _last_draft_headings(user_prompt):
        headings = []
        for line in user_prompt.splitlines():
            if line.startswith("### "):
                headings.append(line[4:].strip())
        return headings


def install_fake_llm(monkeypatch, llm):
    monkeypatch.setattr(main, "call_llm", llm)
    return llm


# --------------------------------------------------------------------------
# Graph driver
# --------------------------------------------------------------------------

def run_graph(request, initial=None):
    """Run the compiled graph and return (visited_nodes, final_state)."""
    state = initial if initial is not None else main._build_initial_state(request)
    visited = []
    final = None
    for chunk in main.agent_graph.stream(state, stream_mode="updates"):
        for node, update in chunk.items():
            visited.append(node)
            final = update
    return visited, final

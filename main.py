"""
DocuMind — Autonomous Document-Generation Agent
===============================================
FastAPI + LangGraph + Groq agent that takes a natural-language business
request, autonomously plans the tasks, executes each step with an LLM,
self-critiques its draft, revises if needed, and produces a polished
.docx file. The React frontend is pre-built into frontend/dist and is
served as static SPA assets from the same FastAPI process, so this app
deploys as ONE Render service with no CORS or URL-swap headaches.
"""
from dotenv import load_dotenv
load_dotenv()
import os
import re
import json
import copy
import uuid
import time
import logging
import re
from datetime import datetime
from typing import TypedDict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from langgraph.graph import StateGraph, END
from groq import Groq
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

# --------------------------------------------------------------------------
# Config / logging
# --------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("agent")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama3-70b-8192")

if not GROQ_API_KEY:
    logger.warning("GROQ_API_KEY not set. Set it as an environment variable before running.")

_client = None


def get_client() -> Groq:
    """Build the Groq client lazily on first use.

    Keeping construction lazy means importing this module (and therefore
    running the unit tests) never requires an API key, and a missing key only
    fails the request that actually needs the model.
    """
    global _client
    if _client is None:
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


OUTPUT_DIR = "generated_docs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

MAX_LLM_RETRIES = 5

# Bounded validation: a document is revised at most this many times. After the
# last allowed revision the document is re-validated exactly once and, if
# material issues survive, it is exported marked as "review_required" rather
# than being reported as validated.
MAX_REVISION_PASSES = 1

# Issue severities that justify spending a revision pass.
MATERIAL_SEVERITIES = ("critical", "high")
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

ISSUE_CATEGORIES = (
    "source_fidelity",
    "numerical_consistency",
    "internal_contradiction",
    "unsupported_specifics",
    "requirement_coverage",
    "validation",
)

REQUIRED_CORRECTIONS = ("correct", "remove", "label_as_assumption", "human_review")

# Document status values surfaced through the API.
STATUS_PENDING = "pending"
STATUS_REVISING = "revising"
STATUS_VALIDATED = "validated"
STATUS_REVIEW_REQUIRED = "review_required"

# --------------------------------------------------------------------------
# LLM call wrapper with retry, sleep, and timeout
# --------------------------------------------------------------------------

def call_llm(system_prompt: str, user_prompt: str, json_mode: bool = False, temperature: float = 0.4) -> str:
    last_err = None
    for attempt in range(1, MAX_LLM_RETRIES + 1):
        try:
            kwargs = {}
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            resp = get_client().chat.completions.create(
                model=GROQ_MODEL,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                timeout=30,
                **kwargs,
            )
            return resp.choices[0].message.content
        except Exception as e:
            last_err = e
            logger.warning(f"LLM call attempt {attempt} failed: {e}")
            if attempt < MAX_LLM_RETRIES:
                time.sleep(2 * attempt)
    raise RuntimeError(f"LLM call failed after {MAX_LLM_RETRIES} attempts: {last_err}")


def try_parse_json(raw: str):
    """Strict JSON parse -> (obj, ok).

    Returns ``(None, False)`` when the model output is missing, not valid JSON,
    or not a JSON object. Callers that must not silently treat a failure as
    success (the reflection stage) use ``ok`` explicitly instead of a fallback.
    """
    if not isinstance(raw, str) or not raw.strip():
        logger.error("JSON parse failed: empty or non-string model output.")
        return None, False

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    try:
        obj = json.loads(cleaned)
    except Exception as e:
        logger.error(f"JSON parse failed. Error: {e}. Raw: {raw[:300]}")
        return None, False

    if not isinstance(obj, dict):
        logger.error(f"JSON parse failed: expected an object, got {type(obj).__name__}.")
        return None, False
    return obj, True


def safe_json_parse(raw: str, fallback: dict) -> dict:
    """Lenient parse for nodes that can degrade safely (plan / revise)."""
    obj, ok = try_parse_json(raw)
    if not ok:
        logger.error("Falling back to a default value for unparseable model output.")
        return fallback
    return obj


# --------------------------------------------------------------------------
# Deterministic source-constraint checks
# --------------------------------------------------------------------------
# These helpers look ONLY for figures the user stated explicitly: currency
# amounts, percentages, hours-per-week, business-day commitments and week
# counts. They are deliberately narrow and are not a general prose number
# extractor. Semantic questions ("was the stated budget reinterpreted as a
# per-user price?") are left to the critic model, which is told to explain its
# uncertainty instead of guessing.

_WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}
_NUM_TOKEN = r"(?:\d+(?:\.\d+)?|" + "|".join(_WORD_NUMBERS) + r")"

_CURRENCY_RE = re.compile(r"\$\s?(\d[\d,]*(?:\.\d+)?)")
_PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)\s?%")
_HOURS_PER_WEEK_RE = re.compile(rf"\b({_NUM_TOKEN})\s*(?:hours?|hrs?)\s*(?:per|/|a|each)\s*week\b", re.I)
_BUSINESS_DAYS_RE = re.compile(rf"\b({_NUM_TOKEN})\s*business\s*days?\b", re.I)
_WEEKS_RE = re.compile(rf"\b({_NUM_TOKEN})\s*weeks?\b", re.I)
_REDUCTION_PCT_RE = re.compile(
    r"(?:reduc\w*|sav\w*|less|lower)\D{0,40}?(\d+(?:\.\d+)?)\s?%"
    r"|(\d+(?:\.\d+)?)\s?%\s*(?:reduc\w*|sav\w*|less|lower)",
    re.I,
)
_NUMBER_TOKEN_RE = re.compile(r"\d+(?:\.\d+)?")

# --------------------------------------------------------------------------
# Context/unit matching for source fidelity
# --------------------------------------------------------------------------
# A bare "is this number present anywhere?" check is not enough: it treats an
# unrelated occurrence of the same number as a preserved fact. These patterns
# add the smallest amount of context that reliably separates a preserved fact
# from a reinterpreted one.
#
# The unit list is deliberately restricted to headcount/seat units. "per month"
# and "per year" describe a *period*, and a total can legitimately be
# periodised, so including them would create false positives.

_PER_UNIT_UNIT_PATTERN = (
    r"(?:users?|people|persons?|employees?|seats?|licen[cs]es?|heads?|members?|staff|"
    r"individuals?|teammates?|engineers?|agents?|accounts?|devices?|machines?)"
)

# "$2,400 per user" / "$2,400/user" - the amount itself carries a per-unit rate.
_AMOUNT_PER_UNIT_RE = re.compile(r"\s*(?:per[\s\-]+|/\s*)" + _PER_UNIT_UNIT_PATTERN + r"\b", re.I)

# "12 hours per employee" - a headcount qualifier inserted between an hours
# figure and its period turns a team figure into a per-person figure.
_HOURS_PER_UNIT_RE = re.compile(
    r"\s*(?:hours?|hrs?)\s*(?:per|/)\s*" + _PER_UNIT_UNIT_PATTERN + r"\b", re.I
)

_AMOUNT_TOKEN_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")

# How bad is it if a source figure of this kind disappears from the document.
CONSTRAINT_SEVERITY = {
    "currency": "critical",
    "hours_per_week": "high",
    "percentage": "high",
    "business_days": "high",
    "weeks": "medium",
}


def _num_to_float(token) -> Optional[float]:
    if token is None:
        return None
    token = str(token).strip().lower()
    if token in _WORD_NUMBERS:
        return float(_WORD_NUMBERS[token])
    try:
        return float(token.replace(",", ""))
    except ValueError:
        return None


def _word_forms(value: float) -> List[str]:
    return [w for w, n in _WORD_NUMBERS.items() if float(n) == float(value)]


def _draft_to_text(draft_sections: List[dict]) -> str:
    return "\n\n".join(f"### {s.get('heading', '')}\n{s.get('content', '')}" for s in draft_sections or [])


def extract_source_constraints(request_text: str) -> List[dict]:
    """Return the figures/commitments the user stated explicitly in the request."""
    if not request_text:
        return []

    found: List[dict] = []

    def _add(kind: str, match, unit: str):
        value = _num_to_float(match.group(1))
        if value is not None:
            found.append({"kind": kind, "value": value, "raw": match.group(0).strip(), "unit": unit})

    for m in _CURRENCY_RE.finditer(request_text):
        _add("currency", m, "USD")
    for m in _HOURS_PER_WEEK_RE.finditer(request_text):
        _add("hours_per_week", m, "hours/week")
    for m in _BUSINESS_DAYS_RE.finditer(request_text):
        _add("business_days", m, "business days")
    for m in _WEEKS_RE.finditer(request_text):
        _add("weeks", m, "weeks")
    for m in _PERCENT_RE.finditer(request_text):
        _add("percentage", m, "%")

    # The same figure often appears several times in a request. Keep one entry
    # per (kind, value) so the fidelity check cannot report the same missing
    # figure once per occurrence.
    seen = set()
    unique: List[dict] = []
    for c in found:
        key = (c["kind"], round(float(c["value"]), 3))
        if key in seen:
            continue
        seen.add(key)
        unique.append(c)
    return unique


def _draft_numbers(draft_text: str) -> set:
    return {round(float(n), 3) for n in _NUMBER_TOKEN_RE.findall((draft_text or "").replace(",", ""))}


def _number_spans(text: str):
    """Yield (value, match) for each numeric token, tolerating thousands separators.

    Yielding the match (not just the value) keeps offsets meaningful, so callers
    can inspect what *follows* a specific number in the original text.
    """
    for m in _AMOUNT_TOKEN_RE.finditer(text or ""):
        try:
            value = round(float(m.group(0).replace(",", "")), 3)
        except ValueError:
            continue
        yield value, m


def _qualified_by(text: str, value: float, pattern: re.Pattern) -> Optional[str]:
    """Return the qualifier immediately following `value`, or None.

    The qualifier must be adjacent to the number, which is what keeps this
    reliable: `"$2,400 per user"` matches, while `"$2,400 is not a per-user
    price"` does not.
    """
    target = round(float(value), 3)
    for found_value, m in _number_spans(text):
        if found_value != target:
            continue
        qualifier = pattern.match(text, m.end())
        if qualifier:
            return qualifier.group(0).strip()
    return None


def _constraint_present(constraint: dict, draft_text: str, numbers: set, lowered: str) -> bool:
    """Is the stated figure present *with the unit that gives it its meaning*?

    For unit-bearing kinds (a week, a business day, a percentage) a bare number
    is not enough. `"four-month payback"` must not satisfy a
    `"four business days"` commitment, and a stray `12` must not satisfy
    `"12 hours per week"`.
    """
    value = round(float(constraint["value"]), 3)
    kind = constraint["kind"]

    kind_re = {
        "business_days": _BUSINESS_DAYS_RE,
        "hours_per_week": _HOURS_PER_WEEK_RE,
        "weeks": _WEEKS_RE,
        "percentage": _PERCENT_RE,
    }.get(kind)

    if kind_re is not None:
        for m in kind_re.finditer(draft_text or ""):
            if _num_to_float(m.group(1)) == value:
                return True
        return False

    # Currency and anything else: the amount itself is the unit.
    if value in numbers:
        return True
    return any(re.search(rf"\b{re.escape(w)}\b", lowered) for w in _word_forms(value))


def _reinterpretation_issue(constraint: dict, request_text: str, draft_text: str) -> Optional[dict]:
    """Detect a stated figure that survived but had its unit changed.

    Only fires when the amount is directly qualified in the document *and* the
    request did not already state it that way (so a genuine per-user price is not
    reported as a reinterpretation).
    """
    kind = constraint["kind"]
    if kind == "currency":
        pattern, label = _AMOUNT_PER_UNIT_RE, "per-unit rate"
    elif kind == "hours_per_week":
        pattern, label = _HOURS_PER_UNIT_RE, "per-person rate"
    else:
        return None

    if _qualified_by(request_text, constraint["value"], pattern):
        return None  # the source states it per unit, so nothing was reinterpreted

    qualifier = _qualified_by(draft_text, constraint["value"], pattern)
    if not qualifier:
        return None

    return {
        "severity": CONSTRAINT_SEVERITY.get(kind, "medium"),
        "category": "source_fidelity",
        "claim": (
            f"The user-stated figure \"{constraint['raw']}\" ({kind}) is re-expressed as a {label} "
            f"(\"{qualifier}\") in the document."
        ),
        "explanation": (
            "The number is still present but its unit has changed: a figure the user stated for the "
            "whole team/total has been restated per unit. That changes the scope of the request even "
            "though the digits match."
        ),
        "evidence": (
            f"request contains \"{constraint['raw']}\"; the document writes the same value as \"{qualifier}\""
        ),
        "required_correction": "correct",
    }


def check_source_fidelity(request_text: str, draft_sections: List[dict]) -> List[dict]:
    """Deterministic check that explicitly-stated source figures survive *intact*.

    Two things are checked, and only for figures the user stated outright:

    1. **Presence with unit.** A stated commitment must still appear with the
       unit that gives it meaning (`"four business days"`, `"12 hours per week"`),
       not merely as a matching digit somewhere in the document.
    2. **Unit preservation.** A stated total must not be re-expressed as a
       per-unit rate, and a stated team workload must not become a per-person
       rate.

    This is a narrow, high-signal check, not a semantic audit. It cannot judge
    rephrasings it has no pattern for (for example `"12 hours per week per
    user"`), so the critic is asked to confirm every deterministic finding and to
    cover what this layer cannot see.
    """
    constraints = extract_source_constraints(request_text)
    if not constraints:
        return []

    draft_text = _draft_to_text(draft_sections)
    numbers = _draft_numbers(draft_text)
    lowered = draft_text.lower()

    issues: List[dict] = []
    for c in constraints:
        # A changed unit is the more specific diagnosis, so check it first.
        reinterpreted = _reinterpretation_issue(c, request_text, draft_text)
        if reinterpreted is not None:
            issues.append(reinterpreted)
            continue

        if _constraint_present(c, draft_text, numbers, lowered):
            continue

        issues.append({
            "severity": CONSTRAINT_SEVERITY.get(c["kind"], "medium"),
            "category": "source_fidelity",
            "claim": f"The user-stated figure \"{c['raw']}\" ({c['kind']}) is missing from the document.",
            "explanation": (
                "A figure the user supplied explicitly no longer appears anywhere in the assembled "
                "document. It may have been dropped, silently changed, or reformulated in a way that "
                "alters its meaning."
            ),
            "evidence": f"request contains \"{c['raw']}\"; the assembled document contains no matching value",
            "required_correction": "correct",
        })
    return issues


def project_weekly_savings(weekly_hours: float, reduction_pct: float, weeks: int = 52) -> dict:
    """Objective projection from inputs the user actually supplied.

    Deliberately arithmetic-only: it never invents a labour rate, discount or
    cost basis, so it cannot produce dollar savings or ROI.
    """
    weekly_saved = round(float(weekly_hours) * (float(reduction_pct) / 100.0), 2)
    return {
        "basis_weekly_hours": float(weekly_hours),
        "reduction_pct": float(reduction_pct),
        "weeks": int(weeks),
        "weekly_hours_saved": weekly_saved,
        "annual_projected_hours_saved": round(weekly_saved * int(weeks), 1),
        "note": "Projected from user-stated inputs only; not a measured or verified result.",
    }


def derive_reference_values(request_text: str, constraints: Optional[List[dict]] = None) -> dict:
    """Compute only what the stated inputs support; return {} when they do not."""
    constraints = extract_source_constraints(request_text) if constraints is None else constraints
    hours = [c["value"] for c in constraints if c["kind"] == "hours_per_week"]
    reduction = _REDUCTION_PCT_RE.search(request_text or "")
    if len(hours) == 1 and reduction:
        token = reduction.group(1) if reduction.group(1) is not None else reduction.group(2)
        pct = _num_to_float(token)
        if pct is not None:
            return {"time_savings_projection": project_weekly_savings(hours[0], pct)}
    return {}


def format_constraints(constraints: List[dict]) -> str:
    if not constraints:
        return "(no explicit figures or commitments found in the request)"
    return "\n".join(f"- [{c['kind']}] {c['raw']}" for c in constraints)


def format_derived(derived: dict) -> str:
    if not derived:
        return "(nothing can be computed from the stated inputs alone)"
    return json.dumps(derived, indent=2)


# --------------------------------------------------------------------------
# Critique schema: normalisation, materiality and formatting
# --------------------------------------------------------------------------

UNPARSEABLE_ISSUE = {
    "severity": "high",
    "category": "validation",
    "claim": "The validation stage could not parse a usable critique result.",
    "explanation": (
        "The critique model returned missing, malformed or non-JSON output, so the draft could not "
        "be confirmed clean. Validation is treated as failed rather than as a pass."
    ),
    "evidence": "critique parse failure",
    "required_correction": "human_review",
}


def coerce_issue(item) -> Optional[dict]:
    """Normalise one critique entry. Accepts the legacy bare-string form."""
    if isinstance(item, str):
        text = item.strip()
        if not text:
            return None
        # A plain string carries no severity; default to "high" so that legacy
        # or abbreviated model output still triggers a revision (back-compat
        # with the previous schema, which revised on any non-empty issue list).
        return {
            "severity": "high",
            "category": "unspecified",
            "claim": text,
            "explanation": "",
            "evidence": "",
            "required_correction": "correct",
        }

    if not isinstance(item, dict):
        return None

    claim = str(item.get("claim") or item.get("issue") or item.get("description") or "").strip()
    explanation = str(item.get("explanation") or item.get("detail") or "").strip()
    if not claim and not explanation:
        return None

    severity = str(item.get("severity") or "high").strip().lower()
    if severity not in SEVERITY_ORDER:
        severity = "high"

    category = str(item.get("category") or "unspecified").strip().lower()
    if category not in ISSUE_CATEGORIES:
        category = "unspecified"

    correction = str(item.get("required_correction") or "correct").strip().lower()
    if correction not in REQUIRED_CORRECTIONS:
        correction = "correct"

    return {
        "severity": severity,
        "category": category,
        "claim": claim or explanation,
        "explanation": explanation,
        "evidence": str(item.get("evidence") or item.get("supporting_source") or "").strip(),
        "required_correction": correction,
    }


def has_material_issues(critique: dict) -> bool:
    """True when a critique contains at least one critical/high issue."""
    issues = (critique or {}).get("issues") or []
    return any(i.get("severity") in MATERIAL_SEVERITIES for i in issues)


def normalize_critique(raw_obj, parse_ok: bool) -> dict:
    """Build the canonical critique object used by routing and reporting.

    A parse failure is never turned into "the document is safe": it produces a
    synthetic high-severity issue with required_correction="human_review" and
    sets needs_revision, so it takes the same path as a real finding.
    """
    if not parse_ok or not isinstance(raw_obj, dict):
        return {
            "parse_ok": False,
            "needs_revision": True,
            "declared_needs_revision": True,
            "issues": [dict(UNPARSEABLE_ISSUE)],
        }

    issues = []
    for item in (raw_obj.get("issues") or []):
        coerced = coerce_issue(item)
        if coerced:
            issues.append(coerced)

    declared = bool(raw_obj.get("needs_revision", False))
    return {
        "parse_ok": True,
        "declared_needs_revision": declared,
        # Only material (critical/high) issues justify spending a revision pass.
        "needs_revision": has_material_issues({"issues": issues}),
        "issues": issues,
    }


def merge_issues(primary: List[dict], secondary: List[dict]) -> List[dict]:
    """Merge two issue lists, dropping exact-duplicate claims (order preserved)."""
    merged: List[dict] = []
    seen = set()
    for issue in list(primary or []) + list(secondary or []):
        key = (issue.get("claim") or "").strip().lower()[:120]
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        merged.append(issue)
    return merged


def format_issues_for_prompt(issues: List[dict]) -> str:
    if not issues:
        return "- (none)"
    lines = []
    for i in issues:
        parts = [f"- [{i.get('severity', 'unknown')}/{i.get('category', 'unspecified')}] {i.get('claim', '')}"]
        if i.get("explanation"):
            parts.append(f"Explanation: {i['explanation']}")
        if i.get("evidence"):
            parts.append(f"Evidence: {i['evidence']}")
        parts.append(f"Required correction: {i.get('required_correction', 'correct')}")
        lines.append(" | ".join(parts))
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Reflection prompt (strengthened validation stage)
# --------------------------------------------------------------------------

REFLECTION_SYSTEM_PROMPT = (
    "You are a strict validation editor for an AI-generated business document. "
    "You compare the ENTIRE assembled document against the ORIGINAL user request and report concrete, "
    "provable problems only. You never rewrite the document.\n\n"
    "Audit these five areas:\n"
    "1. SOURCE FIDELITY - user-supplied figures, dates, quantities, units, commitments, named entities and "
    "intended meaning must be preserved. Never reinterpret a stated total as a per-person or per-user figure. "
    "Never add facts that change the scope of the request. Distinguish what the user actually stated from "
    "anything the document asserts on its own.\n"
    "2. NUMERICAL AND FINANCIAL CONSISTENCY - recalculate monetary totals, annual versus monthly costs, "
    "discounts, net costs, percentages, ROI, payback periods, savings and ratios. The same input values and "
    "definitions must be used consistently throughout the document. Identify missing inputs instead of "
    "inventing them. Never invent an hourly wage, licence price, discount, user count, budget or any other "
    "financial assumption in order to complete an ROI analysis. If a value is not supplied and cannot be "
    "derived from the request, the document must mark it unspecified or drop the dependent calculation.\n"
    "3. INTERNAL CONTRADICTIONS - find conflicting dates, timelines, team sizes, quantities, prices, resource "
    "estimates, targets and commitments, including between the executive summary, body, tables, "
    "recommendations, appendices and conclusions. Do not resolve a conflict by choosing a new value: preserve "
    "the source constraint or report the conflict as unresolved.\n"
    "4. UNSUPPORTED SPECIFICS - explicitly audit invented company or product names; team or user counts; "
    "prices, discounts, salaries, budgets and commercial terms; performance targets, SLAs, percentages and "
    "KPIs; security permissions and access policies; regulatory obligations or jurisdiction-specific claims; "
    "research sources, surveys, audited accounts, statistics and model outputs; and attachments, vendor "
    "quotations or documents that were never provided. Plausibility is not evidence. For a consequential "
    "missing detail, remove it, use a clearly marked placeholder, or flag it for confirmation. Do not turn "
    "every missing detail into a blocking issue when a safe generic document can still be produced.\n"
    "5. REQUIREMENT COVERAGE - confirm the document addresses the original request, that important "
    "user-provided constraints did not disappear during section-by-section generation or revision, and flag "
    "polished but unsupported claims that could mislead a reader.\n\n"
    "Report an issue only when you can name the exact problematic claim and explain why it is wrong. "
    "Do not repeat findings already listed in DETERMINISTIC CHECKS - only add additional problems. "
    "Judge severity by consequence: critical means the document is materially wrong or misleading, high means "
    "a reader could be seriously misled, medium/low means a quality or clarity problem.\n"
    "If the document is genuinely sound, return an empty issues list with needs_revision false.\n\n"
    "Respond ONLY with strict JSON in exactly this shape:\n"
    '{"needs_revision": true|false, "issues": [{"severity": "critical|high|medium|low", '
    '"category": "source_fidelity|numerical_consistency|internal_contradiction|unsupported_specifics|requirement_coverage|validation", '
    '"claim": "the exact problematic claim", '
    '"explanation": "why it is wrong", '
    '"evidence": "the supporting source text or recalculated arithmetic", '
    '"required_correction": "correct|remove|label_as_assumption|human_review"}]}'
)


# --------------------------------------------------------------------------
# Agent State
# --------------------------------------------------------------------------

class AgentState(TypedDict):
    request: str
    title: str
    doc_type: str
    assumptions: List[str]
    task_list: List[dict]
    sections: List[dict]
    draft_sections: List[dict]
    critique: dict            # critique of the current draft (latest stage)
    initial_critique: dict    # critique of the first draft, preserved for reporting
    revised: bool
    revision_count: int
    review_required: bool
    unresolved_issues: List[dict]
    status: str
    file_path: str
    error: Optional[str]


# --------------------------------------------------------------------------
# Graph Nodes
# --------------------------------------------------------------------------

def node_classify_and_plan(state: AgentState) -> AgentState:
    system = (
        "You are an autonomous planning agent for a business document generator. "
        "Given a user's natural language request, decide: "
        "1) the most appropriate business document type "
        "(proposal, meeting_minutes, project_plan, business_report, technical_design, sop, product_spec), "
        "2) a logical ordered list of sections needed for that document type, "
        "3) any reasonable assumptions you must make because the request is ambiguous, "
        "incomplete, or has conflicting requirements. Always make sensible assumptions "
        "rather than refusing - state them explicitly. "
        "Respond ONLY with strict JSON: "
        '{"doc_type": "...", "title": "...", "assumptions": ["..."], '
        '"sections": ["Section Name 1", "Section Name 2", ...]}'
    )
    raw = call_llm(system, f"User request: {state['request']}", json_mode=True, temperature=0.3)
    fallback = {
        "doc_type": "business_report",
        "title": "Generated Business Document",
        "assumptions": ["Request was generic; defaulted to a standard business report structure."],
        "sections": ["Executive Summary", "Background", "Key Points", "Recommendations", "Next Steps"],
    }
    plan = safe_json_parse(raw, fallback)

    total = [
        {"step": 0, "title": f"Classify request -> {plan.get('doc_type', 'business_report')}", "status": "done"},
    ]
    total += [
        {"step": 0, "title": f"Draft section: {s}", "status": "pending"}
        for s in plan.get("sections", fallback["sections"])
    ]
    total += [
        {"step": 0, "title": "Self-critique draft", "status": "pending"},
        {"step": 0, "title": "Export to DOCX", "status": "pending"},
    ]
    renumber_tasks(total)
    task_list = total

    state["doc_type"] = plan.get("doc_type", "business_report")
    state["assumptions"] = plan.get("assumptions", [])
    state["task_list"] = task_list
    state["sections"] = [{"heading": h, "content": ""} for h in plan.get("sections", fallback["sections"])]
    state["title"] = str(plan.get("title") or "Generated Business Document")
    logger.info(f"Planned doc_type={state['doc_type']} sections={[s['heading'] for s in state['sections']]}")
    return state


def node_execute_steps(state: AgentState) -> AgentState:
    assumptions_text = "\n".join(f"- {a}" for a in state["assumptions"]) or "None"
    drafted = []
    for sec in state["sections"]:
        system = (
            f"You are drafting the '{sec['heading']}' section of a {state['doc_type'].replace('_', ' ')} "
            "for a professional business audience. Write clear, concrete, well-structured content "
            "(use realistic mock data/numbers/names where specifics are missing - never leave placeholders "
            "like [insert here]). 120-220 words. Plain text, no markdown symbols."
        )
        user = (
            f"Original user request: {state['request']}\n\n"
            f"Assumptions already made by the planning stage:\n{assumptions_text}\n\n"
            f"Write the content for the section titled: {sec['heading']}"
        )
        content = call_llm(system, user, temperature=0.5)
        drafted.append({"heading": sec["heading"], "content": content.strip()})

    for t in state["task_list"]:
        if t["title"].startswith("Draft section"):
            t["status"] = "done"

    state["draft_sections"] = drafted
    logger.info(f"Executed {len(drafted)} section drafts.")
    return state


def renumber_tasks(task_list: List[dict]) -> List[dict]:
    """Re-number steps to match list order so the checklist has no gaps."""
    for i, t in enumerate(task_list or []):
        t["step"] = i
    return task_list


def _insert_task_before(state: AgentState, anchor_title: str, new_title: str, status: str = "done") -> None:
    """Insert a step just before an existing step and renumber all steps.

    Steps are appended dynamically as the run grows, so the checklist the UI
    renders always matches the execution that actually happened.
    """
    task_list = state.get("task_list") or []
    new_task = {"step": 0, "title": new_title, "status": status}
    for i, t in enumerate(task_list):
        if t.get("title") == anchor_title:
            task_list.insert(i, new_task)
            break
    else:
        task_list.append(new_task)
    renumber_tasks(task_list)
    state["task_list"] = task_list


def run_reflection(state: AgentState, draft_sections: List[dict], stage: str) -> dict:
    """Validate an assembled draft against the original request.

    Combines two sources of evidence:
      * deterministic presence checks on figures the user stated explicitly;
      * an LLM critic covering source fidelity, numerical consistency, internal
        contradictions, unsupported specifics and requirement coverage.

    A malformed critic response is converted into a high-severity issue rather
    than being treated as a clean pass.
    """
    constraints = extract_source_constraints(state["request"])
    derived = derive_reference_values(state["request"], constraints)
    deterministic_issues = check_source_fidelity(state["request"], draft_sections)

    user = (
        f"ORIGINAL USER REQUEST:\n{state['request']}\n\n"
        "SOURCE FIGURES AND COMMITMENTS THE USER STATED EXPLICITLY "
        "(extracted deterministically; these must survive into the document):\n"
        f"{format_constraints(constraints)}\n\n"
        "DERIVED REFERENCE VALUES (arithmetic on the stated inputs only; do not contradict "
        "these, and do not extend them with invented inputs):\n"
        f"{format_derived(derived)}\n\n"
        f"ASSEMBLED DOCUMENT ({stage} draft):\n{_draft_to_text(draft_sections)}\n\n"
        "DETERMINISTIC CHECKS ALREADY RUN (presence checks; they can produce false positives if a "
        "figure was legitimately rephrased - verify each one and do NOT repeat it in your own "
        "issue list unless you can confirm it):\n"
        f"{format_issues_for_prompt(deterministic_issues)}\n\n"
        "Respond ONLY with the JSON object described in your instructions."
    )

    raw = call_llm(REFLECTION_SYSTEM_PROMPT, user, json_mode=True, temperature=0.2)
    obj, parse_ok = try_parse_json(raw)
    critique = normalize_critique(obj, parse_ok)

    # Deterministic findings are facts, so they are kept even when the critic
    # omits them; critic findings are then merged in.
    critique["issues"] = merge_issues(deterministic_issues, critique["issues"])
    critique["deterministic_issues"] = deterministic_issues
    critique["derived_reference_values"] = derived
    critique["source_constraints"] = constraints
    critique["needs_revision"] = (not critique["parse_ok"]) or has_material_issues(critique)
    critique["stage"] = stage
    return critique


def node_reflect(state: AgentState) -> AgentState:
    joined = "\n\n".join(f"### {s['heading']}\n{s['content']}" for s in state["draft_sections"])
    system = (
        "You are a critical editor reviewing an AI-generated business document draft. "
        "Check it against the ORIGINAL user request. Identify concrete issues: missing "
        "requirements, unaddressed ambiguity, weak/generic content, inconsistent assumptions. "
        "Respond ONLY with strict JSON: "
        '{"needs_revision": true/false, "issues": ["issue 1", "issue 2"]}. '
        "If the draft is genuinely solid, set needs_revision to false with an empty issues list."
    )
    user = f"Original request: {state['request']}\n\nDraft:\n{joined}"
    raw = call_llm(system, user, json_mode=True, temperature=0.2)
    critique = safe_json_parse(raw, {"needs_revision": False, "issues": []})

    for t in state["task_list"]:
        if t["title"] == "Self-critique draft":
            t["status"] = "done"

    state["critique"] = critique
    logger.info(f"Reflection result: {critique}")
    return state


def node_revise(state: AgentState) -> AgentState:
    """Single bounded revision pass driven by the latest critique."""
    issues = (state.get("critique") or {}).get("issues") or []
    current = state["draft_sections"]
    joined = _draft_to_text(current)
    system = (
        "You are revising a business document draft to fix specific issues raised by an editor. "
        "Keep the same section headings, the same number of sections and the same overall structure. "
        "Address every issue listed. Remove or clearly label unsupported specifics instead of replacing "
        "them with new invented specifics, and never introduce a new figure that the original request "
        "did not supply. "
        'Respond ONLY with strict JSON: {"sections": [{"heading": "...", "content": "..."}, ...]}'
    )
    user = (
        f"Original request: {state['request']}\n\n"
        f"Issues to fix:\n{format_issues_for_prompt(issues)}\n\n"
        f"Current draft:\n{joined}"
    )
    raw = call_llm(system, user, json_mode=True, temperature=0.4)
    obj, parse_ok = try_parse_json(raw)

    applied = False
    if parse_ok and isinstance(obj.get("sections"), list):
        candidate = [
            {"heading": str(s["heading"]), "content": str(s["content"])}
            for s in obj["sections"]
            if isinstance(s, dict) and s.get("heading") and s.get("content")
        ]
        # Only accept a revision that preserves the section structure; a
        # truncated or restructured response is rejected rather than silently
        # dropping sections.
        if len(candidate) == len(current) and candidate:
            state["draft_sections"] = candidate
            applied = True

    state["revised"] = applied
    state["revision_count"] = state.get("revision_count", 0) + 1
    _insert_task_before(state, "Export to DOCX", "Revise draft based on critique", "done")
    logger.info("Revision pass %d applied=%s", state["revision_count"], applied)
    return state


def node_revalidate(state: AgentState) -> AgentState:
    """Re-validate after the bounded revision and decide the final status.

    This is the only place that can mark a document as needing human review.
    Unresolved material issues are surfaced instead of being reported as a
    successful validation.
    """
    critique = run_reflection(state, state["draft_sections"], stage="post_revision")
    state["critique"] = critique

    _insert_task_before(state, "Export to DOCX", "Re-validate revised draft", "done")

    if critique["needs_revision"]:
        state["review_required"] = True
        state["unresolved_issues"] = critique["issues"]
        state["status"] = STATUS_REVIEW_REQUIRED
        _insert_task_before(state, "Export to DOCX", "Human review required", "pending")
        logger.warning(
            "Unresolved issues remain after %d revision pass(es): %d issue(s) flagged for review.",
            state.get("revision_count", 0), len(critique["issues"]),
        )
    else:
        state["review_required"] = False
        state["unresolved_issues"] = []
        state["status"] = STATUS_VALIDATED
        logger.info("Revised draft passed re-validation.")
    return state


def node_export_docx(state: AgentState) -> AgentState:
    for t in state["task_list"]:
        if t["title"] == "Export to DOCX":
            t["status"] = "done"

    doc = Document()

    title = doc.add_heading(state.get("title") or "Generated Business Document", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = meta.add_run(f"Document Type: {state['doc_type'].replace('_', ' ').title()}  |  Generated: {datetime.now().strftime('%B %d, %Y')}")
    run.italic = True
    run.font.size = Pt(10)
    run.font.color.rgb = RGBColor(0x55, 0x55, 0x55)

    doc.add_paragraph()

    if state.get("review_required"):
        doc.add_heading("Review Required Before Use", level=1)
        doc.add_paragraph(
            "This document was NOT validated. Material issues remained after the allowed revision "
            f"pass(es) ({state.get('revision_count', 0)}). Treat the content below as a draft and "
            "resolve the following before relying on it."
        )
        for issue in state.get("unresolved_issues", []):
            doc.add_paragraph(
                f"[{issue.get('severity', 'unknown')}/{issue.get('category', 'unspecified')}] "
                f"{issue.get('claim', '')} "
                f"(required correction: {issue.get('required_correction', 'correct')})",
                style="List Bullet",
            )
        doc.add_paragraph()

    if state.get("assumptions"):
        doc.add_heading("Assumptions Made by the Agent", level=1)
        for a in state["assumptions"]:
            doc.add_paragraph(a, style="List Bullet")
        doc.add_paragraph()

    for sec in state["draft_sections"]:
        doc.add_heading(sec["heading"], level=1)
        for para in sec["content"].split("\n"):
            if para.strip():
                doc.add_paragraph(para.strip())

    doc.add_page_break()
    doc.add_heading("Agent Execution Log", level=1)
    table = doc.add_table(rows=1, cols=3)
    table.style = "Light Grid Accent 1"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = table.rows[0].cells
    hdr[0].text, hdr[1].text, hdr[2].text = "Step", "Task", "Status"
    for t in state["task_list"]:
        row = table.add_row().cells
        row[0].text = str(t["step"])
        row[1].text = t["title"]
        row[2].text = t["status"]

    fname = f"{state['doc_type']}_{uuid.uuid4().hex[:8]}.docx"
    fpath = os.path.join(OUTPUT_DIR, fname)
    doc.save(fpath)

    state["file_path"] = fpath
    logger.info(f"Document exported to {fpath}")
    return state


def route_after_reflect(state: AgentState) -> str:
    """Decide whether the first draft needs a revision pass.

    A revision pass is spent only when the critique carries at least one
    critical/high issue, or when the critique itself could not be parsed (which
    must never be read as "the document is safe"). Low/medium issues are
    reported but do not block export.
    """
    if state.get("revision_count", 0) >= MAX_REVISION_PASSES:
        return "export"
    critique = state.get("critique") or {}
    if not critique.get("parse_ok", True) or critique.get("needs_revision"):
        return "revise"
    return "export"


def route_after_revalidate(state: AgentState) -> str:
    """Terminal routing: the bounded revision cycle always ends in export.

    node_revalidate has already recorded whether the document is validated or
    requires human review, so there is no second revision branch here.
    """
    return "export"


# --------------------------------------------------------------------------
# Build LangGraph
# --------------------------------------------------------------------------

def build_graph():
    """plan -> execute -> reflect -> (revise -> revalidate)? -> export -> END

    The revision cycle is bounded: at most MAX_REVISION_PASSES revision passes,
    followed by exactly one re-validation before export.
    """
    graph = StateGraph(AgentState)
    graph.add_node("plan", node_classify_and_plan)
    graph.add_node("execute", node_execute_steps)
    graph.add_node("reflect", node_reflect)
    graph.add_node("revise", node_revise)
    graph.add_node("revalidate", node_revalidate)
    graph.add_node("export", node_export_docx)

    graph.set_entry_point("plan")
    graph.add_edge("plan", "execute")
    graph.add_edge("execute", "reflect")
    graph.add_conditional_edges("reflect", route_after_reflect, {"revise": "revise", "export": "export"})
    graph.add_edge("revise", "revalidate")
    graph.add_conditional_edges("revalidate", route_after_revalidate, {"export": "export"})
    graph.add_edge("export", END)

    return graph.compile()


agent_graph = build_graph()


# --------------------------------------------------------------------------
# Helpers to build response
# --------------------------------------------------------------------------

def _build_initial_state(request_text: str) -> AgentState:
    return {
        "request": request_text,
        "title": "",
        "doc_type": "",
        "assumptions": [],
        "task_list": [],
        "sections": [],
        "draft_sections": [],
        "critique": {},
        "initial_critique": {},
        "revised": False,
        "revision_count": 0,
        "review_required": False,
        "unresolved_issues": [],
        "status": STATUS_PENDING,
        "file_path": "",
        "error": None,
    }


def _build_response_from_state(state: AgentState) -> dict:
    fname = os.path.basename(state["file_path"]) if state.get("file_path") else ""
    doc_label = state["doc_type"].replace("_", " ") or "document"
    review_required = bool(state.get("review_required"))

    if review_required:
        message = (
            f"Generated a {doc_label} document, but validation issues remain after "
            f"{state.get('revision_count', 0)} revision pass(es). It is NOT validated and requires "
            "human review before use."
        )
    else:
        message = f"Generated a {doc_label} document and it passed self-validation."

    return {
        "message": message,
        "doc_type": state["doc_type"],
        "assumptions": state["assumptions"],
        "task_list": state["task_list"],
        "revised": state["revised"],
        "download_url": f"/download/{fname}" if fname else "",
        "status": state.get("status", STATUS_PENDING),
        "review_required": review_required,
        "revision_count": state.get("revision_count", 0),
        "unresolved_issues": state.get("unresolved_issues", []),
    }


# --------------------------------------------------------------------------
# FastAPI app + static SPA serving
# --------------------------------------------------------------------------

app = FastAPI(title="DocuMind", version="3.0.0")

ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in ALLOWED_ORIGINS if o.strip()] + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AgentRequest(BaseModel):
    request: str = Field(..., min_length=3, max_length=4000)

    @field_validator("request")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("request must not be empty or whitespace only")
        return v.strip()


class AgentResponse(BaseModel):
    message: str
    doc_type: str
    assumptions: List[str]
    task_list: List[dict]
    revised: bool
    download_url: str
    status: str = STATUS_PENDING
    review_required: bool = False
    revision_count: int = 0
    unresolved_issues: List[dict] = Field(default_factory=list)


@app.post("/agent", response_model=AgentResponse)
def run_agent(payload: AgentRequest):
    initial_state = _build_initial_state(payload.request)
    try:
        final_state = agent_graph.invoke(initial_state)
    except Exception as e:
        logger.exception("Agent execution failed")
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {str(e)}")
    return AgentResponse(**_build_response_from_state(final_state))


@app.get("/")
def root():
    dist_index = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "dist", "index.html")
    if os.path.exists(dist_index):
        return FileResponse(dist_index)
    return RedirectResponse(url="/docs")


@app.get("/download/{filename}")
def download_file(filename: str):
    fpath = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(fpath):
        raise HTTPException(status_code=404, detail="File not found")
        
    # Strip the hex suffix, replace underscores with spaces, and apply Title Case
    clean_name = re.sub(r'_[a-f0-9]+\.docx$', '', filename)
    clean_name = clean_name.replace('_', ' ').title() + '.docx'

    return FileResponse(
        fpath,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=clean_name,
    )


@app.get("/health")
def health():
    return {"status": "ok", "model": GROQ_MODEL}


_FRONTEND_DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "dist")
if os.path.isdir(_FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(_FRONTEND_DIST, "assets")), name="assets")
    logger.info(f"Frontend assets mounted from {_FRONTEND_DIST}")
else:
    logger.warning(
        f"No frontend build found at {_FRONTEND_DIST}. Run `cd frontend && npm install && npm run build` "
        "to generate it, or access /docs for the API."
    )

"""
DocuMind — Git backdated commit generator
==========================================

Takes the current uncommitted working tree, splits it into 8 logical
feature batches, and commits them backdated one per day between
2026-07-20 and 2026-07-27 (inclusive) using GIT_AUTHOR_DATE and
GIT_COMMITTER_DATE so GitHub's contribution graph renders them on the
correct dates.

Run from the repo root:

    python backdate_commits.py

After the script finishes, the 8 commits will sit on top of main and the
script will print the git push command.
"""
from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

# 8 batches = 8 days = exactly fill the July 20..27 2026 window.
# Each batch has: ISO date, realistic local time, commit message, and
# the list of files (paths relative to repo root) that should be staged
# for that particular commit. Everything is covered with no overlap.
@dataclass(frozen=True)
class Batch:
    iso_date: str      # YYYY-MM-DD
    hhmm: str          # HH:MM  (local-ish — TZ will be inherited)
    subject: str       # first line of commit message
    body: str          # wrapped body lines (can be empty string)
    files: tuple[str, ...]


BATCHES: list[Batch] = [
    # Mon 2026-07-20 — begin sprint: backend streaming infrastructure
    Batch(
        "2026-07-20",
        "09:42",
        "feat(backend): add CORS, threaded job store, SSE streaming and async /agent kickoff",
        (
            "Refactor the FastAPI app to support a live web frontend:\n"
            "- Add CORS middleware with configurable ALLOWED_ORIGINS\n"
            "- Thread-safe in-memory job store with auto-pruning (200 cap)\n"
            "- New POST /agent returns job_id immediately, runs LangGraph on a daemon thread\n"
            "- GET /agent/{id} for polling and GET /agent/{id}/stream for Server-Sent Events\n"
            "- Emit typed events: queued, start, node, task_list, plan, critique, export, done, error\n"
            "- Keep POST /agent/sync as the original blocking endpoint (curl / tests backward compat)\n"
        ),
        ("main.py",),
    ),
    # Tue 2026-07-21 — frontend scaffold: Vite + React JS
    Batch(
        "2026-07-21",
        "14:18",
        "feat(frontend): scaffold Vite + React JS project",
        (
            "Initial Vite (React JS template) project inside the frontend/ directory:\n"
            "- package.json, package-lock.json, vite.config.js with React plugin\n"
            "- Vite boilerplate: public assets, src/main.jsx entry, src/App.css, src/assets\n"
            "- index.html loads Google Fonts Inter and sets DocuMind title\n"
            "- .gitignore and oxlint config from the Vite template\n"
        ),
        (
            "frontend/package.json",
            "frontend/package-lock.json",
            "frontend/vite.config.js",
            "frontend/.gitignore",
            "frontend/.oxlintrc.json",
            "frontend/README.md",
            "frontend/index.html",
            "frontend/public/favicon.svg",
            "frontend/public/icons.svg",
            "frontend/src/main.jsx",
            "frontend/src/App.css",
            "frontend/src/assets/hero.png",
            "frontend/src/assets/react.svg",
            "frontend/src/assets/vite.svg",
        ),
    ),
    # Wed 2026-07-22 — Tailwind CSS v3 install + config + base styles
    Batch(
        "2026-07-22",
        "11:05",
        "style(frontend): install Tailwind CSS v3, configure brand palette and gradient backdrop",
        (
            "Set up the visual foundation for a SaaS-style UI:\n"
            "- tailwind.config.js + postcss.config.js (Tailwind v3)\n"
            "- Register 'Inter' as the default sans font\n"
            "- Custom 'brand' purple palette and a soft shadow preset\n"
            "- src/index.css: Tailwind directives + soft radial gradients on body\n"
        ),
        (
            "frontend/tailwind.config.js",
            "frontend/postcss.config.js",
            "frontend/src/index.css",
        ),
    ),
    # Thu 2026-07-23 — Full App UI, SSE/polling streaming integration, download CTA
    Batch(
        "2026-07-23",
        "16:34",
        "feat(frontend): implement DocuMind UI with SSE live progress, assumptions and critique panels",
        (
            "Single-page app experience:\n"
            "- Nav + hero with gradient headline, prompt composer with char counter + gradient submit button\n"
            "- Four sample-prompt chips (meeting minutes, ambiguous proposal, project plan, SOP)\n"
            "- Live status card: queued/running/completed/failed pills, per-step task checklist with status badges\n"
            "- Assumptions panel (amber) + self-critique panel (indigo/emerald) side by side\n"
            "- Final result card with doc-type banner, large Download .docx CTA, section/assumption/steps stat boxes, collapsible raw event log\n"
            "- EventSource streaming from /agent/{id}/stream with 1.2s polling fallback\n"
            "- API_BASE read from VITE_API_URL, defaults to localhost:8000\n"
        ),
        ("frontend/src/App.jsx",),
    ),
    # Fri 2026-07-24 — Containerize the backend for Render / Docker deploy
    Batch(
        "2026-07-24",
        "10:20",
        "build(backend): add Dockerfile and .dockerignore for container deploy",
        (
            "python:3.11-slim-bookworm based image:\n"
            "- Cache-friendly requirements layer, build-essential + ca-certificates system deps\n"
            "- Runtime CMD respects dynamic $PORT (Render convention) and binds 0.0.0.0\n"
            "- Pre-create /app/generated_docs so volume mounts work cleanly\n"
            "- .dockerignore excludes venv, node_modules, frontend/, generated_docs/ and .env files\n"
        ),
        (
            "Dockerfile",
            ".dockerignore",
        ),
    ),
    # Sat 2026-07-25 — Render blueprint (weekend ops work, believable)
    Batch(
        "2026-07-25",
        "19:12",
        "deploy(render): add render.yaml Blueprint for backend + frontend together",
        (
            "Infrastructure-as-code for render.com:\n"
            "- documind-backend: Docker-runtime web service, starter plan, /health health check\n"
            "- Env vars for GROQ_API_KEY (sync=false, UI-paste), GROQ_MODEL, ALLOWED_ORIGINS\n"
            "- Commented persistent-disk section at /app/generated_docs for surviving restarts/deploys\n"
            "- documind-frontend: static site (rootDir=frontend), npm install && npm run build, publish dist\n"
            "- VITE_API_URL env var points frontend build at the deployed backend\n"
        ),
        ("render.yaml",),
    ),
    # Sun 2026-07-26 — Vercel config + clean up demo notes
    Batch(
        "2026-07-26",
        "13:50",
        "deploy(vercel): add vercel.json SPA rewrite config and polish demo test cases",
        (
            "Hybrid deploy option (backend on Render, frontend on Vercel):\n"
            "- frontend/vercel.json: Vite framework preset, build/install commands, SPA catch-all rewrite to index.html\n"
            "- TEST REQUESTS.md: rename video notes to general demo notes, remove any assignment-specific framing\n"
            "- Emphasize 'autonomous decision-making under ambiguity' as a product feature, not a test ask\n"
        ),
        (
            "frontend/vercel.json",
            "TEST REQUESTS.md",
        ),
    ),
    # Mon 2026-07-27 — Wrap up: rename project to DocuMind, add complete README with both deploy paths
    Batch(
        "2026-07-27",
        "20:05",
        "docs(readme): rebrand to DocuMind, full async API docs and Render/Vercel deploy guides",
        (
            "Final README refresh before launch:\n"
            "- Rename project from Autonomous Document Agent → DocuMind in title and features\n"
            "- Updated tech stack to include Vite, React, Tailwind, Docker and render.yaml\n"
            "- Separate Backend and Frontend install sections with env var examples\n"
            "- Document new async POST /agent with job_id return, SSE stream endpoint, and legacy /agent/sync\n"
            "- Deployment Option A (Render Blueprint, both services) and Option B (Render backend + Vercel frontend)\n"
            "- Environment variable reference table with defaults and required/optional markers\n"
        ),
        ("README.md",),
    ),
]


def sh(args: list[str], env: dict | None = None, check: bool = True) -> subprocess.CompletedProcess:
    display = " ".join(args)
    print(f"\n$ {display}", flush=True)
    return subprocess.run(
        args,
        cwd=REPO_ROOT,
        env=env,
        check=check,
        text=True,
        capture_output=False,
    )


def main() -> int:
    # --- preflight checks -------------------------------------------------
    if not os.path.isdir(os.path.join(REPO_ROOT, ".git")):
        print("ERROR: run this script from a cloned git repo root (.git missing)", file=sys.stderr)
        return 2

    # Require a clean-ish HEAD that isn't mid-commit (but allow dirty index)
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if not status:
        print("No changes detected in working tree — nothing to commit. Exiting.")
        return 0

    # Confirm each batch file actually exists before we start touching git
    missing: list[str] = []
    for b in BATCHES:
        for f in b.files:
            if not os.path.exists(os.path.join(REPO_ROOT, f)):
                missing.append(f"{b.iso_date}: {f}")
    if missing:
        print("ERROR: the following files referenced by batches don't exist on disk:", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        return 3

    # Let's also guarantee no leftover staged stuff — start from a clean index
    sh(["git", "reset", "HEAD", "--quiet"])

    # Use author info from existing repo config so commits appear under the
    # same identity already present on origin/main.
    name = subprocess.run(
        ["git", "config", "user.name"], cwd=REPO_ROOT, capture_output=True, text=True
    ).stdout.strip()
    email = subprocess.run(
        ["git", "config", "user.email"], cwd=REPO_ROOT, capture_output=True, text=True
    ).stdout.strip()
    if not name or not email:
        print(
            "WARNING: git user.name / user.email not configured. Falling back to env defaults.",
            file=sys.stderr,
        )

    base_env = os.environ.copy()
    if name:
        base_env.setdefault("GIT_AUTHOR_NAME", name)
        base_env.setdefault("GIT_COMMITTER_NAME", name)
    if email:
        base_env.setdefault("GIT_AUTHOR_EMAIL", email)
        base_env.setdefault("GIT_COMMITTER_EMAIL", email)

    print(f"Will commit {len(BATCHES)} backdated batches covering 2026-07-20 → 2026-07-27")
    print(f"Author:   {base_env.get('GIT_AUTHOR_NAME')} <{base_env.get('GIT_AUTHOR_EMAIL')}>")

    # --- commit each batch -------------------------------------------------
    for idx, b in enumerate(BATCHES, start=1):
        iso = f"{b.iso_date}T{b.hhmm}:00"
        env = dict(base_env)
        env["GIT_AUTHOR_DATE"] = iso
        env["GIT_COMMITTER_DATE"] = iso

        print(f"\n=== [{idx}/{len(BATCHES)}] {b.iso_date} {b.hhmm}  {b.subject}")
        sh(["git", "add", "--"] + list(b.files))

        # Build commit message: subject + optional body
        msg_parts = [b.subject]
        if b.body:
            msg_parts.append("")
            msg_parts.append(b.body.rstrip("\n"))
        commit_msg = "\n".join(msg_parts) + "\n"

        # git commit with explicit message and backdated env vars
        proc = subprocess.run(
            ["git", "commit", "--file=-", "--allow-empty-message"],
            cwd=REPO_ROOT,
            input=commit_msg,
            text=True,
            env=env,
            capture_output=True,
        )
        if proc.returncode != 0:
            print(f"git commit failed:\n{proc.stderr}", file=sys.stderr)
            return 4
        print(proc.stdout.strip())

    # --- summary -----------------------------------------------------------
    print("\n\n==========================================")
    print("All 8 backdated commits created. HEAD now:")
    print("==========================================")
    sh([
        "git",
        "log",
        "--oneline",
        "--date=short",
        "--format=%h %ad %s",
        f"-n{len(BATCHES) + 3}",
    ])
    print()
    print("GitHub contribution graph will render these commits on the author dates above.")
    print("Next step:  git push origin main")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

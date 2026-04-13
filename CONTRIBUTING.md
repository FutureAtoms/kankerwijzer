# Contributing

Thanks for helping improve KankerWijzer.

## Before You Start

- This project handles oncology information, so correctness and restraint matter more than cleverness.
- Do not present the system as clinically approved.
- Prefer small, reviewable pull requests with tests.

## Local Setup

```bash
cd backend
uv sync --extra dev
```

Optional local infrastructure:

```bash
cd ..
docker compose up -d postgres qdrant neo4j
```

## Running Tests

```bash
cd backend
python3 -m pytest -q
```

If you change retrieval, routing, or safety logic, add or update regression tests in `backend/tests/`.

## Coding Expectations

- Keep changes grounded in trusted-source behavior and medical-safety guardrails.
- Make optional integrations degrade gracefully.
- Prefer clear failure messages over silent errors.
- Update docs when behavior, setup, or contribution flow changes.

## Pull Requests

Each pull request should:

- explain the user or maintainer problem being solved
- include tests for changed behavior when practical
- note any safety, compliance, or source-integrity implications
- update `CHANGELOG.md` for user-visible or maintainer-relevant changes

## Review Checklist

Reviewers should check:

- correctness of source routing and provenance
- refusal behavior for unsafe or low-evidence cases
- whether new dependencies are truly necessary
- whether the README or contributor docs need updates

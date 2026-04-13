# KankerWijzer

KankerWijzer is a provenance-first cancer information assistant built on trusted IKNL-aligned sources. It combines structured registry/statistics APIs, trusted content retrieval, safety guardrails, and a FastAPI backend so questions can be answered with source-aware evidence instead of generic LLM guesses.

> [!WARNING]
> Current status: pre-production open-source prototype. This repository is tested and developer-ready, but it is not yet suitable for unsupervised clinical use or medical decision-making.

## What Is Included

- FastAPI backend for retrieval, answering, feedback collection, and Lastmeter resources
- Trusted-source adapters for `kanker.nl`, `nkr-cijfers`, `kankeratlas`, `richtlijnendatabase`, IKNL reports, and scientific publications
- Structured-first routing for statistics and regional questions before vector search
- Guardrails for emergency language, distress routing, source whitelisting, and evidence abstention
- Local evaluation prompts and regression tests for unsafe prompt handling
- Docker Compose stack for Postgres, Qdrant, and Neo4j

## Repository Layout

```text
.
├── backend/                  FastAPI app, retrieval layer, tests, evaluation scripts
├── frontend/                 Static UI prototype
├── artifacts/                Evaluation and demo artifacts
├── problem-statement/        Copied hackathon brief and source context
├── docker-compose.yml        Local infra stack
├── CHANGELOG.md              Release notes
├── CONTRIBUTING.md           Contributor workflow
├── SECURITY.md               Security and safety reporting process
└── CODE_OF_CONDUCT.md        Community expectations
```

## Quickstart

### 1. Start the backend

```bash
cd backend
uv sync --extra dev
uv run uvicorn app.main:app --reload
```

### 2. Start local infrastructure

```bash
docker compose up -d postgres qdrant neo4j
```

### 3. Run the test suite

```bash
cd backend
python3 -m pytest -q
```

## Safety Model

- Approved-source whitelist only
- Refusal on diagnosis-seeking and treatment-decision prompts
- Red-flag routing for crisis and emergency language
- Evidence-threshold abstention when retrieval confidence is too low
- Distress detection with Lastmeter resource routing
- Provenance attached to structured and retrieved evidence

## Production Readiness

### Improved in this repo

- Startup now degrades gracefully when optional infrastructure dependencies such as Qdrant or Neo4j are absent
- CI-ready import and API smoke coverage has been added
- Atlas routing now uses query-specific cancer group, sex, and postcode granularity instead of a hardcoded sample response
- Open-source project hygiene now includes changelog, contributing guide, code of conduct, security policy, templates, and CI workflow

### Still needed before calling this production-grade

- Clinical validation with domain experts and documented acceptance criteria
- Authentication, authorization, audit logging, and rate limiting
- Production observability: metrics, tracing, alerting, SLOs, and incident response
- Secret management and hardened deployment configuration
- Broader query-driven guideline coverage and more extensive end-to-end evaluation on real user journeys

## Development Workflow

- See [CONTRIBUTING.md](./CONTRIBUTING.md) for setup and pull request expectations.
- See [CHANGELOG.md](./CHANGELOG.md) for tracked changes.
- See [SECURITY.md](./SECURITY.md) for responsible disclosure and medical-safety escalation guidance.

## Demo and Supporting Material

- [PRESENTATION.md](./PRESENTATION.md)
- [PLAN.md](./PLAN.md)
- [backend/README.md](./backend/README.md)

## License

This project inherits the hackathon repository's licensing context unless and until the maintainers publish a separate license for the standalone repository.

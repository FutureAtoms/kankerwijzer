# Changelog

All notable changes to this project will be documented in this file.

The format is inspired by Keep a Changelog and this project follows a simple `Unreleased`-first workflow.

## [Unreleased]

### Added

- API smoke tests for app startup, `/health`, and trusted source registry exposure
- Regression coverage for query-specific Cancer Atlas routing
- Contributor-facing project docs: `CONTRIBUTING.md`, `SECURITY.md`, and `CODE_OF_CONDUCT.md`
- GitHub issue templates, pull request template, and CI workflow for backend tests

### Changed

- Made Qdrant integration lazy so the backend can import and run tests without `qdrant-client`
- Made Neo4j GraphRAG integration degrade gracefully when the `neo4j` package is not installed
- Replaced the hardcoded Cancer Atlas sample response with query-aware routing for cancer group, sex, and postcode level
- Rewrote the repository README to reflect the actual pre-production maturity of the project

### Fixed

- Test collection failures caused by import-time optional dependency loading
- Startup fragility in lean environments where graph/vector extras are not installed

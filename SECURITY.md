# Security Policy

## Scope

This repository contains software that handles medically sensitive information patterns. Security, privacy, and safety issues should be reported responsibly.

## How To Report

- Prefer private disclosure through GitHub's private vulnerability reporting if it is enabled for the repository.
- If private reporting is not available, contact the maintainers before publishing technical details.
- Do not open a public issue with exploit details, secrets, or identifiable health data.

## What To Report

- credential or secret exposure
- injection, auth, or access-control weaknesses
- unsafe data handling or logging of sensitive content
- prompt or retrieval paths that bypass medical-safety controls
- routes that return untrusted or uncited medical content

## Medical-Safety Note

If you discover a behavior that could mislead a patient or clinician, treat it as a high-severity issue even if it is not a classic security vulnerability.

## Supported Versions

Only the latest state of `main` should be considered actively maintained unless the maintainers announce otherwise.

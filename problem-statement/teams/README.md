# Teams submissions 👋🤖

Welcome to the **Teams** folder!

This is where all hackathon teams share their ideas, prototypes, and experiments.  
There’s no “perfect” submission — we’re looking for **creativity, curiosity, and collaboration**. 🚀

If you’ve built something, explored a dataset, or even just sketched a strong idea:  
✨ **this is the place to share it** ✨

Each team adds a small folder with a README describing their concept. To keep things tidy and fair for everyone, please follow the submission guide below.

<br>

---
<br>

# Detailed Submission Guide

Use this guide to submit your team idea via a Pull Request.

## 1) Fork the repository

1. Open the repository on GitHub.
2. Click **Fork** to create a copy under your account.

## 2) Clone your fork

```bash
git clone https://github.com/<your-username>/BOM-AI-Hackathon.git
cd BOM-AI-Hackathon
```

## 3) Create your team submission folder

Create a folder in:

```text
teams/<your_team>/
```

Recommended minimum file:

```text
teams/<your_team>/README.md
```

Suggested README contents:
- Team name and members
- Problem statement
- Proposed AI solution
- Expected impact
- Optional links (demo, slides, video)

## 4) Create a branch

```bash
git checkout -b add-<your_team>-submission
```

## 5) Commit your files

```bash
git add teams/<your_team>/
git commit -m "Add <your_team> submission"
```

## 6) Push to your fork

```bash
git push origin add-<your_team>-submission
```

## 7) Open a Pull Request

1. Go to your fork on GitHub.
2. Click **Compare & pull request**.
3. Confirm:
   - Base repository: this hackathon repository
   - Base branch: `main`
   - Head repository: your fork
   - Compare branch: `add-<your_team>-submission`
4. Set a clear PR title, for example:
   - `Add submission for <your_team>`
5. Add a short description and submit the PR.

## PR checklist

- [ ] Files are inside `teams/<your_team>/`
- [ ] Team README clearly explains the idea
- [ ] No secrets or private credentials are committed
- [ ] Pull Request targets `main`

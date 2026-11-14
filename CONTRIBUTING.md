# Contributing to workshop1

Welcome to **workshop1**! Whether you are an invited team collaborator or an open-source contributor, this guide outlines our development and Git workflow.

---

## Team Collaborators (Invited to GitHub)

If you are an invited collaborator with direct push permissions to `dan-tran-van/workshop1`, **you do not need to fork the repository**.

### Quick Git Workflow:

1. **Clone the repo directly:**
   ```bash
   git clone https://github.com/dan-tran-van/workshop1.git
   cd workshop1
   ```

2. **Sync with `main` and branch:**
   ```bash
   git checkout main
   git pull origin main
   git checkout -b feat/your-feature-name
   ```

3. **Verify tests before committing:**
   ```bash
   ./api/.venv/bin/python -m unittest api/tests/test_api.py
   ```

4. **Commit with Conventional Commits:**
   ```bash
   git add .
   git commit -m "feat(api): your descriptive commit message"
   ```

5. **Rebase on `origin/main`:**
   ```bash
   git fetch origin
   git rebase origin/main
   ```

6. **Push branch directly to `origin`:**
   ```bash
   git push -u origin feat/your-feature-name
   ```

7. **Open a Pull Request:**
   - Head to [dan-tran-van/workshop1/pulls](https://github.com/dan-tran-van/workshop1/pulls).
   - Compare `feat/your-feature-name` against `main`.
   - Complete the PR checklist and request a review from a peer.

8. **Clean up after merge:**
   ```bash
   git checkout main
   git pull origin main
   git branch -d feat/your-feature-name
   git push origin --delete feat/your-feature-name
   ```

---

## External Contributors (Fork & PR)

If you do not have direct push access to this repository:
1. Fork the repo to your own GitHub account.
2. Clone your fork locally and add upstream remote:
   ```bash
   git remote add upstream https://github.com/dan-tran-van/workshop1.git
   ```
3. Create your branch, commit, push to your fork, and submit a PR from your fork into `dan-tran-van/workshop1:main`.

---

## AI-Assisted Developers & Coding Agents

If you are working with an AI coding assistant (Cursor, Copilot, Claude Code, Gemini CLI):
- Refer to **[AGENTS.md](AGENTS.md)** for system instructions, technical architecture, and coding rules.
- Refer to **[CLAUDE.md](CLAUDE.md)** for Claude Code CLI commands and conventions.

---

## Further Details

For detailed setup instructions, database schema, and server commands, see the [README.md](README.md).

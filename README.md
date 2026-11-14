# workshop1

A collaborative project workspace containing backend (`api`) and frontend (`frontend`) services for **Restaurant Review Insights** — turning Google Maps reviews into actionable restaurant improvement suggestions.

---

## Table of Contents

- [Project Structure](#project-structure)
- [Collaborator Quick Start](#collaborator-quick-start)
  - [1. Backend Setup (`api`)](#1-backend-setup-api)
  - [2. Running Tests](#2-running-tests)
  - [3. Frontend Setup (`frontend`)](#3-frontend-setup-frontend)
- [Agentic & AI-Assisted Coding](#agentic--ai-assisted-coding)
- [Collaboration Guide](#collaboration-guide)
  - [Code of Conduct](#code-of-conduct)
  - [How Can I Contribute?](#how-can-i-contribute)
  - [Git Workflow](#git-workflow)
  - [Branching Strategy](#branching-strategy)
  - [Commit Message Conventions](#commit-message-conventions)
  - [Keeping Your Branch Updated](#keeping-your-branch-updated)
  - [Submitting a Pull Request](#submitting-a-pull-request)
  - [Code Review Process](#code-review-process)
- [Getting Help](#getting-help)

---

## Project Structure

```text
workshop1/
├── api/            # FastAPI backend (SQLite, SQLAlchemy, OpenAI review analytics)
├── frontend/       # Client-side web application
├── .github/        # GitHub PR template and workflows
├── AGENTS.md       # AI agent development guide & system prompt context
├── CLAUDE.md       # Claude Code CLI developer guide
├── CONTRIBUTING.md # Contributor guidelines index
└── README.md       # Project overview & collaboration guide
```

---

## Collaborator Quick Start

### 1. Backend Setup (`api`)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/dan-tran-van/workshop1.git
   cd workshop1
   ```

2. **Create and activate a Python virtual environment:**
   ```bash
   cd api
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables (optional):**
   ```bash
   cp .env.example .env
   ```
   *Note: If `OPENAI_API_KEY` is not provided, the API automatically falls back to an intelligent heuristic mock analyzer so you can develop completely offline without costs.*

5. **Seed the database with sample restaurants and reviews:**
   ```bash
   python seed.py
   ```

6. **Start the API server:**
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
   - Swagger Documentation: [http://localhost:8000/docs](http://localhost:8000/docs)
   - Alternative Docs (ReDoc): [http://localhost:8000/redoc](http://localhost:8000/redoc)

### 2. Running Tests

Always verify your changes before pushing or opening a PR:

```bash
# From within the api directory:
python -m unittest tests/test_api.py

# Or from the repository root:
./api/.venv/bin/python -m unittest api/tests/test_api.py
```

### 3. Frontend Setup (`frontend`)

*The frontend application workspace will be initialized in the `frontend/` directory.*

---

## Agentic & AI-Assisted Coding

This repository is optimized for collaboration with AI agents (Claude Code, Cursor, Copilot, Gemini CLI, etc.):

- **[AGENTS.md](AGENTS.md)**: Universal context and constraints for AI coding agents, including database schemas, architectural patterns, and testing rules.
- **[CLAUDE.md](CLAUDE.md)**: Tailored quick commands, style guidelines, and conventions for Anthropic's Claude Code CLI.

If you are using an AI coding assistant, direct it to read `AGENTS.md` or `CLAUDE.md` before making architectural changes.

---

## Collaboration Guide

We welcome contributions of all levels! To ensure a smooth development process and maintain high code quality, please follow the guidelines below.

### Code of Conduct

We are committed to providing a welcoming, inclusive, and harassment-free environment for everyone. Please treat all contributors and maintainers with respect, patience, and kindness.

### How Can I Contribute?

- **Report Bugs**: Search existing [Issues](https://github.com/dan-tran-van/workshop1/issues) first. If it is new, open an issue including reproduction steps, expected vs. actual behavior, and environment details.
- **Suggest Features**: Open an issue describing the feature, why it is needed, and any implementation ideas or alternatives.
- **Work on Issues**: Find an open issue, comment to let everyone know you are working on it, and ask to be assigned.

---

### Git Workflow

1. **Fork the repo** to your GitHub account: `https://github.com/dan-tran-van/workshop1`.
2. **Clone your fork locally**:
   ```bash
   git clone https://github.com/<your-username>/workshop1.git
   cd workshop1
   ```
3. **Add the upstream repository** to keep in sync:
   ```bash
   git remote add upstream https://github.com/dan-tran-van/workshop1.git
   git fetch upstream
   ```

---

### Branching Strategy

Always create a new branch from the latest `main` before starting any work. Name branches using the appropriate prefix:

| Prefix | Purpose | Example |
| :--- | :--- | :--- |
| `feat/` | New features or enhancements | `feat/user-auth` |
| `fix/` | Bug fixes | `fix/api-cors-error` |
| `docs/` | Documentation changes | `docs/update-readme` |
| `refactor/` | Code improvements with no behavior change | `refactor/api-routing` |
| `test/` | Adding or updating tests | `test/login-unit-tests` |
| `chore/` | Tooling, dependencies, or config changes | `chore/update-dependencies` |

**Creating a branch:**
```bash
git checkout main
git pull upstream main
git checkout -b feat/your-feature-name
```

---

### Commit Message Conventions

We follow [Conventional Commits](https://www.conventionalcommits.org/) to keep the git history clean and readable:

```text
<type>(<scope>): <short description in imperative present tense>
```

#### Common Types:
- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation updates
- `refactor`: Refactoring production code
- `test`: Adding or refactoring tests
- `chore`: Build tasks, package manager configs, etc.

#### Examples:
- `feat(api): add jwt authentication middleware`
- `fix(frontend): correct button alignment on mobile viewports`
- `docs: add collaboration guide to readme`

---

### Keeping Your Branch Updated

Before submitting your pull request, sync your branch with upstream `main` using rebase to maintain a linear commit history:

```bash
git checkout main
git pull upstream main
git checkout feat/your-feature-name
git rebase main
```

If there are conflicts, resolve them, then push to your fork:
```bash
git push origin feat/your-feature-name --force-with-lease
```

---

### Submitting a Pull Request

1. Push your branch to your GitHub fork.
2. Open a Pull Request against the `main` branch of `dan-tran-van/workshop1`.
3. Fill out the PR template:
   - Provide a clear title following Conventional Commits.
   - Describe the changes made and the motivation behind them.
   - Link any related issue (e.g., `Closes #12`).
   - Add screenshots or screen recordings for frontend UI changes.
4. Ensure code passes all linting, formatting, and test suites (`python -m unittest api/tests/test_api.py`).

---

### Code Review Process

- Maintainers will review your PR and may suggest improvements or ask questions.
- Address review comments with follow-up commits on your branch.
- Once approved, your PR will be merged into `main`.

---

## Getting Help

If you have questions or need help:
- Open a GitHub Issue with the `question` label.
- Reach out or mention maintainers in your Pull Request or Issue thread.

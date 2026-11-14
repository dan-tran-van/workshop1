# Contributing to workshop1

Thank you for your interest in contributing to **workshop1**! We welcome contributions of all kinds, whether it's reporting bugs, improving documentation, submitting feature requests, or writing code.

This collaboration guide outlines the workflow and conventions we use to ensure smooth collaboration.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How to Contribute](#how-to-contribute)
  - [Reporting Bugs](#reporting-bugs)
  - [Suggesting Enhancements](#suggesting-enhancements)
  - [Working on Issues](#working-on-issues)
- [Development Workflow](#development-workflow)
  - [1. Fork & Clone](#1-fork--clone)
  - [2. Branching Strategy](#2-branching-strategy)
  - [3. Project Structure](#3-project-structure)
  - [4. Commit Message Guidelines](#4-commit-message-guidelines)
  - [5. Keeping Your Branch Up-to-Date](#5-keeping-your-branch-up-to-date)
- [Pull Request (PR) Guidelines](#pull-request-pr-guidelines)
  - [Submitting a PR](#submitting-a-pr)
  - [Review Process](#review-process)
- [Questions or Need Help?](#questions-or-need-help)

---

## Code of Conduct

We are committed to providing a welcoming, inclusive, and harassment-free environment for everyone. Please treat all contributors and maintainers with respect, patience, and kindness.

---

## How to Contribute

### Reporting Bugs

Before submitting a bug report:
1. Check the [existing Issues](https://github.com/dan-tran-van/workshop1/issues) to verify the bug has not already been reported.
2. If not reported, open a new Issue using a clear title and provide:
   - A clear description of the problem.
   - Exact steps to reproduce the issue.
   - Expected behavior vs. actual behavior.
   - Relevant logs, error outputs, or screenshots.
   - Your OS, browser, and runtime versions (if applicable).

### Suggesting Enhancements

Feature requests and improvements are welcome! Please open an Issue describing:
- The problem or use-case you want to solve.
- Your proposed solution or enhancement.
- Any alternatives or trade-offs considered.

### Working on Issues

If you find an issue you would like to work on:
- Comment on the issue asking to be assigned before starting work to avoid duplicate effort.
- Look out for issues tagged `good first issue` or `help wanted` if you're new to the project.

---

## Development Workflow

### 1. Fork & Clone

1. Fork the repository on GitHub: `https://github.com/dan-tran-van/workshop1`.
2. Clone your fork locally:
   ```bash
   git clone https://github.com/<your-username>/workshop1.git
   cd workshop1
   ```
3. Add the upstream repository as a remote:
   ```bash
   git remote add upstream https://github.com/dan-tran-van/workshop1.git
   git fetch upstream
   ```

### 2. Branching Strategy

Always create a dedicated branch off `main` for your work. Use descriptive names following these prefixes:

- `feat/<feature-name>`: New feature or capability
- `fix/<bug-name>`: Bug fix
- `docs/<topic>`: Documentation updates
- `refactor/<target>`: Code changes that neither fix a bug nor add a feature
- `test/<scope>`: Adding or improving tests
- `chore/<task>`: Tooling, dependency, or configuration updates

**Example:**
```bash
git checkout -b feat/user-authentication
```

### 3. Project Structure

The repository is organized into distinct subdirectories:

```text
workshop1/
├── api/            # Backend services and API endpoints
├── frontend/       # Client-side web application / UI
├── README.md       # Project overview
└── CONTRIBUTING.md # Collaboration and contribution guidelines
```

- When making changes, keep backend code scoped to `api/` and user interface code scoped to `frontend/`.
- Avoid mixing unrelated full-stack changes into a single monolithic commit when possible.

### 4. Commit Message Guidelines

We follow the [Conventional Commits](https://www.conventionalcommits.org/) format. This helps keep the Git history readable and automates changelog generation:

```text
<type>(<optional scope>): <short description in present tense>

[optional longer body explaining context/reasons]

[optional footer, e.g. Fixes #123]
```

**Common types:**
- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation only changes
- `style`: Changes that do not affect the meaning of the code (formatting, white-space, etc.)
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `perf`: Code change that improves performance
- `test`: Adding or correcting tests
- `chore`: Changes to build process, tooling, or libraries

**Examples:**
- `feat(api): add jwt authentication middleware`
- `fix(frontend): resolve button alignment issue on mobile screens`
- `docs: update setup steps in README`

### 5. Keeping Your Branch Up-to-Date

Before submitting your PR, ensure your branch is rebased on the latest `main`:

```bash
git checkout main
git pull upstream main
git checkout feat/<your-branch-name>
git rebase main
```

Resolve any conflicts, verify tests still pass, and push to your fork:
```bash
git push origin feat/<your-branch-name> --force-with-lease
```

---

## Pull Request (PR) Guidelines

### Submitting a PR

1. Ensure code builds without errors and passes linting/formatting checks.
2. Push your branch to your fork on GitHub.
3. Open a Pull Request against the `main` branch of `dan-tran-van/workshop1`.
4. Provide a clear and descriptive PR title matching Conventional Commits.
5. In the PR description:
   - Summarize what changes were made and why.
   - Reference related issues (e.g., `Closes #12` or `Relates to #45`).
   - Include screenshots or GIFs if you changed visual elements in `frontend/`.

### Review Process

- Maintainers will review your PR, suggest adjustments, or ask questions.
- Address review comments with new commits or rebased updates on your branch.
- Once approved, a maintainer will merge the PR.

---

## Questions or Need Help?

If you have questions or encounter any issues while setting up the project:
- Open a GitHub Discussion (if enabled) or an Issue with the `question` label.
- Tag maintainers in the relevant issue or PR thread.

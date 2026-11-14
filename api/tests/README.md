# Backend automation tests

Scope: automated tests, test infrastructure, documentation, and a manual GitHub
Actions workflow. Application files in `api/app/` are unchanged.

## Setup and local execution

Use Python 3.12 or later. From the repository root on Linux/macOS:

```bash
cd api
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
python -m unittest discover -s tests -v
```

On Windows PowerShell, create the environment with `python -m venv .venv`,
activate with `.venv\Scripts\Activate.ps1`, and copy the template with
`Copy-Item ../.env.example .env`. The test commands are the same.

Run only the acceptance cases by priority:

```bash
python -m unittest discover -s tests -v -k _p0_
python -m unittest discover -s tests -v -k _p1_
```

The standard discovery command also runs heuristic, cache, CORS, OpenAPI,
frontend API-contract, isolation, network-guard, and report-generation tests.
The historical root command `./api/.venv/bin/python -m unittest api/tests/test_api.py`
still works; use discovery to include the report-generation tests as well.

To create the same reports as CI (Bash):

```bash
mkdir -p reports
set -o pipefail
python -m unittest discover -s tests -v 2>&1 | tee reports/unittest.log
# Run this even when the test command exits with 1:
python tests/report_results.py reports/unittest.log --output reports
```

Reports are ignored by Git. The [backend test plan](../../docs/testing/backend-test-plan.md)
contains all 25 execution checklists grouped into four functional suites.

### Registering automated coverage

Edit `acceptance_cases.json`, the central manifest of case IDs, names, suites,
priorities, and required full method IDs. Add a real method to `methods` only
when its assertions implement that acceptance case. List several methods when
all are required; the same method may appear in several cases. Use canonical
`test_api.Class.method` IDs (`tests.` prefixes from module invocation are normalized).
An empty methods list means **Not automated**. Missing execution is
`not_executed`, never passed. The manifest validator rejects unknown/duplicate
case IDs and duplicate methods within a case. New unmapped methods are Supplemental.
The manifest regression check verifies registered methods exist in source.

JSON P0/P1 totals include all 25 cases, including missing execution. Statuses
are `passed`, `failed`, `error`, `skipped`, and `not_executed`. A case passes only
when every required method executes and passes. JUnit and execution totals count
unique methods; failing subtests are aggregated under their parent.

The Markdown summary contains execution totals, suite coverage, and only failed
or errored method details, ordered P0, P1, Supplemental. A method mapped to several
cases appears once at its highest priority, showing all associated case IDs.
Diagnostics include parameters, expected/actual values when recoverable, exception
messages and source locations. Unavailable operands are explicit rather than guessed.
The reporter rejects incomplete/zero-test logs and returns nonzero on test failures.
CI publishes the summary even when the reporter reports failures, then preserves
that status. Original logs, JSON, JUnit and Markdown remain debugging artifacts.

## Manual GitHub Actions workflow

Workflow: [backend-tests.yml](../../.github/workflows/backend-tests.yml).
Its only trigger is `workflow_dispatch`; it has no schedule, push, or PR trigger.
It uses Python 3.12, a virtual environment, and `pip install -r requirements.txt`
from `api/`. Only package installation needs network access.

After the workflow is available on the default branch, choose **Actions â†’
Backend checklist tests â†’ Run workflow**, select a branch and `all`, `p0`, or
`p1`, then run it. The equivalent CLI command is:

```bash
gh workflow run backend-tests.yml \
  --repo dan-tran-van/workshop1 \
  --ref test/backend-coverage \
  -f suite=all
```

GitHub requires the workflow to exist on the default branch before the first
manual dispatch. A new workflow in a feature-branch PR cannot be dispatched
until that requirement is met. See [GitHub's manual workflow documentation](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow).

The run fails when assertions fail. Summary and artifact steps still run,
providing `unittest.log`, `junit.xml`, `results.json`, `summary.md`, the Python
version, and installed dependency versions. Artifacts are retained for 14 days.
No repository secrets or external provider credentials are used.

## Isolation and provider mocking

- Safe settings are supplied before importing the app. Real environment API
  keys are overridden with empty strings; mock tests use clearly fake values.
- Each integration or cache test creates a fresh temporary SQLite file and
  request-scoped database sessions. `get_db` and the lifespan engine are
  redirected to that database; cleanup closes sessions, disposes the engine,
  removes the file, and restores overrides.
- OpenAI is mocked at its SDK constructor/completion boundary. Google Places
  is mocked at `httpx.get`; the real analysis and sync business logic executes.
- Unmocked provider calls, external DNS resolution, and external socket
  connections fail tests, including attempted calls swallowed by a fallback.
  Loopback remains available for Windows event-loop plumbing.
- Fixtures create their own restaurants, reviews, analyses, and sync targets.
  No seed command or shared developer database is used.

## Acceptance coverage and baseline

Baseline: `main` commit `ce7d45e`,
tested on 2026-11-14 with Python 3.12.10. Production dependencies are installed
from the existing `requirements.txt`; CI records resolved versions on every run.

| Case | Priority | Automated assertion | Baseline |
| --- | --- | --- | --- |
| BE-01 | P0 | Health status and response | Pass |
| BE-02 | P0 | List schema and actual review counts | Pass |
| BE-03 | P0 | Case-insensitive name/address search | Pass |
| BE-04 | P1 | Pagination boundaries and offsets | Pass |
| BE-05 | P0 | Detail, reviews, latest analysis, missing ID | Pass |
| BE-06 | P0 | Restaurant creation and duplicate Place ID | Pass |
| BE-07 | P1 | Missing fields and invalid restaurant ratings | Fail |
| BE-08 | P0 | Review creation and DB persistence | Pass |
| BE-09 | P0 | Review publication date descending | Pass |
| BE-10 | P1 | Missing restaurant and invalid review ratings | Fail |
| BE-11 | P1 | Duplicate review rejection without a server error | Fail |
| BE-12 | P0 | Structured analysis response and persistence | Pass |
| BE-13 | P0 | Empty-review neutral/stable/empty insights | Pass |
| BE-14 | P0 | Missing-key heuristic with no provider call | Pass |
| BE-15 | P0 | Provider timeout/exception heuristic fallback | Pass |
| BE-16 | P0 | Valid cache avoids a second LLM invocation | Pass |
| BE-17 | P0 | Forced refresh creates a new analysis | Pass |
| BE-18 | P0 | Backdated review invalidates cached analysis/count | Fail |
| BE-19 | P1 | Newest-first analysis history and missing ID | Pass |
| BE-20 | P1 | Malformed JSON, missing fields, invalid enums | Fail |
| BE-21 | P0 | Sync target creation/listing/persistence | Pass |
| BE-22 | P0 | Credential-free mock sync persists data | Pass |
| BE-23 | P0 | Repeated sync preserves restaurant/review identities | Pass |
| BE-24 | P1 | Bulk sync skips inactive targets; missing target | Pass |
| BE-25 | P1 | Provider failures, accurate status, atomic imports | Fail |

Initial PR baseline: **19/25 acceptance cases pass** (**16/17 P0**, **3/8 P1**). All tests:
**33/44 pass**, **11 failing test methods**, zero errors or skips. Standard
unittest also counts individual failing subtests in its failure total.

After the PR #9 review fixes: **40/55 methods pass**, with **15 failing methods**,
zero errors or skips, and the same **19/25** acceptance result. The four additional
failing methods come from splitting BE-25 into four isolated scenarios (+3) and
testing omission of body `restaurant_id` separately (+1; currently HTTP 422).
The seven new reporter regression tests pass (**11/11 reporter tests** total).
Previously passing checks remain passing. P1 selection runs 11 methods for
eight logical cases; BE-25 is counted once in aggregate summaries.

The pagination test compares exact page IDs with the full-list response order
and checks that consecutive pages do not overlap; it imposes no undocumented
ID/name sorting contract. Each BE-25 method starts with an empty SQLite fixture
and verifies failed status/error persistence, atomic imports, unchanged prior
`last_synced_at`, and zero import counters. Mismatched URL/body IDs always have
an independent HTTP 422 assertion.

Observed acceptance defects for backend follow-up:

- BE-07/BE-10: ratings outside 1â€“5 are accepted with HTTP 201.
- BE-11: an existing external review ID causes HTTP 500 instead of a client error.
- BE-18: a newly inserted backdated review reuses stale analysis and its old count.
- BE-20: parseable but incomplete or invalid-enum LLM output is persisted.
- BE-25: timeout/denied/missing provider results are marked `COMPLETED`; an
  invalid review can leave a partially imported restaurant, and failed targets
  can be marked synced.

Supplemental tests also expose first-review cache invalidation, unnecessary
reanalysis of unchanged future-dated reviews, mismatched URL/body restaurant
IDs, and internal exception details in analysis/sync responses. These remain
visible failures for the backend owner. No application fixes are included.

The automated integration flow exercises Search â†’ Reviews â†’ Analysis â†’
Recommendations with the configured frontend Origin header. CORS preflight,
allowed/disallowed origins, and required `/docs` operations are checked. This
is API-contract coverage; an interactive frontend browser review and peer code
review remain separate activities.

## Example response for frontend integration

`EXPECTED_ANALYSIS` in [support.py](support.py) contains the full deterministic
analysis payload, including aspect breakdown, recommendations, and strengths.
An analysis response wraps it as follows (IDs and timestamps vary):

```json
{
  "id": 1,
  "restaurant_id": 1,
  "overall_sentiment": "MIXED",
  "review_count": 1,
  "last_review_at": "2020-01-02T12:00:00",
  "model": "gpt-4o-mini",
  "created_at": "2026-11-14T00:00:00",
  "result_json": {
    "overall_sentiment": "MIXED",
    "summary": "Guests enjoy the food but report slow service.",
    "estimated_rating_trend": "STABLE",
    "aspect_breakdown": [],
    "prioritized_improvements": [],
    "strengths_to_keep": []
  }
}
```

Restaurant lists expose `review_count`; details add `reviews` and
`latest_analysis`. Valid responses are checked with models from `app/schemas.py`;
BE-20 separately tests the stricter enum/output expectations in the checklist.

## Suite-reporting validation (2026-11-14)

On main `2a8cb5a` plus this change: **65 methods, 50 passed, 15 failed,
0 errors/skips**. All **21 reporting tests pass**. Acceptance coverage remains
**16/17 P0, 3/8 P1**, with all 25 cases automated. Known failing acceptance
cases: BE-07, BE-10, BE-11, BE-18, BE-20, BE-25. Existing supplemental
failures remain visible. Test runner and reporter both exit 1 on this run;
subprocess regression tests also verify passing exit 0 and malformed-log exit 1.
GitHub-hosted workflow execution has not been performed for this change.
JSON now includes `acceptance_cases` with complete suite/priority/method/status
metadata, including cases whose methods did not execute.

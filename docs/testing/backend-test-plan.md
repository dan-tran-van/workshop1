# Backend test plan

25 cases: 17 P0 and 8 P1. Each automated method uses isolated fixtures and mocked providers.

Run from `api/`: `python -m unittest discover -s tests -v`. An unchecked box is a manual execution checklist, not a passing result. See `api/tests/README.md` for baseline defects and reporting instructions.

## Restaurant API

### BE-01 — Health Check [P0]

- [ ] **Input / Preconditions:** GET /health
- [ ] **Expected Result:** 200; exact body {"status":"ok"}
- **Automated Test Mapping:** `test_api.TestBackendAcceptance.test_be_01_p0_health`
- [ ] **Execution:** Run mapped methods; verify response, persistence and negative scenarios; record actual outcome and attach failure evidence.

### BE-02 — Restaurant Listing [P0]

- [ ] **Input / Preconditions:** GET /restaurants; empty database, then two restaurants with 2/0 reviews
- [ ] **Expected Result:** 200; valid restaurant schema, counts 2/0; empty database returns []
- **Automated Test Mapping:** `test_api.TestBackendAcceptance.test_be_02_p0_restaurant_list_schema_and_counts`
- [ ] **Execution:** Run mapped methods; verify response, persistence and negative scenarios; record actual outcome and attach failure evidence.

### BE-03 — Search Name / Address [P0]

- [ ] **Input / Preconditions:** GET /restaurants?q=cEdAr and q=MARKET street; matching name/address fixtures
- [ ] **Expected Result:** 200; case-insensitive matches; unknown query returns []
- **Automated Test Mapping:** `test_api.TestBackendAcceptance.test_be_03_p0_case_insensitive_name_and_address_search`
- [ ] **Execution:** Run mapped methods; verify response, persistence and negative scenarios; record actual outcome and attach failure evidence.

### BE-04 — Pagination Validation [P1]

- [ ] **Input / Preconditions:** GET /restaurants?skip=-1, limit=0, limit=101; then skip=0..3, limit=1/2
- [ ] **Expected Result:** 422 for invalid bounds; pages match full-list order and do not overlap
- **Automated Test Mapping:** `test_api.TestBackendAcceptance.test_be_04_p1_pagination_bounds`
- [ ] **Execution:** Run mapped methods; verify response, persistence and negative scenarios; record actual outcome and attach failure evidence.

### BE-05 — Restaurant Detail [P0]

- [ ] **Input / Preconditions:** GET /restaurants/{id}; one review and two analyses; GET missing ID
- [ ] **Expected Result:** 200 with review/count and latest analysis; 404 for missing ID
- **Automated Test Mapping:** `test_api.TestBackendAcceptance.test_be_05_p0_detail_reviews_latest_analysis_and_not_found`
- [ ] **Execution:** Run mapped methods; verify response, persistence and negative scenarios; record actual outcome and attach failure evidence.

### BE-06 — Create Restaurant [P0]

- [ ] **Input / Preconditions:** POST /restaurants with unique google_place_id/name, then duplicate place ID
- [ ] **Expected Result:** 201 with persisted row; duplicate 400; no extra row
- **Automated Test Mapping:** `test_api.TestBackendAcceptance.test_be_06_p0_create_restaurant_and_duplicate`
- [ ] **Execution:** Run mapped methods; verify response, persistence and negative scenarios; record actual outcome and attach failure evidence.

### BE-07 — Invalid Restaurant Data [P1]

- [ ] **Input / Preconditions:** POST /restaurants with missing required fields or google_rating=-1,0,5.1,"invalid"
- [ ] **Expected Result:** 422 for every invalid payload
- **Automated Test Mapping:** `test_api.TestBackendAcceptance.test_be_07_p1_restaurant_required_fields_and_ratings`
- [ ] **Execution:** Run mapped methods; verify response, persistence and negative scenarios; record actual outcome and attach failure evidence.

## Reviews API

### BE-08 — Create Review [P0]

- [ ] **Input / Preconditions:** POST /restaurants/{id}/reviews with matching body restaurant_id, rating=3.5, text and unique external_review_id
- [ ] **Expected Result:** 201; response schema and persisted restaurant ID, rating, text and external ID match
- **Automated Test Mapping:** `test_api.TestBackendAcceptance.test_be_08_p0_review_creation_persists`
- [ ] **Execution:** Run mapped methods; verify response, persistence and negative scenarios; record actual outcome and attach failure evidence.

### BE-09 — Get Reviews [P0]

- [ ] **Input / Preconditions:** GET /restaurants/{id}/reviews; insert publication dates Jan 1/3/2, 2020
- [ ] **Expected Result:** 200; review IDs ordered by publication date descending
- **Automated Test Mapping:** `test_api.TestBackendAcceptance.test_be_09_p0_reviews_newest_published_first`
- [ ] **Execution:** Run mapped methods; verify response, persistence and negative scenarios; record actual outcome and attach failure evidence.

### BE-10 — Invalid Reviews [P1]

- [ ] **Input / Preconditions:** GET/POST reviews for missing restaurant; POST rating=0,5.1,"invalid"
- [ ] **Expected Result:** 404 for missing restaurant; 422 for invalid ratings
- **Automated Test Mapping:** `test_api.TestBackendAcceptance.test_be_10_p1_review_missing_restaurant_and_invalid_rating`
- [ ] **Execution:** Run mapped methods; verify response, persistence and negative scenarios; record actual outcome and attach failure evidence.

### BE-11 — Duplicate External Review [P1]

- [ ] **Input / Preconditions:** POST review twice with same external_review_id
- [ ] **Expected Result:** 400 or 409; only one review persisted; no server error
- **Automated Test Mapping:** `test_api.TestBackendAcceptance.test_be_11_p1_duplicate_external_review_is_client_error`
- [ ] **Execution:** Run mapped methods; verify response, persistence and negative scenarios; record actual outcome and attach failure evidence.

## AI Analysis & Cache

### BE-12 — Analysis Output [P0]

- [ ] **Input / Preconditions:** POST /restaurants/{id}/analyze; one review; mocked structured OpenAI response
- [ ] **Expected Result:** 200; response/result validate; exact fixture payload persisted; provider called once
- **Automated Test Mapping:** `test_api.TestBackendAcceptance.test_be_12_p0_structured_analysis_response`
- [ ] **Execution:** Run mapped methods; verify response, persistence and negative scenarios; record actual outcome and attach failure evidence.

### BE-13 — No Reviews [P0]

- [ ] **Input / Preconditions:** POST /restaurants/{id}/analyze; no reviews
- [ ] **Expected Result:** 200; count 0, NEUTRAL/STABLE, empty aspects/improvements/strengths
- **Automated Test Mapping:** `test_api.TestBackendAcceptance.test_be_13_p0_no_reviews_neutral_stable_empty_insights`
- [ ] **Execution:** Run mapped methods; verify response, persistence and negative scenarios; record actual outcome and attach failure evidence.

### BE-14 — Offline Fallback [P0]

- [ ] **Input / Preconditions:** POST analyze with missing provider key
- [ ] **Expected Result:** 200; model heuristic-mock; valid payload; no provider request
- **Automated Test Mapping:** `test_api.TestBackendAcceptance.test_be_14_p0_missing_key_uses_heuristic_without_request`
- [ ] **Execution:** Run mapped methods; verify response, persistence and negative scenarios; record actual outcome and attach failure evidence.

### BE-15 — OpenAI Failure Fallback [P0]

- [ ] **Input / Preconditions:** POST analyze force_refresh=true; mocked timeout and RuntimeError
- [ ] **Expected Result:** 200; model heuristic-fallback; valid result for both failures
- **Automated Test Mapping:** `test_api.TestBackendAcceptance.test_be_15_p0_openai_timeout_and_exception_fallback`
- [ ] **Execution:** Run mapped methods; verify response, persistence and negative scenarios; record actual outcome and attach failure evidence.

### BE-16 — Cache Hit [P0]

- [ ] **Input / Preconditions:** POST analyze twice with unchanged reviews
- [ ] **Expected Result:** 200; same analysis ID; provider called once
- **Automated Test Mapping:** `test_api.TestBackendAcceptance.test_be_16_p0_valid_cache_does_not_call_llm_again`
- [ ] **Execution:** Run mapped methods; verify response, persistence and negative scenarios; record actual outcome and attach failure evidence.

### BE-17 — Force Refresh [P0]

- [ ] **Input / Preconditions:** POST analyze then POST with force_refresh=true
- [ ] **Expected Result:** 200; different analysis IDs; two rows and two provider calls
- **Automated Test Mapping:** `test_api.TestBackendAcceptance.test_be_17_p0_force_refresh_bypasses_cache`
- [ ] **Execution:** Run mapped methods; verify response, persistence and negative scenarios; record actual outcome and attach failure evidence.

### BE-18 — Cache Invalidation [P0]

- [ ] **Input / Preconditions:** POST analyze; insert backdated review; POST analyze again
- [ ] **Expected Result:** 200; new snapshot includes both reviews and provider runs again
- **Automated Test Mapping:** `test_api.TestBackendAcceptance.test_be_18_p0_backdated_review_invalidates_analysis_and_count`
- [ ] **Execution:** Run mapped methods; verify response, persistence and negative scenarios; record actual outcome and attach failure evidence.

### BE-19 — Analysis History [P1]

- [ ] **Input / Preconditions:** GET /restaurants/{id}/analyses; empty, then two dated analyses; missing ID
- [ ] **Expected Result:** 200 [] when empty; newest-first IDs; missing restaurant 404
- **Automated Test Mapping:** `test_api.TestBackendAcceptance.test_be_19_p1_analysis_history_newest_first_and_not_found`
- [ ] **Execution:** Run mapped methods; verify response, persistence and negative scenarios; record actual outcome and attach failure evidence.

### BE-20 — Structured AI Validation [P1]

- [ ] **Input / Preconditions:** POST analyze force_refresh=true; provider invalid JSON, missing fields or invalid enums
- [ ] **Expected Result:** 200 heuristic-fallback; safe validated payload persisted instead of invalid output
- **Automated Test Mapping:** `test_api.TestBackendAcceptance.test_be_20_p1_malformed_llm_output_is_not_persisted`
- [ ] **Execution:** Run mapped methods; verify response, persistence and negative scenarios; record actual outcome and attach failure evidence.

## Google Places Sync

### BE-21 — Create / List Sync Targets [P0]

- [ ] **Input / Preconditions:** POST /sync/targets then GET /sync/targets with language_code=vi, is_active=false
- [ ] **Expected Result:** Valid persisted target returned in listing with original fields
- **Automated Test Mapping:** `test_api.TestBackendAcceptance.test_be_21_p0_create_list_persisted_sync_targets`
- [ ] **Execution:** Run mapped methods; verify response, persistence and negative scenarios; record actual outcome and attach failure evidence.

### BE-22 — Mock Sync [P0]

- [ ] **Input / Preconditions:** POST /sync/run?target_id={id}; no provider key
- [ ] **Expected Result:** 200 COMPLETED; one restaurant and three reviews persisted; last_synced_at set; no provider call
- **Automated Test Mapping:** `test_api.TestBackendAcceptance.test_be_22_p0_mock_sync_without_credentials`
- [ ] **Execution:** Run mapped methods; verify response, persistence and negative scenarios; record actual outcome and attach failure evidence.

### BE-23 — Idempotent Sync [P0]

- [ ] **Input / Preconditions:** POST /sync/run twice for same target
- [ ] **Expected Result:** COMPLETED; restaurant/review IDs unchanged; second reviews_upserted=0; two run rows
- **Automated Test Mapping:** `test_api.TestBackendAcceptance.test_be_23_p0_repeated_sync_is_idempotent`
- [ ] **Execution:** Run mapped methods; verify response, persistence and negative scenarios; record actual outcome and attach failure evidence.

### BE-24 — Inactive / Invalid Target [P1]

- [ ] **Input / Preconditions:** POST /sync/run with active/inactive targets; then target_id=999999
- [ ] **Expected Result:** Bulk run imports active only; inactive timestamp stays unset; missing target 404
- **Automated Test Mapping:** `test_api.TestBackendAcceptance.test_be_24_p1_skip_inactive_and_missing_target`
- [ ] **Execution:** Run mapped methods; verify response, persistence and negative scenarios; record actual outcome and attach failure evidence.

### BE-25 — External Sync Failure [P1]

- [ ] **Input / Preconditions:** POST /sync/run?target_id={id}; mocked timeout, REQUEST_DENIED, absent result, invalid review (separate fixtures)
- [ ] **Expected Result:** 200 with FAILED persisted status/error; no partial imports; timestamp unchanged; zero import counters
- **Automated Test Mapping:** `test_api.TestBackendAcceptance.test_be_25_p1_provider_timeout_persists_failed_status`, `test_api.TestBackendAcceptance.test_be_25_p1_provider_denial_persists_failed_status`, `test_api.TestBackendAcceptance.test_be_25_p1_missing_result_persists_failed_status`, `test_api.TestBackendAcceptance.test_be_25_p1_invalid_review_has_no_partial_import`
- [ ] **Execution:** Run mapped methods; verify response, persistence and negative scenarios; record actual outcome and attach failure evidence.

## Known gaps

Existing acceptance failures are recorded in `api/tests/README.md`. Acceptance criteria remain unchanged; failures are not skipped or converted to expected failures. Runtime results, including NOT_EXECUTED cases for priority-only runs, are available in JSON artifacts.

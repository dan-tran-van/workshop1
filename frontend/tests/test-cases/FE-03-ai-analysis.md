# FE-03 — AI Analysis Dashboard

**Scope:** Frontend functional and API-integration testing  
**Priority:** P0/P1  
**Related APIs:** `POST /restaurants/{id}/analyze`, `GET /restaurants/{id}/analyses`

> These cases verify how the frontend triggers analysis and presents the API response. E2E tests use deterministic mocked responses. The latest analysis is included in the restaurant detail response; the current frontend does not display analysis history.

## FE-12 [P0] — Trigger restaurant analysis and render the response

**Type:** Positive

### Preconditions
- A valid restaurant exists.
- The restaurant detail page is accessible.
- The analysis endpoint is available.

### Test Steps
1. Open the restaurant detail page.
2. Locate the Analyze action.
3. Activate Analyze.
4. Wait for the analysis request to complete.

### Expected Results
- The frontend sends a request to `POST /restaurants/{id}/analyze` using the selected restaurant ID.
- The analysis response is rendered on the page.
- The displayed result belongs to the selected restaurant.
- The application does not display an unrelated or stale analysis as the new result.

---

## FE-13 [P0] — Disable Analyze while processing to prevent duplicate requests

**Type:** Positive / Interaction

### Preconditions
- A valid restaurant detail page is open.
- The analysis request can be kept in a loading state long enough to interact with the UI.

### Test Steps
1. Open the restaurant detail page.
2. Activate Analyze.
3. While the request is still processing, attempt to activate Analyze again.

### Expected Results
- The Analyze control becomes disabled or otherwise prevents repeated activation while processing.
- Only one analysis request is submitted for the action.
- A loading indicator or equivalent progress feedback is visible.
- The control becomes available again after the request completes or fails, according to the UI design.

---

## FE-14 [P0] — Display overall sentiment, summary, and estimated rating trend

**Type:** Positive

### Preconditions
- The analysis endpoint returns a valid analysis response containing overall sentiment, summary, and estimated rating trend.

### Test Steps
1. Open a restaurant with an available analysis, or trigger a new analysis.
2. Locate the overall analysis section.
3. Compare the displayed values with the API response.

### Expected Results
- Overall sentiment is displayed.
- The analysis summary is displayed.
- Estimated rating trend is displayed.
- Values shown in the UI correspond to the API response.
- Missing or null values, if permitted by the API contract, do not cause the page to crash.

---

## FE-15 [P0] — Display analysis for all six aspects

**Type:** Positive

### Preconditions
- The analysis response contains aspect breakdown data for the supported aspects.

### Test Steps
1. Open the analysis dashboard.
2. Locate the aspect breakdown section.
3. Inspect the entries for food, service, wait_time, hygiene, ambience, and price.

### Expected Results
- The UI supports and displays all six aspects:
  - `food`
  - `service`
  - `wait_time`
  - `hygiene`
  - `ambience`
  - `price`
- Each displayed aspect shows its label, sentiment, score, and summary.
- Aspect highlights are present in the response fixture but are not rendered by the current UI.
- Aspect labels are understandable to users.
- Data is associated with the correct aspect; values are not mixed between aspects.

---

## FE-16 [P0] — Display improvement suggestions and strength aspects

**Type:** Positive

### Preconditions
- The analysis response contains prioritized improvements and strengths.

### Test Steps
1. Open the analysis dashboard.
2. Locate the prioritized improvements section.
3. Inspect the priority, issue, and recommended action for improvement items.
4. Locate the strengths section.
5. Inspect the aspect labels shown for strengths.

### Expected Results
- Prioritized improvements are displayed.
- Up to two improvement items are shown with priority, aspect, issue, and recommended action.
- Expected impact is not currently rendered.
- Priority ordering matches the API response or the explicitly agreed UI sorting rule.
- Strengths are displayed.
- Strengths are currently represented by aspect chips; the strength text and marketing tip are not rendered.
- Improvement items and strengths are not interchanged or mislabelled.

---

## FE-17 [P1] — Handle analysis with no reviews or empty insight arrays

**Type:** Negative / Empty State

### Preconditions
- A valid restaurant has no reviews, or a test fixture returns an analysis response with empty insight arrays.
- The frontend can access the relevant restaurant and analysis view.

### Test Steps
1. Open the restaurant detail page for the restaurant with no reviews, or load the test fixture with empty insight arrays.
2. Trigger analysis if supported by the product flow.
3. Inspect the analysis result sections.

### Expected Results
- The UI handles the no-review condition with an appropriate message or state.
- Empty improvement, strength, or highlight arrays do not cause rendering errors.
- Empty sections are handled consistently with the agreed UI design (for example, an explanatory empty state or an omitted section).
- The page remains usable and does not display fabricated insights.

---

## FE-18 [P1] — Support re-analysis using force_refresh=true

**Type:** Positive / API Integration

### Preconditions
- A valid restaurant exists.
- An analysis has already been generated or cached.
- The UI provides a re-analysis action.

### Test Steps
1. Open the restaurant detail page with an existing analysis.
2. Activate the re-analysis action.
3. Inspect the outgoing request in the browser Network panel.
4. Wait for the response.

### Expected Results
- The frontend sends the request to `POST /restaurants/{id}/analyze`.
- The request includes `force_refresh=true` using the format required by the API contract.
- The UI indicates that re-analysis is in progress.
- The displayed result is updated from the response.
- The previous result is not incorrectly presented as the newly generated result after the request succeeds.

---

## FE-19 [P1] — Display analysis history from newest to oldest

**Type:** Positive / Sorting

### Preconditions
- The restaurant has multiple analysis records with distinguishable creation timestamps.
- `GET /restaurants/{id}/analyses` returns those records.
- The frontend provides an analysis history view.

### Test Steps
1. Open the restaurant detail page or analysis history view.
2. Locate the analysis history section.
3. Compare the displayed order with the timestamps returned by the API.

### Expected Results
- Analysis history is displayed from newest to oldest.
- Each entry shows the appropriate analysis information defined by the UI.
- The displayed order matches the agreed sorting rule and API data.
- Empty history is handled without a rendering error.

### Implementation note

The current frontend displays only `latest_analysis` from the restaurant
detail response. When analysis history is added, verify the displayed
records are ordered newest to oldest.

---

## Additional exploratory checks

- Analysis API returns an error: the UI displays an error state and does not crash.
- Analysis request times out or takes a long time: the user receives appropriate progress feedback.
- Refreshing the page after analysis does not corrupt or misassociate the displayed result.
- Missing optional response fields are handled gracefully.
- A response for one restaurant is never displayed on another restaurant's page.

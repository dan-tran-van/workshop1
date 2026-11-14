# FE-02 — Restaurant Details & Reviews

**Scope:** Frontend functional testing  
**Priority:** P0/P1  
**Related APIs:** `GET /restaurants/{id}`, `GET /restaurants/{id}/reviews`

> These test cases verify the UI and its interaction with the API. They do not validate backend implementation details. Confirm exact field names, pagination parameters, and UI behavior against the implemented frontend/API contract before execution.

## FE-07 [P0] — Open restaurant detail using selected restaurant ID

**Type:** Positive

### Preconditions
- The restaurant listing page is available.
- `GET /restaurants` returns at least one restaurant with a valid ID.
- The selected restaurant has a detail record.

### Test Steps
1. Open the restaurant listing page.
2. Select a restaurant from the list.
3. Wait for the detail page or detail view to load.

### Expected Results
- The application opens the detail view for the selected restaurant.
- The request uses the selected restaurant's ID.
- The displayed restaurant information belongs to that restaurant.
- The page does not display information from a previously selected restaurant.

### Actual Results
Pending

### Status
Not Run

---

## FE-08 [P0] — Display reviews with author, rating, content, and published date

**Type:** Positive

### Preconditions
- A restaurant exists and has one or more reviews.
- The review response contains author, rating, content, and published date values.

### Test Steps
1. Open the restaurant detail page.
2. Locate the reviews section.
3. Inspect several review entries.

### Expected Results
- Reviews are displayed for the selected restaurant.
- Each review displays its author, rating, content, and published date.
- Each displayed value matches the corresponding API response.
- Long review content remains readable and does not overlap or break the page layout.

### Actual Results
Pending

### Status
Not Run

---

## FE-09 [P0] — Display an empty state when the restaurant has no reviews

**Type:** Negative / Empty State

### Preconditions
- A valid restaurant exists.
- The restaurant has no reviews, or the reviews API returns an empty list.

### Test Steps
1. Open the restaurant detail page for the restaurant without reviews.
2. Locate the reviews section.

### Expected Results
- The page displays an appropriate empty state or explanatory message.
- No broken review cards or placeholder records are displayed.
- The rest of the restaurant detail page remains usable.

### Actual Results
Pending

### Status
Not Run

---

## FE-10 [P1] — Support review pagination without duplicate records

**Type:** Positive / Pagination

### Preconditions
- A restaurant has enough reviews to require more than one page.
- The frontend exposes a pagination or load-more interaction.
- The API supports the pagination parameters defined by its contract.

### Test Steps
1. Open the restaurant detail page.
2. Record the reviews displayed on the first page.
3. Navigate to the next page or activate the load-more control.
4. Compare the newly displayed reviews with the first page.
5. Continue to another page if available.

### Expected Results
- The next set of reviews is loaded.
- Previously displayed reviews are not duplicated.
- Reviews from different pages are combined or navigated according to the UI design.
- The application handles the final page without showing duplicate or nonexistent records.
- The displayed reviews belong to the selected restaurant.

### Actual Results
Pending

### Status
Not Run

---

## FE-11 [P1] — Handle an invalid restaurant ID with a Not Found page

**Type:** Negative

### Preconditions
- The application is running.
- A restaurant ID that does not exist is available for testing.

### Test Steps
1. Navigate directly to the restaurant detail URL using the invalid ID.
2. Wait for the API response.

### Expected Results
- The application displays a Not Found page or an equivalent not-found message.
- The page does not show stale details from another restaurant.
- The application does not crash.
- The user has a clear way to return to the restaurant listing, if provided by the design.

### Actual Results
Pending

### Status
Not Run

---

## Additional exploratory checks

These checks support the required cases above and can be recorded as observations or additional sub-cases:

- The detail page handles a missing or optional restaurant field without crashing.
- The reviews section handles missing optional review fields gracefully.
- An API failure while loading details or reviews displays an understandable error state.
- A retry action, if provided, requests the data again.
- Refreshing a valid detail URL continues to show the correct restaurant.

## Execution Summary

| Test Case | Priority | Status | Notes |
|---|---|---|---|
| FE-07 | P0 | Not Run | |
| FE-08 | P0 | Not Run | |
| FE-09 | P0 | Not Run | |
| FE-10 | P1 | Not Run | |
| FE-11 | P1 | Not Run | |

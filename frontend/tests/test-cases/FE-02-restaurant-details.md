# FE-02 — Restaurant Details & Reviews

**Scope:** Frontend functional testing  
**Priority:** P0/P1  
**Related API used by the frontend:** `GET /restaurants/{id}`

> The frontend loads restaurant details and the restaurant's embedded `reviews` array from `GET /restaurants/{id}`. Although the backend also exposes `GET /restaurants/{id}/reviews`, the current frontend does not call it.

The selected restaurant appears in a detail panel on the overview/listing view; it is not a separate URL-routed detail page.

## FE-07 [P0] — Open restaurant detail using selected restaurant ID

**Type:** Positive

### Preconditions
- The restaurant listing page is available.
- `GET /restaurants` returns at least one restaurant with a valid ID.
- The selected restaurant has a detail record.

### Test Steps
1. Open the restaurant listing page.
2. Select a restaurant from the list.
3. Wait for the detail panel to load.

### Expected Results
- The application opens the detail view for the selected restaurant.
- The request uses the selected restaurant's ID.
- The displayed restaurant information belongs to that restaurant.
- The page does not display information from a previously selected restaurant.

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
- Each review displays its author, rating, content, and a relative date
  (or a formatted date for older reviews).
- Each displayed value matches the corresponding API response.
- Long review content remains readable and does not overlap or break the page layout.

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

---

## FE-10 [P1] — Support review pagination without duplicate records

**Type:** Positive / Pagination

### Current UI behavior

The frontend receives reviews as part of the restaurant detail response
and displays up to four recent reviews. It has no review pagination or
load-more control.

### Expected Results
- The next set of reviews is loaded.
- Previously displayed reviews are not duplicated.
- Reviews from different pages are combined or navigated according to the UI design.
- The application handles the final page without showing duplicate or nonexistent records.
- The displayed reviews belong to the selected restaurant.

---

## FE-11 [P1] — Handle an invalid restaurant URL

**Type:** Negative

### Preconditions
- The application has a URL-routed restaurant detail view.
- A restaurant ID that does not exist is available for testing.

### Test Steps
1. Navigate directly to the restaurant detail URL using the invalid ID.
2. Wait for the API response.

### Expected Results
- The application displays a Not Found page or an equivalent not-found message.
- The page does not show stale details from another restaurant.
- The application does not crash.
- The user has a clear way to return to the restaurant listing, if provided by the design.

### Implementation note

The current frontend does not route restaurant IDs from the URL. When a
URL-based detail route is available, verify how the UI handles the API's
404 response.

---

## Additional exploratory checks

These checks support the required cases above and can be recorded as observations or additional sub-cases:

- The detail page handles a missing or optional restaurant field without crashing.
- The reviews section handles missing optional review fields gracefully.
- An API failure while loading details or reviews displays an understandable error state.
- A retry action, if provided, requests the data again.
- Refreshing a valid detail URL continues to show the correct restaurant.

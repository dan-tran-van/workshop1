# FE-01 --- Restaurant Listing & Search

**Module:** Restaurant Search & Listing\
**Priority:** P0 (FE-01 to FE-05), P1 (FE-06)\
**Test type:** Frontend functional / API integration\
**Scope:** Verify that the Frontend displays restaurant data returned by
the API and correctly handles search, empty, loading, error, and
pagination states.

> These test cases validate the Frontend's interaction with the API.
> They do not validate the Backend's internal implementation.

## API Contract

### Endpoint

`GET /restaurants`

### Query parameters

  Parameter   Type        Default Constraint / Purpose
  ----------- --------- --------- --------------------------------------
  `q`         string       `null` Searches restaurant name or address
  `skip`      integer         `0` Must be greater than or equal to `0`
  `limit`     integer        `20` Must be between `1` and `100`

### Relevant response fields

The endpoint returns a JSON array of restaurant objects. Relevant fields
include:

  Field                 Meaning
  --------------------- ----------------------------------------------
  `id`                  Restaurant ID
  `name`                Restaurant name
  `address`             Restaurant address; may be `null`
  `google_rating`       Google rating; may be `null`
  `user_rating_count`   Google user rating count; may be `null`
  `review_count`        Number of reviews stored by this application

**Important:** `google_rating` and `user_rating_count` are not the same
as `review_count`. The UI should display the values according to the
agreed design and labels.

### Current frontend behavior

- The frontend requests `GET /restaurants?limit=100`; it does not send
  `skip`.
- Search runs automatically after typing, with a 250 ms debounce, and
  trims surrounding whitespace.
- The list has pagination controls, but both are disabled. The UI does
  not currently paginate restaurant results.

------------------------------------------------------------------------

## FE-01 --- Display restaurants

**Priority:** P0\
**Type:** Positive\
**API:** `GET /restaurants`

### Preconditions

-   Frontend application is running.
-   API is available.
-   API returns one or more restaurant records.

### Test Steps

1.  Open the restaurant listing page.
2.  Wait for the restaurant API request to complete.
3.  Inspect the displayed restaurant items.
4.  Compare the displayed values with the API response.

### Expected Results

-   The restaurant list is displayed.
-   Each restaurant displays its name, address, rating, and review count
    according to the UI specification.
-   The displayed data matches the corresponding API response:
    -   Name maps to `name`.
    -   Address maps to `address`.
    -   Google rating maps to `google_rating`.
    -   Review count maps to `review_count`.
-   A missing optional value, such as a `null` address or rating, does
    not break the page.
-   Each restaurant is represented once.

------------------------------------------------------------------------

## FE-02 --- Search restaurants by name

**Priority:** P0\
**Type:** Positive\
**API:** `GET /restaurants?q={search_term}`

### Preconditions

-   Frontend application is running.
-   At least one restaurant with a known name exists in the API data.

### Test Steps

1.  Open the restaurant listing page.
2.  Enter a distinctive part of an existing restaurant name in the
    search field.
3.  Submit the search or wait for the UI's search behavior.
4.  Inspect the results and, if possible, inspect the request sent by
    the Frontend.

### Expected Results

-   The Frontend sends the search term through the `q` query parameter.
-   Restaurants whose names match the search term are displayed.
-   Results match the API response for that query.
-   Unrelated results are not displayed.

------------------------------------------------------------------------

## FE-03 --- Search restaurants by address

**Priority:** P0\
**Type:** Positive\
**API:** `GET /restaurants?q={search_term}`

### Preconditions

-   Frontend application is running.
-   At least one restaurant with a known address exists in the API data.

### Test Steps

1.  Open the restaurant listing page.
2.  Enter a distinctive part of an existing restaurant address in the
    search field.
3.  Submit the search or wait for the UI's search behavior.
4.  Inspect the results and, if possible, inspect the request sent by
    the Frontend.

### Expected Results

-   The Frontend sends the address search term through the `q` query
    parameter.
-   Restaurants whose addresses match the search term are displayed.
-   Results match the API response for that query.
-   Unrelated results are not displayed.

------------------------------------------------------------------------

## FE-04 --- Display empty state when no restaurants match

**Priority:** P0\
**Type:** Negative / Empty state\
**API:** `GET /restaurants?q={search_term}`

### Preconditions

-   Frontend application is running.
-   A search term that does not match any restaurant is available.

### Test Steps

1.  Open the restaurant listing page.
2.  Enter a search term that has no matching restaurant.
3.  Submit the search or wait for the UI's search behavior.
4.  Inspect the page.

### Expected Results

-   The API returns an empty array for the search.
-   The Frontend displays an appropriate empty state.
-   Results from a previous search are not incorrectly presented as
    matches for the new query.
-   The application remains usable and does not show an unhandled error.

------------------------------------------------------------------------

## FE-05 --- Show loading and error states

**Priority:** P0\
**Type:** Negative / Error handling\
**API:** `GET /restaurants`

### Preconditions

-   Frontend application is running.
-   The API response can be delayed or a network/API failure can be
    simulated.

### Test Steps --- Loading

1.  Delay the restaurant API response using a mock or browser network
    throttling.
2.  Open or refresh the restaurant listing page.
3.  Observe the page before the response is returned.
4.  Allow the request to complete.

### Expected Results --- Loading

-   A loading indicator or loading state is displayed while the request
    is pending.
-   The loading state disappears after the request completes.
-   Restaurant data is displayed after a successful response.

### Test Steps --- Error and Retry

1.  Configure the mock API to return an error, or simulate a network
    failure.
2.  Open or refresh the restaurant listing page.
3.  Observe the error state.
4.  Select the page-level **Refresh** action to retry the requests.
5.  Return the mock to a successful response and observe the result.

### Expected Results --- Error and Retry

-   A clear error message is displayed.
-   The page-level **Refresh** action is available as the retry action.
-   Selecting Refresh triggers another restaurant request.
-   If the retry succeeds, the restaurant list is displayed.
-   The API failure does not crash the application.

------------------------------------------------------------------------

## FE-06 --- Paginate restaurant results without duplicates

**Priority:** P1\
**Type:** Positive / Edge case\
**API:** `GET /restaurants?skip={skip}&limit={limit}`

### Current UI behavior

The frontend currently requests up to 100 restaurants and renders
disabled pagination controls. It does not expose a page-size selector or
load-more action, so this behavior cannot currently be exercised.

### Expected Results

-   The Frontend uses `skip` and `limit` to request the appropriate
    records.
-   The first request uses `skip=0` unless the UI has a documented
    alternative.
-   Subsequent requests advance the offset correctly.
-   Previously displayed records are not duplicated when loading
    additional pages.
-   Pagination behaves correctly when fewer than `limit` records remain.
-   An empty final response does not crash the application.

------------------------------------------------------------------------

## Notes

- Search is automatic; clearing the field loads the unfiltered list.
- Restaurant rows display Google rating and stored review count. The
  detail view labels the Google rating and total Google ratings.
- There is no separate retry button in the error banner; use the page
  **Refresh** action.

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

### Actual Result

*To be filled during execution.*

### Status

Not Run

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

### Actual Result

*To be filled during execution.*

### Status

Not Run

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

### Actual Result

*To be filled during execution.*

### Status

Not Run

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

### Actual Result

*To be filled during execution.*

### Status

Not Run

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
4.  Select **Retry**.
5.  Restore a successful API response and observe the result.

### Expected Results --- Error and Retry

-   A clear error message is displayed.
-   A **Retry** action is available.
-   Selecting Retry triggers another request.
-   If the retry succeeds, the restaurant list is displayed.
-   The API failure does not crash the application.

### Actual Result

*To be filled during execution.*

### Status

Not Run

------------------------------------------------------------------------

## FE-06 --- Paginate restaurant results without duplicates

**Priority:** P1\
**Type:** Positive / Edge case\
**API:** `GET /restaurants?skip={skip}&limit={limit}`

### Preconditions

-   Frontend application is running.
-   The API contains more restaurant records than the selected page
    size.
-   Pagination controls or an equivalent load-more interaction are
    available.

### Test Steps

1.  Open the restaurant listing page.
2.  Record the restaurant IDs displayed on the first page.
3.  Navigate to the next page or select **Load more**.
4.  Inspect the request parameters and record the newly displayed
    restaurant IDs.
5.  Continue through the available pages.
6.  Compare the IDs across pages.

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

### Actual Result

*To be filled during execution.*

### Status

Not Run

------------------------------------------------------------------------

## Execution Summary

  Test Case                           Priority   Status    Notes
  ----------------------------------- ---------- --------- -------
  FE-01 --- Display restaurants       P0         Not Run   
  FE-02 --- Search by name            P0         Not Run   
  FE-03 --- Search by address         P0         Not Run   
  FE-04 --- No matching restaurants   P0         Not Run   
  FE-05 --- Loading and API error     P0         Not Run   
  FE-06 --- Pagination                P1         Not Run   

## Items to Confirm with the Frontend Developer

1.  Which UI labels should be used for `google_rating`,
    `user_rating_count`, and `review_count`?
2.  What should the UI do when the search field is cleared or contains
    only whitespace?
3.  Is search triggered by Enter, a search button, or automatically
    while typing?
4.  Is pagination implemented as numbered pages, infinite scroll, or a
    Load more button?
5.  Should pagination reset to the first page when a new search term is
    entered?
6.  What exact loading and error UI should be shown?

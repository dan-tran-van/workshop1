# Market Comparison: Competitive Set and Criteria Gap

Status: **MVP implemented with reduced scope**. This document records what was built for
US-01 (competitive set suggestions) and US-02 (criteria gap table with AI explanation), the
rules agreed with the product owner, the known data limitations, and the plan for the parts
that are not implemented yet.

- Backend: [`api/app/services/competitors.py`](../api/app/services/competitors.py), [`api/app/routers/competitors.py`](../api/app/routers/competitors.py)
- Frontend: [`frontend/src/components/MarketComparison.tsx`](../frontend/src/components/MarketComparison.tsx) (sidebar item **Market comparison**)
- Tests: [`api/tests/test_market_comparison.py`](../api/tests/test_market_comparison.py), [`frontend/tests/e2e/market-comparison.spec.ts`](../frontend/tests/e2e/market-comparison.spec.ts)

## Why the scope is reduced

The seeded datasets (`api/district2_restaurants_reviews.json`, `api/alaska_moose_tooth_reviews.json`,
`api/district1_restaurants_reviews.json`, `api/austin_bbq_reviews.json`)
only contain name, address, Google rating, Google review count, and review text. They do **not**
contain coordinates, cuisine/category, or price level, and 14 of the 30 seeded restaurants have
collected reviews (4 in District 2 with 2–5, 5 in District 1 with 30–45, 4 in Austin with 35–70,
and 1 in Anchorage with 2,833). Finding real
competitors inside a radius needs the Google Places API, which is not configured yet.

## What is implemented

### US-01: Competitive set

| Acceptance criterion | MVP behavior |
| :--- | :--- |
| First suggestion: 5-10 competitors with name, distance, rating, review count, cuisine | Up to `COMPETITOR_MAX_SUGGESTIONS` (10) competitors. Distance and cuisine are returned as `null` and shown as "Not available". |
| Selection criteria: radius, same cuisine, similar price and review volume | **Radius, cuisine, and price are not applied** (no data). Candidates: every other restaurant in the workspace. Ranking: restaurants **with collected reviews first**, then restaurants without reviews. When both the owner's restaurant and a candidate have stored review embeddings (`review_embeddings`), reviewed competitors are ranked by **cosine similarity of their review centroids** first, falling back to closest **Google review volume** (`user_rating_count`). |
| Each competitor shows why it was suggested | `reasons` list, for example "92% similar guest review profile", "5 collected reviews, compared on the same criteria", "404 Google reviews (yours: 536)", "Pinned by you". |
| Pin / Dismiss updates the list immediately; pinned are always kept; dismissed are not suggested again | `PUT /restaurants/{id}/competitors/{competitor_id}` with `PINNED` or `DISMISSED` returns the updated set. Pinned and manual competitors are always listed first and count toward the 10 slots. Dismissed competitors are listed separately and can be restored (`DELETE` resets the choice). |
| Manual add uses the same comparison criteria | Owners pick from restaurants **already in the workspace** (`GET .../competitors/candidates`, then `PUT` with `MANUAL`). Candidate search combines lexical name/address matching with semantic review matching when query embeddings are available. Manual competitors are scored exactly like suggested ones. |
| Fewer than 5 matching places: show the count, a notice, and suggest widening the radius or cuisine | `notice` reports the found count and the suggestion. A second notice reports when fewer than 5 competitors have collected reviews, because only those can be scored. |
| Periodic refresh (for example weekly) without losing pin/dismiss choices | **No scheduled job.** Suggestions are recomputed on every request and with the **Refresh suggestions** button. Pin, dismiss, and manual choices are stored in `competitor_selections` and always survive a refresh. |

### US-02: Criteria gap table

| Acceptance criterion | MVP behavior |
| :--- | :--- |
| Per criterion: own score, competitor average, leader score, gap | `GET /restaurants/{id}/competitors/gap` returns all six fixed criteria: food, service, wait_time, hygiene, ambience, price. |
| Same criteria and scale for every place | Score = average star rating (1-5) of the reviews whose text mentions the criterion (same EN+VI keyword lists as the analysis engine). |
| Losing criteria red, leading criteria green, sortable by gap | Row accent and gap value are red when the gap is below `-GAP_TIE_MARGIN`, green above `+GAP_TIE_MARGIN`, amber in between. Sort: default, most behind first, most ahead first. |
| AI explains the gap with 2-3 real review quotes | `POST /restaurants/{id}/competitors/gap/{aspect}/explain`. Evidence quotes are always selected from stored reviews. With `OPENAI_API_KEY`, the model must cite review IDs from the provided quotes, or the answer is rejected and the rule-based explanation is used. |
| Labels: Learn / Keep / Attack | Computed in code, never by the model (see rules below). |
| Criterion below the minimum review count: "Not enough data", no AI conclusion | `INSUFFICIENT_DATA` status with a reason; the explain endpoint returns 422 for that criterion. |
| AI makes no claim without evidence in collected reviews | The prompt restricts the model to the given facts and quotes, the reply must reference provided review IDs, and invalid replies fall back to a template built only from computed numbers. |

## Agreed business rules

| Rule | Value |
| :--- | :--- |
| Who can use it | **Owner** (own assigned restaurants) and **Analyst** (any restaurant). **Admin** does not see the feature (403). |
| Who can change the competitive set | **Owner only.** Analysts are view-only. Choices are stored per restaurant. |
| Candidate ranking | Collected reviews first, then without reviews; then closest Google review volume. |
| Area restriction | None for now (Moose's Tooth in Anchorage can be suggested for HCMC restaurants). |
| Minimum reviews per criterion | `MIN_REVIEWS_PER_CRITERION`, default **3** for the demo data. **Use 20 in production** (the value in US-02). |
| Below the minimum for the owner's restaurant | Criterion shows "Not enough data", no AI explanation. |
| Below the minimum for a competitor | That competitor is left out of the average and leader for that criterion. If no competitor qualifies, the criterion shows "Not enough data". |
| Labels (`gap = own score - competitor average`) | **Learn from rivals** (Cần học): `gap < -0.3`. **Attack opportunity** (Có thể tấn công): `gap > +0.3` and competitor average `< 3.5`. **Keep** (Cần giữ): everything else (level or ahead). |

All thresholds are environment settings in `api/app/config.py`: `COMPETITOR_MIN_SUGGESTIONS`,
`COMPETITOR_MAX_SUGGESTIONS`, `MIN_REVIEWS_PER_CRITERION`, `GAP_TIE_MARGIN`, `GAP_WEAK_COMPETITOR_AVG`.

## Data model

New table `competitor_selections` (created automatically by `Base.metadata.create_all`; no existing
table changes):

| Column | Notes |
| :--- | :--- |
| `restaurant_id` | The owner's restaurant. |
| `competitor_id` | The competitor restaurant. Unique together with `restaurant_id`. |
| `status` | `PINNED`, `DISMISSED`, or `MANUAL`. No row means "system suggestion". |
| `created_by_user_id` | Owner who made the choice. |

## Notes to revisit later

These were explicitly deferred and must be reviewed before the feature is considered complete:

1. **Cuisine / category is not used.** No dataset field exists. Add a `cuisine` (or Google `primaryType`) column, populate it during sync, and rank same-cuisine competitors first. Then add the "relax cuisine" option promised by the low-match notice.
2. **No area restriction.** Every restaurant is a candidate, including Moose's Tooth (Anchorage) for HCMC restaurants. Restrict candidates to the same area first, then replace it with the radius filter below.
3. **Minimum review threshold is 3, not 20.** Set `MIN_REVIEWS_PER_CRITERION=20` once enough reviews are collected.
4. **Distance and price level are always `null`.** The API contract and UI columns already exist, so they can be filled in without a breaking change.
5. **No weekly refresh job.** Suggestions are computed on demand.
6. **Criteria are fixed** to the six analysis aspects. Admin-configurable criteria are not implemented.
7. **Manual add is limited to restaurants already in the database.** There is no Google search for new places.
8. **Imputed ratings.** The District 2 dataset fills missing star ratings with the restaurant's Google rating (`rating_imputed` in the JSON). That flag is not stored in the database, so for example every review of "con gà mái" counts as 3.9 stars. Decide whether imputed ratings should be excluded from criterion scores, and store the flag if so.
9. **Competitor review visibility.** Owners can now see up to three quoted reviews of competitor restaurants as evidence, even though they cannot open those restaurants elsewhere. Confirm this is acceptable.
10. **Explanations are not cached.** Each "Why?" click recomputes the gap and, with an OpenAI key, calls the model. Cache by `(restaurant, aspect, review counts of the set)` when usage grows.
11. **Keyword-based criterion detection** is approximate (for example "slow" counts for both service and wait time). Scores improve if the aspect tagging moves to the LLM analysis or a classifier.

## Roadmap: radius-based competitor discovery (not implemented)

Requires a `GOOGLE_PLACES_API_KEY` with Places API (New) enabled.

1. **Store coordinates and attributes per restaurant.** Add `latitude`, `longitude`, `primary_type`,
   `price_level` to `Restaurant`. Fill them during sync from Place Details
   (`location`, `primaryType`, `types`, `priceLevel`). Introduce migrations (for example Alembic)
   first, because `create_all` does not alter existing tables.
2. **Admin-configured radius.** Add a workspace setting (default for example 1,500 m) editable from
   the admin screen, with an optional per-restaurant override.
3. **Discover nearby places.** Call Nearby Search (New) `POST https://places.googleapis.com/v1/places:searchNearby`
   with `locationRestriction.circle` (owner restaurant coordinates + radius), `includedTypes`
   set to the owner's `primaryType` (or `restaurant` when relaxed), and a field mask limited to
   `places.id,places.displayName,places.location,places.rating,places.userRatingCount,places.priceLevel,places.primaryType`.
   Upsert results as restaurants with a `discovered_only` flag so they do not appear as owned locations.
4. **Rank by the full US-01 criteria.** Filter by distance <= radius, same cuisine, price level
   within ±1, and review volume within a configurable ratio; compute `distance_m` with the haversine
   formula. Reasons become, for example, "800 m away, same hotpot category, price level $".
5. **Collect reviews for competitors.** Add discovered competitors as sync targets so they receive
   reviews and can be scored. Note that Place Details returns at most 5 reviews per place, so a
   different review source is needed to reach 20 reviews per criterion.
6. **Weekly refresh.** Run discovery on a schedule (cron container, APScheduler, or a CI schedule),
   store a dated snapshot of suggestions, and keep `competitor_selections` untouched so pins and
   dismissals survive.
7. **Low-match handling.** When fewer than 5 places match, offer one-click "expand radius" (for
   example ×2) and "any restaurant type" options that re-run discovery.
8. **Manual add from Google.** Use Text Search (New) to find a place by name and add it as a
   `MANUAL` competitor.

## Manual Testing Guide (Swagger UI & Login)

Note: Restaurant similarity is computed from per-review embeddings (`review_embeddings`), so restaurants without collected reviews fall back to Google review-volume distance.

1. **Seed data and backfill embeddings** (requires `OPENAI_API_KEY` in `.env`):
   ```bash
   docker compose up -d --build
   docker compose run --rm seed
   docker compose run --rm backfill-embeddings
   # Optional targeted backfill:
   # docker compose run --rm backfill-embeddings --restaurant-id 1
   # docker compose run --rm backfill-embeddings --review-id 10 --review-id 11
   ```
2. **Create demo accounts** (prints random passwords once; the `OWNER` account is assigned to restaurant ID `1`):
   ```bash
   docker compose exec api python seed_demo_users.py
   ```
3. **Log in via Swagger UI (`http://localhost:8000/docs`)**:
   - Open `POST /auth/login` → **Try it out** → enter the `OWNER` (or `ANALYST`) email and password → **Execute**.
   - Copy the `access_token` from the response.
   - Click **Authorize** at the top of Swagger UI, paste the token, and click **Authorize**.
4. **Test semantic competitor lookup**:
   - **Competitive set (`GET /restaurants/1/competitors`)**: Execute with `restaurant_id = 1`. Competitors with collected reviews are ranked by review-profile cosine similarity first and include `"<pct>% similar guest review profile"` in `reasons`.
   - **Manual candidate search (`GET /restaurants/1/competitors/candidates`)**: Execute as `OWNER` or `ANALYST` with a semantic query such as `q=truffle pasta` or `q=slow service` to see restaurants matched by their review content even when the query is not in their name or address.

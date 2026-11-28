import { type FormEvent, useCallback, useEffect, useState } from "react";
import {
  CircleHelp,
  LoaderCircle,
  MapPin,
  Search,
  Sparkles,
  Star,
} from "lucide-react";
import type { ReviewSearchResponse } from "../types/reviewSearch";

type RequestFn = <T>(path: string, init?: RequestInit) => Promise<T>;

const EXAMPLE_QUERIES = [
  "cold food",
  "slow service",
  "friendly staff",
  "good value",
];

function timeAgo(value: string | null | undefined) {
  if (!value) return "No recent activity";
  const days = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 86_400_000));
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 7) return `${days} days ago`;
  if (days < 30) return `${Math.floor(days / 7)} weeks ago`;
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", year: "numeric" }).format(new Date(value));
}

export function ReviewSearchPage({
  restaurants,
  initialRestaurantId,
  request,
}: {
  restaurants: { id: number; name: string }[];
  initialRestaurantId: number | null;
  request: RequestFn;
}) {
  const [query, setQuery] = useState("");
  const [restaurantFilter, setRestaurantFilter] = useState<string>(
    initialRestaurantId !== null ? String(initialRestaurantId) : "all",
  );
  const [minSimilarity, setMinSimilarity] = useState<string>("none");
  const [response, setResponse] = useState<ReviewSearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (
      restaurantFilter !== "all" &&
      !restaurants.some((item) => String(item.id) === restaurantFilter)
    ) {
      setRestaurantFilter("all");
    }
  }, [restaurantFilter, restaurants]);

  const runSearch = useCallback(
    async (searchText: string, scopedRestaurant: string, similarityCutoff: string) => {
      const trimmed = searchText.trim();
      if (!trimmed) {
        setResponse(null);
        setError("");
        return;
      }

      setLoading(true);
      setError("");
      try {
        const params = new URLSearchParams({ q: trimmed, limit: "25" });
        if (scopedRestaurant !== "all") {
          params.set("restaurant_id", scopedRestaurant);
        }
        if (similarityCutoff !== "none") {
          params.set("min_similarity", similarityCutoff);
        }
        const data = await request<ReviewSearchResponse>(`/reviews/search?${params.toString()}`);
        setResponse(data);
      } catch (searchError) {
        setResponse(null);
        setError(searchError instanceof Error ? searchError.message : "Unable to search reviews.");
      } finally {
        setLoading(false);
      }
    },
    [request],
  );

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void runSearch(query, restaurantFilter, minSimilarity);
  }

  return (
    <div className="review-search-page">
      <section className="panel market-panel">
        <div className="panel-heading">
          <div>
            <span className="section-kicker">SEMANTIC REVIEW SEARCH</span>
            <h2>Search guest feedback by meaning</h2>
            <p>
              Find reviews that match a topic or dining experience even when they do not use your exact words.
            </p>
          </div>
        </div>

        <form className="review-search-form" onSubmit={handleSubmit}>
          <label className="search-field review-search-input">
            <Search size={15} />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder='Try "cold food", "long wait", or "friendly staff"...'
              aria-label="Search reviews"
            />
          </label>
          <label className="comparison-picker">
            <span className="comparison-picker-label"><MapPin size={13} />Scope</span>
            <select
              className="comparison-select"
              aria-label="Filter by restaurant"
              value={restaurantFilter}
              onChange={(event) => {
                const next = event.target.value;
                setRestaurantFilter(next);
                if (query.trim()) void runSearch(query, next, minSimilarity);
              }}
            >
              <option value="all">All accessible restaurants</option>
              {restaurants.map((item) => (
                <option key={item.id} value={String(item.id)}>{item.name}</option>
              ))}
            </select>
          </label>
          <label className="comparison-picker">
            <span className="comparison-picker-label"><Sparkles size={13} />Min match</span>
            <select
              className="comparison-select"
              aria-label="Minimum similarity"
              value={minSimilarity}
              onChange={(event) => {
                const next = event.target.value;
                setMinSimilarity(next);
                if (query.trim()) void runSearch(query, restaurantFilter, next);
              }}
            >
              <option value="none">Any</option>
              <option value="0.25">25%+</option>
              <option value="0.4">40%+</option>
              <option value="0.6">60%+</option>
            </select>
          </label>
          <button type="submit" className="button button-primary" disabled={loading || !query.trim()}>
            {loading ? <LoaderCircle size={15} className="spin" /> : <Search size={15} />} Search
          </button>
        </form>

        <div className="review-search-examples">
          <span className="muted">Try:</span>
          {EXAMPLE_QUERIES.map((example) => (
            <button
              key={example}
              type="button"
              className="comparison-chip review-example-chip"
              onClick={() => {
                setQuery(example);
                void runSearch(example, restaurantFilter, minSimilarity);
              }}
            >
              {example}
            </button>
          ))}
        </div>
      </section>

      {error && (
        <div className="error-banner market-banner">
          <CircleHelp size={16} />
          <span>{error}</span>
        </div>
      )}

      {loading && (
        <div className="loading-state">
          <LoaderCircle size={19} className="spin" />
          <span>Searching reviews...</span>
        </div>
      )}

      {!loading && response && (
        <section className="panel market-panel" aria-labelledby="review-search-results-title">
          <div className="panel-heading">
            <div>
              <h2 id="review-search-results-title">
                {response.results.length} matching {response.results.length === 1 ? "review" : "reviews"}
              </h2>
              <p>Results for "{response.query}"</p>
            </div>
            <span
              className={`search-mode-badge ${
                response.mode === "semantic" ? "mode-semantic" : "mode-keyword"
              }`}
            >
              {response.mode === "semantic" ? (
                <>
                  <Sparkles size={12} /> Semantic ({response.model})
                </>
              ) : (
                <>
                  <Search size={12} /> Keyword fallback (LIKE)
                </>
              )}
            </span>
          </div>

          {response.results.length ? (
            <div className="review-list">
              {response.results.map((item) => (
                <article key={item.id} className="review-row search-review-row">
                  <span className="review-avatar">
                    {item.author_name
                      .trim()
                      .split(/\s+/)
                      .map((part) => part[0])
                      .slice(0, 2)
                      .join("")
                      .toUpperCase()}
                  </span>
                  <div className="review-body">
                    <div className="review-author-line">
                      <strong>{item.author_name}</strong>
                      <span className="search-restaurant-pill">{item.restaurant_name}</span>
                      <span
                        className={`search-match-pill ${
                          item.match_type === "semantic" ? "match-semantic" : "match-keyword"
                        }`}
                      >
                        {item.similarity !== null
                          ? `${Math.round(item.similarity * 100)}% match`
                          : "Keyword match"}
                      </span>
                      <span className="review-date">{timeAgo(item.published_at)}</span>
                    </div>
                    <div className="review-stars" aria-label={`${item.rating} out of 5 stars`}>
                      {Array.from({ length: 5 }, (_, index) => (
                        <Star
                          key={index}
                          size={12}
                          fill={index < Math.round(item.rating) ? "currentColor" : "none"}
                        />
                      ))}
                    </div>
                    <p>{item.text}</p>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <strong>No matching reviews</strong>
              <p>Try a broader query or lower the minimum match threshold.</p>
            </div>
          )}
        </section>
      )}
    </div>
  );
}

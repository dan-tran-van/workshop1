export type ReviewSearchMatchType = "semantic" | "keyword";
export type ReviewSearchMode = "semantic" | "keyword_fallback";

export interface ReviewSearchResult {
  id: number;
  restaurant_id: number;
  restaurant_name: string;
  author_name: string;
  author_uri?: string | null;
  rating: number;
  text: string;
  published_at: string;
  external_review_id?: string | null;
  similarity: number | null;
  match_type: ReviewSearchMatchType;
}

export interface ReviewSearchResponse {
  query: string;
  mode: ReviewSearchMode;
  model: string | null;
  results: ReviewSearchResult[];
}

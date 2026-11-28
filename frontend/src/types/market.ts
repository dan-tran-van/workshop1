export type CompetitorSource = "SUGGESTED" | "PINNED" | "MANUAL";
export type CompetitorSelectionStatus = "PINNED" | "DISMISSED" | "MANUAL";
export type GapStatus = "LEARN" | "KEEP" | "ATTACK" | "INSUFFICIENT_DATA";

export type Competitor = {
  restaurant_id: number;
  name: string;
  address: string | null;
  google_rating: number | null;
  user_rating_count: number | null;
  collected_review_count: number;
  distance_m: number | null;
  cuisine: string | null;
  price_level: number | null;
  source: CompetitorSource;
  scorable: boolean;
  reasons: string[];
};

export type CompetitiveSet = {
  restaurant_id: number;
  generated_at: string;
  competitors: Competitor[];
  dismissed: { restaurant_id: number; name: string }[];
  matching_count: number;
  scored_competitor_count: number;
  min_suggestions: number;
  max_suggestions: number;
  can_edit: boolean;
  notice: string | null;
  data_limitations: string[];
};

export type CompetitorCandidate = {
  restaurant_id: number;
  name: string;
  address: string | null;
  google_rating: number | null;
  user_rating_count: number | null;
  collected_review_count: number;
};

export type GapRow = {
  aspect: string;
  own_score: number | null;
  own_mentions: number;
  competitor_avg: number | null;
  competitors_scored: number;
  leader: { restaurant_id: number; name: string; score: number } | null;
  gap_vs_avg: number | null;
  gap_vs_leader: number | null;
  status: GapStatus;
  insufficient_reason: string | null;
};

export type GapTable = {
  restaurant_id: number;
  generated_at: string;
  min_reviews_per_criterion: number;
  tie_margin: number;
  weak_competitor_avg: number;
  competitors_considered: number;
  rows: GapRow[];
};

export type GapExplanation = {
  aspect: string;
  status: GapStatus;
  explanation: string;
  evidence: {
    review_id: number;
    restaurant_id: number;
    restaurant_name: string;
    is_own: boolean;
    rating: number;
    text: string;
    published_at: string;
  }[];
  model: string;
};

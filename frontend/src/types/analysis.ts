export type Aspect = {
  aspect: string;
  sentiment: string;
  score: number | null;
  summary: string;
  highlights?: string[];
  mentions_count?: number;
};

export type Improvement = {
  priority: string;
  aspect: string;
  issue: string;
  recommended_action: string;
  expected_impact: string;
};

export type Strength = {
  aspect: string;
  strength: string;
  marketing_tip: string | null;
};

export type AnalysisResult = {
  overall_sentiment: string;
  summary: string;
  estimated_rating_trend: string;
  aspect_breakdown: Aspect[];
  prioritized_improvements: Improvement[];
  strengths_to_keep: Strength[];
};

export type Analysis = {
  id: number;
  restaurant_id: number;
  overall_sentiment: string;
  result_json: AnalysisResult;
  review_count: number;
  last_review_at: string | null;
  model: string;
  created_at: string;
};

export type AnalysisHistoryEntry = {
  id: number;
  created_at: string;
  analysis: Analysis;
};

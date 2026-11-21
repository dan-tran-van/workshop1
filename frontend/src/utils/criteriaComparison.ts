import type { Analysis, Aspect } from "../types/analysis";

export const CANONICAL_ASPECTS = [
  "food",
  "service",
  "wait_time",
  "hygiene",
  "ambience",
  "price",
] as const;

export type CriteriaDeltaDirection = "improved" | "declined" | "unchanged" | "unavailable";

export type AspectComparisonItem = {
  aspect: string;
  current: Aspect | null;
  baseline: Aspect | null;
  currentScore: number | null;
  baselineScore: number | null;
  scoreDelta: number | null;
  direction: CriteriaDeltaDirection;
  sentimentChanged: boolean;
};

export type CriteriaComparisonSummary = {
  items: AspectComparisonItem[];
  improvedCount: number;
  declinedCount: number;
  unchangedCount: number;
  currentAvgScore: number | null;
  baselineAvgScore: number | null;
  avgScoreDelta: number | null;
  reviewCountDelta: number;
};

const DELTA_EPSILON = 0.05;

export function normalizeAspectKey(aspect: string): string {
  return aspect.trim().toLowerCase().replace(/[\s-]+/g, "_");
}

export function formatAspectLabel(aspect: string): string {
  return aspect
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function clampScore(score: number | null | undefined): number | null {
  if (typeof score !== "number" || Number.isNaN(score)) return null;
  return Math.max(0, Math.min(5, score));
}

function roundOneDecimal(value: number): number {
  const rounded = Math.round(value * 10) / 10;
  return Object.is(rounded, -0) ? 0 : rounded;
}

export function formatDelta(delta: number | null): string {
  if (delta === null) return "—";
  const rounded = roundOneDecimal(delta);
  if (Math.abs(rounded) < DELTA_EPSILON) return "0.0";
  return `${rounded > 0 ? "+" : ""}${rounded.toFixed(1)}`;
}

export function formatSnapshotTimestamp(value: string | null | undefined): string {
  if (!value) return "Unknown date";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unknown date";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

export function formatSnapshotDateShort(value: string | null | undefined): string {
  if (!value) return "Unknown date";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unknown date";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

export function formatSnapshotOptionLabel(analysis: Analysis): string {
  const sentiment = formatAspectLabel(analysis.overall_sentiment);
  const reviewLabel = analysis.review_count === 1 ? "1 review" : `${analysis.review_count} reviews`;
  return `${formatSnapshotTimestamp(analysis.created_at)} · ${reviewLabel} · ${sentiment}`;
}

export function getPastAnalyses(
  currentAnalysis: Analysis | null | undefined,
  analyses: Analysis[],
): Analysis[] {
  const seen = new Set<number>();
  const currentId = currentAnalysis?.id ?? null;

  return [...analyses]
    .filter((item) => {
      if (currentId !== null && item.id === currentId) return false;
      if (seen.has(item.id)) return false;
      seen.add(item.id);
      return true;
    })
    .sort((a, b) => {
      const timeDiff = new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      if (timeDiff !== 0) return timeDiff;
      return b.id - a.id;
    });
}

export function buildCriteriaComparison(
  currentAnalysis: Analysis,
  baselineAnalysis: Analysis,
): CriteriaComparisonSummary {
  const currentBreakdown = currentAnalysis.result_json?.aspect_breakdown ?? [];
  const baselineBreakdown = baselineAnalysis.result_json?.aspect_breakdown ?? [];

  const currentMap = new Map<string, Aspect>();
  for (const item of currentBreakdown) {
    currentMap.set(normalizeAspectKey(item.aspect), item);
  }

  const baselineMap = new Map<string, Aspect>();
  for (const item of baselineBreakdown) {
    baselineMap.set(normalizeAspectKey(item.aspect), item);
  }

  const orderedKeys: string[] = [];
  for (const canonical of CANONICAL_ASPECTS) {
    if (currentMap.has(canonical) || baselineMap.has(canonical)) {
      orderedKeys.push(canonical);
    }
  }
  for (const key of currentMap.keys()) {
    if (!orderedKeys.includes(key)) orderedKeys.push(key);
  }

  let improvedCount = 0;
  let declinedCount = 0;
  let unchangedCount = 0;

  const currentScores: number[] = [];
  const baselineScores: number[] = [];

  const items: AspectComparisonItem[] = orderedKeys.map((key) => {
    const current = currentMap.get(key) ?? null;
    const baseline = baselineMap.get(key) ?? null;
    const currentScore = clampScore(current?.score);
    const baselineScore = clampScore(baseline?.score);

    if (currentScore !== null) currentScores.push(currentScore);
    if (baselineScore !== null) baselineScores.push(baselineScore);

    let scoreDelta: number | null = null;
    let direction: CriteriaDeltaDirection = "unavailable";

    if (currentScore !== null && baselineScore !== null) {
      scoreDelta = roundOneDecimal(currentScore - baselineScore);
      if (scoreDelta >= DELTA_EPSILON) {
        direction = "improved";
        improvedCount += 1;
      } else if (scoreDelta <= -DELTA_EPSILON) {
        direction = "declined";
        declinedCount += 1;
      } else {
        scoreDelta = 0;
        direction = "unchanged";
        unchangedCount += 1;
      }
    }

    const sentimentChanged = Boolean(
      current &&
      baseline &&
      current.sentiment.trim().toUpperCase() !== baseline.sentiment.trim().toUpperCase(),
    );

    return {
      aspect: current?.aspect ?? baseline?.aspect ?? key,
      current,
      baseline,
      currentScore,
      baselineScore,
      scoreDelta,
      direction,
      sentimentChanged,
    };
  });

  const currentAvgScore = currentScores.length
    ? roundOneDecimal(currentScores.reduce((sum, val) => sum + val, 0) / currentScores.length)
    : null;
  const baselineAvgScore = baselineScores.length
    ? roundOneDecimal(baselineScores.reduce((sum, val) => sum + val, 0) / baselineScores.length)
    : null;
  const avgScoreDelta =
    currentAvgScore !== null && baselineAvgScore !== null
      ? roundOneDecimal(currentAvgScore - baselineAvgScore)
      : null;

  return {
    items,
    improvedCount,
    declinedCount,
    unchangedCount,
    currentAvgScore,
    baselineAvgScore,
    avgScoreDelta,
    reviewCountDelta: (currentAnalysis.review_count ?? 0) - (baselineAnalysis.review_count ?? 0),
  };
}

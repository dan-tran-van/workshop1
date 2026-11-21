import {
  BarChart3,
  History,
  Info,
  LayoutGrid,
  LoaderCircle,
  Minus,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import type { Analysis } from "../types/analysis";
import {
  formatAspectLabel,
  formatDelta,
  formatSnapshotDateShort,
  formatSnapshotOptionLabel,
  type AspectComparisonItem,
  type CriteriaComparisonSummary,
} from "../utils/criteriaComparison";

export type ComparisonViewMode = "cards" | "chart";

export function ComparisonToolbar({
  pastAnalyses,
  selectedBaselineId,
  onSelectBaseline,
  viewMode,
  onChangeViewMode,
  loading,
  error,
}: {
  pastAnalyses: Analysis[];
  selectedBaselineId: number | "none";
  onSelectBaseline: (value: number | "none") => void;
  viewMode: ComparisonViewMode;
  onChangeViewMode: (mode: ComparisonViewMode) => void;
  loading: boolean;
  error: string;
}) {
  if (loading) {
    return (
      <div className="comparison-hint" role="status">
        <LoaderCircle size={13} className="spin" />
        <span>Loading your past analysis runs...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="comparison-hint comparison-hint-error" role="status">
        <Info size={13} />
        <span>Your analysis history is unavailable: {error}</span>
      </div>
    );
  }

  if (!pastAnalyses.length) {
    return (
      <div className="comparison-hint" data-testid="comparison-single-snapshot">
        <History size={13} />
        <span>No past analysis runs in your history yet. Refresh analysis later to compare the 6 criteria over time.</span>
      </div>
    );
  }

  const isComparing = selectedBaselineId !== "none";

  return (
    <div className="comparison-toolbar" role="region" aria-label="Criteria comparison controls">
      <label className="comparison-picker">
        <span className="comparison-picker-label">
          <History size={13} />
          Compare with
        </span>
        <select
          className="comparison-select"
          aria-label="Compare with past analysis"
          value={selectedBaselineId === "none" ? "none" : String(selectedBaselineId)}
          onChange={(event) => {
            const value = event.target.value;
            onSelectBaseline(value === "none" ? "none" : Number(value));
          }}
        >
          {pastAnalyses.map((item, index) => (
            <option key={item.id} value={item.id}>
              {index === 0 ? `Previous · ${formatSnapshotOptionLabel(item)}` : formatSnapshotOptionLabel(item)}
            </option>
          ))}
          <option value="none">No comparison</option>
        </select>
      </label>

      {isComparing && (
        <div className="comparison-view-toggle" role="group" aria-label="Comparison view mode">
          <button
            type="button"
            className={`view-toggle-button${viewMode === "cards" ? " active" : ""}`}
            aria-pressed={viewMode === "cards"}
            onClick={() => onChangeViewMode("cards")}
          >
            <LayoutGrid size={12} />
            Cards
          </button>
          <button
            type="button"
            className={`view-toggle-button${viewMode === "chart" ? " active" : ""}`}
            aria-pressed={viewMode === "chart"}
            onClick={() => onChangeViewMode("chart")}
          >
            <BarChart3 size={12} />
            Chart
          </button>
        </div>
      )}
    </div>
  );
}

export function ComparisonSummaryStrip({
  summary,
  baseline,
}: {
  summary: CriteriaComparisonSummary;
  baseline: Analysis;
}) {
  const avgDirection =
    summary.avgScoreDelta === null
      ? "flat"
      : summary.avgScoreDelta >= 0.05
        ? "up"
        : summary.avgScoreDelta <= -0.05
          ? "down"
          : "flat";

  const reviewDeltaText =
    summary.reviewCountDelta > 0
      ? `+${summary.reviewCountDelta} reviews`
      : summary.reviewCountDelta < 0
        ? `${summary.reviewCountDelta} reviews`
        : "Same review count";

  return (
    <div className="comparison-summary-strip" role="region" aria-label="Criteria comparison summary">
      {summary.currentAvgScore !== null && summary.baselineAvgScore !== null && (
        <span className={`comparison-chip avg ${avgDirection}`}>
          {avgDirection === "up" && <TrendingUp size={12} />}
          {avgDirection === "down" && <TrendingDown size={12} />}
          {avgDirection === "flat" && <Minus size={12} />}
          Avg {summary.baselineAvgScore.toFixed(1)} → {summary.currentAvgScore.toFixed(1)} ({formatDelta(summary.avgScoreDelta)})
        </span>
      )}
      <span className="comparison-chip up">{summary.improvedCount} improved</span>
      <span className="comparison-chip down">{summary.declinedCount} declined</span>
      <span className="comparison-chip flat">{summary.unchangedCount} unchanged</span>
      <span className="comparison-meta-note">
        {reviewDeltaText} since {formatSnapshotDateShort(baseline.created_at)}
      </span>
    </div>
  );
}

export function AspectDeltaBadge({ comparison }: { comparison: AspectComparisonItem }) {
  if (comparison.baseline === null) {
    return <span className="aspect-delta delta-new">New</span>;
  }
  if (comparison.scoreDelta === null) {
    return <span className="aspect-delta delta-flat">—</span>;
  }
  const deltaText = formatDelta(comparison.scoreDelta);
  if (comparison.direction === "improved") {
    return (
      <span className="aspect-delta delta-up" aria-label={`Improved by ${deltaText}`}>
        <TrendingUp size={10} />
        {deltaText}
      </span>
    );
  }
  if (comparison.direction === "declined") {
    return (
      <span className="aspect-delta delta-down" aria-label={`Declined by ${deltaText}`}>
        <TrendingDown size={10} />
        {deltaText}
      </span>
    );
  }
  return (
    <span className="aspect-delta delta-flat" aria-label="Unchanged score">
      <Minus size={10} />
      {deltaText}
    </span>
  );
}

export function CriteriaComparisonChart({
  summary,
  current,
  baseline,
}: {
  summary: CriteriaComparisonSummary;
  current: Analysis;
  baseline: Analysis;
}) {
  const items = summary.items;
  const showRadar = items.length >= 3;

  const cx = 140;
  const cy = 118;
  const maxRadius = 72;
  const levels = [1, 2, 3, 4, 5];

  function pointAt(index: number, value: number, radiusScale = maxRadius) {
    const angle = -Math.PI / 2 + (2 * Math.PI * index) / items.length;
    const r = (Math.max(0, Math.min(5, value)) / 5) * radiusScale;
    return {
      x: cx + r * Math.cos(angle),
      y: cy + r * Math.sin(angle),
      angle,
    };
  }

  function polygonPoints(values: Array<number | null>): string {
    return values
      .map((val, index) => {
        const pt = pointAt(index, val ?? 0);
        return `${pt.x.toFixed(1)},${pt.y.toFixed(1)}`;
      })
      .join(" ");
  }

  return (
    <div className="comparison-chart-card" role="region" aria-label="6 criteria comparison chart">
      <div className="comparison-chart-legend">
        <span className="legend-item">
          <i className="legend-swatch current" />
          Current ({formatSnapshotDateShort(current.created_at)})
        </span>
        <span className="legend-item">
          <i className="legend-swatch baseline" />
          Past ({formatSnapshotDateShort(baseline.created_at)})
        </span>
      </div>

      <div className="comparison-chart-body">
        {showRadar && (
          <div className="radar-wrap">
            <svg
              className="criteria-radar-svg"
              viewBox="0 0 280 236"
              role="img"
              aria-label="Radar chart comparing current and past scores across 6 criteria"
            >
              <title>6 Criteria Comparison: Current vs Past</title>
              {levels.map((level) => (
                <polygon
                  key={level}
                  className="radar-grid"
                  points={items
                    .map((_, index) => {
                      const pt = pointAt(index, level);
                      return `${pt.x.toFixed(1)},${pt.y.toFixed(1)}`;
                    })
                    .join(" ")}
                />
              ))}

              {items.map((item, index) => {
                const end = pointAt(index, 5);
                const labelPos = pointAt(index, 5, maxRadius + 22);
                const cos = Math.cos(end.angle);
                const anchor = Math.abs(cos) < 0.2 ? "middle" : cos > 0 ? "start" : "end";
                return (
                  <g key={item.aspect}>
                    <line className="radar-axis" x1={cx} y1={cy} x2={end.x} y2={end.y} />
                    <text
                      className="radar-label"
                      x={labelPos.x}
                      y={labelPos.y + 3}
                      textAnchor={anchor}
                    >
                      {formatAspectLabel(item.aspect)}
                    </text>
                  </g>
                );
              })}

              <polygon
                className="radar-polygon-baseline"
                points={polygonPoints(items.map((item) => item.baselineScore))}
              />
              <polygon
                className="radar-polygon-current"
                points={polygonPoints(items.map((item) => item.currentScore))}
              />

              {items.map((item, index) => {
                if (item.currentScore === null) return null;
                const pt = pointAt(index, item.currentScore);
                return (
                  <circle
                    key={`dot-${item.aspect}`}
                    className="radar-dot-current"
                    cx={pt.x}
                    cy={pt.y}
                    r="3.2"
                  />
                );
              })}
            </svg>
          </div>
        )}

        <div className="paired-bars-list">
          {items.map((item) => {
            const currentScore = item.currentScore;
            const baselineScore = item.baselineScore;
            const barTone =
              currentScore === null
                ? "score-mid"
                : currentScore >= 4
                  ? "score-good"
                  : currentScore >= 3
                    ? "score-mid"
                    : "score-low";
            return (
              <div className="paired-bar-row" key={item.aspect}>
                <div className="paired-bar-head">
                  <strong>{formatAspectLabel(item.aspect)}</strong>
                  <div className="paired-bar-values">
                    <span className="paired-score-text">
                      {currentScore !== null ? currentScore.toFixed(1) : "—"}
                      <small> vs {baselineScore !== null ? baselineScore.toFixed(1) : "—"}</small>
                    </span>
                    <AspectDeltaBadge comparison={item} />
                  </div>
                </div>
                <div className="paired-tracks">
                  <div className="paired-track" title={`Current: ${currentScore !== null ? currentScore.toFixed(1) : "—"}/5`}>
                    <span className={barTone} style={{ width: `${(currentScore ?? 0) * 20}%` }} />
                  </div>
                  <div className="paired-track baseline" title={`Past: ${baselineScore !== null ? baselineScore.toFixed(1) : "—"}/5`}>
                    <span style={{ width: `${(baselineScore ?? 0) * 20}%` }} />
                  </div>
                </div>
                {item.sentimentChanged && item.current && item.baseline && (
                  <div className="paired-sentiment-shift">
                    Sentiment: {formatAspectLabel(item.baseline.sentiment)} → {formatAspectLabel(item.current.sentiment)}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

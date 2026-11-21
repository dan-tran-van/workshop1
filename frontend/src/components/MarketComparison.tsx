import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CircleHelp,
  Info,
  LoaderCircle,
  MapPin,
  Pin,
  PinOff,
  Plus,
  RefreshCw,
  RotateCcw,
  Search,
  Sparkles,
  Star,
  X,
} from "lucide-react";
import type {
  CompetitiveSet,
  CompetitorCandidate,
  CompetitorSelectionStatus,
  GapExplanation,
  GapRow,
  GapStatus,
  GapTable,
} from "../types/market";

type RequestFn = <T>(path: string, init?: RequestInit) => Promise<T>;
type GapSort = "default" | "behind-first" | "ahead-first";

const STATUS_LABELS: Record<GapStatus, string> = {
  LEARN: "Learn from rivals",
  KEEP: "Keep",
  ATTACK: "Attack opportunity",
  INSUFFICIENT_DATA: "Not enough data",
};

const STATUS_HINTS: Record<GapStatus, string> = {
  LEARN: "Competitors are doing better on this criterion.",
  KEEP: "You are level with or ahead of competitors.",
  ATTACK: "You lead and competitors are weak on this criterion.",
  INSUFFICIENT_DATA: "Too few reviews mention this criterion to draw a conclusion.",
};

function criterionLabel(aspect: string) {
  const label = aspect.replace(/_/g, " ");
  return label.charAt(0).toUpperCase() + label.slice(1);
}

function formatScore(value: number | null | undefined) {
  return value === null || value === undefined ? "—" : value.toFixed(1);
}

function formatGap(value: number | null) {
  if (value === null) return "—";
  const rounded = Math.round(value * 10) / 10;
  return `${rounded > 0 ? "+" : ""}${rounded.toFixed(1)}`;
}

function gapTone(row: GapRow, margin: number) {
  if (row.status === "INSUFFICIENT_DATA" || row.gap_vs_avg === null) return "gap-insufficient";
  if (row.gap_vs_avg < -margin) return "gap-behind";
  if (row.gap_vs_avg > margin) return "gap-ahead";
  return "gap-level";
}

export function MarketComparisonPage({
  restaurants,
  initialRestaurantId,
  request,
}: {
  restaurants: { id: number; name: string }[];
  initialRestaurantId: number | null;
  request: RequestFn;
}) {
  const [restaurantId, setRestaurantId] = useState<number | null>(initialRestaurantId ?? restaurants[0]?.id ?? null);
  const [competitiveSet, setCompetitiveSet] = useState<CompetitiveSet | null>(null);
  const [gapTable, setGapTable] = useState<GapTable | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [busyCompetitorId, setBusyCompetitorId] = useState<number | null>(null);
  const [sort, setSort] = useState<GapSort>("default");
  const [expandedAspect, setExpandedAspect] = useState<string | null>(null);
  const [explanations, setExplanations] = useState<Record<string, GapExplanation>>({});
  const [explainingAspect, setExplainingAspect] = useState<string | null>(null);
  const [explainError, setExplainError] = useState("");
  const [addOpen, setAddOpen] = useState(false);

  useEffect(() => {
    if (restaurantId === null || !restaurants.some((item) => item.id === restaurantId)) {
      setRestaurantId(initialRestaurantId ?? restaurants[0]?.id ?? null);
    }
  }, [initialRestaurantId, restaurantId, restaurants]);

  const resetExplanations = useCallback(() => {
    setExplanations({});
    setExpandedAspect(null);
    setExplainError("");
  }, []);

  const loadGap = useCallback(async (id: number) => {
    setGapTable(await request<GapTable>(`/restaurants/${id}/competitors/gap`));
  }, [request]);

  const load = useCallback(async (id: number) => {
    setLoading(true);
    setError("");
    resetExplanations();
    try {
      const [set, gap] = await Promise.all([
        request<CompetitiveSet>(`/restaurants/${id}/competitors`),
        request<GapTable>(`/restaurants/${id}/competitors/gap`),
      ]);
      setCompetitiveSet(set);
      setGapTable(gap);
    } catch (loadError) {
      setCompetitiveSet(null);
      setGapTable(null);
      setError(loadError instanceof Error ? loadError.message : "Unable to load the market comparison.");
    } finally {
      setLoading(false);
    }
  }, [request, resetExplanations]);

  useEffect(() => {
    if (restaurantId !== null) void load(restaurantId);
  }, [load, restaurantId]);

  async function changeSelection(competitorId: number, status: CompetitorSelectionStatus | null) {
    if (restaurantId === null) return;
    setBusyCompetitorId(competitorId);
    setError("");
    try {
      const path = `/restaurants/${restaurantId}/competitors/${competitorId}`;
      const updated = status === null
        ? await request<CompetitiveSet>(path, { method: "DELETE" })
        : await request<CompetitiveSet>(path, { method: "PUT", body: JSON.stringify({ status }) });
      setCompetitiveSet(updated);
      resetExplanations();
      await loadGap(restaurantId);
    } catch (updateError) {
      setError(updateError instanceof Error ? updateError.message : "Unable to update the competitive set.");
    } finally {
      setBusyCompetitorId(null);
    }
  }

  async function toggleExplanation(aspect: string) {
    if (restaurantId === null) return;
    if (expandedAspect === aspect) {
      setExpandedAspect(null);
      return;
    }
    setExpandedAspect(aspect);
    setExplainError("");
    if (explanations[aspect]) return;
    setExplainingAspect(aspect);
    try {
      const result = await request<GapExplanation>(`/restaurants/${restaurantId}/competitors/gap/${aspect}/explain`, { method: "POST" });
      setExplanations((current) => ({ ...current, [aspect]: result }));
    } catch (explainFailure) {
      setExplainError(explainFailure instanceof Error ? explainFailure.message : "Unable to explain this gap.");
    } finally {
      setExplainingAspect(null);
    }
  }

  const sortedRows = useMemo(() => {
    const rows = [...(gapTable?.rows ?? [])];
    if (sort === "default") return rows;
    const direction = sort === "behind-first" ? 1 : -1;
    return rows.sort((a, b) => {
      if (a.gap_vs_avg === null && b.gap_vs_avg === null) return 0;
      if (a.gap_vs_avg === null) return 1;
      if (b.gap_vs_avg === null) return -1;
      return direction * (a.gap_vs_avg - b.gap_vs_avg);
    });
  }, [gapTable, sort]);

  if (!restaurants.length) {
    return (
      <section className="panel market-panel">
        <div className="empty-state"><strong>No restaurants available</strong><p>Market comparison needs at least one restaurant assigned to your account.</p></div>
      </section>
    );
  }

  const canEdit = competitiveSet?.can_edit ?? false;
  const margin = gapTable?.tie_margin ?? 0.3;

  return (
    <div className="market-layout" data-testid="market-comparison">
      <section className="panel market-panel">
        <div className="panel-heading">
          <div><h2>Compare with the market</h2><p>Benchmark a restaurant against a suggested competitive set.</p></div>
          <div className="market-controls">
            <label className="comparison-picker">
              <span className="comparison-picker-label"><MapPin size={13} />Restaurant</span>
              <select className="comparison-select" aria-label="Restaurant to compare" value={restaurantId ?? ""} onChange={(event) => setRestaurantId(Number(event.target.value))}>
                {restaurants.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </label>
            <button type="button" className="button button-secondary" onClick={() => restaurantId !== null && void load(restaurantId)} disabled={loading}>
              {loading ? <LoaderCircle size={15} className="spin" /> : <RefreshCw size={15} />} Refresh suggestions
            </button>
          </div>
        </div>
        {competitiveSet && (
          <ul className="market-limitations" aria-label="Data limitations">
            {competitiveSet.data_limitations.map((item) => <li key={item}><Info size={12} />{item}</li>)}
          </ul>
        )}
      </section>

      {error && <div className="error-banner market-banner"><CircleHelp size={16} /><span>{error}</span></div>}
      {loading && !competitiveSet && <div className="loading-state"><LoaderCircle size={19} className="spin" /><span>Loading market comparison...</span></div>}

      {competitiveSet && (
        <section className="panel market-panel" aria-labelledby="competitive-set-title">
          <div className="panel-heading">
            <div>
              <h2 id="competitive-set-title">Competitive set</h2>
              <p>{competitiveSet.competitors.length} competitors · {competitiveSet.scored_competitor_count} with collected reviews{canEdit ? " · Pin to keep, dismiss to stop suggesting" : " · View only"}</p>
            </div>
            {canEdit && <button type="button" className="button button-secondary" onClick={() => setAddOpen(true)}><Plus size={14} /> Add competitor</button>}
          </div>
          {competitiveSet.notice && <div className="notice-banner notice-info market-banner" role="status"><Info size={16} /><span>{competitiveSet.notice}</span></div>}
          {competitiveSet.competitors.length ? (
            <div className="table-wrap">
              <table className="market-table">
                <thead><tr><th>Competitor</th><th>Distance</th><th>Rating</th><th>Reviews</th><th>Cuisine</th><th>Why suggested</th>{canEdit && <th><span className="sr-only">Actions</span></th>}</tr></thead>
                <tbody>
                  {competitiveSet.competitors.map((competitor) => {
                    const kept = competitor.source !== "SUGGESTED";
                    const busy = busyCompetitorId === competitor.restaurant_id;
                    return (
                      <tr key={competitor.restaurant_id} data-testid="competitor-row">
                        <td>
                          <strong className="market-name">{competitor.name}</strong>
                          {kept && <span className="market-source">{competitor.source === "PINNED" ? "Pinned" : "Added manually"}</span>}
                        </td>
                        <td className="muted">{competitor.distance_m === null ? "Not available" : `${Math.round(competitor.distance_m)} m`}</td>
                        <td>{competitor.google_rating === null ? "—" : <span className="market-rating"><Star size={12} />{competitor.google_rating.toFixed(1)}</span>}</td>
                        <td>{(competitor.user_rating_count ?? 0).toLocaleString()} <span className="muted">Google · {competitor.collected_review_count.toLocaleString()} collected</span></td>
                        <td className="muted">{competitor.cuisine ?? "Not available"}</td>
                        <td><ul className="market-reasons">{competitor.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul></td>
                        {canEdit && (
                          <td>
                            <div className="table-row-actions">
                              {kept ? (
                                <button type="button" className="text-button" disabled={busy} onClick={() => void changeSelection(competitor.restaurant_id, null)} aria-label={`Unpin ${competitor.name}`}><PinOff size={13} /> Unpin</button>
                              ) : (
                                <button type="button" className="text-button" disabled={busy} onClick={() => void changeSelection(competitor.restaurant_id, "PINNED")} aria-label={`Pin ${competitor.name}`}><Pin size={13} /> Pin</button>
                              )}
                              <button type="button" className="text-button market-dismiss" disabled={busy} onClick={() => void changeSelection(competitor.restaurant_id, "DISMISSED")} aria-label={`Dismiss ${competitor.name}`}><X size={13} /> Dismiss</button>
                            </div>
                          </td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="empty-state"><strong>No competitors found</strong><p>There are no other restaurants to compare with yet.</p></div>
          )}
          {competitiveSet.dismissed.length > 0 && (
            <div className="market-dismissed">
              <span>Dismissed ({competitiveSet.dismissed.length}):</span>
              {competitiveSet.dismissed.map((item) => (
                <span key={item.restaurant_id} className="comparison-chip">
                  {item.name}
                  {canEdit && <button type="button" className="text-button" disabled={busyCompetitorId === item.restaurant_id} onClick={() => void changeSelection(item.restaurant_id, null)} aria-label={`Restore ${item.name}`}><RotateCcw size={12} /> Restore</button>}
                </span>
              ))}
            </div>
          )}
        </section>
      )}

      {gapTable && (
        <section className="panel market-panel" aria-labelledby="gap-table-title">
          <div className="panel-heading">
            <div>
              <h2 id="gap-table-title">Criteria gap</h2>
              <p>Each score is the average star rating (1–5) of reviews that mention the criterion. A criterion needs at least {gapTable.min_reviews_per_criterion} mentions. Compared with {gapTable.competitors_considered} competitors.</p>
            </div>
            <label className="comparison-picker market-sort">
              <span className="comparison-picker-label">Sort</span>
              <select className="comparison-select" aria-label="Sort criteria" value={sort} onChange={(event) => setSort(event.target.value as GapSort)}>
                <option value="default">Default order</option>
                <option value="behind-first">Most behind first</option>
                <option value="ahead-first">Most ahead first</option>
              </select>
            </label>
          </div>
          <div className="table-wrap">
            <table className="market-table gap-table">
              <thead><tr><th>Criterion</th><th>You</th><th>Competitor avg</th><th>Leader</th><th>Gap vs avg</th><th>Label</th><th><span className="sr-only">Explanation</span></th></tr></thead>
              <tbody>
                {sortedRows.map((row) => {
                  const insufficient = row.status === "INSUFFICIENT_DATA";
                  const expanded = expandedAspect === row.aspect;
                  const explanation = explanations[row.aspect];
                  return [
                    <tr key={row.aspect} className={gapTone(row, margin)} data-testid={`gap-row-${row.aspect}`}>
                      <td><strong>{criterionLabel(row.aspect)}</strong></td>
                      <td>{formatScore(row.own_score)} <span className="muted">({row.own_mentions} mentions)</span></td>
                      <td>{formatScore(row.competitor_avg)} <span className="muted">({row.competitors_scored} scored)</span></td>
                      <td>{row.leader ? <>{formatScore(row.leader.score)} <span className="muted">{row.leader.name}</span></> : "—"}</td>
                      <td className="gap-value">{formatGap(row.gap_vs_avg)}</td>
                      <td><span className={`gap-label gap-label-${row.status.toLowerCase()}`} title={STATUS_HINTS[row.status]}>{STATUS_LABELS[row.status]}</span></td>
                      <td>
                        {insufficient ? (
                          <span className="muted gap-warning">{row.insufficient_reason}</span>
                        ) : (
                          <button type="button" className="text-button" aria-expanded={expanded} onClick={() => void toggleExplanation(row.aspect)}>
                            <Sparkles size={13} /> {expanded ? "Hide" : "Why?"}
                          </button>
                        )}
                      </td>
                    </tr>,
                    expanded && (
                      <tr key={`${row.aspect}-explanation`} className="gap-explanation-row">
                        <td colSpan={7}>
                          {explainingAspect === row.aspect && <div className="loading-state"><LoaderCircle size={16} className="spin" /><span>Explaining the gap from reviews...</span></div>}
                          {explainError && explainingAspect === null && !explanation && <div className="error-banner"><CircleHelp size={16} /><span>{explainError}</span></div>}
                          {explanation && (
                            <div className="gap-explanation">
                              <p><Sparkles size={13} /> {explanation.explanation}</p>
                              <ul className="gap-evidence">
                                {explanation.evidence.map((item) => (
                                  <li key={item.review_id}>
                                    <span className="gap-evidence-source">{item.is_own ? "Your guest" : item.restaurant_name} · {item.rating.toFixed(1)}★</span>
                                    <q>{item.text}</q>
                                  </li>
                                ))}
                              </ul>
                              <span className="muted gap-model">Source: {explanation.model.startsWith("heuristic") ? "rule-based summary of collected reviews" : `AI (${explanation.model}) grounded in the quoted reviews`}</span>
                            </div>
                          )}
                        </td>
                      </tr>
                    ),
                  ];
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {addOpen && restaurantId !== null && (
        <AddCompetitorDialog
          restaurantId={restaurantId}
          request={request}
          onClose={() => setAddOpen(false)}
          onAdd={async (competitorId) => {
            await changeSelection(competitorId, "MANUAL");
            setAddOpen(false);
          }}
        />
      )}
    </div>
  );
}

function AddCompetitorDialog({ restaurantId, request, onClose, onAdd }: {
  restaurantId: number;
  request: RequestFn;
  onClose: () => void;
  onAdd: (competitorId: number) => Promise<void>;
}) {
  const [query, setQuery] = useState("");
  const [candidates, setCandidates] = useState<CompetitorCandidate[]>([]);
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState<number | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setLoading(true);
      setError("");
      request<CompetitorCandidate[]>(`/restaurants/${restaurantId}/competitors/candidates?limit=20${query.trim() ? `&q=${encodeURIComponent(query.trim())}` : ""}`)
        .then(setCandidates)
        .catch((loadError: unknown) => setError(loadError instanceof Error ? loadError.message : "Unable to load restaurants."))
        .finally(() => setLoading(false));
    }, query ? 250 : 0);
    return () => window.clearTimeout(timer);
  }, [query, request, restaurantId]);

  return (
    <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="add-dialog" role="dialog" aria-modal="true" aria-labelledby="add-competitor-title">
        <div className="dialog-heading">
          <div><span className="section-kicker">COMPETITIVE SET</span><h2 id="add-competitor-title">Add a competitor</h2><p>Choose a restaurant already in the workspace. Searching Google Maps is not available yet.</p></div>
          <button type="button" className="quiet-icon-button" aria-label="Close dialog" onClick={onClose}>×</button>
        </div>
        <label className="search-field market-search"><Search size={14} /><input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search by name or address" aria-label="Search restaurants" /></label>
        {error && <div className="error-banner"><CircleHelp size={16} /><span>{error}</span></div>}
        {loading ? (
          <div className="loading-state"><LoaderCircle size={16} className="spin" /><span>Loading restaurants...</span></div>
        ) : candidates.length ? (
          <ul className="market-candidates">
            {candidates.map((candidate) => (
              <li key={candidate.restaurant_id}>
                <div><strong>{candidate.name}</strong><span className="muted">{candidate.address ?? "No address"} · {candidate.collected_review_count} collected reviews</span></div>
                <button type="button" className="button button-secondary" disabled={adding !== null} onClick={async () => { setAdding(candidate.restaurant_id); await onAdd(candidate.restaurant_id); setAdding(null); }}>
                  {adding === candidate.restaurant_id ? <LoaderCircle size={14} className="spin" /> : <Plus size={14} />} Add
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="empty-inline">No matching restaurants that are not already in your competitive set.</p>
        )}
      </section>
    </div>
  );
}

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  Clock3,
  Filter,
  LayoutDashboard,
  LoaderCircle,
  MapPin,
  MessageSquareText,
  MoreHorizontal,
  Plus,
  RefreshCw,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  Star,
  Store,
  ThumbsUp,
  TrendingDown,
  TrendingUp,
  Utensils,
  Waves,
  Zap,
} from "lucide-react";

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

type Restaurant = {
  id: number;
  google_place_id: string;
  name: string;
  address: string | null;
  google_rating: number | null;
  user_rating_count: number | null;
  last_synced_at: string | null;
  updated_at: string | null;
  review_count: number;
};

type Review = {
  id: number;
  restaurant_id: number;
  author_name: string;
  author_uri: string | null;
  rating: number;
  text: string;
  published_at: string;
};

type Aspect = {
  aspect: string;
  sentiment: string;
  score: number | null;
  summary: string;
  highlights: string[];
};

type Improvement = {
  priority: string;
  aspect: string;
  issue: string;
  recommended_action: string;
  expected_impact: string;
};

type Strength = {
  aspect: string;
  strength: string;
  marketing_tip: string | null;
};

type AnalysisResult = {
  overall_sentiment: string;
  summary: string;
  estimated_rating_trend: string;
  aspect_breakdown: Aspect[];
  prioritized_improvements: Improvement[];
  strengths_to_keep: Strength[];
};

type Analysis = {
  id: number;
  restaurant_id: number;
  overall_sentiment: string;
  result_json: AnalysisResult;
  review_count: number;
  last_review_at: string | null;
  model: string;
  created_at: string;
};

type RestaurantDetail = Restaurant & {
  reviews: Review[];
  latest_analysis: Analysis | null;
};

type SyncTarget = {
  id: number;
  target_type: string;
  value: string;
  language_code: string;
  is_active: boolean;
  last_synced_at: string | null;
};

type SyncRun = {
  id: number;
  status: string;
  started_at: string;
  finished_at: string | null;
  restaurants_upserted: number;
  reviews_upserted: number;
  error_message: string | null;
};

type Page = "overview" | "restaurants" | "insights" | "sync";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      message = typeof body.detail === "string" ? body.detail : message;
    } catch {
      // Keep the HTTP status message when the server does not return JSON.
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

function formatDate(value: string | null | undefined) {
  if (!value) return "Not synced yet";
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", year: "numeric" }).format(new Date(value));
}

function timeAgo(value: string | null | undefined) {
  if (!value) return "No recent activity";
  const days = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 86_400_000));
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 7) return `${days} days ago`;
  if (days < 30) return `${Math.floor(days / 7)} weeks ago`;
  return formatDate(value);
}

function titleCase(value: string) {
  return value.replace(/_/g, " ").toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function App() {
  const [page, setPage] = useState<Page>("overview");
  const [restaurants, setRestaurants] = useState<Restaurant[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<RestaurantDetail | null>(null);
  const [search, setSearch] = useState("");
  const [loadingRestaurants, setLoadingRestaurants] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [restaurantError, setRestaurantError] = useState("");
  const [detailError, setDetailError] = useState("");
  const [apiConnected, setApiConnected] = useState<boolean | null>(null);
  const [syncTargets, setSyncTargets] = useState<SyncTarget[]>([]);
  const [syncRuns, setSyncRuns] = useState<SyncRun[]>([]);
  const [syncLoading, setSyncLoading] = useState(false);
  const [syncRunning, setSyncRunning] = useState(false);
  const [syncError, setSyncError] = useState("");
  const [syncNotice, setSyncNotice] = useState("");
  const [addTargetOpen, setAddTargetOpen] = useState(false);
  const [addTargetError, setAddTargetError] = useState("");
  const [addingTarget, setAddingTarget] = useState(false);
  const [sortBy, setSortBy] = useState<"rating" | "reviews">("rating");
  const [addRestaurantOpen, setAddRestaurantOpen] = useState(false);
  const [addRestaurantError, setAddRestaurantError] = useState("");
  const [addingRestaurant, setAddingRestaurant] = useState(false);

  const loadRestaurants = useCallback(async (query: string, signal?: AbortSignal) => {
    setLoadingRestaurants(true);
    setRestaurantError("");
    try {
      const items = await request<Restaurant[]>(`/restaurants?limit=100${query ? `&q=${encodeURIComponent(query)}` : ""}`, { signal });
      setRestaurants(items);
      setSelectedId((current) => items.some((item) => item.id === current) ? current : items[0]?.id ?? null);
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setRestaurantError(error instanceof Error ? error.message : "Unable to load restaurants.");
    } finally {
      if (!signal?.aborted) setLoadingRestaurants(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => void loadRestaurants(search.trim(), controller.signal), search ? 250 : 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [loadRestaurants, search]);

  const checkApiConnection = useCallback(async () => {
    try {
      await request<{ status: string }>("/health");
      setApiConnected(true);
    } catch {
      setApiConnected(false);
    }
  }, []);

  useEffect(() => {
    void checkApiConnection();
  }, [checkApiConnection]);

  useEffect(() => {
    if (selectedId === null) {
      setDetail(null);
      return;
    }
    const controller = new AbortController();
    setLoadingDetail(true);
    setDetailError("");
    request<RestaurantDetail>(`/restaurants/${selectedId}`, { signal: controller.signal })
      .then(setDetail)
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setDetailError(error instanceof Error ? error.message : "Unable to load restaurant details.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoadingDetail(false);
      });
    return () => controller.abort();
  }, [selectedId]);

  const loadSyncData = useCallback(async () => {
    setSyncLoading(true);
    setSyncError("");
    try {
      const [targets, runs] = await Promise.all([
        request<SyncTarget[]>("/sync/targets"),
        request<SyncRun[]>("/sync/runs?limit=20"),
      ]);
      setSyncTargets(targets);
      setSyncRuns(runs);
    } catch (error) {
      setSyncError(error instanceof Error ? error.message : "Unable to load sync data.");
    } finally {
      setSyncLoading(false);
    }
  }, []);

  useEffect(() => {
    if (page === "sync") void loadSyncData();
  }, [loadSyncData, page]);

  const sortedRestaurants = useMemo(() => [...restaurants].sort((a, b) => {
    if (sortBy === "reviews") return (b.review_count ?? 0) - (a.review_count ?? 0);
    return (b.google_rating ?? 0) - (a.google_rating ?? 0);
  }), [restaurants, sortBy]);

  const averageRating = restaurants.length
    ? restaurants.reduce((sum, item) => sum + (item.google_rating ?? 0), 0) / restaurants.filter((item) => item.google_rating !== null).length
    : 0;
  const totalReviews = restaurants.reduce((sum, item) => sum + (item.review_count ?? 0), 0);
  const lastSynced = restaurants
    .map((item) => item.last_synced_at)
    .filter((value): value is string => Boolean(value))
    .sort((a, b) => new Date(b).getTime() - new Date(a).getTime())[0] ?? null;
  const analysis = detail?.latest_analysis?.result_json;

  async function runAnalysis(forceRefresh = false) {
    if (!selectedId) return;
    setAnalyzing(true);
    setDetailError("");
    try {
      const result = await request<Analysis>(`/restaurants/${selectedId}/analyze`, {
        method: "POST",
        body: JSON.stringify({ force_refresh: forceRefresh }),
      });
      setDetail((current) => current ? { ...current, latest_analysis: result } : current);
    } catch (error) {
      setDetailError(error instanceof Error ? error.message : "Unable to analyze reviews.");
    } finally {
      setAnalyzing(false);
    }
  }

  async function runSync() {
    setSyncRunning(true);
    setSyncError("");
    setSyncNotice("");
    try {
      const run = await request<SyncRun>("/sync/run", { method: "POST" });
      setSyncNotice(run.status === "FAILED"
        ? run.error_message || "The sync job failed."
        : `Sync ${run.status.toLowerCase()}: ${run.restaurants_upserted} restaurants and ${run.reviews_upserted} reviews updated.`);
      await Promise.all([loadSyncData(), loadRestaurants(search.trim())]);
    } catch (error) {
      setSyncError(error instanceof Error ? error.message : "Unable to start sync.");
    } finally {
      setSyncRunning(false);
    }
  }

  async function createSyncTarget(value: string, languageCode: string) {
    setAddingTarget(true);
    setAddTargetError("");
    try {
      await request<SyncTarget>("/sync/targets", {
        method: "POST",
        body: JSON.stringify({ target_type: "place_id", value: value.trim(), language_code: languageCode, is_active: true }),
      });
      setAddTargetOpen(false);
      setSyncNotice("Google Place ID added as an active sync target.");
      await loadSyncData();
    } catch (error) {
      setAddTargetError(error instanceof Error ? error.message : "Unable to add this sync target.");
    } finally {
      setAddingTarget(false);
    }
  }

  async function createRestaurant(form: { google_place_id: string; name: string; address: string; google_rating: string; user_rating_count: string }) {
    setAddingRestaurant(true);
    setAddRestaurantError("");
    try {
      const created = await request<Restaurant>("/restaurants", {
        method: "POST",
        body: JSON.stringify({
          google_place_id: form.google_place_id.trim(),
          name: form.name.trim(),
          address: form.address.trim() || null,
          google_rating: form.google_rating ? Number(form.google_rating) : null,
          user_rating_count: form.user_rating_count ? Number(form.user_rating_count) : null,
        }),
      });
      setAddRestaurantOpen(false);
      setSearch("");
      setPage("restaurants");
      setSelectedId(created.id);
      await loadRestaurants("");
      setSelectedId(created.id);
    } catch (error) {
      setAddRestaurantError(error instanceof Error ? error.message : "Unable to add this restaurant.");
    } finally {
      setAddingRestaurant(false);
    }
  }

  const pageTitles: Record<Page, { title: string; subtitle: string }> = {
    overview: { title: "Good morning", subtitle: "Here’s what your guests are saying." },
    restaurants: { title: "Restaurants", subtitle: "Explore locations and understand every guest experience." },
    insights: { title: "Review insights", subtitle: "Turn customer feedback into your next best move." },
    sync: { title: "Data sync", subtitle: "Manage Google Maps review collection and sync activity." },
  };
  const todayLabel = new Intl.DateTimeFormat("en", { weekday: "long", month: "long", day: "numeric" }).format(new Date()).toUpperCase();

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#" onClick={(event) => { event.preventDefault(); setPage("overview"); }}>
          <span className="brand-mark"><Waves size={21} strokeWidth={2.5} /></span>
          <span className="brand-name">gather<span>.</span></span>
        </a>
        <div className="workspace-switcher">
          <div className="workspace-avatar">H</div>
          <div className="workspace-copy"><strong>Hearth &amp; Honey</strong><span>Workspace</span></div>
          <ChevronDown size={15} className="muted-icon" />
        </div>
        <div className="nav-section-label">WORKSPACE</div>
        <nav className="main-nav" aria-label="Main navigation">
          <NavItem active={page === "overview"} onClick={() => setPage("overview")} icon={<LayoutDashboard size={18} />} label="Overview" />
          <NavItem active={page === "restaurants"} onClick={() => setPage("restaurants")} icon={<Store size={18} />} label="Restaurants" count={restaurants.length} />
          <NavItem active={page === "insights"} onClick={() => setPage("insights")} icon={<BarChart3 size={18} />} label="Review insights" />
          <NavItem active={page === "sync"} onClick={() => setPage("sync")} icon={<RefreshCw size={17} />} label="Data sync" />
        </nav>
        <div className="sidebar-bottom">
          <div className="help-card">
            <span className="help-icon"><CircleHelp size={17} /></span>
            <strong>Need a hand?</strong>
            <p>Get the most out of your guest insights.</p>
            <button type="button" className="help-link" onClick={() => window.open(`${API_BASE}/docs`, "_blank", "noopener,noreferrer")}>Explore API docs <ArrowRight size={13} /></button>
          </div>
          <button type="button" className="profile-button">
            <span className="profile-avatar">AM</span>
            <span className="profile-copy"><strong>Alex Morgan</strong><span>Restaurant owner</span></span>
            <MoreHorizontal size={19} className="muted-icon" />
          </button>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div className="breadcrumbs"><span>Workspace</span><ChevronRight size={14} /><strong>{pageTitles[page].title}</strong></div>
          <div className="topbar-actions">
            <span className={`sync-status${apiConnected === false ? " disconnected" : ""}`}><span className="status-dot" /> {apiConnected === null ? "Connecting to API" : apiConnected ? "API connected" : "API unavailable"}</span>
            <button type="button" className="icon-button" aria-label="Settings"><Settings2 size={18} /></button>
            <button type="button" className="top-avatar" aria-label="User profile">AM</button>
          </div>
        </header>

        <div className="page-container">
          <section className="page-heading">
            <div>
              <div className="eyebrow">{page === "overview" ? todayLabel : "YOUR BUSINESS"}</div>
              <h1>{pageTitles[page].title}{page === "overview" && <span className="heading-period">, Alex</span>}</h1>
              <p>{pageTitles[page].subtitle}</p>
            </div>
            <div className="heading-actions">
              <button type="button" className="button button-secondary" onClick={() => { void checkApiConnection(); page === "sync" ? void loadSyncData() : void loadRestaurants(search.trim()); }}>
                <RefreshCw size={15} /> Refresh
              </button>
              <button type="button" className="button button-primary" onClick={() => { setAddRestaurantError(""); setAddRestaurantOpen(true); }}><Plus size={16} /> Add restaurant</button>
            </div>
          </section>

          {(page === "overview" || page === "restaurants") && (
            <RestaurantWorkspace
              restaurants={sortedRestaurants}
              detail={detail}
              analysis={analysis}
              selectedId={selectedId}
              search={search}
              sortBy={sortBy}
              loadingRestaurants={loadingRestaurants}
              loadingDetail={loadingDetail}
              analyzing={analyzing}
              restaurantError={restaurantError}
              detailError={detailError}
              averageRating={averageRating}
              totalReviews={totalReviews}
              lastSynced={lastSynced}
              onSearch={setSearch}
              onSort={setSortBy}
              onSelect={setSelectedId}
              onAnalyze={runAnalysis}
              onGoToRestaurants={() => setPage("restaurants")}
            />
          )}

          {page === "insights" && (
            <InsightsPage
              restaurants={restaurants}
              detail={detail}
              loading={loadingDetail}
              error={detailError}
              onSelect={(id) => { setSelectedId(id); setPage("overview"); }}
              onAnalyze={runAnalysis}
              analyzing={analyzing}
            />
          )}

          {page === "sync" && (
            <SyncPage
              targets={syncTargets}
              runs={syncRuns}
              loading={syncLoading}
              running={syncRunning}
              error={syncError}
              notice={syncNotice}
              onRun={runSync}
              onRefresh={() => void loadSyncData()}
              onAddTarget={() => { setAddTargetError(""); setAddTargetOpen(true); }}
            />
          )}
        </div>
      </main>
      {addRestaurantOpen && <AddRestaurantDialog error={addRestaurantError} loading={addingRestaurant} onClose={() => setAddRestaurantOpen(false)} onSubmit={createRestaurant} />}
      {addTargetOpen && <AddSyncTargetDialog error={addTargetError} loading={addingTarget} onClose={() => setAddTargetOpen(false)} onSubmit={createSyncTarget} />}
    </div>
  );
}

function NavItem({ active, onClick, icon, label, count }: { active: boolean; onClick: () => void; icon: React.ReactNode; label: string; count?: number }) {
  return (
    <button type="button" className={`nav-item${active ? " active" : ""}`} onClick={onClick}>
      {icon}<span>{label}</span>{count !== undefined && <span className="nav-count">{count}</span>}
    </button>
  );
}

function RestaurantWorkspace(props: {
  restaurants: Restaurant[];
  detail: RestaurantDetail | null;
  analysis: AnalysisResult | undefined;
  selectedId: number | null;
  search: string;
  sortBy: "rating" | "reviews";
  loadingRestaurants: boolean;
  loadingDetail: boolean;
  analyzing: boolean;
  restaurantError: string;
  detailError: string;
  averageRating: number;
  totalReviews: number;
  lastSynced: string | null;
  onSearch: (value: string) => void;
  onSort: (value: "rating" | "reviews") => void;
  onSelect: (id: number) => void;
  onAnalyze: (refresh?: boolean) => void;
  onGoToRestaurants: () => void;
}) {
  const isOverview = props.search === "" && props.restaurants.length > 0;
  return (
    <>
      {isOverview && (
        <section className="stats-grid" aria-label="Business overview">
          <StatCard label="Total restaurants" value={String(props.restaurants.length).padStart(2, "0")} icon={<Store size={18} />} tint="mint" change="Across your workspace" />
          <StatCard label="Guest reviews" value={props.totalReviews.toLocaleString()} icon={<MessageSquareText size={18} />} tint="lavender" change="Collected so far" />
          <StatCard label="Average rating" value={props.averageRating ? props.averageRating.toFixed(1) : "—"} icon={<Star size={18} fill="currentColor" />} tint="peach" change="Across all locations" />
          <StatCard label="Last data sync" value={timeAgo(props.lastSynced)} icon={<RefreshCw size={18} />} tint="blue" change="Across your locations" />
        </section>
      )}
      <section className={`content-grid${isOverview ? "" : " content-grid-tall"}`}>
        <div className="panel restaurants-panel">
          <div className="panel-heading">
            <div><h2>{isOverview ? "Your restaurants" : "All restaurants"}</h2><p>{props.restaurants.length} locations in your workspace</p></div>
            <button type="button" className="text-button" onClick={props.onGoToRestaurants}>View all <ArrowRight size={14} /></button>
          </div>
          <div className="restaurant-tools">
            <label className="search-field">
              <Search size={16} />
              <input value={props.search} onChange={(event) => props.onSearch(event.target.value)} placeholder="Search restaurants..." aria-label="Search restaurants" />
              {props.search && <button type="button" aria-label="Clear search" onClick={() => props.onSearch("")}>×</button>}
            </label>
            <button type="button" className="filter-button" onClick={() => props.onSort(props.sortBy === "rating" ? "reviews" : "rating")}><Filter size={15} /> Sort: {props.sortBy === "rating" ? "Rating" : "Reviews"} <ChevronDown size={14} /></button>
          </div>
          {props.restaurantError && <ErrorBanner message={props.restaurantError} />}
          <div className="restaurant-list">
            {props.loadingRestaurants ? <LoadingState label="Loading restaurants..." /> :
              props.restaurants.length ? props.restaurants.map((restaurant) => (
                <button type="button" className={`restaurant-row${restaurant.id === props.selectedId ? " selected" : ""}`} key={restaurant.id} onClick={() => props.onSelect(restaurant.id)}>
                  <RestaurantAvatar name={restaurant.name} />
                  <span className="restaurant-row-copy">
                    <strong>{restaurant.name}</strong>
                    <span><MapPin size={12} />{restaurant.address || "Address not available"}</span>
                  </span>
                  <span className="restaurant-row-rating"><Star size={14} fill="currentColor" />{restaurant.google_rating?.toFixed(1) ?? "—"}</span>
                  <span className="restaurant-row-reviews">{restaurant.review_count ?? 0} reviews</span>
                  <ChevronRight className="row-chevron" size={16} />
                </button>
              )) : !props.restaurantError && <EmptyState title={props.search ? "No restaurants found" : "No restaurants yet"} description={props.search ? "Try a different name or address." : "Your synced locations will appear here."} />}
          </div>
          <div className="panel-footer">
            <span>Showing <strong>{props.restaurants.length}</strong> locations</span>
            <div className="pagination"><button type="button" disabled aria-label="Previous page"><ChevronLeft size={15} /></button><span>1</span><button type="button" disabled aria-label="Next page"><ChevronRight size={15} /></button></div>
          </div>
        </div>

        <section className="panel detail-panel" aria-live="polite">
          {props.loadingDetail ? <LoadingState label="Loading restaurant details..." /> :
            props.detailError ? <ErrorBanner message={props.detailError} /> :
              props.detail ? <RestaurantDetails detail={props.detail} analysis={props.analysis} analyzing={props.analyzing} onAnalyze={props.onAnalyze} /> :
                <EmptyState title="Choose a restaurant" description="Select a location to see its reviews and insights." />}
        </section>
      </section>
    </>
  );
}

function StatCard({ label, value, icon, tint, change }: { label: string; value: string; icon: React.ReactNode; tint: string; change: string }) {
  return (
    <article className="stat-card">
      <div className={`stat-icon ${tint}`}>{icon}</div>
      <span className="stat-label">{label}</span>
      <div className="stat-bottom"><strong>{value}</strong><span>{change}</span></div>
    </article>
  );
}

function RestaurantAvatar({ name, large = false }: { name: string; large?: boolean }) {
  const initial = name.trim().charAt(0).toUpperCase() || "R";
  const tone = ["tone-sage", "tone-peach", "tone-violet", "tone-gold"][name.length % 4];
  return <span className={`restaurant-avatar ${tone}${large ? " large" : ""}`}><Utensils size={large ? 22 : 17} strokeWidth={1.8} /><span>{initial}</span></span>;
}

function RestaurantDetails({ detail, analysis, analyzing, onAnalyze }: { detail: RestaurantDetail; analysis: AnalysisResult | undefined; analyzing: boolean; onAnalyze: (refresh?: boolean) => void }) {
  const reviews = detail.reviews ?? [];
  return (
    <div className="detail-content">
      <div className="detail-hero">
        <RestaurantAvatar name={detail.name} large />
        <div className="detail-title">
          <div className="detail-name-line"><h2>{detail.name}</h2><button type="button" className="quiet-icon-button" aria-label="More restaurant options"><MoreHorizontal size={19} /></button></div>
          <div className="detail-address"><MapPin size={14} />{detail.address || "Address not available"}</div>
          <div className="detail-meta"><span><Star size={15} fill="currentColor" /> <strong>{detail.google_rating?.toFixed(1) ?? "—"}</strong> <span className="muted">Google rating</span></span><i /><span>{detail.user_rating_count?.toLocaleString() ?? 0} total ratings</span></div>
        </div>
      </div>
      <div className="detail-action-row">
        <div className="updated-note"><span className="status-dot" /> Synced {timeAgo(detail.last_synced_at)}</div>
        <button type="button" className="button button-primary analyze-button" onClick={() => onAnalyze(Boolean(detail.latest_analysis))} disabled={analyzing}>
          {analyzing ? <LoaderCircle size={15} className="spin" /> : <Sparkles size={15} />}
          {analyzing ? "Analyzing..." : detail.latest_analysis ? "Refresh analysis" : "Analyze reviews"}
        </button>
      </div>

      {analysis ? (
        <div className="analysis-section">
          <div className="section-title-row"><div><div className="section-kicker"><Sparkles size={13} /> AI REVIEW ANALYSIS</div><h3>At a glance</h3></div><span className={`sentiment-pill ${sentimentClass(analysis.overall_sentiment)}`}>{titleCase(analysis.overall_sentiment)}</span></div>
          <p className="analysis-summary">{analysis.summary}</p>
          <div className="trend-line"><span className={`trend-badge ${analysis.estimated_rating_trend.toLowerCase()}`}><TrendIcon trend={analysis.estimated_rating_trend} />{titleCase(analysis.estimated_rating_trend)}</span><span>Estimated rating trend</span><span className="trend-spacer" /><span className="analysis-count">Based on {detail.latest_analysis?.review_count ?? reviews.length} reviews</span></div>
          <div className="aspects-grid">
            {(analysis.aspect_breakdown ?? []).slice(0, 6).map((aspect) => <AspectCard key={aspect.aspect} aspect={aspect} />)}
            {!analysis.aspect_breakdown?.length && <p className="empty-inline">Not enough review data for an aspect breakdown yet.</p>}
          </div>
          {analysis.prioritized_improvements?.length > 0 && <div className="recommendations">
            <div className="section-title-row compact"><div><div className="section-kicker"><Zap size={13} /> WHAT TO FOCUS ON</div><h3>Room to improve</h3></div><span className="tiny-count">{analysis.prioritized_improvements.length} suggestions</span></div>
            {analysis.prioritized_improvements.slice(0, 2).map((item, index) => <ImprovementCard key={`${item.aspect}-${index}`} item={item} />)}
          </div>}
          {analysis.strengths_to_keep?.length > 0 && <div className="strengths-block">
            <div className="strength-heading"><span className="strength-icon"><ThumbsUp size={15} /></span><div><h4>What guests love</h4><p>Keep doing what you do best.</p></div></div>
            <div className="strength-chips">{analysis.strengths_to_keep.slice(0, 3).map((item) => <span className="strength-chip" key={item.aspect}><Check size={12} />{titleCase(item.aspect)}</span>)}</div>
          </div>}
        </div>
      ) : <div className="analysis-empty"><div className="analysis-empty-icon"><Sparkles size={20} /></div><strong>See the story behind your reviews</strong><p>Get a clear snapshot of sentiment, guest favorites, and the changes that could make the biggest difference.</p><button type="button" className="text-button" onClick={() => onAnalyze(false)} disabled={analyzing}>Generate your first analysis <ArrowRight size={14} /></button></div>}

      <div className="reviews-section">
        <div className="section-title-row reviews-heading"><div><h3>Recent reviews</h3><p>{detail.review_count ?? reviews.length} guest experiences</p></div><button type="button" className="view-reviews-button" onClick={() => document.getElementById("all-reviews")?.scrollIntoView({ behavior: "smooth" })}>View all <ArrowRight size={14} /></button></div>
        <div className="review-list" id="all-reviews">
          {reviews.slice(0, 4).map((review) => <ReviewRow key={review.id} review={review} />)}
          {!reviews.length && <div className="empty-inline">No reviews have been collected for this location yet.</div>}
        </div>
      </div>
    </div>
  );
}

function AspectCard({ aspect }: { aspect: Aspect }) {
  const score = aspect.score === null ? 0 : Math.max(0, Math.min(5, aspect.score));
  return (
    <article className="aspect-card">
      <div className="aspect-top"><span>{titleCase(aspect.aspect)}</span><span className={`aspect-mood ${sentimentClass(aspect.sentiment)}`}>{titleCase(aspect.sentiment)}</span></div>
      <div className="aspect-score">{aspect.score === null ? "—" : score.toFixed(1)}<span>/5</span></div>
      <div className="score-track"><span style={{ width: `${score * 20}%` }} className={score >= 4 ? "score-good" : score >= 3 ? "score-mid" : "score-low"} /></div>
      <p>{aspect.summary}</p>
    </article>
  );
}

function ImprovementCard({ item }: { item: Improvement }) {
  return (
    <article className="improvement-card">
      <span className={`priority-mark ${item.priority.toLowerCase()}`}><ArrowUpRight size={15} /></span>
      <div className="improvement-copy"><div className="improvement-label"><strong>{titleCase(item.aspect)}</strong><span className={`priority-text ${item.priority.toLowerCase()}`}>{item.priority} PRIORITY</span></div><p>{item.issue}</p><div className="action-note"><strong>Try this</strong> {item.recommended_action}</div></div>
    </article>
  );
}

function ReviewRow({ review }: { review: Review }) {
  return (
    <article className="review-row">
      <span className="review-avatar">{review.author_name.trim().split(/\s+/).map((part) => part[0]).slice(0, 2).join("").toUpperCase()}</span>
      <div className="review-body"><div className="review-author-line"><strong>{review.author_name}</strong><span className="review-date">{timeAgo(review.published_at)}</span></div><div className="review-stars" aria-label={`${review.rating} out of 5 stars`}>{Array.from({ length: 5 }, (_, index) => <Star key={index} size={12} fill={index < Math.round(review.rating) ? "currentColor" : "none"} />)}</div><p>{review.text}</p></div>
    </article>
  );
}

function InsightsPage({ restaurants, detail, loading, error, onSelect, onAnalyze, analyzing }: { restaurants: Restaurant[]; detail: RestaurantDetail | null; loading: boolean; error: string; onSelect: (id: number) => void; onAnalyze: (refresh?: boolean) => void; analyzing: boolean }) {
  const analyzed = restaurants.filter((restaurant) => restaurant.id === detail?.id && detail.latest_analysis);
  return (
    <div className="insights-layout">
      <div className="insights-intro panel">
        <div className="insights-intro-copy"><span className="section-kicker"><Sparkles size={13} /> YOUR AI ASSISTANT</span><h2>Listen closer.<br /><span>Grow smarter.</span></h2><p>Gather turns your guest feedback into the kind of clarity that helps your team make every visit a little better.</p><button type="button" className="button button-primary" disabled={!detail || analyzing} onClick={() => onAnalyze(Boolean(detail?.latest_analysis))}>{analyzing ? <LoaderCircle size={15} className="spin" /> : <Sparkles size={15} />}{detail?.latest_analysis ? "Refresh analysis" : "Analyze selected restaurant"}</button></div>
        <div className="insights-art"><div className="orbit orbit-one" /><div className="orbit orbit-two" /><span className="art-sparkle sparkle-one">✳</span><span className="art-sparkle sparkle-two">✦</span><span className="art-center"><Waves size={36} /></span><span className="art-tag tag-rating"><Star size={13} fill="currentColor" /> 4.8 guest love</span><span className="art-tag tag-growth"><TrendingUp size={14} /> Growing stronger</span></div>
      </div>
      {error && <ErrorBanner message={error} />}
      <div className="panel insights-results">
        <div className="panel-heading"><div><h2>Location insights</h2><p>Your latest analysis, by restaurant</p></div><span className="insight-info"><ShieldCheck size={14} /> Private to your workspace</span></div>
        {loading ? <LoadingState label="Loading selected analysis..." /> : detail?.latest_analysis ? (
          <div className="insight-result">
            <div className="insight-result-top"><RestaurantAvatar name={detail.name} /><div className="insight-result-copy"><strong>{detail.name}</strong><span>Analyzed {formatDate(detail.latest_analysis.created_at)} · {detail.latest_analysis.review_count} reviews</span></div><span className={`sentiment-pill ${sentimentClass(detail.latest_analysis.overall_sentiment)}`}>{titleCase(detail.latest_analysis.overall_sentiment)}</span></div>
            <p className="analysis-summary">{detail.latest_analysis.result_json.summary}</p>
            <div className="insight-result-footer"><span><TrendingLabel trend={detail.latest_analysis.result_json.estimated_rating_trend} /></span><button type="button" className="text-button" onClick={() => onSelect(detail.id)}>Open restaurant <ArrowRight size={14} /></button></div>
          </div>
        ) : <EmptyState title="Your insights are one click away" description={restaurants.length ? "Select a restaurant and generate an analysis to see what your guests are telling you." : "Add restaurants and reviews to start understanding your guest experience."} />}
      </div>
      <div className="insights-note"><ShieldCheck size={17} /><span><strong>Insights are a starting point, not the whole story.</strong> AI recommendations are advisory and depend on the reviews available.</span></div>
      {analyzed.length > 0 && <span className="sr-only">Analysis available for {analyzed.length} location</span>}
    </div>
  );
}

function SyncPage({ targets, runs, loading, running, error, notice, onRun, onRefresh, onAddTarget }: { targets: SyncTarget[]; runs: SyncRun[]; loading: boolean; running: boolean; error: string; notice: string; onRun: () => void; onRefresh: () => void; onAddTarget: () => void }) {
  return (
    <div className="sync-layout">
      <section className="sync-banner">
        <div className="sync-banner-icon"><RefreshCw size={22} /></div>
        <div className="sync-banner-copy"><span className="section-kicker">GOOGLE MAPS CONNECTION</span><h2>Keep your feedback fresh.</h2><p>Run a sync to pull the latest available restaurant and review data from your configured targets.</p></div>
        <button type="button" className="button button-primary" onClick={onRun} disabled={running || !targets.length}>{running ? <LoaderCircle size={15} className="spin" /> : <RefreshCw size={15} />}{running ? "Syncing..." : "Run sync now"}</button>
      </section>
      {error && <ErrorBanner message={error} />}
      {notice && <div className="notice-banner"><Check size={16} />{notice}</div>}
      {!targets.length && !loading && <div className="notice-banner notice-info"><CircleHelp size={16} />No sync targets are configured yet. Add a target through the API to begin collecting data.</div>}
      <section className="sync-stats">
        <StatCard label="Active targets" value={String(targets.filter((target) => target.is_active).length).padStart(2, "0")} icon={<MapPin size={18} />} tint="mint" change="Configured locations" />
        <StatCard label="Sync runs" value={String(runs.length).padStart(2, "0")} icon={<RefreshCw size={18} />} tint="lavender" change="Recent activity" />
        <StatCard label="Last completed" value={runs[0]?.finished_at ? timeAgo(runs[0].finished_at) : "—"} icon={<Clock3 size={18} />} tint="peach" change="Most recent run" />
      </section>
      <section className="panel sync-target-panel">
        <div className="panel-heading"><div><h2>Sync targets</h2><p>Places configured for review collection</p></div><div className="target-heading-actions"><span className="count-pill">{targets.length} targets</span><button type="button" className="button button-secondary add-target-button" onClick={onAddTarget}><Plus size={14} /> Add target</button></div></div>
        {loading ? <LoadingState label="Loading sync targets..." /> : targets.length ? <div className="table-wrap"><table><thead><tr><th>Target</th><th>Type</th><th>Language</th><th>Status</th><th>Last synced</th></tr></thead><tbody>{targets.map((target) => <tr key={target.id}><td><span className="target-value"><MapPin size={14} />{target.value}</span></td><td>{titleCase(target.target_type)}</td><td>{target.language_code.toUpperCase()}</td><td><span className={`run-status ${target.is_active ? "complete" : "inactive"}`}><span />{target.is_active ? "Active" : "Paused"}</span></td><td>{timeAgo(target.last_synced_at)}</td></tr>)}</tbody></table></div> : <EmptyState title="No sync targets yet" description="Sync targets are added through the API and will appear here." />}
      </section>
      <section className="panel sync-target-panel">
        <div className="panel-heading"><div><h2>Recent sync activity</h2><p>A history of your data collection jobs</p></div><button type="button" className="text-button" onClick={onRefresh}>Refresh <RefreshCw size={13} /></button></div>
        {loading ? <LoadingState label="Loading sync history..." /> : runs.length ? <div className="table-wrap"><table><thead><tr><th>Run</th><th>Status</th><th>Restaurants</th><th>Reviews</th><th>Started</th></tr></thead><tbody>{runs.map((run) => <tr key={run.id}><td>Sync #{run.id}</td><td><span className={`run-status ${run.status.toLowerCase()}`}><span />{titleCase(run.status)}</span>{run.error_message && <small className="table-error">{run.error_message}</small>}</td><td>{run.restaurants_upserted}</td><td>{run.reviews_upserted}</td><td>{formatDate(run.started_at)}</td></tr>)}</tbody></table></div> : <EmptyState title="No sync runs yet" description="Your sync history will show up here after the first run." />}
      </section>
      <div className="sync-footnote"><ShieldCheck size={16} /><span>The Google Places API may return a limited number of reviews. Your collected data depends on the configured provider and available access.</span></div>
    </div>
  );
}

function TrendIcon({ trend }: { trend: string }) {
  if (trend === "IMPROVING") return <TrendingUp size={14} />;
  if (trend === "DECLINING") return <TrendingDown size={14} />;
  return <ArrowRight size={14} />;
}

function TrendingLabel({ trend }: { trend: string }) {
  return <span className={`trend-badge ${trend.toLowerCase()}`}><TrendIcon trend={trend} />{titleCase(trend)} rating trend</span>;
}

function sentimentClass(sentiment: string) {
  return sentiment.toLowerCase();
}

function ErrorBanner({ message }: { message: string }) {
  return <div className="error-banner"><CircleHelp size={16} /><span>{message}</span></div>;
}

function LoadingState({ label }: { label: string }) {
  return <div className="loading-state"><LoaderCircle size={19} className="spin" /><span>{label}</span></div>;
}

function EmptyState({ title, description }: { title: string; description: string }) {
  return <div className="empty-state"><span className="empty-icon"><MessageSquareText size={20} /></span><strong>{title}</strong><p>{description}</p></div>;
}

function AddRestaurantDialog({ error, loading, onClose, onSubmit }: {
  error: string;
  loading: boolean;
  onClose: () => void;
  onSubmit: (form: { google_place_id: string; name: string; address: string; google_rating: string; user_rating_count: string }) => void;
}) {
  const [form, setForm] = useState({ google_place_id: "", name: "", address: "", google_rating: "", user_rating_count: "" });
  return (
    <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="add-dialog" role="dialog" aria-modal="true" aria-labelledby="add-dialog-title">
        <div className="dialog-heading"><div><span className="section-kicker">NEW LOCATION</span><h2 id="add-dialog-title">Add a restaurant</h2><p>Connect a restaurant to start collecting guest feedback.</p></div><button type="button" className="quiet-icon-button" aria-label="Close dialog" onClick={onClose}>×</button></div>
        <form onSubmit={(event) => { event.preventDefault(); onSubmit(form); }}>
          <label>Restaurant name<input required maxLength={255} value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="e.g. Golden Lotus Bistro" /></label>
          <label>Google Place ID<input required maxLength={255} value={form.google_place_id} onChange={(event) => setForm({ ...form, google_place_id: event.target.value })} placeholder="Paste the Google Place ID" /></label>
          <label>Address <span className="optional-label">Optional</span><input maxLength={500} value={form.address} onChange={(event) => setForm({ ...form, address: event.target.value })} placeholder="Street, city" /></label>
          <div className="dialog-fields">
            <label>Google rating <span className="optional-label">Optional</span><input type="number" min="0" max="5" step="0.1" value={form.google_rating} onChange={(event) => setForm({ ...form, google_rating: event.target.value })} placeholder="4.5" /></label>
            <label>Rating count <span className="optional-label">Optional</span><input type="number" min="0" step="1" value={form.user_rating_count} onChange={(event) => setForm({ ...form, user_rating_count: event.target.value })} placeholder="120" /></label>
          </div>
          {error && <ErrorBanner message={error} />}
          <div className="dialog-actions"><button type="button" className="button button-secondary" onClick={onClose} disabled={loading}>Cancel</button><button type="submit" className="button button-primary" disabled={loading}>{loading ? <LoaderCircle size={15} className="spin" /> : <Plus size={15} />}{loading ? "Adding..." : "Add restaurant"}</button></div>
        </form>
      </section>
    </div>
  );
}

function AddSyncTargetDialog({ error, loading, onClose, onSubmit }: {
  error: string;
  loading: boolean;
  onClose: () => void;
  onSubmit: (value: string, languageCode: string) => void;
}) {
  const [value, setValue] = useState("");
  const [languageCode, setLanguageCode] = useState("en");
  return (
    <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="add-dialog" role="dialog" aria-modal="true" aria-labelledby="sync-target-dialog-title">
        <div className="dialog-heading"><div><span className="section-kicker">GOOGLE MAPS</span><h2 id="sync-target-dialog-title">Add a sync target</h2><p>Sync restaurant details and available reviews using a Google Place ID.</p></div><button type="button" className="quiet-icon-button" aria-label="Close dialog" onClick={onClose}>×</button></div>
        <form onSubmit={(event) => { event.preventDefault(); onSubmit(value, languageCode); }}>
          <label>Google Place ID<input required maxLength={255} value={value} onChange={(event) => setValue(event.target.value)} placeholder="Paste the Google Place ID" /></label>
          <label>Review language<select value={languageCode} onChange={(event) => setLanguageCode(event.target.value)}><option value="en">English</option><option value="vi">Vietnamese</option><option value="ja">Japanese</option><option value="ko">Korean</option><option value="fr">French</option></select></label>
          {error && <ErrorBanner message={error} />}
          <div className="dialog-actions"><button type="button" className="button button-secondary" onClick={onClose} disabled={loading}>Cancel</button><button type="submit" className="button button-primary" disabled={loading}>{loading ? <LoaderCircle size={15} className="spin" /> : <Plus size={15} />}{loading ? "Adding..." : "Add sync target"}</button></div>
        </form>
      </section>
    </div>
  );
}

export default App;

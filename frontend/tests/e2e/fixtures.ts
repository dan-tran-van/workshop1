import type { Page, Route } from "@playwright/test";

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

type AnalysisResult = {
  overall_sentiment: string;
  summary: string;
  estimated_rating_trend: string;
  aspect_breakdown: Array<{
    aspect: string;
    sentiment: string;
    score: number;
    summary: string;
    highlights: string[];
  }>;
  prioritized_improvements: Array<{
    priority: string;
    aspect: string;
    issue: string;
    recommended_action: string;
    expected_impact: string;
  }>;
  strengths_to_keep: Array<{
    aspect: string;
    strength: string;
    marketing_tip: string;
  }>;
};

type Analysis = {
  id: number;
  restaurant_id: number;
  overall_sentiment: string;
  result_json: AnalysisResult;
  review_count: number;
  last_review_at: string;
  model: string;
  created_at: string;
};

type AnalysisHistoryEntry = {
  id: number;
  created_at: string;
  analysis: Analysis;
};

type RestaurantDetail = Restaurant & {
  reviews: Review[];
  latest_analysis: Analysis | null;
};

type MockOptions = {
  beforeListResponse?: () => Promise<void>;
  analysisDelayMs?: number;
  ttsDelayMs?: number;
  ttsErrorStatus?: number;
  ttsErrorDetail?: string;
  failFirstRestaurantList?: boolean;
  details?: Record<number, Partial<RestaurantDetail>>;
  initialAnalysis?: Analysis | null;
  analysisResult?: AnalysisResult;
  analysisHistory?: AnalysisHistoryEntry[];
  restaurantAnalyses?: Record<number, Analysis[]>;
  role?: "OWNER" | "ANALYST" | "ADMIN";
};

export const restaurants: Restaurant[] = [
  {
    id: 1,
    google_place_id: "place-hearth",
    name: "Hearth & Honey",
    address: "18 Oak Street, Portland",
    google_rating: 4.8,
    user_rating_count: 182,
    last_synced_at: "2026-11-13T10:00:00Z",
    updated_at: "2026-11-13T10:00:00Z",
    review_count: 2,
  },
  {
    id: 2,
    google_place_id: "place-lotus",
    name: "Lotus Garden",
    address: "240 River Road, Portland",
    google_rating: 4.3,
    user_rating_count: 74,
    last_synced_at: null,
    updated_at: null,
    review_count: 1,
  },
  {
    id: 3,
    google_place_id: "place-empty",
    name: "Quiet Corner Cafe",
    address: null,
    google_rating: null,
    user_rating_count: null,
    last_synced_at: null,
    updated_at: null,
    review_count: 0,
  },
];

export const reviews: Review[] = [
  {
    id: 11,
    restaurant_id: 1,
    author_name: "Jamie Rivera",
    author_uri: null,
    rating: 5,
    text: "Wonderful seasonal menu and a thoughtful team.",
    published_at: "2020-11-12T10:00:00Z",
  },
  {
    id: 12,
    restaurant_id: 1,
    author_name: "Morgan Lee",
    author_uri: null,
    rating: 4,
    text: "The meal was lovely. " + "The service was attentive. ".repeat(24),
    published_at: "2020-11-10T10:00:00Z",
  },
  {
    id: 21,
    restaurant_id: 2,
    author_name: "Taylor Chen",
    author_uri: null,
    rating: 5,
    text: "Fresh food and a welcoming atmosphere.",
    published_at: "2020-11-11T10:00:00Z",
  },
];

export const analysisResult: AnalysisResult = {
  overall_sentiment: "POSITIVE",
  summary: "Guests appreciate the seasonal menu and welcoming service.",
  estimated_rating_trend: "IMPROVING",
  aspect_breakdown: [
    { aspect: "food", sentiment: "POSITIVE", score: 4.8, summary: "Fresh, seasonal dishes.", highlights: ["Seasonal menu"] },
    { aspect: "service", sentiment: "POSITIVE", score: 4.6, summary: "Warm and attentive staff.", highlights: ["Attentive staff"] },
    { aspect: "wait_time", sentiment: "MIXED", score: 3.2, summary: "Some guests mention delays.", highlights: ["Busy evenings"] },
    { aspect: "hygiene", sentiment: "POSITIVE", score: 4.5, summary: "Guests describe a clean dining room.", highlights: [] },
    { aspect: "ambience", sentiment: "POSITIVE", score: 4.4, summary: "A comfortable atmosphere.", highlights: [] },
    { aspect: "price", sentiment: "NEUTRAL", score: 3.7, summary: "Pricing is considered fair.", highlights: [] },
  ],
  prioritized_improvements: [
    {
      priority: "HIGH",
      aspect: "wait_time",
      issue: "Guests report long waits during peak hours.",
      recommended_action: "Review staffing coverage for weekend dinner.",
      expected_impact: "Shorter waits and smoother service.",
    },
  ],
  strengths_to_keep: [
    {
      aspect: "food",
      strength: "Fresh seasonal dishes",
      marketing_tip: "Feature seasonal specials in your menu photos.",
    },
  ],
};

export const analysis: Analysis = {
  id: 91,
  restaurant_id: 1,
  overall_sentiment: analysisResult.overall_sentiment,
  result_json: analysisResult,
  review_count: 2,
  last_review_at: "2026-11-12T10:00:00Z",
  model: "test-fixture",
  created_at: "2026-11-14T09:00:00Z",
};

export const pastAnalysisResult: AnalysisResult = {
  overall_sentiment: "MIXED",
  summary: "Earlier feedback noted slower evening pacing alongside solid food.",
  estimated_rating_trend: "STABLE",
  aspect_breakdown: [
    { aspect: "food", sentiment: "POSITIVE", score: 4.4, summary: "Good seasonal ingredients.", highlights: [] },
    { aspect: "service", sentiment: "POSITIVE", score: 4.6, summary: "Friendly team.", highlights: [] },
    { aspect: "wait_time", sentiment: "NEGATIVE", score: 2.6, summary: "Noticeable weekend wait times.", highlights: [] },
    { aspect: "hygiene", sentiment: "POSITIVE", score: 4.8, summary: "Spotless dining room.", highlights: [] },
    { aspect: "ambience", sentiment: "POSITIVE", score: 4.4, summary: "Cozy lighting and decor.", highlights: [] },
    { aspect: "price", sentiment: "MIXED", score: 3.2, summary: "Some guests felt prices were high.", highlights: [] },
  ],
  prioritized_improvements: [],
  strengths_to_keep: [],
};

export const pastAnalysis: Analysis = {
  id: 85,
  restaurant_id: 1,
  overall_sentiment: pastAnalysisResult.overall_sentiment,
  result_json: pastAnalysisResult,
  review_count: 1,
  last_review_at: "2026-11-08T10:00:00Z",
  model: "test-fixture",
  created_at: "2026-11-08T09:00:00Z",
};

export const olderAnalysisResult: AnalysisResult = {
  overall_sentiment: "MIXED",
  summary: "Initial baseline snapshot before menu updates.",
  estimated_rating_trend: "STABLE",
  aspect_breakdown: [
    { aspect: "food", sentiment: "POSITIVE", score: 4.0, summary: "Reliable dishes.", highlights: [] },
    { aspect: "service", sentiment: "POSITIVE", score: 4.2, summary: "Polite service.", highlights: [] },
    { aspect: "wait_time", sentiment: "MIXED", score: 3.5, summary: "Moderate wait times.", highlights: [] },
    { aspect: "hygiene", sentiment: "POSITIVE", score: 4.5, summary: "Clean seating area.", highlights: [] },
    { aspect: "ambience", sentiment: "POSITIVE", score: 4.1, summary: "Warm ambiance.", highlights: [] },
    { aspect: "price", sentiment: "NEUTRAL", score: 3.9, summary: "Reasonable pricing.", highlights: [] },
  ],
  prioritized_improvements: [],
  strengths_to_keep: [],
};

export const olderAnalysis: Analysis = {
  id: 80,
  restaurant_id: 1,
  overall_sentiment: olderAnalysisResult.overall_sentiment,
  result_json: olderAnalysisResult,
  review_count: 1,
  last_review_at: "2026-11-01T10:00:00Z",
  model: "test-fixture",
  created_at: "2026-11-01T09:00:00Z",
};

const analysisResultLotus: AnalysisResult = {
  ...analysisResult,
  overall_sentiment: "MIXED",
  summary: "Fresh food and a welcoming atmosphere, with occasional pacing concerns.",
  estimated_rating_trend: "STABLE",
};

const analysisLotus: Analysis = {
  id: 88,
  restaurant_id: 2,
  overall_sentiment: analysisResultLotus.overall_sentiment,
  result_json: analysisResultLotus,
  review_count: 1,
  last_review_at: "2026-11-11T10:00:00Z",
  model: "test-fixture",
  created_at: "2026-11-12T08:00:00Z",
};

export const analysisHistory: AnalysisHistoryEntry[] = [
  {
    id: 3,
    created_at: "2026-11-14T11:00:00Z",
    analysis,
  },
  {
    id: 2,
    created_at: "2026-11-13T15:30:00Z",
    analysis: analysisLotus,
  },
  {
    id: 1,
    created_at: "2026-11-12T09:15:00Z",
    analysis,
  },
];

export async function installApiMocks(page: Page, options: MockOptions = {}) {
  let listRequests = 0;
  let nextHistoryId = 100;
  const role = options.role ?? "ADMIN";
  const historyRuns = [...(options.analysisHistory ?? [])];
  const analysesByRestaurant: Record<number, Analysis[]> = {};
  for (const [key, list] of Object.entries(options.restaurantAnalyses ?? {})) {
    analysesByRestaurant[Number(key)] = [...list];
  }
  if (options.initialAnalysis && !analysesByRestaurant[options.initialAnalysis.restaurant_id]) {
    analysesByRestaurant[options.initialAnalysis.restaurant_id] = [options.initialAnalysis];
  }

  await page.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.hostname !== "localhost" || url.port !== "8000") {
      await route.continue();
      return;
    }
    const path = url.pathname;

    if (request.method() === "OPTIONS") {
      await route.fulfill({
        status: 204,
        headers: {
          "access-control-allow-origin": "*",
          "access-control-allow-methods": "GET, POST, PATCH, OPTIONS",
          "access-control-allow-headers": "authorization, content-type",
        },
      });
      return;
    }

    if (path === "/health") {
      await json(route, { status: "ok" });
      return;
    }

    if (path === "/auth/setup") {
      await json(route, { setup_required: false });
      return;
    }

    if (path === "/auth/login" && request.method() === "POST") {
      await json(route, {
        access_token: "test-token",
        token_type: "bearer",
        expires_in: 1800,
        user: {
          id: 1,
          email: "test@example.com",
          full_name: "Test User",
          role,
          is_active: true,
          restaurant_ids: role === "OWNER" ? [1] : [],
        },
      });
      return;
    }

    if (path === "/auth/me") {
      await json(route, {
        id: 1,
        email: "test@example.com",
        full_name: "Test User",
        role,
        is_active: true,
        restaurant_ids: role === "OWNER" ? [1] : [],
      });
      return;
    }

    if (path === "/auth/me/analysis-history" && request.method() === "GET") {
      const visibleRuns = historyRuns.filter((entry) => {
        if (role !== "OWNER") return true;
        return entry.analysis.restaurant_id === 1;
      });
      await json(route, visibleRuns);
      return;
    }

    if (path === "/admin/users" && request.method() === "GET") {
      await json(route, []);
      return;
    }

    if (path === "/admin/users" && request.method() === "POST") {
      await json(route, { id: 2, ...request.postDataJSON() }, 201);
      return;
    }

    if (path.startsWith("/admin/users/") && request.method() === "PATCH") {
      await json(route, { id: 2, ...request.postDataJSON() });
      return;
    }

    if (path === "/restaurants" && request.method() === "GET") {
      listRequests += 1;
      if (options.beforeListResponse) await options.beforeListResponse();
      if (options.failFirstRestaurantList && listRequests === 1) {
        await json(route, { detail: "Restaurant service unavailable" }, 503);
        return;
      }

      const query = (url.searchParams.get("q") ?? "").trim().toLowerCase();
      const skip = Number(url.searchParams.get("skip") ?? 0);
      const limit = Number(url.searchParams.get("limit") ?? 20);
      const matching = restaurants.filter((restaurant) =>
        (role !== "OWNER" || restaurant.id === 1)
        && `${restaurant.name} ${restaurant.address ?? ""}`.toLowerCase().includes(query),
      );
      await json(route, matching.slice(skip, skip + limit));
      return;
    }

    const detailMatch = path.match(/^\/restaurants\/(\d+)$/);
    if (detailMatch && request.method() === "GET") {
      const id = Number(detailMatch[1]);
      const restaurant = restaurants.find((item) => item.id === id);
      if (!restaurant) {
        await json(route, { detail: `Restaurant with ID ${id} not found` }, 404);
        return;
      }
      const detail: RestaurantDetail = {
        ...restaurant,
        reviews: reviews.filter((review) => review.restaurant_id === id),
        latest_analysis: id === 1 ? options.initialAnalysis ?? null : null,
        ...options.details?.[id],
      };
      await json(route, detail);
      return;
    }

    const analyzeMatch = path.match(/^\/restaurants\/(\d+)\/analyze$/);
    if (analyzeMatch && request.method() === "POST") {
      if (options.analysisDelayMs) await page.waitForTimeout(options.analysisDelayMs);
      const id = Number(analyzeMatch[1]);
      const refresh = Boolean(request.postDataJSON()?.force_refresh);
      const baseResult = options.analysisResult ?? analysisResult;
      const result = refresh
        ? { ...baseResult, summary: "Refreshed analysis: service remains a guest favorite." }
        : baseResult;
      const snapshot: Analysis = {
        ...analysis,
        id: refresh ? 92 : analysis.id,
        restaurant_id: id,
        overall_sentiment: result.overall_sentiment,
        result_json: result,
        created_at: refresh ? "2026-11-14T10:00:00Z" : analysis.created_at,
      };
      nextHistoryId += 1;
      historyRuns.unshift({
        id: nextHistoryId,
        created_at: new Date().toISOString(),
        analysis: snapshot,
      });
      const existingList = analysesByRestaurant[id] ?? [];
      if (!existingList.some((item) => item.id === snapshot.id)) {
        analysesByRestaurant[id] = [snapshot, ...existingList];
      }
      await json(route, snapshot);
      return;
    }

    const analysesMatch = path.match(/^\/restaurants\/(\d+)\/analyses$/);
    if (analysesMatch) {
      const id = Number(analysesMatch[1]);
      await json(route, analysesByRestaurant[id] ?? []);
      return;
    }

    const ttsMatch = path.match(/^\/restaurants\/(\d+)\/analyses\/(\d+)\/tts$/);
    if (ttsMatch && request.method() === "POST") {
      if (options.ttsDelayMs) await page.waitForTimeout(options.ttsDelayMs);
      if (options.ttsErrorStatus) {
        await json(
          route,
          { detail: options.ttsErrorDetail ?? "Text-to-speech is not configured on the server." },
          options.ttsErrorStatus,
        );
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: "audio/wav",
        headers: { "access-control-allow-origin": "*" },
        body: createSilentWavBuffer(),
      });
      return;
    }

    await json(route, { detail: `Unmocked endpoint: ${request.method()} ${path}` }, 404);
  });
}

export async function authenticateTestUser(page: Page) {
  const email = page.getByRole("textbox", { name: "Email" });
  if (await email.isVisible()) {
    await email.fill("test@example.com");
    await page.getByLabel("Password").fill("secure-test-password-123");
    const loginResponsePromise = page.waitForResponse((response) =>
      response.request().method() === "POST" && new URL(response.url()).pathname === "/auth/login",
    );
    await page.getByRole("button", { name: "Sign in" }).click();
    const loginResponse = await loginResponsePromise;
    if (!loginResponse.ok()) {
      throw new Error(`Mock login failed (${loginResponse.status()}): ${await loginResponse.text()}`);
    }
  }
  await page.locator(".app-shell").waitFor();
}

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    headers: { "access-control-allow-origin": "*" },
    body: JSON.stringify(body),
  });
}

function createSilentWavBuffer(durationSeconds = 2): Buffer {
  const sampleRate = 8000;
  const numSamples = sampleRate * durationSeconds;
  const header = Buffer.alloc(44);
  header.write("RIFF", 0);
  header.writeUInt32LE(36 + numSamples, 4);
  header.write("WAVE", 8);
  header.write("fmt ", 12);
  header.writeUInt32LE(16, 16); // PCM chunk size
  header.writeUInt16LE(1, 20); // Audio format = PCM
  header.writeUInt16LE(1, 22); // Mono
  header.writeUInt32LE(sampleRate, 24);
  header.writeUInt32LE(sampleRate, 28); // Byte rate (8-bit mono)
  header.writeUInt16LE(1, 32); // Block align
  header.writeUInt16LE(8, 34); // Bits per sample
  header.write("data", 36);
  header.writeUInt32LE(numSamples, 40);
  const samples = Buffer.alloc(numSamples, 128); // Silence for unsigned 8-bit PCM
  return Buffer.concat([header, samples]);
}

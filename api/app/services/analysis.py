import json
import logging
import time
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.config import settings
from app.models import Restaurant, Review, Analysis
from app.schemas import AnalysisResultPayload, AspectBreakdown, ImprovementSuggestion, StrengthItem

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


ASPECTS_KEYWORDS = {
    "food": [
        # English
        "taste", "delicious", "food", "dish", "flavor", "menu", "portion", "fresh",
        # Vietnamese (District 2 / HCMC domain)
        "ngon", "dở", "món", "đồ ăn", "thức ăn", "vị", "nêm", "khẩu vị", "thực đơn", "phần ăn", "tươi"
    ],
    "service": [
        # English
        "staff", "server", "waiter", "service", "friendly", "attentive", "rude", "slow",
        # Vietnamese
        "nhân viên", "phục vụ", "thái độ", "nhiệt tình", "thô lỗ", "chậm chạp", "lễ tân", "order", "bồi bàn"
    ],
    "wait_time": [
        # English
        "wait", "time", "line", "delay", "queue", "quick", "fast", "slow", "hours",
        # Vietnamese
        "chờ", "đợi", "xếp hàng", "lâu", "chậm", "nhanh", "chờ đợi", "trễ", "muộn"
    ],
    "hygiene": [
        # English
        "clean", "dirty", "hygiene", "tidy", "smell", "restroom", "table",
        # Vietnamese
        "sạch", "dơ", "bẩn", "vệ sinh", "mùi", "toilet", "nhà vệ sinh", "bàn", "rác", "lau"
    ],
    "ambience": [
        # English
        "atmosphere", "ambience", "music", "decor", "vibe", "cozy", "noise", "loud",
        # Vietnamese
        "không gian", "không khí", "nhạc", "trang trí", "view", "ồn", "ấm cúng", "thoáng", "đẹp"
    ],
    "price": [
        # English
        "price", "expensive", "cheap", "value", "worth", "cost", "affordable",
        # Vietnamese
        "giá", "đắt", "mắc", "rẻ", "tiền", "hợp lý", "chi phí", "bill", "hóa đơn"
    ]
}

# Pre-compiled module-level constants to avoid per-request memory allocation
ASPECT_ITEMS = list(ASPECTS_KEYWORDS.items())
ALL_ASPECTS_KEYWORDS = tuple(kw for kws in ASPECTS_KEYWORDS.values() for kw in kws)


def calculate_global_review_metrics(reviews: List[Review]) -> Dict[str, Any]:
    """
    Stage 1: Deterministic Math Engine.
    Scans 100% of reviews (whether 50 or 10,000+) in a single O(N) pass to calculate
    exact rating distributions, chronological trends, and aspect metrics.
    Zero hallucination, 0ms overhead, $0 token cost.
    """
    start_time = time.perf_counter()
    total_reviews = len(reviews)
    if total_reviews == 0:
        return {
            "total_reviews": 0,
            "avg_rating": 0.0,
            "overall_sentiment": "NEUTRAL",
            "trend": "STABLE",
            "rating_distribution": {5: 0, 4: 0, 3: 0, 2: 0, 1: 0},
            "aspect_scores": {
                aspect: {
                    "aspect": aspect,
                    "score": 0.0,
                    "mentions_count": 0,
                    "sentiment": "NEUTRAL",
                    "summary": "No reviews available yet."
                }
                for aspect in ASPECTS_KEYWORDS
            }
        }

    # Single pass accumulators
    total_rating = 0.0
    distribution = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
    aspect_matched_ratings: Dict[str, List[float]] = {aspect: [] for aspect in ASPECTS_KEYWORDS}

    for r in reviews:
        rating = r.rating
        total_rating += rating

        # Histogram distribution
        star = max(1, min(5, int(round(rating))))
        distribution[star] += 1

        # Text lowercased once per review across all aspects
        text_lower = r.text.lower()
        for aspect, kws in ASPECT_ITEMS:
            if any(k in text_lower for k in kws):
                aspect_matched_ratings[aspect].append(rating)

    avg_rating = total_rating / total_reviews

    aspect_scores: Dict[str, Dict[str, Any]] = {}
    for aspect in ASPECTS_KEYWORDS:
        matched = aspect_matched_ratings[aspect]
        mentions_count = len(matched)
        if mentions_count > 0:
            aspect_avg = sum(matched) / mentions_count
            sentiment = "POSITIVE" if aspect_avg >= 4.0 else ("MIXED" if aspect_avg >= 3.0 else "NEGATIVE")
        else:
            aspect_avg = avg_rating
            sentiment = "POSITIVE" if avg_rating >= 4.0 else ("MIXED" if avg_rating >= 3.0 else "NEGATIVE")

        aspect_scores[aspect] = {
            "aspect": aspect,
            "score": round(aspect_avg, 1),
            "mentions_count": mentions_count,
            "sentiment": sentiment,
            "summary": f"Rated approx {round(aspect_avg, 1)}/5 based on customer comments."
        }

    overall_sentiment = "POSITIVE" if avg_rating >= 4.0 else ("MIXED" if avg_rating >= 3.0 else "NEGATIVE")

    # Rating trend heuristic across chronological halves (O(N) slice without re-sorting)
    half = total_reviews // 2
    if half > 0:
        if reviews[0].published_at >= reviews[-1].published_at:
            # Descending order (newest first, default DB order): first half is newest
            first_half_avg = sum(r.rating for r in reviews[half:]) / (total_reviews - half)
            second_half_avg = sum(r.rating for r in reviews[:half]) / half
        elif reviews[0].published_at <= reviews[-1].published_at:
            # Ascending order (oldest first): first half is oldest
            first_half_avg = sum(r.rating for r in reviews[:half]) / half
            second_half_avg = sum(r.rating for r in reviews[half:]) / (total_reviews - half)
        else:
            sorted_by_date = sorted(reviews, key=lambda r: r.published_at)
            first_half_avg = sum(r.rating for r in sorted_by_date[:half]) / half
            second_half_avg = sum(r.rating for r in sorted_by_date[half:]) / (total_reviews - half)

        if second_half_avg - first_half_avg > 0.3:
            trend = "IMPROVING"
        elif first_half_avg - second_half_avg > 0.3:
            trend = "DECLINING"
        else:
            trend = "STABLE"
    else:
        trend = "STABLE"

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    logger.info(
        f"[Analysis Stage 1] Computed ground truth across {total_reviews} reviews "
        f"(avg_rating={avg_rating:.1f}, trend={trend}) in {elapsed_ms:.2f}ms"
    )

    return {
        "total_reviews": total_reviews,
        "avg_rating": round(avg_rating, 1),
        "overall_sentiment": overall_sentiment,
        "trend": trend,
        "rating_distribution": distribution,
        "aspect_scores": aspect_scores
    }


def sample_stratified_reviews(reviews: List[Review], target_limit: int = 45) -> List[Review]:
    """
    Stage 2: High-Signal Stratified Sampler.
    Curates a balanced, diverse cross-section of customer reviews in a single pass:
    - Recent reviews (capturing current operational shifts)
    - Critical negative complaints (1-2 stars with aspect keywords for root-cause discovery)
    - Standout positive praises (4-5 stars for genuine strengths)
    - Mixed reviews (3 stars for inconsistent quality signals)
    """
    if len(reviews) <= target_limit:
        return reviews

    start_time = time.perf_counter()
    selected_ids = set()
    sampled: List[Review] = []

    def add_review(r: Review) -> bool:
        ident = getattr(r, "id", None) or getattr(r, "external_review_id", None) or id(r)
        if ident not in selected_ids:
            selected_ids.add(ident)
            sampled.append(r)
            return True
        return False

    # 1. Latest reviews (SQL already queries newest first; avoid re-sorting)
    newest_first = reviews if reviews[0].published_at >= reviews[-1].published_at else sorted(reviews, key=lambda r: r.published_at, reverse=True)
    for r in newest_first[:15]:
        add_review(r)

    # 2. Single pass classification across the review list using pre-compiled keywords tuple
    negative_with_kws: List[Review] = []
    negative_other: List[Review] = []
    positive_with_kws: List[Review] = []
    positive_other: List[Review] = []
    mixed_reviews: List[Review] = []

    for r in reviews:
        t_lower = r.text.lower()
        has_kw = any(k in t_lower for k in ALL_ASPECTS_KEYWORDS)
        rating = r.rating

        if rating <= 2.0:
            if has_kw:
                negative_with_kws.append(r)
            else:
                negative_other.append(r)
        elif rating >= 4.0:
            if has_kw:
                positive_with_kws.append(r)
            else:
                positive_other.append(r)
        else:
            mixed_reviews.append(r)

    # 3. Curate negative pain points (up to 18)
    for r in (negative_with_kws + negative_other)[:18]:
        add_review(r)

    # 4. Curate standout positive praises (up to 12)
    for r in (positive_with_kws + positive_other)[:12]:
        add_review(r)

    # 5. Curate mixed/moderate feedback (up to 5)
    for r in mixed_reviews[:5]:
        add_review(r)

    # 6. Backfill from remaining newest reviews if we still have room
    if len(sampled) < target_limit:
        for r in newest_first:
            if len(sampled) >= target_limit:
                break
            add_review(r)

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    compression_pct = (1.0 - len(sampled) / len(reviews)) * 100
    logger.info(
        f"[Analysis Stage 2] Curated {len(sampled)}/{len(reviews)} high-signal reviews "
        f"({len(negative_with_kws)} pain points, {len(positive_with_kws)} praises, {len(mixed_reviews)} mixed; "
        f"compression: {compression_pct:.1f}%) in {elapsed_ms:.2f}ms"
    )

    return sampled


def generate_mock_analysis(restaurant_name: str, reviews: List[Review]) -> Tuple[str, Dict[str, Any]]:
    """
    Intelligent heuristic fallback analyzer when OpenAI API key is not configured.
    Ensures the system is immediately runnable for demos, local development, and testing.
    """
    metrics = calculate_global_review_metrics(reviews)
    total_reviews = metrics["total_reviews"]
    if total_reviews == 0:
        return "NEUTRAL", {
            "overall_sentiment": "NEUTRAL",
            "summary": "No reviews available yet to analyze.",
            "estimated_rating_trend": "STABLE",
            "aspect_breakdown": [],
            "prioritized_improvements": [],
            "strengths_to_keep": []
        }

    avg_rating = metrics["avg_rating"]
    aspect_scores = metrics["aspect_scores"]
    overall_sentiment = metrics["overall_sentiment"]
    trend = metrics["trend"]

    # Prioritized suggestions and strengths
    improvements = []
    strengths = []

    for aspect, data in aspect_scores.items():
        if data["sentiment"] == "NEGATIVE":
            improvements.append({
                "priority": "HIGH",
                "aspect": aspect,
                "issue": f"Recurring customer complaints regarding {aspect.replace('_', ' ')}.",
                "recommended_action": f"Review team workflows and standards for {aspect.replace('_', ' ')}.",
                "expected_impact": "Direct improvement in 1-star to 3-star customer ratings."
            })
        elif data["sentiment"] == "MIXED":
            improvements.append({
                "priority": "MEDIUM",
                "aspect": aspect,
                "issue": f"Inconsistent feedback on {aspect.replace('_', ' ')}.",
                "recommended_action": f"Standardize quality control during peak hours.",
                "expected_impact": "Stabilizes overall guest satisfaction."
            })
        else:
            strengths.append({
                "aspect": aspect,
                "strength": f"High praise from guests for {aspect.replace('_', ' ')}.",
                "marketing_tip": f"Highlight your {aspect.replace('_', ' ')} on social media and promotions."
            })

    result_json = {
        "overall_sentiment": overall_sentiment,
        "summary": f"{restaurant_name} shows an average rating of {round(avg_rating, 1)} across {total_reviews} reviews. Key strengths include {', '.join([s['aspect'] for s in strengths[:2]]) or 'general offerings'}.",
        "estimated_rating_trend": trend,
        "aspect_breakdown": list(aspect_scores.values()),
        "prioritized_improvements": improvements[:3],
        "strengths_to_keep": strengths[:3]
    }
    logger.info(
        f"[Analysis Heuristic] Completed heuristic analysis for '{restaurant_name}' "
        f"({total_reviews} reviews, sentiment={overall_sentiment}, trend={trend})"
    )
    return overall_sentiment, result_json


def analyze_with_openai(restaurant_name: str, reviews: List[Review], model_name: str) -> Tuple[str, Dict[str, Any]]:
    """
    Call OpenAI API to generate structured insights and prioritized recommendations
    using the Two-Stage Hybrid pattern (Deterministic Aggregation + Stratified Sampling).
    """
    from openai import OpenAI
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    metrics = calculate_global_review_metrics(reviews)
    sampled_reviews = sample_stratified_reviews(reviews, target_limit=45)

    reviews_summary = [
        {"rating": r.rating, "text": r.text[:500], "date": r.published_at.strftime("%Y-%m-%d")}
        for r in sampled_reviews
    ]

    system_prompt = (
        "You are an expert F&B restaurant consultant and customer review intelligence analyst. "
        "Analyze the provided customer reviews and output valid JSON conforming strictly to the requested schema. "
        "Aspects to evaluate: 'food', 'service', 'wait_time', 'hygiene', 'ambience', 'price'. "
        "Prioritize actionable, root-cause improvements that restaurant managers can execute."
    )

    aspect_summary_lines = [
        f"- {data['aspect']}: approx score {data['score']}/5.0 ({data['sentiment']}, {data['mentions_count']} mentions)"
        for data in metrics["aspect_scores"].values()
    ]

    user_prompt = f"""
Restaurant: {restaurant_name}
Total Reviews in Database: {metrics['total_reviews']}
Overall Average Rating: {metrics['avg_rating']}/5.0
Rating Distribution: 5★: {metrics['rating_distribution'][5]}, 4★: {metrics['rating_distribution'][4]}, 3★: {metrics['rating_distribution'][3]}, 2★: {metrics['rating_distribution'][2]}, 1★: {metrics['rating_distribution'][1]}
Estimated Rating Trend: {metrics['trend']}

Calculated Aspect Metrics (analyzed across all {metrics['total_reviews']} reviews):
{chr(10).join(aspect_summary_lines)}

Representative Sample of Customer Reviews ({len(reviews_summary)} high-signal quotes across negative pain points, strengths, and recent feedback):
{json.dumps(reviews_summary, ensure_ascii=False, indent=2)}

Please return a JSON object with this exact structure:
{{
  "overall_sentiment": "POSITIVE" | "NEGATIVE" | "MIXED" | "NEUTRAL",
  "summary": "Concise 2-3 sentence overview of findings",
  "estimated_rating_trend": "IMPROVING" | "STABLE" | "DECLINING",
  "aspect_breakdown": [
    {{
      "aspect": "food | service | wait_time | hygiene | ambience | price",
      "sentiment": "POSITIVE" | "NEGATIVE" | "MIXED" | "NEUTRAL",
      "score": float (1.0 to 5.0),
      "summary": "Brief aspect summary",
      "highlights": ["quote or notable comment 1", "quote 2"]
    }}
  ],
  "prioritized_improvements": [
    {{
      "priority": "HIGH" | "MEDIUM" | "LOW",
      "aspect": "aspect_name",
      "issue": "Root cause issue identified",
      "recommended_action": "Specific concrete action step",
      "expected_impact": "Expected outcome"
    }}
  ],
  "strengths_to_keep": [
    {{
      "aspect": "aspect_name",
      "strength": "What customers love",
      "marketing_tip": "How to use this in marketing or branding"
    }}
  ]
}}
"""

    effective_model = model_name or settings.OPENAI_MODEL or "gpt-4o-mini"
    logger.info(
        f"[Analysis Stage 3] Calling OpenAI ({effective_model}) for '{restaurant_name}' "
        f"with {len(reviews_summary)} stratified quotes (scanned from {len(reviews)} total reviews)..."
    )
    start_time = time.perf_counter()

    response = client.chat.completions.create(
        model=effective_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        response_format={"type": "json_object"},
        temperature=0.2
    )

    elapsed_s = time.perf_counter() - start_time
    content = response.choices[0].message.content
    parsed = json.loads(content)
    validated = AnalysisResultPayload.model_validate(parsed)
    sentiment = validated.overall_sentiment
    logger.info(
        f"[Analysis Stage 3] OpenAI ({effective_model}) completed in {elapsed_s:.2f}s "
        f"with overall_sentiment='{sentiment}'"
    )
    return sentiment, validated.model_dump()


def get_or_run_restaurant_analysis(
    db: Session,
    restaurant_id: int,
    force_refresh: bool = False,
    requested_model: Optional[str] = None
) -> Analysis:
    """
    Get cached analysis if available and not stale, or trigger a new AI analysis.
    """
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        raise ValueError(f"Restaurant with ID {restaurant_id} not found")

    reviews = db.query(Review).filter(Review.restaurant_id == restaurant_id).order_by(Review.published_at.desc()).all()
    review_count = len(reviews)
    last_review_date = reviews[0].published_at if reviews else None

    # Check cache if not forcing refresh
    if not force_refresh:
        latest_analysis = (
            db.query(Analysis)
            .filter(Analysis.restaurant_id == restaurant_id)
            .order_by(Analysis.created_at.desc())
            .first()
        )
        if latest_analysis and latest_analysis.review_count == review_count:
            logger.info(
                f"[Analysis Cache] HIT for '{restaurant.name}' (ID {restaurant_id}): "
                f"reusing analysis ID {latest_analysis.id} ({review_count} reviews)"
            )
            return latest_analysis

    logger.info(
        f"[Analysis Cache] MISS/REFRESH for '{restaurant.name}' (ID {restaurant_id}): "
        f"running fresh analysis over {review_count} reviews (force_refresh={force_refresh})"
    )

    # Run new analysis
    model_name = requested_model or settings.OPENAI_MODEL or "gpt-4o-mini"
    if settings.OPENAI_API_KEY:
        try:
            sentiment, result_json = analyze_with_openai(restaurant.name, reviews, model_name)
        except Exception as e:
            logger.error(f"OpenAI analysis failed: {e}. Falling back to heuristic mock analyzer.")
            sentiment, result_json = generate_mock_analysis(restaurant.name, reviews)
            model_name = "heuristic-fallback"
    else:
        sentiment, result_json = generate_mock_analysis(restaurant.name, reviews)
        model_name = "heuristic-mock"

    analysis = Analysis(
        restaurant_id=restaurant_id,
        overall_sentiment=sentiment,
        result_json=result_json,
        review_count=review_count,
        last_review_at=last_review_date,
        model=model_name
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    logger.info(
        f"[Analysis Complete] Persisted analysis ID {analysis.id} for '{restaurant.name}' "
        f"(model={model_name}, sentiment={sentiment}, reviews={review_count})"
    )
    return analysis

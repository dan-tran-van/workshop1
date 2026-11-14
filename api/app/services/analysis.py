import json
import logging
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.config import settings
from app.models import Restaurant, Review, Analysis
from app.schemas import AnalysisResultPayload, AspectBreakdown, ImprovementSuggestion, StrengthItem

logger = logging.getLogger(__name__)


def generate_mock_analysis(restaurant_name: str, reviews: List[Review]) -> Tuple[str, Dict[str, Any]]:
    """
    Intelligent heuristic fallback analyzer when OpenAI API key is not configured.
    Ensures the system is immediately runnable for demos, local development, and testing.
    """
    total_reviews = len(reviews)
    if total_reviews == 0:
        return "NEUTRAL", {
            "overall_sentiment": "NEUTRAL",
            "summary": "No reviews available yet to analyze.",
            "estimated_rating_trend": "STABLE",
            "aspect_breakdown": [],
            "prioritized_improvements": [],
            "strengths_to_keep": []
        }

    avg_rating = sum(r.rating for r in reviews) / total_reviews
    
    # Calculate aspect mentions and sentiment
    aspects_keywords = {
        "food": ["taste", "delicious", "food", "dish", "flavor", "menu", "portion", "fresh"],
        "service": ["staff", "server", "waiter", "service", "friendly", "attentive", "rude", "slow"],
        "wait_time": ["wait", "time", "line", "delay", "queue", "quick", "fast", "slow", "hours"],
        "hygiene": ["clean", "dirty", "hygiene", "tidy", "smell", "restroom", "table"],
        "ambience": ["atmosphere", "ambience", "music", "decor", "vibe", "cozy", "noise", "loud"],
        "price": ["price", "expensive", "cheap", "value", "worth", "cost", "affordable"]
    }

    aspect_scores: Dict[str, Dict[str, Any]] = {}
    for aspect, kws in aspects_keywords.items():
        matched_ratings = []
        for r in reviews:
            text_lower = r.text.lower()
            if any(k in text_lower for k in kws):
                matched_ratings.append(r.rating)
        
        if matched_ratings:
            aspect_avg = sum(matched_ratings) / len(matched_ratings)
            sentiment = "POSITIVE" if aspect_avg >= 4.0 else ("MIXED" if aspect_avg >= 3.0 else "NEGATIVE")
        else:
            aspect_avg = avg_rating
            sentiment = "POSITIVE" if avg_rating >= 4.0 else ("MIXED" if avg_rating >= 3.0 else "NEGATIVE")
        
        aspect_scores[aspect] = {
            "aspect": aspect,
            "score": round(aspect_avg, 1),
            "sentiment": sentiment,
            "summary": f"Rated approx {round(aspect_avg, 1)}/5 based on customer comments."
        }

    overall_sentiment = "POSITIVE" if avg_rating >= 4.0 else ("MIXED" if avg_rating >= 3.0 else "NEGATIVE")
    
    # Rating trend heuristic
    sorted_by_date = sorted(reviews, key=lambda r: r.published_at)
    half = len(sorted_by_date) // 2
    if half > 0:
        first_half_avg = sum(r.rating for r in sorted_by_date[:half]) / half
        second_half_avg = sum(r.rating for r in sorted_by_date[half:]) / (len(sorted_by_date) - half)
        if second_half_avg - first_half_avg > 0.3:
            trend = "IMPROVING"
        elif first_half_avg - second_half_avg > 0.3:
            trend = "DECLINING"
        else:
            trend = "STABLE"
    else:
        trend = "STABLE"

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
    return overall_sentiment, result_json


def analyze_with_openai(restaurant_name: str, reviews: List[Review], model_name: str) -> Tuple[str, Dict[str, Any]]:
    """
    Call OpenAI API to generate structured insights and prioritized recommendations.
    """
    from openai import OpenAI
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    reviews_summary = [
        {"rating": r.rating, "text": r.text[:500], "date": r.published_at.strftime("%Y-%m-%d")}
        for r in reviews[:50]
    ]

    system_prompt = (
        "You are an expert F&B restaurant consultant and customer review intelligence analyst. "
        "Analyze the provided customer reviews and output valid JSON conforming strictly to the requested schema. "
        "Aspects to evaluate: 'food', 'service', 'wait_time', 'hygiene', 'ambience', 'price'. "
        "Prioritize actionable, root-cause improvements that restaurant managers can execute."
    )

    user_prompt = f"""
Restaurant: {restaurant_name}
Reviews count: {len(reviews)}

Reviews:
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

    response = client.chat.completions.create(
        model=model_name or settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        response_format={"type": "json_object"},
        temperature=0.2
    )

    content = response.choices[0].message.content
    parsed = json.loads(content)
    validated = AnalysisResultPayload.model_validate(parsed)
    sentiment = validated.overall_sentiment
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
            return latest_analysis

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
    return analysis

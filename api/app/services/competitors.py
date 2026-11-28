"""Market comparison: competitive set suggestions (US-01) and criteria gap analysis (US-02).

Scope notes (see docs/market-comparison.md for the roadmap):
- The datasets have no coordinates, cuisine or price level, so candidates are not filtered by
  radius, cuisine or price. Every other restaurant in the workspace is a candidate.
- Ranking: competitors with collected reviews come first, then restaurants without reviews,
  each group ordered by how close their Google review volume is to the owner's restaurant.
- Criteria are the six fixed analysis aspects, scored on the same 1-5 scale for every place:
  the average star rating of the reviews whose text mentions that aspect.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models import CompetitorSelection, Restaurant, Review
from app.services.analysis import ASPECT_ITEMS, ASPECTS_KEYWORDS

logger = logging.getLogger(__name__)

ASPECTS: Tuple[str, ...] = tuple(ASPECTS_KEYWORDS)
KEPT_STATUSES = ("PINNED", "MANUAL")
EVIDENCE_LIMIT = 3
LLM_CANDIDATES_PER_SIDE = 6

DATA_LIMITATIONS = [
    "Distance, cuisine and price level are not in the current data, so suggestions are not limited by radius, cuisine or price yet.",
    "Suggestions are not limited to one area yet: every restaurant in the workspace is a candidate.",
    "Competitors without collected reviews are listed but cannot be scored in the gap table.",
]


class InsufficientDataError(Exception):
    """Raised when a criterion lacks enough reviews for an AI conclusion."""


def aspect_label(aspect: str) -> str:
    return aspect.replace("_", " ")


def collected_review_counts(db: Session) -> Dict[int, int]:
    rows = db.query(Review.restaurant_id, func.count(Review.id)).group_by(Review.restaurant_id).all()
    return {restaurant_id: count for restaurant_id, count in rows}


def load_selections(db: Session, restaurant_id: int) -> Dict[int, CompetitorSelection]:
    rows = db.query(CompetitorSelection).filter(CompetitorSelection.restaurant_id == restaurant_id).all()
    return {row.competitor_id: row for row in rows}


def _volume_distance(own_volume: Optional[int], other_volume: Optional[int]) -> float:
    if own_volume is None or other_volume is None:
        return float("inf")
    return float(abs(other_volume - own_volume))


def _reasons(restaurant: Restaurant, other: Restaurant, source: str, collected: int) -> List[str]:
    reasons: List[str] = []
    if source == "PINNED":
        reasons.append("Pinned by you")
    elif source == "MANUAL":
        reasons.append("Added manually")
    if collected:
        reasons.append(f"{collected} collected reviews, compared on the same criteria")
    else:
        reasons.append("No collected reviews yet, so not scored in the gap table")
    if other.user_rating_count is not None and restaurant.user_rating_count is not None:
        reasons.append(f"{other.user_rating_count:,} Google reviews (yours: {restaurant.user_rating_count:,})")
    return reasons


def build_competitive_set(db: Session, restaurant: Restaurant, can_edit: bool) -> Dict[str, Any]:
    selections = load_selections(db, restaurant.id)
    counts = collected_review_counts(db)
    others = db.query(Restaurant).filter(Restaurant.id != restaurant.id).order_by(Restaurant.id.asc()).all()

    kept = [other for other in others if other.id in selections and selections[other.id].status in KEPT_STATUSES]
    dismissed = [other for other in others if other.id in selections and selections[other.id].status == "DISMISSED"]
    excluded_ids = {other.id for other in kept} | {other.id for other in dismissed}
    pool = [other for other in others if other.id not in excluded_ids]
    pool.sort(key=lambda other: (
        0 if counts.get(other.id, 0) > 0 else 1,
        _volume_distance(restaurant.user_rating_count, other.user_rating_count),
        other.id,
    ))
    slots = max(0, settings.COMPETITOR_MAX_SUGGESTIONS - len(kept))
    suggested = pool[:slots]

    competitors: List[Dict[str, Any]] = []
    for other, source in [(item, selections[item.id].status) for item in kept] + [(item, "SUGGESTED") for item in suggested]:
        collected = counts.get(other.id, 0)
        competitors.append({
            "restaurant_id": other.id,
            "name": other.name,
            "address": other.address,
            "google_rating": other.google_rating,
            "user_rating_count": other.user_rating_count,
            "collected_review_count": collected,
            "distance_m": None,
            "cuisine": None,
            "price_level": None,
            "source": source,
            "scorable": collected > 0,
            "reasons": _reasons(restaurant, other, source, collected),
        })

    matching_count = len(kept) + len(pool)
    scored = sum(1 for item in competitors if item["scorable"])
    minimum = settings.COMPETITOR_MIN_SUGGESTIONS
    notices: List[str] = []
    if matching_count < minimum:
        notices.append(
            f"Only {matching_count} matching places were found (target: {minimum}). "
            "Try expanding the radius or relaxing the cuisine filter once location and cuisine data are available."
        )
    if scored < minimum:
        notices.append(
            f"Only {scored} of these competitors have collected reviews, so the gap table compares against {scored}."
        )

    return {
        "restaurant_id": restaurant.id,
        "generated_at": datetime.now(timezone.utc),
        "competitors": competitors,
        "dismissed": [{"restaurant_id": other.id, "name": other.name} for other in dismissed],
        "matching_count": matching_count,
        "scored_competitor_count": scored,
        "min_suggestions": minimum,
        "max_suggestions": settings.COMPETITOR_MAX_SUGGESTIONS,
        "can_edit": can_edit,
        "notice": " ".join(notices) or None,
        "data_limitations": DATA_LIMITATIONS,
    }


def list_manual_candidates(db: Session, restaurant: Restaurant, query: Optional[str], limit: int) -> List[Dict[str, Any]]:
    """Restaurants already in the workspace that can be added manually (no Google lookup yet)."""
    selections = load_selections(db, restaurant.id)
    kept_ids = {competitor_id for competitor_id, row in selections.items() if row.status in KEPT_STATUSES}
    rows = db.query(Restaurant).filter(Restaurant.id != restaurant.id)
    if kept_ids:
        rows = rows.filter(Restaurant.id.notin_(kept_ids))
    if query:
        rows = rows.filter((Restaurant.name.ilike(f"%{query}%")) | (Restaurant.address.ilike(f"%{query}%")))
    counts = collected_review_counts(db)
    return [
        {
            "restaurant_id": other.id,
            "name": other.name,
            "address": other.address,
            "google_rating": other.google_rating,
            "user_rating_count": other.user_rating_count,
            "collected_review_count": counts.get(other.id, 0),
        }
        for other in rows.order_by(Restaurant.name.asc()).limit(limit).all()
    ]


def set_selection(db: Session, restaurant: Restaurant, competitor: Restaurant, status: str, user_id: int) -> None:
    if competitor.id == restaurant.id:
        raise ValueError("A restaurant cannot be its own competitor")
    row = (
        db.query(CompetitorSelection)
        .filter(CompetitorSelection.restaurant_id == restaurant.id, CompetitorSelection.competitor_id == competitor.id)
        .first()
    )
    if row is None:
        row = CompetitorSelection(restaurant_id=restaurant.id, competitor_id=competitor.id)
        db.add(row)
    row.status = status
    row.created_by_user_id = user_id
    db.commit()


def clear_selection(db: Session, restaurant: Restaurant, competitor_id: int) -> None:
    db.query(CompetitorSelection).filter(
        CompetitorSelection.restaurant_id == restaurant.id,
        CompetitorSelection.competitor_id == competitor_id,
    ).delete()
    db.commit()


# --------------------------------------------------------
# Criteria gap (US-02)
# --------------------------------------------------------
def aspect_mentions(reviews: Sequence[Review]) -> Dict[str, List[Review]]:
    mentions: Dict[str, List[Review]] = {aspect: [] for aspect in ASPECTS}
    for review in reviews:
        text_lower = review.text.lower()
        for aspect, keywords in ASPECT_ITEMS:
            if any(keyword in text_lower for keyword in keywords):
                mentions[aspect].append(review)
    return mentions


def _mean(values: Sequence[float]) -> Optional[float]:
    return sum(values) / len(values) if values else None


def _round(value: Optional[float]) -> Optional[float]:
    return None if value is None else round(value, 2)


def _gap_context(db: Session, restaurant: Restaurant) -> Tuple[Dict[str, Any], Dict[int, str], Dict[int, Dict[str, List[Review]]]]:
    competitive = build_competitive_set(db, restaurant, can_edit=False)
    competitor_ids = [item["restaurant_id"] for item in competitive["competitors"] if item["scorable"]]
    names = {item["restaurant_id"]: item["name"] for item in competitive["competitors"]}
    names[restaurant.id] = restaurant.name
    reviews = db.query(Review).filter(Review.restaurant_id.in_([restaurant.id, *competitor_ids])).all()
    grouped: Dict[int, List[Review]] = {restaurant_id: [] for restaurant_id in [restaurant.id, *competitor_ids]}
    for review in reviews:
        grouped[review.restaurant_id].append(review)
    mentions = {restaurant_id: aspect_mentions(items) for restaurant_id, items in grouped.items()}
    return competitive, names, mentions


def compute_gap_row(
    aspect: str,
    own_reviews: Sequence[Review],
    competitor_reviews: Dict[int, Sequence[Review]],
    names: Dict[int, str],
) -> Dict[str, Any]:
    threshold = settings.MIN_REVIEWS_PER_CRITERION
    margin = settings.GAP_TIE_MARGIN
    label = aspect_label(aspect)
    own_mentions = len(own_reviews)
    own_score = _mean([review.rating for review in own_reviews])

    # Competitors below the threshold on this criterion are left out of the average and leader.
    qualified = {
        competitor_id: _mean([review.rating for review in reviews])
        for competitor_id, reviews in competitor_reviews.items()
        if len(reviews) >= threshold
    }
    competitor_avg = _mean(list(qualified.values()))
    leader = None
    if qualified:
        leader_id = min(qualified, key=lambda competitor_id: (-qualified[competitor_id], competitor_id))
        leader = {"restaurant_id": leader_id, "name": names.get(leader_id, f"Restaurant {leader_id}"), "score": round(qualified[leader_id], 2)}

    row: Dict[str, Any] = {
        "aspect": aspect,
        "own_score": _round(own_score),
        "own_mentions": own_mentions,
        "competitor_avg": _round(competitor_avg),
        "competitors_scored": len(qualified),
        "leader": leader,
        "gap_vs_avg": None,
        "gap_vs_leader": None,
        "status": "INSUFFICIENT_DATA",
        "insufficient_reason": None,
    }
    if own_mentions < threshold:
        row["insufficient_reason"] = (
            f"Not enough data: {own_mentions} of your reviews mention {label}; at least {threshold} are needed."
        )
        return row
    if not qualified:
        row["insufficient_reason"] = (
            f"Not enough data: no competitor has at least {threshold} reviews mentioning {label}."
        )
        return row

    gap = own_score - competitor_avg
    row["gap_vs_avg"] = round(gap, 2)
    row["gap_vs_leader"] = round(own_score - qualified[leader["restaurant_id"]], 2)
    if gap < -margin:
        row["status"] = "LEARN"
    elif gap > margin and competitor_avg < settings.GAP_WEAK_COMPETITOR_AVG:
        row["status"] = "ATTACK"
    else:
        row["status"] = "KEEP"
    return row


def _rows_from_context(restaurant: Restaurant, names: Dict[int, str], mentions: Dict[int, Dict[str, List[Review]]]) -> List[Dict[str, Any]]:
    competitor_ids = [restaurant_id for restaurant_id in mentions if restaurant_id != restaurant.id]
    return [
        compute_gap_row(
            aspect,
            mentions[restaurant.id][aspect],
            {competitor_id: mentions[competitor_id][aspect] for competitor_id in competitor_ids},
            names,
        )
        for aspect in ASPECTS
    ]


def build_gap_table(db: Session, restaurant: Restaurant) -> Dict[str, Any]:
    competitive, names, mentions = _gap_context(db, restaurant)
    return {
        "restaurant_id": restaurant.id,
        "generated_at": datetime.now(timezone.utc),
        "min_reviews_per_criterion": settings.MIN_REVIEWS_PER_CRITERION,
        "tie_margin": settings.GAP_TIE_MARGIN,
        "weak_competitor_avg": settings.GAP_WEAK_COMPETITOR_AVG,
        "competitors_considered": competitive["scored_competitor_count"],
        "rows": _rows_from_context(restaurant, names, mentions),
    }


def _newest_first(review: Review) -> float:
    return -review.published_at.timestamp()


def _evidence_pools(
    row: Dict[str, Any],
    restaurant: Restaurant,
    mentions: Dict[int, Dict[str, List[Review]]],
) -> Tuple[List[Review], List[Review]]:
    """Return (primary, secondary) review pools for the criterion, most relevant first."""
    aspect = row["aspect"]
    own = mentions[restaurant.id][aspect]
    threshold = settings.MIN_REVIEWS_PER_CRITERION
    qualified_ids = [
        restaurant_id for restaurant_id in mentions
        if restaurant_id != restaurant.id and len(mentions[restaurant_id][aspect]) >= threshold
    ]
    own_low = sorted(own, key=lambda review: (review.rating, _newest_first(review)))
    own_high = sorted(own, key=lambda review: (-review.rating, _newest_first(review)))
    if row["status"] == "LEARN":
        leader = mentions[row["leader"]["restaurant_id"]][aspect]
        return sorted(leader, key=lambda review: (-review.rating, _newest_first(review))), own_low
    if row["status"] == "ATTACK":
        rivals = [review for restaurant_id in qualified_ids for review in mentions[restaurant_id][aspect]]
        return own_high, sorted(rivals, key=lambda review: (review.rating, _newest_first(review)))
    rivals = [review for restaurant_id in qualified_ids for review in mentions[restaurant_id][aspect]]
    return own_high, sorted(rivals, key=lambda review: (-review.rating, _newest_first(review)))


def _interleave(primary: Sequence[Review], secondary: Sequence[Review], limit: int) -> List[Review]:
    picked: List[Review] = []
    for index in range(max(len(primary), len(secondary))):
        for pool in (primary, secondary):
            if index < len(pool) and len(picked) < limit:
                picked.append(pool[index])
    return picked


def _heuristic_explanation(row: Dict[str, Any], restaurant: Restaurant) -> str:
    label = aspect_label(row["aspect"])
    own = row["own_score"]
    avg = row["competitor_avg"]
    count = row["competitors_scored"]
    leader = row["leader"]
    plural = "competitor" if count == 1 else "competitors"
    if row["status"] == "LEARN":
        return (
            f"Guests who mention {label} rate {leader['name']} {leader['score']:.1f}/5, while {restaurant.name} averages "
            f"{own:.1f}/5 across {row['own_mentions']} reviews. That is {abs(row['gap_vs_avg']):.1f} points below the "
            f"average of {count} {plural} ({avg:.1f}/5)."
        )
    if row["status"] == "ATTACK":
        return (
            f"{restaurant.name} leads on {label} with {own:.1f}/5 across {row['own_mentions']} reviews, while the "
            f"{count} {plural} average only {avg:.1f}/5. Guests mentioning {label} at competitors give lower ratings."
        )
    position = "level with" if abs(row["gap_vs_avg"]) <= settings.GAP_TIE_MARGIN else "ahead of"
    return (
        f"{restaurant.name} scores {own:.1f}/5 on {label} across {row['own_mentions']} reviews, {position} the "
        f"average of {count} {plural} ({avg:.1f}/5). {leader['name']} scores {leader['score']:.1f}/5."
    )


def _evidence_payload(reviews: Sequence[Review], restaurant: Restaurant, names: Dict[int, str]) -> List[Dict[str, Any]]:
    return [
        {
            "review_id": review.id,
            "restaurant_id": review.restaurant_id,
            "restaurant_name": names.get(review.restaurant_id, f"Restaurant {review.restaurant_id}"),
            "is_own": review.restaurant_id == restaurant.id,
            "rating": review.rating,
            "text": review.text,
            "published_at": review.published_at,
        }
        for review in reviews
    ]


def _llm_explanation(
    row: Dict[str, Any],
    restaurant: Restaurant,
    candidates: Sequence[Review],
    names: Dict[int, str],
) -> Tuple[str, List[Review], str]:
    """Ask OpenAI for a short, quote-grounded explanation. Raises on any invalid output."""
    from openai import OpenAI

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    model_name = settings.OPENAI_MODEL or "gpt-4o-mini"
    by_id = {review.id: review for review in candidates}
    quotes = [
        {
            "review_id": review.id,
            "restaurant": names.get(review.restaurant_id, ""),
            "is_owner_restaurant": review.restaurant_id == restaurant.id,
            "rating": review.rating,
            "text": review.text[:500],
        }
        for review in candidates
    ]
    facts = {
        "criterion": aspect_label(row["aspect"]),
        "owner_restaurant": restaurant.name,
        "owner_score": row["own_score"],
        "owner_reviews_mentioning_criterion": row["own_mentions"],
        "competitor_average": row["competitor_avg"],
        "competitors_scored": row["competitors_scored"],
        "leader": row["leader"],
        "gap_vs_average": row["gap_vs_avg"],
        "label": row["status"],
    }
    system_prompt = (
        "You explain why a restaurant is ahead of or behind its competitors on one criterion. "
        "Use ONLY the facts and the review quotes provided. Do not add any claim, number, dish, or cause that "
        "is not stated in them. If the quotes do not show a cause, say that the reviews only show the score difference. "
        "Answer in English with valid JSON."
    )
    user_prompt = (
        f"Facts:\n{json.dumps(facts, ensure_ascii=False)}\n\n"
        f"Review quotes:\n{json.dumps(quotes, ensure_ascii=False, indent=2)}\n\n"
        'Return {"explanation": "at most 2 short sentences", '
        '"evidence_review_ids": [2 or 3 review_id values from the quotes that support the explanation]}'
    )
    response = client.chat.completions.create(
        model=model_name,
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    parsed = json.loads(response.choices[0].message.content)
    explanation = parsed.get("explanation")
    evidence_ids = parsed.get("evidence_review_ids")
    if not isinstance(explanation, str) or not explanation.strip() or len(explanation) > 800:
        raise ValueError("Explanation missing or too long")
    if not isinstance(evidence_ids, list) or not 1 <= len(evidence_ids) <= EVIDENCE_LIMIT:
        raise ValueError("Evidence ids missing")
    if any(not isinstance(review_id, int) or review_id not in by_id for review_id in evidence_ids):
        raise ValueError("Evidence ids must come from the provided quotes")
    return explanation.strip(), [by_id[review_id] for review_id in dict.fromkeys(evidence_ids)], model_name


def explain_gap(db: Session, restaurant: Restaurant, aspect: str) -> Dict[str, Any]:
    if aspect not in ASPECTS:
        raise KeyError(aspect)
    _, names, mentions = _gap_context(db, restaurant)
    row = next(item for item in _rows_from_context(restaurant, names, mentions) if item["aspect"] == aspect)
    if row["status"] == "INSUFFICIENT_DATA":
        raise InsufficientDataError(row["insufficient_reason"])

    primary, secondary = _evidence_pools(row, restaurant, mentions)
    explanation = _heuristic_explanation(row, restaurant)
    evidence = _interleave(primary, secondary, EVIDENCE_LIMIT)
    model_name = "heuristic"
    if settings.OPENAI_API_KEY:
        candidates = _interleave(primary, secondary, LLM_CANDIDATES_PER_SIDE * 2)
        try:
            explanation, evidence, model_name = _llm_explanation(row, restaurant, candidates, names)
        except Exception as error:
            logger.error(f"OpenAI gap explanation failed: {error}. Falling back to heuristic explanation.")
            model_name = "heuristic-fallback"

    return {
        "aspect": aspect,
        "status": row["status"],
        "explanation": explanation,
        "evidence": _evidence_payload(evidence, restaurant, names),
        "model": model_name,
    }

"""Business logic for producing day-by-day travel plans."""
from __future__ import annotations

from itertools import cycle
from typing import Dict, Iterable, List, Sequence, Set

from .data import (
    ACTIVITY_LIBRARY,
    DEFAULT_DAILY_STRUCTURE,
    GUARDRAIL_RULES,
    INTEREST_OPTIONS,
)


def _normalize_interests(interests: Sequence[str]) -> List[str]:
    normalized = [interest for interest in interests if interest in INTEREST_OPTIONS]
    return normalized or INTEREST_OPTIONS[:3]


def _extract_guardrail_rules(guardrails: Sequence[str]) -> Dict[str, Set[str]]:
    require_tags: Set[str] = set()
    exclude_tags: Set[str] = set()
    for guardrail in guardrails:
        rule = GUARDRAIL_RULES.get(guardrail)
        if not rule:
            continue
        require_tags |= set(rule.get("require_tags", set()))
        exclude_tags |= set(rule.get("exclude_tags", set()))
    return {"require_tags": require_tags, "exclude_tags": exclude_tags}


def _filter_by_interest(interests: Iterable[str]) -> List[Dict[str, object]]:
    interest_set = set(interests)
    if not interest_set:
        return list(ACTIVITY_LIBRARY)
    scoped = [activity for activity in ACTIVITY_LIBRARY if activity["category"] in interest_set]
    return scoped or list(ACTIVITY_LIBRARY)


def _apply_guardrails(
    activities: List[Dict[str, object]],
    require_tags: Set[str],
    exclude_tags: Set[str],
) -> List[Dict[str, object]]:
    filtered: List[Dict[str, object]] = []
    for activity in activities:
        tags = set(activity.get("tags", set()))
        if exclude_tags and tags & exclude_tags:
            continue
        if require_tags and not require_tags.issubset(tags):
            continue
        filtered.append(activity)
    return filtered


def _daily_tip(items: List[Dict[str, object]], guardrails: Sequence[str]) -> str:
    guardrail_text = ", ".join(guardrails) if guardrails else "flexible day"
    highlight = items[0].get("tip") if items else "Mix high-energy stops with slow moments."
    return f"{highlight} Guardrails considered: {guardrail_text}."


def generate_itinerary(
    destination: str,
    days: int,
    interests: Sequence[str],
    guardrails: Sequence[str],
) -> Dict[str, object]:
    """Create a structured itinerary based on preferences."""
    try:
        parsed_days = int(days)
    except (TypeError, ValueError):
        parsed_days = 1
    safe_days = max(1, min(parsed_days, 30))
    normalized_destination = destination.strip() or "Your Destination"
    normalized_interests = _normalize_interests(interests)
    guardrail_summary = list(guardrails)
    constraints = _extract_guardrail_rules(guardrails)

    interest_pool = _filter_by_interest(normalized_interests)
    constrained_pool = _apply_guardrails(
        interest_pool,
        constraints["require_tags"],
        constraints["exclude_tags"],
    )

    if not constrained_pool and constraints["require_tags"]:
        constrained_pool = _apply_guardrails(interest_pool, set(), constraints["exclude_tags"])
    if not constrained_pool:
        constrained_pool = list(ACTIVITY_LIBRARY)

    activity_cycle = cycle(constrained_pool)
    interest_cycle = cycle(normalized_interests)

    day_plans: List[Dict[str, object]] = []
    for day_index in range(safe_days):
        slot_details: List[Dict[str, object]] = []
        for slot in DEFAULT_DAILY_STRUCTURE:
            activity = next(activity_cycle)
            slot_details.append(
                {
                    "slot": slot,
                    "name": activity["name"],
                    "category": activity["category"],
                    "description": activity["description"],
                    "duration_hours": activity.get("duration_hours", 2),
                    "tip": activity.get("tip", "Use this moment to slow down and take photos."),
                }
            )
        daily_interest = next(interest_cycle)
        day_plans.append(
            {
                "day": day_index + 1,
                "theme": f"{daily_interest} focus",
                "items": slot_details,
                "daily_tip": _daily_tip(slot_details, guardrail_summary),
            }
        )

    guardrail_message = (
        f"Guardrails locked in: {', '.join(guardrail_summary)}"
        if guardrail_summary
        else "No guardrails selected. Using balanced variety."
    )

    highlight_text = ", ".join(dict.fromkeys(normalized_interests))

    return {
        "destination": normalized_destination,
        "days": day_plans,
        "interests": normalized_interests,
        "guardrails": guardrail_summary,
        "guardrail_message": guardrail_message,
        "highlight_text": highlight_text,
    }

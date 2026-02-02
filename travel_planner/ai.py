"""OpenAI-powered helpers for itinerary generation and insights."""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional, Sequence, Tuple

from .data import DEFAULT_DAILY_STRUCTURE

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - handled at runtime
    OpenAI = None  # type: ignore[assignment]

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
ITINERARY_SYSTEM_PROMPT = (
    "You are an elite travel concierge. Craft practical, family-friendly itineraries with "
    "clear pacing, honoring constraints exactly as provided. Always respond with strict JSON."
)
SUMMARY_SYSTEM_PROMPT = (
    "You are a concise travel concierge. Summarize multi-day itineraries in under 180 words, "
    "calling out pacing tips, standout activities, and how guardrails are respected."
)


def _get_openai_client() -> Tuple[Optional[OpenAI], Optional[str]]:
    if OpenAI is None:
        return None, "Install the openai package to enable AI planning."
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None, "Set OPENAI_API_KEY to unlock AI planning."
    try:
        return OpenAI(api_key=api_key), None
    except Exception:
        return None, "OpenAI client initialization failed. Verify the key and package version."


def _safe_int(value: object, default: int = 1) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(parsed, 30))


def _extract_json_block(raw_text: str) -> str:
    raw_text = raw_text.strip()
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("JSON block not found in AI response.")
    return raw_text[start : end + 1]


def _build_plan_from_json(
    payload: Dict[str, object],
    destination: str,
    interests: Sequence[str],
    guardrails: Sequence[str],
) -> Dict[str, object]:
    highlight = payload.get("highlight_text") or ", ".join(dict.fromkeys(interests)) or "Varied interests"
    guardrail_message = payload.get("guardrail_message") or (
        f"Guardrails locked in: {', '.join(guardrails)}" if guardrails else "No guardrails selected."
    )

    structured_days: List[Dict[str, object]] = []
    for index, day in enumerate(payload.get("days", []) or payload.get("daily_plan", []), start=1):
        slots_data = day.get("slots", []) if isinstance(day, dict) else []
        normalized_slots: List[Dict[str, object]] = []
        if not slots_data:
            for slot_label in DEFAULT_DAILY_STRUCTURE:
                normalized_slots.append(
                    {
                        "slot": slot_label,
                        "name": "Free exploration",
                        "category": "Flexible",
                        "description": "Build your own moment in this slot.",
                        "duration_hours": 2,
                        "tip": "Use this pocket to rest or follow spontaneous inspiration.",
                    }
                )
        else:
            for slot in slots_data:
                if not isinstance(slot, dict):
                    continue
                slot_name = slot.get("slot") or slot.get("time_block")
                if not slot_name:
                    slot_name = DEFAULT_DAILY_STRUCTURE[len(normalized_slots) % len(DEFAULT_DAILY_STRUCTURE)]
                normalized_slots.append(
                    {
                        "slot": slot_name,
                        "name": slot.get("name", "Experience"),
                        "category": slot.get("category", "General"),
                        "description": slot.get("description", ""),
                        "duration_hours": slot.get("duration_hours", 2),
                        "tip": slot.get("tip", "Capture a few photos."),
                    }
                )

        structured_days.append(
            {
                "day": day.get("day", index) if isinstance(day, dict) else index,
                "theme": day.get("theme", "Balanced focus") if isinstance(day, dict) else "Balanced focus",
                "items": normalized_slots,
                "daily_tip": day.get("daily_tip", "Blend must-see icons with slow blocks."),
            }
        )

    return {
        "destination": destination.strip() or "Your Destination",
        "days": structured_days or [],
        "interests": list(interests),
        "guardrails": list(guardrails),
        "guardrail_message": guardrail_message,
        "highlight_text": highlight,
        "ai_summary": payload.get("ai_summary") or payload.get("summary"),
    }


def generate_ai_itinerary(
    destination: str,
    days: int,
    interests: Sequence[str],
    guardrails: Sequence[str],
) -> Tuple[Optional[Dict[str, object]], Optional[str]]:
    client, error = _get_openai_client()
    if error:
        return None, error
    assert client is not None

    safe_days = _safe_int(days)
    interest_text = ", ".join(interests) if interests else "General explorer"
    guardrail_text = ", ".join(guardrails) if guardrails else "None specified"
    prompt = (
        "Design a {days}-day plan for {destination}. Interests: {interests}. Guardrails: {guardrails}. "
        "Return strict JSON with keys days (list), guardrail_message, highlight_text, ai_summary. Each day must "
        "include a theme, daily_tip, and slots array for Morning, Afternoon, and Evening with name, category, "
        "description, duration_hours (1-4), and tip."
    ).format(
        days=safe_days,
        destination=destination.strip() or "the traveler",
        interests=interest_text,
        guardrails=guardrail_text,
    )

    try:
        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            temperature=0.7,
            max_tokens=1200,
            messages=[
                {"role": "system", "content": ITINERARY_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
    except Exception:
        return None, "OpenAI request failed. Check connectivity and API quota."

    if not response.choices:
        return None, "OpenAI returned no choices. Try again shortly."

    raw_content = (response.choices[0].message.content or "").strip()
    if not raw_content:
        return None, "OpenAI response was empty."

    try:
        payload = json.loads(_extract_json_block(raw_content))
    except Exception:
        return None, "OpenAI response was not valid JSON. Try regenerating."

    plan = _build_plan_from_json(payload, destination, interests, guardrails)
    return plan, None


def _format_outline(plan: Dict[str, object]) -> str:
    lines: List[str] = []
    for day in plan.get("days", []):
        lines.append(f"Day {day['day']} ({day['theme']}): {day['daily_tip']}")
        for item in day.get("items", []):
            lines.append(
                f"- {item['slot']}: {item['name']} [{item['category']}] - {item['description']}"
            )
    return "\n".join(lines)


def summarize_itinerary(plan: Dict[str, object]) -> Tuple[Optional[str], Optional[str]]:
    client, error = _get_openai_client()
    if error:
        return None, error
    assert client is not None

    outline = _format_outline(plan)
    user_prompt = (
        f"Destination: {plan.get('destination', 'Unknown')}.\n"
        f"Guardrails: {plan.get('guardrail_message', 'None')}\n"
        f"Focus interests: {plan.get('highlight_text', 'Varied')}\n"
        f"{outline}"
    )

    try:
        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            temperature=0.6,
            max_tokens=400,
            messages=[
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
    except Exception:
        return None, "OpenAI request failed. Confirm API key, network access, or usage limits."

    if not response.choices:
        return None, "OpenAI returned no choices. Try again shortly."
    summary = response.choices[0].message.content or ""
    summary = summary.strip()
    if not summary:
        return None, "OpenAI response was empty. Try regenerating."
    return summary, None

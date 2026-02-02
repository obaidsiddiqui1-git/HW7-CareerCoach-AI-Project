"""PDF generation utilities for the travel planner."""
from __future__ import annotations

import unicodedata
from typing import Dict, Sequence

from fpdf import FPDF


def _content_width(pdf: FPDF) -> float:
    return pdf.w - pdf.l_margin - pdf.r_margin


def _normalize_theme_label(theme: str) -> str:
    cleaned = theme.replace(" focus", "").strip()
    return cleaned.title() if cleaned else "Balanced Focus"


def _format_focus_text(interests: Sequence[str], fallback: str | None = None) -> str:
    deduped = [label for label in dict.fromkeys(interests or []) if label]
    if not deduped and fallback:
        deduped = [fallback]
    if not deduped:
        return "Balanced Variety"
    if len(deduped) == 1:
        return deduped[0]
    return ", ".join(deduped[:-1]) + f" & {deduped[-1]}"


def _ascii(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return normalized.encode("ascii", "ignore").decode("ascii")


def _write_day_section(pdf: FPDF, destination: str, day_block: Dict[str, object]) -> None:
    width = _content_width(pdf)
    pdf.set_font("Helvetica", "B", 14)
    header = f"Day {day_block['day']} - {destination} ({_normalize_theme_label(day_block.get('theme', ''))})"
    pdf.cell(0, 8, header, ln=1)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(width, 6, _ascii(f"Daily tip: {day_block.get('daily_tip', 'Balance landmarks with recharge moments.')}"))
    pdf.ln(1)

    for idx, item in enumerate(day_block["items"], start=1):
        pdf.set_font("Helvetica", "B", 11)
        headline = _ascii(f"{idx}. {item['slot']}: {item['name']}")
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(width, 6, headline)
        pdf.set_font("Helvetica", "", 11)
        details = _ascii(f"{item['description']}")
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(width, 6, details)
        if item.get("tip"):
            pdf.set_font("Helvetica", "I", 10)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(width, 5, "Tip:")
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(width, 5, _ascii(item["tip"]))
        pdf.ln(1)


def build_itinerary_pdf(
    plan: Dict[str, object],
) -> bytes:
    """Create a PDF (as bytes) from an itinerary plan."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, f"{plan['destination']} Travel Plan", ln=1, align="C")
    pdf.set_font("Helvetica", "", 12)
    width = _content_width(pdf)
    focus_line = _format_focus_text(plan.get("interests", []), plan.get("highlight_text"))
    guard_line = plan["guardrail_message"]
    pdf.multi_cell(width, 7, f"Focus: {focus_line}", align="C")
    pdf.multi_cell(width, 6, guard_line, align="C")
    pdf.multi_cell(width, 6, f"Trip length: {len(plan['days'])} day(s)", align="C")
    pdf.ln(4)

    for day in plan["days"]:
        _write_day_section(pdf, plan["destination"], day)
        pdf.ln(2)

    raw_pdf = pdf.output(dest="S")
    if isinstance(raw_pdf, str):
        return raw_pdf.encode("latin-1")
    return bytes(raw_pdf)

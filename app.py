from dotenv import load_dotenv
import streamlit as st

from travel_planner.ai import generate_ai_itinerary, summarize_itinerary
from travel_planner.data import GUARDRAIL_OPTIONS, INTEREST_OPTIONS
from travel_planner.itinerary import generate_itinerary
from travel_planner.pdf import build_itinerary_pdf

load_dotenv()

st.set_page_config(page_title="Travel Guide Planner", page_icon="🧭", layout="wide")


def _init_state() -> None:
    defaults = {
        "destination": "",
        "days": 5,
        "interests": INTEREST_OPTIONS[:3],
        "guardrails": [],
        "itinerary": None,
        "ai_summary": None,
        "ai_summary_error": None,
        "plan_from_ai": False,
        "ai_generation_error": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _reset_form() -> None:
    for key in [
        "destination",
        "days",
        "interests",
        "guardrails",
        "itinerary",
        "ai_summary",
        "ai_summary_error",
        "plan_from_ai",
        "ai_generation_error",
    ]:
        st.session_state.pop(key, None)
    st.rerun()


def _normalize_theme_label(theme: str) -> str:
    cleaned = theme.replace(" focus", "").strip()
    return cleaned.title() if cleaned else "Balanced Focus"


def _format_focus_text(interests: list[str], fallback: str | None = None) -> str:
    deduped = [label for label in dict.fromkeys(interests or []) if label]
    if not deduped and fallback:
        deduped = [fallback]
    if not deduped:
        return "Balanced Variety"
    if len(deduped) == 1:
        return deduped[0]
    return ", ".join(deduped[:-1]) + f" & {deduped[-1]}"


def _format_day_block(destination: str, day: dict) -> str:
    theme_label = _normalize_theme_label(day.get("theme", ""))
    lines = [f"Day {day['day']} - {destination} ({theme_label})"]
    for idx, item in enumerate(day.get("items", []), start=1):
        lines.append(
            f"{idx}. {item['slot']}: {item['name']} - {item['description']}"
        )
    lines.append(f"Tip: {day.get('daily_tip', 'Mix must-see icons with restorative pauses.')}")
    return "\n".join(lines)


def _render_plan(plan: dict) -> None:
    st.subheader(f"{plan['destination']} itinerary")
    focus_text = _format_focus_text(plan.get("interests", []), plan.get("highlight_text"))
    st.markdown(f"**Focus:** {focus_text}")
    st.caption(plan["guardrail_message"])

    if st.session_state.get("plan_from_ai"):
        st.info("Itinerary crafted by OpenAI. Adjust interests or guardrails to regenerate.")
    elif st.session_state.get("ai_generation_error"):
        st.warning(
            f"AI planner unavailable: {st.session_state['ai_generation_error']}. Showing rule-based fallback."
        )

    day_tabs = st.tabs([f"Day {day['day']}" for day in plan["days"]])
    for tab, day in zip(day_tabs, plan["days"]):
        with tab:
            day_block = _format_day_block(plan["destination"], day)
            st.text(day_block)

    pdf_data = build_itinerary_pdf(plan)
    safe_name = plan["destination"].strip().replace(" ", "_").lower() or "travel_plan"
    st.download_button(
        label="Download PDF travel plan",
        data=pdf_data,
        file_name=f"{safe_name}_itinerary.pdf",
        mime="application/pdf",
    )


def _render_ai_section(plan: dict) -> None:
    st.divider()
    st.subheader("AI insight (optional)")
    st.caption("Uses your OPENAI_API_KEY to describe the flow of this trip.")

    stored_summary = st.session_state.get("ai_summary") or plan.get("ai_summary")
    stored_error = st.session_state.get("ai_summary_error")

    if stored_summary:
        st.success(stored_summary)
    elif stored_error:
        st.error(stored_error)
    else:
        st.info("Generate a short narrative recap to share with travelers.")

    if st.button("Generate AI insight", type="primary"):
        with st.spinner("Contacting OpenAI..."):
            summary, error = summarize_itinerary(plan)
        if summary:
            st.session_state["ai_summary"] = summary
            st.session_state["ai_summary_error"] = None
            st.success(summary)
        else:
            st.session_state["ai_summary"] = None
            st.session_state["ai_summary_error"] = error or "Unable to create insight."
            st.error(st.session_state["ai_summary_error"])


def main() -> None:
    _init_state()

    st.title("Travel Guide Planner")
    st.write("Design a day-by-day itinerary with your favorite interests and guardrails.")

    with st.form(key="planner_form", clear_on_submit=False):
        destination = st.text_input(
            "Destination to Travel",
            value=st.session_state["destination"],
            placeholder="e.g., Lisbon",
        )
        days = st.number_input(
            "Number of days",
            min_value=1,
            max_value=30,
            value=int(st.session_state["days"]),
            help="We will map three anchor experiences per day by default.",
        )
        interests = st.multiselect(
            "Special interests",
            INTEREST_OPTIONS,
            default=st.session_state["interests"],
            help="Select what excites you. We will rotate these themes across days.",
        )
        guardrails = st.multiselect(
            "Guardrails to honor",
            GUARDRAIL_OPTIONS,
            default=st.session_state["guardrails"],
            help="Restrict the plan (e.g., kids friendly only, no walking tours).",
        )

        submitted = st.form_submit_button("Generate travel plan", type="primary")

    _, reset_col = st.columns([3, 1])
    with reset_col:
        st.button("Reset Form", type="secondary", on_click=_reset_form)

    if submitted:
        if not destination.strip():
            st.warning("Please provide a destination to start your plan.")
        else:
            with st.spinner("Asking OpenAI to craft your trip..."):
                ai_plan, ai_error = generate_ai_itinerary(destination, int(days), interests, guardrails)

            if ai_plan:
                plan = ai_plan
                st.session_state["plan_from_ai"] = True
                st.session_state["ai_generation_error"] = None
                st.session_state["ai_summary"] = plan.get("ai_summary")
                st.session_state["ai_summary_error"] = None
                st.success("AI travel guide ready. Scroll down to review or download the PDF.")
            else:
                plan = generate_itinerary(destination, int(days), interests, guardrails)
                st.session_state["plan_from_ai"] = False
                st.session_state["ai_generation_error"] = ai_error or "AI planner unavailable."
                st.session_state["ai_summary"] = None
                st.session_state["ai_summary_error"] = None
                if ai_error:
                    st.warning(f"AI planner unavailable: {ai_error}. Showing rule-based fallback.")
                else:
                    st.info("Using rule-based fallback itinerary.")

            st.session_state["destination"] = destination
            st.session_state["days"] = int(days)
            st.session_state["interests"] = interests or INTEREST_OPTIONS[:3]
            st.session_state["guardrails"] = guardrails
            st.session_state["itinerary"] = plan

    current_plan = st.session_state.get("itinerary")
    if current_plan:
        _render_plan(current_plan)
        _render_ai_section(current_plan)
    else:
        st.info("Fill out the form and click Generate travel plan to see your itinerary here.")


if __name__ == "__main__":
    main()

"""Streamlit HITL dashboard for marketing campaign generation, review, and approval."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st
from pydantic import ValidationError

from campaign.config import get_settings
from campaign.models import USER_ID_REGEX, ProductBrief
from campaign.sanitize import HostileInputError
from campaign.service import CampaignService


def get_service() -> CampaignService:
    settings = get_settings()
    return CampaignService(settings=settings)


def main() -> None:
    st.set_page_config(page_title="Brightside Goods — Campaign Studio", layout="wide")
    settings = get_settings()
    service = get_service()

    # 1. Sidebar: Mode banner and User ID
    st.sidebar.title("Campaign Studio")

    # Mode banner (SPEC V4 / TASKS T12)
    if settings.llm_mode == "scripted":
        st.sidebar.warning("SCRIPTED DEMO: outputs are deterministic, not Gemini")
    else:
        st.sidebar.info(f"LIVE GEMINI: {settings.gemini_model}")

    user_id = st.sidebar.text_input("User ID", value="USR-manager", key="user_id").strip()

    # Retrieve current active run if stored in session state
    current_run_id = st.session_state.get("current_run_id")
    active_run = service.store.get_run(current_run_id) if current_run_id else None

    # Telemetry in sidebar
    if active_run:
        st.sidebar.subheader("Run Telemetry")
        st.sidebar.metric("Status", active_run.status)
        st.sidebar.metric("Tool Calls Used", f"{active_run.tool_calls_used}/15")
        st.sidebar.metric("Notional Cost", f"${active_run.cost_usd:.4f}/$0.25")
        st.sidebar.caption(
            "Cost is notional (tokens x pricing rate); free tier and scripted runs bill $0.00."
        )

        # Compute tool success rate for this run from trace log
        trace_path = Path(settings.trace_log_path)
        if trace_path.exists():
            traces: list[dict] = []
            with open(trace_path, encoding="utf-8") as f:
                for line in f:
                    try:
                        rec = json.loads(line)
                        if (
                            rec.get("run_id") == active_run.run_id
                            and rec.get("type") == "tool_call"
                        ):
                            traces.append(rec)
                    except json.JSONDecodeError:
                        continue
            if traces:
                ok_count = sum(1 for t in traces if t.get("ok"))
                rate = (ok_count / len(traces)) * 100
                st.sidebar.metric("Tool Success Rate", f"{rate:.1f}%")

    # Main area
    st.title("Brightside Goods — Marketing Campaign Studio")
    st.caption(
        "AI-assisted campaign angle research, demographic insight, and multi-channel copy drafting."
    )

    # 2. Product Brief Input Form
    st.subheader("1. Product Brief")
    with st.form("product_form"):
        col1, col2 = st.columns(2)
        with col1:
            prod_name = st.text_input(
                "Product Name",
                value="Brightside Smart Water Bottle",
                key="product_name",
            )
            segment = st.selectbox(
                "Audience Segment",
                options=[
                    "young-professionals",
                    "fitness-enthusiasts",
                    "eco-conscious-families",
                    "students",
                ],
                key="segment",
            )
        with col2:
            budget_usd = st.number_input(
                "Campaign Budget (USD)",
                min_value=100.0,
                max_value=100000.0,
                value=5000.0,
                step=500.0,
                key="budget_usd",
            )
            prod_desc = st.text_area(
                "Product Description",
                value="Smart insulated stainless steel water bottle with glow reminder and Bluetooth hydration tracking",
                key="product_description",
            )

        generate_submitted = st.form_submit_button("Generate angles")

    if generate_submitted:
        if not USER_ID_REGEX.fullmatch(user_id):
            st.error(f"Invalid User ID '{user_id}'. Must match ^[A-Za-z][A-Za-z0-9_.-]{{1,31}}$")
        else:
            try:
                brief = ProductBrief(
                    name=prod_name,
                    description=prod_desc,
                    segment=segment,
                    budget_usd=float(budget_usd),
                )
                result = service.start_run(user_id=user_id, brief=brief)
                if result.status == "RATE_LIMITED":
                    st.warning(
                        f"Rate limited: please wait {result.wait_seconds:.1f} seconds before retrying."
                    )
                elif result.status == "AWAITING_APPROVAL":
                    st.session_state["current_run_id"] = result.run.run_id
                    st.success(
                        f"Phase 1 Complete: 5 campaign angles generated! Run ID: {result.run.run_id}"
                    )
                    st.rerun()
                else:
                    st.error(f"Run ended in status: {result.status}")
            except HostileInputError:
                st.error("Hostile brief rejected: prompt injection detected.")
            except ValidationError as e:
                st.error(f"Validation error: {e}")

    # Re-fetch active run if updated
    current_run_id = st.session_state.get("current_run_id")
    active_run = service.store.get_run(current_run_id) if current_run_id else None

    # 3. Angle Review & Human Gate
    if active_run and active_run.angles and active_run.status == "AWAITING_APPROVAL":
        st.subheader("2. Review Proposed Campaign Angles")
        st.write(
            "Select one angle to approve for Phase 2 advertising copy drafting, or reject all."
        )

        for idx, angle in enumerate(active_run.angles.angles):
            with st.container(border=True):
                st.markdown(f"**Angle [{idx}]: {angle.title}**")
                st.text(f"Positioning: {angle.positioning}")
                st.text(f"Key Message: {angle.key_message}")
                st.text(f"Estimated Reach: {angle.estimated_reach:,}")
                st.text(f"Competitor Contrast: {angle.competitor_contrast}")
                st.text(f"Evidence: {', '.join(angle.evidence)}")

        selected_angle_idx = st.radio(
            "Select Angle to Approve",
            options=list(range(len(active_run.angles.angles))),
            format_func=lambda i: f"[{i}] {active_run.angles.angles[i].title}",
            key="angle_choice",
        )

        col_approve, col_reject = st.columns(2)
        with col_approve:
            if st.button("Approve and draft package", type="primary", key="approve_btn"):
                res = service.approve_angle(
                    run_id=active_run.run_id,
                    selected_index=selected_angle_idx,
                    user_id=user_id,
                )
                if res.status == "COMPLETED":
                    st.success("Angle approved! Campaign package successfully drafted.")
                else:
                    st.error(f"Drafting ended in status: {res.status}")
                st.rerun()

        with col_reject:
            if st.button("Reject", key="reject_btn"):
                service.reject_run(run_id=active_run.run_id, user_id=user_id)
                st.warning(f"Run {active_run.run_id} has been rejected.")
                st.rerun()

    # 4. Status alerts for terminal runs
    if active_run:
        if active_run.status == "REJECTED":
            st.warning(f"Run {active_run.run_id} was rejected.")
        elif active_run.status in ("LIMIT_REACHED", "BUDGET_EXCEEDED", "FAILED"):
            st.error(f"Run {active_run.run_id} ended in status: {active_run.status}")

    # 5. Display Approved Campaign Package
    if active_run and active_run.package:
        st.subheader(f"3. Approved Campaign Package: '{active_run.package.angle_title}'")
        tab_gads, tab_insta, tab_email = st.tabs(["Google Ads", "Instagram", "Email"])

        pkg = active_run.package
        with tab_gads:
            st.markdown("#### Responsive Search Ads")
            for i, hl in enumerate(pkg.google_ads.headlines, start=1):
                st.caption(f"Headline {i} ({len(hl)}/30 chars)")
                st.text(hl)
            for i, desc in enumerate(pkg.google_ads.descriptions, start=1):
                st.caption(f"Description {i} ({len(desc)}/90 chars)")
                st.text(desc)

        with tab_insta:
            st.markdown("#### Instagram Post")
            st.caption(f"Caption ({len(pkg.instagram.caption)}/2200 chars)")
            st.text(pkg.instagram.caption)
            st.caption(f"Hashtags ({len(pkg.instagram.hashtags)} tags)")
            st.text(" ".join(pkg.instagram.hashtags))
            st.caption("Image Concept Idea")
            st.text(pkg.instagram.image_idea)

        with tab_email:
            st.markdown("#### Marketing Email")
            st.caption(f"Subject ({len(pkg.email.subject)}/60 chars)")
            st.text(pkg.email.subject)
            st.caption(f"Preheader ({len(pkg.email.preheader)}/100 chars)")
            st.text(pkg.email.preheader)
            st.caption(f"Email Body ({len(pkg.email.body)}/1200 chars)")
            st.text(pkg.email.body)
            st.caption(f"Call to Action ({len(pkg.email.cta)}/40 chars)")
            st.text(f"[{pkg.email.cta}]")

    # 6. Observability: Run Trace Expander
    if active_run:
        with st.expander("Run Trace & Observability Telemetry"):
            st.text(f"Run Identifier: {active_run.run_id}")
            st.text(f"Status:         {active_run.status}")
            st.text(f"Tools Used:     {active_run.tool_calls_used}/15")
            st.text(f"Notional Spend: ${active_run.cost_usd:.4f}/$0.25")
            st.markdown("---")

            trace_path = Path(settings.trace_log_path)
            found_traces = False
            if trace_path.exists():
                with open(trace_path, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            rec = json.loads(line)
                            if rec.get("run_id") == active_run.run_id:
                                found_traces = True
                                if rec.get("type") == "tool_call":
                                    status_flag = (
                                        "OK"
                                        if rec.get("ok")
                                        else f"FAILED ({rec.get('error_code')})"
                                    )
                                    st.text(
                                        f"[Tool Call] {rec.get('tool')} | {status_flag} | {rec.get('duration_ms')}ms\n"
                                        f"             Args: {rec.get('args')}"
                                    )
                                elif rec.get("type") == "model_step":
                                    st.text(
                                        f"[Model Step {rec.get('step')}] in={rec.get('input_tokens')}, "
                                        f"out={rec.get('output_tokens')}, cost=${rec.get('running_cost_usd'):.4f}"
                                    )
                        except json.JSONDecodeError:
                            continue
            if not found_traces:
                st.text("(No trace records found for this run)")


if __name__ == "__main__":
    main()

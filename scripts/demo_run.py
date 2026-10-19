"""Full marketing campaign workflow demo in scripted mode."""

from __future__ import annotations

import sys

from campaign.config import Settings
from campaign.models import ProductBrief
from campaign.service import CampaignService


def main() -> int:
    settings = Settings(llm_mode="scripted")
    service = CampaignService(settings=settings)

    brief = ProductBrief(
        name="Brightside Smart Water Bottle",
        description="Smart insulated stainless steel water bottle with glow reminder and Bluetooth hydration tracking",
        segment="young-professionals",
        budget_usd=5000.0,
    )

    print("=" * 70)
    print("STARTING CAMPAIGN RUN (SCRIPTED DEMO)")
    print(f"Product: {brief.name}")
    print(f"Segment: {brief.segment}")
    print(f"Budget:  ${brief.budget_usd:.2f}")
    print("=" * 70)

    import random

    user_id = f"demo_user_{random.randint(1000, 9999)}"

    # Phase 1: Research and generate 5 angles
    run = service.start_run(brief, user_id=user_id)
    if run.status == "RATE_LIMITED":
        print(f"ERROR: Run rate limited. Wait {run.wait_seconds:.1f}s.")
        return 1

    print("\nPhase 1 Complete!")
    print(f"Run ID:          {run.run_id}")
    print(f"Status:          {run.status}")
    print(f"Tool calls used: {run.tool_calls_used}/15")
    print(
        f"Notional cost:   ${run.cost_usd:.4f} (Notional: tokens x pricing; free tier bills $0.00)\n"
    )

    if not run.angles or len(run.angles.angles) != 5:
        print("ERROR: Did not receive 5 campaign angles!")
        return 1

    print("--- 5 PROPOSED CAMPAIGN ANGLES ---")
    for i, angle in enumerate(run.angles.angles):
        print(f"\n[{i}] {angle.title}")
        print(f"    Positioning: {angle.positioning}")
        print(f"    Key Message: {angle.key_message}")
        print(f"    Reach:       {angle.estimated_reach:,}")
        print(f"    Evidence:    {', '.join(angle.evidence)}")

    # Phase 2: Approve angle 0 and draft package
    selected_idx = 0
    print(f"\nManager Approval: Approving Angle [{selected_idx}]...")
    completed_run = service.approve_angle(run.run_id, selected_index=selected_idx, user_id=user_id)
    print("\nPhase 2 Complete!")
    print(f"Status:                {completed_run.status}")
    print(f"Total tool calls used: {completed_run.tool_calls_used}/15")
    print(
        f"Total notional cost:   ${completed_run.cost_usd:.4f} (Notional: tokens x pricing; free tier bills $0.00)\n"
    )

    pkg = completed_run.package
    if not pkg:
        print("ERROR: Campaign package not generated!")
        return 1

    print("=" * 70)
    print(f"GENERATED CAMPAIGN PACKAGE: '{pkg.angle_title}'")
    print("=" * 70)
    print("\n[Google Ads]")
    print(f"Headlines:    {' | '.join(pkg.google_ads.headlines)}")
    print(f"Descriptions: {' // '.join(pkg.google_ads.descriptions)}")

    print("\n[Instagram]")
    print(f"Caption:      {pkg.instagram.caption}")
    print(f"Hashtags:     {' '.join(pkg.instagram.hashtags)}")
    print(f"Image Idea:   {pkg.instagram.image_idea}")

    print("\n[Email Copy]")
    print(f"Subject:      {pkg.email.subject}")
    print(f"Preheader:    {pkg.email.preheader}")
    print(f"Body:\n{pkg.email.body}")
    print(f"CTA:          [{pkg.email.cta}]")
    print("\nDemo run completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

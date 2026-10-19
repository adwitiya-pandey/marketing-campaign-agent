"""Deterministic scripted chat model for testing and offline execution, not an LLM."""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

USAGE = {"input_tokens": 450, "output_tokens": 150, "total_tokens": 600}


def _get_demo_product_key(prompt_text: str) -> str:
    text = prompt_text.lower()
    if "shoe" in text or "trail" in text:
        return "trail-running-shoes"
    if "lunch" in text or "bento" in text:
        return "reusable-lunch-box"
    return "smart-water-bottle"


SCRIPTED_ANGLES = {
    "smart-water-bottle": [
        {
            "title": "Smart Hydration for Busy Professionals",
            "positioning": "The intelligent hydration system designed specifically for desk-bound professionals and daily commuters.",
            "target_insight": "SQL reveals young-professionals maintain $412.50 average lifetime value and prioritize wellness tech.",
            "key_message": "Build healthy hydration habits automatically without interrupting your workday.",
            "evidence": [
                "Search shows top competitor lacks insulated lid",
                "68% of customers prefer 24oz capacity",
            ],
            "estimated_reach": 54000,
            "competitor_contrast": "Unlike HydroSmart, features 24-hour chilled vacuum insulation with zero plastic parts.",
        },
        {
            "title": "Zero-Waste Campus Essential",
            "positioning": "Rugged, leak-proof smart hydration built to survive university lecture halls and library sessions.",
            "target_insight": "SQL shows student segment purchases containers frequently with high price elasticity.",
            "key_message": "One bottle to power your entire campus day sustainably.",
            "evidence": [
                "Competitor plastic bottles fail drop durability tests",
                "Students prefer impact-resistant sleeves",
            ],
            "estimated_reach": 48000,
            "competitor_contrast": "Double-wall stainless steel survives heavy backpack drops that crack competitor bottles.",
        },
        {
            "title": "Endurance Athlete Performance Companion",
            "positioning": "Precision hydration tracking and glow reminders tailored for long-distance training and workouts.",
            "target_insight": "Demographic queries indicate fitness-enthusiasts have the highest multi-item purchase rate.",
            "key_message": "Optimize workout recovery with real-time hydration metrics.",
            "evidence": ["Search highlights fitness wearables integration demand"],
            "estimated_reach": 60000,
            "competitor_contrast": "Bluetooth sensor syncs directly with workout wearables without requiring extra subscription apps.",
        },
        {
            "title": "Family Eco-Friendly Daily Health",
            "positioning": "Non-toxic, dishwasher-safe smart hydration designed for health-conscious family routines.",
            "target_insight": "SQL data indicates eco-conscious-families buy across hydration and food prep categories.",
            "key_message": "Pure taste, zero toxins, and complete peace of mind for the whole family.",
            "evidence": ["EcoConsumer trends report 70% demand for BPA-free stainless drinkware"],
            "estimated_reach": 42000,
            "competitor_contrast": "Modular food-grade silicone spout replaces easily without needing to discard the bottle.",
        },
        {
            "title": "Executive Minimalist Desk Edition",
            "positioning": "Sleek matte design fitting modern executive workspace aesthetics with subtle LED reminders.",
            "target_insight": "High-income customers in North and West regions demonstrate high repeat purchase loyalty.",
            "key_message": "Sophisticated hydration that elevates your workspace aesthetic.",
            "evidence": [
                "Customer reviews favor minimalist form factor over bulky plastic fitness bottles"
            ],
            "estimated_reach": 45000,
            "competitor_contrast": "Whisper-quiet silent notification ring replaces loud, intrusive chimes found in cheap rivals.",
        },
    ],
    "trail-running-shoes": [
        {
            "title": "Alpine Grip Rock Plate Defender",
            "positioning": "Engineered for technical alpine ascents with puncture-resistant stone shielding.",
            "target_insight": "Demographic analysis shows high spend in footwear category among active outdoor runners.",
            "key_message": "Tackle the most aggressive trails with confidence and zero slippage.",
            "evidence": ["Competitor reviews cite premature lug wear on wet rocky trails"],
            "estimated_reach": 60000,
            "competitor_contrast": "Vibram Megagrip compound lasts 40% longer than standard EVA soles.",
        },
        {
            "title": "Ultralight Mountain Commuter Hybrid",
            "positioning": "Seamless road-to-trail transition shoe for urban runners heading into weekend wilderness.",
            "target_insight": "Young professionals prioritize versatile gear bridging weekday fitness and weekend trips.",
            "key_message": "From city pavement to mountain summit in a single shoe.",
            "evidence": [
                "Search reports hybrid road-to-trail is the fastest growing footwear category"
            ],
            "estimated_reach": 54000,
            "competitor_contrast": "Dual-density foam balances road shock absorption with off-road trail bite.",
        },
        {
            "title": "Sustainable Eco-Trail Pioneer",
            "positioning": "Crafted from 100% recycled ocean plastic uppers and sustainable algae foam.",
            "target_insight": "Eco-conscious customer segment has 2.4x higher affinity for verified sustainable materials.",
            "key_message": "Leave no trace on the trails you love.",
            "evidence": [
                "Consumer research shows eco runners actively switch brands for ocean-bound plastic soles"
            ],
            "estimated_reach": 42000,
            "competitor_contrast": "First performance trail runner offering full cradle-to-cradle sole recycling.",
        },
        {
            "title": "Ultra-Marathon Blister-Free Endurance",
            "positioning": "Wide anatomical toe box with zero-friction lining designed for 50-mile plus expeditions.",
            "target_insight": "High lifetime value customers purchase high-ticket technical endurance equipment.",
            "key_message": "Endurance comfort that keeps your feet fresh mile after mile.",
            "evidence": [
                "Endurance Lab data highlights toe blisters as primary cause of trail race DNF"
            ],
            "estimated_reach": 50000,
            "competitor_contrast": "Zero-drop geometry eliminates Achilles strain during steep alpine climbs.",
        },
        {
            "title": "Student Trail Starter Edition",
            "positioning": "Budget-friendly, highly durable off-road running shoe for university athletics.",
            "target_insight": "Student demographic seeks accessible entry-level outdoor running equipment.",
            "key_message": "Premium trail grip without the premium price tag.",
            "evidence": ["Campus outdoor clubs report demand for sub-$120 trail footwear"],
            "estimated_reach": 48000,
            "competitor_contrast": "Reinforced toe cap provides 2x durability compared to generic running sneakers.",
        },
    ],
    "reusable-lunch-box": [
        {
            "title": "Executive Bento Workday Edition",
            "positioning": "Slim stainless steel multi-tier lunch box designed for corporate briefcases and backpacks.",
            "target_insight": "SQL queries show young professionals spend consistently on meal prep and storage items.",
            "key_message": "Upgrade your lunch hour with leak-proof culinary elegance.",
            "evidence": ["Reviews show plastic containers stain and absorb strong food odors"],
            "estimated_reach": 54000,
            "competitor_contrast": "Food-grade 304 steel never retains food odors and cleans effortlessly in dishwashers.",
        },
        {
            "title": "Zero-Waste Family Meal Prep System",
            "positioning": "Modular, stackable bento containers that eliminate single-use plastic wrap and baggies.",
            "target_insight": "Eco-conscious families generate the highest average purchase count across storage products.",
            "key_message": "Healthier lunches for your kids and a cleaner planet for their future.",
            "evidence": [
                "Studies indicate families cut plastic waste by 85% with stainless bento systems"
            ],
            "estimated_reach": 42000,
            "competitor_contrast": "Silicone gasket seals soup and sauces without microplastic contamination.",
        },
        {
            "title": "Campus Commuter Dorm Bento",
            "positioning": "Compact, impact-resistant lunch storage built for dorm fridges and campus bags.",
            "target_insight": "Students value dishwasher-safe, shatterproof lunch containers with customizable dividers.",
            "key_message": "Eat healthy on a student budget anywhere on campus.",
            "evidence": [
                "Student surveys highlight durable bento boxes save up to $150/month in food costs"
            ],
            "estimated_reach": 48000,
            "competitor_contrast": "Removable dividers adapt instantly for salads, warm entrees, or afternoon snacks.",
        },
        {
            "title": "Active Athlete Macro-Nutrition Kit",
            "positioning": "Portion-controlled precision containers for fitness enthusiasts tracking nutrition.",
            "target_insight": "Fitness enthusiasts have highest average purchase amount in health and storage categories.",
            "key_message": "Fuel your gains with perfectly measured pre-workout nutrition.",
            "evidence": [
                "Fitness influencers cite portion control bento containers as key to diet compliance"
            ],
            "estimated_reach": 60000,
            "competitor_contrast": "Laser-etched volume indicators make macro tracking effortless without a scale.",
        },
        {
            "title": "Eco-Minimalist Outdoor Travel Box",
            "positioning": "Rugged stainless camp-and-work lunch box with heavy-duty locking clasps.",
            "target_insight": "Cross-category customers in West region favor multi-purpose outdoor lifestyle gear.",
            "key_message": "From office desk to backcountry trail without skipping a meal.",
            "evidence": [
                "Outdoor reviewers rate stainless steel clips superior to brittle plastic latches"
            ],
            "estimated_reach": 45000,
            "competitor_contrast": "Stove-safe bottom allows direct reheating over camping stoves or warm water baths.",
        },
    ],
}

SCRIPTED_PACKAGES = {
    "smart-water-bottle": {
        "angle_title": "Smart Hydration for Busy Professionals",
        "google_ads": {
            "headlines": [
                "Brightside Smart Bottle",
                "Hydrate on Busy Days",
                "Chilled for 24 Hours",
            ],
            "descriptions": [
                "Track daily hydration with smart glow reminders. Stainless steel vacuum insulation.",
                "Sleek desk-friendly design with whisper-quiet notifications. Shop Brightside Goods.",
            ],
        },
        "instagram": {
            "caption": "Workdays get busy, but staying hydrated should be effortless. The Brightside Smart Bottle reminds you when it's time to drink, keeping your water chilled for 24 hours without plastic. #hydrate #productivity #wellness #brightside #workday",
            "hashtags": ["#hydrate", "#productivity", "#wellness", "#brightside", "#workday"],
            "image_idea": "Minimalist desk with laptop, notebook, and the matte black Smart Bottle glowing softly.",
        },
        "email": {
            "subject": "Meet your workday hydration partner",
            "preheader": "Stay energized and focused all day long",
            "body": "Hi there,\n\nBetween meetings and deadlines, it is easy to forget the simplest habit: drinking water.\n\nThe Brightside Smart Bottle makes hydration automatic with gentle reminders and double-wall vacuum insulation that keeps water ice-cold for 24 hours.\n\nCrafted from food-grade stainless steel with zero plastic parts, it is built to elevate your daily routine.\n\nStay energized all day.\n\nThe Brightside Team",
            "cta": "Shop the Smart Bottle",
        },
    },
    "trail-running-shoes": {
        "angle_title": "Alpine Grip Rock Plate Defender",
        "google_ads": {
            "headlines": [
                "TerraGrip Trail Shoes",
                "Rugged Alpine Traction",
                "Conquer Tough Terrain",
            ],
            "descriptions": [
                "Vibram Megagrip soles with rock plate defense. Designed for tough mountain ascents.",
                "Breathable mesh uppers and zero-blister heel lock. Explore Brightside trail footwear.",
            ],
        },
        "instagram": {
            "caption": "Mud, rocks, or steep scree—take on every mountain trail with relentless grip. The TerraGrip Pro features rock plate protection and high-traction lugs to keep you moving forward. #trailrunning #outdoors #mountainlife #runninggear #brightside",
            "hashtags": [
                "#trailrunning",
                "#outdoors",
                "#mountainlife",
                "#runninggear",
                "#brightside",
            ],
            "image_idea": "A trail runner mid-stride on a misty mountain ridgeline, dirt kicking up under rugged lugs.",
        },
        "email": {
            "subject": "Ready for the trails less traveled?",
            "preheader": "Tackle rugged terrain with zero slippage",
            "body": "Hello Runner,\n\nWhen you step onto the trail, traction is everything.\n\nThe TerraGrip Pro is engineered for unpredictable alpine terrain. With heavy-duty Vibram Megagrip lugs and a rock plate shield, you get confident footing on wet granite, loose gravel, and muddy ascents.\n\nExperience responsive trail cushioning that protects your feet over any distance.\n\nSee you on the trail.\n\nThe Brightside Team",
            "cta": "Explore Trail Shoes",
        },
    },
    "reusable-lunch-box": {
        "angle_title": "Executive Bento Workday Edition",
        "google_ads": {
            "headlines": [
                "Brightside Bento Box",
                "Leak-Proof Work Lunches",
                "Stainless Steel Lunch",
            ],
            "descriptions": [
                "Food-grade 304 steel lunch box with modular dividers. 100% leak-proof silicone seal.",
                "Say goodbye to single-use plastics and stained tupperware. Shop Brightside Goods.",
            ],
        },
        "instagram": {
            "caption": "Ditch soggy takeout and stained plastic containers. The Brightside EcoBento keeps salads crisp, entrees warm, and backpacks completely leak-free. #mealprep #zerowaste #bentobox #healthylunch #brightside",
            "hashtags": ["#mealprep", "#zerowaste", "#bentobox", "#healthylunch", "#brightside"],
            "image_idea": "Open stainless bento box filled with fresh avocado salad, quinoa, and fruit on a wooden table.",
        },
        "email": {
            "subject": "Upgrade your lunch hour sustainably",
            "preheader": "Leak-proof bento dining made effortless",
            "body": "Hi there,\n\nWhy settle for takeout when you can enjoy home-prepared meals in style?\n\nThe Brightside EcoBento Box brings culinary elegance to your workday. Crafted from durable food-grade 304 stainless steel with leak-proof silicone dividers, your meals stay fresh, crisp, and separated until you are ready to eat.\n\nZero waste, zero microplastics, 100% dishwasher safe.\n\nEnjoy lunch again.\n\nThe Brightside Team",
            "cta": "Shop EcoBento",
        },
    },
}


class ScriptedChatModel(BaseChatModel):
    """Deterministic demo chat model simulating full LLM tool loops without an external API.

    Docstring:
        This is a deterministic demo model for testing and offline demonstrations, NOT an LLM.
    """

    model_name: str = "scripted-demo"

    def bind_tools(self, tools: Any, **kwargs: Any) -> ScriptedChatModel:
        return self

    @property
    def _llm_type(self) -> str:
        return "scripted-demo"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        full_text = " ".join(str(m.content) for m in messages)
        product_key = _get_demo_product_key(full_text)
        is_phase2 = "<approved_angle>" in full_text or "draft_copy" in full_text

        tool_messages = [m for m in messages if getattr(m, "type", "") == "tool"]
        tool_count = len(tool_messages)

        if not is_phase2:
            # Phase 1 tool loop
            if tool_count == 0:
                # Turn 1: web_search
                q = product_key.replace("-", " ")
                msg = AIMessage(
                    content="",
                    tool_calls=[{"name": "web_search", "args": {"query": q}, "id": "call_search"}],
                    usage_metadata=USAGE,
                )
            elif tool_count == 1:
                # Turn 2: sql_query
                sql = "SELECT age_band, AVG(lifetime_value) AS avg_ltv FROM customers GROUP BY age_band LIMIT 50"
                msg = AIMessage(
                    content="",
                    tool_calls=[{"name": "sql_query", "args": {"query": sql}, "id": "call_sql"}],
                    usage_metadata=USAGE,
                )
            elif tool_count == 2:
                # Turn 3: analytics_lookup
                msg = AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "analytics_lookup",
                            "args": {
                                "segment": "fitness-enthusiasts",
                                "channel": "instagram",
                                "budget_usd": 5000.0,
                            },
                            "id": "call_analytics",
                        }
                    ],
                    usage_metadata=USAGE,
                )
            else:
                # Turn 4: return final 5 angles
                angles = SCRIPTED_ANGLES[product_key]
                msg = AIMessage(
                    content=json.dumps({"angles": angles}, indent=2),
                    usage_metadata=USAGE,
                )
        else:
            # Phase 2 tool loop
            pkg_data = SCRIPTED_PACKAGES[product_key]
            if tool_count == 0:
                # Call draft_copy for Google Ads
                msg = AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "draft_copy",
                            "args": {
                                "channel": "google_ads",
                                "fields": pkg_data["google_ads"],
                            },
                            "id": "call_draft_gads",
                        }
                    ],
                    usage_metadata=USAGE,
                )
            elif tool_count == 1:
                # Call draft_copy for Instagram
                msg = AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "draft_copy",
                            "args": {
                                "channel": "instagram",
                                "fields": pkg_data["instagram"],
                            },
                            "id": "call_draft_insta",
                        }
                    ],
                    usage_metadata=USAGE,
                )
            elif tool_count == 2:
                # Call draft_copy for Email
                msg = AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "draft_copy",
                            "args": {
                                "channel": "email",
                                "fields": pkg_data["email"],
                            },
                            "id": "call_draft_email",
                        }
                    ],
                    usage_metadata=USAGE,
                )
            else:
                # Return final CampaignPackage
                # Extract approved angle title if present
                title_match = re.search(r"Title:\s*(.+)", full_text)
                title = title_match.group(1).strip() if title_match else pkg_data["angle_title"]
                full_pkg = {
                    "angle_title": title,
                    "google_ads": pkg_data["google_ads"],
                    "instagram": pkg_data["instagram"],
                    "email": pkg_data["email"],
                }
                msg = AIMessage(
                    content=json.dumps(full_pkg, indent=2),
                    usage_metadata=USAGE,
                )

        generation = ChatGeneration(message=msg)
        return ChatResult(generations=[generation])

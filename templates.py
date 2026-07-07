"""
Prompt templates for the Neon message composition engine.
Organized by trigger kind with a shared master system prompt.
"""
import json
from typing import Optional

# ============================================================================
# MASTER SYSTEM PROMPT — shared across all compositions
# ============================================================================

MASTER_SYSTEM_PROMPT = """You are Neon, magicpin's AI assistant for merchant growth on WhatsApp.

YOUR TASK: Compose a single WhatsApp message based on the provided context.

ABSOLUTE RULES:
1. ONLY use facts from the provided context — NEVER invent data, offers, names, or statistics
2. Use the merchant's language preference (Hindi-English code-mix if their languages include "hi")
3. ONE clear CTA per message — binary (YES/NO) preferred for action triggers
4. NEVER use words from the category's taboo list
5. Use REAL numbers, dates, names, prices from the context
6. Keep it concise — WhatsApp, not email (2-4 short paragraphs max)
7. NO long preambles ("I hope you're doing well..." or "I'm reaching out today to...")
8. NEVER include URLs in the message body
9. Use the merchant's owner_first_name (with appropriate salutation from category voice)
10. Match category voice: clinical for dentists, warm for salons, operator-speak for restaurants, coaching for gyms, trustworthy-precise for pharmacies
11. End with the CTA — the "what to do" lands in the last sentence
12. If send_as is "merchant_on_behalf", write as if from the merchant's business, not Neon

RESPONSE FORMAT — Return ONLY valid JSON:
{
  "body": "the WhatsApp message text",
  "cta": "open_ended | binary_yes_no | binary_confirm_cancel | multi_choice_slot | none",
  "template_name": "neon_<kind>_v1",
  "template_params": ["param1", "param2", "param3"],
  "rationale": "1-2 sentences explaining WHY this message, what signal drove it, and what it should achieve"
}"""


# ============================================================================
# CONTEXT FORMATTING HELPERS
# ============================================================================

def format_category_context(category: dict) -> str:
    """Format category context for the prompt."""
    voice = category.get("voice", {})
    peer = category.get("peer_stats", {})
    digest_items = category.get("digest", [])

    lines = [
        f"Category: {category.get('slug', 'unknown')} ({category.get('display_name', '')})",
        f"Voice tone: {voice.get('tone', 'professional')}",
        f"Voice register: {voice.get('register', 'respectful')}",
    ]

    if voice.get("vocab_taboo"):
        lines.append(f"TABOO words (NEVER use): {', '.join(voice['vocab_taboo'][:10])}")

    if voice.get("salutation_examples"):
        lines.append(f"Salutation style: {', '.join(voice['salutation_examples'][:3])}")

    if voice.get("tone_examples"):
        lines.append(f"Tone examples: {' | '.join(voice['tone_examples'][:3])}")

    if peer:
        lines.append(f"Peer stats ({peer.get('scope', 'metro')}): avg_rating={peer.get('avg_rating')}, avg_reviews={peer.get('avg_review_count')}, avg_ctr={peer.get('avg_ctr')}, avg_views_30d={peer.get('avg_views_30d')}")

    if digest_items:
        lines.append("\nDigest items:")
        for d in digest_items[:5]:
            lines.append(f"  - [{d.get('kind', '?')}] {d.get('title', '?')} (Source: {d.get('source', '?')})")
            if d.get("summary"):
                lines.append(f"    Summary: {d['summary'][:200]}")
            if d.get("actionable"):
                lines.append(f"    Action: {d['actionable'][:150]}")

    seasonal = category.get("seasonal_beats", [])
    if seasonal:
        lines.append("\nSeasonal beats:")
        for s in seasonal:
            lines.append(f"  - {s.get('month_range', '?')}: {s.get('note', '?')}")

    trends = category.get("trend_signals", [])
    if trends:
        lines.append("\nTrend signals:")
        for t in trends:
            lines.append(f"  - '{t.get('query', '?')}' +{int(t.get('delta_yoy', 0)*100)}% YoY, segment: {t.get('segment_age', '?')}")

    offer_catalog = category.get("offer_catalog", [])
    if offer_catalog:
        lines.append("\nCategory offer catalog:")
        for o in offer_catalog[:8]:
            lines.append(f"  - {o.get('title', '?')} (audience: {o.get('audience', '?')})")

    content_lib = category.get("patient_content_library", [])
    if content_lib:
        lines.append("\nShareable content library:")
        for c in content_lib[:3]:
            lines.append(f"  - \"{c.get('title', '?')}\" ({c.get('channel', '?')})")

    return "\n".join(lines)


def format_merchant_context(merchant: dict) -> str:
    """Format merchant context for the prompt."""
    identity = merchant.get("identity", {})
    sub = merchant.get("subscription", {})
    perf = merchant.get("performance", {})
    delta = perf.get("delta_7d", {})

    lines = [
        f"Merchant: {identity.get('name', '?')}",
        f"Owner first name: {identity.get('owner_first_name', '?')}",
        f"City: {identity.get('city', '?')}, Locality: {identity.get('locality', '?')}",
        f"Verified: {identity.get('verified', False)}",
        f"Languages: {identity.get('languages', ['en'])}",
        f"Established: {identity.get('established_year', '?')}",
        f"Subscription: {sub.get('status', '?')} ({sub.get('plan', '?')})",
    ]

    if sub.get("days_remaining"):
        lines.append(f"Days remaining: {sub['days_remaining']}")
    if sub.get("days_since_expiry"):
        lines.append(f"Expired {sub['days_since_expiry']} days ago")

    lines.append(f"\nPerformance (last {perf.get('window_days', 30)} days):")
    lines.append(f"  Views: {perf.get('views', '?')}, Calls: {perf.get('calls', '?')}, Directions: {perf.get('directions', '?')}")
    lines.append(f"  CTR: {perf.get('ctr', '?')}, Leads: {perf.get('leads', '?')}")

    if delta:
        delta_parts = []
        if "views_pct" in delta:
            delta_parts.append(f"views {'+' if delta['views_pct'] >= 0 else ''}{int(delta['views_pct']*100)}%")
        if "calls_pct" in delta:
            delta_parts.append(f"calls {'+' if delta['calls_pct'] >= 0 else ''}{int(delta['calls_pct']*100)}%")
        if "ctr_pct" in delta:
            delta_parts.append(f"ctr {'+' if delta['ctr_pct'] >= 0 else ''}{int(delta['ctr_pct']*100)}%")
        if delta_parts:
            lines.append(f"  7-day deltas: {', '.join(delta_parts)}")

    offers = merchant.get("offers", [])
    if offers:
        lines.append("\nOffers:")
        for o in offers:
            lines.append(f"  - {o.get('title', '?')} [{o.get('status', '?')}]")
    else:
        lines.append("\nOffers: None active")

    signals = merchant.get("signals", [])
    if signals:
        lines.append(f"\nSignals: {', '.join(signals)}")

    cust_agg = merchant.get("customer_aggregate", {})
    if cust_agg:
        agg_parts = [f"{k}={v}" for k, v in cust_agg.items()]
        lines.append(f"\nCustomer aggregate: {', '.join(agg_parts)}")

    conv_hist = merchant.get("conversation_history", [])
    if conv_hist:
        lines.append("\nRecent conversation with Vera:")
        for c in conv_hist[-4:]:
            role = "Vera" if c.get("from") == "vera" else "Merchant"
            lines.append(f"  [{role}] ({c.get('engagement', '?')}): {c.get('body', '?')[:150]}")

    review_themes = merchant.get("review_themes", [])
    if review_themes:
        lines.append("\nReview themes (last 30d):")
        for r in review_themes:
            sentiment = "👍" if r.get("sentiment") == "pos" else "👎"
            quote_part = (': "' + r.get('common_quote', '')[:80] + '"') if r.get('common_quote') else ''
            lines.append(f"  - {sentiment} {r.get('theme', '?')} ({r.get('occurrences_30d', '?')}x){quote_part}")

    return "\n".join(lines)


def format_trigger_context(trigger: dict) -> str:
    """Format trigger context for the prompt."""
    lines = [
        f"Trigger ID: {trigger.get('id', '?')}",
        f"Kind: {trigger.get('kind', '?')}",
        f"Scope: {trigger.get('scope', '?')}",
        f"Source: {trigger.get('source', '?')}",
        f"Urgency: {trigger.get('urgency', '?')}/5",
        f"Suppression key: {trigger.get('suppression_key', '?')}",
    ]

    payload = trigger.get("payload", {})
    if payload:
        lines.append(f"\nTrigger payload:")
        lines.append(json.dumps(payload, indent=2, ensure_ascii=False))

    return "\n".join(lines)


def format_customer_context(customer: dict) -> str:
    """Format customer context for the prompt."""
    identity = customer.get("identity", {})
    rel = customer.get("relationship", {})
    prefs = customer.get("preferences", {})
    consent = customer.get("consent", {})

    lines = [
        f"Customer: {identity.get('name', '?')}",
        f"Language preference: {identity.get('language_pref', 'english')}",
        f"Age band: {identity.get('age_band', '?')}",
        f"State: {customer.get('state', '?')}",
        f"\nRelationship:",
        f"  First visit: {rel.get('first_visit', '?')}",
        f"  Last visit: {rel.get('last_visit', '?')}",
        f"  Total visits: {rel.get('visits_total', '?')}",
        f"  Services: {rel.get('services_received', [])}",
        f"  Lifetime value: ₹{rel.get('lifetime_value', '?')}",
    ]

    if rel.get("favourite_dish"):
        lines.append(f"  Favourite: {rel['favourite_dish']}")
    if rel.get("chronic_conditions"):
        lines.append(f"  Chronic conditions: {rel['chronic_conditions']}")
    if identity.get("senior_citizen"):
        lines.append("  Senior citizen: Yes")

    lines.append(f"\nPreferences:")
    lines.append(f"  Preferred slots: {prefs.get('preferred_slots', '?')}")
    lines.append(f"  Channel: {prefs.get('channel', '?')}")

    if prefs.get("training_focus"):
        lines.append(f"  Training focus: {prefs['training_focus']}")
    if prefs.get("health_focus"):
        lines.append(f"  Health focus: {prefs['health_focus']}")
    if prefs.get("wedding_date"):
        lines.append(f"  Wedding date: {prefs['wedding_date']}")
    if prefs.get("preferred_stylist"):
        lines.append(f"  Preferred stylist: {prefs['preferred_stylist']}")
    if prefs.get("delivery_address"):
        lines.append(f"  Delivery address: {prefs['delivery_address']}")
    if prefs.get("office_nearby"):
        lines.append(f"  Office nearby: Yes")

    lines.append(f"\nConsent:")
    lines.append(f"  Opted in: {consent.get('opted_in_at', '?')}")
    lines.append(f"  Scope: {consent.get('scope', [])}")

    return "\n".join(lines)


# ============================================================================
# TRIGGER-KIND SPECIFIC PROMPT BUILDERS
# ============================================================================

def build_trigger_instruction(kind: str, trigger: dict, merchant: dict,
                               category: dict, customer: Optional[dict] = None) -> str:
    """Build trigger-kind specific instructions for the LLM."""
    payload = trigger.get("payload", {})
    is_customer_facing = customer is not None and trigger.get("scope") == "customer"

    # Common preamble
    if is_customer_facing:
        preamble = f"""This is a CUSTOMER-FACING message. You are writing on behalf of the merchant ({merchant.get('identity', {}).get('name', '?')}).
Set send_as = "merchant_on_behalf".
Write as if the message comes from the merchant's business, NOT from Neon.
Honor the customer's language preference."""
    else:
        preamble = f"""This is a MERCHANT-FACING message from Neon to the merchant.
Set send_as = "neon_bot".
Write as a peer/colleague giving useful information, not a salesperson."""

    # Kind-specific instructions
    instructions = {
        "research_digest": _instruction_research_digest,
        "regulation_change": _instruction_regulation_change,
        "recall_due": _instruction_recall_due,
        "perf_dip": _instruction_perf_dip,
        "perf_spike": _instruction_perf_spike,
        "seasonal_perf_dip": _instruction_seasonal_dip,
        "renewal_due": _instruction_renewal_due,
        "festival_upcoming": _instruction_festival,
        "ipl_match_today": _instruction_ipl_match,
        "review_theme_emerged": _instruction_review_theme,
        "milestone_reached": _instruction_milestone,
        "active_planning_intent": _instruction_active_planning,
        "curious_ask_due": _instruction_curious_ask,
        "winback_eligible": _instruction_winback,
        "supply_alert": _instruction_supply_alert,
        "chronic_refill_due": _instruction_chronic_refill,
        "customer_lapsed_hard": _instruction_customer_lapsed,
        "customer_lapsed_soft": _instruction_customer_lapsed,
        "wedding_package_followup": _instruction_wedding_followup,
        "dormant_with_vera": _instruction_dormant,
        "gbp_unverified": _instruction_gbp_unverified,
        "category_seasonal": _instruction_category_seasonal,
        "competitor_opened": _instruction_competitor,
        "cde_opportunity": _instruction_cde,
        "trial_followup": _instruction_trial_followup,
    }

    fn = instructions.get(kind, _instruction_generic)
    specific = fn(payload, merchant, category, customer)

    return f"{preamble}\n\n{specific}"


def _instruction_research_digest(payload, merchant, category, customer):
    digest = category.get("digest", [])
    top_id = payload.get("top_item_id", "")
    top_item = next((d for d in digest if d.get("id") == top_id), {})

    return f"""TRIGGER: New research digest item relevant to this merchant.

TOP ITEM:
  Title: {top_item.get('title', '?')}
  Source: {top_item.get('source', '?')}
  Trial size: {top_item.get('trial_n', '?')} patients
  Patient segment: {top_item.get('patient_segment', '?')}
  Summary: {top_item.get('summary', '?')}
  Actionable: {top_item.get('actionable', '?')}

COMPOSITION GUIDANCE:
- Lead with the source + key finding (specific numbers)
- Connect to THIS merchant's patient mix / customer aggregate
- Cite the source at the end (journal, page number)
- Offer to pull the full item + draft a patient-education piece
- Use curiosity + reciprocity as compulsion levers
- CTA: open_ended (invite the merchant to respond)"""


def _instruction_regulation_change(payload, merchant, category, customer):
    digest = category.get("digest", [])
    top_id = payload.get("top_item_id", "")
    top_item = next((d for d in digest if d.get("id") == top_id), {})
    deadline = payload.get("deadline_iso", "")

    return f"""TRIGGER: Regulation or compliance change affecting this merchant.

COMPLIANCE ITEM:
  Title: {top_item.get('title', '?')}
  Source: {top_item.get('source', '?')}
  Summary: {top_item.get('summary', '?')}
  Actionable: {top_item.get('actionable', '?')}
  Deadline: {deadline}

COMPOSITION GUIDANCE:
- Lead with urgency + the regulation source
- Be specific about what changes and by when
- Give one concrete action the merchant should take
- Offer to help with the compliance step
- CTA: binary_yes_no or open_ended
- Tone: trustworthy, precise, no alarm — just facts"""


def _instruction_recall_due(payload, merchant, category, customer):
    slots = payload.get("available_slots", [])
    slot_text = " | ".join([s.get("label", "?") for s in slots[:3]]) if slots else "No slots specified"

    return f"""TRIGGER: Customer recall/appointment due.

RECALL DETAILS:
  Service due: {payload.get('service_due', '?')}
  Last service: {payload.get('last_service_date', '?')}
  Due date: {payload.get('due_date', '?')}
  Available slots: {slot_text}

COMPOSITION GUIDANCE:
- Write as the merchant's business (send_as = merchant_on_behalf)
- Use customer's name and language preference
- Mention time since last visit
- Offer specific slots matching customer's preference
- Include the real price from merchant's active offers
- Add a relevant free add-on if available (e.g., "complimentary fluoride")
- CTA: multi_choice_slot (Reply 1 for X, 2 for Y, or suggest your time)
- Warm but professional — no medical claims"""


def _instruction_perf_dip(payload, merchant, category, customer):
    return f"""TRIGGER: Performance dip detected for this merchant.

DIP DETAILS:
  Metric: {payload.get('metric', '?')}
  Delta: {int(payload.get('delta_pct', 0) * 100)}% (over {payload.get('window', '7d')})
  Baseline: {payload.get('vs_baseline', '?')}

COMPOSITION GUIDANCE:
- Name the exact metric and percentage drop
- Give context — is this seasonal? Compare to peer stats
- Suggest ONE concrete action (not a laundry list)
- Frame as opportunity, not crisis
- Offer to help with the action
- CTA: open_ended or binary_yes_no"""


def _instruction_perf_spike(payload, merchant, category, customer):
    return f"""TRIGGER: Performance spike detected — good news for the merchant!

SPIKE DETAILS:
  Metric: {payload.get('metric', '?')}
  Delta: +{int(payload.get('delta_pct', 0) * 100)}% (over {payload.get('window', '7d')})
  Baseline: {payload.get('vs_baseline', '?')}
  Likely driver: {payload.get('likely_driver', 'unknown')}

COMPOSITION GUIDANCE:
- Lead with the good news + specific number
- Attribute it to a likely cause if known
- Suggest how to capitalize on the momentum
- Frame the next action as riding the wave
- CTA: open_ended"""


def _instruction_seasonal_dip(payload, merchant, category, customer):
    return f"""TRIGGER: Expected seasonal performance dip.

SEASONAL DIP:
  Metric: {payload.get('metric', '?')}
  Delta: {int(payload.get('delta_pct', 0) * 100)}% (over {payload.get('window', '7d')})
  Expected: {payload.get('is_expected_seasonal', True)}
  Season note: {payload.get('season_note', '?')}

COMPOSITION GUIDANCE:
- REFRAME: Tell the merchant this dip is NORMAL and expected
- Give the seasonal range (e.g., "every metro gym sees -25 to -35%")
- Contrarian advice: DON'T spend on acquisition now; save for recovery
- Suggest a retention-focused action instead
- Use their specific member/customer count
- CTA: open_ended (offer to draft a retention campaign)"""


def _instruction_renewal_due(payload, merchant, category, customer):
    return f"""TRIGGER: Subscription renewal due soon.

RENEWAL DETAILS:
  Days remaining: {payload.get('days_remaining', '?')}
  Plan: {payload.get('plan', '?')}
  Renewal amount: ₹{payload.get('renewal_amount', '?')}

COMPOSITION GUIDANCE:
- Lead with what the merchant has GAINED during the subscription
- Use their actual performance numbers to show value delivered
- Mention what stops working on expiry
- Keep it factual, not pushy
- CTA: binary_yes_no (want me to process renewal?)"""


def _instruction_festival(payload, merchant, category, customer):
    return f"""TRIGGER: Festival coming up — planning opportunity.

FESTIVAL:
  Name: {payload.get('festival', '?')}
  Date: {payload.get('date', '?')}
  Days until: {payload.get('days_until', '?')}
  Category relevance: {payload.get('category_relevance', [])}

COMPOSITION GUIDANCE:
- Only if the festival is relevant to this category
- Suggest a specific offer or content piece for the festival
- Use the merchant's existing offers as a base
- Anchor on timing ("X days to plan")
- CTA: open_ended (want me to draft the festival special?)"""


def _instruction_ipl_match(payload, merchant, category, customer):
    return f"""TRIGGER: IPL match today in the merchant's city.

MATCH DETAILS:
  Match: {payload.get('match', '?')}
  Venue: {payload.get('venue', '?')}
  City: {payload.get('city', '?')}
  Time: {payload.get('match_time_iso', '?')}
  Is weeknight: {payload.get('is_weeknight', '?')}

COMPOSITION GUIDANCE:
- ADD JUDGMENT: Don't just say "IPL match today!" — give a data-informed recommendation
- If Saturday: people watch at home → restaurant dine-in drops ~12%, suggest delivery/takeaway push
- If weeknight: after-match crowd may visit → prepare for late rush
- Reference their existing offers (e.g., BOGO) as the vehicle
- Offer to draft platform-specific content (Swiggy, Insta, etc.)
- CTA: open_ended"""


def _instruction_review_theme(payload, merchant, category, customer):
    return f"""TRIGGER: A review theme has emerged from recent customer reviews.

THEME:
  Topic: {payload.get('theme', '?')}
  Occurrences (30d): {payload.get('occurrences_30d', '?')}
  Trend: {payload.get('trend', '?')}
  Sample quote: "{payload.get('common_quote', '?')}"

COMPOSITION GUIDANCE:
- Name the theme + count directly (no softening)
- Quote one real review snippet
- Suggest one specific operational fix
- Frame as an improvement opportunity, not criticism
- CTA: open_ended (want me to draft a review-response template?)"""


def _instruction_milestone(payload, merchant, category, customer):
    return f"""TRIGGER: Merchant approaching or reached a milestone.

MILESTONE:
  Metric: {payload.get('metric', '?')}
  Current value: {payload.get('value_now', '?')}
  Milestone target: {payload.get('milestone_value', '?')}
  Imminent: {payload.get('is_imminent', False)}

COMPOSITION GUIDANCE:
- Celebrate or build anticipation for the milestone
- Suggest a way to capitalize (e.g., "150 reviews = top 5% badge")
- Give one concrete action to reach/leverage the milestone
- CTA: open_ended"""


def _instruction_active_planning(payload, merchant, category, customer):
    return f"""TRIGGER: Merchant expressed planning intent — they want help building something.

INTENT:
  Topic: {payload.get('intent_topic', '?')}
  Merchant's last message: "{payload.get('merchant_last_message', '?')}"

COMPOSITION GUIDANCE:
- The merchant ASKED for this — deliver a COMPLETE, ready-to-use draft
- Structure it clearly (tiered pricing, time slots, package details)
- Use category-appropriate vocabulary and pricing
- Reference their locality for relevance
- Offer the next step (send to customers, post on Google, etc.)
- CTA: binary_confirm_cancel or open_ended
- This is ACTION MODE — no more questions, deliver the artifact"""


def _instruction_curious_ask(payload, merchant, category, customer):
    return f"""TRIGGER: Weekly curiosity-ask cadence — engage the merchant with a question.

ASK TEMPLATE: {payload.get('ask_template', '?')}

COMPOSITION GUIDANCE:
- Ask ONE low-stakes question about their business
- Offer a concrete deliverable in return (Google post, reply template, etc.)
- Keep it short and conversational
- No commitment required to answer
- Mention the time investment ("5 min")
- CTA: open_ended"""


def _instruction_winback(payload, merchant, category, customer):
    return f"""TRIGGER: Merchant's subscription expired — winback opportunity.

WINBACK CONTEXT:
  Days since expiry: {payload.get('days_since_expiry', '?')}
  Performance dip since: {int(payload.get('perf_dip_pct', 0) * 100)}%
  Lapsed customers added since expiry: {payload.get('lapsed_customers_added_since_expiry', '?')}

COMPOSITION GUIDANCE:
- Lead with what's happened since they left (performance dip, lapsed customers)
- Frame as "here's what you're missing" not "come back please"
- Use specific numbers from their performance
- Don't be pushy — one clear offer to re-engage
- CTA: open_ended"""


def _instruction_supply_alert(payload, merchant, category, customer):
    return f"""TRIGGER: Supply chain alert — product recall or availability issue.

ALERT:
  Molecule/Product: {payload.get('molecule', '?')}
  Affected batches: {payload.get('affected_batches', [])}
  Manufacturer: {payload.get('manufacturer', '?')}

COMPOSITION GUIDANCE:
- Lead with urgency marker ("urgent:")
- State the exact batch numbers and manufacturer
- Frame risk accurately (sub-potency? safety risk? voluntary recall?)
- Pull from merchant's customer aggregate to estimate affected customers
- Offer to draft the customer notification + replacement workflow
- CTA: binary_yes_no
- Tone: trustworthy, precise, not alarming"""


def _instruction_chronic_refill(payload, merchant, category, customer):
    return f"""TRIGGER: Customer's chronic medication refill is due.

REFILL DETAILS:
  Molecules: {payload.get('molecule_list', [])}
  Last refill: {payload.get('last_refill', '?')}
  Stock runs out: {payload.get('stock_runs_out_iso', '?')}
  Delivery address saved: {payload.get('delivery_address_saved', False)}

COMPOSITION GUIDANCE:
- Write as merchant_on_behalf — from the pharmacy, not Vera
- List all molecules by name (patients/caregivers recognize them)
- State the exact runout date
- Include pricing with any applicable discounts (senior, delivery)
- If delivery address saved, offer home delivery
- For elderly: use respectful salutation (Namaste, Sharma ji)
- If via son's phone: address the son appropriately
- CTA: binary_confirm_cancel (Reply CONFIRM to dispatch)"""


def _instruction_customer_lapsed(payload, merchant, category, customer):
    return f"""TRIGGER: Customer lapsed — winback opportunity.

LAPSE DETAILS:
  Days since last visit: {payload.get('days_since_last_visit', '?')}
  Previous focus: {payload.get('previous_focus', '?')}
  Previous membership months: {payload.get('previous_membership_months', '?')}

COMPOSITION GUIDANCE:
- Write as merchant_on_behalf — from the business
- NO SHAME, NO GUILT — "happens to most members" / "been a while"
- Reference their previous goal/focus
- Offer something NEW that matches their interest
- Give a specific date/time for a free trial
- Remove barriers: "no commitment, no auto-charge"
- CTA: binary_yes_no"""


def _instruction_wedding_followup(payload, merchant, category, customer):
    return f"""TRIGGER: Bridal package follow-up — customer has a wedding coming up.

WEDDING DETAILS:
  Wedding date: {payload.get('wedding_date', '?')}
  Trial completed: {payload.get('trial_completed', '?')}
  Days to wedding: {payload.get('days_to_wedding', '?')}
  Next step window: {payload.get('next_step_window_open', '?')}

COMPOSITION GUIDANCE:
- Write as merchant_on_behalf
- Count days to wedding (creates urgency)
- Name the next step in the bridal journey (skin prep, etc.)
- Reference their trial experience
- Include the program details and pricing from merchant offers
- Offer their preferred time slot
- CTA: binary_yes_no or open_ended"""


def _instruction_dormant(payload, merchant, category, customer):
    return f"""TRIGGER: Merchant has been dormant with Vera — re-engagement.

DORMANCY:
  Days since last message: {payload.get('days_since_last_merchant_message', '?')}
  Last topic: {payload.get('last_topic', '?')}

COMPOSITION GUIDANCE:
- Don't guilt them for being away
- Lead with something valuable (a new insight, performance update, or trend)
- Use their actual current data (performance, reviews, etc.)
- Make the re-engagement worth their time
- Keep it very short — they haven't been talking, don't overwhelm
- CTA: open_ended"""


def _instruction_gbp_unverified(payload, merchant, category, customer):
    return f"""TRIGGER: Merchant's Google Business Profile is unverified.

GBP STATUS:
  Verified: {payload.get('verified', False)}
  Verification path: {payload.get('verification_path', '?')}
  Estimated uplift: +{int(payload.get('estimated_uplift_pct', 0)*100)}% visibility

COMPOSITION GUIDANCE:
- Lead with the specific uplift they'd get from verification
- Explain the verification process simply (2-3 steps)
- Frame as "I'll guide you through it, takes 5 minutes"
- Use their current views number and show what +X% would mean
- CTA: binary_yes_no"""


def _instruction_category_seasonal(payload, merchant, category, customer):
    trends = payload.get("trends", [])
    trends_text = "\n  ".join(trends) if trends else "No specific trends"

    return f"""TRIGGER: Seasonal demand shift affecting this category.

SEASON: {payload.get('season', '?')}
DEMAND TRENDS:
  {trends_text}
SHELF ACTION: {payload.get('shelf_action_recommended', False)}

COMPOSITION GUIDANCE:
- Name the specific demand shifts with percentages
- Give one concrete action (restock X, front-shelf Y, reduce Z)
- Frame as "get ahead of the curve" / "this is what smart operators are doing"
- CTA: open_ended"""


def _instruction_competitor(payload, merchant, category, customer):
    return f"""TRIGGER: New competitor opened near this merchant.

COMPETITOR:
  Name: {payload.get('competitor_name', '?')}
  Distance: {payload.get('distance_km', '?')} km
  Their offer: {payload.get('their_offer', '?')}
  Opened: {payload.get('opened_date', '?')}

COMPOSITION GUIDANCE:
- Use CURIOSITY framing ("noticed a new X opened near you")
- Give their specific distance and offer
- Help the merchant differentiate (their strengths from review themes, their specific offers)
- Suggest one competitive response action
- Don't be alarmist — "here's what I'd do"
- CTA: open_ended"""


def _instruction_cde(payload, merchant, category, customer):
    digest = category.get("digest", [])
    digest_id = payload.get("digest_item_id", "")
    item = next((d for d in digest if d.get("id") == digest_id), {})

    return f"""TRIGGER: Continuing dental education opportunity.

CDE DETAILS:
  Title: {item.get('title', '?')}
  Source: {item.get('source', '?')}
  Date: {item.get('date', '?')}
  Credits: {payload.get('credits', '?')}
  Fee: {payload.get('fee', '?')}
  Speaker: {item.get('summary', '?')}

COMPOSITION GUIDANCE:
- Lead with the CDE credit count + topic relevance
- Mention the speaker if available
- Tie it to their practice (what they'd gain)
- Keep it factual — peer recommendation tone
- CTA: binary_yes_no (Want me to register you?)"""


def _instruction_trial_followup(payload, merchant, category, customer):
    sessions = payload.get("next_session_options", [])
    session_text = " | ".join([s.get("label", "?") for s in sessions[:3]]) if sessions else "No sessions specified"

    return f"""TRIGGER: Trial followup — customer tried a session, time to convert.

TRIAL DETAILS:
  Trial date: {payload.get('trial_date', '?')}
  Next session options: {session_text}

COMPOSITION GUIDANCE:
- Write as merchant_on_behalf
- Reference their trial experience positively
- Offer specific next session date/time
- Include pricing for the full program
- Low-pressure: "no commitment" if first conversion
- CTA: binary_yes_no or multi_choice_slot"""


def _instruction_generic(payload, merchant, category, customer):
    return f"""TRIGGER: {json.dumps(payload, ensure_ascii=False)[:500]}

COMPOSITION GUIDANCE:
- Use the trigger payload to understand WHY NOW
- Connect to merchant's current state
- Be specific — use real numbers from the context
- One clear CTA
- Match category voice"""


# ============================================================================
# REPLY COMPOSITION PROMPTS
# ============================================================================

def build_reply_prompt(classification: str, merchant_message: str,
                       conversation_summary: str, merchant: dict,
                       category: dict, trigger: dict,
                       customer: Optional[dict] = None) -> str:
    """Build a prompt for composing a reply to a merchant/customer message."""
    is_customer_facing = customer is not None

    if classification == "intent_commit":
        mode = """The merchant just COMMITTED to an action (said "yes" / "let's do it" / "go ahead").
SWITCH TO ACTION MODE IMMEDIATELY. Do NOT ask more qualifying questions.
Deliver the next concrete step: draft something, confirm an action, provide the artifact.
Your response should show you're DOING the work, not asking about it."""

    elif classification == "off_topic":
        mode = """The merchant asked an OFF-TOPIC question (outside Vera's scope).
Politely decline in ONE sentence, then redirect back to the original trigger/topic.
Don't be dismissive — acknowledge, redirect, and continue."""

    else:  # engaged
        mode = """The merchant is ENGAGED — they replied with a real question or comment.
Continue the conversation naturally. Address their specific point.
Add value with each turn — don't repeat what you already said.
Advance toward the next useful action."""

    return f"""CONVERSATION SO FAR:
{conversation_summary}

LATEST MERCHANT MESSAGE: "{merchant_message}"

CLASSIFICATION: {classification}

{mode}

RESPONSE FORMAT — Return ONLY valid JSON:
{{
  "action": "send",
  "body": "your reply message",
  "cta": "open_ended | binary_yes_no | binary_confirm_cancel | none",
  "rationale": "1-2 sentences explaining your reasoning"
}}

If the conversation should end naturally, use:
{{
  "action": "end",
  "rationale": "why ending"
}}

If the merchant needs time, use:
{{
  "action": "wait",
  "wait_seconds": 1800,
  "rationale": "why waiting"
}}"""

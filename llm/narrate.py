"""
llm/narrate.py
Stage 4 LLM Plan Narration Layer.
Takes ONLY structured deterministic output from Stages 2-3 and generates human-readable recommendations.
Strictly grounded — not allowed to invent numbers, dates, or entities.
"""

import json
from typing import Dict, Any, List
from llm.client import generate_json_with_timeout

STAGE4_SYSTEM_PROMPT = """You are the narration layer of a supply-chain disruption assistant. You will
be given a fully computed, structured impact assessment (already traced
through the distributor's own data by deterministic code) — affected orders,
shortfall quantities, days-late estimates, customer tiers, and pre-computed
option costs (expedite/part-ship/reallocate/notify). You did NOT compute any
of these numbers and must not alter them.

Rules:
- You may only reference orders, customers, shipments, and figures that
  appear in the input JSON. Never introduce a number, date, or entity that
  isn't there.
- Every claim you make about impact must be traceable — attach the
  relevant order_id / shipment_id / sku next to the claim.
- Present options exactly as given, stated plainly with their real
  trade-offs (cost, speed, customer impact). Do not soften or omit any
  option's downside.
- Recommend ONE course of action per affected order, with a one-line reason
  tied to the input data (e.g. VIP tier + smallest delay wins).
- If the input indicates no orders are affected (affected_orders is empty or total_orders_affected is 0),
  your entire output must state that clearly with "no_impact": true — do not manufacture urgency or suggest action.
- You are producing a recommendation for a human operator. Never phrase
  anything as already executed ("I have contacted...", "Stock has been
  reallocated..."). Always future/conditional ("recommend reallocating...").
- Output ONLY valid JSON matching the schema below. No markdown fences.

Output schema:
{
  "headline": "<one sentence — impact or 'no impact' stated plainly>",
  "affected_orders": [
    {
      "order_id": "...",
      "customer_tier": "...",
      "urgency_score": 0-100,
      "shortfall_summary": "<plain language, cites shipment_id/sku>",
      "days_late_estimate": 0,
      "options": [
        {
          "action": "expedite|part_ship|reallocate|notify_customer",
          "tradeoff": "<plain language of cost/speed/risk>",
          "source_figures": {"...": "..."}
        }
      ],
      "recommended_option": "...",
      "recommendation_reason": "<short, tied to data>"
    }
  ],
  "no_impact": true | false
}
"""

def narrate_plan(impact_report: Dict[str, Any]) -> Dict[str, Any]:
    """
    Stage 4 Plan Narration:
    Passes Stage 2-3 deterministic impact report to Gemini LLM with strict grounding constraints.
    Falls back to deterministic narration formatting if Gemini API is unreachable or times out (>15s).
    """
    affected_orders = impact_report.get("affected_orders", [])
    total_affected = impact_report.get("total_orders_affected", len(affected_orders))

    # Explicit check for No Impact
    if total_affected == 0 or not affected_orders:
        return {
            "headline": "No pending customer orders affected by this disruption notice.",
            "affected_orders": [],
            "no_impact": True
        }

    # Prepare input payload for Gemini
    prompt = f"""
STAGE 2-3 DETERMINISTIC IMPACT ASSESSMENT INPUT:
{json.dumps(impact_report, indent=2)}
"""

    llm_output = generate_json_with_timeout(
        prompt=prompt,
        system_instruction=STAGE4_SYSTEM_PROMPT,
        timeout=15.0
    )

    if llm_output and "headline" in llm_output and "affected_orders" in llm_output:
        # Attach evidence and options from Stage 3 input so deterministic evidence is never dropped
        impact_by_ord = {o["order_id"]: o for o in affected_orders}
        for n_ord in llm_output.get("affected_orders", []):
            oid = n_ord.get("order_id")
            if oid in impact_by_ord:
                orig = impact_by_ord[oid]
                n_ord.setdefault("evidence", orig.get("evidence", {}))
                n_ord.setdefault("options", orig.get("options", []))
                n_ord.setdefault("recommended_option", orig.get("recommended_option"))
                n_ord.setdefault("recommendation_reason", orig.get("recommendation_reason"))
        return llm_output

    # -------------------------------------------------------------
    # Fallback Deterministic Narration (No LLM call / Timeout)
    # -------------------------------------------------------------
    headline = f"Disruption impacts {total_affected} pending customer order(s) totaling ${impact_report.get('total_at_risk_value', 0.0):,.2f} at risk."
    
    narrated_orders = []
    for ord_item in affected_orders:
        shortfall_summary = (
            f"Order {ord_item['order_id']} for {ord_item['customer_name']} ({ord_item['customer_tier']}) "
            f"has a shortfall of {ord_item['shortfall_qty']} units of {ord_item['sku_name']} ({ord_item['sku']}), "
            f"delayed by {ord_item['days_late']} days due to supplier/shipment {ord_item.get('source_shipment_id') or ord_item.get('source_supplier_id')}."
        )

        narrated_orders.append({
            "order_id": ord_item["order_id"],
            "customer_tier": ord_item["customer_tier"],
            "urgency_score": ord_item.get("urgency_score", 50.0),
            "shortfall_summary": shortfall_summary,
            "days_late_estimate": ord_item["days_late"],
            "options": ord_item.get("options", []),
            "recommended_option": ord_item.get("recommended_option", "notify_customer"),
            "recommendation_reason": ord_item.get("recommendation_reason", "Deterministic recommendation based on customer tier and stock math."),
            "evidence": ord_item.get("evidence", {})
        })

    return {
        "headline": headline,
        "affected_orders": narrated_orders,
        "no_impact": False,
        "is_fallback": True
    }

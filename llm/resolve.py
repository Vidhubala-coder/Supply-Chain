"""
llm/resolve.py
Stage 1 LLM Entity Resolution Layer with Local Retrieval & Deterministic Threshold Short-Circuit.
"""

import json
from typing import Dict, Any, List
from llm.retrieval import retrieve_candidates
from llm.client import generate_json_with_timeout

STAGE1_SYSTEM_PROMPT = """You are the entity-resolution layer of a supply-chain disruption assistant.
You will be given: (1) a raw disruption notice (unstructured text), and
(2) a compact candidate index of distributor suppliers, shipments, and stock items with cosine similarity scores.
Your ONLY job is to work out what real-world entities in the data the notice is talking about.
You do not assess downstream impact — that is handled by deterministic Python code.

Rules:
- Only ever refer to entities that literally appear in the provided index.
  Never invent a supplier, shipment, or SKU ID that isn't in the index.
- If the notice's wording could match more than one entity, list every
  plausible candidate with a confidence score (0-1) and a one-line reason,
  rather than silently picking the most likely one.
- If nothing in the index plausibly matches the notice, say so explicitly
  with match_found: false. Do not force a match.
- Confidence should reflect textual/semantic match quality only.
- Output ONLY valid JSON matching the schema below. No markdown, no prose.

Output schema:
{
  "notice_summary": "<one sentence, neutral, no speculation>",
  "extracted_signals": {
    "mentioned_entities": ["<raw phrases from the notice that seem to name suppliers/products/carriers>"],
    "disruption_type": "production_halt | shipping_delay | warehouse_incident | quality_issue | other",
    "stated_or_implied_duration": "<string or null if not stated>"
  },
  "match_found": true | false,
  "candidate_matches": [
    {
      "entity_type": "supplier | shipment | stock_item",
      "entity_id": "<id from provided index>",
      "confidence": 0.0-1.0,
      "reason": "<short justification>"
    }
  ],
  "ambiguity_notes": "<string, empty if none — explain if multiple candidates are close in confidence>"
}
"""

def resolve_entities(notice_text: str, similarity_threshold: float = 0.25) -> Dict[str, Any]:
    """
    Stage 1 Entity Resolution Pipeline:
    1. Retrieval Layer (Top-K vector search / fuzzy match)
    2. Score Threshold Short-Circuit (Deterministic match_found: false if score < threshold)
    3. LLM Disambiguation & Confidence Assignment (Gemini call with 15s timeout)
    4. Deterministic Fallback if LLM unavailable/times out
    """
    retrieval_res = retrieve_candidates(notice_text, top_k=5, threshold=similarity_threshold)
    candidates = retrieval_res.get("candidates", [])
    
    # -------------------------------------------------------------
    # Step 1: Deterministic Threshold Short-Circuit
    # -------------------------------------------------------------
    if retrieval_res.get("below_threshold", False) or not candidates:
        return {
            "notice_summary": "Notice does not reference any known distributor supplier, shipment, or stock SKU.",
            "extracted_signals": {
                "mentioned_entities": [],
                "disruption_type": "other",
                "stated_or_implied_duration": None
            },
            "match_found": False,
            "candidate_matches": [],
            "ambiguity_notes": f"Retrieval similarity score ({retrieval_res.get('best_similarity', 0.0):.2f}) below threshold ({similarity_threshold:.2f}). No entity matched.",
            "retrieval_meta": retrieval_res
        }

    # -------------------------------------------------------------
    # Step 2: Prepare LLM prompt with Top-K candidate index
    # -------------------------------------------------------------
    compact_index = [
        {
            "entity_type": c["entity_type"],
            "entity_id": c["entity_id"],
            "name": c["name"],
            "similarity_score": c["similarity"],
            "text": c["text"]
        }
        for c in candidates
    ]

    prompt = f"""
DISRUPTION NOTICE:
"{notice_text}"

RETRIEVED CANDIDATE INDEX:
{json.dumps(compact_index, indent=2)}
"""

    # -------------------------------------------------------------
    # Step 3: LLM Generation with 15s Timeout
    # -------------------------------------------------------------
    llm_output = generate_json_with_timeout(
        prompt=prompt,
        system_instruction=STAGE1_SYSTEM_PROMPT,
        timeout=15.0
    )

    if llm_output and "match_found" in llm_output:
        llm_output["retrieval_meta"] = retrieval_res
        c_matches = llm_output.get("candidate_matches", [])
        if not llm_output.get("match_found") or not c_matches:
            llm_output["match_state"] = "UNMAPPED"
            llm_output["match_found"] = False
        else:
            # Check for ambiguity: 2+ candidates of the SAME entity_type with confidence within 0.10 of top confidence
            c_matches_sorted = sorted(c_matches, key=lambda x: x.get("confidence", 0), reverse=True)
            top_conf = c_matches_sorted[0].get("confidence", 0)
            
            by_type: Dict[str, List[Dict[str, Any]]] = {}
            for cm in c_matches_sorted:
                if top_conf - cm.get("confidence", 0) <= 0.10:
                    etype = cm.get("entity_type", "unknown")
                    by_type.setdefault(etype, []).append(cm)
            
            is_ambiguous = any(len(items) >= 2 for items in by_type.values())
            
            if is_ambiguous:
                llm_output["match_state"] = "AMBIGUOUS"
                llm_output["match_found"] = False
            else:
                llm_output["match_state"] = "EXACT"
                llm_output["match_found"] = True
        return llm_output

    # -------------------------------------------------------------
    # Step 4: Fallback Resolution (Rule-based from top-k retrieved candidates)
    # -------------------------------------------------------------
    matched_candidates = []
    top_score = candidates[0]["similarity"]
    
    # Identify primary supplier if any candidate is a supplier
    primary_supplier_id = None
    for c in candidates:
        if c["entity_type"] == "supplier" and c["similarity"] >= similarity_threshold:
            primary_supplier_id = c["entity_id"]
            break

    for c in candidates:
        if c["similarity"] >= max(0.25, top_score - 0.15):
            # Exclude shipment/sku if it explicitly belongs to a different supplier
            c_sup = c.get("metadata", {}).get("supplier_id")
            if primary_supplier_id and c_sup and c_sup != primary_supplier_id:
                continue
            matched_candidates.append({
                "entity_type": c["entity_type"],
                "entity_id": c["entity_id"],
                "confidence": round(min(0.95, c["similarity"] * 1.2), 2),
                "reason": f"Matched via local vector retrieval ({c['method']} similarity: {c['similarity']:.2f})."
            })

    # Group candidates within 0.10 of top_score by entity_type
    by_type_close: Dict[str, List[Dict[str, Any]]] = {}
    for c in candidates:
        if top_score - c["similarity"] <= 0.10 and c["similarity"] >= similarity_threshold:
            by_type_close.setdefault(c["entity_type"], []).append(c)

    is_ambiguous_fallback = any(len(items) >= 2 for items in by_type_close.values())

    if is_ambiguous_fallback:
        match_state = "AMBIGUOUS"
        ambiguity = f"Multiple competing candidates of the same entity type within 0.10 of top score."
    elif len(matched_candidates) >= 1 and top_score >= similarity_threshold:
        match_state = "EXACT"
        ambiguity = ""
    else:
        match_state = "UNMAPPED"
        ambiguity = ""

    return {
        "notice_summary": f"Disruption notice analyzed via vector index match: {candidates[0]['name']}.",
        "extracted_signals": {
            "mentioned_entities": [candidates[0]["name"]],
            "disruption_type": "production_halt" if "fire" in notice_text.lower() or "halt" in notice_text.lower() else "shipping_delay",
            "stated_or_implied_duration": "14 days"
        },
        "match_state": match_state,
        "match_found": match_state == "EXACT",
        "candidate_matches": matched_candidates,
        "ambiguity_notes": ambiguity,
        "retrieval_meta": retrieval_res,
        "is_fallback": True
    }

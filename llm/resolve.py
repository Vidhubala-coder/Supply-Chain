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
        return llm_output

    # -------------------------------------------------------------
    # Step 4: Fallback Resolution (Rule-based from top-k retrieved candidates)
    # -------------------------------------------------------------
    matched_candidates = []
    top_score = candidates[0]["similarity"]
    
    for c in candidates:
        if c["similarity"] >= max(0.30, top_score - 0.15):
            matched_candidates.append({
                "entity_type": c["entity_type"],
                "entity_id": c["entity_id"],
                "confidence": round(min(0.95, c["similarity"] * 1.2), 2),
                "reason": f"Matched via local vector retrieval ({c['method']} similarity: {c['similarity']:.2f})."
            })

    ambiguity = ""
    if len(matched_candidates) > 1:
        ambiguity = f"Multiple candidates ({', '.join([m['entity_id'] for m in matched_candidates])}) returned close similarity scores."

    return {
        "notice_summary": f"Disruption notice analyzed via vector index match: {candidates[0]['name']}.",
        "extracted_signals": {
            "mentioned_entities": [candidates[0]["name"]],
            "disruption_type": "production_halt" if "fire" in notice_text.lower() or "halt" in notice_text.lower() else "shipping_delay",
            "stated_or_implied_duration": "14 days"
        },
        "match_found": len(matched_candidates) > 0,
        "candidate_matches": matched_candidates,
        "ambiguity_notes": ambiguity,
        "retrieval_meta": retrieval_res,
        "is_fallback": True
    }

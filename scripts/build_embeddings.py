import os
import json
import numpy as np
import math
import re

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

def build_entity_corpus():
    suppliers_path = os.path.join(DATA_DIR, "suppliers.json")
    stock_path = os.path.join(DATA_DIR, "stock.json")
    shipments_path = os.path.join(DATA_DIR, "shipments.json")

    with open(suppliers_path, "r", encoding="utf-8") as f:
        suppliers = json.load(f)
    with open(stock_path, "r", encoding="utf-8") as f:
        stock = json.load(f)
    with open(shipments_path, "r", encoding="utf-8") as f:
        shipments = json.load(f)

    stock_by_id = {s["sku"]: s for s in stock}
    
    entities = []

    # Suppliers
    for s in suppliers:
        skus_handled = [stock_by_id.get(sku, {}).get("name", sku) for sku in s.get("skus", [])]
        aliases_str = ", ".join(s.get("aliases", []))
        text = (
            f"Supplier ID: {s['id']}. Name: {s['name']}. Aliases: {aliases_str}. "
            f"Region: {s.get('region', '')}. Carrier: {s.get('default_carrier', '')}. "
            f"SKUs supplied: {', '.join(skus_handled)}."
        )
        entities.append({
            "entity_type": "supplier",
            "entity_id": s["id"],
            "name": s["name"],
            "text": text,
            "metadata": {
                "skus": s.get("skus", []),
                "region": s.get("region"),
                "carrier": s.get("default_carrier")
            }
        })

    # Stock Items
    for st in stock:
        text = (
            f"Stock SKU: {st['sku']}. Name: {st['name']}. "
            f"Supplier ID: {st.get('supplier_id', '')}. "
            f"On hand: {st.get('on_hand', 0)}, Reserved: {st.get('reserved', 0)}, Safety stock: {st.get('safety_stock', 0)}."
        )
        entities.append({
            "entity_type": "stock_item",
            "entity_id": st["sku"],
            "name": st["name"],
            "text": text,
            "metadata": {
                "supplier_id": st.get("supplier_id"),
                "on_hand": st.get("on_hand"),
                "unit_cost": st.get("unit_cost")
            }
        })

    # Shipments
    for shp in shipments:
        sku_name = stock_by_id.get(shp["sku"], {}).get("name", shp["sku"])
        text = (
            f"Shipment ID: {shp['shipment_id']}. Supplier: {shp['supplier_id']}. SKU: {shp['sku']} ({sku_name}). "
            f"Quantity: {shp['qty']}. Carrier: {shp['carrier']}. Status: {shp['status']}. "
            f"ETA: {shp['eta']}. Origin: {shp.get('origin', '')}."
        )
        entities.append({
            "entity_type": "shipment",
            "entity_id": shp["shipment_id"],
            "name": f"{shp['shipment_id']} ({sku_name})",
            "text": text,
            "metadata": {
                "supplier_id": shp["supplier_id"],
                "sku": shp["sku"],
                "carrier": shp["carrier"],
                "eta": shp["eta"]
            }
        })

    return entities

def deterministic_feature_vector(text, dim=768):
    """
    Fallback deterministic feature vector generator (768 dimensions, L2 normalized).
    Uses hashed n-gram subword features for robust offline similarity matching.
    """
    tokens = re.findall(r'\w+', text.lower())
    vec = np.zeros(dim, dtype=np.float32)
    
    for token in tokens:
        # Unigram feature
        h1 = hash(token) % dim
        vec[h1] += 1.0
        # Character trigrams for typo resilience
        for i in range(len(token) - 2):
            trigram = token[i:i+3]
            h2 = hash(trigram) % dim
            vec[h2] += 0.5

    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec

def generate_embeddings(entities):
    embeddings = []
    api_key = os.environ.get("GEMINI_API_KEY")
    
    use_gemini = False
    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            print("Generating embeddings using Gemini API (gemini-embedding-001 / text-embedding-004)...")
            for ent in entities:
                response = client.models.embed_content(
                    model="text-embedding-004",
                    contents=ent["text"]
                )
                vec = np.array(response.embedding.values, dtype=np.float32)
                norm = np.linalg.norm(vec)
                if norm > 0:
                    vec = vec / norm
                embeddings.append(vec)
            use_gemini = True
        except Exception as e:
            print(f"Gemini API embedding call failed ({e}). Falling back to deterministic feature vector encoding.")
            use_gemini = False

    if not use_gemini:
        print("Building precomputed vector index using deterministic feature vector encoding...")
        for ent in entities:
            vec = deterministic_feature_vector(ent["text"])
            embeddings.append(vec)

    return np.array(embeddings, dtype=np.float32)

def main():
    entities = build_entity_corpus()
    embeddings = generate_embeddings(entities)

    os.makedirs(DATA_DIR, exist_ok=True)
    npy_path = os.path.join(DATA_DIR, "precomputed_embeddings.npy")
    meta_path = os.path.join(DATA_DIR, "index_meta.json")

    np.save(npy_path, embeddings)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(entities, f, indent=2)

    print(f"Successfully generated precomputed embeddings:")
    print(f"  Vectors saved to: {npy_path} (shape: {embeddings.shape})")
    print(f"  Metadata saved to: {meta_path} ({len(entities)} entities)")

if __name__ == "__main__":
    main()

import json
import os
from typing import Dict, List, Optional

STORES_FILE = os.path.join(os.path.dirname(__file__), 'stores.json')

def load_stores() -> Dict:
    """Load stores data from JSON file"""
    try:
        with open(STORES_FILE, 'r') as f:
            data = json.load(f)
        return data.get('stores', {})
    except FileNotFoundError:
        raise ValueError(f"Stores file not found at {STORES_FILE}")
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON in stores file")

def validate_store_id(store_id: str) -> bool:
    """Check if store ID exists in stores database"""
    stores = load_stores()
    return store_id in stores

def get_store_info(store_id: str) -> Optional[Dict]:
    """Get store information by ID"""
    stores = load_stores()
    return stores.get(store_id)

def get_store_products(store_id: str) -> List[str]:
    """Get list of product barcodes available in store"""
    store_info = get_store_info(store_id)
    if store_info:
        return store_info.get('products', [])
    return []

def filter_recommendations_by_store(recommendations: List[Dict], store_id: str) -> List[Dict]:
    """Filter recommendation list to only include products available in store"""
    store_products = get_store_products(store_id)

    if not store_products:
        return recommendations

    filtered_recommendations = []
    for rec in recommendations:
        # Check if the recommendation has a barcode/product code
        product_code = rec.get('barcode') or rec.get('code') or rec.get('product_id')
        if product_code and str(product_code) in store_products:
            filtered_recommendations.append(rec)
        # If no product code, include it (some recommendations might not have barcodes)
        elif not product_code:
            filtered_recommendations.append(rec)

    return filtered_recommendations

def get_all_store_ids() -> List[str]:
    """Get list of all available store IDs"""
    stores = load_stores()
    return list(stores.keys())

def get_all_stores() -> Dict:
    """Get all stores information"""
    return load_stores()

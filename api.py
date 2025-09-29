import requests
import sys
from pathlib import Path
from typing import Dict, Optional, Any

# Add the project root to Python path to allow absolute imports
sys.path.append(str(Path(__file__).parent))

from recommender import ProductRecommender

def fetch_product(barcode: str, country_code: str = 'in') -> Optional[Dict[str, Any]]:
    """
    Fetch product data from Open Food Facts API with country-specific filtering.
    
    Args:
        barcode: The barcode of the product to look up
        country_code: ISO 3166-1 alpha-2 country code (default: 'in' for India)
        
    Returns:
        Dict containing product data and recommendations, or None if not found
    """
    try:
        # Request only the fields we need to reduce response size
        fields = [
            "code", "product_name", "brands", "categories_tags", "ingredients_text",
            "nutriscore_grade", "ecoscore_grade", "image_url", "nutriments", 
            "nova_group", "additives_n", "allergens", "quantity", "countries_tags",
            "purchase_places"
        ]
        
        # Use v2 of the API for better country filtering
        url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
        params = {
            "fields": ",".join(fields),
            "cc": country_code,  # Filter by country
            "lc": "en"          # Prefer English labels
        }
        
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        if data.get("status") != 1 or not data.get("product"):
            return None
            
        product = data["product"]
        
        # Get recommendations using the new ProductRecommender
        recommender = ProductRecommender(product)
        recommendations = recommender.recommend()
        
        # Get the most specific category (last one in categories_tags)
        categories = product.get("categories_tags", [])
        category = categories[-1] if categories else None
        
        # Format the response according to requirements
        return {
            "scanned_product": {
                "name": product.get("product_name"),
                "brand": (product.get("brands", "").split(',')[0] 
                         if product.get("brands") else None),
                "nutriscore": product.get("nutriscore_grade"),
                "ecoscore": product.get("ecoscore_grade"),
                "category": category
            },
            "recommendations": recommendations
        }
        
    except requests.RequestException as e:
        print(f"Error fetching product data: {e}")
        return None

import requests
import sys
from pathlib import Path
from typing import Dict, Optional, Any

# Add the project root to Python path to allow absolute imports
sys.path.append(str(Path(__file__).parent))

from recommender import ProductRecommender

def fetch_product(barcode: str) -> Optional[Dict[str, Any]]:
    """
    Fetch product data from Open Food Facts API along with recommendations.
    
    Args:
        barcode: The barcode of the product to look up
        
    Returns:
        Dict containing product data and recommendations, or None if not found
    """
    try:
        # Request only the fields we need to reduce response size
        fields = [
            "code", "product_name", "brands", "categories_tags", "ingredients_text",
            "nutriscore_grade", "ecoscore_grade", "image_url", "nutriments", 
            "nova_group", "additives_n", "allergens", "quantity"
        ]
        
        url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
        params = {"fields": ",".join(fields)}
        
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

def find_similar_products(category: str, exclude_barcode: str = None, limit: int = 5) -> list:
    """
    Find products in the same category as a fallback recommendation method.
    
    Args:
        category: The category to search in
        exclude_barcode: Barcode to exclude from results (the original product)
        limit: Maximum number of products to return
        
    Returns:
        List of similar products with basic information
    """
    try:
        # Request only the fields we need to reduce response size
        fields = [
            "code", "product_name", "brands", "categories_tags",
            "nutriscore_grade", "ecoscore_grade", "image_url", "nutriments"
        ]
        
        # Search for products in the same category
        params = {
            "json": "1",
            "action": "process",
            "tagtype_0": "categories",
            "tag_contains_0": "contains",
            "tag_0": category,
            "fields": ",".join(fields),
            "page_size": limit + (1 if exclude_barcode else 0),  # Get one extra in case we need to exclude one
            "sort_by": "unique_scans_n",  # Sort by popularity
            "page": 1
        }
        
        url = "https://world.openfoodfacts.org/cgi/search.pl"
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        if not data.get("products"):
            return []
            
        # Format the products
        similar_products = []
        for product in data["products"]:
            # Skip the original product if it's in the results
            if exclude_barcode and str(product.get("code")) == str(exclude_barcode):
                continue
                
            # Skip products without a name or barcode
            if not product.get("product_name") or not product.get("code"):
                continue
                
            similar_products.append({
                "code": product.get("code"),
                "product_name": product.get("product_name"),
                "brands": product.get("brands", ""),
                "nutriscore_grade": product.get("nutriscore_grade", "").lower(),
                "ecoscore_grade": product.get("ecoscore_grade", "").lower(),
                "image_url": product.get("image_url", ""),
                "reason": f"Similar product in the {category} category"
            })
            
            # Stop if we have enough products
            if len(similar_products) >= limit:
                break
                
        return similar_products
        
    except Exception as e:
        print(f"Error finding similar products: {e}")
        return []

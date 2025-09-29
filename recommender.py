import requests
from typing import Dict, List, Optional, Tuple
import time

class ProductRecommender:
    """
    Recommends alternative products based on Nutri-Score and Eco-Score.
    Fetches real products from Open Food Facts API with pagination support.
    """
    
    BASE_URL = "https://world.openfoodfacts.org"
    PAGE_SIZE = 100  # Max allowed by the API
    REQUEST_DELAY = 2  # Seconds to wait between API requests to respect rate limits
    
    def __init__(self, product_data: Dict):
        self.product_data = product_data
        self.scanned_nutriscore = (product_data.get("nutriscore_grade") or "").lower()
        self.scanned_ecoscore = (product_data.get("ecoscore_grade") or "").lower()
    
    def get_most_specific_category(self) -> Optional[str]:
        """Extract the most specific category from the product's categories_tags."""
        categories = self.product_data.get("categories_tags", [])
        if not categories:
            return None
        
        # Return the most specific category (usually the last one)
        return categories[-1].replace("en:", "")
    
    def _fallback_search_products(self, category: str, page: int = 1) -> Tuple[List[Dict], bool]:
        """
        Fallback method to search for products using the search API when category search fails.
        
        Args:
            category: The category to search for
            page: Page number to fetch
            
        Returns:
            Tuple of (products, has_more) where has_more indicates if there are more pages
        """
        try:
            # Use the search API with the category as a search term
            url = f"{self.BASE_URL}/cgi/search.pl"
            params = {
                "search_terms": category,
                "page_size": self.PAGE_SIZE,
                "page": page,
                "json": 1,
                "fields": "code,product_name,brands,nutriscore_grade,ecoscore_grade,categories_tags,image_url"
            }
            
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            if not isinstance(data, dict):
                return [], False
                
            products = data.get("products", [])
            
            # Estimate if there are more pages
            count = data.get("count", 0)
            has_more = count > (page * self.PAGE_SIZE) if count else len(products) >= self.PAGE_SIZE
            
            return products, has_more
            
        except (requests.RequestException, ValueError) as e:
            print(f"Error in fallback search: {e}")
            return [], False
    
    def fetch_category_products(self, category: str, page: int = 1, page_size: int = 50) -> tuple[List[Dict], bool]:
        """
        Fetch products from a specific category with pagination.
        
        Args:
            category: The category to search in
            page: Page number (1-based)
            page_size: Number of products per page (reduced for better API compatibility)
            
        Returns:
            Tuple of (products_list, has_more_pages)
        """
        try:
            # Use the search API instead of category endpoint for better field support
            url = "https://world.openfoodfacts.org/cgi/search.pl"
            params = {
                "search_terms": "",
                "tagtype_0": "categories",
                "tag_contains_0": "contains",
                "tag_0": category,
                "page": page,
                "page_size": page_size,
                "json": 1,
                "fields": "code,product_name,brands,nutriscore_grade,ecoscore_grade,categories_tags,image_url"
            }
            
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            products = data.get("products", [])
            
            # Check if there are more pages
            count = data.get("count", 0)
            has_more = count > (page * page_size) if count else len(products) >= page_size
            
            return products, has_more
            
        except requests.RequestException as e:
            print(f"Error fetching category products: {e}")
            # Try fallback search on error
            if page == 1:
                return self._fallback_search_products(category, page)
            return [], False
    
    def get_all_category_products(self, category: str, max_pages: int = 10) -> List[Dict]:
        """
        Fetch all products from a category with pagination and multiple search strategies.
        
        Args:
            category: The category to search in
            max_pages: Maximum number of pages to fetch (to prevent excessive API calls)
            
        Returns:
            List of all products from the category
        """
        # First try: Direct category search
        all_products = self._fetch_products_with_pagination(category, max_pages)
        
        # If no products found, try with broader categories
        if not all_products and ':' in category:
            # Try with parent category (e.g., 'en:breakfast-cereals' -> 'breakfast-cereals')
            simple_category = category.split(':')[-1]
            all_products = self._fetch_products_with_pagination(simple_category, max_pages)
            
            # If still no products, try with a more general search
            if not all_products and '-' in simple_category:
                general_category = simple_category.split('-')[0]
                all_products = self._fetch_products_with_pagination(general_category, max_pages)
        
        return all_products
    
    def _fetch_products_with_pagination(self, category: str, max_pages: int) -> List[Dict]:
        """Helper method to fetch products with pagination."""
        all_products = []
        page = 1
        has_more = True
        
        while has_more and page <= max_pages:
            products, has_more = self.fetch_category_products(category, page)
            
            if not products and page == 1:
                # If first page is empty, no need to continue
                break
                
            all_products.extend(products)
            
            if has_more and page < max_pages:
                time.sleep(self.REQUEST_DELAY)
                page += 1
            else:
                break
                
        return all_products
    
    def is_healthier_alternative(self, product: Dict) -> bool:
        """
        Check if a product is a healthier alternative to the scanned product.
        A product is considered healthier if it has a better Nutri-Score.
        """
        if not self.scanned_nutriscore or self.scanned_nutriscore in [""]:
            return False
            
        # Map scores to numerical values for comparison
        score_map = {'a': 5, 'b': 4, 'c': 3, 'd': 2, 'e': 1}
        
        current_score = score_map.get(self.scanned_nutriscore.lower(), 0)
        product_score = score_map.get((product.get("nutriscore_grade") or "").lower(), 0)
        
        # Product is healthier if its score is higher than the current product
        return product_score > current_score
    
    def is_greener_alternative(self, product: Dict) -> bool:
        """
        Check if a product is a more sustainable alternative to the scanned product.
        A product is considered more sustainable if it has a better Eco-Score.
        """
        if not self.scanned_ecoscore or self.scanned_ecoscore in ["", "unknown", "not-applicable"]:
            return False
            
        # Map scores to numerical values for comparison
        score_map = {'a': 5, 'b': 4, 'c': 3, 'd': 2, 'e': 1}
        
        current_score = score_map.get(self.scanned_ecoscore.lower(), 0)
        product_score = score_map.get((product.get("ecoscore_grade") or "").lower(), 0)
        
        # Product is more sustainable if its score is higher than the current product
        # and the product has at least a 'c' score
        return product_score > current_score and product_score >= 3  # At least 'C' score
    
    def _calculate_health_score(self, product: Dict) -> float:
        """Calculate a health score based on Nutri-Score and other factors."""
        # Map Nutri-Score to numerical values (A=5, B=4, ..., E=1)
        nutriscore_map = {'a': 5, 'b': 4, 'c': 3, 'd': 2, 'e': 1}
        nutriscore = (product.get("nutriscore_grade") or "").lower()
        score = nutriscore_map.get(nutriscore, 0)
        
        # Add small bonus for organic products
        if "organic" in (product.get("categories_tags") or []):
            score += 0.5
            
        return score
    
    def _calculate_sustainability_score(self, product: Dict) -> float:
        """Calculate a sustainability score based on Eco-Score and other factors."""
        # Map Eco-Score to numerical values (A=5, B=4, ..., E=1)
        ecoscore_map = {'a': 5, 'b': 4, 'c': 3, 'd': 2, 'e': 1}
        ecoscore = (product.get("ecoscore_grade") or "").lower()
        score = ecoscore_map.get(ecoscore, 0)
        
        # Add bonus for organic and fair trade
        categories = [c.lower() for c in (product.get("categories_tags") or [])]
        if any(term in categories for term in ["organic", "bio", "ecocert"]):
            score += 0.5
        if any(term in categories for term in ["fairtrade", "fair-trade"]):
            score += 0.3
            
        return score
    
    def recommend(self) -> List[Dict]:
        """
        Generate product recommendations based on Nutri-Score and Eco-Score.
        
        Returns:
            List of recommended products with details, sorted by relevance
        """
        category = self.get_most_specific_category()
        if not category:
            return []
        
        products = self.get_all_category_products(category)
        
        if not products:
            return []
        
        recommendations = []
        
        # Get the scanned product's scores (or defaults if not available)
        scanned_nutriscore = (self.scanned_nutriscore or "").lower()
        scanned_ecoscore = (self.scanned_ecoscore or "").lower()
        
        for product in products:
            # Skip products without required data
            if not all(key in product for key in ["product_name", "nutriscore_grade", "ecoscore_grade"]):
                continue
                
            # Skip the scanned product itself
            if product.get("code") == self.product_data.get("code"):
                continue
                
            nutriscore = (product.get("nutriscore_grade") or "").lower()
            ecoscore = (product.get("ecoscore_grade") or "").lower()
            
            # Skip products with completely missing scores
            if not nutriscore or not ecoscore:
                continue
                
            # Calculate scores for ranking
            health_score = self._calculate_health_score(product)
            sustainability_score = self._calculate_sustainability_score(product)
            
            # Prepare base recommendation according to requirements
            recommendation = {
                "product_name": product.get("product_name"),
                "brand": product.get("brands", "").split(",")[0] if product.get("brands") else None,
                "nutriscore": nutriscore,
                "ecoscore": ecoscore
            }
            
            
            # Apply filtering logic according to requirements
            should_recommend = False
            
            # Rule 1: If scanned product has Nutri-Score D or E → recommend products with Nutri-Score A/B/C
            if (scanned_nutriscore and scanned_nutriscore in ['d', 'e'] and 
                nutriscore and nutriscore in ['a', 'b', 'c']):
                recommendation["reason"] = "Better nutritional quality"
                should_recommend = True
                
            # Rule 2: If scanned product has Nutri-Score A or B but Eco-Score D or E → recommend products with Eco-Score A/B/C
            elif (scanned_nutriscore and scanned_nutriscore in ['a', 'b'] and
                  scanned_ecoscore and scanned_ecoscore in ['d', 'e'] and
                  ecoscore and ecoscore in ['a', 'b', 'c']):
                recommendation["reason"] = "Better environmental impact"
                should_recommend = True
            
            if should_recommend:
                recommendations.append(recommendation)
        
        if not recommendations:
            return []
        
        # Remove duplicates and return clean results
        seen = set()
        unique_recommendations = []
        
        for rec in recommendations:
            rec_name = rec.get("product_name")
            if rec_name and rec_name not in seen:
                seen.add(rec_name)
                unique_recommendations.append(rec)
        
        return unique_recommendations

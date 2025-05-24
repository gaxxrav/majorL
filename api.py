import requests

def fetch_product(barcode):
    url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
    response = requests.get(url)
    data = response.json()

    if data.get("status") == 1:
        product = data["product"]
        print("Product:", product.get("product_name", "N/A"))
        print("Brands:", product.get("brands", "N/A"))
        print("Ingredients:", product.get("ingredients_text", "N/A"))
        print("Calories (per 100g):", product.get("nutriments", {}).get("energy-kcal_100g", "N/A"))
        print("Fat (g):", product.get("nutriments", {}).get("fat_100g", "N/A"))
        print("Carbs (g):", product.get("nutriments", {}).get("carbohydrates_100g", "N/A"))
        print("Protein (g):", product.get("nutriments", {}).get("proteins_100g", "N/A"))
    else:
        print("Product not found.")
    return None

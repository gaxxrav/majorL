import json
from api import fetch_product

def test_product_recommendations(barcode):
    """Test the product recommendation system with a given barcode."""
    print(f"\n{'='*80}")
    print(f"Testing product with barcode: {barcode}")
    print("="*80)
    
    # Fetch product data and recommendations
    print("\nFetching product data...")
    result = fetch_product(barcode)
    
    if not result:
        print("❌ Product not found or error occurred.")
        return
    
    # Print scanned product info
    scanned = result["scanned_product"]
    print("\n📦 Scanned Product:")
    print(f"   Name: {scanned['name']}")
    print(f"   Brand: {scanned['brand'] or 'Unknown'}")
    print(f"   Nutri-Score: {scanned['nutriscore'] or 'N/A'}")
    print(f"   Eco-Score: {scanned['ecoscore'] or 'N/A'}")
    print(f"   Category: {scanned['category'] or 'N/A'}")
    
    # Print recommendations
    recommendations = result["recommendations"]
    print(f"\n✨ Found {len(recommendations)} recommendations:")
    for i, rec in enumerate(recommendations[:10], 1):
        print(f"\n{i}. {rec['product_name']}")
        print(f"   Brand: {rec['brand'] or 'Unknown'}")
        print(f"   Reason: {rec['reason']}")
        print(f"   Nutri-Score: {rec['nutriscore'].upper()}")
        print(f"   Eco-Score: {rec['ecoscore'].upper()}")

def main():
    # Test with a specific known product that should have recommendations
    test_barcodes = [
        "3017620422003",  # Nutella - should have healthier alternatives
        "7622210285288",  # Milka Chocolate - another product that might have alternatives
        "5449000000996"   # Coca Cola - for testing products with unknown scores
    ]
    
    for barcode in test_barcodes:
        test_product_recommendations(barcode)
        print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    main()

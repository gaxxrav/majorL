from scanner import scan_barcode
from api import fetch_product

if __name__ == "__main__":
    print("Scanning barcode...")
    barcode = scan_barcode()
    if barcode:
        print(f"Barcode: {barcode}")
        product = fetch_product(barcode)
        if product:
            print("\nProduct Details:")
            for k, v in product.items():
                print(f"{k.capitalize()}: {v}")
        else:
            print("Product not found.")
    else:
        print("No barcode detected.")

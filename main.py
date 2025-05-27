import cv2
import numpy as np
import requests
from flask import Flask, render_template, request, jsonify
import os
from pyzbar.pyzbar import decode as pyzbar_decode

app = Flask(__name__)

def process_barcode_image(image):
    """Process image to improve barcode detection"""
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Apply adaptive thresholding to handle different lighting conditions
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY, 11, 2
    )
    
    # Apply some blur to reduce noise
    blurred = cv2.GaussianBlur(thresh, (3, 3), 0)
    
    # Try different processing techniques
    processed_images = [
        gray,  # Original grayscale
        thresh,  # Thresholded
        blurred,  # Blurred
        cv2.bitwise_not(blurred),  # Inverted
    ]
    
    return processed_images

def fetch_product_info(barcode):
    """Fetch product information from Open Food Facts API"""
    url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data.get("status") == 1:
            product = data["product"]
            return {
                "status": "success",
                "product_name": product.get("product_name", "N/A"),
                "brands": product.get("brands", "N/A"),
                "quantity": product.get("quantity", "N/A"),
                "ingredients": product.get("ingredients_text", "N/A"),
                "nutriments": product.get("nutriments", {})
            }
        return {"status": "not_found", "message": "Product not found in database"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/scan', methods=['POST'])
def scan():
    if 'image' not in request.files:
        return jsonify({"status": "error", "message": "No image file provided"}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No selected file"}), 400
    
    try:
        # Read image file
        img_bytes = file.read()
        np_arr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        
        if img is None:
            return jsonify({"status": "error", "message": "Could not read image"}), 400

        # Process the image with multiple techniques
        processed_images = process_barcode_image(img)
        
        # Try to detect barcodes in each processed version
        barcodes_found = []
        for processed_img in processed_images:
            try:
                # Try pyzbar first
                barcodes = pyzbar_decode(processed_img)
                
                for barcode in barcodes:
                    barcode_data = barcode.data.decode('utf-8')
                    # Only add if it's a valid barcode (EAN-13, UPC-A, etc.)
                    if len(barcode_data) >= 8:  # Most barcodes are at least 8 digits
                        # Clean the barcode data (remove any non-digit characters)
                        clean_barcode = ''.join(c for c in barcode_data if c.isdigit())
                        if clean_barcode not in [b[0] for b in barcodes_found]:
                            barcodes_found.append((clean_barcode, barcode.type))
            except Exception as e:
                print(f"Error processing image: {str(e)}")
                continue
        
        if not barcodes_found:
            return jsonify({"status": "not_found", "message": "No valid barcode detected in the image"})
        
        # Get the most likely barcode (prioritize longer barcodes as they're more specific)
        barcodes_found.sort(key=lambda x: len(x[0]), reverse=True)
        barcode_data = barcodes_found[0][0]
        barcode_type = barcodes_found[0][1]
        
        print(f"Detected barcode: {barcode_data} (Type: {barcode_type})")
        
        # Fetch product info
        product_info = fetch_product_info(barcode_data)
        
        if product_info["status"] == "success":
            return jsonify({
                "status": "success",
                "barcode": barcode_data,
                "product": product_info
            })
        else:
            return jsonify({
                "status": "not_found",
                "barcode": barcode_data,
                "message": "Product not found in database"
            })
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    os.makedirs('uploads', exist_ok=True)
    app.run(host='0.0.0.0', port=5001, debug=True)

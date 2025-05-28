import cv2
import numpy as np
import requests
from flask import Flask, render_template, request, jsonify
import os
from pyzbar.pyzbar import decode as pyzbar_decode
from dotenv import load_dotenv
import google.generativeai as genai
import os

load_dotenv()

app = Flask(__name__)
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-1.5-flash')

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
    url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data.get("status") == 1:
            product = data["product"]
            # Check multiple possible ingredient fields
            ingredients = product.get("ingredients_text") or product.get("ingredients_text_en") or "N/A"
            
            return {
                "status": "success",
                "product_name": product.get("product_name", "N/A"),
                "brands": product.get("brands", "N/A"),
                "quantity": product.get("quantity", "N/A"),
                "ingredients_text": ingredients,  # Make sure this matches your frontend
                "nutriments": product.get("nutriments", {}),
                "nutriscore_grade": product.get("nutriscore_grade", "").lower()
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
                barcodes = pyzbar_decode(processed_img)
                for barcode in barcodes:
                    barcode_data = barcode.data.decode('utf-8')
                    if len(barcode_data) >= 8:  # Minimum valid barcode length
                        clean_barcode = ''.join(c for c in barcode_data if c.isdigit())
                        if clean_barcode not in [b[0] for b in barcodes_found]:
                            barcodes_found.append((clean_barcode, barcode.type))
            except Exception as e:
                print(f"Barcode decode error: {str(e)}")
                continue
        
        if not barcodes_found:
            return jsonify({
                "status": "not_found", 
                "message": "No valid barcode detected"
            })

        # Get the most likely barcode
        barcodes_found.sort(key=lambda x: len(x[0]), reverse=True)
        barcode_data, barcode_type = barcodes_found[0]
        
        print(f"Detected barcode: {barcode_data} (Type: {barcode_type})")
        
        # Fetch product info from Open Food Facts
        product_info = fetch_product_info(barcode_data)
        
        # Enhanced response structure
        response_data = {
            "status": product_info["status"],
            "barcode": barcode_data,
            "product": product_info
        }

        if product_info["status"] == "success":
            # Add Gemini analysis only if ingredients exist
            ingredients = product_info.get("ingredients_text", "N/A")
            analysis = analyze_ingredients(ingredients)
            
            # Merge analysis with product info
            response_data["product"]["ingredient_analysis"] = {
                "health_warnings": analysis.get("health_warnings", []),
                "allergens": analysis.get("allergens", []),
                "analysis": analysis.get("analysis", "No analysis available"),
                "source": analysis.get("source", "Unknown")
            }
            
            # Add barcode type to response
            response_data["barcode_type"] = str(barcode_type)
            
        return jsonify(response_data)

    except Exception as e:
        print(f"Scan endpoint error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Internal server error: {str(e)}"
        }), 500

def analyze_ingredients(ingredients_text):
    """Use Gemini to analyze ingredients for health and allergens"""
    if not ingredients_text or ingredients_text == "N/A":
        return {
            "health_warnings": [],
            "allergens": [],
            "analysis": "No ingredient information available"
        }
    
    try:
        prompt = f"""
        Analyze these food product ingredients for potential health concerns and allergens:
        {ingredients_text}

        Respond in JSON format with these keys:
        - "health_warnings": list of potentially unhealthy ingredients/additives
        - "allergens": list of common allergens present
        - "analysis": brief summary of healthiness (1-2 sentences)
        """
        
        response = model.generate_content(prompt)
        
        try:
            # Try to parse the JSON response
            return eval(response.text)
        except:
            # Fallback if JSON parsing fails
            return {
                "health_warnings": [],
                "allergens": [],
                "analysis": response.text
            }
            
    except Exception as e:
        print(f"Gemini API error: {str(e)}")
        return {
            "health_warnings": [],
            "allergens": [],
            "analysis": "Could not analyze ingredients"
        }
    
if __name__ == "__main__":
    os.makedirs('uploads', exist_ok=True)
    app.run(host='0.0.0.0', port=5001, debug=True)

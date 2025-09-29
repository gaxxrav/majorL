import cv2

import numpy as np
import requests
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import os
from dotenv import load_dotenv
import google.generativeai as genai
import json
import re
from api import fetch_product
from store_manager import load_stores, validate_store_id, get_store_info, filter_recommendations_by_store, get_all_stores

load_dotenv()

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'  # Required for sessions
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-1.5-flash')

def get_store_id_from_session():
    return session.get('store_id')

def set_store_id_in_session(store_id):
    session['store_id'] = store_id
    """Process image to improve barcode detection"""
    # Initialize the barcode detector
    barcode_detector = cv2.barcode.BarcodeDetector()
    
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
                "sugar": product.get("nutrients", {}).get("sugars_100g", "N/A"),
                "ingredients_text": ingredients,  # Make sure this matches your frontend
                "nutrients": product.get("nutrients", {}),
                "nutriscore_grade": product.get("nutriscore_grade", "").lower()
            }
        return {"status": "not_found", "message": "Product not found in database"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    

@app.route('/')
def index():
    # Redirect to store selection if no store is selected
    if 'store_id' not in session:
        return redirect('/select-store')
    return render_template('index.html')

@app.route('/select-store', methods=['GET'])
def select_store_page():
    return render_template('store_selection.html')

@app.route('/api/stores', methods=['GET'])
def get_stores():
    try:
        stores = get_all_stores()
        return jsonify({
            'success': True,
            'stores': stores
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/verify-store/<store_id>', methods=['GET'])
def verify_store(store_id):
    try:
        store_info = get_store_info(store_id)
        if store_info:
            return jsonify({
                'success': True,
                'store': {
                    'name': store_info['name'],
                    'location': store_info['location']
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Store not found'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/select-store', methods=['POST'])
def select_store():
    data = request.get_json()
    store_id = data.get('store_id')
    
    if not store_id:
        return jsonify({
            'success': False,
            'error': 'No store ID provided'
        }), 400
        
    if not validate_store_id(store_id):
        return jsonify({
            'success': False,
            'error': 'Invalid store ID'
        }), 400
        
    session['store_id'] = store_id
    return jsonify({
        'success': True,
        'store_id': store_id
    })

@app.route('/api/current-store', methods=['GET'])
def current_store():
    if 'store_id' not in session:
        return jsonify({
            'success': False,
            'error': 'No store selected'
        }), 404
        
    store_info = get_store_info(session['store_id'])
    if not store_info:
        return jsonify({
            'success': False,
            'error': 'Store not found'
        }), 404
        
    return jsonify({
        'success': True,
        'store': {
            'id': session['store_id'],
            'name': store_info['name'],
            'location': store_info['location']
        }
    })

@app.route('/product/<barcode>')
def product_details(barcode):
    # Get product details from Open Food Facts
    product = fetch_product(barcode)
    if not product:
        return jsonify({"status": "error", "message": "Product not found"}), 404
    
    return render_template('result.html', product=product)

@app.route('/api/recommendations/<barcode>', methods=['GET'])
def get_recommendations(barcode):
    try:
        # Get store ID from session
        store_id = session.get('store_id')
        if not store_id:
            return jsonify({
                'success': False,
                'error': 'No store selected. Please select a store first.'
            }), 400

        # Get the original product
        product = fetch_product(barcode)
        if not product:
            return jsonify({
                'success': False,
                'error': 'Product not found in database'
            }), 404

        # Get store products
        store_products = get_store_products(store_id) if store_id else None
        
        # Get recommendations from the recommender
        recommendations = []
        try:
            from recommender import get_recommendations as get_ai_recommendations
            recommendations = get_ai_recommendations(product)
            
            # Filter recommendations based on store inventory if store is selected
            if store_products:
                recommendations = [r for r in recommendations if str(r.get('code')) in store_products]
                
            # Limit to top 15 recommendations (pagination will handle the rest)
            recommendations = recommendations[:15]
            
        except Exception as e:
            print(f"Error getting AI recommendations: {str(e)}")
            # Fallback to similar products from the same category
            if 'categories' in product and product['categories']:
                from api import find_similar_products
                recommendations = find_similar_products(
                    product['categories'].split(',')[0],
                    exclude_barcode=barcode,
                    limit=10
                )
                
                # Filter by store
                if store_products:
                    recommendations = [r for r in recommendations if str(r.get('code')) in store_products]
        
        return jsonify({
            'success': True,
            'recommendations': recommendations,
            'store_filtered': bool(store_products)
        })
        
    except Exception as e:
        print(f"Error in get_recommendations: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to get recommendations',
            'details': str(e)
        }), 500

@app.route('/change-store', methods=['GET'])
def change_store():
    session.pop('store_id', None)
    return redirect('/select-store')

@app.route('/scanner')
def scanner():
    if 'store_id' not in session:
        return redirect('/select-store')
    return render_template('index.html')

@app.route('/product/<barcode>', methods=['GET'])
def get_product_recommendations(barcode):
    """
    Get product details and recommendations for a given barcode.

    Returns JSON with:
    - scanned_product: {name, brand, nutriscore, ecoscore, category}
    - recommendations: list of products with {product_name, brand, nutriscore, ecoscore, reason}
    """
    try:
        # Validate barcode format
        if not barcode or not barcode.isdigit() or len(barcode) < 8:
            return jsonify({
                "error": "Invalid barcode format. Must be at least 8 digits."
            }), 400

        # Get store ID from session
        store_id = get_store_id_from_session()
        if not store_id:
            return jsonify({
                "error": "Please select a store first."
            }), 400

        # Fetch product data and recommendations
        result = fetch_product(barcode)

        if not result:
            return jsonify({
                "error": "Product not found or API error occurred."
            }), 404

        # Filter recommendations by store inventory
        if 'recommendations' in result and result['recommendations']:
            filtered_recommendations = filter_recommendations_by_store(
                result['recommendations'],
                store_id
            )
            result['recommendations'] = filtered_recommendations
            result['store_filtered'] = True
        else:
            result['store_filtered'] = False

        return jsonify(result)

    except Exception as e:
        return jsonify({
            "error": f"Internal server error: {str(e)}"
        }), 500
    """
    Get product details and recommendations for a given barcode.
    
    Returns JSON with:
    - scanned_product: {name, brand, nutriscore, ecoscore, category}
    - recommendations: list of products with {product_name, brand, nutriscore, ecoscore, reason}
    """
    try:
        # Validate barcode format
        if not barcode or not barcode.isdigit() or len(barcode) < 8:
            return jsonify({
                "error": "Invalid barcode format. Must be at least 8 digits."
            }), 400
        
        # Fetch product data and recommendations
        result = fetch_product(barcode)
        
        if not result:
            return jsonify({
                "error": "Product not found or API error occurred."
            }), 404
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            "error": f"Internal server error: {str(e)}"
        }), 500

@app.route('/scan', methods=['POST'])
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
        
        # Try to detect barcodes
        barcodes_found = []
        for processed_img in processed_images:
            try:
                barcodes = pyzbar_decode(processed_img)
                for barcode in barcodes:
                    barcode_data = barcode.data.decode('utf-8')
                    if len(barcode_data) >= 8:
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
        
        # 1. FIRST FETCH FROM OPEN FOOD FACTS
        product_info = fetch_product_info(barcode_data)
        
        response_data = {
            "status": product_info["status"],
            "barcode": barcode_data,
            "barcode_type": str(barcode_type),
            "product": product_info
        }

        if product_info["status"] == "success":
            ## 2. CALCULATE NUTRI-SCORE IF MISSING
            if not product_info.get("nutriscore_grade") or product_info["nutriscore_grade"] == "":
                if product_info.get("nutrients"):
                    print("Calculating Nutri-Score with Gemini...")
                    nutriscore_result = calculate_nutriscore_with_gemini(
                        product_info["nutrients"], 
                        product_info.get("product_name", "")
                    )
                
                    # Add calculated Nutri-Score to product info
                    product_info["nutriscore_grade"] = nutriscore_result["nutriscore_grade"]
                    product_info["nutriscore_source"] = nutriscore_result["calculation_source"]
                    product_info["nutriscore_details"] = nutriscore_result["details"]
                
                    print(f"Calculated Nutri-Score: {nutriscore_result['nutriscore_grade']}")
        
            # 3. ANALYZE INGREDIENTS IF AVAILABLE
            if product_info.get("ingredients_text") and product_info["ingredients_text"] != "N/A":
                analysis = analyze_ingredients(product_info["ingredients_text"])
                response_data["product"]["ingredient_analysis"] = analysis
            
            return jsonify(response_data)
        
        return jsonify(response_data)

    except Exception as e:
        print(f"Scan endpoint error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Internal server error: {str(e)}"
        }), 500
    
def analyze_ingredients(ingredients_text):
    """Use Gemini to analyze ingredients for health, allergens, and environmental impact"""
    if not ingredients_text or ingredients_text == "N/A":
        return {
            "health_warnings": [],
            "allergens": [],
            "health_concerns": [],
            "environmental_impact": {
                "score": 3,
                "label": "Moderate",
                "summary": "No ingredient information available",
                "main_concern": "",
                "suggestion": ""
            },
            "analysis": "No ingredient information available"
        }
    
    try:
        prompt = f"""
        Analyze these food product ingredients for health and allergens:
        {ingredients_text}

        Respond ONLY with valid JSON in this exact format:
        {{
            "health_warnings": ["warning1", "warning2"],
            "allergens": ["allergen1", "allergen2"],
            "analysis": "brief health summary"
        }}
        
        Rules:
        - Maximum 3 health warnings
        - Maximum 3 allergens
        - Analysis must be under 50 words
        - Only return the JSON object, no other text
        - No markdown formatting
        """
        
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        print(f"Raw Gemini response: {response_text}")  # Debug log
        
        # Clean the response - remove markdown code blocks if present
        json_text = response_text
        if response_text.startswith('```'):
            # Extract JSON from markdown code block
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                json_text = json_match.group(1)
            else:
                # Try to find JSON between the first { and last }
                start = response_text.find('{')
                end = response_text.rfind('}')
                if start != -1 and end != -1 and end > start:
                    json_text = response_text[start:end+1]
        
        # Parse JSON properly
        try:
            result = json.loads(json_text)
            print(f"Parsed JSON: {result}")  # Debug log
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            print(f"Attempted to parse: {json_text}")
            # Fallback: try to extract info manually
            return extract_info_manually(response_text)
        
        # Ensure required fields exist with proper defaults
        result = {
            "health_warnings": result.get("health_warnings", [])[:3],  # Limit to 3
            "allergens": result.get("allergens", [])[:3],  # Limit to 3
            "analysis": result.get("analysis", "Analysis unavailable")
        }
        
        return result
        
    except Exception as e:
        print(f"Gemini API error: {str(e)}")
        return {
            "health_warnings": [],
            "allergens": [],
            "analysis": f"Analysis failed: {str(e)}"
        }

def extract_info_manually(response_text):
    """Fallback method to extract information if JSON parsing fails"""
    try:
        # Simple regex patterns to extract info
        health_warnings = []
        allergens = []
        
        # Look for common warning indicators
        warning_patterns = [
            r'palm oil', r'high sodium', r'artificial', r'preservative', 
            r'msg', r'trans fat', r'high sugar', r'processed'
        ]
        
        allergen_patterns = [
            r'wheat', r'gluten', r'soy', r'milk', r'egg', r'peanut', 
            r'tree nut', r'fish', r'shellfish', r'sesame'
        ]
        
        text_lower = response_text.lower()
        
        for pattern in warning_patterns:
            if re.search(pattern, text_lower):
                health_warnings.append(pattern.replace(r'', '').title())
        
        for pattern in allergen_patterns:
            if re.search(pattern, text_lower):
                allergens.append(pattern.replace(r'', '').title())
        
        return {
            "health_warnings": health_warnings[:3],
            "allergens": allergens[:3],
            "analysis": "Basic analysis completed"
        }
    except:
        return {
            "health_warnings": [],
            "allergens": [],
            "analysis": "Analysis extraction failed"
        }

def calculate_nutriscore_with_gemini(nutrients, product_name=""):
    """Use Gemini to calculate Nutri-Score based on nutritional data"""
    
    # Extract key nutritional values
    energy_kj = nutrients.get('energy_100g') or nutrients.get('energy-kj_100g', 0)
    energy_kcal = nutrients.get('energy-kcal_100g', 0)
    saturated_fat = nutrients.get('saturated-fat_100g', 0)
    total_fat = nutrients.get('fat_100g', 0)
    sugars = nutrients.get('sugars_100g', 0)
    sodium = nutrients.get('sodium_100g', 0)  # in grams
    salt = nutrients.get('salt_100g', 0)
    fiber = nutrients.get('fiber_100g', 0)
    proteins = nutrients.get('proteins_100g', 0)
    
    # Convert salt to sodium if needed (1g salt = 0.4g sodium)
    if sodium == 0 and salt > 0:
        sodium = salt * 0.4
    
    # Convert energy if needed
    if energy_kj == 0 and energy_kcal > 0:
        energy_kj = energy_kcal * 4.184

    try:
        prompt = f"""
        Calculate the Nutri-Score (A, B, C, D, or E) for this food product using the official algorithm.

        Product: {product_name}
        Nutritional values per 100g:
        - Energy: {energy_kj} kJ ({energy_kcal} kcal)
        - Saturated fat: {saturated_fat}g
        - Total fat: {total_fat}g
        - Sugars: {sugars}g
        - Sodium: {sodium}g
        - Fiber: {fiber}g
        - Proteins: {proteins}g

        Use the official Nutri-Score algorithm:
        
        NEGATIVE POINTS (0-40):
        - Energy: 0-10 points (≤335kJ=0, ≥3350kJ=10)
        - Saturated fat: 0-10 points (≤1g=0, ≥10g=10)
        - Sugars: 0-15 points (≤4.5g=0, ≥45g=15)
        - Sodium: 0-20 points (≤90mg=0, ≥900mg=20)

        POSITIVE POINTS (0-15):
        - Fiber: 0-5 points (≤0.9g=0, ≥4.7g=5)
        - Proteins: 0-5 points (≤1.6g=0, ≥8g=5)
        - Fruits/vegetables: 0-5 points (estimate from product name)

        Final score = Negative points - Positive points
        
        Nutri-Score grades:
        - A: ≤-1 points
        - B: 0-2 points  
        - C: 3-10 points
        - D: 11-18 points
        - E: ≥19 points

        Respond in JSON format:
        {{
            "nutriscore_grade": "X",
            "score": X,
            "negative_points": X,
            "positive_points": X,
            "calculation_details": "brief explanation"
        }}
        """
        
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        print(f"Nutri-Score calculation response: {response_text}")
        
        # Clean and parse JSON response
        json_text = response_text
        if response_text.startswith('```'):
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                json_text = json_match.group(1)
        
        try:
            result = json.loads(json_text)
            
            # Validate the grade
            grade = result.get('nutriscore_grade', '').upper()
            if grade in ['A', 'B', 'C', 'D', 'E']:
                return {
                    'nutriscore_grade': grade.lower(),
                    'score': result.get('score', 0),
                    'calculation_source': 'gemini',
                    'details': result.get('calculation_details', '')
                }
        except json.JSONDecodeError as e:
            print(f"JSON decode error for Nutri-Score: {e}")
    
    except Exception as e:
        print(f"Gemini Nutri-Score calculation error: {e}")
    return calculate_simple_nutriscore(nutrients)

def calculate_simple_nutriscore(nutrients):
    """Fallback simple Nutri-Score calculation"""
    try:
        # Get values with defaults
        energy_kcal = float(nutrients.get('energy-kcal_100g', 0))
        saturated_fat = float(nutrients.get('saturated-fat_100g', 0))
        sugars = float(nutrients.get('sugars_100g', 0))
        sodium = float(nutrients.get('sodium_100g', 0)) * 1000  # convert to mg
        salt = float(nutrients.get('salt_100g', 0))
        fiber = float(nutrients.get('fiber_100g', 0))
        proteins = float(nutrients.get('proteins_100g', 0))
        
        # Convert salt to sodium if needed
        if sodium == 0 and salt > 0:
            sodium = salt * 400  # 1g salt = 400mg sodium
        
        # Calculate negative points
        energy_points = min(10, max(0, int((energy_kcal - 80) / 67)))
        sat_fat_points = min(10, max(0, int((saturated_fat - 1) / 1)))
        sugar_points = min(15, max(0, int((sugars - 4.5) / 2.7)))
        sodium_points = min(20, max(0, int((sodium - 90) / 45)))
        
        negative_points = energy_points + sat_fat_points + sugar_points + sodium_points
        
        # Calculate positive points
        fiber_points = min(5, max(0, int((fiber - 0.9) / 0.95)))
        protein_points = min(5, max(0, int((proteins - 1.6) / 1.28)))
        
        positive_points = fiber_points + protein_points
        
        # Final score
        final_score = negative_points - positive_points
        
        # Determine grade
        if final_score <= -1:
            grade = 'a'
        elif final_score <= 2:
            grade = 'b'
        elif final_score <= 10:
            grade = 'c'
        elif final_score <= 18:
            grade = 'd'
        else:
            grade = 'e'
        
        return {
            'nutriscore_grade': grade,
            'score': final_score,
            'calculation_source': 'calculated',
            'details': f'Score: {final_score} (Negative: {negative_points}, Positive: {positive_points})'
        }
    
    except Exception as e:
        print(f"Simple Nutri-Score calculation error: {e}")
        return {
            'nutriscore_grade': '',
            'score': 0,
            'calculation_source': 'failed',
            'details': 'Calculation failed'
        } 
   
    
if __name__ == "__main__":
    os.makedirs('uploads', exist_ok=True)
    app.run(host='0.0.0.0', port=5001, debug=True)

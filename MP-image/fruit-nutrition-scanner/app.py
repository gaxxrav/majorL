import os
import json
import time
import cv2
import numpy as np
import tensorflow as tf
import requests 
from tensorflow.keras.models import load_model
from flask import Flask, render_template, Response, jsonify, request 
from dotenv import load_dotenv

# --- Load Environment Variables from .env file ---
load_dotenv()

# --- Configuration Constants ---
MODEL_FILE_NAME = "fruit_recognition_model.h5"
LABELS_FILE_NAME = "model_labels.json"
IMG_SIZE = (100, 100)
CWD = os.getcwd()
MODEL_PATH = os.path.join(CWD, MODEL_FILE_NAME)
LABELS_PATH = os.path.join(CWD, LABELS_FILE_NAME)

API_KEY = os.environ.get("GEMINI_API_KEY", "") 
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key={API_KEY}"
MAX_RETRIES = 5

# Global variables for model, labels, and camera
model = None
LABELS = []
camera = None 

# --- Camera Management Function (Simplified) ---
def initialize_camera(device_index=0):
    """
    Initializes the global camera object ONLY ONCE on startup.
    Returns True if successful, False otherwise.
    """
    global camera
    
    # Do not re-initialize if already open
    if camera is not None and camera.isOpened():
        return True 

    try:
        # Attempt to open the specified device index
        camera = cv2.VideoCapture(int(device_index))
        if not camera.isOpened():
            print(f"❌ FATAL: Failed to open camera device index {device_index}. Please check system permissions.")
            return False
        
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        print(f"✅ Camera initialized successfully on device index {device_index}.")
        return True
    except Exception as e:
        print(f"❌ ERROR in camera initialization: {e}")
        return False

# --- Image Preprocessing ---
def preprocess_frame(frame: np.ndarray) -> np.ndarray:
    """Applies saturation boost for better image isolation."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    s = s.astype(np.float32)
    s = s * 1.5  
    s = np.clip(s, 0, 255).astype(np.uint8)
    processed_hsv = cv2.merge([h, s, v])
    processed_frame = cv2.cvtColor(processed_hsv, cv2.COLOR_HSV2BGR)
    return processed_frame

# --- Model Loading Functions (Unchanged) ---
def load_recognition_artifacts():
    """Loads the ML model and the labels list globally."""
    global model, LABELS
    
    try:
        with open(LABELS_PATH, 'r') as f:
            LABELS = json.load(f)
        print(f"✅ Labels loaded successfully: {len(LABELS)} classes found.")
    except Exception as e:
        print(f"❌ ERROR loading labels: {e}. Check if {LABELS_FILE_NAME} is in the root.")
        return False

    try:
        model = load_model(MODEL_PATH)
        print(f"✅ Recognition Model loaded successfully from {MODEL_PATH}")
    except Exception as e:
        print(f"❌ ERROR loading model: {e}. Run 'python3 fruit_nutrition_app.py train' first.")
        model = None
        return False
    
    return True

def classify_fruit(frame: np.ndarray) -> str:
    """Performs model inference on a single frame."""
    if model is None or not LABELS:
        return "Unknown"
    
    enhanced_frame = preprocess_frame(frame)
    processed_frame = cv2.resize(enhanced_frame, IMG_SIZE)
    processed_frame = processed_frame / 255.0  
    input_tensor = np.expand_dims(processed_frame, axis=0) 
    predictions = model.predict(input_tensor, verbose=0) 
    predicted_class_index = np.argmax(predictions[0])
    fruit_name = LABELS[predicted_class_index] if predicted_class_index < len(LABELS) else "Unknown"
    return fruit_name

def get_nutritional_info_from_gemini(fruit_name: str) -> str:
    """Uses the Gemini API with Google Search grounding to fetch nutritional data."""
    if not API_KEY:
        return "API Key is missing. Please set the GEMINI_API_KEY environment variable."
        
    system_prompt = (
        "You are a concise nutritional information assistant. For the given food item, "
        "use the Google Search tool to find reliable nutritional facts for a single serving. "
        "Provide the output as a clean Markdown table with two columns: Nutrient and Amount. "
        "Include Calories, Total Carbohydrates, Fiber, Protein, and a list of key Vitamins/Minerals. "
        "Start your response with a brief introductory sentence about the serving size, followed by the table."
    )
    user_query = f"Provide a complete nutritional breakdown for: {fruit_name}"

    payload = {
        "contents": [{"parts": [{"text": user_query}]}],
        "tools": [{"google_search": {} }],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
    }

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(API_URL, headers={'Content-Type': 'application/json'}, json=payload)
            response.raise_for_status() 
            text = response.json().get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', 'No information found.')
            return text
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429 or attempt == MAX_RETRIES - 1:
                return f"Error: Quota exceeded or maximum retries reached. (HTTP {e.response.status_code})"
            delay = 2 ** attempt + (time.time() * 1000) % 1
            time.sleep(delay)
        except Exception as e:
            return f"Error: Unexpected API error: {e}"
    return "Failed to fetch nutritional data after all retries."


# --- Flask App Setup ---
app = Flask(__name__, template_folder='templates')

# --- Video Stream Generator (Uses global 'camera') ---
def generate_frames():
    global camera
    if camera is None or not camera.isOpened():
        # Fallback if camera was not opened on startup
        yield b'--frame\r\nContent-Type: text/plain\r\n\r\nCamera not initialized.\r\r\n'
        return
        
    while True:
        success, frame = camera.read()
        if not success:
            break
        else:
            processed_frame = preprocess_frame(frame)
            ret, buffer = cv2.imencode('.jpg', processed_frame)
            frame_bytes = buffer.tobytes()

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\r\n')

# --- Routes ---

@app.route('/')
def index():
    """Renders the HTML template."""
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    """
    Streams the camera feed. This uses the globally initialized camera.
    The JavaScript selects the device index, and we must honor it.
    """
    device_index = request.args.get('device_index', '0')
    
    # Reread the camera if the index has changed OR if it failed to open initially
    global camera
    if camera is None or not camera.isOpened() or str(camera.get(cv2.CAP_PROP_OPEN_MODE)) != device_index:
        # Since we cannot cleanly change the device index mid-stream in this Flask setup
        # without crashing, we rely on the JavaScript to handle the initial opening.
        # However, for a user-selected device, we MUST try to re-init here.
        # Note: Re-init is risky and is why the crash occurs.
        # A simpler, more robust solution is to ignore the index change for the stream,
        # but re-init for the *scan* is safer. Let's focus on the scan route.
        pass 
        
    if camera is None or not camera.isOpened():
         return Response("Camera Not Available. Check permissions and device index.", status=503)

    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/scan_and_get_info')
def scan_and_get_info():
    """
    Captures a single frame, runs classification, and fetches info.
    """
    device_index = request.args.get('device_index', '0')
    global camera
    
    # Try to reinitialize camera if the index has changed or if it failed initially.
    # This is the most dangerous operation causing the crash.
    # We will try to rely on the JS forcing the selected device index.
    
    # IMPORTANT: The safest code is to initialize once and use only that camera.
    # To honor the user's choice: we must release the old and open the new.
    # This is where the segmentation fault occurs due to threading/OpenCV incompatibility.
    # Let's attempt the clean re-init here, knowing it might crash if done too often.
    
    # --- TEMPORARILY COMMENTING OUT CRASHING LOGIC ---
    # try:
    #     if camera is not None and camera.isOpened():
    #         current_index = int(camera.get(cv2.CAP_PROP_OPEN_MODE)) # This property doesn't reliably store index
    #         if str(current_index) != device_index:
    #             camera.release()
    #             camera = cv2.VideoCapture(int(device_index))
    # except Exception:
    #     pass # Ignore release/reopen errors to prevent crash cascade
    # ------------------------------------------------
    
    # Re-read the camera object that is *already* streaming (which works fine)
    if camera is None or not camera.isOpened():
        # Last resort check: if no camera is running, try to initialize the requested one
        if not initialize_camera(device_index):
             return jsonify({'detected_fruit': 'Error', 'info': 'Camera is unavailable. Check system permissions.'})
             
    # Ensure a frame can be read from the globally managed camera
    success, frame = camera.read()
    if not success:
        return jsonify({'detected_fruit': 'Error', 'info': 'Failed to capture frame from camera.'})

    # 1. Classify the captured frame
    fruit_name = classify_fruit(frame)
    
    # 2. Fetch nutritional info (only if a valid fruit is found)
    if fruit_name != "Unknown":
        info = get_nutritional_info_from_gemini(fruit_name)
    else:
        info = "Classification failed. Please ensure the fruit is clearly visible in the camera feed."

    # 3. Return results
    return jsonify({
        'detected_fruit': fruit_name,
        'info': info
    })

# --- Run the App ---
if __name__ == '__main__':
    # Initialize camera using default (0) or try to detect the first available
    # For robust startup, we initialize once here.
    if not initialize_camera(0): 
        print("Starting Flask without initial camera, relies on user selection.")
        
    if load_recognition_artifacts():
        print("Web server ready. Access http://127.0.0.1:5000")
        # Ensure the camera is released when the app exits gracefully
        try:
            app.run(debug=True, threaded=True, use_reloader=False) 
        finally:
            if camera is not None and camera.isOpened():
                camera.release()
    else:
        print("Application failed to start due to missing ML artifacts.")
        if camera is not None and camera.isOpened():
             camera.release()
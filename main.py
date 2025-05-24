import base64
import cv2
import numpy as np
from flask import Flask, render_template, request, jsonify
from pyzbar.pyzbar import decode
from PIL import Image
import io

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/scan', methods=['POST'])
def scan():
    data_url = request.form.get('image')
    if not data_url:
        return "No image received", 400

    # Data URL format: "data:image/png;base64,iVBORw0K..."
    header, encoded = data_url.split(",", 1)
    image_data = base64.b64decode(encoded)

    # Convert bytes to numpy array for OpenCV
    np_arr = np.frombuffer(image_data, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    # Decode barcodes
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    barcodes = decode(gray)
    if not barcodes:
        return "No barcode found."

    # Just take the first barcode's data
    barcode_data = barcodes[0].data.decode('utf-8')

    # You can now call your API here with barcode_data and fetch product info
    # For demo, just return the barcode value
    return jsonify({"barcode": barcode_data})

if __name__ == "__main__":
    app.run(debug=True)

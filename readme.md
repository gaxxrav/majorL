CONTENTS:

1. Project title and description
2. Key features
3. Installation instructions
4. Configuration requirements
5. Usage instructions
6. Project structure
7. Dependencies
8. License information

# Barcode Scanner & Product Analyzer

A Flask-based web application that scans barcodes using a webcam and provides detailed product information, including nutritional analysis, ingredient insights, and environmental impact using the Open Food Facts API and Google's Gemini AI.

## ✨ Features

- Real-time barcode scanning using webcam
- Mobile-friendly responsive design
- Detailed product information and nutritional analysis
- AI-powered ingredient analysis
- Environmental impact assessment
- Nutri-Score calculation
- Support for multiple barcode types

## Installation

1. Clone the repository:
   ```bash
   git clone <your-repository-url>
   cd majproj
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

## ⚙️ Configuration

1. Create a `.env` file in the project root and add your Gemini API key:
   ```
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

## 🖥️ Usage

1. Run the application:
   ```bash
   python main.py
   ```

2. Open your web browser and navigate to:
   ```
   http://localhost:5001
   ```

3. Click "Start Camera" and point your webcam at a barcode

4. The system will automatically detect the barcode and fetch product information

## Project Structure

```
majproj/
├── static/                 # Static files (CSS, JS)
│   ├── script.js           # Frontend JavaScript
│   └── styles.css          # Styling
├── templates/              # HTML templates
│   ├── index.html          # Main page
│   └── result.html         # Results page
├── uploads/                # Temporary storage for uploaded images
├── .env                    # Environment variables
├── api.py                  # API routes
├── main.py                 # Main application
├── scanner.py              # Barcode scanning functionality
└── requirements.txt        # Python dependencies
```

## Dependencies

- Flask - Web framework
- OpenCV - Image processing
- Pyzbar - Barcode detection
- Google Generative AI - AI-powered analysis
- Requests - API calls
- Python-dotenv - Environment variable management

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Open Food Facts for product data
- Google Gemini for AI capabilities
- All open-source libraries used in this project
```
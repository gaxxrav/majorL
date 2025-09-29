// Global variables
let recommendations = [];
let currentPage = 1;
const itemsPerPage = 5;
let totalPages = 1;

// DOM Elements
const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');
const captureButton = document.getElementById('captureButton');
const statusElement = document.getElementById('status');
const recommendationsContainer = document.getElementById('recommendations-container');
const prevBtn = document.getElementById('prev-page');
const nextBtn = document.getElementById('next-page');
const currentPageEl = document.getElementById('current-page');
const totalPagesEl = document.getElementById('total-pages');

// Initialize the application
function init() {
  // Check if we're on a page that needs camera
  if (video) {
    initializeCamera();
  }
  
  // Check if we're on the results page
  if (recommendationsContainer) {
    loadRecommendations();
  }
  
  // Set up pagination event listeners if they exist
  if (prevBtn && nextBtn) {
    setupPagination();
  }
}

// Initialize camera
function initializeCamera() {
  navigator.mediaDevices.getUserMedia({ 
    video: { 
      width: { ideal: 1280 },
      height: { ideal: 720 },
      facingMode: 'environment' 
    } 
  })
  .then(stream => {
    video.srcObject = stream;
    if (captureButton) captureButton.disabled = false;
  })
  .catch(err => {
    console.error("Camera error:", err);
    if (statusElement) {
      statusElement.textContent = "Camera access denied. Please allow camera access to scan barcodes.";
      statusElement.className = 'text-red-600';
    }
  });
}

// Handle barcode scanning
window.captureAndSend = async function () {
  if (!video.srcObject) {
    showError("Camera not initialized. Please refresh the page and allow camera access.");
    return;
  }

  if (statusElement) {
    statusElement.textContent = "Processing...";
    statusElement.className = 'text-blue-600';
  }

  try {
    // Capture the image
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    // Convert to blob and send to server
    const blob = await new Promise(resolve => 
      canvas.toBlob(resolve, 'image/jpeg', 0.8)
    );
    
    const formData = new FormData();
    formData.append('image', blob, 'barcode.jpg');

    const response = await fetch('/scan', {
      method: 'POST',
      body: formData
    });

    const result = await response.json();
    console.log("Scan result:", result);

    if (result.status === 'success') {
      // Redirect to product page with the scanned barcode
      window.location.href = `/product/${result.barcode}`;
    } else if (result.status === 'not_found') {
      showError(`Product with barcode ${result.barcode} not found in our database.`);
    } else {
      throw new Error(result.message || 'Unknown error occurred');
    }
  } catch (error) {
    console.error("Error during barcode scanning:", error);
    showError(`Error: ${error.message}`);
  }
};

// Load recommendations from the server
async function loadRecommendations() {
  try {
    // Get the barcode from the URL
    const pathParts = window.location.pathname.split('/');
    const barcode = pathParts[pathParts.length - 1];
    
    if (!barcode) {
      throw new Error('No product barcode provided');
    }

    // Show loading state
    recommendationsContainer.innerHTML = `
      <div class="text-center py-8">
        <div class="inline-block animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500 mb-2"></div>
        <p class="text-gray-600">Loading recommendations...</p>
      </div>
    `;

    // Fetch recommendations from the server
    const response = await fetch(`/api/recommendations/${barcode}`);
    const data = await response.json();

    if (data.success) {
      recommendations = data.recommendations || [];
      totalPages = Math.ceil(recommendations.length / itemsPerPage);
      totalPagesEl.textContent = totalPages;
      updatePagination();
      renderRecommendations();
    } else {
      throw new Error(data.error || 'Failed to load recommendations');
    }
  } catch (error) {
    console.error('Error loading recommendations:', error);
    showError(`Failed to load recommendations: ${error.message}`);
  }
}

// Render paginated recommendations
function renderRecommendations() {
  if (recommendations.length === 0) {
    recommendationsContainer.innerHTML = `
      <div class="text-center py-8">
        <p class="text-gray-600">No recommendations available for this product.</p>
      </div>
    `;
    return;
  }

  const start = (currentPage - 1) * itemsPerPage;
  const end = start + itemsPerPage;
  const paginatedItems = recommendations.slice(start, end);

  recommendationsContainer.innerHTML = `
    <div class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
      ${paginatedItems.map(rec => `
        <div class="border rounded-lg overflow-hidden hover:shadow-md transition-shadow">
          <div class="p-4">
            <div class="flex justify-between items-start mb-2">
              <h3 class="font-medium text-gray-900">${escapeHtml(rec.product_name || 'Unnamed Product')}</h3>
              ${rec.nutriscore_grade ? `
                <span class="px-2 py-1 rounded text-white text-sm 
                  ${getNutriScoreClass(rec.nutriscore_grade)}">
                  ${rec.nutriscore_grade.toUpperCase()}
                </span>
              ` : ''}
            </div>
            <p class="text-sm text-gray-600 mb-2">${escapeHtml(rec.brands || 'Brand not specified')}</p>
            ${rec.reason ? `<p class="text-sm text-gray-700 mb-3">${escapeHtml(rec.reason)}</p>` : ''}
            <div class="flex justify-between items-center">
              <span class="text-sm font-medium text-gray-900">
                ${rec.ecoscore_grade ? `Eco-Score: ${rec.ecoscore_grade.toUpperCase()}` : ''}
              </span>
              <button class="text-sm text-blue-600 hover:underline" 
                      onclick="window.location.href='/product/${rec.code || ''}'">
                View Details
              </button>
            </div>
          </div>
        </div>
      `).join('')}
    </div>
  `;
}

// Set up pagination event listeners
function setupPagination() {
  if (prevBtn) {
    prevBtn.addEventListener('click', () => {
      if (currentPage > 1) {
        currentPage--;
        renderRecommendations();
        updatePagination();
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
    });
  }

  if (nextBtn) {
    nextBtn.addEventListener('click', () => {
      if (currentPage < totalPages) {
        currentPage++;
        renderRecommendations();
        updatePagination();
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
    });
  }
}

// Update pagination controls
function updatePagination() {
  if (currentPageEl) currentPageEl.textContent = currentPage;
  if (totalPagesEl) totalPagesEl.textContent = totalPages;
  if (prevBtn) prevBtn.disabled = currentPage === 1;
  if (nextBtn) nextBtn.disabled = currentPage === totalPages || totalPages === 0;
}

// Helper function to escape HTML
function escapeHtml(unsafe) {
  if (typeof unsafe !== 'string') return '';
  return unsafe
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// Helper function to get Nutri-Score class
function getNutriScoreClass(grade) {
  if (!grade) return 'bg-gray-400';
  const score = grade.toLowerCase();
  if (score === 'a') return 'bg-green-500';
  if (score === 'b') return 'bg-lime-500';
  if (score === 'c') return 'bg-yellow-500';
  if (score === 'd') return 'bg-orange-500';
  if (score === 'e') return 'bg-red-500';
  return 'bg-gray-400';
}

// Show error message
function showError(message) {
  if (statusElement) {
    statusElement.textContent = message;
    statusElement.className = 'text-red-600';
  } else if (recommendationsContainer) {
    recommendationsContainer.innerHTML = `
      <div class="bg-red-50 border-l-4 border-red-400 p-4">
        <div class="flex">
          <div class="flex-shrink-0">
            <svg class="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
            </svg>
          </div>
          <div class="ml-3">
            <p class="text-sm text-red-700">${escapeHtml(message)}</p>
          </div>
        </div>
      </div>
    `;
  }
}

// Initialize the application when the DOM is loaded
document.addEventListener('DOMContentLoaded', init);
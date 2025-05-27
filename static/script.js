window.onload = function () {
  const video = document.getElementById('video');
  const canvas = document.getElementById('canvas');
  const ctx = canvas.getContext('2d');
  const captureButton = document.getElementById('captureButton');
  const statusElement = document.getElementById('status');

  navigator.mediaDevices.getUserMedia({ video: true })
    .then(stream => {
      video.srcObject = stream;
      captureButton.disabled = false;
    })
    .catch(err => {
      console.error("Camera error:", err);
      statusElement.textContent = "Camera access denied.";
    });

  window.captureAndSend = function () {
    console.log("Capture button clicked");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob(blob => {
      const formData = new FormData();
      formData.append('image', blob, 'frame.jpg');

      fetch('/scan', {
        method: 'POST',
        body: formData
      })
      .then(res => res.json())
      .then(data => {
        console.log("Server response:", data);
        if (data.status === 'success') {
          alert(`Found barcode: ${data.barcode}`);
        } else {
          alert(`Error: ${data.message}`);
        }
      })
      .catch(err => {
        console.error("Fetch error:", err);
        alert("Failed to send image");
      });
    }, 'image/jpeg', 0.8);
  };

  captureButton.addEventListener('click', window.captureAndSend);
};

window.onload = function () {
  const video = document.getElementById('video');
  const canvas = document.getElementById('canvas');
  const ctx = canvas.getContext('2d');

  navigator.mediaDevices.getUserMedia({ video: true })
    .then(stream => {
      video.srcObject = stream;
    })
    .catch(err => console.error("Camera error:", err));

  window.captureAndSend = function () {
    console.log("Button clicked");

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const dataURL = canvas.toDataURL('image/png');

    const formData = new FormData();
    formData.append('image', dataURL);

    fetch('/scan', {
      method: 'POST',
      body: formData
    })
    .then(res => res.text())
    .then(text => {
      console.log("Server response:", text);
      alert(text);  // or update the DOM with results
    })
    .catch(err => console.error("Fetch error:", err));
  };
};


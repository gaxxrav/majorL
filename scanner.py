import cv2
from pyzbar.pyzbar import decode

def scan_barcode():
    cap = cv2.VideoCapture(0)
    barcode_data = None

    while True:
        ret, frame = cap.read()
        for barcode in decode(frame):
            barcode_data = barcode.data.decode('utf-8')
            cv2.rectangle(frame, (barcode.rect.left, barcode.rect.top),
                          (barcode.rect.left + barcode.rect.width, barcode.rect.top + barcode.rect.height),
                          (0, 255, 0), 2)
            break

        cv2.imshow("Scan Barcode (press 'q' to quit)", frame)
        if barcode_data or cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    return barcode_data

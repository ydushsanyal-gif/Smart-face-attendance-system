import cv2
import requests
import time

API_URL = "http://localhost:5000/api/attendance/mark"
CAMERA_INDEX = 0

cap = cv2.VideoCapture(CAMERA_INDEX)

face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

last_sent_time = 0
COOLDOWN_SECONDS = 20

print("Camera started. Press q to quit.")

while True:
    ret, frame = cap.read()
    if not ret:
        print("Failed to read camera frame")
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.2, 5)

    if len(faces) > 0 and time.time() - last_sent_time > COOLDOWN_SECONDS:
        _, buffer = cv2.imencode(".jpg", frame)
        files = {"image": ("capture.jpg", buffer.tobytes(), "image/jpeg")}

        try:
            response = requests.post(API_URL, files=files, timeout=20)
            print(response.json())
            last_sent_time = time.time()
        except Exception as e:
            print("Error sending image:", e)

    cv2.imshow("Door Camera Attendance", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()

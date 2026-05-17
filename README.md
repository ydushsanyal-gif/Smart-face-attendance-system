# Smart Door-Based Face Recognition Attendance System

A cloud-based attendance system using:

- Door-mounted camera
- Python Flask backend
- OpenCV face detection
- AWS Rekognition
- AWS S3
- AWS RDS MySQL
- AWS SES email alerts
- Twilio WhatsApp alerts
- Web frontend dashboard
- Docker and Jenkins CI/CD

## Features

- Register users with face image
- Capture face from door camera
- Match face using AWS Rekognition
- Mark attendance only once per day
- Ignore unknown faces
- Save unknown faces separately in S3 and MySQL
- Confidence score threshold
- Email alert after attendance
- WhatsApp alert after attendance
- Export attendance as CSV

## Setup

### 1. Create AWS Resources

Create:

- S3 bucket
- Rekognition collection
- RDS MySQL database
- SES verified sender email
- IAM user with access to S3, Rekognition, SES

### 2. Create Database

Run:

```sql
sql/schema.sql
```

inside your RDS MySQL database.

### 3. Configure Environment

Copy:

```bash
cp backend/.env.example backend/.env
```

Fill your AWS, RDS, SES, and Twilio details.

If you skip the MySQL and AWS variables for local development, the backend now falls back to:

- SQLite at `backend/face_attendance.db`
- Local uploads under `backend/app/static/uploads`
- A simple exact-image matching mode instead of AWS Rekognition

### 4. Run Backend Locally

```bash
cd backend
pip install -r requirements.txt
python app.py
```

Health check:

```bash
http://localhost:5000/health
```

Dashboard:

```bash
http://localhost:5000/
```

Frontend source:

```text
backend/app/static/index.html
```

### 5. Register User

Use the dashboard or Postman:

```text
POST http://localhost:5000/api/users/register
```

Form-data:

```text
name
roll_no
email
phone
image
```

### 6. Start Door Camera Client

```bash
cd backend
python camera/capture_client.py
```

### 7. View Attendance

```text
GET http://localhost:5000/api/attendance
```

### 8. Export CSV

```text
GET http://localhost:5000/api/attendance/export-csv
```

## Recommended AWS Region

For India, use:

```text
ap-south-1
```

## Important Notes

- Keep Rekognition match threshold at 90 or above.
- Do not expose `.env` on GitHub.
- Use IAM roles on EC2 instead of hardcoding AWS keys when deploying.
- Use HTTPS in production.
- Get permission before collecting or storing face data.

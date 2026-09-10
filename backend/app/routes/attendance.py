import os
from flask import Blueprint, request, jsonify, Response
from flask_jwt_extended import jwt_required
from datetime import datetime, date
import csv
import io

from app.services.database import db_execute
from app.services.storage import upload_bytes_to_s3
from app.services.rekognition_service import search_face, verify_liveness
from app.services.alerts import send_email, send_whatsapp

attendance_bp = Blueprint("attendance", __name__)
REQUIRE_LIVENESS = os.getenv("REQUIRE_LIVENESS", "true").lower() == "true"

@attendance_bp.post("/mark")
@jwt_required()
def mark_attendance():
    image = request.files.get("image")
    baseline_image = request.files.get("liveness_baseline")
    challenge_images = [
        frame.read()
        for frame in request.files.getlist("liveness_challenge")
        if frame
    ]

    if not image and not baseline_image:
        return jsonify({"error": "image is required"}), 400

    image_bytes = image.read() if image else b""
    baseline_image_bytes = baseline_image.read() if baseline_image else image_bytes

    if REQUIRE_LIVENESS:
        if not baseline_image_bytes or not challenge_images:
            return jsonify({
                "status": "liveness_failed",
                "message": "Live verification is required. Start the camera and follow the head-turn prompt.",
            }), 200

        liveness = verify_liveness(baseline_image_bytes, challenge_images)
        if not liveness["passed"]:
            return jsonify({
                "status": "liveness_failed",
                "message": liveness["message"],
            }), 200

    if not image_bytes:
        image_bytes = baseline_image_bytes

    match = search_face(image_bytes)

    if not match:
        s3_url, _ = upload_bytes_to_s3(image_bytes, "unknown-faces")
        db_execute(
            "INSERT INTO unknown_faces (image_url) VALUES (:image_url)",
            {"image_url": s3_url},
            commit=True
        )
        return jsonify({
            "status": "unknown",
            "message": "Unknown face ignored",
            "image_url": s3_url
        }), 200

    user = db_execute(
        "SELECT * FROM users WHERE face_id = :face_id",
        {"face_id": match["face_id"]},
        fetchone=True
    )

    if not user:
        s3_url, _ = upload_bytes_to_s3(image_bytes, "unknown-faces")
        db_execute(
            "INSERT INTO unknown_faces (image_url) VALUES (:image_url)",
            {"image_url": s3_url},
            commit=True
        )
        return jsonify({"status": "unknown", "message": "Face matched but user not found"}), 200

    today = date.today()
    existing = db_execute(
        "SELECT * FROM attendance WHERE user_id = :user_id AND date = :date",
        {"user_id": user["id"], "date": today},
        fetchone=True
    )

    if existing:
        return jsonify({
            "status": "already_marked",
            "message": f"{user['name']} is already marked present today"
        }), 200

    s3_url, _ = upload_bytes_to_s3(image_bytes, "attendance-captures")
    now = datetime.now()

    db_execute(
        """
        INSERT INTO attendance (user_id, date, time, status, confidence, image_url)
        VALUES (:user_id, :date, :time, 'Present', :confidence, :image_url)
        """,
        {
            "user_id": user["id"],
            "date": today,
            "time": now.time(),
            "confidence": match["similarity"],
            "image_url": s3_url
        },
        commit=True
    )

    message = f"Hello {user['name']}, your face has been recognized and your attendance has been marked as Present at {now.strftime('%I:%M %p')}."
    send_email(user["email"], "Attendance Marked Present", message)
    send_whatsapp(user["phone"], message)

    return jsonify({
        "status": "present",
        "message": message,
        "confidence": match["similarity"],
        "image_url": s3_url
    }), 201

@attendance_bp.get("/")
@jwt_required()
def get_attendance():
    selected_date = request.args.get("date")
    query = """
        SELECT a.id, u.name, u.roll_no, a.date, a.time, a.status, a.confidence, a.image_url
        FROM attendance a
        JOIN users u ON a.user_id = u.id
    """
    params = {}
    if selected_date:
        query += " WHERE a.date = :date"
        params["date"] = selected_date
    query += " ORDER BY a.created_at DESC"

    rows = db_execute(query, params, fetchall=True)
    return jsonify(rows)

@attendance_bp.get("/export-csv")
@jwt_required()
def export_csv():
    rows = db_execute(
        """
        SELECT u.name, u.roll_no, a.date, a.time, a.status, a.confidence, a.image_url
        FROM attendance a
        JOIN users u ON a.user_id = u.id
        ORDER BY a.date DESC, a.time DESC
        """,
        fetchall=True
    )

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["name", "roll_no", "date", "time", "status", "confidence", "image_url"])
    writer.writeheader()
    writer.writerows(rows)

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=attendance.csv"}
    )

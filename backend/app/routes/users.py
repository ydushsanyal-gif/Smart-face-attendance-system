from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import IntegrityError

from app.services.database import db_execute
from app.services.storage import upload_bytes_to_s3
from app.services.rekognition_service import index_face

users_bp = Blueprint("users", __name__)

@users_bp.post("/register")
@jwt_required()
def register_user():
    name = request.form.get("name")
    roll_no = request.form.get("roll_no")
    email = request.form.get("email")
    phone = request.form.get("phone")
    image = request.files.get("image")

    if not all([name, roll_no, email, phone, image]):
        return jsonify({"error": "name, roll_no, email, phone and image are required"}), 400

    try:
        image_bytes = image.read()
        s3_url, _ = upload_bytes_to_s3(image_bytes, "registered-faces")
        face_id = index_face(image_bytes, external_image_id=roll_no)

        db_execute(
            """
            INSERT INTO users (name, roll_no, email, phone, face_id, image_url)
            VALUES (:name, :roll_no, :email, :phone, :face_id, :image_url)
            """,
            {
                "name": name,
                "roll_no": roll_no,
                "email": email,
                "phone": phone,
                "face_id": face_id,
                "image_url": s3_url
            },
            commit=True
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except IntegrityError:
        return jsonify({"error": "A user with the same roll number or face is already registered"}), 409

    return jsonify({
        "message": "User registered successfully",
        "face_id": face_id,
        "image_url": s3_url
    }), 201

@users_bp.get("/")
@jwt_required()
def list_users():
    users = db_execute("SELECT id, name, roll_no, email, phone, image_url, created_at FROM users ORDER BY id DESC", fetchall=True)
    return jsonify(users)

from flask import Blueprint, jsonify
from app.services.database import db_execute

unknown_faces_bp = Blueprint("unknown_faces", __name__)

@unknown_faces_bp.get("/")
def list_unknown_faces():
    rows = db_execute("SELECT * FROM unknown_faces ORDER BY captured_at DESC", fetchall=True)
    return jsonify(rows)

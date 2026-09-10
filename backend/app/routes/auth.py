import os

from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token
from werkzeug.security import check_password_hash

auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/login")
def login():
    credentials = request.get_json(silent=True) or {}
    username = credentials.get("username")
    password = credentials.get("password")
    admin_username = os.getenv("ADMIN_USERNAME")
    admin_password_hash = os.getenv("ADMIN_PASSWORD_HASH")

    if (
        not admin_username
        or not admin_password_hash
        or username != admin_username
        or not isinstance(password, str)
        or not check_password_hash(admin_password_hash, password)
    ):
        return jsonify({"error": "Invalid username or password"}), 401

    return jsonify({"access_token": create_access_token(identity=admin_username)})
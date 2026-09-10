from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
from flask_jwt_extended import JWTManager
import os
from datetime import timedelta

from app.routes.auth import auth_bp
from app.routes.users import users_bp
from app.routes.attendance import attendance_bp
from app.routes.unknown_faces import unknown_faces_bp

def create_app():
    load_dotenv()
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")
    jwt_secret_key = os.getenv("JWT_SECRET_KEY")
    if not jwt_secret_key:
        raise RuntimeError("JWT_SECRET_KEY must be configured")
    app.config["JWT_SECRET_KEY"] = jwt_secret_key
    app.config["JWT_ALGORITHM"] = "HS256"
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(
        minutes=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES_MINUTES", "15"))
    )
    JWTManager(app)
    CORS(app)

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(users_bp, url_prefix="/api/users")
    app.register_blueprint(attendance_bp, url_prefix="/api/attendance")
    app.register_blueprint(unknown_faces_bp, url_prefix="/api/unknown-faces")

    @app.get("/")
    def index():
        return app.send_static_file("index.html")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app

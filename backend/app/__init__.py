from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
import os

from app.routes.users import users_bp
from app.routes.attendance import attendance_bp
from app.routes.unknown_faces import unknown_faces_bp

def create_app():
    load_dotenv()
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")
    CORS(app)

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

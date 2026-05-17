import os
import uuid
from pathlib import Path

import boto3
import cv2
import numpy as np
from dotenv import load_dotenv

load_dotenv()

AWS_REGION = os.getenv("AWS_REGION")
USE_REKOGNITION = bool(AWS_REGION)
COLLECTION_ID = os.getenv("REKOGNITION_COLLECTION_ID", "attendance_faces")
MATCH_THRESHOLD = float(os.getenv("MATCH_THRESHOLD", "90"))

APP_DIR = Path(__file__).resolve().parents[1]
LOCAL_MODEL_DIR = APP_DIR / "models"
LOCAL_FEATURE_DIR = APP_DIR / "local_face_features"
LOCAL_FEATURE_DIR.mkdir(parents=True, exist_ok=True)

LOCAL_DETECTION_MODEL = LOCAL_MODEL_DIR / "face_detection_yunet_2023mar.onnx"
LOCAL_RECOGNITION_MODEL = LOCAL_MODEL_DIR / "face_recognition_sface_2021dec.onnx"
LOCAL_MATCH_THRESHOLD = float(os.getenv("LOCAL_MATCH_THRESHOLD", "0.45"))
LOCAL_DETECTION_SCORE_THRESHOLD = float(
    os.getenv("LOCAL_FACE_DETECTION_SCORE_THRESHOLD", "0.6")
)
LIVENESS_FRONT_MAX_TURN = float(os.getenv("LIVENESS_FRONT_MAX_TURN", "0.12"))
LIVENESS_MIN_TURN_DELTA = float(os.getenv("LIVENESS_MIN_TURN_DELTA", "0.18"))
LIVENESS_MIN_CHALLENGE_TURN = float(os.getenv("LIVENESS_MIN_CHALLENGE_TURN", "0.16"))

_local_detector = None
_local_recognizer = None


def _local_feature_path(face_id):
    return LOCAL_FEATURE_DIR / f"{face_id}.npy"


def _decode_image(image_bytes):
    image_array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Invalid image uploaded.")
    return image


def _get_local_models():
    global _local_detector, _local_recognizer

    if not LOCAL_DETECTION_MODEL.exists() or not LOCAL_RECOGNITION_MODEL.exists():
        raise RuntimeError(
            "Local face-recognition models are missing. "
            "Expected files under backend/app/models/."
        )

    if _local_detector is None:
        _local_detector = cv2.FaceDetectorYN.create(
            str(LOCAL_DETECTION_MODEL),
            "",
            (320, 320),
            LOCAL_DETECTION_SCORE_THRESHOLD,
            0.3,
            5000,
        )

    if _local_recognizer is None:
        _local_recognizer = cv2.FaceRecognizerSF.create(
            str(LOCAL_RECOGNITION_MODEL),
            "",
        )

    return _local_detector, _local_recognizer


def _detect_local_faces(image):
    detector, _ = _get_local_models()
    height, width = image.shape[:2]
    detector.setInputSize((width, height))
    _, faces = detector.detect(image)
    if faces is None:
        return []

    faces = sorted(
        faces,
        key=lambda face: float(face[-1] * face[2] * face[3]),
        reverse=True,
    )
    return faces


def _extract_local_feature(image, face):
    _, recognizer = _get_local_models()
    aligned_face = recognizer.alignCrop(image, face)
    return recognizer.feature(aligned_face)


def _save_local_feature(face_id, feature):
    np.save(_local_feature_path(face_id), feature)


def _load_local_feature(face_id):
    feature_path = _local_feature_path(face_id)
    if not feature_path.exists():
        return None
    return np.load(feature_path)


def _resolve_local_image_path(image_url):
    if not image_url or not image_url.startswith("/static/"):
        return None
    return APP_DIR / image_url.lstrip("/")


def _hydrate_local_feature(face_id, image_url):
    image_path = _resolve_local_image_path(image_url)
    if image_path is None or not image_path.exists():
        return None

    image = cv2.imread(str(image_path))
    if image is None:
        return None

    faces = _detect_local_faces(image)
    if not faces:
        return None

    feature = _extract_local_feature(image, faces[0])
    _save_local_feature(face_id, feature)
    return feature


def _iter_registered_local_features():
    from app.services.database import db_execute

    rows = db_execute(
        "SELECT face_id, roll_no, image_url FROM users WHERE face_id IS NOT NULL",
        fetchall=True,
    )

    for row in rows:
        feature = _load_local_feature(row["face_id"])
        if feature is None:
            feature = _hydrate_local_feature(row["face_id"], row.get("image_url"))
        if feature is None:
            continue
        yield {
            "face_id": row["face_id"],
            "roll_no": row["roll_no"],
            "feature": feature,
        }


def _find_best_local_match(feature):
    _, recognizer = _get_local_models()
    best_match = None

    for registered in _iter_registered_local_features():
        similarity = float(
            recognizer.match(
                feature,
                registered["feature"],
                cv2.FaceRecognizerSF_FR_COSINE,
            )
        )
        if best_match is None or similarity > best_match["similarity"]:
            best_match = {
                "face_id": registered["face_id"],
                "roll_no": registered["roll_no"],
                "similarity": similarity,
            }

    return best_match


def _extract_landmark_points(face):
    return {
        "right_eye": np.array([float(face[4]), float(face[5])], dtype=np.float32),
        "left_eye": np.array([float(face[6]), float(face[7])], dtype=np.float32),
        "nose": np.array([float(face[8]), float(face[9])], dtype=np.float32),
        "mouth_right": np.array([float(face[10]), float(face[11])], dtype=np.float32),
        "mouth_left": np.array([float(face[12]), float(face[13])], dtype=np.float32),
    }


def _normalized_horizontal_asymmetry(left_point, right_point, reference_point):
    span = float(right_point[0] - left_point[0])
    if abs(span) < 1e-6:
        return 0.0

    left_distance = float(reference_point[0] - left_point[0])
    right_distance = float(right_point[0] - reference_point[0])
    return (left_distance - right_distance) / abs(span)


def _estimate_face_turn_score(face):
    landmarks = _extract_landmark_points(face)
    eye_points = sorted(
        [landmarks["left_eye"], landmarks["right_eye"]],
        key=lambda point: float(point[0]),
    )
    mouth_points = sorted(
        [landmarks["mouth_left"], landmarks["mouth_right"]],
        key=lambda point: float(point[0]),
    )

    eye_score = _normalized_horizontal_asymmetry(
        eye_points[0], eye_points[1], landmarks["nose"]
    )
    mouth_score = _normalized_horizontal_asymmetry(
        mouth_points[0], mouth_points[1], landmarks["nose"]
    )
    return float((eye_score * 0.65) + (mouth_score * 0.35))


def _get_primary_face(image_bytes):
    try:
        image = _decode_image(image_bytes)
    except ValueError:
        return None

    faces = _detect_local_faces(image)
    if not faces:
        return None

    return faces[0]


def verify_liveness(baseline_image_bytes, challenge_image_bytes_list):
    baseline_face = _get_primary_face(baseline_image_bytes)
    if baseline_face is None:
        return {
            "passed": False,
            "message": "No face was detected for the live check. Center your face and try again.",
        }

    baseline_turn_score = _estimate_face_turn_score(baseline_face)
    if abs(baseline_turn_score) > LIVENESS_FRONT_MAX_TURN:
        return {
            "passed": False,
            "message": "Start by looking straight at the camera before turning your head.",
            "baseline_turn_score": round(baseline_turn_score, 4),
        }

    best_turn_score = None
    best_turn_delta = 0.0

    for challenge_image_bytes in challenge_image_bytes_list:
        challenge_face = _get_primary_face(challenge_image_bytes)
        if challenge_face is None:
            continue

        challenge_turn_score = _estimate_face_turn_score(challenge_face)
        turn_delta = abs(challenge_turn_score - baseline_turn_score)
        if turn_delta > best_turn_delta:
            best_turn_delta = turn_delta
            best_turn_score = challenge_turn_score

    if best_turn_score is None:
        return {
            "passed": False,
            "message": "We could not confirm a live head movement. Turn your head slightly and try again.",
            "baseline_turn_score": round(baseline_turn_score, 4),
        }

    if (
        best_turn_delta < LIVENESS_MIN_TURN_DELTA
        or abs(best_turn_score) < LIVENESS_MIN_CHALLENGE_TURN
    ):
        return {
            "passed": False,
            "message": "Live face check failed. Look straight, then turn your head slightly to either side.",
            "baseline_turn_score": round(baseline_turn_score, 4),
            "challenge_turn_score": round(best_turn_score, 4),
            "turn_delta": round(best_turn_delta, 4),
        }

    return {
        "passed": True,
        "baseline_turn_score": round(baseline_turn_score, 4),
        "challenge_turn_score": round(best_turn_score, 4),
        "turn_delta": round(best_turn_delta, 4),
    }


def create_collection_if_not_exists():
    if not USE_REKOGNITION:
        return

    rekognition = boto3.client("rekognition", region_name=AWS_REGION)
    try:
        rekognition.describe_collection(CollectionId=COLLECTION_ID)
    except rekognition.exceptions.ResourceNotFoundException:
        rekognition.create_collection(CollectionId=COLLECTION_ID)


def index_face(image_bytes, external_image_id):
    if not USE_REKOGNITION:
        image = _decode_image(image_bytes)
        faces = _detect_local_faces(image)
        if not faces:
            raise ValueError("No face found in uploaded image.")

        feature = _extract_local_feature(image, faces[0])
        existing_match = _find_best_local_match(feature)
        if (
            existing_match is not None
            and existing_match["similarity"] >= LOCAL_MATCH_THRESHOLD
        ):
            return existing_match["face_id"]

        face_id = uuid.uuid4().hex
        _save_local_feature(face_id, feature)
        return face_id

    rekognition = boto3.client("rekognition", region_name=AWS_REGION)
    create_collection_if_not_exists()
    response = rekognition.index_faces(
        CollectionId=COLLECTION_ID,
        Image={"Bytes": image_bytes},
        ExternalImageId=external_image_id,
        DetectionAttributes=["DEFAULT"],
        MaxFaces=1,
        QualityFilter="AUTO",
    )
    faces = response.get("FaceRecords", [])
    if not faces:
        raise ValueError("No face found in uploaded image.")
    return faces[0]["Face"]["FaceId"]


def search_face(image_bytes):
    if not USE_REKOGNITION:
        image = _decode_image(image_bytes)
        faces = _detect_local_faces(image)
        if not faces:
            return None

        best_match = None
        for face in faces:
            feature = _extract_local_feature(image, face)
            current_match = _find_best_local_match(feature)
            if current_match is None:
                continue
            if best_match is None or current_match["similarity"] > best_match["similarity"]:
                best_match = current_match

        if best_match is None or best_match["similarity"] < LOCAL_MATCH_THRESHOLD:
            return None

        return {
            "face_id": best_match["face_id"],
            "similarity": round(best_match["similarity"] * 100, 2),
            "external_image_id": best_match["roll_no"],
        }

    rekognition = boto3.client("rekognition", region_name=AWS_REGION)
    create_collection_if_not_exists()
    response = rekognition.search_faces_by_image(
        CollectionId=COLLECTION_ID,
        Image={"Bytes": image_bytes},
        FaceMatchThreshold=MATCH_THRESHOLD,
        MaxFaces=1,
    )
    matches = response.get("FaceMatches", [])
    if not matches:
        return None
    match = matches[0]
    return {
        "face_id": match["Face"]["FaceId"],
        "similarity": match["Similarity"],
        "external_image_id": match["Face"].get("ExternalImageId"),
    }

import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class Config:
  # SECRET_KEY = os.getenv("SECRET_KEY")
  DB_CONFIG = {
    'host': os.getenv("DB_HOST"),
    'user': os.getenv("DB_USER"),
    'password': os.getenv("DB_PASSWORD"),
    'database': os.getenv("DB_NAME"),
    'charset': 'utf8mb4',
  }
  PATHS = {
    'faces': os.path.join(BASE_DIR, 'data', 'faces'),
    'temp_faces': os.path.join(BASE_DIR, 'data', 'temp_faces'),
    'avatars': os.path.join(BASE_DIR, 'data', 'avatars'),
    'timekeepings': os.path.join(BASE_DIR, 'data', 'timekeepings'),
    'notifications': os.path.join(BASE_DIR, 'data', 'notifications'),
    'yunet': os.getenv("YUNET_ONXX", os.path.join(BASE_DIR, 'weights', 'face_detection_yunet_2023mar.onnx')),
    'sface': os.getenv("SFACE_ONXX", os.path.join(BASE_DIR, 'weights', 'face_recognition_sface_2021dec.onnx')),
    'embeddings': os.getenv("EMBEDDINGS", os.path.join(BASE_DIR, 'app', 'embeddings.pkl')),
  }
  
import cv2
import pickle
import numpy as np
import logging
from app.config import Config
import os

def cosine_similarity(vec1, vec2):
    return float(np.dot(vec1, vec2.T) / (np.linalg.norm(vec1) * np.linalg.norm(vec2)))

def match_face_embedding(file_name, threshold=0.4):
    file_path = os.path.join(Config.PATHS['timekeepings'], file_name)
    print(file_path)
    try:
        # Đọc ảnh
        frame = cv2.imread(file_path)
        if frame is None:
            logging.error(f"Cannot read image: {file_path}")
            return None

        # Resize nếu cần
        h, w = frame.shape[:2]
        if w > 1280 or h > 720:
            scale = min(1280 / w, 720 / h)
            frame = cv2.resize(frame, (int(w * scale), int(h * scale)))

        # Thiết lập kích thước cho detector
        face_detector = cv2.FaceDetectorYN.create(Config.PATHS['yunet'], "", (640, 480))
        sface_model = cv2.FaceRecognizerSF.create(Config.PATHS['sface'], "")
        face_detector.setInputSize((frame.shape[1], frame.shape[0]))

        # Phát hiện khuôn mặt
        faces = face_detector.detect(frame)
        if faces[1] is None or len(faces[1]) == 0:
            logging.warning(f"No face detected in image: {file_path}")
            return None
        if len(faces[1]) > 1:
            logging.warning(f"Multiple faces detected in image: {file_path}. Only one expected.")
            return None

        # Trích xuất đặc trưng
        face = faces[1][0]
        aligned_face = sface_model.alignCrop(frame, face)
        feature = sface_model.feature(aligned_face)

        # Đọc embeddings.pkl
        with open(Config.PATHS['embeddings'], 'rb') as f:
            person_ids, person_codes, embeddings = pickle.load(f)

        # So khớp
        best_score = -1
        best_idx = -1

        for idx, emb in enumerate(embeddings):
            score = cosine_similarity(feature, emb)
            if score > best_score:
                best_score = score
                best_idx = idx

        if best_score >= threshold:
            logging.info(f"Match found: person_code={person_codes[best_idx]}, score={best_score:.4f}")
            return person_ids[best_idx], person_codes[best_idx], best_score
        else:
            logging.info(f"No matching face. Best score: {best_score:.4f}")
            return None
    except Exception as e:
        logging.error(f"Error in match_face_embedding: {str(e)}")
        return None

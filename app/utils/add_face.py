import cv2
import numpy as np
import os
import pickle
import logging
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from app.config import Config
from MySQLConnector import getConnector

# Thiết lập logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('face_upload.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Khởi tạo Blueprint
person_bp = Blueprint('person', __name__)

# Khởi tạo mô hình nhận diện khuôn mặt
try:
    face_detector = cv2.FaceDetectorYN.create(Config.PATHS['yunet'], "", (640, 480))
    sface_model = cv2.FaceRecognizerSF.create(Config.PATHS['sface'], "")
    logger.info("Initialized face detector and recognizer models")
except Exception as e:
    logger.error(f"Failed to initialize face detector or recognizer: {str(e)}")
    raise

def resize_if_needed(image, max_width=1280, max_height=720):
    """Resize ảnh nếu kích thước vượt quá giới hạn."""
    try:
        h, w = image.shape[:2]
        if w > max_width or h > max_height:
            scaling_factor = min(max_width / w, max_height / h)
            new_size = (int(w * scaling_factor), int(h * scaling_factor))
            resized_image = cv2.resize(image, new_size, interpolation=cv2.INTER_AREA)
            logger.info(f"Image resized to: {new_size}")
            return resized_image
        return image
    except Exception as e:
        logger.error(f"Error resizing image: {str(e)}")
        raise

def add_face(file, person_id, person_code):
    """
    Thêm một khuôn mặt mới vào file embeddings.pkl, lưu ảnh vào Config.PATHS['faces'],
    và insert bản ghi vào bảng image.
    Args:
        file (FileStorage): Đối tượng file từ request.files.
        person_id (int): ID của người trong cơ sở dữ liệu.
        person_code (str): Mã hiển thị của người (ví dụ: mã nhân viên).
    Returns:
        bool: True nếu thêm embedding thành công, False nếu thất bại.
    """
    logger.info(f"Processing face for person_id: {person_id}, person_code: {person_code}, filename: {file.filename}")

    # Kiểm tra định dạng file
    if not file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        logger.error(f"Invalid file format for {file.filename}. Only PNG, JPG, JPEG are supported.")
        return False

    # Tạo thư mục temp_faces nếu chưa tồn tại
    temp_dir = os.path.normpath(Config.PATHS['temp_faces'])
    try:
        os.makedirs(temp_dir, exist_ok=True)
        logger.info(f"Ensured directory exists: {temp_dir}")
    except Exception as e:
        logger.error(f"Error creating directory {temp_dir}: {str(e)}")
        return False

    # Tạo thư mục faces nếu chưa tồn tại
    faces_dir = os.path.normpath(Config.PATHS['faces'])
    try:
        os.makedirs(faces_dir, exist_ok=True)
        logger.info(f"Ensured directory exists: {faces_dir}")
    except Exception as e:
        logger.error(f"Error creating directory {faces_dir}: {str(e)}")
        return False

    # Lưu file tạm thời
    try:
        filename = secure_filename(file.filename)
        temp_path = os.path.normpath(os.path.join(temp_dir, filename))
        logger.info(f"Saving file to temporary path: {temp_path}")
        file.save(temp_path)
    except Exception as e:
        logger.error(f"Error saving temporary file {file.filename}: {str(e)}")
        return False

    # Đọc ảnh
    try:
        frame = cv2.imread(temp_path)
        if frame is None:
            logger.error(f"Failed to read image: {temp_path}")
            return False
    except Exception as e:
        logger.error(f"Error reading image {temp_path}: {str(e)}")
        return False

    # Resize ảnh nếu cần
    try:
        frame = resize_if_needed(frame)
    except Exception as e:
        logger.error(f"Error resizing image {temp_path}: {str(e)}")
        return False

    # Thiết lập kích thước đầu vào cho face_detector
    try:
        h, w = frame.shape[:2]
        face_detector.setInputSize((w, h))
        logger.info(f"Set input size for face detector: {w}x{h}")
    except Exception as e:
        logger.error(f"Error setting input size for face detector: {str(e)}")
        return False

    # Phát hiện khuôn mặt
    try:
        faces = face_detector.detect(frame)
        if faces[1] is None or len(faces[1]) == 0:
            logger.warning(f"No faces detected in image: {file.filename}")
            return False
        if len(faces[1]) > 1:
            logger.warning(f"Multiple faces detected in image: {file.filename}. Only one face is allowed.")
            return False
    except Exception as e:
        logger.error(f"Error detecting faces in {file.filename}: {str(e)}")
        return False

    # Trích xuất đặc trưng khuôn mặt
    try:
        face = faces[1][0]  # Lấy khuôn mặt đầu tiên
        aligned_face = sface_model.alignCrop(frame, face)
        feature = sface_model.feature(aligned_face)
        logger.info(f"Extracted face feature for {file.filename}")
    except Exception as e:
        logger.error(f"Error extracting face feature for {file.filename}: {str(e)}")
        return False

    # Đọc file embeddings.pkl hiện tại (nếu có)
    output_file = Config.PATHS['embeddings']
    person_ids = []
    person_codes = []
    embeddings = []

    if os.path.exists(output_file):
        if os.path.getsize(output_file) == 0:
            logger.warning(f"Embeddings file {output_file} is empty. Initializing empty lists.")
        else:
            try:
                with open(output_file, 'rb') as f:
                    data = pickle.load(f)
                    if not isinstance(data, tuple) or len(data) != 3:
                        logger.error(f"Invalid data format in {output_file}. Initializing empty lists.")
                    else:
                        person_ids, show_person_ids, embeddings = data
                        if not (isinstance(person_ids, list) and isinstance(show_person_ids, list) and isinstance(embeddings, list)):
                            logger.error(f"Invalid data types in {output_file}. Initializing empty lists.")
                            person_ids = []
                            show_person_ids = []
                            embeddings = []
                        else:
                            logger.info(f"Loaded existing embeddings from {output_file}: {len(person_ids)} entries")
            except Exception as e:
                logger.error(f"Error reading embeddings file {output_file}: {str(e)}")
                logger.warning("Initializing empty lists due to read error.")
    else:
        logger.info(f"Embeddings file {output_file} does not exist. Initializing empty lists.")

    # Thêm đặc trưng mới
    try:
        person_ids.append(person_id)
        person_codes.append(person_code)
        embeddings.append(feature)
        logger.info(f"Added new embedding for person_id: {person_id}, person_code: {person_code}")
    except Exception as e:
        logger.error(f"Error adding new embedding: {str(e)}")
        return False

    # Lưu lại file embeddings.pkl
    try:
        with open(output_file, 'wb') as f:
            pickle.dump((person_ids, person_codes, embeddings), f)
        logger.info(f"Saved embeddings to {output_file} for person_id: {person_id}, person_code: {person_code}")
    except Exception as e:
        logger.error(f"Error saving embeddings file {output_file}: {str(e)}")
        return False

    # Lưu ảnh vào Config.PATHS['faces']
    try:
        face_path = os.path.normpath(os.path.join(faces_dir, filename))
        logger.info(f"Saving image to faces directory: {face_path}")
        import shutil
        shutil.copy(temp_path, face_path)
        logger.info(f"Image saved to {face_path}")
    except Exception as e:
        logger.error(f"Error saving image to {face_path}: {str(e)}")
        return False

    # Insert vào bảng image
    try:
        conn = getConnector()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO image (person_id, url) VALUES (%s, %s)",
            (person_id, filename)
        )
        conn.commit()
        logger.info(f"Inserted record into image table: person_id={person_id}, url={filename}")
    except Exception as e:
        logger.error(f"Error inserting into image table: {str(e)}")
        # Không trả về False để ưu tiên việc lưu embedding/ảnh
    finally:
        cursor.close()
        conn.close()

    # Xóa file tạm
    try:
        if os.path.exists(temp_path):
            os.remove(temp_path)
            logger.info(f"Deleted temporary file: {temp_path}")
    except Exception as e:
        logger.error(f"Error deleting temporary file {temp_path}: {str(e)}")

    return True
import os
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
        logging.FileHandler('avatar_upload.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Khởi tạo Blueprint
person_bp = Blueprint('person', __name__)

def upload_avatar(file, person_code):
    """
    Lưu ảnh đại diện vào Config.PATHS['avatars'] và cập nhật avatar_path trong bảng person.
    Args:
        file (FileStorage): Đối tượng file từ request.files.
        person_code (str): Mã của người (code trong bảng person).
    Returns:
        tuple: (message, status_code)
    """
    logger.info(f"Processing avatar upload for person_code: {person_code}, filename: {file.filename}")

    # Kiểm tra định dạng file
    if not file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        logger.error(f"Invalid file format for {file.filename}. Only PNG, JPG, JPEG are supported.")
        return {"error": "Only PNG, JPG, JPEG files are supported"}, 400

    # Tạo thư mục avatars nếu chưa tồn tại
    avatar_dir = os.path.normpath(Config.PATHS['avatars'])
    try:
        os.makedirs(avatar_dir, exist_ok=True)
        logger.info(f"Ensured directory exists: {avatar_dir}")
    except Exception as e:
        logger.error(f"Error creating directory {avatar_dir}: {str(e)}")
        return {"error": f"Failed to create avatar directory: {str(e)}"}, 500

    # Lưu file
    try:
        filename = secure_filename(file.filename)
        avatar_path = os.path.normpath(os.path.join(avatar_dir, filename))
        logger.info(f"Saving avatar to: {avatar_path}")

        # Xóa file cũ nếu tồn tại
        if os.path.exists(avatar_path):
            os.remove(avatar_path)
            logger.info(f"Deleted existing avatar: {avatar_path}")

        file.save(avatar_path)
        logger.info(f"Avatar saved to: {avatar_path}")
    except Exception as e:
        logger.error(f"Error saving avatar {file.filename}: {str(e)}")
        return {"error": f"Failed to save avatar: {str(e)}"}, 500

    # Cập nhật avatar_path trong bảng person
    try:
        conn = getConnector()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE person SET avatar_url = %s WHERE code = %s",
            (filename, person_code)
        )
        if cursor.rowcount == 0:
            logger.warning(f"No person found with code: {person_code}")
            return {"error": f"No person found with code: {person_code}"}, 404
        conn.commit()
        logger.info(f"Updated avatar_path for person_code: {person_code}, avatar_path: {filename}")
    except Exception as e:
        logger.error(f"Error updating person table: {str(e)}")
        return {"error": f"Failed to update avatar path: {str(e)}"}, 500
    finally:
        cursor.close()
        conn.close()

    return {"message": "Avatar uploaded and updated successfully"}, 200
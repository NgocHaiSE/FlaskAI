from flask import Blueprint, jsonify, request
from app.services.person_services import upload_avatar
from app.config import Config
import mysql.connector
from app.utils.add_face import add_face

person_bp = Blueprint('person', __name__)

@person_bp.route('/face/upload', methods=['POST'])
def upload_face_route():
    """Upload ảnh khuôn mặt và thêm vào embeddings."""
    
    try:
        # Kiểm tra dữ liệu đầu vào
        if 'file' not in request.files or 'personid' not in request.form or 'code' not in request.form:
            return jsonify({"error": "Missing file, personid, or code"}), 400

        file = request.files['file']
        person_id = request.form['personid']
        person_code = request.form['code']

        # Kiểm tra file rỗng
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400

        # Kiểm tra định dạng file
        if not file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            return jsonify({"error": "Only PNG, JPG, JPEG files are supported"}), 400

        try:
            person_id = int(person_id)
        except ValueError:
            return jsonify({"error": "Invalid personid format"}), 400

        # Gọi hàm add_face
        result = add_face(file, person_id, person_code)

        if result:
            return jsonify({"message": "Face added successfully"}), 200
        else:
            return jsonify({"error": "Failed to add face"}), 500

    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
      
@person_bp.route('/avatar/upload', methods=['POST'])
def upload_avatar_route():
    try:
        # Kiểm tra dữ liệu đầu vào
        if 'file' not in request.files or 'code' not in request.form:
            return jsonify({"error": "Missing file or code"}), 400

        file = request.files['file']
        person_code = request.form['code']

        # Kiểm tra file rỗng
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400

        # Kiểm tra định dạng file
        if not file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            return jsonify({"error": "Only PNG, JPG, JPEG files are supported"}), 400

        result, status_code = upload_avatar(file, person_code)

        return jsonify(result), status_code

    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
      
@person_bp.route('/get/<person_id>', methods=['GET'])
def get_information(person_id):
    try:
        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor(dictionary=True)

        cursor.callproc('GetPerson', [int(person_id)])

        result = next(cursor.stored_results(), None).fetchone()
        if not result:
            return jsonify({"error": "Không tìm thấy thông tin người dùng"}), 404

        cursor.close()
        connection.close()

        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
      
@person_bp.route('/images/<person_id>', methods=['GET'])
def get_images(person_id):
    try:
        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor(dictionary=True)

        cursor.callproc('GetImages', [person_id])

        result = []
        for res in cursor.stored_results():
            result.extend(res.fetchall())

        cursor.close()
        connection.close()

        if not result:
            return jsonify({"message": "Không tìm thấy hình ảnh cho person_id này"}), 404

        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
      
@person_bp.route('/get', methods=['GET'])
def get_all_person():
    try:
        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor(dictionary=True)

        cursor.callproc('GetAllPersons')

        result = []
        for res in cursor.stored_results():
            result.extend(res.fetchall())

        cursor.close()
        connection.close()

        if not result:
            return jsonify({"message": "Không tìm thấy người dùng nào"}), 404

        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
    
@person_bp.route('/adjust', methods=['GET'])
def adjust_person():
    try:
        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor(dictionary=True)

        cursor.callproc('AdjustPerson')

        result = []
        for res in cursor.stored_results():
            result.extend(res.fetchall())

        cursor.close()
        connection.close()

        if not result:
            return jsonify({"message": "Không tìm thấy người dùng nào"}), 404

        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500.
    


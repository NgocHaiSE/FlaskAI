from flask import Blueprint, jsonify, request
from app.services.person_services import upload_avatar
from app.config import Config
from app.middleware.auth import require_permission, require_resource_access, login_required
import mysql.connector
from app.utils.add_face import add_face

person_bp = Blueprint('person', __name__)

@person_bp.route('/face/upload', methods=['POST'])
@require_permission('employees.update')
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
@require_permission('employees.update')
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
@require_permission('employees.view')
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
@require_permission('employees.view')
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
@require_permission('employees.view')
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
    
@person_bp.route('/create', methods=['POST'])
@require_permission('employees.create')
def create_person():
    """Tạo nhân viên mới"""
    try:
        data = request.get_json()
        required_fields = ['code', 'fullname']
        
        if not data or not all(field in data for field in required_fields):
            return jsonify({"error": "Missing required fields"}), 400

        code = data['code']
        fullname = data['fullname']
        gender = data.get('gender', 1)
        birth = data.get('birth')
        phone = data.get('phone')
        address = data.get('address')
        email = data.get('email')
        position = data.get('position')
        department_id = data.get('department_id')

        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor()

        cursor.callproc('AddPerson', [
            code, fullname, gender, birth, phone, address, email, position, department_id
        ])

        connection.commit()
        return jsonify({"message": "Person created successfully"}), 201

    except mysql.connector.Error as e:
        if e.errno == 1062:  # Duplicate entry
            return jsonify({"error": "Person code already exists"}), 409
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
    
@person_bp.route('/adjust/<int:person_id>', methods=['PUT'])
@require_permission('employees.update')
def adjust_person(person_id):
    """Cập nhật thông tin nhân viên"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing data"}), 400

        fullname = data.get('fullname')
        gender = data.get('gender')
        birth = data.get('birth')
        phone = data.get('phone')
        address = data.get('address')
        email = data.get('email')
        position = data.get('position')
        department_id = data.get('department_id')

        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor()

        cursor.callproc('AdjustPerson', [
            person_id, fullname, gender, birth, phone, address, email, position, department_id
        ])

        connection.commit()
        return jsonify({"message": "Person updated successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@person_bp.route('/delete/<int:person_id>', methods=['DELETE'])
@require_permission('employees.delete')
def delete_person(person_id):
    """Xóa nhân viên"""
    try:
        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor()

        # Soft delete - chỉ cập nhật status
        cursor.execute("""
            UPDATE person SET status = 0 WHERE id = %s
        """, (person_id,))

        if cursor.rowcount == 0:
            return jsonify({"error": "Person not found"}), 404

        connection.commit()
        return jsonify({"message": "Person deleted successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@person_bp.route('/departments', methods=['GET'])
@login_required
def get_departments():
    """Lấy danh sách phòng ban"""
    try:
        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor(dictionary=True)

        cursor.execute("SELECT id, name FROM departments ORDER BY name")
        departments = cursor.fetchall()

        return jsonify(departments), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
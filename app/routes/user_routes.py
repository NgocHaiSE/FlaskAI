from flask import Blueprint, jsonify, request
from app.config import Config
import mysql.connector
import hashlib
import jwt
import datetime
from functools import wraps

user_bp = Blueprint('user', __name__)

# Secret key cho JWT (nên đặt trong config hoặc env)
JWT_SECRET = 'your-secret-key-change-this'
JWT_ALGORITHM = 'HS256'

def generate_password_hash(password):
    """Tạo hash password đơn giản"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password_hash(password, password_hash):
    """Kiểm tra password với hash"""
    return hashlib.sha256(password.encode()).hexdigest() == password_hash

def generate_token(user_data):
    """Tạo JWT token"""
    payload = {
        'user_id': user_data['id'],
        'username': user_data['username'],
        'role_id': user_data['role_id'],
        'role_name': user_data['role_name'],
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_token(token):
    """Xác thực JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

@user_bp.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        if not data or 'username' not in data or 'password' not in data:
            return jsonify({"error": "Missing username or password"}), 400

        username = data['username']
        password = data['password']

        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor(dictionary=True)

        # Gọi stored procedure để lấy thông tin user với permissions
        cursor.callproc('AuthenticateUserWithPermissions', [username, generate_password_hash(password)])

        result = None
        for res in cursor.stored_results():
            result = res.fetchone()

        if not result:
            return jsonify({"error": "Invalid username or password"}), 401

        # Tạo JWT token
        token = generate_token(result)

        # Parse permissions string thành array
        permissions = []
        if result.get('permissions'):
            permissions = result['permissions'].split(',')

        response_data = {
            "token": token,
            "user": {
                "id": result['id'],
                "username": result['username'],
                "email": result.get('email'),
                "full_name": result.get('full_name'),
                "role_name": result.get('role_name'),
                "role_description": result.get('role_description'),
                "status": result['status'],
                "permissions": permissions
            }
        }

        return jsonify(response_data), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@user_bp.route('/profile', methods=['GET'])
def get_profile():
    """Lấy thông tin profile của user hiện tại"""
    try:
        # Lấy token từ header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Missing or invalid authorization header"}), 401

        token = auth_header.split(' ')[1]
        payload = verify_token(token)
        if not payload:
            return jsonify({"error": "Invalid or expired token"}), 401

        user_id = payload['user_id']

        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor(dictionary=True)

        # Lấy thông tin user
        cursor.execute("""
            SELECT u.id, u.username, u.email, u.full_name, u.status,
                   r.name as role_name, r.description as role_description
            FROM users u
            LEFT JOIN roles r ON u.role_id = r.id
            WHERE u.id = %s
        """, (user_id,))

        user = cursor.fetchone()
        if not user:
            return jsonify({"error": "User not found"}), 404

        # Lấy permissions
        cursor.execute("""
            SELECT p.name
            FROM users u
            JOIN roles r ON u.role_id = r.id
            JOIN role_permissions rp ON r.id = rp.role_id
            JOIN permissions p ON rp.permission_id = p.id
            WHERE u.id = %s
        """, (user_id,))

        permissions = [row['name'] for row in cursor.fetchall()]
        user['permissions'] = permissions

        return jsonify(user), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@user_bp.route('/check-permission', methods=['POST'])
def check_permission():
    """Kiểm tra quyền của user"""
    try:
        data = request.get_json()
        if not data or 'permission' not in data:
            return jsonify({"error": "Missing permission parameter"}), 400

        # Lấy token từ header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Missing or invalid authorization header"}), 401

        token = auth_header.split(' ')[1]
        payload = verify_token(token)
        if not payload:
            return jsonify({"error": "Invalid or expired token"}), 401

        user_id = payload['user_id']
        permission_name = data['permission']

        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor(dictionary=True)

        cursor.callproc('CheckUserPermission', [user_id, permission_name])

        result = None
        for res in cursor.stored_results():
            result = res.fetchone()

        has_permission = result and result.get('has_permission', 0) > 0

        return jsonify({"has_permission": has_permission}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@user_bp.route('/all', methods=['GET'])
def get_all_users():
    """Lấy danh sách tất cả users (chỉ admin)"""
    try:
        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT u.id, u.username, u.email, u.full_name, u.status, u.created_at,
                   r.name as role_name
            FROM users u
            LEFT JOIN roles r ON u.role_id = r.id
            ORDER BY u.created_at DESC
        """)

        users = cursor.fetchall()
        return jsonify(users), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@user_bp.route('/create', methods=['POST'])
def create_user():
    """Tạo user mới (chỉ admin)"""
    try:
        data = request.get_json()
        required_fields = ['username', 'password', 'role_id']
        
        if not data or not all(field in data for field in required_fields):
            return jsonify({"error": "Missing required fields"}), 400

        username = data['username']
        password = generate_password_hash(data['password'])
        email = data.get('email')
        full_name = data.get('full_name')
        role_id = data['role_id']

        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO users (username, password, email, full_name, role_id)
            VALUES (%s, %s, %s, %s, %s)
        """, (username, password, email, full_name, role_id))

        connection.commit()
        user_id = cursor.lastrowid

        return jsonify({"message": "User created successfully", "user_id": user_id}), 201

    except mysql.connector.Error as e:
        if e.errno == 1062:  # Duplicate entry
            return jsonify({"error": "Username already exists"}), 409
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@user_bp.route('/update-role/<int:user_id>', methods=['PUT'])
def update_user_role(user_id):
    """Cập nhật role của user (chỉ admin)"""
    try:
        data = request.get_json()
        if not data or 'role_id' not in data:
            return jsonify({"error": "Missing role_id"}), 400

        role_id = data['role_id']

        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor()

        cursor.execute("UPDATE users SET role_id = %s WHERE id = %s", (role_id, user_id))
        
        if cursor.rowcount == 0:
            return jsonify({"error": "User not found"}), 404

        connection.commit()
        return jsonify({"message": "User role updated successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@user_bp.route('/change-password', methods=['PUT'])
def change_password():
    """Đổi mật khẩu"""
    try:
        data = request.get_json()
        if not data or 'old_password' not in data or 'new_password' not in data:
            return jsonify({"error": "Missing old_password or new_password"}), 400

        # Lấy token từ header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Missing or invalid authorization header"}), 401

        token = auth_header.split(' ')[1]
        payload = verify_token(token)
        if not payload:
            return jsonify({"error": "Invalid or expired token"}), 401

        user_id = payload['user_id']
        old_password = generate_password_hash(data['old_password'])
        new_password = generate_password_hash(data['new_password'])

        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor()

        # Kiểm tra mật khẩu cũ
        cursor.execute("SELECT password FROM users WHERE id = %s", (user_id,))
        result = cursor.fetchone()
        
        if not result or result[0] != old_password:
            return jsonify({"error": "Invalid old password"}), 400

        # Cập nhật mật khẩu mới
        cursor.execute("UPDATE users SET password = %s WHERE id = %s", (new_password, user_id))
        connection.commit()

        return jsonify({"message": "Password changed successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
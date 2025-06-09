from flask import Blueprint, jsonify, request, current_app, g
from app.config import Config
import mysql.connector
import hashlib
from flask_jwt_extended import (
    jwt_required, get_jwt_identity, create_access_token, 
    create_refresh_token, get_jwt
)
from app.middleware.auth import (
    login_required, get_current_user, get_current_user_permissions,
    admin_required, require_permission
)

user_bp = Blueprint('user', __name__)

def generate_password_hash(password):
    """Tạo hash password đơn giản"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password_hash(password, password_hash):
    """Kiểm tra password với hash"""
    return hashlib.sha256(password.encode()).hexdigest() == password_hash

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

        # Tạo JWT tokens
        access_token = create_access_token(
            identity=result['id'],
            additional_claims={
                'username': result['username'],
                'role_id': result.get('role_id'),
                'role_name': result.get('role_name')
            }
        )
        
        refresh_token = create_refresh_token(identity=result['id'])

        # Parse permissions string thành array
        permissions = []
        if result.get('permissions'):
            permissions = result['permissions'].split(',')

        response_data = {
            "token": access_token,
            "refresh_token": refresh_token,
            "user": {
                "id": result['id'],
                "username": result['username'],
                "email": result.get('email'),
                "full_name": result.get('full_name'),
                "role_name": result.get('role_name'),
                "role_description": result.get('role_description'),
                "status": result['status'],
                "permissions": permissions,
                "created_at": result.get('created_at')
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

@user_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Refresh access token"""
    try:
        current_user_id = get_jwt_identity()
        
        # Kiểm tra user vẫn còn active
        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT u.id, u.username, u.status,
                   r.id as role_id, r.name as role_name
            FROM users u
            LEFT JOIN roles r ON u.role_id = r.id
            WHERE u.id = %s
        """, (current_user_id,))

        user = cursor.fetchone()
        if not user or user['status'] != 'active':
            return jsonify({"error": "User not found or inactive"}), 401

        # Tạo access token mới
        new_access_token = create_access_token(
            identity=current_user_id,
            additional_claims={
                'username': user['username'],
                'role_id': user.get('role_id'),
                'role_name': user.get('role_name')
            }
        )

        return jsonify({"access_token": new_access_token}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@user_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """Logout user by blacklisting the token"""
    try:
        jti = get_jwt()['jti']
        current_app.blacklisted_tokens.add(jti)
        return jsonify({"message": "Successfully logged out"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@user_bp.route('/profile', methods=['GET'])
@login_required
def get_profile():
    """Lấy thông tin profile của user hiện tại"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({"error": "User not found"}), 404

        # Lấy permissions
        permissions = get_current_user_permissions()
        user['permissions'] = permissions

        return jsonify(user), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@user_bp.route('/profile', methods=['PUT'])
@login_required
def update_profile():
    """Cập nhật thông tin profile của user hiện tại"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing data"}), 400

        current_user = get_current_user()
        user_id = current_user['id']

        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor()

        # Tạo câu query động cho các field được phép update
        update_fields = []
        params = []
        
        allowed_fields = ['email', 'full_name']
        
        for field in allowed_fields:
            if field in data:
                update_fields.append(f"{field} = %s")
                params.append(data[field])

        if not update_fields:
            return jsonify({"error": "No valid fields to update"}), 400

        params.append(user_id)
        query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = %s"
        
        cursor.execute(query, params)
        connection.commit()

        return jsonify({"message": "Profile updated successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@user_bp.route('/check-permission', methods=['POST'])
@login_required
def check_permission():
    """Kiểm tra quyền của user"""
    try:
        data = request.get_json()
        if not data or 'permission' not in data:
            return jsonify({"error": "Missing permission parameter"}), 400

        permission_name = data['permission']
        current_user = get_current_user()
        user_id = current_user['id']

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
@require_permission('system.admin')
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
@require_permission('system.admin')
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
@require_permission('system.admin')
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
@login_required
def change_password():
    """Đổi mật khẩu"""
    try:
        data = request.get_json()
        if not data or 'old_password' not in data or 'new_password' not in data:
            return jsonify({"error": "Missing old_password or new_password"}), 400

        current_user = get_current_user()
        user_id = current_user['id']
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

@user_bp.route('/deactivate/<int:user_id>', methods=['PUT'])
@require_permission('system.admin')
def deactivate_user(user_id):
    """Vô hiệu hóa user (chỉ admin)"""
    try:
        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor()

        cursor.execute("UPDATE users SET status = 'inactive' WHERE id = %s", (user_id,))
        
        if cursor.rowcount == 0:
            return jsonify({"error": "User not found"}), 404

        connection.commit()
        return jsonify({"message": "User deactivated successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@user_bp.route('/activate/<int:user_id>', methods=['PUT'])
@require_permission('system.admin')
def activate_user(user_id):
    """Kích hoạt user (chỉ admin)"""
    try:
        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor()

        cursor.execute("UPDATE users SET status = 'active' WHERE id = %s", (user_id,))
        
        if cursor.rowcount == 0:
            return jsonify({"error": "User not found"}), 404

        connection.commit()
        return jsonify({"message": "User activated successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
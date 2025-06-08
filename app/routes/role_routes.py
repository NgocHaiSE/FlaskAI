from flask import Blueprint, jsonify, request
from app.config import Config
import mysql.connector

role_bp = Blueprint('role', __name__)

@role_bp.route('/all', methods=['GET'])
def get_all_roles():
    """Lấy danh sách tất cả roles"""
    try:
        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor(dictionary=True)

        cursor.callproc('GetAllRoles')

        result = []
        for res in cursor.stored_results():
            result.extend(res.fetchall())

        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@role_bp.route('/<int:role_id>/permissions', methods=['GET'])
def get_role_permissions(role_id):
    """Lấy danh sách permissions của một role"""
    try:
        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor(dictionary=True)

        cursor.callproc('GetRolePermissions', [role_id])

        result = []
        for res in cursor.stored_results():
            result.extend(res.fetchall())

        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@role_bp.route('/create', methods=['POST'])
def create_role():
    """Tạo role mới"""
    try:
        data = request.get_json()
        if not data or 'name' not in data:
            return jsonify({"error": "Missing role name"}), 400

        name = data['name']
        description = data.get('description')

        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO roles (name, description) 
            VALUES (%s, %s)
        """, (name, description))

        connection.commit()
        role_id = cursor.lastrowid

        return jsonify({
            "message": "Role created successfully",
            "role_id": role_id
        }), 201

    except mysql.connector.Error as e:
        if e.errno == 1062:  # Duplicate entry
            return jsonify({"error": "Role name already exists"}), 409
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@role_bp.route('/<int:role_id>', methods=['PUT'])
def update_role(role_id):
    """Cập nhật thông tin role"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing data"}), 400

        name = data.get('name')
        description = data.get('description')

        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor()

        # Tạo câu query động
        update_fields = []
        params = []

        if name:
            update_fields.append("name = %s")
            params.append(name)
        
        if description is not None:  # Cho phép description rỗng
            update_fields.append("description = %s")
            params.append(description)

        if not update_fields:
            return jsonify({"error": "No fields to update"}), 400

        params.append(role_id)
        query = f"UPDATE roles SET {', '.join(update_fields)} WHERE id = %s"
        
        cursor.execute(query, params)
        
        if cursor.rowcount == 0:
            return jsonify({"error": "Role not found"}), 404

        connection.commit()
        return jsonify({"message": "Role updated successfully"}), 200

    except mysql.connector.Error as e:
        if e.errno == 1062:  # Duplicate entry
            return jsonify({"error": "Role name already exists"}), 409
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@role_bp.route('/<int:role_id>', methods=['DELETE'])
def delete_role(role_id):
    """Xóa role"""
    try:
        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor()

        # Kiểm tra xem role có đang được sử dụng không
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE role_id = %s", (role_id,))
        result = cursor.fetchone()
        
        if result[0] > 0:
            return jsonify({"error": "Cannot delete role that is currently assigned to users"}), 400

        # Xóa role
        cursor.execute("DELETE FROM roles WHERE id = %s", (role_id,))
        
        if cursor.rowcount == 0:
            return jsonify({"error": "Role not found"}), 404

        connection.commit()
        return jsonify({"message": "Role deleted successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@role_bp.route('/<int:role_id>/permissions/<int:permission_id>', methods=['POST'])
def assign_permission_to_role(role_id, permission_id):
    """Gán permission cho role"""
    try:
        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO role_permissions (role_id, permission_id) 
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE role_id = role_id
        """, (role_id, permission_id))

        connection.commit()
        return jsonify({"message": "Permission assigned to role successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@role_bp.route('/<int:role_id>/permissions/<int:permission_id>', methods=['DELETE'])
def remove_permission_from_role(role_id, permission_id):
    """Gỡ permission khỏi role"""
    try:
        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor()

        cursor.execute("""
            DELETE FROM role_permissions 
            WHERE role_id = %s AND permission_id = %s
        """, (role_id, permission_id))

        if cursor.rowcount == 0:
            return jsonify({"error": "Permission not found for this role"}), 404

        connection.commit()
        return jsonify({"message": "Permission removed from role successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@role_bp.route('/<int:role_id>/permissions/bulk', methods=['POST'])
def bulk_assign_permissions(role_id):
    """Gán nhiều permissions cho role cùng lúc"""
    try:
        data = request.get_json()
        if not data or 'permission_ids' not in data:
            return jsonify({"error": "Missing permission_ids"}), 400

        permission_ids = data['permission_ids']
        if not isinstance(permission_ids, list):
            return jsonify({"error": "permission_ids must be a list"}), 400

        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor()

        # Xóa tất cả permissions hiện tại của role
        cursor.execute("DELETE FROM role_permissions WHERE role_id = %s", (role_id,))

        # Thêm permissions mới
        for permission_id in permission_ids:
            cursor.execute("""
                INSERT INTO role_permissions (role_id, permission_id) 
                VALUES (%s, %s)
            """, (role_id, permission_id))

        connection.commit()
        return jsonify({"message": f"Assigned {len(permission_ids)} permissions to role"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
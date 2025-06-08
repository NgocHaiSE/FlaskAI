from flask import Blueprint, jsonify, request
from app.config import Config
import mysql.connector

permission_bp = Blueprint('permission', __name__)

@permission_bp.route('/all', methods=['GET'])
def get_all_permissions():
    """Lấy danh sách tất cả permissions"""
    try:
        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT id, name, resource, action, description, created_at
            FROM permissions 
            ORDER BY resource, action
        """)

        permissions = cursor.fetchall()
        return jsonify(permissions), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@permission_bp.route('/resources', methods=['GET'])
def get_resources():
    """Lấy danh sách tất cả resources"""
    try:
        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT DISTINCT resource 
            FROM permissions 
            ORDER BY resource
        """)

        resources = [row['resource'] for row in cursor.fetchall()]
        return jsonify(resources), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@permission_bp.route('/actions', methods=['GET'])
def get_actions():
    """Lấy danh sách tất cả actions"""
    try:
        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT DISTINCT action 
            FROM permissions 
            ORDER BY action
        """)

        actions = [row['action'] for row in cursor.fetchall()]
        return jsonify(actions), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@permission_bp.route('/by-resource/<resource>', methods=['GET'])
def get_permissions_by_resource(resource):
    """Lấy permissions theo resource"""
    try:
        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT id, name, resource, action, description
            FROM permissions 
            WHERE resource = %s
            ORDER BY action
        """, (resource,))

        permissions = cursor.fetchall()
        return jsonify(permissions), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@permission_bp.route('/create', methods=['POST'])
def create_permission():
    """Tạo permission mới"""
    try:
        data = request.get_json()
        required_fields = ['name', 'resource', 'action']
        
        if not data or not all(field in data for field in required_fields):
            return jsonify({"error": "Missing required fields: name, resource, action"}), 400

        name = data['name']
        resource = data['resource']
        action = data['action']
        description = data.get('description')

        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO permissions (name, resource, action, description)
            VALUES (%s, %s, %s, %s)
        """, (name, resource, action, description))

        connection.commit()
        permission_id = cursor.lastrowid

        return jsonify({
            "message": "Permission created successfully",
            "permission_id": permission_id
        }), 201

    except mysql.connector.Error as e:
        if e.errno == 1062:  # Duplicate entry
            return jsonify({"error": "Permission name already exists"}), 409
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@permission_bp.route('/<int:permission_id>', methods=['PUT'])
def update_permission(permission_id):
    """Cập nhật thông tin permission"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing data"}), 400

        name = data.get('name')
        resource = data.get('resource')
        action = data.get('action')
        description = data.get('description')

        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor()

        # Tạo câu query động
        update_fields = []
        params = []

        if name:
            update_fields.append("name = %s")
            params.append(name)
        
        if resource:
            update_fields.append("resource = %s")
            params.append(resource)
            
        if action:
            update_fields.append("action = %s")
            params.append(action)
        
        if description is not None:
            update_fields.append("description = %s")
            params.append(description)

        if not update_fields:
            return jsonify({"error": "No fields to update"}), 400

        params.append(permission_id)
        query = f"UPDATE permissions SET {', '.join(update_fields)} WHERE id = %s"
        
        cursor.execute(query, params)
        
        if cursor.rowcount == 0:
            return jsonify({"error": "Permission not found"}), 404

        connection.commit()
        return jsonify({"message": "Permission updated successfully"}), 200

    except mysql.connector.Error as e:
        if e.errno == 1062:  # Duplicate entry
            return jsonify({"error": "Permission name already exists"}), 409
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@permission_bp.route('/<int:permission_id>', methods=['DELETE'])
def delete_permission(permission_id):
    """Xóa permission"""
    try:
        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor()

        # Kiểm tra xem permission có đang được sử dụng không
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM role_permissions 
            WHERE permission_id = %s
        """, (permission_id,))
        result = cursor.fetchone()
        
        if result[0] > 0:
            return jsonify({"error": "Cannot delete permission that is currently assigned to roles"}), 400

        # Xóa permission
        cursor.execute("DELETE FROM permissions WHERE id = %s", (permission_id,))
        
        if cursor.rowcount == 0:
            return jsonify({"error": "Permission not found"}), 404

        connection.commit()
        return jsonify({"message": "Permission deleted successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@permission_bp.route('/roles/<int:permission_id>', methods=['GET'])
def get_roles_with_permission(permission_id):
    """Lấy danh sách roles có permission này"""
    try:
        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT r.id, r.name, r.description
            FROM roles r
            JOIN role_permissions rp ON r.id = rp.role_id
            WHERE rp.permission_id = %s
            ORDER BY r.name
        """, (permission_id,))

        roles = cursor.fetchall()
        return jsonify(roles), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@permission_bp.route('/seed', methods=['POST'])
def seed_permissions():
    """Tạo dữ liệu permissions mẫu"""
    try:
        default_permissions = [
            # Employee permissions
            {'name': 'employees.view', 'resource': 'employees', 'action': 'view', 'description': 'Xem danh sách nhân viên'},
            {'name': 'employees.create', 'resource': 'employees', 'action': 'create', 'description': 'Thêm nhân viên mới'},
            {'name': 'employees.update', 'resource': 'employees', 'action': 'update', 'description': 'Chỉnh sửa thông tin nhân viên'},
            {'name': 'employees.delete', 'resource': 'employees', 'action': 'delete', 'description': 'Xóa nhân viên'},
            
            # Security permissions
            {'name': 'security.view', 'resource': 'security', 'action': 'view', 'description': 'Xem camera an ninh'},
            {'name': 'security.manage', 'resource': 'security', 'action': 'manage', 'description': 'Quản lý hệ thống an ninh'},
            
            # Timekeeping permissions
            {'name': 'timekeeping.view', 'resource': 'timekeeping', 'action': 'view', 'description': 'Xem chấm công'},
            {'name': 'timekeeping.manage', 'resource': 'timekeeping', 'action': 'manage', 'description': 'Quản lý chấm công'},
            
            # Reports permissions
            {'name': 'reports.view', 'resource': 'reports', 'action': 'view', 'description': 'Xem báo cáo'},
            
            # System permissions
            {'name': 'system.admin', 'resource': 'system', 'action': 'admin', 'description': 'Quản trị hệ thống'},
        ]

        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor()

        created_count = 0
        for perm in default_permissions:
            try:
                cursor.execute("""
                    INSERT INTO permissions (name, resource, action, description)
                    VALUES (%s, %s, %s, %s)
                """, (perm['name'], perm['resource'], perm['action'], perm['description']))
                created_count += 1
            except mysql.connector.Error as e:
                if e.errno != 1062:  # Ignore duplicate entries
                    raise e

        connection.commit()
        return jsonify({
            "message": f"Created {created_count} permissions successfully"
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
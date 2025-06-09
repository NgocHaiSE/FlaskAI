# app/middleware/auth.py

from flask import request, jsonify, g, current_app
from functools import wraps
from flask_jwt_extended import (
    jwt_required, get_jwt_identity, get_jwt, 
    verify_jwt_in_request, create_access_token,
    create_refresh_token
)
import mysql.connector
from app.config import Config

def get_user_permissions(user_id):
    """Lấy danh sách permissions của user từ database"""
    try:
        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor()

        cursor.execute("""
            SELECT p.name
            FROM users u
            JOIN roles r ON u.role_id = r.id
            JOIN role_permissions rp ON r.id = rp.role_id
            JOIN permissions p ON rp.permission_id = p.id
            WHERE u.id = %s AND u.status = 'active'
        """, (user_id,))

        permissions = [row[0] for row in cursor.fetchall()]
        return permissions

    except Exception as e:
        print(f"Error getting user permissions: {str(e)}")
        return []

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

def get_user_info(user_id):
    """Lấy thông tin user từ database"""
    try:
        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT u.id, u.username, u.email, u.full_name, u.status,
                   r.id as role_id, r.name as role_name, r.description as role_description
            FROM users u
            LEFT JOIN roles r ON u.role_id = r.id
            WHERE u.id = %s AND u.status = 'active'
        """, (user_id,))

        user = cursor.fetchone()
        return user

    except Exception as e:
        print(f"Error getting user info: {str(e)}")
        return None

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

def login_required_with_user_info(f):
    """Decorator yêu cầu đăng nhập và tự động load user info"""
    @wraps(f)
    @jwt_required()
    def decorated_function(*args, **kwargs):
        current_user_id = get_jwt_identity()
        
        # Lấy thông tin user
        user_info = get_user_info(current_user_id)
        if not user_info:
            return jsonify({"error": "User not found or inactive"}), 401
        
        # Lưu thông tin user vào g để sử dụng trong route
        g.current_user = user_info
        
        return f(*args, **kwargs)
    
    return decorated_function

def require_permission(permission):
    """Decorator yêu cầu permission cụ thể"""
    def decorator(f):
        @wraps(f)
        @jwt_required()
        def decorated_function(*args, **kwargs):
            current_user_id = get_jwt_identity()
            
            # Lấy thông tin user
            user_info = get_user_info(current_user_id)
            if not user_info:
                return jsonify({"error": "User not found or inactive"}), 401
            
            # Lấy permissions
            user_permissions = get_user_permissions(current_user_id)
            
            if permission not in user_permissions:
                return jsonify({"error": f"Access denied. Required permission: {permission}"}), 403
            
            # Lưu thông tin vào g để sử dụng trong route
            g.current_user = user_info
            g.user_permissions = user_permissions
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

def require_any_permission(permissions):
    """Decorator yêu cầu ít nhất một trong các permissions"""
    def decorator(f):
        @wraps(f)
        @jwt_required()
        def decorated_function(*args, **kwargs):
            current_user_id = get_jwt_identity()
            
            # Lấy thông tin user
            user_info = get_user_info(current_user_id)
            if not user_info:
                return jsonify({"error": "User not found or inactive"}), 401
            
            # Lấy permissions
            user_permissions = get_user_permissions(current_user_id)
            
            has_permission = any(perm in user_permissions for perm in permissions)
            
            if not has_permission:
                return jsonify({
                    "error": f"Access denied. Required one of: {', '.join(permissions)}"
                }), 403
            
            g.current_user = user_info
            g.user_permissions = user_permissions
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

def require_all_permissions(permissions):
    """Decorator yêu cầu tất cả permissions"""
    def decorator(f):
        @wraps(f)
        @jwt_required()
        def decorated_function(*args, **kwargs):
            current_user_id = get_jwt_identity()
            
            # Lấy thông tin user
            user_info = get_user_info(current_user_id)
            if not user_info:
                return jsonify({"error": "User not found or inactive"}), 401
            
            # Lấy permissions
            user_permissions = get_user_permissions(current_user_id)
            
            has_all_permissions = all(perm in user_permissions for perm in permissions)
            
            if not has_all_permissions:
                return jsonify({
                    "error": f"Access denied. Required all of: {', '.join(permissions)}"
                }), 403
            
            g.current_user = user_info
            g.user_permissions = user_permissions
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

def require_role(role_name):
    """Decorator yêu cầu role cụ thể"""
    def decorator(f):
        @wraps(f)
        @jwt_required()
        def decorated_function(*args, **kwargs):
            current_user_id = get_jwt_identity()
            
            # Lấy thông tin user
            user_info = get_user_info(current_user_id)
            if not user_info:
                return jsonify({"error": "User not found or inactive"}), 401
            
            user_role = user_info.get('role_name')
            
            if user_role != role_name:
                return jsonify({"error": f"Access denied. Required role: {role_name}"}), 403
            
            g.current_user = user_info
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

def require_resource_access(resource, action=None):
    """Decorator kiểm tra quyền truy cập resource"""
    def decorator(f):
        @wraps(f)
        @jwt_required()
        def decorated_function(*args, **kwargs):
            current_user_id = get_jwt_identity()
            
            # Lấy thông tin user
            user_info = get_user_info(current_user_id)
            if not user_info:
                return jsonify({"error": "User not found or inactive"}), 401
            
            # Lấy permissions
            user_permissions = get_user_permissions(current_user_id)
            
            # Tạo permission name từ resource và action
            if action:
                required_permission = f"{resource}.{action}"
                has_permission = required_permission in user_permissions
            else:
                # Kiểm tra có ít nhất một permission cho resource này
                has_permission = any(
                    perm.startswith(f"{resource}.") 
                    for perm in user_permissions
                )
            
            if not has_permission:
                return jsonify({
                    "error": f"Access denied. No permission for resource: {resource}" + 
                            (f" with action: {action}" if action else "")
                }), 403
            
            g.current_user = user_info
            g.user_permissions = user_permissions
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

def admin_required(f):
    """Decorator yêu cầu quyền admin"""
    @wraps(f)
    @require_any_permission(['system.admin'])
    def decorated_function(*args, **kwargs):
        return f(*args, **kwargs)
    
    return decorated_function

# Alias cho compatibility với code cũ
login_required = login_required_with_user_info

# Helper functions để sử dụng trong routes
def has_permission(permission):
    """Kiểm tra xem user hiện tại có permission không"""
    if not hasattr(g, 'user_permissions'):
        if not hasattr(g, 'current_user'):
            return False
        user_id = g.current_user['id']
        g.user_permissions = get_user_permissions(user_id)
    
    return permission in g.user_permissions

def has_any_permission(permissions):
    """Kiểm tra xem user hiện tại có ít nhất một permission không"""
    if not hasattr(g, 'user_permissions'):
        if not hasattr(g, 'current_user'):
            return False
        user_id = g.current_user['id']
        g.user_permissions = get_user_permissions(user_id)
    
    return any(perm in g.user_permissions for perm in permissions)

def has_all_permissions(permissions):
    """Kiểm tra xem user hiện tại có tất cả permissions không"""
    if not hasattr(g, 'user_permissions'):
        if not hasattr(g, 'current_user'):
            return False
        user_id = g.current_user['id']
        g.user_permissions = get_user_permissions(user_id)
    
    return all(perm in g.user_permissions for perm in permissions)

def has_role(role_name):
    """Kiểm tra xem user hiện tại có role không"""
    if not hasattr(g, 'current_user'):
        return False
    return g.current_user.get('role_name') == role_name

def is_admin():
    """Kiểm tra xem user hiện tại có phải admin không"""
    return has_permission('system.admin') or has_role('admin')

def get_current_user():
    """Lấy thông tin user hiện tại"""
    if hasattr(g, 'current_user'):
        return g.current_user
    
    # Nếu chưa có trong g, thử lấy từ JWT
    try:
        verify_jwt_in_request()
        current_user_id = get_jwt_identity()
        user_info = get_user_info(current_user_id)
        if user_info:
            g.current_user = user_info
            return user_info
    except:
        pass
    
    return None

def get_current_user_permissions():
    """Lấy permissions của user hiện tại"""
    if hasattr(g, 'user_permissions'):
        return g.user_permissions
    
    current_user = get_current_user()
    if current_user:
        user_permissions = get_user_permissions(current_user['id'])
        g.user_permissions = user_permissions
        return user_permissions
    
    return []
# app/middleware/auth.py

from flask import request, jsonify, g
from functools import wraps
import jwt
import mysql.connector
from app.config import Config

JWT_SECRET = 'mta-jwt'  # Nên đặt trong config
JWT_ALGORITHM = 'HS256'

def verify_token(token):
    """Xác thực JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

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

def login_required(f):
    """Decorator yêu cầu đăng nhập"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Missing or invalid authorization header"}), 401

        token = auth_header.split(' ')[1]
        payload = verify_token(token)
        
        if not payload:
            return jsonify({"error": "Invalid or expired token"}), 401

        # Lưu thông tin user vào g để sử dụng trong route
        g.current_user = {
            'id': payload['user_id'],
            'username': payload['username'],
            'role_id': payload['role_id'],
            'role_name': payload['role_name']
        }
        
        return f(*args, **kwargs)
    
    return decorated_function

def require_permission(permission):
    """Decorator yêu cầu permission cụ thể"""
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            user_id = g.current_user['id']
            user_permissions = get_user_permissions(user_id)
            
            if permission not in user_permissions:
                return jsonify({"error": f"Access denied. Required permission: {permission}"}), 403
            
            # Lưu permissions vào g để sử dụng trong route
            g.user_permissions = user_permissions
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

def require_any_permission(permissions):
    """Decorator yêu cầu ít nhất một trong các permissions"""
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            user_id = g.current_user['id']
            user_permissions = get_user_permissions(user_id)
            
            has_permission = any(perm in user_permissions for perm in permissions)
            
            if not has_permission:
                return jsonify({
                    "error": f"Access denied. Required one of: {', '.join(permissions)}"
                }), 403
            
            g.user_permissions = user_permissions
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

def require_all_permissions(permissions):
    """Decorator yêu cầu tất cả permissions"""
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            user_id = g.current_user['id']
            user_permissions = get_user_permissions(user_id)
            
            has_all_permissions = all(perm in user_permissions for perm in permissions)
            
            if not has_all_permissions:
                return jsonify({
                    "error": f"Access denied. Required all of: {', '.join(permissions)}"
                }), 403
            
            g.user_permissions = user_permissions
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

def require_role(role_name):
    """Decorator yêu cầu role cụ thể"""
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            user_role = g.current_user['role_name']
            
            if user_role != role_name:
                return jsonify({"error": f"Access denied. Required role: {role_name}"}), 403
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

def require_resource_access(resource, action=None):
    """Decorator kiểm tra quyền truy cập resource"""
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            user_id = g.current_user['id']
            user_permissions = get_user_permissions(user_id)
            
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

# Helper functions để sử dụng trong routes
def has_permission(permission):
    """Kiểm tra xem user hiện tại có permission không"""
    if not hasattr(g, 'user_permissions'):
        user_id = g.current_user['id']
        g.user_permissions = get_user_permissions(user_id)
    
    return permission in g.user_permissions

def has_any_permission(permissions):
    """Kiểm tra xem user hiện tại có ít nhất một permission không"""
    if not hasattr(g, 'user_permissions'):
        user_id = g.current_user['id']
        g.user_permissions = get_user_permissions(user_id)
    
    return any(perm in g.user_permissions for perm in permissions)

def has_all_permissions(permissions):
    """Kiểm tra xem user hiện tại có tất cả permissions không"""
    if not hasattr(g, 'user_permissions'):
        user_id = g.current_user['id']
        g.user_permissions = get_user_permissions(user_id)
    
    return all(perm in g.user_permissions for perm in permissions)

def has_role(role_name):
    """Kiểm tra xem user hiện tại có role không"""
    return g.current_user['role_name'] == role_name

def is_admin():
    """Kiểm tra xem user hiện tại có phải admin không"""
    return has_permission('system.admin') or has_role('admin')

# Middleware để tự động inject user info (optional)
def init_auth_middleware(app):
    """Khởi tạo auth middleware cho app"""
    @app.before_request
    def load_user():
        # Chỉ load user cho các API routes (check URL path instead of endpoint)
        if request.path.startswith('/api/'):
            auth_header = request.headers.get('Authorization')
            
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
                payload = verify_token(token)
                
                if payload:
                    g.current_user = {
                        'id': payload['user_id'],
                        'username': payload['username'],
                        'role_id': payload['role_id'],
                        'role_name': payload['role_name']
                    }
                    # Lazy load permissions khi cần
                    g._user_permissions = None
                else:
                    g.current_user = None
            else:
                g.current_user = None
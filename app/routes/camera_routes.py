from flask import Blueprint, jsonify, request
from app.services.camera_services import start, check, stop
from app.middleware.auth import require_permission, require_resource_access, admin_required
from app.config import Config
import mysql.connector

camera_bp = Blueprint('camera', __name__)

@camera_bp.route('/start/<id>', methods=['GET'])
@require_permission('security.manage')
def start_camera(id):
    try:
        start(id)
        return jsonify({"status": "Thành công", "message": "Camera đã được khởi động"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@camera_bp.route('/stop/<id>', methods=['GET'])
@require_permission('security.manage')
def stop_camera(id):
    try:
        stop(id)
        return jsonify({"status": "Thành công", "message": "Camera đã được dừng"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@camera_bp.route('/check/<id>', methods=['GET'])
@require_permission('security.view')
def check_camera_status(id):
    """Kiểm tra trạng thái camera"""
    try:
        is_running = check(id)
        return jsonify({
            "status": "success", 
            "camera_id": id,
            "is_running": is_running
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@camera_bp.route('/list', methods=['GET'])
@require_permission('security.view')
def get_camera_list():
    """Lấy danh sách cameras"""
    try:
        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT id, name, link, type, ip, username, status, location, created_at
            FROM camera
            ORDER BY name
        """)

        cameras = cursor.fetchall()
        return jsonify(cameras), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@camera_bp.route('/create', methods=['POST'])
@require_permission('security.manage')
def create_camera():
    """Tạo camera mới"""
    try:
        data = request.get_json()
        required_fields = ['name', 'link', 'type', 'location']
        
        if not data or not all(field in data for field in required_fields):
            return jsonify({"error": "Missing required fields"}), 400

        name = data['name']
        link = data['link']
        camera_type = data['type']
        location = data['location']
        ip = data.get('ip')
        username = data.get('username')
        password = data.get('password')

        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO camera (name, link, type, ip, username, password, location, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 1)
        """, (name, link, camera_type, ip, username, password, location))

        connection.commit()
        camera_id = cursor.lastrowid

        return jsonify({
            "message": "Camera created successfully",
            "camera_id": camera_id
        }), 201

    except mysql.connector.Error as e:
        if e.errno == 1062:  # Duplicate entry
            return jsonify({"error": "Camera name already exists"}), 409
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@camera_bp.route('/update/<int:camera_id>', methods=['PUT'])
@require_permission('security.manage')
def update_camera(camera_id):
    """Cập nhật thông tin camera"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing data"}), 400

        # Tạo câu query động
        update_fields = []
        params = []
        
        allowed_fields = ['name', 'link', 'type', 'ip', 'username', 'password', 'location', 'status']
        
        for field in allowed_fields:
            if field in data:
                update_fields.append(f"{field} = %s")
                params.append(data[field])

        if not update_fields:
            return jsonify({"error": "No fields to update"}), 400

        params.append(camera_id)
        query = f"UPDATE camera SET {', '.join(update_fields)} WHERE id = %s"

        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor()
        
        cursor.execute(query, params)
        
        if cursor.rowcount == 0:
            return jsonify({"error": "Camera not found"}), 404

        connection.commit()
        return jsonify({"message": "Camera updated successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@camera_bp.route('/delete/<int:camera_id>', methods=['DELETE'])
@require_permission('security.manage')
def delete_camera(camera_id):
    """Xóa camera"""
    try:
        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor()

        # Soft delete - chỉ cập nhật status
        cursor.execute("UPDATE camera SET status = 0 WHERE id = %s", (camera_id,))
        
        if cursor.rowcount == 0:
            return jsonify({"error": "Camera not found"}), 404

        connection.commit()
        return jsonify({"message": "Camera deleted successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@camera_bp.route('/bulk-action', methods=['POST'])
@require_permission('security.manage')
def bulk_camera_action():
    """Thực hiện hành động hàng loạt trên nhiều camera"""
    try:
        data = request.get_json()
        if not data or 'camera_ids' not in data or 'action' not in data:
            return jsonify({"error": "Missing camera_ids or action"}), 400

        camera_ids = data['camera_ids']
        action = data['action']

        if not isinstance(camera_ids, list) or not camera_ids:
            return jsonify({"error": "camera_ids must be a non-empty list"}), 400

        if action not in ['start', 'stop', 'enable', 'disable']:
            return jsonify({"error": "Invalid action. Must be: start, stop, enable, disable"}), 400

        results = []
        
        for camera_id in camera_ids:
            try:
                if action == 'start':
                    start(camera_id)
                    results.append({"camera_id": camera_id, "status": "started"})
                elif action == 'stop':
                    stop(camera_id)
                    results.append({"camera_id": camera_id, "status": "stopped"})
                elif action in ['enable', 'disable']:
                    status = 1 if action == 'enable' else 0
                    connection = mysql.connector.connect(**Config.DB_CONFIG)
                    cursor = connection.cursor()
                    cursor.execute("UPDATE camera SET status = %s WHERE id = %s", (status, camera_id))
                    connection.commit()
                    cursor.close()
                    connection.close()
                    results.append({"camera_id": camera_id, "status": action + "d"})
            except Exception as e:
                results.append({"camera_id": camera_id, "error": str(e)})

        return jsonify({
            "message": f"Bulk {action} completed",
            "results": results
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@camera_bp.route('/stream-status', methods=['GET'])
@require_permission('security.view')
def get_all_stream_status():
    """Lấy trạng thái stream của tất cả cameras"""
    try:
        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT id, name, location, status as db_status
            FROM camera
            WHERE status = 1
            ORDER BY name
        """)

        cameras = cursor.fetchall()
        
        # Kiểm tra trạng thái stream cho từng camera
        for camera in cameras:
            try:
                camera['stream_running'] = check(camera['id'])
            except:
                camera['stream_running'] = False

        return jsonify(cameras), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@camera_bp.route('/config/<int:camera_id>', methods=['GET'])
@require_permission('security.view')
def get_camera_config(camera_id):
    """Lấy cấu hình chi tiết của camera"""
    try:
        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT id, name, link, type, ip, username, location, status, created_at
            FROM camera
            WHERE id = %s
        """, (camera_id,))

        camera = cursor.fetchone()
        
        if not camera:
            return jsonify({"error": "Camera not found"}), 404

        # Kiểm tra trạng thái stream
        try:
            camera['stream_running'] = check(camera_id)
        except:
            camera['stream_running'] = False

        return jsonify(camera), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
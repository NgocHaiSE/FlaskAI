from flask import Blueprint, jsonify, request
from app.services.timekeeping_services import checkin_logic, checkout_logic, get_all, get_attendance_by_date, get_attendance_by_person_and_range, get_realtime_attendance
from app.middleware.auth import require_permission, require_any_permission, login_required, has_permission
import mysql.connector
from app.config import Config
import os
from werkzeug.utils import secure_filename
import base64
from io import BytesIO
from PIL import Image
import datetime

timekeeping_bp = Blueprint('timekeeping', __name__)

@timekeeping_bp.route('/get', methods=['GET'])
@require_permission('timekeeping.view')
def get():
    try:
        records = get_all()
        return jsonify(records), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@timekeeping_bp.route('/person/<person_id>', methods=['GET'])
@login_required
def get_person_attendance_by_range(person_id):
    """Lấy chấm công theo người và khoảng thời gian"""
    # Kiểm tra quyền: user có thể xem chấm công của chính mình, 
    # hoặc cần quyền timekeeping.view để xem của người khác
    from flask import g
    
    current_user_id = g.current_user['id']
    can_view_all = has_permission('timekeeping.view')
    
    # Chuyển đổi person_id thành user_id nếu cần
    if not can_view_all:
        # Kiểm tra xem person_id có phải của chính user hiện tại không
        try:
            connection = mysql.connector.connect(**Config.DB_CONFIG)
            cursor = connection.cursor()
            
            cursor.execute("""
                SELECT id FROM person WHERE id = %s AND user_id = %s
            """, (person_id, current_user_id))
            
            if not cursor.fetchone():
                return jsonify({'error': 'Access denied. You can only view your own attendance'}), 403
                
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()

    start_date = request.args.get('start')
    end_date = request.args.get('end')

    if not start_date or not end_date:
        return jsonify({'error': 'Thiếu tham số start hoặc end'}), 400

    try:
        records = get_attendance_by_person_and_range(person_id, start_date, end_date)
        return jsonify(records), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@timekeeping_bp.route('/attendance/<date>', methods=['GET'])
@require_permission('timekeeping.view')
def get_attendance(date):
    try:
        records = get_attendance_by_date(date)
        return jsonify(records), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@timekeeping_bp.route('/realtime', methods=['GET'])
@require_permission('timekeeping.view')
def realtime():
    try:
        records = get_realtime_attendance()
        return jsonify(records), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
      
@timekeeping_bp.route('/checkin', methods=['POST'])
@login_required  # Chỉ cần đăng nhập, không cần quyền đặc biệt
def checkin():
    try:
        data = request.get_json()
        if not data or 'file' not in data:
            return jsonify({"error": "Missing base64 image data"}), 400

        base64_image = data['file']
        if ',' in base64_image:
            base64_image = base64_image.split(',')[1]

        image_data = base64.b64decode(base64_image)
        image = Image.open(BytesIO(image_data))

        save_dir = Config.PATHS['timekeepings']
        os.makedirs(save_dir, exist_ok=True)
        filename = f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        save_path = os.path.join(save_dir, filename)
        image.save(save_path)

        # Gọi service để check-in
        result = checkin_logic(filename)

        if isinstance(result, dict) and result.get("status") == "error":
            return jsonify(result), 400
        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
      
@timekeeping_bp.route('/checkout', methods=['POST'])
@login_required  # Chỉ cần đăng nhập, không cần quyền đặc biệt
def checkout():
    try:
        data = request.get_json()
        if not data or 'file' not in data:
            return jsonify({"error": "Missing base64 image data"}), 400

        base64_image = data['file']
        if ',' in base64_image:
            base64_image = base64_image.split(',')[1]

        image_data = base64.b64decode(base64_image)
        image = Image.open(BytesIO(image_data))

        save_dir = Config.PATHS['timekeepings']
        os.makedirs(save_dir, exist_ok=True)
        filename = f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        save_path = os.path.join(save_dir, filename)
        image.save(save_path)

        # Gọi service để check-out
        result = checkout_logic(filename)

        if isinstance(result, dict) and result.get("status") == "error":
            return jsonify(result), 400
        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@timekeeping_bp.route('/attendance/stats', methods=['GET'])
@require_any_permission(['timekeeping.view', 'reports.view'])
def get_attendance_stats():
    """Lấy thống kê chấm công theo khoảng thời gian"""
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    
    if not start_date or not end_date:
        return jsonify({'error': 'Missing start or end parameter'}), 400

    try:
        conn = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        cursor.callproc('sp_get_attendance_stats_range', [start_date, end_date])

        results = []
        for result in cursor.stored_results():
            results = result.fetchall()

        return jsonify(results), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()

@timekeeping_bp.route('/attendance/stats/<person_id>', methods=['GET'])
@login_required
def get_personal_stats(person_id):
    """Lấy thống kê chấm công cá nhân"""
    # Kiểm tra quyền tương tự như get_person_attendance_by_range
    from flask import g
    
    current_user_id = g.current_user['id']
    can_view_all = has_permission('timekeeping.view')
    
    if not can_view_all:
        try:
            connection = mysql.connector.connect(**Config.DB_CONFIG)
            cursor = connection.cursor()
            
            cursor.execute("""
                SELECT id FROM person WHERE id = %s AND user_id = %s
            """, (person_id, current_user_id))
            
            if not cursor.fetchone():
                return jsonify({'error': 'Access denied. You can only view your own stats'}), 403
                
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()

    start = request.args.get('start')
    end = request.args.get('end')
    
    if not (person_id and start and end):
        return jsonify({"error": "Thiếu tham số"}), 400
        
    try:
        conn = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.callproc('sp_personal_attendance_stats', [person_id, start, end])
        
        result = {}
        for res in cursor.stored_results():
            result = res.fetchone()
            
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass

@timekeeping_bp.route('/recognitions')
@require_permission('security.view')
def get_recent_recognitions():
    """Lấy lịch sử nhận diện gần đây"""
    try:
        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor(dictionary=True) 
        
        cursor.execute("""
            SELECT fullname, personcode, location, time, image
            FROM face_application.recognise_history
            ORDER BY time DESC
            LIMIT 20
        """)
        
        records = cursor.fetchall()
        return jsonify(records), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@timekeeping_bp.route('/manual-checkin', methods=['POST'])
@require_permission('timekeeping.manage')
def manual_checkin():
    """Check-in thủ công cho nhân viên (chỉ dành cho quản lý)"""
    try:
        data = request.get_json()
        if not data or 'person_id' not in data:
            return jsonify({"error": "Missing person_id"}), 400

        person_id = data['person_id']
        check_time = data.get('check_time')  # Optional, default to now
        
        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor()

        if check_time:
            cursor.callproc('sp_manual_check_in', [person_id, check_time])
        else:
            cursor.callproc('sp_check_in', [person_id, 'manual_checkin'])

        connection.commit()
        return jsonify({"message": "Manual check-in successful"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@timekeeping_bp.route('/manual-checkout', methods=['POST'])
@require_permission('timekeeping.manage')
def manual_checkout():
    """Check-out thủ công cho nhân viên (chỉ dành cho quản lý)"""
    try:
        data = request.get_json()
        if not data or 'person_id' not in data:
            return jsonify({"error": "Missing person_id"}), 400

        person_id = data['person_id']
        check_time = data.get('check_time')  # Optional, default to now
        
        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor()

        if check_time:
            cursor.callproc('sp_manual_check_out', [person_id, check_time])
        else:
            cursor.callproc('sp_check_out', [person_id, 'manual_checkout'])

        connection.commit()
        return jsonify({"message": "Manual check-out successful"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
from flask import Blueprint, jsonify, request
from app.services.timekeeping_services import  checkin_logic, checkout_logic, get_all,get_attendance_by_date, get_attendance_by_person_and_range, get_realtime_attendance
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
def get():
    try:
        records = get_all()
        return jsonify(records), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@timekeeping_bp.route('/person/<person_id>', methods=['GET'])
def get_person_attendance_by_range(person_id):
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
def get_attendance(date):
    try:
        records = get_attendance_by_date(date)
        return jsonify(records), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@timekeeping_bp.route('/realtime', methods=['GET'])
def realtime():
    try:
        records = get_realtime_attendance()
        return jsonify(records), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
      
      
@timekeeping_bp.route('/checkin', methods=['POST'])
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

        # Gọi service để check-in (sẽ gọi sp_check_in(employee_id, photo_url))
        result = checkin_logic(filename)

        if isinstance(result, dict) and result.get("status") == "error":
            return jsonify(result), 400
        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
      
      
@timekeeping_bp.route('/checkout', methods=['POST'])
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

        # Gọi service để check-out (sẽ gọi sp_check_out(employee_id, photo_url))
        result = checkout_logic(filename)

        if isinstance(result, dict) and result.get("status") == "error":
            return jsonify(result), 400
        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

@timekeeping_bp.route('/attendance/stats', methods=['GET'])
def get_attendance_stats():
    start_date = request.args.get('start')
    end_date   = request.args.get('end')
    if not start_date or not end_date:
        return jsonify({'error': 'Missing start or end parameter'}), 400

    try:
        conn = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # Gọi stored procedure
        cursor.callproc('sp_get_attendance_stats_range', [start_date, end_date])

        # Lấy kết quả từ cursor
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
def get_personal_stats(person_id):
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
def get_recent_recognitions():
    connection = mysql.connector.connect(**Config.DB_CONFIG)
    cursor = connection.cursor(dictionary=True) 
    cursor.execute("""
        SELECT fullname, personcode, location, time, image
        FROM face_application.recognise_history
        ORDER BY time DESC
        LIMIT 20
    """)
    records = cursor.fetchall()
    return jsonify(records)
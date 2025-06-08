import mysql.connector
from mysql.connector import Error
from app.config import Config
from datetime import datetime
from app.utils.recognise import match_face_embedding


def get_all():
    try:
        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor(dictionary=True) 
        cursor.callproc('GetAllTimekeepingRecords')
        results = []
        for result in cursor.stored_results():
            results = result.fetchall()

        return results

    except Error as e:
        raise Exception(f"Error executing stored procedure: {str(e)}")

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

def get_attendance_by_person_and_range(person_id, start_date, end_date):
    try:
        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor(dictionary=True)
        cursor.callproc('sp_get_attendance_by_person_and_range', [person_id, start_date, end_date])
        results = []
        for result in cursor.stored_results():
            results.extend(result.fetchall())
        return results

    except Error as e:
        raise Exception(f"Error executing stored procedure: {str(e)}")

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


def get_attendance_by_date(date_str):
    """
    Gọi stored procedure sp_get_attendance_by_date
    trả về toàn bộ chấm công ngày date_str (format: 'YYYY-MM-DD').
    """
    connection = None
    cursor = None
    try:
        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor(dictionary=True)

        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        cursor.callproc('sp_get_attendance_by_date', [date_obj])

        results = []
        for res in cursor.stored_results():
            results.extend(res.fetchall())
        return results

    except Exception as e:
        raise Exception(f"Error executing sp_get_attendance_by_date: {str(e)}")

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
            
def get_realtime_attendance():
    """
    Gọi stored procedure sp_get_realtime_attendance()
    để lấy danh sách nhân viên đã check-in nhưng chưa check-out của ngày hôm nay.
    """
    connection = None
    cursor = None
    try:
        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor(dictionary=True)

        cursor.callproc('sp_get_realtime_attendance')

        results = []
        for res in cursor.stored_results():
            results.extend(res.fetchall())
        return results

    except Exception as e:
        raise Exception(f"Error executing sp_get_realtime_attendance: {str(e)}")

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

def checkin_logic(file_name):
    """
    1. Nhận tham số file_name (tên file hoặc đường dẫn file ảnh).
    2. Gọi match_face_embedding(file_name) để lấy (confidence, personcode).
    3. Truy vấn bảng Employee để lấy employee_id từ personcode.
    4. Gọi stored procedure sp_check_in(employee_id, photo_url).
    """
    # 1. Nhận kết quả nhận diện gương mặt
    result = match_face_embedding(file_name)
    if not result or len(result) < 2:
        return {"status": "error", "message": "Không xác định được personcode từ ảnh"}
    person_id = result[0]

    connection = None
    cursor = None
    try:
        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor()

        # 2. Lấy employee_id từ personcode
        # sql_lookup = "SELECT id FROM Person WHERE code = %s AND status = 1 LIMIT 1"
        # cursor.execute(sql_lookup, (personcode,))
        # row = cursor.fetchone()
        # if not row:
        #     return {"status": "error", "message": f"Không tìm thấy nhân viên với mã = {personcode}"}
        # person_id = row[0]

        # 3. Gọi stored procedure sp_check_in(employee_id, photo_url)
        #    photo_url ở đây có thể là đường dẫn (relative path) tới file_name
        cursor.callproc('sp_check_in', [person_id, file_name])
        connection.commit()
        return {"status": "success", "message": "Check-in thành công"}

    except Error as e:
        return {"status": "error", "message": f"Error calling sp_check_in: {str(e)}"}

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
            
def checkout_logic(file_name):
    """
    Tương tự checkin_logic, nhưng gọi sp_check_out(employee_id, photo_url).
    """
    result = match_face_embedding(file_name)
    if not result or len(result) < 2:
        return {"status": "error", "message": "Không xác định được personcode từ ảnh"}
    person_id = result[0]

    connection = None
    cursor = None
    try:
        connection = mysql.connector.connect(**Config.DB_CONFIG)
        cursor = connection.cursor()

        # 1. Lấy employee_id từ personcode
        # sql_lookup = "SELECT id FROM Person WHERE code = %s AND status = 1 LIMIT 1"
        # cursor.execute(sql_lookup, (personcode,))
        # row = cursor.fetchone()
        # if not row:
        #     return {"status": "error", "message": f"Không tìm thấy nhân viên với mã = {personcode}"}
        # person_id = row[0]

        # 2. Gọi stored procedure sp_check_out(employee_id, photo_url)
        cursor.callproc('sp_check_out', [person_id, file_name])
        connection.commit()
        return {"status": "success", "message": "Check-out thành công"}

    except Error as e:
        return {"status": "error", "message": f"Error calling sp_check_out: {str(e)}"}

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
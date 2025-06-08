from flask import Flask, request, redirect, url_for, send_from_directory, jsonify
import os
from reloadEmbeding import reloadEmbeding
import cv2
import numpy as np
import base64
import datetime
from addFace import addFace
import subprocess
from MySQLConnector import getConnector
from flask_cors import CORS

from addcamera import check_rtsp_camera
app = Flask(__name__)


# CORS(app, resources={r"/*": {"origins": "http://192.168.*.*"}})
CORS(app)

dict_processes = {}
TEMP_FACE_FOLDER = 'temp_faces'
NOTI_UPLOAD_FOLDER = 'notifications'
FACE_UPLOAD_FOLDER = 'faces'
AVATAR_UPLOAD_FOLDER = 'avatars'
INFO_UPLOAD_FOLDER = 'info'
TIMEKEEPING_UPLOAD_FOLDER = 'timekeeping'
app.config['info'] = INFO_UPLOAD_FOLDER
app.config['avatars'] = AVATAR_UPLOAD_FOLDER
app.config['notifications'] = NOTI_UPLOAD_FOLDER
app.config['faces'] = FACE_UPLOAD_FOLDER
app.config['temp_faces'] = TEMP_FACE_FOLDER
app.config['timekeeping'] = TIMEKEEPING_UPLOAD_FOLDER

for folder in [INFO_UPLOAD_FOLDER, FACE_UPLOAD_FOLDER, NOTI_UPLOAD_FOLDER, AVATAR_UPLOAD_FOLDER, TEMP_FACE_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)
    
reloadEmbeding()

import sys
import cv2
import os
import numpy as np
import pickle
import base64
import subprocess
from datetime import datetime
from flask import request, jsonify
from MySQLConnector import getConnector



@app.route('/timekeeping', methods=['POST'])
def process_face_recognition():
    try:
        # Nhận dữ liệu ảnh từ request
        data = request.json
        image_base64 = data.get('image')

        if not image_base64:
            return jsonify({"error": "Không có ảnh được gửi"}), 400

        # Loại bỏ tiền tố base64 nếu có
        if ',' in image_base64:
            image_base64 = image_base64.split(',')[1]

        # Giải mã ảnh
        image_bytes = base64.b64decode(image_base64)
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if image is None:
            return jsonify({"error": "Không thể giải mã ảnh"}), 400

        # Tạo thư mục lưu ảnh nếu chưa tồn tại
        os.makedirs('timekeeping', exist_ok=True)

        # Tạo tên file duy nhất
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f'timekeeping/capture_{timestamp}.jpg'

        # Lưu ảnh
        cv2.imwrite(filename, image)

        # Gọi script nhận diện khuôn mặt
        try:
            result = subprocess.run(
                ['python', 'faceRecognise.py', filename], 
                capture_output=True, 
                text=True, 
                timeout=30
            )
            
            # Phân tích kết quả từ subprocess
            if result.returncode == 0:
                # Nếu thành công
                return jsonify({
                    "status": "success", 
                    "message": result.stdout.strip(),
                    "file": filename
                }), 200
            else:
                # Nếu có lỗi
                return jsonify({
                    "status": "error", 
                    "message": result.stderr.strip()
                }), 500

        except subprocess.TimeoutExpired:
            return jsonify({
                "status": "error", 
                "message": "Quá trình nhận diện mất quá nhiều thời gian"
            }), 504
        except Exception as e:
            return jsonify({
                "status": "error", 
                "message": str(e)
            }), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

# Route để truy cập và hiển thị ảnh thông báo
@app.route('/timekeeping/<filename>')
def face_timekeeping(filename):
    return send_from_directory(app.config['timekeeping'], filename)
    
    
# Route để upload ảnh thông báo
@app.route('/upload-noti', methods=['POST'])
def upload_noti():
    if 'file' not in request.files:
        return 'No file part', 400
    file = request.files['file']
    if file.filename == '':
        return 'No selected file', 400
    if file:
        filepath = os.path.join(app.config['notifications'], file.filename)
        file.save(filepath)
        return f"Tải ảnh lên thành công: {file.filename}", 200

# Route để truy cập và hiển thị ảnh thông báo
@app.route('/notifications/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['notifications'], filename)

# Route để upload ảnh face
@app.route('/upload-face', methods=['POST'])
def upload_face():
    if 'file' not in request.files:
        return 'No file part', 400
    
    file = request.files['file']
    if file.filename == '':
        return 'No selected file', 400
    
    filepath = os.path.join(app.config['faces'], file.filename)
        
    if os.path.exists(filepath):
        return "Ảnh đã tồn tại trong thư mục. Vui lòng chọn ảnh khác.", 409  

    if file:
        filepath = os.path.join(app.config['temp_faces'], file.filename)
        file.save(filepath)      
        count_face = addFace(filepath)
        
        if count_face == 1:
            reloadEmbeding()
            return f"Ảnh đạt yêu cầu với một khuôn mặt: {file.filename}", 200
        elif count_face == 0:
            return "Không phát hiện khuôn mặt trong hình", 400
        elif count_face > 1:
            return "Phát hiện nhiều hơn một khuôn mặt trong hình", 400

# Route để truy cập và hiển thị ảnh thông báo
@app.route('/face/<filename>')
def uploaded_face(filename):
    return send_from_directory(app.config['faces'], filename)

# Route láy tất cả ảnh
@app.route('/get-images/<personId>', methods=['GET'])
def get_images(personId):
    conn = getConnector()
    cursor = conn.cursor()
    sql_select_images = "SELECT link FROM image WHERE personid = %s"
    
    try:
        cursor.execute(sql_select_images, (personId,))
        images = cursor.fetchall()
        image_paths = [image[0] for image in images]

        return jsonify(image_paths), 200
    except Exception as e:
        return jsonify({"Lỗi": str(e)}), 500
    finally:
        cursor.close()
        conn.close()
        

@app.route('/add-images', methods=['POST'])
def add_images():
    # Kiểm tra yêu cầu JSON có mã, personid và file không
    if 'code' not in request.form or 'personid' not in request.form or 'filenames' not in request.files:
        return "Thiếu dữ liệu yêu cầu hoặc file", 400

    personid = request.form['personid']
    code = request.form['code']
    files = request.files.getlist('filenames')
    
    conn = getConnector()
    cursor = conn.cursor()

    # Xác định thư mục faces để lưu file
    save_folder = app.config['faces']
    temp_folder = app.config['temp_faces']
    
    values_to_insert = []
    saved_filepaths = []
    temp_filepaths = []

    sql_insert_image = "INSERT INTO image(personcode, link, personid) VALUES (%s, %s, %s)"
    
    try:
        for file in files:
            if file.filename == '':
                raise ValueError("Không có file được chọn")
            
            filename = f"{code}_{file.filename}"
            temp_filepath = os.path.join(temp_folder, filename)
            final_filepath = os.path.join(save_folder, filename)
            
            file.save(temp_filepath)
            temp_filepaths.append(temp_filepath)
            
            count_face = addFace(temp_filepath)
            if count_face == 1:
                # Di chuyển file từ temp sang thư mục chính
                os.rename(temp_filepath, final_filepath)
                saved_filepaths.append(final_filepath)
                values_to_insert.append((code, filename, personid))
            elif count_face == 0:
                raise ValueError(f"Không phát hiện khuôn mặt trong hình: {filename}")
            elif count_face > 1:
                raise ValueError(f"Phát hiện nhiều hơn một khuôn mặt trong hình: {filename}")
            
        cursor.executemany(sql_insert_image, values_to_insert)
        conn.commit()
        reloadEmbeding()  # Giả sử reloadEmbeding() cần gọi sau khi thêm ảnh thành công
        return "Cập nhật và lưu đường dẫn hình ảnh thành công", 200
            
            # Lưu file và lưu đường dẫn vào list để rollback nếu cần
    except Exception as e:
        # Rollback cơ sở dữ liệu và xóa các file đã lưu
        conn.rollback()
        for path in saved_filepaths:
            if os.path.exists(path):
                os.remove(path)
        for temp_path in temp_filepaths:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        return f"Lỗi khi cập nhật và lưu hình ảnh: {str(e)}", 500

    finally:
        cursor.close()
        conn.close()


@app.route('/delete-person/<personcode>', methods=['DELETE'])
def delete_person(personcode):
    faces_dir = app.config['faces']
    avatars_dir = app.config['avatars']
    
    deleted_files = []

    # Helper function to delete files in a given directory
    def delete_files_with_prefix(directory, prefix):
        for filename in os.listdir(directory):
            if filename.startswith(prefix):
                filepath = os.path.join(directory, filename)
                try:
                    os.remove(filepath)
                    deleted_files.append(filepath)
                except Exception as e:
                    return jsonify({"Lỗi": f"Không thể xóa {filepath}: {str(e)}"}), 500
    # Delete files in faces and avatars directories
    delete_files_with_prefix(faces_dir, personcode)
    delete_files_with_prefix(avatars_dir, personcode)
    conn = getConnector()
    cursor = conn.cursor()
    try:
        sql_delete_images = "DELETE FROM image WHERE personcode = %s"
        cursor.execute(sql_delete_images, (personcode,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        return jsonify({"Lỗi": f"Không thể xóa dữ liệu trong bảng image: {str(e)}"}), 500
    finally:
        cursor.close()
        conn.close()
    # Respond with the list of deleted files
    return jsonify({"File đã xóa": deleted_files}), 200


@app.route('/delete-image/<filename>', methods=['DELETE'])
def delete_image(filename):
    file_path = os.path.join(app.config['faces'], filename)
    
    if not os.path.exists(file_path):
        return jsonify({"error": "Không tìm thấy ảnh"}), 404
    
    conn = getConnector()
    cursor = conn.cursor()
    
    try:
        cursor.execute("START TRANSACTION")
        os.remove(file_path)
        cursor.callproc('DeleteImage', (filename,))
        conn.commit() 
        return jsonify({"message": "Xóa ảnh thành công"}), 200
    except Exception as e:
        conn.rollback()  # Rollback nếu có lỗi
        return jsonify({"error": f"Lỗi khi xóa ảnh: {str(e)}"}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/upload-avatar/<code>', methods=['POST'])
def upload_avatar(code):
    conn = getConnector()
    cursor = conn.cursor()
    sql_check_user = "SELECT id FROM person WHERE code = %s"
    try:
        cursor.execute(sql_check_user, (code,))
        result = cursor.fetchone()

        if not result:
            return f"Không tìm thấy cán bộ có mã {code}.", 404

        if 'file' not in request.files:
            return 'Chưa thêm ảnh', 400

        file = request.files['file']
        if file.filename == '':
            return 'Chưa chọn ảnh', 400

        if file:
            # Save the file in the avatar folder
            filename = f"{code}_avatar.png"
            filepath = os.path.join(app.config['avatars'], filename)
            file.save(filepath)

            # Update the database with the new avatar path
            sql_update_avatar = "UPDATE person SET avatar_path = %s WHERE code = %s"
            cursor.execute(sql_update_avatar, (filename, code))
            conn.commit()
            
            return "Cập nhật ảnh đại diện thành công", 200

    except Exception as e:
        conn.rollback()
        return f"Lỗi khi cập nhật ảnh đại diện: {str(e)}", 500

    finally:
        cursor.close()
        conn.close()


@app.route('/avatar/<filename>')
def get_avatar(filename):
    return send_from_directory(app.config['avatars'], filename)


# API giới thiệu
@app.route('/about', methods=['GET'])
def about():
    intro = {
        "message": "Chào mừng đến với API của chúng tôi!",
        "description": "Đây là một API đơn giản để upload và hiển thị ảnh.",
        "endpoints": {
            "upload": "/upload",
            "view_image": "/uploads/<filename>"
        }
    }
    return jsonify(intro)


#--------------------------------------------------------------
@app.route('/start/<CAMERA_ID>')
def start(CAMERA_ID):
    process = subprocess.Popen(['python', 'pub.py',str(CAMERA_ID)])
    dict_processes[CAMERA_ID] = process
    return f"Khởi dộng camera {CAMERA_ID} thành công", 200

@app.route('/check/<CAMERA_ID>')
def check(CAMERA_ID):
    if int(CAMERA_ID)  in dict_processes:
        status = dict_processes[int(CAMERA_ID)].poll()
        if status is None:
            print("Tiến trình đang chạy.")
            return f"Tiến trình {CAMERA_ID} đang chạy", 200
        else:
            print(f"Tiến trình đã kết thúc với mã trạng thái: {status}")
            return f"Tiến trình {CAMERA_ID} đã kết thúc với mã trạng thái: {status}", 200
    elif CAMERA_ID  in dict_processes:
        status = dict_processes[CAMERA_ID].poll()
        if status is None:
            print("Tiến trình đang chạy.")
            return f"Tiến trình {CAMERA_ID} đang chạy", 200
        else:
            print(f"Tiến trình đã kết thúc với mã trạng thái: {status}")
            return f"Tiến trình {CAMERA_ID} đã kết thúc với mã trạng thái: {status}", 200
    else:
        print("Không có tiến trình: ",CAMERA_ID)
        return f"Tiến trình {CAMERA_ID} không tồn tại",200
    
@app.route('/stop/<CAMERA_ID>')
def stop(CAMERA_ID):
    if int(CAMERA_ID) in dict_processes:
        dict_processes[int(CAMERA_ID)].terminate()
        return f"Đã kết thúc tiến trình {CAMERA_ID}",200
    elif CAMERA_ID in dict_processes:
        dict_processes[CAMERA_ID].terminate()
        return f"Đã kết thúc tiến trình {CAMERA_ID}",200
    else:
        return f"Tiến trình {CAMERA_ID} không tồn tại",200

@app.route('/startall')
def startall():
    conn = getConnector()
    cursor = conn.cursor()
    cursor.execute("select camera.id from camera where isactivate=1")
    list_cam = cursor.fetchall()
    for cam, in list_cam:
        start(cam)
        print('start',cam)
    # Đóng kết nối
    cursor.close()
    conn.close()
    return f"{len(list_cam)} Tiến trình đã được bật",200

@app.route('/getall')
def getall():
    keys_list = list(dict_processes.keys())
    return jsonify(keys_list)


@app.route('/addCam/<CAMERA_ID>')
def addCam(CAMERA_ID):
    conn = getConnector()
    cursor = conn.cursor()
    cursor.execute("SELECT link,name,status,type FROM face_application.camera where id="+CAMERA_ID+";")
    camera_infor = cursor.fetchone()
    camera_link,camera_name,camera_status,camera_type = camera_infor
    if check_rtsp_camera(camera_link):
        start(CAMERA_ID)
        return f"Camera {CAMERA_ID}: hoạt động ",200
    else:
        return f"Camera {CAMERA_ID}: lỗi",400
    
@app.route('/checkLink/<CAMERA_LINK>')
def checkCam(CAMERA_LINK):
    if check_rtsp_camera(CAMERA_LINK):
        return f"OK",200
    else:
        return f"Lỗi",400
    
@app.route('/stopall')
def stoptall():
    keys_list = list(dict_processes.keys())
    for key in keys_list:
        CAMERA_ID = key
        if int(CAMERA_ID) in dict_processes:
            dict_processes[int(CAMERA_ID)].terminate()
            print("Đã kết thúc tiến trình {CAMERA_ID}")
        elif CAMERA_ID in dict_processes:   
            dict_processes[CAMERA_ID].terminate()
            print(f"Đã kết thúc tiến trình {CAMERA_ID}")
        else:
            print(f"Tiến trình {CAMERA_ID} không tồn tại") 

    return f"{len(keys_list)} Tiến trình đã được tắt",200  

#--------------------------------------------------------------
# Chạy server Flask
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, threaded=True)

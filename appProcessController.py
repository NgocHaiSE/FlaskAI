from flask import Flask, request, redirect, url_for, send_from_directory, jsonify
import os
from reloadEmbeding import reloadEmbeding
import subprocess
from MySQLConnector import getConnector
from addcamera import check_rtsp_camera


app = Flask(__name__)
dict_processes = {}

@app.route('/start/<CAMERA_ID>')
def start(CAMERA_ID):
    process = subprocess.Popen(['python', 'pub.py',str(CAMERA_ID)])
    dict_processes[CAMERA_ID] = process
    return f"Khởi chạy camera {CAMERA_ID} thành công", 200

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
    else:
        print("Không có tiến trình: ",CAMERA_ID)
        return f"Tiến trình {CAMERA_ID} không tồn tại",200
    
@app.route('/stop/<CAMERA_ID>')
def stop(CAMERA_ID):
    if int(CAMERA_ID) in dict_processes:
        dict_processes[int(CAMERA_ID)].terminate()
        return f"Đã kết thúc tiến trình {CAMERA_ID}",200
    else:
        return f"Tiến trình {CAMERA_ID} không tồn tại",200

@app.route('/startall')
def startall():
    conn = getConnector()
    cursor = conn.cursor()
    cursor.execute("select camera.id from camera where is_activate=1")
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
    camera_link,camera_name,camera_is_recog,camera_type = camera_infor
    if check_rtsp_camera(camera_link):
        start(CAMERA_ID)
        return f"Camera link {CAMERA_ID}: hoạt động ",200
    else:
        return f"Camera link {CAMERA_ID}: lỗi",400
    
@app.route('/checkLink/<CAMERA_LINK>')
def checkCam(CAMERA_LINK):
    if check_rtsp_camera(CAMERA_LINK):
        return f"OK",200
    else:
        return f"NOT OK",400
    

# Chạy server Flask
if __name__ == '__main__':
    startall()
    app.run(host='0.0.0.0', port=8000)
    
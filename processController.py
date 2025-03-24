import subprocess
from MySQLConnector import getConnector

dict_processes = {}

def start(CAMERA_ID):
    process = subprocess.Popen(['python', 'gait.py',str(CAMERA_ID)])
    dict_processes[CAMERA_ID] = process
    
def check(CAMERA_ID):
    if CAMERA_ID in dict_processes:
        status = dict_processes[CAMERA_ID].poll()
        if status is None:
            print("Tiến trình đang chạy.")
            return True
        else:
            print(f"Tiến trình đã kết thúc với mã trạng thái: {status}")
            return False
    else:
        print("Không có tiến trình: ",CAMERA_ID)
        return False
    
def stop(CAMERA_ID):
    if CAMERA_ID in dict_processes:
        dict_processes[CAMERA_ID].terminate()
    
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

check('1')
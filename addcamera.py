import cv2
from MySQLConnector import getConnector

def check_rtsp_camera(rtsp_link):
    cap = cv2.VideoCapture(rtsp_link)

    try:
        if not cap.isOpened():
            print("Không thể kết nối với camera.")
            return False

        ret, frame = cap.read()

        if ret:
            print("Kết nối thành công và đọc được khung hình.")
            cv2.imshow("Khung hình", frame)
            cv2.waitKey(1000)
            cv2.destroyAllWindows()
            return True
        else:
            print("Kết nối được nhưng không thể đọc khung hình.")
            return False
    finally:
        cap.release()  # Đảm bảo luôn giải phóng camera
        


def addCamera(CAMERA_ID):
    conn = getConnector()
    cursor = conn.cursor()
    cursor.execute("SELECT link,name,status,type FROM face_application.camera where id="+CAMERA_ID+";")
    camera_infor = cursor.fetchone()
    camera_link,camera_name,camera_status,camera_type = camera_infor
    
    check_rtsp_camera(camera_link)
    
    
    
    
    return 0
    

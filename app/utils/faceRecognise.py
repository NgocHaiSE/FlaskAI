import sys
import cv2
import os
import numpy as np
import pickle
from datetime import datetime
from MySQLConnector import getConnector

def process_single_image(image_path):
    # Kiểm tra tồn tại của ảnh
    if not os.path.exists(image_path):
        print(f"Error: can't find {image_path}")
        sys.exit(1)

    # Đọc ảnh
    frame = cv2.imread(image_path)
    if frame is None:
        print(f"error reading: {image_path}")
        sys.exit(1)

    # Kết nối CSDL
    conn = getConnector()
    cursor = conn.cursor()

    # Đường dẫn đến file chứa embeddings đã lưu
    input_file = "embeddings.pkl"

    # Đọc mảng embeddings từ file
    with open(input_file, 'rb') as f:
        personIds, showpersonIds, embeddings = pickle.load(f)

    # Load YuNet model
    face_detector = cv2.FaceDetectorYN.create("./weights/face_detection_yunet_2023mar.onnx", "", (640, 480))
    
    # Tải mô hình SFace để nhận diện khuôn mặt
    sface_model = cv2.FaceRecognizerSF.create("./weights/face_recognition_sface_2021dec.onnx", "")

    # Cài đặt các ngưỡng
    SCORE_THRESH = 0.5
    IOU_THRESH = 0.5

    # Detect faces using YuNet
    h, w, _ = frame.shape
    face_detector.setInputSize((w, h))
    faces = face_detector.detect(frame)

    faces = faces[1]  # faces is a tuple (retval, faces)
    if faces is None:
        faces = []
        print("Can't detect face")
        sys.exit(1)

    # Chuẩn bị truy vấn insert cho CSDL
    insert_query = """
    INSERT INTO timekeeping 
    (personcode, time, location, image_url, score)
    VALUES (%s, %s, %s, %s, %s)
    """

    # Xử lý từng khuôn mặt
    for face in faces:
        x, y, w, h = face[:4].astype(np.int32)
        bbox = (x, y, w, h)

        # Căn chỉnh và trích xuất đặc trưng khuôn mặt
        aligned_face = sface_model.alignCrop(frame, face)
        feature = sface_model.feature(aligned_face)

        # Nhận diện khuôn mặt
        detected = False
        matched_person_id = None
        matched_dist = 0

        for i in range(len(embeddings)):
            dist = sface_model.match(embeddings[i], feature)
            if dist > SCORE_THRESH:
                detected = True
                matched_person_id = showpersonIds[i]
                matched_dist = dist
                break

        # Ghi vào CSDL nếu nhận diện được
        if detected:
            try:
                # Sử dụng tên file gốc đã được tạo từ hàm process_face_recognition
                img_name = os.path.basename(image_path)
                data = (
                    matched_person_id, 
                    datetime.now(), 
                    'Đại đội 157',
                    img_name, 
                    matched_dist, 
                )
                cursor.execute(insert_query, data)
                conn.commit()
                print(f"Mã nhân viên: {matched_person_id}")
                sys.exit(0)  # Thoát với mã trạng thái thành công
            except Exception as e:
                print(f"error writting db: {e}")
                sys.exit(1)
        else:
            print("Không nhận diện được khuôn mặt")
            sys.exit(1)

# Kiểm tra và xử lý đầu vào
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("provide image")
        sys.exit(1)
    
    image_path = sys.argv[1]
    process_single_image(image_path)
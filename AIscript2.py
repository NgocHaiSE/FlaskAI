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
        print(f"Lỗi: Không tìm thấy ảnh {image_path}")
        return

    # Đọc ảnh
    frame = cv2.imread(image_path)
    if frame is None:
        print(f"Lỗi: Không thể đọc ảnh {image_path}")
        return

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

    # Chuẩn bị truy vấn insert cho CSDL
    insert_query = """
    INSERT INTO timekeeping 
    (personid, imagelink, date, score, x, y, w, h)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """

    # Thư mục lưu ảnh nhận dạng
    os.makedirs('timekeeping', exist_ok=True)

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

        # Vẽ hình chữ nhật và nhãn
        p1 = (int(bbox[0]), int(bbox[1]))
        p2 = (int(bbox[0] + bbox[2]), int(bbox[1] + bbox[3]))
        save_frame = frame.copy()
        cv2.rectangle(save_frame, p1, p2, (255, 0, 0), 2)

        # Tạo tên file
        d_time = datetime.now()
        img_name = f"timekeeping_{d_time.strftime('%Y-%m-%d_%H-%M-%S')}.jpg"
        img_name = img_name.replace(':', '-').replace(' ', '-')
        full_img_path = os.path.join('timekeeping', img_name)

        # Lưu ảnh
        cv2.imwrite(full_img_path, save_frame)

        # Ghi vào CSDL nếu nhận diện được
        if detected:
            try:
                data = (
                    matched_person_id, 
                    img_name, 
                    d_time, 
                    matched_dist, 
                    int(x), 
                    int(y), 
                    int(w), 
                    int(h)
                )
                cursor.execute(insert_query, data)
                conn.commit()
                print(f"Nhận diện thành công: {matched_person_id}")
            except Exception as e:
                print(f"Lỗi khi ghi vào CSDL: {e}")
        else:
            print("Không nhận diện được khuôn mặt")

    # Đóng kết nối CSDL
    cursor.close()
    conn.close()

    print(f"Đã xử lý xong ảnh: {image_path}")

# Kiểm tra và xử lý đầu vào
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Vui lòng cung cấp đường dẫn ảnh")
        sys.exit(1)
    
    image_path = sys.argv[1]
    process_single_image(image_path)
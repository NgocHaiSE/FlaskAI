import cv2
import numpy as np
import os
import pickle
from MySQLConnector import getConnector
from app.config import Config

def reloadEmbeding():

    face_detector = cv2.FaceDetectorYN.create(Config.PATHS['yunet'], "", (640, 480))
    sface_model = cv2.FaceRecognizerSF.create(Config.PATHS['sface'], "")

    embeddings = []
    personIds = []
    showpersonIds = []
    # Kết nối tới MySQL
    conn = getConnector()
    cursor = conn.cursor()
    cursor.execute("SELECT image.link, person.id, person.code FROM image INNER JOIN person ON image.personcode = person.code")
    list_img = cursor.fetchall()

    # Đóng kết nối
    cursor.close()
    conn.close()
    count_face=0
    # Đọc danh sách các file ảnh trong thư mục
    for filename,idperson,showpersonID in list_img:
        if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            img_path = os.path.join(Config.PATHS['faces'], filename)
            img = cv2.imread(img_path)

            if img is None:
                print(f"Không thể đọc ảnh: {img_path}")
                continue

            h, w = img.shape[:2]
            face_detector.setInputSize((w, h))

            # Phát hiện khuôn mặt
            faces = face_detector.detect(img)

            if faces[1] is not None:
                count_face+=1
                faces = faces[1]
                for face in faces:
                    aligned_face = sface_model.alignCrop(img, face)
                    feature = sface_model.feature(aligned_face)
                    embeddings.append(feature)
                    personIds.append(idperson)
                    showpersonIds.append(showpersonID)
    print(count_face," / ",len(list_img))
    # Lưu mảng embeddings vào file

    out_arr = [personIds,showpersonIds,embeddings ]
    output_file = "embeddings.pkl"
    with open(output_file, 'wb') as f:
        pickle.dump(out_arr, f)

    print(f"Embeddings đã được lưu vào file {output_file}")
    return True
import sys
import cv2
import os
import numpy as np
import pickle
import zmq
import time
from datetime import datetime
from MySQLConnector import getConnector

def send_notification(person_id, camera_id, img_path):
    """Gửi thông báo qua ZeroMQ"""
    notification_data = {
        "person_id": person_id,
        "camera_id": camera_id,
        "image_path": img_path,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    socket.send_json(notification_data)


if len(sys.argv) > 1:
    CAMERA_ID = sys.argv[1]
else:
    print("Không đủ biến truyền vào.")
    sys.exit()

# Thiết lập ZeroMQ
context = zmq.Context()
socket = context.socket(zmq.PUB)
port = 8000 + int(CAMERA_ID)
socket.bind(f"tcp://*:{port}")

#Đọc thông tin camera
conn = getConnector()
cursor = conn.cursor()
cursor.execute("SELECT link, name, status, type FROM face_application.camera where id="+CAMERA_ID+";")
camera_infor = cursor.fetchone()

camera_link,camera_name,camera_status,camera_type = camera_infor
insert_query = """
INSERT INTO notification (personid, cameraid, imagelink, date, score, trackid, x, y, w, h)
VALUES (%s, %s, %s, %s, %s, %s, %s,%s, %s, %s)
"""

if int(camera_type) == 0:
    cap = cv2.VideoCapture(int(camera_link))
    print('webcam')
else:
    cap = cv2.VideoCapture(camera_link)
    print("Sử dụng RTSP URL với UDP.")
SCORE_THRESH = 0.5
IOU_THRESH = 0.5

# Đường dẫn đến file chứa embeddings đã lưu
input_file = "embeddings.pkl"

# Đọc mảng embeddings từ file
with open(input_file, 'rb') as f:
    personIds,showpersonIds,embeddings = pickle.load(f)
    
# Load YuNet model
face_detector = cv2.FaceDetectorYN.create("./weights/face_detection_yunet_2023mar.onnx", "", (640, 480))
# Tải mô hình SFace để nhận diện khuôn mặt
sface_model = cv2.FaceRecognizerSF.create("./weights/face_recognition_sface_2021dec.onnx", "")


# Lists to keep track of trackers and bounding boxes
trackers = []
bboxes = []
detected_face_ids = []
detected_face_ids_show = []
next_id = 0

def assign_new_id():
    global next_id
    new_id = next_id
    next_id += 1
    return "NA_"+str(new_id)

def send_frame(camera_index, frame):
    topic = "newframe"
    _, buffer = cv2.imencode('.jpg', frame)
    socket.send_string(topic, zmq.SNDMORE)
    socket.send(buffer.tobytes())
    
while True:
    ret, frame = cap.read()
    if not ret:
        print("Failed to read frame from video capture")
        time.sleep(1)
        continue

    # Detect faces using YuNet
    h, w, _ = frame.shape
    face_detector.setInputSize((w, h))
    faces = face_detector.detect(frame)

    faces = faces[1]  # faces is a tuple (retval, faces)
    if faces is None:
        faces = []
    
    # Initialize a list for new detected faces
    new_bboxes = []
    new_face_ids = []
    old_bboxes = []
    old_face_ids =[]
    for face in faces:
        x, y, w, h = face[:4].astype(np.int32)
        bbox = (x, y, w, h)

        # Check if the detected face overlaps with any existing trackers
        matched = False
        for i, existing_bbox in enumerate(bboxes):
            
            # Calculate intersection over union (IoU) to check overlap
            xi1, yi1, xi2, yi2 = max(x, existing_bbox[0]), max(y, existing_bbox[1]), min(x+w, existing_bbox[0]+existing_bbox[2]), min(y+h, existing_bbox[1]+existing_bbox[3])
            inter_area = max(0, xi2 - xi1) * max(0, yi2 - yi1)
            bbox_area = (x+w - x) * (y+h - y)
            existing_bbox_area = existing_bbox[2] * existing_bbox[3]
            iou = inter_area / float(bbox_area + existing_bbox_area - inter_area)
            
            if iou > IOU_THRESH:
                if str(detected_face_ids[i]).startswith("NA"):
                    matched = False
                    print("NA")
                else:
                    matched = True
                    old_bboxes.append(bbox)
                    old_face_ids.append(detected_face_ids[i])
                    break
        
        if not matched:
            aligned_face = sface_model.alignCrop(frame, face)
            feature = sface_model.feature(aligned_face)
            detected = False
            for i in range(len(embeddings)):
                dist = sface_model.match(embeddings[i], feature)
                #print(f"Distance between face {i}: {dist}")
                if(dist > SCORE_THRESH):

                    detected=True
                    #store a image herre
                    p1 = (int(bbox[0]), int(bbox[1]))
                    p2 = (int(bbox[0] + bbox[2]), int(bbox[1] + bbox[3]))
                    save_frame = frame.copy()
                    
                    cv2.rectangle(save_frame, p1, p2, (255, 0, 0), 2)
                    d_time = datetime.now()
                    img_name = str(CAMERA_ID) + '_' + str(d_time)+'.jpg'
                    img_name = img_name.replace(':','-')
                    img_name = img_name.replace(' ','-')
                    print(img_name)
                    cv2.imwrite('notifications/'+img_name,save_frame)
                    
                    data = (personIds[i],CAMERA_ID,img_name, d_time,dist, 0,int(x),int(y),int(w),int(h))
                    cursor.execute(insert_query, data)
                    conn.commit()
                    
                    print(personIds[i])
                    new_bboxes.append(bbox)
                    new_face_ids.append(showpersonIds[i])
                    break
            if detected == False:
                new_bboxes.append(bbox)
                new_face_ids.append(assign_new_id())
                
                print("NA")

            if detected:
                # Sau khi phát hiện khuôn mặt
                p1 = (int(bbox[0]), int(bbox[1]))
                p2 = (int(bbox[0] + bbox[2]), int(bbox[1] + bbox[3]))
                save_frame = frame.copy()
                cv2.rectangle(save_frame, p1, p2, (255, 0, 0), 2)
                
                d_time = datetime.now()
                img_name = f"{CAMERA_ID}_{d_time}.jpg".replace(':', '-').replace(' ', '-')
                cv2.imwrite(f'notifications/{img_name}', save_frame)

                data = (personIds[i], CAMERA_ID, img_name, d_time, dist, 0, int(x), int(y), int(w), int(h))
                cursor.execute(insert_query, data)
                conn.commit()

                # Gửi thông báo qua ZeroMQ
                send_notification(personIds[i], CAMERA_ID, img_name)

                print(f"Thông báo gửi cho ID: {personIds[i]}, Hình ảnh: {img_name}")

    
    # Re-initialize trackers with new faces
    trackers = []
    bboxes = []
    detected_face_ids = []
    for i, bbox in enumerate(old_bboxes):
        tracker = cv2.TrackerCSRT_create()
        tracker.init(frame, tuple(bbox))
        trackers.append(tracker)
        bboxes.append(bbox)
        detected_face_ids.append(old_face_ids[i])
    for i, bbox in enumerate(new_bboxes):
        tracker = cv2.TrackerCSRT_create()
        tracker.init(frame, tuple(bbox))
        trackers.append(tracker)
        bboxes.append(bbox)
        detected_face_ids.append(new_face_ids[i])
    
    # Update trackers
    for i, tracker in enumerate(trackers):
        success, bbox = tracker.update(frame)
        if success:
            bboxes[i] = bbox
            p1 = (int(bbox[0]), int(bbox[1]))
            p2 = (int(bbox[0] + bbox[2]), int(bbox[1] + bbox[3]))
            cv2.rectangle(frame, p1, p2, (255, 0, 0), 2)
            
            if str(detected_face_ids[i]).startswith("NA"):
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.7
                color = (255, 0, 0)  # Màu chữ (xanh )
                thickness = 2
                text_position = (p1[0], p1[1] - 10)  # Đặt chữ ngay trên hình chữ nhật (10 pixel phía trên)
                cv2.putText(frame,"NA" , text_position, font, font_scale, color, thickness)
            else:
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.7
                color = (0, 255, 0)  # Màu chữ (xanh lá cây)
                thickness = 2
                text_position = (p1[0], p1[1] - 10)  # Đặt chữ ngay trên hình chữ nhật (10 pixel phía trên)
                cv2.putText(frame,""+str(detected_face_ids[i]) , text_position, font, font_scale, color, thickness)
        else:
            cv2.putText(frame, "Tracking failure detected", (100, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 255), 2)
    
    # Display the frame
    send_frame(0, frame)
    
    if datetime.now().second % 10 == 0:
        with open(input_file, 'rb') as f:
            personIds,showpersonIds,embeddings = pickle.load(f)
    cv2.imshow('Face Detection and Tracking', frame)
    
    # Exit if ESC pressed
    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()




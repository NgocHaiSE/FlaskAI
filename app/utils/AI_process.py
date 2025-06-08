import sys
import cv2
import os
import numpy as np
import pickle
import zmq
import time
from datetime import datetime
from MySQLConnector import getConnector
import logging

# Thiết lập logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('face_recognition.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

if len(sys.argv) > 1:
    CAMERA_ID = sys.argv[1]
else:
    logger.error("Không đủ biến truyền vào.")
    sys.exit()
    
# Thiết lập ZeroMQ
context = zmq.Context()
socket = context.socket(zmq.PUB)
port = 8000 + int(CAMERA_ID)
socket.bind(f"tcp://*:{port}")
logger.info(f"ZeroMQ publisher bound to port {port}")

# Đọc thông tin camera
conn = getConnector()
cursor = conn.cursor()
cursor.execute("SELECT link, name, status, type, location FROM face_application.camera where id=%s;", (CAMERA_ID,))
camera_infor = cursor.fetchone()
if not camera_infor:
    logger.error(f"No camera found with ID {CAMERA_ID}")
    sys.exit(1)
camera_link, camera_name, camera_status, camera_type, camera_location = camera_infor

if int(camera_type) == 0:
    cap = cv2.VideoCapture(int(camera_link))
    logger.info('webcam')
else:
    cap = cv2.VideoCapture(camera_link)
    logger.info("Sử dụng RTSP URL với UDP.")

# Các thông số cấu hình
SCORE_THRESH = 0.5
IOU_THRESH = 0.5
SKIP_FRAMES = 1
EARLY_STOP_THRESHOLD = 0.6
REDETECT_INTERVAL = 30  # Giây, khoảng thời gian tối thiểu giữa các lần capture

# Đường dẫn đến file chứa embeddings đã lưu (giữ nguyên)
input_file = 'D:/ElectronJS/FlaskAICore/embeddings.pkl'

try:
    with open(input_file, 'rb') as f:
        personIds, showpersonIds, embeddings = pickle.load(f)
    logger.info(f"Loaded embeddings from {input_file}: {len(personIds)} entries")
except Exception as e:
    logger.error(f"Error loading embeddings: {e}")
    sys.exit(1)

yunet_path = 'D:/ElectronJS/FlaskAICore/weights/face_detection_yunet_2023mar.onnx'
sface_path = 'D:/ElectronJS/FlaskAICore/weights/face_recognition_sface_2021dec.onnx'

try:
    face_detector = cv2.FaceDetectorYN.create(yunet_path, "", (640, 480))
    sface_model = cv2.FaceRecognizerSF.create(sface_path, "")
    logger.info("Initialized face detector and recognizer models")
except Exception as e:
    logger.error(f"Failed to initialize models: {e}")
    sys.exit(1)

trackers = []
bboxes = []
detected_face_ids = []
next_id = 0
frame_count = 0
last_recognized_time = {}  # person_id -> datetime

def assign_new_id():
    global next_id
    new_id = next_id
    next_id += 1
    return "NA_" + str(new_id)

def send_frame(camera_index, frame):
    try:
        topic = "newframe"
        _, buffer = cv2.imencode('.jpg', frame)
        socket.send_string(topic, zmq.SNDMORE)
        socket.send(buffer.tobytes())
        logger.debug(f"Frame sent to ZeroMQ port {port} with topic '{topic}'")
    except Exception as e:
        logger.error(f"Error sending frame via ZeroMQ: {e}")

def calculate_iou(box1, box2):
    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2
    xi1, yi1, xi2, yi2 = max(x1, x2), max(y1, y2), min(x1+w1, x2+w2), min(y1+h1, y2+h2)
    inter_area = max(0, xi2 - xi1) * max(0, yi2 - yi1)
    box1_area = w1 * h1
    box2_area = w2 * h2
    return inter_area / float(box1_area + box2_area - inter_area)

while True:
    ret, frame = cap.read()
    if not ret:
        logger.error("Failed to read frame from video capture")
        time.sleep(1)
        continue
    
    frame_count += 1
    process_full_detection = (frame_count % SKIP_FRAMES == 0)
    h, w, _ = frame.shape
    
    # Giảm độ phân giải khung hình để tăng tốc
    scale_factor = 0.75
    frame_resized = cv2.resize(frame, (int(w * scale_factor), int(h * scale_factor)))
    
    # Cập nhật trackers
    new_trackers = []
    new_bboxes = []
    new_face_ids = []
    
    for i, tracker in enumerate(trackers):
        success, bbox = tracker.update(frame_resized)
        if success:
            bbox = [int(b / scale_factor) for b in bbox]
            new_bboxes.append(bbox)
            new_face_ids.append(detected_face_ids[i])
            
            p1 = (int(bbox[0]), int(bbox[1]))
            p2 = (int(bbox[0] + bbox[2]), int(bbox[1] + bbox[3]))
            cv2.rectangle(frame, p1, p2, (255, 0, 0), 2)
            
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.7
            thickness = 2
            text_position = (p1[0], p1[1] - 10)
            if str(detected_face_ids[i]).startswith("NA"):
                cv2.putText(frame, "NA", text_position, font, font_scale, (255, 0, 0), thickness)
            else:
                cv2.putText(frame, str(detected_face_ids[i]), text_position, font, font_scale, (0, 255, 0), thickness)
        else:
            # Xóa face_id khỏi last_recognized_time nếu tracker thất bại
            last_recognized_time.pop(detected_face_ids[i], None)
    
    trackers = new_trackers
    bboxes = new_bboxes
    detected_face_ids = new_face_ids
    
    # Phát hiện đầy đủ
    if process_full_detection:
        face_detector.setInputSize((int(w * scale_factor), int(h * scale_factor)))
        detection_result = face_detector.detect(frame_resized)
        
        # Kiểm tra và xử lý kết quả phát hiện khuôn mặt
        if detection_result is None or len(detection_result) < 2 or detection_result[1] is None:
            faces = []
            logger.debug("No faces detected in current frame")
        else:
            faces = detection_result[1]
        
        new_bboxes = []
        new_face_ids = []
        old_bboxes = []
        old_face_ids = []
        
        for face in faces:
            x, y, w, h = face[:4].astype(np.int32)
            confidence = face[14]
            bbox = (x, y, w, h)
            bbox = [int(b / scale_factor) for b in bbox]
            
            if confidence < EARLY_STOP_THRESHOLD:
                continue
                
            matched = False
            for i, existing_bbox in enumerate(bboxes):
                iou = calculate_iou(bbox, existing_bbox)
                if iou > IOU_THRESH:
                    if not str(detected_face_ids[i]).startswith("NA"):
                        matched = True
                        old_bboxes.append(bbox)
                        old_face_ids.append(detected_face_ids[i])
                        break
            
            if not matched:
                aligned_face = sface_model.alignCrop(frame_resized, face)
                feature = sface_model.feature(aligned_face)
                detected = False
                max_dist = 0
                best_idx = -1
                
                for i in range(len(embeddings)):
                    dist = sface_model.match(embeddings[i], feature)
                    if dist > max_dist:
                        max_dist = dist
                        best_idx = i
                    if dist > SCORE_THRESH:
                        detected = True
                        face_id = showpersonIds[i]
                        current_time = datetime.now()
                        
                        # Kiểm tra thời gian capture cuối cho người đã biết
                        if (face_id not in last_recognized_time or
                                (current_time - last_recognized_time[face_id]).total_seconds() >= REDETECT_INTERVAL):
                            last_recognized_time[face_id] = current_time
                            
                            p1 = (int(bbox[0]), int(bbox[1]))
                            p2 = (int(bbox[0] + bbox[2]), int(bbox[1] + bbox[3]))
                            save_frame = frame.copy()
                            cv2.rectangle(save_frame, p1, p2, (255, 0, 0), 2)
                            d_time = datetime.now()
                            img_name = f"{CAMERA_ID}_{str(d_time).replace(':', '-').replace(' ', '-')}.jpg"
                            notifications_dir = 'D:/ElectronJS/FlaskAICore/data/notifications'
                            try:
                                os.makedirs(notifications_dir, exist_ok=True)
                                cv2.imwrite(os.path.join(notifications_dir, img_name), save_frame)
                                logger.info(f"Saved recognition image to {notifications_dir}/{img_name}")
                            except Exception as e:
                                logger.error(f"Error saving image to {notifications_dir}/{img_name}: {e}")
                                continue
                            
                            try:
                                cursor.execute("SELECT fullname, code FROM face_application.person WHERE id=%s", (personIds[i],))
                                result = cursor.fetchone()
                                if result:
                                    fullname, personcode = result
                                    cursor.execute("""
                                        INSERT INTO recognise_history (personcode, fullname, location, time, image) 
                                        VALUES (%s, %s, %s, %s, %s)
                                    """, (
                                        personcode,
                                        fullname,
                                        camera_location,
                                        d_time.strftime("%Y-%m-%d %H:%M:%S"),
                                        img_name
                                    ))
                                    conn.commit()
                                    logger.info(f"Ghi nhận: {fullname} ({personcode}) tại {camera_location}")
                                else:
                                    logger.warning(f"No person found for ID {personIds[i]}")
                            except Exception as e:
                                logger.error(f"Lỗi khi ghi nhận nhận diện: {e}")
                        else:
                            logger.debug(f"Skipped capture for {face_id}: within {REDETECT_INTERVAL}s interval")
                        
                        new_bboxes.append(bbox)
                        new_face_ids.append(face_id)
                        break
                
                if not detected:
                    na_id = "NA"
                    current_time = datetime.now()

                    if (na_id not in last_recognized_time or
                            (current_time - last_recognized_time[na_id]).total_seconds() >= REDETECT_INTERVAL):
                        last_recognized_time[na_id] = current_time
                        
                        p1 = (int(bbox[0]), int(bbox[1]))
                        p2 = (int(bbox[0] + bbox[2]), int(bbox[1] + bbox[3]))
                        save_frame = frame.copy()
                        cv2.rectangle(save_frame, p1, p2, (0, 0, 255), 2)
                        d_time = datetime.now()
                        img_name = f"{CAMERA_ID}_{str(d_time).replace(':', '-').replace(' ', '-')}_NA.jpg"
                        notifications_dir = 'D:/ElectronJS/FlaskAICore/data/notifications'
                        try:
                            os.makedirs(notifications_dir, exist_ok=True)
                            cv2.imwrite(os.path.join(notifications_dir, img_name), save_frame)
                            logger.info(f"Saved NA image to {notifications_dir}/{img_name}")
                        except Exception as e:
                            logger.error(f"Error saving NA image to {notifications_dir}/{img_name}: {e}")
                            continue
                        
                        try:
                            cursor.execute("""
                                INSERT INTO recognise_history (personcode, fullname, location, time, image)
                                VALUES (%s, %s, %s, %s, %s)
                            """, (
                                "NA",
                                "Người lạ",
                                camera_location,
                                d_time.strftime("%Y-%m-%d %H:%M:%S"),
                                img_name
                            ))
                            conn.commit()
                            logger.info(f"Ghi nhận: Người lạ tại {camera_location}")
                        except Exception as e:
                            logger.error(f"Lỗi khi ghi nhận người lạ: {e}")
                    else:
                        logger.debug(f"Skipped capture for {na_id}: within {REDETECT_INTERVAL}s interval")
                    
                    new_bboxes.append(bbox)
                    new_face_ids.append(na_id)
        
        # Cập nhật trackers
        trackers = []
        bboxes = []
        detected_face_ids = []
        
        for i, bbox in enumerate(old_bboxes):
            tracker = cv2.TrackerKCF_create()
            tracker.init(frame_resized, tuple([int(b * scale_factor) for b in bbox]))
            trackers.append(tracker)
            bboxes.append(bbox)
            detected_face_ids.append(old_face_ids[i])
        
        for i, bbox in enumerate(new_bboxes):
            tracker = cv2.TrackerKCF_create()
            tracker.init(frame_resized, tuple([int(b * scale_factor) for b in bbox]))
            trackers.append(tracker)
            bboxes.append(bbox)
            detected_face_ids.append(new_face_ids[i])
    
    # Gửi và hiển thị khung hình qua ZeroMQ
    send_frame(CAMERA_ID, frame)
    
    cv2.imshow('Face Detection and Tracking', frame)
    
    if cv2.waitKey(1) & 0xFF == 27:
        break

# Giải phóng tài nguyên
cursor.close()
conn.close()
cap.release()
cv2.destroyAllWindows()
import sys
import cv2
import os
import numpy as np
import pickle
import zmq
import time
from datetime import datetime
from MySQLConnector import getConnector
from app.config import Config
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

# Kiểm tra tham số dòng lệnh
if len(sys.argv) > 1:
    CAMERA_ID = sys.argv[1]
else:
    logger.error("No camera ID provided.")
    sys.exit(1)

# Thiết lập ZeroMQ
context = zmq.Context()
socket = context.socket(zmq.PUB)
port = 8000 + int(CAMERA_ID)
socket.bind(f"tcp://*:{port}")
logger.info(f"ZeroMQ publisher bound to port {port}")

# Đọc thông tin camera
try:
    conn = getConnector()
    cursor = conn.cursor()
    cursor.execute("SELECT link, name, status, type, location FROM face_application.camera WHERE id=%s", (CAMERA_ID,))
    camera_infor = cursor.fetchone()
    if not camera_infor:
        logger.error(f"No camera found with ID {CAMERA_ID}")
        sys.exit(1)
    camera_link, camera_name, camera_status, camera_type, camera_location = camera_infor
    logger.info(f"Camera info: ID={CAMERA_ID}, name={camera_name}, location={camera_location}")
except Exception as e:
    logger.error(f"Error fetching camera info: {str(e)}")
    sys.exit(1)
finally:
    cursor.close()
    conn.close()

# Khởi tạo video capture
if int(camera_type) == 0:
    cap = cv2.VideoCapture(int(camera_link))
    logger.info("Using webcam")
else:
    cap = cv2.VideoCapture(camera_link)
    logger.info("Using RTSP URL with UDP")

# Các thông số cấu hình
SCORE_THRESH = 0.5
IOU_THRESH = 0.5
SKIP_FRAMES = 1
EARLY_STOP_THRESHOLD = 0.8

# Đường dẫn đến file embeddings
input_file = './app/embeddings.pkl'
try:
    with open(input_file, 'rb') as f:
        person_ids, person_codes, embeddings = pickle.load(f)
    logger.info(f"Loaded embeddings from {input_file}")
except Exception as e:
    logger.error(f"Error loading embeddings file {input_file}: {str(e)}")
    sys.exit(1)

# Load YuNet và SFace models
try:
    face_detector = cv2.FaceDetectorYN.create(
        os.path.normpath(Config.PATHS['yunet']), "", (640, 480)
    )
    sface_model = cv2.FaceRecognizerSF.create(
        os.path.normpath(Config.PATHS['sface']), ""
    )
    logger.info("Initialized face detector and recognizer models")
except Exception as e:
    logger.error(f"Error initializing models: {str(e)}")
    sys.exit(1)

# Lists to keep track of trackers and bounding boxes
trackers = []
bboxes = []
next_id = 0
frame_count = 0

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
        logger.debug(f"Sent frame via ZeroMQ for camera {camera_index}")
    except Exception as e:
        logger.error(f"Error sending frame via ZeroMQ: {str(e)}")

def calculate_iou(box1, box2):
    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2
    xi1, yi1, xi2, yi2 = max(x1, x2), max(y1, y2), min(x1+w1, x2+w2), min(y1+h1, y2+h2)
    inter_area = max(0, xi2 - xi1) * max(0, yi2 - yi1)
    box1_area = w1 * h1
    box2_area = w2 * h2
    return inter_area / float(box1_area + box2_area - inter_area)

def get_fullname(person_code):
    """Truy vấn fullname từ bảng person dựa trên personcode."""
    try:
        conn = getConnector()
        cursor = conn.cursor()
        cursor.execute("SELECT fullname FROM person WHERE code = %s", (person_code,))
        result = cursor.fetchone()
        if result:
            return result[0]
        logger.warning(f"No person found with code: {person_code}")
        return None
    except Exception as e:
        logger.error(f"Error fetching fullname for person_code {person_code}: {str(e)}")
        return None
    finally:
        cursor.close()
        conn.close()

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
    
    # Cập nhật trackers trên mỗi khung hình
    current_tracked_boxes = []
    current_tracked_ids = []
    
    for i, tracker in enumerate(trackers):
        success, bbox = tracker.update(frame_resized)
        if success:
            # Quy đổi lại kích thước gốc
            bbox = [int(b / scale_factor) for b in bbox]
            current_tracked_boxes.append(bbox)
            current_tracked_ids.append(person_codes[i])
            
            p1 = (int(bbox[0]), int(bbox[1]))
            p2 = (int(bbox[0] + bbox[2]), int(bbox[1] + bbox[3]))
            cv2.rectangle(frame, p1, p2, (255, 0, 0), 2)
            
            if str(person_codes[i]).startswith("NA"):
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.7
                color = (255, 0, 0)
                thickness = 2
                text_position = (p1[0], p1[1] - 10)
                cv2.putText(frame, "NA", text_position, font, font_scale, color, thickness)
            else:
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.7
                color = (0, 255, 0)
                thickness = 2
                text_position = (p1[0], p1[1] - 10)
                cv2.putText(frame, str(person_codes[i]), text_position, font, font_scale, color, thickness)
    
    # Chỉ chạy phát hiện đầy đủ trên các khung hình được chỉ định
    if process_full_detection:
        face_detector.setInputSize((int(w * scale_factor), int(h * scale_factor)))
        detection_result = face_detector.detect(frame_resized)
        
        # Kiểm tra và xử lý kết quả phát hiện khuôn mặt
        if detection_result is None or len(detection_result) < 2:
            faces = []
        else:
            faces = detection_result[1]
            if faces is None:
                faces = []
        
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
            for i, existing_bbox in enumerate(current_tracked_boxes):
                iou = calculate_iou(bbox, existing_bbox)
                if iou > IOU_THRESH:
                    if not str(current_tracked_ids[i]).startswith("NA"):
                        matched = True
                        old_bboxes.append(bbox)
                        old_face_ids.append(current_tracked_ids[i])
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
                        p1 = (int(bbox[0]), int(bbox[1]))
                        p2 = (int(bbox[0] + bbox[2]), int(bbox[1] + bbox[3]))
                        save_frame = frame.copy()
                        cv2.rectangle(save_frame, p1, p2, (255, 0, 0), 2)
                        d_time = datetime.now()
                        img_name = f"{CAMERA_ID}_{str(d_time).replace(':', '-').replace(' ', '-')}.jpg"
                        
                        # Lưu ảnh vào Config.PATHS['notifications']
                        notifications_dir = os.path.normpath(Config.PATHS['notifications'])
                        try:
                            os.makedirs(notifications_dir, exist_ok=True)
                            img_path = os.path.join(notifications_dir, img_name)
                            cv2.imwrite(img_path, save_frame)
                            logger.info(f"Saved recognition image to {img_path}")
                        except Exception as e:
                            logger.error(f"Error saving image to {img_path}: {str(e)}")
                            continue
                        
                        # Lấy fullname từ bảng person
                        fullname = get_fullname(person_codes[i])
                        
                        # Insert vào bảng recognise_history
                        try:
                            conn = getConnector()
                            cursor = conn.cursor()
                            cursor.execute(
                                "INSERT INTO recognise_history (personcode, fullname, location, time, image) "
                                "VALUES (%s, %s, %s, %s, %s)",
                                (person_codes[i], fullname, camera_location, d_time, img_name)
                            )
                            conn.commit()
                            logger.info(
                                f"Inserted into recognise_history: personcode={person_codes[i]}, "
                                f"fullname={fullname}, location={camera_location}, time={d_time}, image={img_name}"
                            )
                        except Exception as e:
                            logger.error(f"Error inserting into recognise_history: {str(e)}")
                        finally:
                            cursor.close()
                            conn.close()
                        
                        logger.info(f"Recognized person: ID={person_ids[i]}, code={person_codes[i]}")
                        new_bboxes.append(bbox)
                        new_face_ids.append(person_codes[i])
                        break
                
                if not detected:
                    new_bboxes.append(bbox)
                    na_id = assign_new_id()
                    new_face_ids.append(na_id)
                    logger.info(f"Unrecognized face: {na_id}")
                    
                    # Lưu ảnh cho người lạ
                    p1 = (int(bbox[0]), int(bbox[1]))
                    p2 = (int(bbox[0] + bbox[2]), int(bbox[1] + bbox[3]))
                    save_frame = frame.copy()
                    cv2.rectangle(save_frame, p1, p2, (255, 0, 0), 2)
                    d_time = datetime.now()
                    img_name = f"{CAMERA_ID}_{str(d_time).replace(':', '-').replace(' ', '-')}_NA.jpg"
                    
                    # Lưu ảnh vào Config.PATHS['notifications']
                    notifications_dir = os.path.normpath(Config.PATHS['notifications'])
                    try:
                        os.makedirs(notifications_dir, exist_ok=True)
                        img_path = os.path.join(notifications_dir, img_name)
                        cv2.imwrite(img_path, save_frame)
                        logger.info(f"Saved NA image to {img_path}")
                    except Exception as e:
                        logger.error(f"Error saving NA image to {img_path}: {str(e)}")
                        continue
                    
                    # Insert vào bảng recognise_history cho người lạ
                    try:
                        conn = getConnector()
                        cursor = conn.cursor()
                        cursor.execute(
                            "INSERT INTO recognise_history (personcode, fullname, location, time, image) "
                            "VALUES (%s, %s, %s, %s, %s)",
                            ("NA", "Người lạ", camera_location, d_time, img_name)
                        )
                        conn.commit()
                        logger.info(
                            f"Inserted NA into recognise_history: personcode=NA, "
                            f"fullname=Người lạ, location={camera_location}, time={d_time}, image={img_name}"
                        )
                    except Exception as e:
                        logger.error(f"Error inserting NA into recognise_history: {str(e)}")
                    finally:
                        cursor.close()
                        conn.close()
        
        # Khởi tạo lại trackers
        trackers = []
        bboxes = []
        person_codes = []
        
        for i, bbox in enumerate(old_bboxes):
            tracker = cv2.TrackerKCF_create()
            tracker.init(frame_resized, tuple([int(b * scale_factor) for b in bbox]))
            trackers.append(tracker)
            bboxes.append(bbox)
            person_codes.append(old_face_ids[i])
        
        for i, bbox in enumerate(new_bboxes):
            tracker = cv2.TrackerKCF_create()
            tracker.init(frame_resized, tuple([int(b * scale_factor) for b in bbox]))
            trackers.append(tracker)
            bboxes.append(bbox)
            person_codes.append(new_face_ids[i])
    
    # Gửi và hiển thị khung hình qua ZeroMQ
    send_frame(CAMERA_ID, frame)
    
    # Tải lại embeddings mỗi 10 giây
    if datetime.now().second % 10 == 0:
        try:
            with open(input_file, 'rb') as f:
                person_ids, person_codes, embeddings = pickle.load(f)
            logger.info(f"Reloaded embeddings from {input_file}")
        except Exception as e:
            logger.error(f"Error reloading embeddings file {input_file}: {str(e)}")
    
    cv2.imshow('Face Detection and Tracking', frame)
    
    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()
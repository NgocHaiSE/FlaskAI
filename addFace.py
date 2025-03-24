import cv2

# Load YuNet model
add_face_detector = cv2.FaceDetectorYN.create("./weights/face_detection_yunet_2023mar.onnx", "", (640, 480))

def resize_if_needed(image, max_width=1280, max_height=720):
    h, w, _ = image.shape
    if w > max_width or h > max_height:
        scaling_factor = min(max_width / w, max_height / h)
        new_size = (int(w * scaling_factor), int(h * scaling_factor))
        resized_image = cv2.resize(image, new_size)
        print(f"Image resized to: {new_size}")
        return resized_image
    return image

def addFace(path):
    frame = cv2.imread(path)
    if frame is None:
        print("Failed to read frame from image")
        return 0

    # Resize image if too large
    frame = resize_if_needed(frame)

    # Detect faces using YuNet
    h, w, _ = frame.shape
    add_face_detector.setInputSize((w, h))
    faces = add_face_detector.detect(frame)
    print(w,h)

    faces = faces[1]  # faces is a tuple (retval, faces)
    if faces is None:
        return 0
    else:
        return len(faces)

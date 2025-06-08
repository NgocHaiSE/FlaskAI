import base64
import numpy as np
import cv2
import os
from datetime import datetime
from flask import request, jsonify
import subprocess

def process_image(image_base64, output_dir='timekeepings'):
    try:
        # Loại bỏ tiền tố base64 nếu có
        if ',' in image_base64:
            image_base64 = image_base64.split(',')[1]

        # Giải mã ảnh
        image_bytes = base64.b64decode(image_base64)
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if image is None:
            return {'status': 'error', 'message': 'Không thể giải mã ảnh'}

        # Tạo thư mục lưu ảnh nếu chưa tồn tại
        os.makedirs(output_dir, exist_ok=True)

        # Tạo tên file duy nhất
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f'{output_dir}/capture_{timestamp}.jpg'

        # Lưu ảnh
        cv2.imwrite(filename, image)
        
        try:
            result = subprocess.run(
                ['python', 'faceRecognise.py', filename], 
                capture_output=True, 
                text=True, 
                timeout=30
            )
            
            # Phân tích kết quả từ subprocess
            if result.returncode == 0:
                # Nếu thành công
                return jsonify({
                    "status": "success", 
                    "message": result.stdout.strip(),
                    "file": filename
                }), 200
            else:
                # Nếu có lỗi
                return jsonify({
                    "status": "error", 
                    "message": result.stderr.strip()
                }), 500

        except subprocess.TimeoutExpired:
            return jsonify({
                "status": "error", 
                "message": "Quá trình nhận diện mất quá nhiều thời gian"
            }), 504
        except Exception as e:
            return jsonify({
                "status": "error", 
                "message": str(e)
            }), 500

    except Exception as e:
        return {'status': 'error', 'message': str(e)}
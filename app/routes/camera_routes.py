from flask import Blueprint, jsonify, request
from app.services.camera_services import start, check, stop

camera_bp = Blueprint('camera', __name__)

@camera_bp.route('/start/<id>', methods=['GET'])
def start_camera(id):
    try:
        start(id)
        return jsonify({"status": "Thành công", "message": "Camera đã được khởi động"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@camera_bp.route('/stop/<id>')
def stop_camera(id):
    try:
        stop(id)
        return jsonify({"status": "Thành công", "message": "Camera đã được khởi động"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
      

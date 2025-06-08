from flask import Blueprint, send_from_directory
from app.config import Config   

static_bp = Blueprint('static', __name__)

@static_bp.route('/avatar/<path:filename>')
def serve_avatar(filename):
    return send_from_directory(Config.PATHS['avatars'], filename)  
  
@static_bp.route('/face/<path:filename>')
def serve_face(filename):
    return send_from_directory(Config.PATHS['faces'], filename)
  
@static_bp.route('/image/<path:filename>')
def serve_timekeeping(filename):
    return send_from_directory(Config.PATHS['timekeepings'], filename)

@static_bp.route('/recognise/<path:filename>')
def serve_recognise(filename):
    
    return send_from_directory(Config.PATHS['notifications'], filename)
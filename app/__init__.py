from flask import Flask
from .routes.timekeeping_routes import timekeeping_bp
from .routes.static_routes import static_bp
from .routes.person_routes import person_bp
from .routes.camera_routes import camera_bp
from flask_cors import CORS

def create_app():
    app = Flask(__name__)
    app.config.from_object('app.config.Config')
    # CORS(app, resources={r"/api/*": {"origins": "http://localhost:5173", }})  
    CORS(app, resources={r"/api/*": {"origins": "*"}})  # Cho phép tất cả các nguồn gốc

    # Đăng ký blueprint
    app.register_blueprint(static_bp)
    app.register_blueprint(timekeeping_bp, url_prefix='/api/timekeeping')
    app.register_blueprint(person_bp, url_prefix='/api/person')
    app.register_blueprint(camera_bp, url_prefix='/api/camera')

    return app
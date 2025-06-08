from flask import Flask
from .routes.timekeeping_routes import timekeeping_bp
from .routes.static_routes import static_bp
from .routes.person_routes import person_bp
from .routes.camera_routes import camera_bp
from .routes.user_routes import user_bp
from .routes.role_routes import role_bp
from .routes.permission_routes import permission_bp
from .middleware.auth import init_auth_middleware
from flask_cors import CORS

def create_app():
    app = Flask(__name__)
    app.config.from_object('app.config.Config')
    
    # CORS configuration
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Initialize auth middleware
    init_auth_middleware(app)

    # Đăng ký blueprint
    app.register_blueprint(static_bp)
    app.register_blueprint(timekeeping_bp, url_prefix='/api/timekeeping')
    app.register_blueprint(person_bp, url_prefix='/api/person')
    app.register_blueprint(camera_bp, url_prefix='/api/camera')
    
    # Authentication & Authorization blueprints
    app.register_blueprint(user_bp, url_prefix='/api/user')
    app.register_blueprint(role_bp, url_prefix='/api/role')
    app.register_blueprint(permission_bp, url_prefix='/api/permission')

    # Error handlers
    @app.errorhandler(401)
    def unauthorized(error):
        return {"error": "Unauthorized access"}, 401

    @app.errorhandler(403)
    def forbidden(error):
        return {"error": "Access forbidden"}, 403

    @app.errorhandler(404)
    def not_found(error):
        return {"error": "Resource not found"}, 404

    @app.errorhandler(500)
    def internal_error(error):
        return {"error": "Internal server error"}, 500

    return app
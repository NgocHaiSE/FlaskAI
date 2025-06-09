from flask import Flask
from .routes.timekeeping_routes import timekeeping_bp
from .routes.static_routes import static_bp
from .routes.person_routes import person_bp
from .routes.camera_routes import camera_bp
from .routes.user_routes import user_bp
from .routes.role_routes import role_bp
from .routes.permission_routes import permission_bp
from flask_cors import CORS
from flask_jwt_extended import JWTManager
import os
from datetime import timedelta

def create_app():
    app = Flask(__name__)
    
    # JWT Configuration
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')  # Change this in production!
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)
    app.config['JWT_REFRESH_TOKEN_EXPIRES'] = timedelta(days=30)
    app.config['JWT_ALGORITHM'] = 'HS256'
    app.config['JWT_BLACKLIST_ENABLED'] = True
    app.config['JWT_BLACKLIST_TOKEN_CHECKS'] = ['access', 'refresh']
    
    # Initialize JWT Manager
    jwt = JWTManager(app)
    
    # CORS configuration
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # JWT Error Handlers
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return {"error": "Token has expired"}, 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return {"error": "Invalid token"}, 401

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return {"error": "Authorization token is required"}, 401

    @jwt.needs_fresh_token_loader
    def token_not_fresh_callback(jwt_header, jwt_payload):
        return {"error": "Fresh token required"}, 401

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return {"error": "Token has been revoked"}, 401

    # Optional: Token blacklist (you'll need to implement this if you want logout functionality)
    blacklisted_tokens = set()
    
    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        return jwt_payload['jti'] in blacklisted_tokens

    # Store blacklisted_tokens in app context for access in routes
    app.blacklisted_tokens = blacklisted_tokens

    # Register blueprints
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
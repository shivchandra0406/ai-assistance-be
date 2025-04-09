from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from app.config import Config
from app.api.schema_routes import schema_bp as schema_routes
from app.api.auth_routes import auth_bp
from app.api.report_routes import report_bp
from app.websockets.socket_manager import init_socketio
import os

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()

def create_app(config_class=Config):
    app = Flask(__name__)
    # Configure CORS to allow credentials
    CORS(app, supports_credentials=True, resources={
        r"/api/*": {
            "origins": ["http://localhost:3000"],
            "allow_credentials": True
        }
    })
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Configure session
    app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-here')
    app.config['SESSION_TYPE'] = 'filesystem'
    
    # Initialize SocketIO
    socketio = init_socketio(app)
    
    # Import models for migrations
    from app.models import leads  # noqa
    
    # Register blueprints
    from app.api.routes import api_bp as api
    from app.api.bulk_routes import bulk_routes
    
    app.register_blueprint(api, url_prefix='/api')
    app.register_blueprint(schema_routes, url_prefix='/api/schema')
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(report_bp, url_prefix='/api/report')
    app.register_blueprint(bulk_routes)
    
    @app.route('/health')
    def health_check():
        return {'status': 'healthy'}
    
    return app, socketio

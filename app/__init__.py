from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from app.config import Config

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()

def create_app(config_class=Config):
    app = Flask(__name__)
    CORS(app)
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Import models for migrations
    from app.models import leads  # noqa
    
    # Register blueprints
    from app.api.routes import api_bp as api
    from app.api.schema_routes import schema_bp as schema_routes
    from app.api.bulk_routes import bulk_routes
    
    app.register_blueprint(api, url_prefix='/api')
    app.register_blueprint(schema_routes, url_prefix='/api/schema')
    app.register_blueprint(bulk_routes)
    
    @app.route('/health')
    def health_check():
        return {'status': 'healthy'}
    
    return app

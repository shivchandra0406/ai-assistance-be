from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from app.config import Config

db = SQLAlchemy()
migrate = Migrate()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # Register blueprints
    from app.api.routes import api_bp
    from app.api.schema_routes import schema_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(schema_bp, url_prefix='/api/schema')

    @app.route('/health')
    def health_check():
        return {'status': 'healthy'}

    return app

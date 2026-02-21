"""
Capitán Coditos – Flask API
"""
from flask import Flask
from flask_cors import CORS

from config import Config
from database.mongo import init_mongo
from tasks.celery_app import create_celery


def create_app(config: Config = None) -> Flask:
    app = Flask(__name__)
    cfg = config or Config()

    # CORS
    CORS(app, origins=cfg.CORS_ORIGINS)

    # Store config on app
    app.config.from_object(cfg)

    # Initialize MongoDB connection pool
    init_mongo(cfg.MONGO_URL, cfg.MONGO_DB)

    # Register blueprints
    from routes.summoner import summoner_bp
    from routes.tasks import tasks_bp
    from routes.ai import ai_bp
    from routes.db import db_bp

    app.register_blueprint(summoner_bp, url_prefix="/api/summoner")
    app.register_blueprint(tasks_bp, url_prefix="/api/tasks")
    app.register_blueprint(ai_bp, url_prefix="/api/ai")
    app.register_blueprint(db_bp, url_prefix="/api/db")

    return app


def create_celery_app():
    """Entry-point for the Celery worker process."""
    app = create_app()
    celery = create_celery(app)
    return celery


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=False)

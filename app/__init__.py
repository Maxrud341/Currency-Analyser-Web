from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from app.logger import get_logger



db = SQLAlchemy()
migrate = Migrate()
logger = get_logger('app')

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')

    logger.info('Starting application')

    db.init_app(app)
    migrate.init_app(app, db)
    from app.models import message

    from app.controllers.main import main_bp
    app.register_blueprint(main_bp)

    from app.controllers.exchange_controller import exchange_bp
    app.register_blueprint(exchange_bp)

    logger.info('Blueprints registered')
    return app
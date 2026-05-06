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


    from app.auth_manager import login_manager
    login_manager.init_app(app)
    app.login_manager = login_manager

    from app.models import user


    from app.controllers.main import main_bp
    app.register_blueprint(main_bp)

    from app.controllers.auth import auth_bp
    app.register_blueprint(auth_bp)

    from app.controllers.exchange_controller import exchange_bp
    app.register_blueprint(exchange_bp)

    logger.info('Blueprints registered')


    # with app.app_context():
    #     db.create_all()
    return app
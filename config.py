import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret')

    uri = os.environ.get("DATABASE_URL")

    if uri and uri.startswith("postgres://"):
        uri = uri.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_DATABASE_URI = uri
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    DEBUG = os.environ.get('DEBUG', 'false').lower() == 'true'
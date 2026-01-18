# config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev_key'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Cadena de conexión para MySQL
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+mysqlconnector://{os.environ.get('DB_USER')}:"
        f"{os.environ.get('DB_PASSWORD')}@"
        f"{os.environ.get('DB_HOST')}/"
        f"{os.environ.get('DB_NAME')}"
    )

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "hostelos-super-secret-key-12345")
    
    # Database configuration
    # Default to SQLite, override with MySQL url from environment
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///hostel.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Gemini API Configuration
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    
    # Reports upload/save folder
    UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static', 'assets', 'reports')
    
    # Documents folder for RAG knowledge base
    DOCUMENTS_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static', 'assets', 'documents')

# Ensure folders exist
os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
os.makedirs(Config.DOCUMENTS_FOLDER, exist_ok=True)

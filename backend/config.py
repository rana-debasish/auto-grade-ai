import os
import logging
from dotenv import load_dotenv

# Load .env from project root (try parent of backend/, then CWD)
_env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
if not os.path.exists(_env_path):
    _env_path = os.path.join(os.getcwd(), '.env')
load_dotenv(_env_path)


class Config:
    """Application configuration loaded from environment variables."""

    # MongoDB
    MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
    MONGO_DB_NAME = os.getenv('MONGO_DB_NAME', 'answer_evaluation_system')

    # JWT
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'dev-secret-key-change-in-production')
    JWT_ACCESS_TOKEN_EXPIRES = int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', 1800))  # 30 minutes
    JWT_REFRESH_TOKEN_EXPIRES = int(os.getenv('JWT_REFRESH_TOKEN_EXPIRES', 2592000))  # 30 days

    # Flask
    DEBUG = os.getenv('FLASK_DEBUG', '0') == '1'  # Default to production (debug off)

    # Upload (reduced for Render free tier - 8MB max)
    UPLOAD_FOLDER = os.path.abspath(os.getenv('UPLOAD_FOLDER', os.path.join(os.path.dirname(__file__), 'uploads')))
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 10 * 1024 * 1024))  # 10MB
    ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}
    
    # Memory limits for Render free tier (512MB)
    MAX_CONCURRENT_EVALUATIONS = max(1, int(os.getenv('MAX_CONCURRENT_EVALUATIONS', 2)))
    MAX_PDF_PAGES = int(os.getenv('MAX_PDF_PAGES', 10))  # Limit pages per PDF
    MAX_EXTRACTED_CHARS = int(os.getenv('MAX_EXTRACTED_CHARS', 20000))
    EVALUATION_WORKERS = max(1, int(os.getenv('EVALUATION_WORKERS', MAX_CONCURRENT_EVALUATIONS)))
    MIN_OCR_REVIEW_CHARS = max(0, int(os.getenv('MIN_OCR_REVIEW_CHARS', 80)))
    REVIEW_CONFIDENCE_THRESHOLD = min(1.0, max(0.0, float(os.getenv('REVIEW_CONFIDENCE_THRESHOLD', 0.6))))
    GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-flash-lite-latest')
    GEMINI_FALLBACK_MODEL = os.getenv('GEMINI_FALLBACK_MODEL', 'gemini-2.0-flash-lite')
    GEMINI_TIMEOUT_SECONDS = max(1, int(os.getenv('GEMINI_TIMEOUT_SECONDS', 60)))
    LOGIN_RATE_LIMIT = os.getenv('LOGIN_RATE_LIMIT', '5 per minute')
    UPLOAD_RATE_LIMIT = os.getenv('UPLOAD_RATE_LIMIT', '10 per minute')

    # Optional integrations
    OLLAMA_ENABLED = os.getenv('OLLAMA_ENABLED', '0') == '1'
    
    # Production settings
    IS_PRODUCTION = os.getenv('RENDER', '') == 'true' or os.getenv('FLASK_DEBUG', '0') == '0'
    
    @classmethod
    def log_config(cls):
        """Log configuration for debugging."""
        logging.info(f"[CONFIG] Debug: {cls.DEBUG}")
        logging.info(f"[CONFIG] Production: {cls.IS_PRODUCTION}")
        logging.info(f"[CONFIG] Max upload: {cls.MAX_CONTENT_LENGTH / 1024 / 1024:.1f}MB")
        logging.info(f"[CONFIG] Max concurrent evals: {cls.MAX_CONCURRENT_EVALUATIONS}")
        logging.info(f"[CONFIG] Ollama enabled: {cls.OLLAMA_ENABLED}")

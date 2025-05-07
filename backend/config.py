import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
# Create a .env file in this directory with GEMINI_API_KEY=your_key_here
# Get your Gemini API key from: https://aistudio.google.com/app/apikey
load_dotenv()

# API Settings
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

# Google Gemini API
# If not set, the application will raise an error when attempting to use Gemini features
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Celery Configuration
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

# Upload directory for video files
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Configuration for development/production
DEBUG = os.getenv("DEBUG", "True").lower() in ("true", "1", "t") 
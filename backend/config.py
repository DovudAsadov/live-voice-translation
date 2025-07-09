import os
import secrets
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Configuration class for the application"""
    
    # Flask configuration
    SECRET_KEY = os.getenv('SECRET_KEY', secrets.token_hex(32))
    
    # API Keys
    DEEPL_TOKEN = os.getenv("DEEPL_TOKEN")
    TILMOCH_TOKEN = os.getenv("TILMOCH_TOKEN")
    AISHA_TOKEN = os.getenv("AISHA_TOKEN")
    AISHA_API_KEY = os.getenv("AISHA_API_KEY", os.getenv("AISHA_TOKEN"))  # Support both names
    OPENAI_TOKEN = os.getenv("OPENAI_TOKEN")
    
    # Application settings
    DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 5000))
    USE_GPU = False
    
    # Model settings
    WHISPER_MODEL = os.getenv('WHISPER_MODEL', 'small')
    
    # TTS Voice mapping
    VOICE_MAP = {
        'uz': 'uz-UZ-MadinaNeural',  # Uzbek voice
        'en': 'en-US-AriaNeural',
        'es': 'es-ES-ElviraNeural',
        'fr': 'fr-FR-DeniseNeural',
        'de': 'de-DE-KatjaNeural',
        'it': 'it-IT-ElsaNeural',
        'pt': 'pt-BR-FranciscaNeural',
        'ru': 'ru-RU-SvetlanaNeural',
        'ja': 'ja-JP-NanamiNeural',
        'ko': 'ko-KR-SunHiNeural',
        'zh': 'zh-CN-XiaoxiaoNeural',
        'ar': 'ar-SA-ZariyahNeural',
        'hi': 'hi-IN-SwaraNeural'
    }
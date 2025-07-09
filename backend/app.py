import logging
from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO
from config import Config
from services.translation_service import TranslationService
from routes.api import api_bp
from socket_handlers.handlers import register_socket_handlers

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__, static_folder='../frontend', static_url_path='')
app.config.from_object(Config)

# Initialize extensions
CORS(app, origins="*")
socketio = SocketIO(
    app, 
    cors_allowed_origins="*", 
    async_mode='threading',
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=10000000  # 10MB for large audio files
)

# Initialize translation service
translation_service = TranslationService()

# Register blueprints
app.register_blueprint(api_bp)

# Register socket handlers
register_socket_handlers(socketio, translation_service)

# Serve frontend
@app.route('/')
def index():
    return app.send_static_file('index.html')

# Store active rooms and users (shared state)
active_rooms = {}
user_languages = {}

# Make shared state available to modules
app.active_rooms = active_rooms
app.user_languages = user_languages

if __name__ == "__main__":
    logger.info("Starting translation server...")
    print("Starting translation server on port 5000...")
    socketio.run(app, host="0.0.0.0", port=5000, debug=True, allow_unsafe_werkzeug=True)
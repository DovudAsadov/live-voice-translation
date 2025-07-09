import os
import tempfile
import io
import logging
from flask import Blueprint, request, send_file, jsonify, current_app
from services.translation_service import TranslationService

logger = logging.getLogger(__name__)

# Create blueprint
api_bp = Blueprint('api', __name__)

# Initialize translation service (will be shared across requests)
translation_service = None

@api_bp.before_app_request
def initialize_translation_service():
    global translation_service
    translation_service = TranslationService()

@api_bp.route("/translate", methods=["POST"])
def translate_audio():
    """Legacy REST API endpoint for backward compatibility"""
    global translation_service
    
    if not translation_service:
        translation_service = TranslationService()
    
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file uploaded"}), 400

    lang_from = request.form.get("lang_from", "en")
    lang_to = request.form.get("lang_to", "ru")

    audio_file = request.files['audio']

    # Save temp WAV file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_in:
        audio_path = tmp_in.name
        audio_file.save(audio_path)

    try:
        # Transcribe
        text = translation_service.transcribe_audio(audio_path, language=lang_from)
        logger.info(f"Transcribed: {text}")

        # Translate
        translated = translation_service.translate_text(text, lang_from, lang_to)
        logger.info(f"Translated: {translated}")

        # TTS
        audio_data = translation_service.text_to_speech(translated, lang_to)
        
        # Return audio file
        audio_io = io.BytesIO(audio_data)
        return send_file(audio_io, mimetype="audio/mpeg", as_attachment=True, download_name="translated.mp3")

    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)

@api_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        active_rooms = getattr(current_app, 'active_rooms', {})
        return jsonify({
            'status': 'healthy',
            'active_rooms': len(active_rooms),
            'total_users': sum(len(users) for users in active_rooms.values())
        })
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

@api_bp.route('/rooms', methods=['GET'])
def get_rooms():
    """Get list of active rooms"""
    try:
        active_rooms = getattr(current_app, 'active_rooms', {})
        return jsonify({
            'rooms': list(active_rooms.keys()),
            'total_rooms': len(active_rooms)
        })
    except Exception as e:
        logger.error(f"Get rooms error: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/rooms/<room_id>', methods=['GET'])
def get_room_info(room_id):
    """Get information about a specific room"""
    try:
        active_rooms = getattr(current_app, 'active_rooms', {})
        user_languages = getattr(current_app, 'user_languages', {})
        
        if room_id not in active_rooms:
            return jsonify({'error': 'Room not found'}), 404
        
        room_users = active_rooms[room_id]
        users_info = []
        
        for user_id in room_users:
            users_info.append({
                'user_id': user_id,
                'language': user_languages.get(user_id, 'unknown')
            })
        
        return jsonify({
            'room_id': room_id,
            'users_count': len(room_users),
            'users': users_info
        })
    except Exception as e:
        logger.error(f"Get room info error: {e}")
        return jsonify({'error': str(e)}), 500
import tempfile
import base64
import logging
from flask import request, current_app
from flask_socketio import emit, join_room, leave_room
from utils.audio_utils import cleanup_temp_file

logger = logging.getLogger(__name__)

def register_socket_handlers(socketio, translation_service):
    """Register all socket event handlers"""
    
    @socketio.on('connect')
    def handle_connect():
        logger.info(f"Client connected: {request.sid}")
        print(f"Client connected: {request.sid}")
        emit('connected', {'message': 'Connected to translation server'})

    @socketio.on('disconnect')
    def handle_disconnect():
        logger.info(f"Client disconnected: {request.sid}")
        
        # Get shared state
        active_rooms = getattr(current_app, 'active_rooms', {})
        user_languages = getattr(current_app, 'user_languages', {})
        
        # Clean up user from rooms
        for room_id, users in list(active_rooms.items()):
            if request.sid in users:
                users.remove(request.sid)
                leave_room(room_id)
                emit('user_left', {'user_id': request.sid}, room=room_id)
                # Clean up empty rooms
                if not users:
                    del active_rooms[room_id]
                break
        
        # Clean up user language preferences
        if request.sid in user_languages:
            del user_languages[request.sid]

    @socketio.on('join_room')
    def handle_join_room(data):
        room_id = data['room_id']
        user_lang = data['language']
        
        # Get shared state
        active_rooms = getattr(current_app, 'active_rooms', {})
        user_languages = getattr(current_app, 'user_languages', {})
        
        # Store user language preference
        user_languages[request.sid] = user_lang
        
        # Add user to room
        if room_id not in active_rooms:
            active_rooms[room_id] = []
        
        if request.sid not in active_rooms[room_id]:
            active_rooms[room_id].append(request.sid)
            join_room(room_id)
            
            logger.info(f"User {request.sid} joined room {room_id} with language {user_lang}")
            
            # Notify other users in the room
            emit('user_joined', {
                'user_id': request.sid,
                'language': user_lang,
                'room_users': len(active_rooms[room_id])
            }, room=room_id, include_self=False)
            
            # Send room info to the joining user
            emit('room_joined', {
                'room_id': room_id,
                'users_count': len(active_rooms[room_id])
            })

    @socketio.on('leave_room')
    def handle_leave_room(data):
        room_id = data['room_id']
        
        # Get shared state
        active_rooms = getattr(current_app, 'active_rooms', {})
        
        if room_id in active_rooms and request.sid in active_rooms[room_id]:
            active_rooms[room_id].remove(request.sid)
            leave_room(room_id)
            
            logger.info(f"User {request.sid} left room {room_id}")
            
            # Clean up empty rooms
            if not active_rooms[room_id]:
                del active_rooms[room_id]
            
            emit('user_left', {'user_id': request.sid}, room=room_id)

    @socketio.on('audio_data')
    def handle_audio_data(data):
        logger.info(f"Received audio_data event from {request.sid} (room: {data.get('room_id')})")
        print(f"Received audio_data event from {request.sid} (room: {data.get('room_id')})")
        """Handle real-time audio data from clients"""
        try:
            room_id = data['room_id']
            audio_base64 = data['audio']
            
            # Get shared state
            active_rooms = getattr(current_app, 'active_rooms', {})
            user_languages = getattr(current_app, 'user_languages', {})
            
            # Get sender's language
            user_lang = user_languages.get(request.sid, 'en')
            print(f"Sender language: {user_lang}, audio size: {len(audio_base64)} chars")
            
            # Decode audio data
            audio_data = base64.b64decode(audio_base64)
            print(f"Decoded audio size: {len(audio_data)} bytes")
            
            # Save to temporary file for Whisper processing
            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp_file:
                tmp_file.write(audio_data)
                tmp_file_path = tmp_file.name
            
            # For each recipient in the room (except sender), queue a translation task for their language
            if room_id in active_rooms:
                print(f"Room {room_id} has {len(active_rooms[room_id])} users: {active_rooms[room_id]}")
                for recipient_id in active_rooms[room_id]:
                    if recipient_id != request.sid:
                        target_lang = user_languages.get(recipient_id, 'en')
                        print(f"Recipient {recipient_id} language: {target_lang}, sender language: {user_lang}")
                        if target_lang != user_lang:  # Only translate if languages are different
                            print(f"Adding translation task: {user_lang} -> {target_lang}")
                            translation_service.add_translation_task(
                                tmp_file_path,
                                user_lang,
                                target_lang,
                                room_id,  # still pass room_id for context, but not used for emission
                                recipient_id,  # pass recipient's socket ID
                                socketio
                            )
                        else:
                            print(f"Skipping translation - same language ({user_lang})")
            else:
                print(f"Room {room_id} not found in active_rooms: {list(active_rooms.keys())}")
            
            # Clean up temp file after processing
            cleanup_temp_file(tmp_file_path, delay=5)
            
        except Exception as e:
            logger.error(f"Error handling audio data: {e}")
            emit('error', {'message': 'Error processing audio'})

    @socketio.on('get_room_info')
    def handle_get_room_info(data):
        """Get information about current room"""
        try:
            room_id = data.get('room_id')
            if not room_id:
                emit('error', {'message': 'Room ID required'})
                return
            
            # Get shared state
            active_rooms = getattr(current_app, 'active_rooms', {})
            user_languages = getattr(current_app, 'user_languages', {})
            
            if room_id not in active_rooms:
                emit('room_info', {
                    'room_id': room_id,
                    'users_count': 0,
                    'users': []
                })
                return
            
            room_users = active_rooms[room_id]
            users_info = []
            
            for user_id in room_users:
                users_info.append({
                    'user_id': user_id,
                    'language': user_languages.get(user_id, 'unknown'),
                    'is_self': user_id == request.sid
                })
            
            emit('room_info', {
                'room_id': room_id,
                'users_count': len(room_users),
                'users': users_info
            })
            
        except Exception as e:
            logger.error(f"Error getting room info: {e}")
            emit('error', {'message': 'Error getting room information'})

    @socketio.on('ping')
    def handle_ping():
        """Handle ping for connection testing"""
        emit('pong', {'timestamp': request.sid})

    return socketio
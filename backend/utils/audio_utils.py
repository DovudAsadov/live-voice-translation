import os
import time
import threading
import logging
from pydub import AudioSegment
import tempfile
import base64

logger = logging.getLogger(__name__)

def cleanup_temp_file(file_path, delay=5):
    """Clean up temporary file after a delay"""
    def cleanup():
        time.sleep(delay)
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.debug(f"Cleaned up temporary file: {file_path}")
        except Exception as e:
            logger.error(f"Error cleaning up temp file {file_path}: {e}")
    
    threading.Thread(target=cleanup, daemon=True).start()

def convert_audio_format(input_path, output_path, target_format="wav"):
    """Convert audio file to specified format"""
    try:
        audio = AudioSegment.from_file(input_path)
        audio.export(output_path, format=target_format)
        return True
    except Exception as e:
        logger.error(f"Error converting audio format: {e}")
        return False

def normalize_audio(audio_path, target_dBFS=-20.0):
    """Normalize audio volume"""
    try:
        audio = AudioSegment.from_file(audio_path)
        normalized_audio = audio.normalize()
        
        # Adjust to target dBFS
        change_in_dBFS = target_dBFS - normalized_audio.dBFS
        normalized_audio = normalized_audio.apply_gain(change_in_dBFS)
        
        # Save normalized audio
        normalized_audio.export(audio_path, format="wav")
        return True
    except Exception as e:
        logger.error(f"Error normalizing audio: {e}")
        return False

def split_audio_chunks(audio_path, chunk_duration_ms=30000):
    """Split audio into chunks for processing"""
    try:
        audio = AudioSegment.from_file(audio_path)
        chunks = []
        
        for i in range(0, len(audio), chunk_duration_ms):
            chunk = audio[i:i + chunk_duration_ms]
            chunks.append(chunk)
        
        return chunks
    except Exception as e:
        logger.error(f"Error splitting audio: {e}")
        return []

def save_audio_chunks(chunks, output_dir):
    """Save audio chunks to files"""
    try:
        chunk_paths = []
        
        for i, chunk in enumerate(chunks):
            chunk_path = os.path.join(output_dir, f"chunk_{i}.wav")
            chunk.export(chunk_path, format="wav")
            chunk_paths.append(chunk_path)
        
        return chunk_paths
    except Exception as e:
        logger.error(f"Error saving audio chunks: {e}")
        return []

def merge_audio_files(audio_paths, output_path):
    """Merge multiple audio files into one"""
    try:
        combined = AudioSegment.empty()
        
        for audio_path in audio_paths:
            if os.path.exists(audio_path):
                audio = AudioSegment.from_file(audio_path)
                combined += audio
        
        combined.export(output_path, format="wav")
        return True
    except Exception as e:
        logger.error(f"Error merging audio files: {e}")
        return False

def get_audio_duration(audio_path):
    """Get audio duration in seconds"""
    try:
        audio = AudioSegment.from_file(audio_path)
        return len(audio) / 1000.0  # Convert to seconds
    except Exception as e:
        logger.error(f"Error getting audio duration: {e}")
        return 0

def is_audio_file_valid(audio_path):
    """Check if audio file is valid and can be processed"""
    try:
        if not os.path.exists(audio_path):
            return False
        
        # Try to load the audio file
        audio = AudioSegment.from_file(audio_path)
        
        # Check if audio has content
        if len(audio) == 0:
            return False
        
        return True
    except Exception as e:
        logger.error(f"Audio file validation error: {e}")
        return False

def reduce_audio_noise(audio_path, noise_reduction_factor=0.5):
    """Apply basic noise reduction to audio"""
    try:
        audio = AudioSegment.from_file(audio_path)
        
        # Apply high-pass filter to remove low-frequency noise
        # This is a simple approach - more sophisticated noise reduction
        # would require additional libraries like noisereduce
        
        # Normalize and apply gain
        normalized = audio.normalize()
        
        # Apply compression to reduce dynamic range
        compressed = normalized.compress_dynamic_range(
            threshold=-20.0,
            ratio=4.0,
            attack=5.0,
            release=50.0
        )
        
        # Save processed audio
        compressed.export(audio_path, format="wav")
        return True
    except Exception as e:
        logger.error(f"Error reducing audio noise: {e}")
        return False

def base64_to_audio_file(base64_data, output_path):
    """Convert base64 audio data to file"""
    try:
        audio_data = base64.b64decode(base64_data)
        
        with open(output_path, 'wb') as f:
            f.write(audio_data)
        
        return True
    except Exception as e:
        logger.error(f"Error converting base64 to audio file: {e}")
        return False

def audio_file_to_base64(audio_path):
    """Convert audio file to base64 string"""
    try:
        with open(audio_path, 'rb') as f:
            audio_data = f.read()
        
        return base64.b64encode(audio_data).decode('utf-8')
    except Exception as e:
        logger.error(f"Error converting audio file to base64: {e}")
        return None

def create_temp_audio_file(suffix=".wav"):
    """Create a temporary audio file and return its path"""
    try:
        temp_file = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        temp_file.close()
        return temp_file.name
    except Exception as e:
        logger.error(f"Error creating temporary audio file: {e}")
        return None

def get_audio_info(audio_path):
    """Get detailed information about audio file"""
    try:
        audio = AudioSegment.from_file(audio_path)
        
        return {
            'duration_seconds': len(audio) / 1000.0,
            'sample_rate': audio.frame_rate,
            'channels': audio.channels,
            'sample_width': audio.sample_width,
            'frame_count': audio.frame_count(),
            'max_dBFS': audio.max_dBFS,
            'dBFS': audio.dBFS,
            'rms': audio.rms
        }
    except Exception as e:
        logger.error(f"Error getting audio info: {e}")
        return None
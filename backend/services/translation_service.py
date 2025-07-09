import os
import asyncio
import deepl
import base64
import threading
import queue
import logging
import tempfile
import time
import requests
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from config import Config
from openai import OpenAI, AsyncOpenAI
import io
from pydub import AudioSegment

# Try importing GPU dependencies
try:
    import whisper
    import torch
    from transformers import pipeline
    import edge_tts
    GPU_AVAILABLE = True
except ImportError:
    GPU_AVAILABLE = False

logger = logging.getLogger(__name__)
logging.info(f"Using GPU: {GPU_AVAILABLE}")

class TranslationService:
    """Enhanced translation service with better error handling and optimization"""
    
    def __init__(self):
        self.use_gpu = Config.USE_GPU if hasattr(Config, 'USE_GPU') else False
        self.use_gpu = self.use_gpu and GPU_AVAILABLE
        
        # Initialize speech processing
        self._init_speech_service()
        
        # Initialize text translation
        self._init_translation_service()
        
        # Setup audio processing queue
        self._init_audio_queue()
        
        logger.info(f"Translation service initialized (GPU: {self.use_gpu})")
    
    def _init_speech_service(self):
        """Initialize speech-to-text and text-to-speech services"""
        if self.use_gpu:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Using device: {self.device}")
            
            # Load Whisper model
            model_name = getattr(Config, 'WHISPER_MODEL', 'base')
            self.speech_model = whisper.load_model(model_name, device=self.device)
        else:
            # Use OpenAI API
            self.openai_client = OpenAI(api_key=Config.OPENAI_TOKEN)
            self.async_openai_client = AsyncOpenAI(api_key=Config.OPENAI_TOKEN)
            
            # Voice mapping for different languages
            self.voice_map = {
                'en': 'nova',
                'pt': 'coco', 
                'ru': 'echo',
                'es': 'coral',
                'fr': 'alloy',
                'de': 'onyx',
                'uz': 'nova',  # fallback
            }
    
    def _init_translation_service(self):
        """Initialize text translation service"""
        self.translator = None
        self.hf_translators = {}
        
        if hasattr(Config, 'DEEPL_TOKEN') and Config.DEEPL_TOKEN:
            try:
                self.translator = deepl.Translator(Config.DEEPL_TOKEN)
                logger.info("DeepL translator initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize DeepL: {e}")
        else:
            logger.warning("DeepL token not found, using fallback translator")
    
    def __init_translation_service_uz(self, ):
        self.token = Config.TILMOCH_TOKEN
        # API endpoint
        url = "https://websocket.tahrirchi.uz/translate-v2"

        # Headers
        headers = {
            "Content-Type": "application/json",
            "Authorization": self.token
        }
    
    def _init_audio_queue(self):
        """Initialize audio processing queue and worker thread"""
        self.audio_queue = queue.Queue()
        self.shutdown_event = threading.Event()
        
        self.worker_thread = threading.Thread(
            target=self._process_audio_queue, 
            daemon=True,
            name="AudioTranslationWorker"
        )
        self.worker_thread.start()
    
    def _process_audio_queue(self):
        """Background worker thread for processing audio translations"""
        print("Translation worker thread started")
        while not self.shutdown_event.is_set():
            try:
                task = self.audio_queue.get(timeout=1)
                if task is None:  # Shutdown signal
                    break
                print(f"Processing translation task from queue...")
                self._handle_translation_task(task)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in audio queue worker: {e}")
                print(f"Error in audio queue worker: {e}")
        print("Translation worker thread stopped")
    
    def _handle_translation_task(self, task):
        """Process a single translation task"""
        audio_data, lang_from, lang_to, room_id, user_id, socketio = task
        start_time = time.time()
        
        try:
            print(f"Starting translation task: {lang_from} -> {lang_to}")
            
            # Step 1: Transcribe audio
            step1_start = time.time()
            print("Step 1: Starting transcription...")
            text = self._transcribe_audio(audio_data, lang_from)
            step1_time = time.time() - step1_start
            print(f"Transcribed text: '{text}' (took {step1_time:.2f}s)")
            if not text or not text.strip():
                print("No text transcribed from audio")
                return
            
            # Step 2: Translate text
            step2_start = time.time()
            print("Step 2: Starting translation...")
            translated_text = self._translate_text(text, lang_from, lang_to)
            step2_time = time.time() - step2_start
            print(f"Translated text: '{translated_text}' (took {step2_time:.2f}s)")
            if not translated_text:
                print("Translation failed")
                return
            
            # Step 3: Generate speech
            step3_start = time.time()
            print("Step 3: Starting TTS...")
            audio_bytes = self._text_to_speech(translated_text, lang_to)
            step3_time = time.time() - step3_start
            print(f"Generated audio bytes: {len(audio_bytes) if audio_bytes else 0} (took {step3_time:.2f}s)")
            if not audio_bytes:
                print("TTS generation failed")
                return
            
            # Step 4: Send to room participants
            step4_start = time.time()
            print("Step 4: Sending result...")
            self._send_translation_result(
                socketio, room_id, user_id, 
                audio_bytes, text, translated_text
            )
            step4_time = time.time() - step4_start
            total_time = time.time() - start_time
            print(f"Translation task completed successfully! (Step 4: {step4_time:.2f}s, Total: {total_time:.2f}s)")
            
        except Exception as e:
            print(f"Translation task failed: {e}")
            logger.error(f"Translation task failed: {e}")
        finally:
            # Clean up temporary files
            self._cleanup_temp_file(audio_data)
    
    def _transcribe_audio(self, audio_data, language: str) -> str:
        """Transcribe audio to text"""
        try:
            if self.use_gpu:
                result = self.speech_model.transcribe(audio_data, language=language)
                return result["text"].strip()
            else:
                with open(audio_data, "rb") as f:
                    result = self.openai_client.audio.transcriptions.create(
                        model="whisper-1",
                        file=f,
                        response_format="text"
                    )
                return result.strip() if isinstance(result, str) else ""
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return ""
    
    def _translate_text(self, text: str, lang_from: str, lang_to: str) -> str:
        """Translate text between languages"""
        if lang_from == lang_to:
            return text
        if lang_to == "en":
            lang_to = "EN-US"
            
        try:
            if self.translator:
                # Use DeepL for better quality
                result = self.translator.translate_text(
                    text=text,
                    source_lang=lang_from.upper(),
                    target_lang=lang_to.upper()
                )
                return result.text
            else:
                # Fallback to HuggingFace
                return self._translate_with_huggingface(text, lang_from, lang_to)
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return text  # Return original if translation fails
    
    def _translate_with_huggingface(self, text: str, lang_from: str, lang_to: str) -> str:
        """Translate using HuggingFace transformers"""
        model_name = f"Helsinki-NLP/opus-mt-{lang_from}-{lang_to}"
        
        if model_name not in self.hf_translators:
            try:
                device = 0 if self.use_gpu and self.device == "cuda" else -1
                self.hf_translators[model_name] = pipeline(
                    "translation",
                    model=model_name,
                    device=device
                )
            except Exception as e:
                logger.error(f"Failed to load translation model {model_name}: {e}")
                return text
        
        try:
            result = self.hf_translators[model_name](text)
            return result[0]['translation_text']
        except Exception as e:
            logger.error(f"HuggingFace translation error: {e}")
            return text
    
    def _text_to_speech(self, text: str, language: str) -> bytes:
        """Convert text to speech"""
        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                return loop.run_until_complete(self._text_to_speech_async(text, language))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"TTS error: {e}")
            return b""
    
    async def _text_to_speech_async(self, text: str, language: str) -> bytes:
        """Async text-to-speech conversion"""
        try:
            if self.use_gpu:
                return await self._edge_tts(text, language)
            else:
                return await self._openai_tts(text, language)
        except Exception as e:
            logger.error(f"Async TTS error: {e}")
            return b""
    
    async def _edge_tts(self, text: str, language: str) -> bytes:
        """Generate speech using Edge TTS and ensure MP3 output"""
        try:
            voice = getattr(Config, 'VOICE_MAP', {}).get(language, 'en-US-AriaNeural')
            communicate = edge_tts.Communicate(text, voice)
            
            audio_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]
            
            # Convert to MP3 if not already
            if not audio_data.startswith(b'ID3') and not audio_data[:2] == b'\xff\xfb':
                # Assume WAV or other format, convert to MP3
                audio_segment = AudioSegment.from_file(io.BytesIO(audio_data))
                mp3_io = io.BytesIO()
                audio_segment.export(mp3_io, format="mp3")
                audio_data = mp3_io.getvalue()
            
            return audio_data
        except Exception as e:
            logger.error(f"Edge TTS error: {e}")
            return b""
    
    async def _openai_tts(self, text: str, language: str) -> bytes:
        """Generate speech using OpenAI TTS"""
        try:
            voice = self.voice_map.get(language, "nova")
            
            async with self.async_openai_client.audio.speech.with_streaming_response.create(
                model="tts-1",
                voice=voice,
                input=text,
                response_format="mp3"
            ) as response:
                audio_data = b""
                async for chunk in response.iter_bytes():
                    audio_data += chunk
                return audio_data
        except Exception as e:
            logger.error(f"OpenAI TTS error: {e}")
            return b""
    
    def _send_translation_result(self, socketio, room_id: str, user_id: str, 
                               audio_bytes: bytes, original_text: str, 
                               translated_text: str):
        """Send translation result to the intended recipient only"""
        try:
            audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
            print(f"Sending translation result to room {room_id}, target user: {user_id}")
            print(f"Audio size: {len(audio_bytes)} bytes, Base64 size: {len(audio_base64)} chars")
            
            socketio.emit('translated_audio', {
                'audio': audio_base64,
                'text': translated_text,
                'original_text': original_text,
                'target_user': user_id  # specify which user should receive this translation
            }, room=room_id)  # emit to the entire room
            
            print("Translation result sent successfully!")
        except Exception as e:
            logger.error(f"Failed to send translation result: {e}")
            print(f"Failed to send translation result: {e}")
    
    def _cleanup_temp_file(self, file_path):
        """Clean up temporary files"""
        try:
            if isinstance(file_path, str) and os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file {file_path}: {e}")
    
    # Public API methods
    def transcribe_audio(self, audio_path: str, language: str = "en") -> str:
        """Transcribe audio file to text"""
        return self._transcribe_audio(audio_path, language)
    
    def translate_text(self, text: str, lang_from: str, lang_to: str) -> str:
        """Translate text between languages"""
        return self._translate_text(text, lang_from, lang_to)
    
    def text_to_speech(self, text: str, language: str) -> bytes:
        """Convert text to speech"""
        return self._text_to_speech(text, language)
    
    def add_translation_task(self, audio_data, lang_from: str, lang_to: str, 
                           room_id: str, user_id: str, socketio):
        """Add a translation task to the processing queue"""
        try:
            print(f"Adding translation task to queue: {lang_from} -> {lang_to}")
            self.audio_queue.put((audio_data, lang_from, lang_to, room_id, user_id, socketio))
            print(f"Task added to queue. Queue size: {self.audio_queue.qsize()}")
        except Exception as e:
            logger.error(f"Failed to add translation task: {e}")
            print(f"Failed to add translation task: {e}")
    
    def shutdown(self):
        """Gracefully shutdown the service"""
        logger.info("Shutting down translation service...")
        self.shutdown_event.set()
        self.audio_queue.put(None)  # Signal worker to stop
        
        if self.worker_thread.is_alive():
            self.worker_thread.join(timeout=5)
        
        logger.info("Translation service shutdown complete")
    
    def get_status(self) -> Dict[str, Any]:
        """Get service status information"""
        return {
            'gpu_enabled': self.use_gpu,
            'device': getattr(self, 'device', 'cpu'),
            'deepl_available': self.translator is not None,
            'queue_size': self.audio_queue.qsize(),
            'worker_alive': self.worker_thread.is_alive()
        }
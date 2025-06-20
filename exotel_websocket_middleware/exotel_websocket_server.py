import asyncio
import websockets
import base64
import json
import requests
import os

from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

# Set pydub ffmpeg and ffprobe paths explicitly with verification
ffmpeg_bin_path = os.path.join(os.getcwd(), 'ffmpeg', 'ffmpeg-7.1.1-essentials_build', 'bin')
ffmpeg_path = os.path.join(ffmpeg_bin_path, 'ffmpeg.exe')
ffprobe_path = os.path.join(ffmpeg_bin_path, 'ffprobe.exe')

# Set environment variables for ffmpeg and ffprobe binaries
os.environ["FFMPEG_BINARY"] = ffmpeg_path
os.environ["FFPROBE_BINARY"] = ffprobe_path

# Add ffmpeg bin directory to PATH environment variable
os.environ["PATH"] = ffmpeg_bin_path + os.pathsep + os.environ.get("PATH", "")

from pydub import AudioSegment
import io
import logging

# Configure logging before using logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Verify paths exist before setting
if not os.path.exists(ffmpeg_path):
    raise RuntimeError(f"FFmpeg executable not found at: {ffmpeg_path}")
if not os.path.exists(ffprobe_path):
    raise RuntimeError(f"FFprobe executable not found at: {ffprobe_path}")

logger.info(f"Using FFmpeg at: {ffmpeg_path}")
logger.info(f"Using FFprobe at: {ffprobe_path}")

# Set paths and verify they're properly configured
AudioSegment.converter = ffmpeg_path
AudioSegment.ffprobe = ffprobe_path

class TTSService:
    def __init__(self):
        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        self.voice_id = os.getenv("ELEVENLABS_VOICE_ID")
        if not self.api_key or not self.voice_id:
            raise ValueError("Missing ElevenLabs API credentials in environment variables")

    def generate_speech(self, text: str) -> bytes:
        """Generate TTS audio from text using ElevenLabs API"""
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        json_data = {
            "text": text,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }
        
        try:
            response = requests.post(url, json=json_data, headers=headers)
            response.raise_for_status()
            return response.content
        except requests.exceptions.RequestException as e:
            logger.error(f"ElevenLabs API error: {str(e)}")
            return None

class AudioConverter:
    @staticmethod
    def to_pcm_base64(audio_bytes: bytes) -> str:
        """Convert audio bytes to 16-bit 8kHz mono PCM base64 string"""
        try:
            # Verify ffmpeg/ffprobe are accessible
            if not os.path.exists(AudioSegment.converter):
                raise FileNotFoundError(f"ffmpeg not found at {AudioSegment.converter}")
            if not os.path.exists(AudioSegment.ffprobe):
                raise FileNotFoundError(f"ffprobe not found at {AudioSegment.ffprobe}")

            audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
            audio = audio.set_frame_rate(8000).set_channels(1).set_sample_width(2)
            pcm_bytes = audio.raw_data
            return base64.b64encode(pcm_bytes).decode('utf-8')
        except Exception as e:
            logger.error(f"Audio conversion failed: {str(e)}")
            logger.debug("FFmpeg paths - Converter: %s, FFprobe: %s", 
                        AudioSegment.converter, AudioSegment.ffprobe)
            return None

async def exotel_handler(websocket, path=None):
    logger.info("WebSocket connection established")
    tts_service = TTSService()
    
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                if not isinstance(data, dict):
                    raise ValueError("Invalid message format")
                
                event = data.get("event")
                logger.info(f"Event received: {event}")

                if event == "connected":
                    logger.info("Call connected")
                
                elif event == "start":
                    call_info = data.get("start", {})
                    logger.info(f"Call started from: {call_info.get('from')} to: {call_info.get('to')}")
                
                elif event == "media":
                    media = data.get("media", {})
                    if not all(k in media for k in ["payload", "chunk", "timestamp"]):
                        raise ValueError("Missing required media fields")
                    
                    audio_b64 = media["payload"]
                    raw_audio = base64.b64decode(audio_b64)
                    logger.debug(f"Received media chunk {media['chunk']} - {len(raw_audio)} bytes")

                    # Get response text from call parameters or use default
                    response_text = data.get("parameters", {}).get("response_text", 
                                      "Hello, this is an automated response")

                    # Generate TTS response
                    audio_bytes = tts_service.generate_speech(response_text)
                    if not audio_bytes:
                        logger.error("Failed to generate TTS audio")
                        continue

                    audio_b64_response = AudioConverter.to_pcm_base64(audio_bytes)
                    if not audio_b64_response:
                        logger.error("Failed to convert audio to PCM")
                        continue

                    response = {
                        "event": "media",
                        "stream_sid": data["stream_sid"],
                        "sequence_number": data["sequence_number"] + 1,
                        "media": {
                            "chunk": media["chunk"] + 1,
                            "timestamp": str(int(media["timestamp"]) + 20),
                            "payload": audio_b64_response
                        }
                    }
                    await websocket.send(json.dumps(response))
                
                elif event == "stop":
                    logger.info("Call ended")
                
                else:
                    logger.warning(f"Unknown event type: {event}")

            except json.JSONDecodeError:
                logger.error("Invalid JSON received")
            except ValueError as e:
                logger.error(f"Invalid message: {str(e)}")
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")

    except websockets.exceptions.ConnectionClosedError as e:
        logger.error(f"WebSocket connection closed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
    finally:
        logger.info("WebSocket connection terminated")

async def main():
    PORT = int(os.getenv("WEBSOCKET_PORT", "8777"))
    logger.info(f"Starting server on ws://0.0.0.0:{PORT}")

    async with websockets.serve(exotel_handler, "0.0.0.0", PORT):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())

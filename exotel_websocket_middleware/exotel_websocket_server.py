import asyncio
import websockets
import base64
import json
import requests
import os
import io
import logging
from dotenv import load_dotenv
from aiohttp import web
from pydub import AudioSegment

# Load environment variables
load_dotenv()

# Set ffmpeg paths
ffmpeg_bin_path = os.path.join(os.getcwd(), 'ffmpeg', 'ffmpeg-7.1.1-essentials_build', 'bin')
ffmpeg_path = os.path.join(ffmpeg_bin_path, 'ffmpeg.exe')
ffprobe_path = os.path.join(ffmpeg_bin_path, 'ffprobe.exe')

# Validate paths
if not os.path.exists(ffmpeg_path):
    raise RuntimeError(f"FFmpeg executable not found at: {ffmpeg_path}")
if not os.path.exists(ffprobe_path):
    raise RuntimeError(f"FFprobe executable not found at: {ffprobe_path}")

# Set ffmpeg env vars
os.environ["FFMPEG_BINARY"] = ffmpeg_path
os.environ["FFPROBE_BINARY"] = ffprobe_path
os.environ["PATH"] = ffmpeg_bin_path + os.pathsep + os.environ.get("PATH", "")

# Assign ffmpeg to pydub
AudioSegment.converter = ffmpeg_path
AudioSegment.ffprobe = ffprobe_path

# Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.info(f"Using FFmpeg at: {ffmpeg_path}")
logger.info(f"Using FFprobe at: {ffprobe_path}")


class TTSService:
    def __init__(self):
        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        self.voice_id = os.getenv("ELEVENLABS_VOICE_ID")
        if not self.api_key or not self.voice_id:
            raise ValueError("Missing ElevenLabs API credentials in environment variables")

    def generate_speech(self, text: str) -> bytes:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "text": text,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }
        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.content
        except requests.RequestException as e:
            logger.error(f"TTS generation failed: {str(e)}")
            return None


class AudioConverter:
    @staticmethod
    def to_pcm_base64(audio_bytes: bytes) -> str:
        try:
            audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
            audio = audio.set_frame_rate(8000).set_channels(1).set_sample_width(2)
            pcm_bytes = audio.raw_data
            return base64.b64encode(pcm_bytes).decode('utf-8')
        except Exception as e:
            logger.error(f"Audio conversion failed: {str(e)}")
            return None


async def exotel_handler(ws):
    logger.info("WebSocket connection established")
    tts_service = TTSService()

    try:
        async for message in ws:
            try:
                data = json.loads(message)
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
                    logger.debug(f"Received chunk {media['chunk']} ({len(raw_audio)} bytes)")

                    response_text = data.get("parameters", {}).get("response_text", "Hello, this is an automated response")

                    audio_bytes = tts_service.generate_speech(response_text)
                    if not audio_bytes:
                        continue

                    audio_b64_response = AudioConverter.to_pcm_base64(audio_bytes)
                    if not audio_b64_response:
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
                    await ws.send(json.dumps(response))

                elif event == "stop":
                    logger.info("Call ended")

                else:
                    logger.warning(f"Unknown event type: {event}")

            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")

    except websockets.exceptions.ConnectionClosed:
        logger.info("WebSocket connection closed")


# ---------------------------
# AIOHTTP + WEBSOCKET SERVER
# ---------------------------

async def healthcheck(request):
    return web.Response(text="OK")


async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    await exotel_handler(ws)
    return ws


async def main():
    PORT = int(os.getenv("WEBSOCKET_PORT", "8777"))
    logger.info(f"Starting server at ws://0.0.0.0:{PORT}/ws")

    app = web.Application()
    app.router.add_get("/", healthcheck)       # HTTP HEAD/GET check
    app.router.add_get("/ws", websocket_handler)  # WebSocket endpoint

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())

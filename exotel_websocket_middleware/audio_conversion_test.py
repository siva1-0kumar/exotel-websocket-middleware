import os
import base64
import logging
from pydub import AudioSegment
import io
import numpy as np

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Set ffmpeg and ffprobe paths (adjust if needed)
ffmpeg_bin_path = os.path.join(os.getcwd(), 'ffmpeg', 'ffmpeg-7.1.1-essentials_build', 'bin')
ffmpeg_path = os.path.join(ffmpeg_bin_path, 'ffmpeg.exe')
ffprobe_path = os.path.join(ffmpeg_bin_path, 'ffprobe.exe')

os.environ["FFMPEG_BINARY"] = ffmpeg_path
os.environ["FFPROBE_BINARY"] = ffprobe_path
os.environ["PATH"] = ffmpeg_bin_path + os.pathsep + os.environ.get("PATH", "")

AudioSegment.converter = ffmpeg_path
AudioSegment.ffprobe = ffprobe_path

def to_pcm_base64(audio_bytes: bytes) -> str:
    try:
        audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
        audio = audio.set_frame_rate(8000).set_channels(1).set_sample_width(2)
        pcm_bytes = audio.raw_data
        return base64.b64encode(pcm_bytes).decode('utf-8')
    except Exception as e:
        logging.error(f"Audio conversion failed: {str(e)}")
        return None

def generate_sine_wave(duration_ms=1000, freq=440, sample_rate=44100):
    t = np.linspace(0, duration_ms / 1000, int(sample_rate * duration_ms / 1000), False)
    sine_wave = 0.5 * np.sin(2 * np.pi * freq * t)
    audio_data = (sine_wave * (2**15 - 1)).astype(np.int16)
    return audio_data.tobytes(), sample_rate

def main():
    # Generate synthetic sine wave audio bytes as WAV
    audio_data, sample_rate = generate_sine_wave()
    audio_segment = AudioSegment(
        data=audio_data,
        sample_width=2,
        frame_rate=sample_rate,
        channels=1
    )
    audio_bytes_io = io.BytesIO()
    audio_segment.export(audio_bytes_io, format="wav")
    audio_bytes = audio_bytes_io.getvalue()

    pcm_b64 = to_pcm_base64(audio_bytes)
    if pcm_b64:
        logging.info(f"Audio conversion successful, base64 length: {len(pcm_b64)}")
    else:
        logging.error("Audio conversion failed")

if __name__ == "__main__":
    main()

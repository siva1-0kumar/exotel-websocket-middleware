import pytest
import base64
from audio_conversion_test import to_pcm_base64, generate_sine_wave
import io
from pydub import AudioSegment

def test_audio_conversion_success():
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
    assert pcm_b64 is not None
    assert isinstance(pcm_b64, str)
    assert len(pcm_b64) > 0

def test_audio_conversion_invalid_data():
    invalid_audio = b"not audio data"
    pcm_b64 = to_pcm_base64(invalid_audio)
    assert pcm_b64 is None

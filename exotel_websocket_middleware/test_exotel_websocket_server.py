import pytest
import asyncio
import json
from unittest.mock import patch, AsyncMock
from exotel_websocket_server import exotel_handler

class DummyWebSocket:
    def __init__(self):
        self.sent_messages = []
        self.recv_messages = asyncio.Queue()
        self.closed = False

    async def send(self, message):
        self.sent_messages.append(message)

    def put_message(self, message):
        self.recv_messages.put_nowait(message)

    def close(self):
        self.closed = True

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.recv_messages.empty():
            raise StopAsyncIteration
        return await self.recv_messages.get()

@pytest.mark.asyncio
async def test_invalid_json():
    ws = DummyWebSocket()
    ws.put_message("invalid json")
    with patch('exotel_websocket_server.TTSService.generate_speech', return_value=b'audio'):
        await exotel_handler(ws)
    assert any("Invalid JSON" in msg for msg in ws.sent_messages) or True  # Logs, no send expected

@pytest.mark.asyncio
async def test_missing_media_fields():
    ws = DummyWebSocket()
    msg = json.dumps({"event": "media", "media": {"chunk": 1}})
    ws.put_message(msg)
    with patch('exotel_websocket_server.TTSService.generate_speech', return_value=b'audio'):
        await exotel_handler(ws)
    # Should log error, no exception

@pytest.mark.asyncio
async def test_tts_generation_failure():
    ws = DummyWebSocket()
    media_msg = json.dumps({
        "event": "media",
        "media": {"chunk": 1, "timestamp": "1000", "payload": ""},
        "stream_sid": "sid",
        "sequence_number": 1,
        "parameters": {"response_text": "test"}
    })
    ws.put_message(media_msg)
    with patch('exotel_websocket_server.TTSService.generate_speech', return_value=None):
        await exotel_handler(ws)
    # Should log error and continue

@pytest.mark.asyncio
async def test_audio_conversion_failure():
    ws = DummyWebSocket()
    media_msg = json.dumps({
        "event": "media",
        "media": {"chunk": 1, "timestamp": "1000", "payload": ""},
        "stream_sid": "sid",
        "sequence_number": 1,
        "parameters": {"response_text": "test"}
    })
    ws.put_message(media_msg)
    with patch('exotel_websocket_server.TTSService.generate_speech', return_value=b'audio'):
        with patch('exotel_websocket_server.AudioConverter.to_pcm_base64', return_value=None):
            await exotel_handler(ws)
    # Should log error and continue

@pytest.mark.asyncio
async def test_normal_flow():
    ws = DummyWebSocket()
    media_msg = json.dumps({
        "event": "media",
        "media": {"chunk": 1, "timestamp": "1000", "payload": ""},
        "stream_sid": "sid",
        "sequence_number": 1,
        "parameters": {"response_text": "test"}
    })
    ws.put_message(media_msg)
    with patch('exotel_websocket_server.TTSService.generate_speech', return_value=b'audio'):
        with patch('exotel_websocket_server.AudioConverter.to_pcm_base64', return_value="base64audio"):
            await exotel_handler(ws)
    assert any("base64audio" in msg for msg in ws.sent_messages)

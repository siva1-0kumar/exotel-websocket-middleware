import asyncio
import websockets
import json
import pytest
import pytest_asyncio

@pytest.mark.asyncio
async def test_client():
    uri = "ws://localhost:8765"
    async with websockets.connect(uri) as websocket:
        # Send connected event
        await websocket.send(json.dumps({"event": "connected"}))
        print("Sent connected event")

        # Send start event
        await websocket.send(json.dumps({"event": "start", "start": {"from": "1234", "to": "5678"}}))
        print("Sent start event")

        # Send media event with dummy payload
        media_event = {
            "event": "media",
            "stream_sid": "test_stream",
            "sequence_number": 1,
            "media": {
                "chunk": 1,
                "timestamp": "0",
                "payload": "UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAIA+AAACABAAZGF0YQAAAAA="
            }
        }
        await websocket.send(json.dumps(media_event))
        print("Sent media event")

        # Receive response
        response = await websocket.recv()
        print("Received response:", response)

        # Send stop event
        await websocket.send(json.dumps({"event": "stop"}))
        print("Sent stop event")

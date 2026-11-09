import pytest
import json
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint(async_client: AsyncClient):
    resp = await async_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "Figgy" in data["service"]


@pytest.mark.asyncio
async def test_chat_endpoint_standard(async_client: AsyncClient):
    payload = {
        "message": "I'm bored, what should I do?",
        "conversation_id": "test-chat-conv",
        "device_id": "test-device"
    }
    resp = await async_client.post("/v1/chat", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["conversation_id"] == "test-chat-conv"
    assert "reply" in data
    assert data["status"] == "completed"


@pytest.mark.asyncio
async def test_chat_stream_endpoint(async_client: AsyncClient):
    payload = {
        "message": "Give me a quick stream",
        "conversation_id": "test-stream-conv",
        "device_id": "test-device"
    }
    resp = await async_client.post("/v1/chat/stream", json=payload)
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    text = resp.text
    assert "data: " in text
    assert '"done": true' in text.lower() or '"done":true' in text.lower()


@pytest.mark.asyncio
async def test_persona_switching_and_status(async_client: AsyncClient):
    # Get current status
    status_resp = await async_client.get("/v1/persona")
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert "available_personas" in data
    assert len(data["available_personas"]) == 5

    # Switch to Homelander
    switch_resp = await async_client.post(
        "/v1/persona",
        json={"mode": "single", "persona": "homelander", "intensity": 0.9}
    )
    assert switch_resp.status_code == 200
    s_data = switch_resp.json()
    assert s_data["active_persona"] == "homelander"
    assert s_data["device_command"]["action"] == "set_led"

    # Switch to Fusion
    fusion_resp = await async_client.post(
        "/v1/persona",
        json={
            "mode": "fusion",
            "fusion_weights": {"dark_comedian": 0.7, "existentialist": 0.3}
        }
    )
    assert fusion_resp.status_code == 200
    f_data = fusion_resp.json()
    assert f_data["mode"] == "fusion"


@pytest.mark.asyncio
async def test_device_event_and_actions(async_client: AsyncClient):
    # Trigger button press event
    btn_event = {
        "device_id": "esp32-001",
        "event": "button_click",
        "battery": 88
    }
    resp = await async_client.post("/v1/device/event", json=btn_event)
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "device_action"
    actions = data["actions"]
    assert any(a["action"] == "haptic_pulse" for a in actions)
    assert any(a["action"] == "set_led" for a in actions)


@pytest.mark.asyncio
async def test_memory_api_endpoints(async_client: AsyncClient):
    # Store a memory
    mem_payload = {
        "category": "semantic",
        "key": "test_hobby",
        "content": "User loves building electronics",
        "confidence": 0.9
    }
    create_resp = await async_client.post("/v1/memory", json=mem_payload)
    assert create_resp.status_code == 200
    mem_id = create_resp.json()["id"]

    # List memories
    list_resp = await async_client.get("/v1/memory?category=semantic")
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) >= 1
    assert items[0]["key"] == "test_hobby"

    # Delete memory
    del_resp = await async_client.delete(f"/v1/memory/{mem_id}")
    assert del_resp.status_code == 200

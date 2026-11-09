import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_db
from app.device.manager import DeviceManager
from app.device.commands import DeviceActionResponse, create_persona_led_feedback
from app.personality.manager import personality_manager
from app.core.security import verify_api_key

router = APIRouter(prefix="/device", tags=["Device"])


class DeviceEventRequest(BaseModel):
    device_id: str = Field(default="figgy-001")
    event: str = Field(..., description="button_click, wake_word, heartbeat, offline_sync")
    battery: Optional[int] = Field(default=None, ge=0, le=100)
    led_status: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@router.post("/event", response_model=DeviceActionResponse, dependencies=[Depends(verify_api_key)])
async def handle_device_event(
    req: DeviceEventRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Handle incoming device event from ESP32.
    Returns structured action commands (LED patterns, haptic pulses, etc.) for the ESP32.
    """
    meta_str = json.dumps(req.metadata) if req.metadata else None
    await DeviceManager.update_device_event(
        session=session,
        device_id=req.device_id,
        event_type=req.event,
        battery=req.battery,
        led_status=req.led_status,
        metadata=meta_str
    )

    actions: List[Dict[str, Any]] = []

    # Map device events to appropriate hardware responses
    if req.event == "button_click":
        # Short haptic feedback on button press
        actions.append({"action": "haptic_pulse", "parameters": {"duration_ms": 60, "intensity": 80}})
        # Active persona color pulse
        active = personality_manager.active_persona
        actions.append(create_persona_led_feedback(active))

    elif req.event == "wake_word":
        # Double pulse when wake word is detected
        actions.append({"action": "haptic_pulse", "parameters": {"duration_ms": 100, "intensity": 90}})
        actions.append({"action": "set_led", "parameters": {"color": "white", "pattern": "pulse", "brightness": 100}})

    elif req.event == "heartbeat":
        # Echo current persona led mode to maintain sync
        active = personality_manager.active_persona
        actions.append(create_persona_led_feedback(active))

    return DeviceActionResponse(actions=actions)


@router.get("/status", dependencies=[Depends(verify_api_key)])
async def get_device_status(
    device_id: str = "figgy-001",
    session: AsyncSession = Depends(get_db)
):
    """Check device connectivity and recorded status."""
    status = await DeviceManager.get_device_status(session, device_id)
    if not status:
        return {"device_id": device_id, "status": "unknown", "registered": False}
    return {"status": "registered", "device": status}

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class LEDCommand(BaseModel):
    action: str = "set_led"
    color: str = Field(default="purple", description="Color: red, green, blue, purple, yellow, cyan, white")
    pattern: str = Field(default="pulse", description="Pattern: solid, pulse, rainbow, blink, breathe")
    brightness: int = Field(default=80, ge=0, le=100)


class HapticCommand(BaseModel):
    action: str = "haptic_pulse"
    duration_ms: int = Field(default=150, ge=10, le=2000)
    intensity: int = Field(default=80, ge=0, le=100)


class DeviceActionResponse(BaseModel):
    type: str = "device_action"
    actions: List[Dict[str, Any]] = Field(default_factory=list)


def create_persona_led_feedback(persona_id: str) -> Dict[str, Any]:
    """Map personality mode to distinctive LED feedback color and pulse."""
    colormap = {
        "dark_comedian": {"color": "purple", "pattern": "pulse", "brightness": 90},
        "existentialist": {"color": "cyan", "pattern": "breathe", "brightness": 60},
        "first_principles": {"color": "blue", "pattern": "solid", "brightness": 100},
        "ted_mosby": {"color": "yellow", "pattern": "pulse", "brightness": 85},
        "homelander": {"color": "red", "pattern": "blink", "brightness": 100},
    }
    spec = colormap.get(persona_id, {"color": "purple", "pattern": "pulse", "brightness": 80})
    return {
        "action": "set_led",
        "parameters": spec
    }

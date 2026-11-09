from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict
from app.personality.manager import personality_manager
from app.device.commands import create_persona_led_feedback
from app.core.security import verify_api_key

router = APIRouter(prefix="/persona", tags=["Persona"])


class PersonaSwitchRequest(BaseModel):
    mode: str = Field(default="single", description="'single' or 'fusion'")
    persona: Optional[str] = Field(default=None, description="Persona ID if mode is 'single'")
    fusion_weights: Optional[Dict[str, float]] = Field(default=None, description="Weights if mode is 'fusion'")
    intensity: Optional[float] = Field(default=None, ge=0.1, le=1.0)


@router.get("", dependencies=[Depends(verify_api_key)])
async def get_persona_status():
    """Retrieve current active persona, intensity, fusion weights, and list of all available personas."""
    return personality_manager.get_status()


@router.post("", dependencies=[Depends(verify_api_key)])
async def switch_persona(req: PersonaSwitchRequest):
    """Switch Figgy's personality mode, fusion weights, or intensity."""
    try:
        if req.mode == "single":
            if not req.persona:
                raise HTTPException(status_code=400, detail="Missing 'persona' field for single mode")
            profile = personality_manager.set_single_persona(req.persona, req.intensity)
            led_action = create_persona_led_feedback(profile.id)
            return {
                "status": "success",
                "mode": "single",
                "active_persona": profile.id,
                "name": profile.name,
                "intensity": personality_manager.intensity,
                "device_command": led_action
            }
        elif req.mode == "fusion":
            if not req.fusion_weights:
                raise HTTPException(status_code=400, detail="Missing 'fusion_weights' field for fusion mode")
            weights = personality_manager.set_fusion(req.fusion_weights, req.intensity)
            return {
                "status": "success",
                "mode": "fusion",
                "fusion_weights": weights,
                "intensity": personality_manager.intensity,
                "device_command": {
                    "action": "set_led",
                    "parameters": {"color": "rainbow", "pattern": "pulse", "brightness": 90}
                }
            }
        else:
            raise HTTPException(status_code=400, detail=f"Invalid mode '{req.mode}'. Choose 'single' or 'fusion'.")
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

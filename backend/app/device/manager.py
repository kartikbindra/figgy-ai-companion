from datetime import datetime, timezone
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.models import DeviceState


class DeviceManager:
    @staticmethod
    async def update_device_event(
        session: AsyncSession,
        device_id: str,
        event_type: str,
        battery: Optional[int] = None,
        led_status: Optional[str] = None,
        metadata: Optional[str] = None
    ) -> DeviceState:
        stmt = select(DeviceState).where(DeviceState.device_id == device_id)
        result = await session.execute(stmt)
        dev = result.scalar_one_or_none()

        now = datetime.now(timezone.utc)
        if not dev:
            dev = DeviceState(
                device_id=device_id,
                last_seen=now,
                battery_level=battery,
                led_status=led_status,
                extra_data=metadata
            )
            session.add(dev)
        else:
            dev.last_seen = now
            if battery is not None:
                dev.battery_level = battery
            if led_status is not None:
                dev.led_status = led_status
            if metadata is not None:
                dev.extra_data = metadata

        await session.commit()
        await session.refresh(dev)
        return dev

    @staticmethod
    async def get_device_status(session: AsyncSession, device_id: str) -> Optional[Dict[str, Any]]:
        stmt = select(DeviceState).where(DeviceState.device_id == device_id)
        result = await session.execute(stmt)
        dev = result.scalar_one_or_none()
        if not dev:
            return None
        return {
            "device_id": dev.device_id,
            "last_seen": dev.last_seen.isoformat() if dev.last_seen else None,
            "battery_level": dev.battery_level,
            "led_status": dev.led_status,
            "extra_data": dev.extra_data
        }

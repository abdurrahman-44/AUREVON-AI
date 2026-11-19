from typing import Any, Dict, Optional
from backend.app.services.live.weather import WeatherService


class WeatherTool:
    """Provides verified real-time weather and forecasts for any location."""

    name = "weather"

    @classmethod
    async def execute(cls, location: str, target_day: Optional[str] = "current") -> Dict[str, Any]:
        return await WeatherService.get_weather(location=location, target_day=target_day or "current")

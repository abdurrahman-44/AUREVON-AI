from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from backend.app.services.tools.date_calculator import DateCalculator


class DateTimeTool:
    """Provides verified current UTC/local date, time, day of week, exact age, and date calculations."""

    name = "date_time"

    @classmethod
    def execute(
        cls,
        timezone_name: Optional[str] = None,
        offset_days: int = 0,
        dob: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        reference_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        tz_str = (timezone_name or "Asia/Colombo").strip()

        # 1. Age Calculation
        if dob and dob.strip():
            return DateCalculator.calculate_exact_age(
                dob_input=dob.strip(),
                current_date_input=reference_date,
                tz_name=tz_str,
            )

        # 2. Date Difference Calculation
        if start_date and end_date:
            return DateCalculator.calculate_date_difference(
                start_date_str=start_date.strip(),
                end_date_str=end_date.strip(),
                tz_name=tz_str,
            )

        # 3. Base Date & Time
        now_utc = datetime.now(timezone.utc)
        tz_upper = tz_str.upper()
        if tz_upper in ("UTC", "GMT", "Z"):
            target_dt = now_utc
            tz_label = "UTC"
        else:
            try:
                zi = ZoneInfo(tz_str)
                target_dt = now_utc.astimezone(zi)
                tz_label = tz_str
            except Exception:
                if tz_str.lower() in ("asia/colombo", "colombo", "sri lanka", "sri lanka standard time"):
                    target_dt = now_utc.astimezone(timezone(timedelta(hours=5, minutes=30)))
                    tz_label = "Asia/Colombo (UTC+05:30)"
                else:
                    target_dt = datetime.now().astimezone()
                    tz_label = str(target_dt.tzinfo or "local")

        if offset_days:
            target_dt = target_dt + timedelta(days=int(offset_days))

        return {
            "ok": True,
            "iso": target_dt.isoformat(),
            "date": target_dt.strftime("%Y-%m-%d"),
            "formatted_date": target_dt.strftime("%d %B %Y"),
            "time_24h": target_dt.strftime("%H:%M:%S"),
            "day_of_week": target_dt.strftime("%A"),
            "timezone": tz_label,
            "utc_iso": now_utc.isoformat(),
        }

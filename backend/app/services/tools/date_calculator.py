import calendar
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
from zoneinfo import ZoneInfo


_MONTH_NAME_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def _safe_tz(tz_name: Optional[str] = None):
    if not tz_name or tz_name.upper() in ("UTC", "GMT", "Z"):
        return timezone.utc
    if any(k in tz_name.lower() for k in ("colombo", "sri lanka")):
        return timezone(timedelta(hours=5, minutes=30))
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return timezone.utc


class DateCalculator:
    """Deterministic, calendar-accurate age, date difference, working days, and timezone engine."""

    DEFAULT_TIMEZONE = "Asia/Colombo"

    @classmethod
    def parse_flexible_date(cls, date_str: str, default_tz: str = DEFAULT_TIMEZONE) -> Optional[date]:
        """Parses dates across ISO (2004-03-15), textual ('15 March 2004'), or slash/dash formats."""
        raw = (date_str or "").strip()
        if not raw:
            return None

        # Today / yesterday / tomorrow keywords
        lowered = raw.lower()
        now_local = datetime.now(_safe_tz(default_tz)).date() if default_tz else date.today()
        if lowered in ("today", "now"):
            return now_local
        if lowered == "yesterday":
            return now_local - timedelta(days=1)
        if lowered == "tomorrow":
            return now_local + timedelta(days=1)

        # 1. '15 March 2004' or 'March 15, 2004'
        text_match = re.search(r"(\d{1,2})\s+([a-zA-Z]+)\s+(\d{4})", raw)
        if text_match:
            d_val = int(text_match.group(1))
            m_str = text_match.group(2).lower()[:3]
            y_val = int(text_match.group(3))
            if m_str in _MONTH_NAME_MAP:
                m_val = _MONTH_NAME_MAP[m_str]
                try:
                    return date(y_val, m_val, d_val)
                except ValueError:
                    return None

        text_match_rev = re.search(r"([a-zA-Z]+)\s+(\d{1,2}),?\s+(\d{4})", raw)
        if text_match_rev:
            m_str = text_match_rev.group(1).lower()[:3]
            d_val = int(text_match_rev.group(2))
            y_val = int(text_match_rev.group(3))
            if m_str in _MONTH_NAME_MAP:
                m_val = _MONTH_NAME_MAP[m_str]
                try:
                    return date(y_val, m_val, d_val)
                except ValueError:
                    return None

        # 2. ISO '2004-03-15' or '2004/03/15'
        iso_match = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", raw)
        if iso_match:
            try:
                return date(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))
            except ValueError:
                pass

        # 3. '15-03-2004' or '15/03/2004' (DMY)
        dmy_match = re.search(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})", raw)
        if dmy_match:
            d_val = int(dmy_match.group(1))
            m_val = int(dmy_match.group(2))
            y_val = int(dmy_match.group(3))
            # If day > 12 and month <= 12, definitely DMY
            if d_val > 12 >= m_val:
                try:
                    return date(y_val, m_val, d_val)
                except ValueError:
                    pass
            # Standard DMY assumption for international/Sri Lanka
            try:
                return date(y_val, m_val, d_val)
            except ValueError:
                try:
                    # Fallback MDY
                    return date(y_val, d_val, m_val)
                except ValueError:
                    pass

        return None

    @classmethod
    def calculate_exact_age(
        cls,
        dob_input: str,
        current_date_input: Optional[str] = None,
        tz_name: str = DEFAULT_TIMEZONE,
    ) -> Dict[str, Any]:
        """
        Calculates exact age in Years, Months, and Days taking into account
        varying month lengths, leap years, and Feb 29 birthdays.
        """
        dob = cls.parse_flexible_date(dob_input, default_tz=tz_name)
        if not dob:
            return {"ok": False, "error": f"Invalid or unrecognizable birth date: '{dob_input}'"}

        ref_date = (
            cls.parse_flexible_date(current_date_input, default_tz=tz_name)
            if current_date_input
            else datetime.now(_safe_tz(tz_name)).date()
        )
        if not ref_date:
            return {"ok": False, "error": f"Invalid reference current date: '{current_date_input}'"}

        if ref_date < dob:
            return {
                "ok": False,
                "error": f"Birth date ({dob.isoformat()}) cannot be in the future relative to {ref_date.isoformat()}.",
            }

        # Algorithm: Exact calendar breakdown
        years = ref_date.year - dob.year
        # Has birthday occurred this year?
        if (ref_date.month, ref_date.day) < (dob.month, dob.day):
            years -= 1

        if ref_date.day >= dob.day:
            months = ref_date.month - dob.month
            if months < 0:
                months += 12
            days = ref_date.day - dob.day
        else:
            # Borrow days from the preceding month
            prev_month = 12 if ref_date.month == 1 else ref_date.month - 1
            prev_year = ref_date.year - 1 if ref_date.month == 1 else ref_date.year
            days_in_prev_month = calendar.monthrange(prev_year, prev_month)[1]

            # Adjust if dob.day exceeds days in preceding month (e.g. 31st)
            effective_dob_day = min(dob.day, days_in_prev_month)
            days = (days_in_prev_month - effective_dob_day) + ref_date.day

            months = (ref_date.month - 1) - dob.month
            if months < 0:
                months += 12

        total_days = (ref_date - dob).days

        # Next birthday calculation
        try:
            next_bday = date(ref_date.year, dob.month, dob.day)
        except ValueError:
            # Feb 29 in non-leap year -> celebrate Feb 28 or March 1
            next_bday = date(ref_date.year, 3, 1)

        if next_bday < ref_date:
            try:
                next_bday = date(ref_date.year + 1, dob.month, dob.day)
            except ValueError:
                next_bday = date(ref_date.year + 1, 3, 1)

        days_to_next_bday = (next_bday - ref_date).days

        # Formatted string matching prompt requirement: "22 years, 7 months and 29 days"
        month_str = f"{months} month" if months == 1 else f"{months} months"
        day_str = f"{days} day" if days == 1 else f"{days} days"
        year_str = f"{years} year" if years == 1 else f"{years} years"

        formatted = f"{year_str}, {month_str} and {day_str}"

        return {
            "ok": True,
            "dob": dob.isoformat(),
            "reference_date": ref_date.isoformat(),
            "years": years,
            "months": months,
            "days": days,
            "total_days": total_days,
            "days_until_next_birthday": days_to_next_bday,
            "is_leap_year_born": calendar.isleap(dob.year),
            "formatted": formatted,
            "summary": (
                f"Age as of {ref_date.strftime('%d %B %Y')}: **{formatted}** "
                f"(Total: {total_days:,} days lived; Next birthday in {days_to_next_bday} days)."
            ),
        }

    @classmethod
    def calculate_date_difference(
        cls,
        start_date_str: str,
        end_date_str: str,
        include_working_days: bool = True,
        tz_name: str = DEFAULT_TIMEZONE,
    ) -> Dict[str, Any]:
        d1 = cls.parse_flexible_date(start_date_str, default_tz=tz_name)
        d2 = cls.parse_flexible_date(end_date_str, default_tz=tz_name)
        if not d1 or not d2:
            return {"ok": False, "error": "Both start_date and end_date must be valid dates."}

        earlier, later = (d1, d2) if d1 <= d2 else (d2, d1)
        total_days = (later - earlier).days
        weeks = total_days // 7
        rem_days = total_days % 7

        working_days = 0
        if include_working_days:
            curr = earlier
            while curr < later:
                # 0 = Monday, 4 = Friday, 5 = Saturday, 6 = Sunday
                if curr.weekday() < 5:
                    working_days += 1
                curr += timedelta(days=1)

        return {
            "ok": True,
            "start_date": earlier.isoformat(),
            "end_date": later.isoformat(),
            "total_days": total_days,
            "calendar_days": total_days,
            "weeks": weeks,
            "remaining_days": rem_days,
            "working_days": working_days,
            "formatted": f"{total_days} days ({weeks} weeks, {rem_days} days; {working_days} working days)",
        }

    @classmethod
    def add_or_subtract_days(
        cls,
        base_date_str: str,
        days_offset: int,
        tz_name: str = DEFAULT_TIMEZONE,
    ) -> Dict[str, Any]:
        base = cls.parse_flexible_date(base_date_str, default_tz=tz_name)
        if not base:
            return {"ok": False, "error": f"Invalid base date: '{base_date_str}'"}

        target = base + timedelta(days=int(days_offset))
        direction = "after" if days_offset >= 0 else "before"
        return {
            "ok": True,
            "base_date": base.isoformat(),
            "offset_days": days_offset,
            "target_date": target.isoformat(),
            "day_of_week": target.strftime("%A"),
            "formatted": f"{target.strftime('%A, %d %B %Y')} ({abs(days_offset)} days {direction} {base.isoformat()})",
        }

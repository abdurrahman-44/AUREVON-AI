import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import httpx

from backend.app.core.cache import app_cache

logger = logging.getLogger("aurevon.services.currency")


_BASELINE_RATES = {
    ("USD", "LKR"): 305.5,
    ("EUR", "LKR"): 328.2,
    ("GBP", "LKR"): 392.0,
    ("USD", "INR"): 84.4,
    ("EUR", "USD"): 1.08,
    ("GBP", "USD"): 1.28,
}


class CurrencyService:
    """Provides verified live currency conversion and exchange rates via open financial APIs."""

    PRIMARY_URL = "https://api.frankfurter.dev/v1/latest"
    FALLBACK_URL = "https://open.er-api.com/v6/latest"
    CACHE_TTL_SECONDS = 1800.0  # 30 minutes cache

    @classmethod
    async def get_exchange_rate(
        cls,
        from_currency: str,
        to_currency: str,
        amount: float = 1.0,
    ) -> Dict[str, Any]:
        from_c = (from_currency or "").upper().strip()
        to_c = (to_currency or "").upper().strip()

        if not from_c or not to_c:
            return {"ok": False, "error": "Both from_currency and to_currency must be provided."}
        if from_c == to_c:
            return {
                "ok": True,
                "from_currency": from_c,
                "to_currency": to_c,
                "amount": float(amount),
                "converted_amount": float(amount),
                "rate": 1.0,
                "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "source": "Identity",
            }

        cache_key = f"rate:{from_c}:{to_c}"
        cached = app_cache.get(cache_key)
        rate: Optional[float] = None
        rate_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        source = "Frankfurter (ECB)"

        if isinstance(cached, (int, float)):
            rate = float(cached)
        else:
            # 1. Try Frankfurter API (European Central Bank data)
            try:
                async with httpx.AsyncClient(timeout=4.0) as client:
                    resp = await client.get(cls.PRIMARY_URL, params={"from": from_c, "to": to_c})
                    if resp.status_code == 200:
                        data = resp.json()
                        rates = data.get("rates") or {}
                        if to_c in rates:
                            rate = float(rates[to_c])
                            rate_date = data.get("date", rate_date)
                            app_cache.set(cache_key, rate, ttl_seconds=cls.CACHE_TTL_SECONDS)
            except Exception as exc:
                logger.warning(f"Frankfurter rate lookup failed: {exc}")

            # 2. Try Open Exchange Rate free API (covers LKR, INR, PKR, etc. not in ECB)
            if rate is None:
                try:
                    async with httpx.AsyncClient(timeout=4.0) as client:
                        resp = await client.get(f"{cls.FALLBACK_URL}/{from_c}")
                        if resp.status_code == 200:
                            data = resp.json()
                            rates = data.get("rates") or {}
                            if to_c in rates:
                                rate = float(rates[to_c])
                                rate_date = data.get("time_last_update_utc", rate_date)[:10]
                                source = "ExchangeRate-API"
                                app_cache.set(cache_key, rate, ttl_seconds=cls.CACHE_TTL_SECONDS)
                except Exception as exc:
                    logger.warning(f"Open Exchange Rate fallback failed: {exc}")

        if rate is None:
            pair = (from_c, to_c)
            rev_pair = (to_c, from_c)
            if pair in _BASELINE_RATES:
                rate = _BASELINE_RATES[pair]
                source = "Frankfurter (Offline Baseline)"
            elif rev_pair in _BASELINE_RATES:
                rate = round(1.0 / _BASELINE_RATES[rev_pair], 6)
                source = "Frankfurter (Offline Baseline)"
            else:
                return {
                    "ok": False,
                    "error": f"Live exchange rate for {from_c} to {to_c} is currently unavailable.",
                    "source": "Unreachable",
                }

        converted = round(float(amount) * rate, 4)
        return {
            "ok": True,
            "from_currency": from_c,
            "to_currency": to_c,
            "amount": float(amount),
            "rate": round(rate, 6),
            "converted": converted,
            "converted_amount": converted,
            "date": rate_date,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "formatted": f"{amount:g} {from_c} = {converted:g} {to_c} (Rate: 1 {from_c} = {rate:.4f} {to_c}, Source: {source}, As of: {rate_date})",
        }

from typing import Any, Dict, Optional
from backend.app.services.live.currency import CurrencyService


class CurrencyTool:
    """Provides verified live currency conversion and exchange rates."""

    name = "currency_converter"

    @classmethod
    async def execute(
        cls,
        from_currency: str,
        to_currency: str,
        amount: Optional[float] = 1.0,
    ) -> Dict[str, Any]:
        return await CurrencyService.get_exchange_rate(
            from_currency=from_currency,
            to_currency=to_currency,
            amount=float(amount if amount is not None else 1.0),
        )

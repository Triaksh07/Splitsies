from decimal import Decimal
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models.settlement import ExchangeRate
import httpx
import os

API_KEY = os.getenv("EXCHANGE_RATE_API_KEY", "")
CACHE_TTL_MINUTES = 60
CURRENCY_SYMBOLS = {"INR": "₹", "USD": "$", "GBP": "£"}

# Approximate fallback rates to INR — update periodically
FALLBACK_RATES_TO_INR = {
    "INR": Decimal("1.0"),
    "USD": Decimal("83.5"),
    "GBP": Decimal("106.0"),
}


def get_rate(from_currency: str, to_currency: str, db: Session) -> Decimal:
    if from_currency == to_currency:
        return Decimal("1.0")

    cached = db.query(ExchangeRate).filter(
        ExchangeRate.from_currency == from_currency,
        ExchangeRate.to_currency == to_currency,
    ).first()

    cutoff = datetime.utcnow() - timedelta(minutes=CACHE_TTL_MINUTES)
    if cached and cached.fetched_at > cutoff:
        return cached.rate

    rate = _fetch_rate(from_currency, to_currency)

    if cached:
        cached.rate = rate
        cached.fetched_at = datetime.utcnow()
    else:
        db.add(ExchangeRate(
            from_currency=from_currency,
            to_currency=to_currency,
            rate=rate,
            fetched_at=datetime.utcnow(),
        ))
    db.commit()
    return rate


def _fetch_rate(from_currency: str, to_currency: str) -> Decimal:
    if not API_KEY or API_KEY.startswith("get-free"):
        return _fallback_rate(from_currency, to_currency)
    try:
        url = f"https://v6.exchangerate-api.com/v6/{API_KEY}/pair/{from_currency}/{to_currency}"
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return Decimal(str(resp.json()["conversion_rate"]))
    except Exception:
        return _fallback_rate(from_currency, to_currency)


def _fallback_rate(from_currency: str, to_currency: str) -> Decimal:
    if to_currency == "INR":
        return FALLBACK_RATES_TO_INR.get(from_currency, Decimal("1.0"))
    if from_currency == "INR":
        return Decimal("1.0") / FALLBACK_RATES_TO_INR.get(to_currency, Decimal("1.0"))
    from_inr = FALLBACK_RATES_TO_INR.get(from_currency, Decimal("1.0"))
    to_inr = FALLBACK_RATES_TO_INR.get(to_currency, Decimal("1.0"))
    return from_inr / to_inr


def convert_to_inr(amount: Decimal, from_currency: str, db: Session) -> Decimal:
    """Always call this at expense entry time. Never re-convert historical records."""
    rate = get_rate(from_currency, "INR", db)
    return (amount * rate).quantize(Decimal("0.01"))


def convert_from_inr(amount_inr: Decimal, to_currency: str, db: Session) -> Decimal:
    rate = get_rate("INR", to_currency, db)
    return (amount_inr * rate).quantize(Decimal("0.01"))


def format_amount(amount: Decimal, currency: str) -> str:
    symbol = CURRENCY_SYMBOLS.get(currency, currency)
    return f"{symbol}{amount:,.2f}"

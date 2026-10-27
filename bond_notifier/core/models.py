from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

@dataclass
class Bond:
    secid: str          # ISIN или тикер
    user_id: int
    added_at: datetime

@dataclass
class CouponPayment:
    secid: str
    coupon_date: date
    value: Optional[float]   # сумма купона в рублях
    value_percent: Optional[float]
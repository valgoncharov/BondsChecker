from dataclasses import dataclass
from datetime import date, datetime


@dataclass
class Bond:
    secid: str
    user_id: int
    added_at: datetime | None = None


@dataclass
class CouponPayment:
    secid: str
    coupon_date: date
    value: float | None
    value_percent: float | None
    value_rub: float | None = None
    faceunit: str | None = None
    recorddate: date | None = None
    name: str | None = None
    isin: str | None = None


@dataclass
class SecurityInfo:
    secid: str
    shortname: str | None = None
    isin: str | None = None
    type: str | None = None
    group: str | None = None
    is_traded: bool = False
    emitent_title: str | None = None


@dataclass
class UpcomingCoupon:
    secid: str
    shortname: str | None
    isin: str | None
    coupondate: str
    value_rub: float | None
    value: float | None
    faceunit: str | None


@dataclass
class DueNotification:
    user_id: int
    chat_id: int
    secid: str
    shortname: str | None
    coupondate: str
    value_rub: float | None
    value: float | None
    faceunit: str | None
